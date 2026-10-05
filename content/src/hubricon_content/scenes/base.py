"""The Manim base every chart scene inherits.

A scene renders exactly one timeline segment: it knows when it starts, how
long it lasts, and at what second each `{{key}}` in the narration is spoken,
so a number can appear the instant it is said. Charts build progressively
(axes, then data, then annotation) and every data landing is written to
`events.json`, where the sound design picks it up as a tick.

The look is the film stage's (VISUAL_SPEC.md §8.4): paper ground, ink lines,
rule-2 axes, blue only on money and the leak, Inter Display at the stage's own
sizes and margins, the corner with its label and the mark. Every colour comes
from content/assets/tokens.json and every size from the stage's CSS, through
tokens.stage(), so a Manim chart and a stage chart in one film read as one film.
"""

import functools
import json
import math
import os
import re
from pathlib import Path

import numpy as np
from PIL import ImageFont
from manim import (DOWN, LEFT, ORIGIN, RIGHT, UP, Axes, Circle, DashedLine, FadeIn, FadeOut, Polygon, RoundedRectangle,
                   Scene, Text, VGroup, VMobject, config, linear, smooth)

from .. import subtitles, tokens

try:
    tokens.register_fonts()
except Exception:
    pass

PAPER = tokens.colour("paper")
INK = tokens.colour("ink")
INK_2 = tokens.colour("ink_2")
INK_3 = tokens.colour("ink_3")
INK_4 = tokens.colour("ink_4")
RULE = tokens.colour("rule")
RULE_2 = tokens.colour("rule_2")
BLUE = tokens.colour("blue")
FONT = tokens.family(display=True)
T = tokens.load()
S = tokens.stage()

# Pango's em for one unit of Manim font_size (measured from Inter's cap height,
# 0.7275 em, on 2026-10-04).
EM_PER_FONT_SIZE = 0.013880
# Inter's vertical metrics (units per em 2048): where CSS puts the baseline in a line box.
ASCENT, DESCENT = 1984 / 2048, 494 / 2048
# Glyphs that sit flat on the baseline; their bottoms find it.
FLAT = set("ABDEFHIKLMNPRTXZhiklmnrxz1247")
# The film stage draws the site's SVG charts 1200 wide in a 1600 px frame, so a
# chart's px tokens (line weights, 30 px labels) land 4/3 larger on screen.
CHART_SCALE = 4 / 3

# The right column's stat captions: how wide they wrap and how many lines they keep.
CALLOUT_W, CALLOUT_LINES = 340, 4

# The cadence (VISUAL_SPEC.md §4, which retires the bible's two-to-four seconds):
# a shot runs seven to eleven seconds, never past fourteen, and never under three;
# a spoken figure holds three seconds before the cut. A segment of narration is
# longer than any one shot, so a scene cuts inside itself.
SHOT_S, SHOT_MAX_S, SHOT_MIN_S, FIGURE_HOLD_S = 9.0, 14.0, 3.0, 3.0
# A kinetic card: how wide its line wraps, and the size it drops to when a long
# sentence would run past four lines.
CARD_CH, CARD_LINES, CARD_SMALL_PX = 22, 4, 56

STYLE = {
    "palette": T["colour"],
    "type": {"family": FONT, **{k: v for k, v in S.items() if k.endswith("_px") and not isinstance(v, list)}},
    "chart": {"axis": "rule_2", "text": "ink_3", "line_px": T["line"]["step"] * CHART_SCALE,
              "leak_px": T["line"]["leak"] * CHART_SCALE, "hair_px": T["line"]["hair"] * CHART_SCALE,
              "label_px": 30 * CHART_SCALE, "band_opacity": T["chart"]["band"], "path_opacity": T["chart"]["path_rest"],
              "path_draw_opacity": T["chart"]["path_draw"],
              "build_axes_s": 0.9, "build_data_s": 2.2, "annotation_s": 0.55, "drift_scale": 1.015},
    "cards": {"chapter_px": 96, "hairline_px": 120, "hold_s": 2.5},
    "restraint": {"blue": "money and the leak only", "blue_elements_per_frame": 1, "callouts_visible": 2,
                  "reveal_rate_func": "smooth", "no_gradients_or_glows": True},
}

# The drift that replaces a frozen hold (§3.4): the stage grows 1.000 → 1.015 over a
# shot, so the rate below is per second at the nominal shot length and a picture's
# drift starts again at each cut. A held picture that runs long would otherwise swell,
# so the drift turns around at the cap and comes back down: the picture is always
# moving and never reads as a zoom.
DRIFT_RATE = STYLE["chart"]["drift_scale"] ** (1 / SHOT_S)
DRIFT_CAP = 1.03
# §4: a chart build may hold up to thirty seconds before the picture has to change.
# The scene's own clock stops short of that, so the cut lands on a sentence inside the
# stretch rather than on the thirtieth second, and the measured interval between cuts
# keeps a margin under the limit QA reads (V01's QA, 2026-10-05).
BUILD_MAX_S, BUILD_CUT_S = 30.0, 20.0


def cubic_bezier(x1: float, y1: float, x2: float, y2: float):
    """A CSS cubic-bezier() timing function as a Manim rate_func."""
    def bez(t, a, b):
        return 3 * a * (1 - t) ** 2 * t + 3 * b * (1 - t) * t ** 2 + t ** 3

    def rate(x: float) -> float:
        if x <= 0 or x >= 1:
            return float(min(1.0, max(0.0, x)))
        t = x
        for _ in range(12):   # Newton on x(t) = x
            dx = 3 * x1 * (1 - t) ** 2 + 6 * (x2 - x1) * (1 - t) * t + 3 * (1 - x2) * t ** 2
            t = min(1.0, max(0.0, t - (bez(t, x1, x2) - x) / dx)) if dx else t
        return bez(t, y1, y2)
    return rate


EASE_OUT = cubic_bezier(*T["ease_out"])          # the site's --ease-out: every entrance
EASE_STILL = cubic_bezier(0.37, 0, 0.63, 1)      # VISUAL_SPEC §3.4: the slow move on a still
ENTER_S, ENTER_RISE_PX = 0.7, 18                 # film.css .in: 700 ms, 18 px


def fit(m, max_width: float):
    """Shrink a mobject to a maximum width. Manim 0.21's set_max_width is a
    deprecated no-op, so the clamp lives here."""
    if m.width > max_width:
        m.scale_to_fit_width(max_width)
    return m


def money(v: float, digits: int = 0) -> str:
    v = float(v)
    if abs(v) >= 1e6:
        return ("−" if v < 0 else "") + f"${abs(v) / 1e6:.1f}M"
    if abs(v) >= 1e3 and digits == 0:
        return ("−" if v < 0 else "") + f"${abs(v) / 1e3:,.0f}k"
    return ("−" if v < 0 else "") + f"${abs(v):,.{digits}f}"


def is_money(value: str) -> bool:
    """Blue is for money and the leak: a spoken figure in dollars."""
    return "$" in str(value)


def nice_step(lo: float, hi: float, n: int = 5) -> float:
    raw = (hi - lo) / max(1, n)
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


# ── units: the stage is laid out in px; Manim in frame units ──
def px() -> float:
    """Frame units per pixel of the frame being rendered."""
    return config.frame_height / config.pixel_height


def font_size(size_px: float) -> float:
    return size_px * px() / EM_PER_FONT_SIZE


def stroke(size_px: float) -> float:
    """Manim's stroke_width for a line this many px wide (cairo draws 0.01 frame units per unit)."""
    return size_px * px() / 0.01


def at(x_px: float, y_px: float) -> np.ndarray:
    """A point given in px from the frame's top-left, as the stage's CSS gives it."""
    return np.array([(x_px - config.pixel_width / 2) * px(), (config.pixel_height / 2 - y_px) * px(), 0.0])


def baseline(m: Text) -> float:
    """The y of a line's baseline: the bottom of its flat-footed glyphs."""
    pairs = list(zip(m.hc_text, m.submobjects))
    glyphs = [g for ch, g in pairs if ch in FLAT and g.has_points()]
    if not glyphs:
        glyphs = [g for ch, g in pairs if ch not in "gjpqyQ,;()[]{}" and g.has_points()] or m.submobjects
    return float(np.median([g.get_bottom()[1] for g in glyphs]))


@functools.lru_cache(maxsize=64)
def _face(display: bool, weight: int, size_px: float):
    """Pillow's view of the font, shaped by libraqm so kerning counts as it does in Chrome."""
    return ImageFont.truetype(str(tokens.font_file(weight, display)), size_px, layout_engine=ImageFont.Layout.RAQM)


@functools.lru_cache(maxsize=4)
def _metrics(display: bool, weight: int):
    from fontTools.ttLib import TTFont
    f = TTFont(str(tokens.font_file(weight, display)), lazy=True)
    return f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm


def bearing(c: str, size_px: float, weight: int = 600) -> float:
    """A glyph's left side bearing in px: where its ink starts after its origin."""
    cmap, hmtx, upm = _metrics(True, weight)
    g = cmap.get(ord(c))
    return hmtx[g][1] / upm * size_px if g else 0.0


def _opsz(size_px: float) -> float:
    """How far toward the Display cut Chrome's optical sizing sets this size: 0 at 14 px, 1 from 32 px."""
    return min(1.0, max(0.0, (size_px - 14) / 18))


def advance(s: str, size_px: float, weight: int = 600, track_em: float = 0.0) -> float:
    """The width CSS gives a line, in px: the glyph advances at this optical size,
    plus letter-spacing after every character (the browser adds it after the last too)."""
    t = _opsz(size_px)
    a = _face(True, weight, size_px).getlength(s)
    if t < 1:
        a = t * a + (1 - t) * _face(False, weight, size_px).getlength(s)
    return a + track_em * size_px * len(s)


def type_line(text: str, size_px: float, colour: str = INK, weight: int = 600, track_em: float = 0.0,
              upper: bool = False) -> Text:
    """One line of Inter as the stage sets it: the Display cut, widened toward the
    text cut below 32 px as optical sizing does, letter-spacing included."""
    s = text.upper() if upper else text
    m = Text(s, font=FONT, font_size=font_size(size_px), weight="SEMIBOLD" if weight >= 500 else "NORMAL",
             color=colour, disable_ligatures=True)
    m.hc_text, m.hc_size, m.hc_weight = s, size_px, weight
    if _opsz(size_px) < 1 and s.strip():
        wide = advance(s, size_px, weight) / _face(True, weight, size_px).getlength(s)
        m.stretch(wide, 0, about_edge=LEFT)
    if track_em:
        step = track_em * size_px * px()
        for i, g in enumerate(m.submobjects):
            g.shift(RIGHT * step * i)
    return m


def place(m: Text, left_px: float, baseline_px: float) -> Text:
    """Put a line's origin at left_px (its first glyph's side bearing in from
    there, as CSS draws it) and its baseline at baseline_px."""
    lsb = bearing(m.hc_text.lstrip()[:1] or "0", m.hc_size, m.hc_weight)
    m.shift(RIGHT * (at(left_px + lsb, 0)[0] - m.get_left()[0]) + UP * (at(0, baseline_px)[1] - baseline(m)))
    return m


def first_baseline(top_px: float, size_px: float, line_height: float) -> float:
    """Where CSS draws the first baseline of a block whose line box starts at top_px."""
    return top_px + ((line_height - (ASCENT + DESCENT)) / 2 + ASCENT) * size_px


def _greedy(words: list[str], size_px: float, max_px: float, weight: int, track_em: float) -> list[str]:
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        # the trailing letter-spacing does not count against the box, as in the browser
        if cur and advance(trial, size_px, weight, track_em) - track_em * size_px > max_px:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    return lines + ([cur] if cur else [])


def block(text: str, size_px: float, max_px: float, colour: str = INK, weight: int = 600, track_em: float = 0.0,
          wrap: str = "pretty") -> list[Text]:
    """A paragraph wrapped to max_px as the stage wraps it: `balance` for headings
    (h1–h3, .display), `pretty` for paragraphs (no word alone on the last line)."""
    words = text.split()
    lines = _greedy(words, size_px, max_px, weight, track_em)
    if wrap == "balance" and len(lines) > 1:
        lo, hi = max_px / len(lines), max_px      # the narrowest box that keeps the same number of lines
        for _ in range(16):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if len(_greedy(words, size_px, mid, weight, track_em)) > len(lines) else (lo, mid)
        lines = _greedy(words, size_px, hi, weight, track_em)
    elif wrap == "pretty" and len(lines) > 1 and len(lines[-1].split()) == 1 and len(lines[-2].split()) > 2:
        head, last = lines[-2].rsplit(" ", 1)
        lines[-2:] = [head, last + " " + lines[-1]]
    return [type_line(ln, size_px, colour, weight, track_em) for ln in lines]


def fit_clause(text: str, size_px: float, max_px: float, lines: int, weight: int = 400) -> str:
    """The longest leading clause of `text` that wraps inside `lines`. A caption
    cut by line count stops mid-sentence and loses the words that say what the
    figure is of; cutting at a comma leaves a whole thought."""
    parts = text.split(", ")
    for i in range(len(parts), 1, -1):
        if len(_greedy(", ".join(parts[:i]).split(), size_px, max_px, weight, 0.0)) <= lines:
            return ", ".join(parts[:i])
    return parts[0]


def sentences(words: list[dict]) -> list[dict]:
    """The narration's sentences with the second each is spoken, read off the
    alignment. A sentence is where a kinetic card can cut, because the cut lands
    in the pause the speaker already takes."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.!?][\"')\]]?$", str(w.get("word", ""))):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [{"text": " ".join(str(w["word"]) for w in g), "start": float(g[0]["start"]), "end": float(g[-1]["end"])}
            for g in out if g]


def phrases(words: list[dict], min_s: float = SHOT_MIN_S, max_s: float = SHOT_MAX_S) -> list[dict]:
    """The sentences grouped into shots the cadence allows: a sentence shorter
    than the minimum shot joins the one after it, so a card is never a flash."""
    out: list[dict] = []
    for s in sentences(words):
        prev = out[-1] if out else None
        if prev and prev["end"] - prev["start"] < min_s and s["end"] - prev["start"] <= max_s:
            prev.update(text=f"{prev['text']} {s['text']}", end=s["end"])
        else:
            out.append(dict(s))
    if len(out) > 1 and out[-1]["end"] - out[-1]["start"] < min_s:
        last = out.pop()
        out[-1].update(text=f"{out[-1]['text']} {last['text']}", end=last["end"])
    return out


def stack(lines: list[Text], left_px: float, top_px: float, size_px: float, line_height: float) -> tuple[VGroup, float]:
    """Lay wrapped lines down from top_px; returns the group and the block's bottom in px."""
    b = first_baseline(top_px, size_px, line_height)
    for i, ln in enumerate(lines):
        place(ln, left_px, b + i * line_height * size_px)
    return VGroup(*lines), top_px + len(lines) * line_height * size_px


def ch(size_px: float, weight: int = 600) -> float:
    """CSS's ch: the advance of the zero."""
    return advance("0", size_px, weight)


class HubriconScene(Scene):
    def setup(self):
        ctx = json.loads(os.environ["HC_CONTEXT"])
        self.d = Path(ctx["dir"])
        self.seg = ctx["segment"]
        self.vertical = bool(ctx.get("vertical"))
        self.run = json.loads((self.d / "run.json").read_text(encoding="utf-8"))
        self.facts = json.loads((self.d / "facts.json").read_text(encoding="utf-8"))
        self.length = float(self.seg["end"]) - float(self.seg["start"])
        self.events = []
        self.camera.background_color = PAPER
        self.W = config.frame_width
        self.H = config.frame_height
        self.Wpx, self.Hpx = config.pixel_width, config.pixel_height
        # The stage's padding (film.css .scene); the vertical cut keeps its bottom for the subtitles.
        top, side, bottom = S["pad_px"]
        self.pad = {"top": top, "side": side if not self.vertical else 96, "bottom": bottom if not self.vertical else 520,
                    "chart_top": S["pad_top_chart_px"] if not self.vertical else 200}
        # Tier D burns nothing (VISUAL_SPEC.md §8.6); everything else burns a block
        # at the bottom, and the picture keeps out of it.
        self.sub_band = 0.0 if str(ctx.get("tier", "")).upper() == "D" else subtitles.band_px(self.vertical)
        self.chart_top = None
        self.callout_stack = VGroup()
        self.entering = []
        self.shot_mobs = []
        # What the drift moves, what it pivots on, how far it has moved and which way,
        # and when the picture now on screen came up. The segment's own first frame is
        # a cut, so the clock starts at zero.
        self.stage_group, self.stage_about = None, None
        self._drift_f, self._drift_dir, self._shot_since = 1.0, 1, 0.0
        self.furniture = self.corner()

    # ── clock ──
    def _trace(self, what: str):
        if os.environ.get("HC_DEBUG"):
            import sys
            print(f"[hc] {what:28s} clock={self.clock:7.2f} rendered={self.renderer.time:7.2f}", file=sys.stderr)

    @property
    def clock(self) -> float:
        """Seconds rendered so far. The renderer's own count, because Manim's
        wait() is itself a play() and a hand-kept tally double-counts it."""
        return float(self.renderer.time)

    def enter(self, *mobs):
        """The stage's entrance (film.css .in): rise 18 px and fade in, ease-out.
        It plays alongside the scene's next animation, so it costs no time."""
        for m in mobs:
            self.entering.append(FadeIn(m, shift=UP * ENTER_RISE_PX * px(), rate_func=EASE_OUT))

    def play(self, *anims, **kw):
        if self.entering:
            anims, self.entering = (*self.entering, *anims), []
        rt = kw.get("run_time") or max((getattr(a, "run_time", 1.0) for a in anims), default=1.0)
        super().play(*anims, **kw)
        self._trace(f"play {rt:.2f}")

    def wait(self, duration=1.0, **kw):
        if self.entering and duration > 0.01:
            first = min(duration, ENTER_S)
            self.play(run_time=first)
            duration -= first
        if duration > 0.01:
            super().wait(duration, **kw)

    def wait_until(self, t: float):
        self.wait(max(0.0, t - self.clock))

    def rel(self, key: str):
        r = self.seg.get("reveals", {}).get(key)
        return None if not r else max(0.0, float(r["t"]) - float(self.seg["start"]))

    @property
    def position(self) -> int | None:
        """Which clip of the timeline this scene is, and the key its landings are
        filed under. A beat carries its own number and a chapter card carries none,
        so a card falls back to its place in the timeline and the two numbering
        schemes collide: on V01 the third beat and the first card were both 3, and
        the card's render wiped that chart segment's six landings out of
        events.json, which is where the sound design reads its ticks."""
        p = self.seg.get("position")
        return p if p is not None else self.seg.get("index")

    def landed(self, kind: str = "data"):
        self.events.append({"t": round(float(self.seg["start"]) + self.clock, 3), "kind": kind, "segment": self.position})

    # ── furniture: the stage's corner (film.css .corner), on every frame ──
    def label_text(self) -> str | None:
        """The honesty label: the proof label on a case-study figure, else the
        demo label, since every Manim figure comes from the demo catalogue's run."""
        if self.seg.get("proof"):
            return "Modeled from public data · Not a client · Not a result"
        brand = self.facts.get("demo_brand", {}).get("value")   # facts.DEMO_LABEL, from the unit's own facts
        return f"{brand} demo data" if brand else "demo data"

    def corner(self):
        side = self.pad["side"]
        bottom = self.Hpx - S["corner_bottom_px"]
        size, (pad_y, pad_x) = S["label_px"], S["label_pad_px"]
        row = size * 1.6 + 2 * pad_y + 2   # the label box: line-height 1.6, its padding, a 1 px border
        mid = bottom - row / 2
        parts = VGroup()
        text = self.label_text()
        if text:
            lab = type_line(text, size, INK_3, 600, S["label_track_em"], upper=True)
            place(lab, side + 1 + pad_x, first_baseline(bottom - row + 1 + pad_y, size, 1.6))
            w = advance(lab.hc_text, size, 600, S["label_track_em"]) + 2 * pad_x + 2
            box = RoundedRectangle(width=w * px(), height=row * px(), corner_radius=6 * px(),
                                   stroke_color=RULE_2, stroke_width=stroke(1), fill_opacity=0)
            box.move_to(at(side + w / 2, mid))
            parts.add(box, lab)
        size, icon = S["mark_px"], S["mark_icon_px"]
        name = type_line("Hubricon", size, INK, 600, S["mark_track_em"])
        right = self.Wpx - side
        origin = right - advance("Hubricon", size, 600, S["mark_track_em"])
        place(name, origin, mid - (ASCENT + DESCENT) * size / 2 + ASCENT * size)
        cx, k = origin - 12 - icon / 2, icon / 64
        ring = Circle(radius=27 * k * px(), stroke_color=INK, stroke_width=stroke(5 * k)).move_to(at(cx, mid))
        h = [(22.5, 18), (29, 18), (29, 29), (35, 29), (35, 18), (41.5, 18), (41.5, 46), (35, 46), (35, 35.5),
             (29, 35.5), (29, 46), (22.5, 46)]
        glyph = Polygon(*[at(cx + (x - 32) * k, mid + (y - 32) * k) for x, y in h], fill_color=INK, fill_opacity=1,
                        stroke_width=0)
        parts.add(ring, glyph, name)
        self.add(parts)
        return parts

    def demo_label(self):
        """The corner carries the label now; kept so older scenes still run."""
        return None

    def heading(self, text: str, caption: str | None = None) -> float:
        """A chart scene's top block (film.css .scene.top: .heading, then .caption),
        drawn at once. Returns the px where the chart starts."""
        left = self.pad["side"]
        width = self.Wpx - 2 * left
        lines = block(text, S["heading_px"], min(width, 28 * ch(S["heading_px"])), INK, 600, S["heading_track_em"], "balance")
        g, bottom = stack(lines, left, self.pad["chart_top"], S["heading_px"], 1.1)
        self.enter(g)
        if caption:
            cl = block(caption, S["caption_px"], min(width, 46 * ch(S["caption_px"], 400)), INK_2, 400)
            cg, bottom = stack(cl, left, bottom + 24, S["caption_px"], 1.4)
            self.enter(cg)
        self.chart_top = bottom + 32
        return self.chart_top

    def caption(self, text: str, size: int = 0):
        """A chart's title line, set as the stage's heading."""
        return self.heading(text)

    def big_number(self, value: str, label: str, size: int = 0):
        """film.css .number over .number-sub, centred in the stage: blue when it is money."""
        num = type_line(value, S["number_px"], BLUE if is_money(value) else INK, 600, S["number_track_em"])
        sub = block(label, S["number_sub_px"], 26 * ch(S["number_sub_px"]), INK, 600, S["number_sub_track_em"]) if label else []
        left = self.pad["side"]
        # .number-sub inherits the page's line-height, 1.6
        height = S["number_px"] + (32 + len(sub) * 1.6 * S["number_sub_px"] if sub else 0)
        top = self.pad["top"] + (self.Hpx - self.pad["top"] - self.floor() - height) / 2
        place(num, left, first_baseline(top, S["number_px"], 1.0))
        g, _ = stack(sub, left, top + S["number_px"] + 32, S["number_sub_px"], 1.6)
        return VGroup(num, *g)

    def floor(self) -> float:
        """The bottom margin the picture keeps: the stage's own, or the burned-in
        subtitles' band when that is deeper, so no line of type lands on the words."""
        return max(self.pad["bottom"], self.sub_band)

    # ── shots: a segment of narration is cut into the cadence's shots (§4) ──
    def type_card(self, text: str) -> VGroup:
        """One sentence of the narration as the stage's display line, centred in
        the stage; a long sentence drops a size rather than running off the page."""
        size = S["display_small_px"]
        width = min(self.Wpx - 2 * self.pad["side"], CARD_CH * ch(size))
        lines = block(text, size, width, INK, 600, S["display_track_em"], "balance")
        if len(lines) > CARD_LINES:
            size = CARD_SMALL_PX
            width = min(self.Wpx - 2 * self.pad["side"], (CARD_CH + 8) * ch(size))
            lines = block(text, size, width, INK, 600, S["display_track_em"], "balance")
        height = len(lines) * 1.04 * size
        top = self.pad["top"] + (self.Hpx - self.pad["top"] - self.floor() - height) / 2
        g, _ = stack(lines, self.pad["side"], top, size, 1.04)
        return g

    def cut_to(self, mob, until: float):
        """The next shot: what was on the stage is gone in one frame (a hard cut,
        never a dissolve), the new picture is up, and it drifts while it is held so
        nothing on screen is ever frozen (§3.4)."""
        for old in list(self.shot_mobs):
            self.remove(old)
        self.shot_mobs = [mob]
        self.add(mob)
        self.landed("annotation")
        self._drift_f, self._drift_dir, self._shot_since = 1.0, 1, self.clock
        self.drift(max(0.0, until - self.clock), group=mob)

    # ── the drift, and the hold that cuts rather than sit still (§3.4, §4) ──
    def stage(self, group, about=None):
        """What the drift moves and what a cut away comes back to: the picture this
        scene drew, the corner's furniture excepted. `about` is the blue the drift is
        centred on; without one it pivots on the stage's anchor."""
        if group is not self.stage_group:
            self._drift_f, self._drift_dir = 1.0, 1
        self.stage_group, self.stage_about = group, about
        return group

    def anchor(self) -> np.ndarray:
        """Where a drift pivots when the scene names no blue: the bottom left of the
        live stage, where its grid starts. A picture scaled about its own centre
        travels too little to read as motion, and a card drifting about itself is what
        freezedetect called a frozen frame (V01's QA, 2026-10-05)."""
        return at(self.pad["side"], self.Hpx - self.floor())

    def _pivot(self, about, group) -> np.ndarray:
        if about is None and group is self.stage_group:
            about = self.stage_about
        if about is None:
            return self.anchor()
        return about if isinstance(about, np.ndarray) else about.get_center()

    def drift(self, seconds: float, group=None, about=None):
        """Hold a picture by drifting it rather than freezing it (§3.4): 1.000 → 1.015
        over a shot, centred on the blue, turning around at the cap so a long hold
        never swells into a zoom."""
        if seconds <= 0.05:
            return
        g = self.stage_group if group is None else group
        if g is None:
            self.wait(seconds)
            return
        own = g is self.stage_group
        if own:
            if self._drift_f >= DRIFT_CAP:
                self._drift_dir = -1
            elif self._drift_f <= 1.0:
                self._drift_dir = 1
        f = DRIFT_RATE ** (seconds * (self._drift_dir if own else 1))
        if own:
            self._drift_f *= f
        self.play(g.animate.scale(f, about_point=self._pivot(about, g)), run_time=seconds, rate_func=linear)

    def spoken_at(self, t: float) -> str | None:
        """The narration's sentence being spoken `t` seconds into the segment, so a cut
        away from the chart lands on the line the viewer is hearing."""
        ps = phrases(self.seg.get("words") or [])
        if not ps:
            vo = (self.seg.get("vo") or "").strip()
            return re.split(r"(?<=[.!?])\s", vo, maxsplit=1)[0] if vo else None
        start = float(self.seg["start"])
        said = [p for p in ps if p["start"] - start <= t + 0.25]
        return (said[-1] if said else ps[0])["text"]

    def cut_away(self, seconds: float):
        """A hard cut from the chart to the sentence being spoken, and back to the
        chart in the framing it was drawn in (§14.5 C3). The cadence will not hold one
        picture over a long segment, and a chart with an annotation landing on it is
        not a cut: the detector reads a change of picture, not a change inside one."""
        g = self.stage_group
        text = self.spoken_at(self.clock)
        if g is None or not text:
            self.drift(seconds)
            return
        card = self.type_card(text)
        # the whole paper stage gives way, not only the chart: a card drawn under the
        # chart's own heading, with its stat rail still standing, is not a cut, and it
        # puts five blocks of type on one frame (V01's frames, 2026-10-05)
        hidden = [m for m in self.mobjects if m is not self.furniture]
        for m in hidden:
            self.remove(m)
        self.add(card)
        self.landed("annotation")
        self._shot_since = self.clock
        self.drift(seconds, group=card)
        self.remove(card)
        if self._drift_f != 1.0:
            g.scale(1 / self._drift_f, about_point=self._pivot(None, g))
        self._drift_f, self._drift_dir, self._shot_since = 1.0, 1, self.clock
        for m in hidden:
            self.add(m)
        self.landed("annotation")

    def hold_to(self, until: float):
        """Hold the stage until `until` seconds into the segment: drifting, never
        frozen (§3.4), and never one picture past the cadence (§4). A stretch longer
        than the chart's clock allows cuts away to the narration and comes back."""
        while True:
            rest = until - self.clock
            if rest <= 0.05:
                return
            if self.stage_group is None:
                self.wait(rest)
                return
            # what the picture now up may still hold: its own shot's maximum, and
            # what is left of the build's clock, whichever runs out first
            room = min(SHOT_MAX_S, max(0.0, BUILD_CUT_S - (self.clock - self._shot_since)))
            if rest <= room or rest < SHOT_MIN_S:
                self.drift(rest)
                return
            # the chart holds what it may, keeping back a shot for the line and a shot
            # for its own return, so the annotation at `until` lands on the chart
            self.drift(min(room, max(0.0, rest - 2 * SHOT_MIN_S)))
            card_s = min(SHOT_S, until - self.clock - SHOT_MIN_S)
            if card_s < SHOT_MIN_S:
                self.drift(max(0.0, until - self.clock))
                return
            self.cut_away(card_s)

    # ── charts, in the site's chart grammar (assets/hubricon.css .chart) ──
    def plot_box(self) -> tuple[float, float, float, float]:
        """The plot area in px: below the heading, inside the stage, the right
        column kept for the spoken figures, the floor clear of the burned-in
        subtitles so the words never land on the axis's own labels."""
        top = self.chart_top or self.pad["chart_top"] + 120
        left = self.pad["side"] + 170
        right = self.Wpx - self.pad["side"] - (380 if not self.vertical else 0)
        bottom = self.Hpx - max(self.pad["bottom"], self.sub_band) - 70
        return left, top, right, bottom

    def axes(self, x_range, y_range, x_len=None, y_len=None, room_px: float = 0):
        """Axes filling the plot box; room_px lifts the floor for labels that wrap."""
        left, top, right, bottom = self.plot_box()
        bottom -= room_px
        ax = Axes(x_range=x_range, y_range=y_range, x_length=x_len or (right - left) * px(),
                  y_length=y_len or (bottom - top) * px(), tips=False,
                  axis_config={"stroke_color": RULE_2, "stroke_width": stroke(STYLE["chart"]["hair_px"]),
                               "include_ticks": False, "include_numbers": False})
        ax.shift(at(left, bottom) - ax.c2p(x_range[0], y_range[0]))
        return ax

    def chart_text(self, text: str, colour: str = INK_3, weight: int = 400) -> Text:
        return type_line(text, STYLE["chart"]["label_px"], colour, weight)

    def axis_numbers(self, ax, xs, ys, xfmt=str, yfmt=money):
        g = VGroup()
        for x in xs:
            t = self.chart_text(xfmt(x))
            # the first label starts at the axis, so it never sits under the y axis's own
            t.next_to(ax.c2p(x, ax.y_range[0]), DOWN, buff=16 * px(), aligned_edge=LEFT if x <= ax.x_range[0] else ORIGIN)
            g.add(t)
        for y in ys:
            g.add(self.chart_text(yfmt(y)).next_to(ax.c2p(ax.x_range[0], y), LEFT, buff=16 * px()))
        return g

    def polyline(self, ax, xs, ys, color=INK, width=None, opacity=1.0):
        v = VMobject(stroke_color=color, stroke_width=width if width is not None else stroke(STYLE["chart"]["line_px"]),
                     stroke_opacity=opacity)
        v.set_points_as_corners([ax.c2p(x, y) for x, y in zip(xs, ys)])
        return v

    def leak_line(self, ax, xs, ys):
        """The money line: blue, at the leak's weight."""
        return self.polyline(ax, xs, ys, BLUE, stroke(STYLE["chart"]["leak_px"]))

    def band(self, ax, xs, lo, hi, color=BLUE, opacity=None):
        pts = [ax.c2p(x, y) for x, y in zip(xs, lo)] + [ax.c2p(x, y) for x, y in zip(reversed(list(xs)), reversed(list(hi)))]
        return Polygon(*pts, fill_color=color, fill_opacity=opacity or STYLE["chart"]["band_opacity"], stroke_width=0)

    def dashed(self, a, b, color=INK_3):
        """The site's .step-alt: ink-3, 1.25 px, dashed 5 on 4."""
        return DashedLine(a, b, color=color, stroke_width=stroke(1.25 * CHART_SCALE), dash_length=5 * CHART_SCALE * px(),
                          dashed_ratio=5 / 9)

    def callout(self, value: str, label: str, at_=None, color=None):
        """A number and what it is, stacked in the chart's right column; the
        default way an unhandled spoken figure gets on screen the moment it is said."""
        val = type_line(value, 72, color or (BLUE if is_money(value) else INK), 600, S["heading_track_em"])
        lab = block(fit_clause(label, 36, CALLOUT_W, CALLOUT_LINES), 36, CALLOUT_W, INK_3, 400)[:CALLOUT_LINES]
        blk = VGroup(val, *lab)
        # one blue element per frame: the figure being spoken. Earlier ones step back to ink.
        for prev in self.callout_stack:
            prev[0].set_color(INK)
        if len(self.callout_stack) >= STYLE["restraint"]["callouts_visible"]:
            old = self.callout_stack[0]
            self.callout_stack.remove(old)
            self.play(FadeOut(old), run_time=0.25)
        self.callout_stack.add(blk)
        self._lay_callouts()
        self.play(FadeIn(blk, shift=UP * 18 * px()), run_time=STYLE["chart"]["annotation_s"], rate_func=smooth)
        self.landed("annotation")
        return blk

    def _lay_callouts(self):
        _, top, right, _ = self.plot_box()
        left, y = right + 48, top
        for blk in self.callout_stack:
            val, *lab = blk
            place(val, left, first_baseline(y, 72, 1.0))
            _, bottom = stack(lab, left, y + 72 + 12, 36, 1.25)
            y = bottom + 40

    def reveal_loop(self, handlers: dict | None = None, skip: set | None = None):
        """Walk the spoken figures in time order; a handler draws the special
        ones, everything else becomes a callout."""
        handlers = handlers or {}
        skip = skip or set()
        reveals = sorted(self.seg.get("reveals", {}).items(), key=lambda kv: kv[1]["t"])
        for key, r in reveals:
            if key in skip:
                continue
            t = max(0.0, float(r["t"]) - float(self.seg["start"]))
            self.hold_to(t)
            fact = self.facts.get(key, {})
            if key in handlers:
                for prev in self.callout_stack:   # the annotation takes the blue; earlier figures step back
                    prev[0].set_color(INK)
                handlers[key](fact.get("value", r.get("value", "")), fact.get("label", ""))
            else:
                self.callout(fact.get("value", r.get("value", "")), fact.get("label", key))

    def finish(self, group=None, about=None):
        """Hold the rest of the segment the way §3.4 and §4 say: the stage drifting,
        centred on the blue, never frozen, and cutting away to the narration when the
        tail runs past what one picture may hold, rather than sitting on the chart to
        the end of the segment."""
        if group is not None:
            self.stage(group, about)
        self.hold_to(self.length)
        ev = self.d / "events.json"
        existing = json.loads(ev.read_text(encoding="utf-8")) if ev.exists() else []
        existing = [e for e in existing if e.get("segment") != self.position] + self.events
        ev.write_text(json.dumps(sorted(existing, key=lambda e: e["t"])) + "\n", encoding="utf-8")
        self._trace("finish")
