"""The Manim base every chart scene inherits.

A scene renders exactly one timeline segment: it knows when it starts, how
long it lasts, and at what second each `{{key}}` in the narration is spoken,
so a number can appear the instant it is said. Charts build progressively
(axes, then data, then annotation) and every data landing is written to
`events.json`, where the sound design picks it up as a tick.
"""

import json
import math
import os
from pathlib import Path

import numpy as np
from manim import (DL, DOWN, DR, LEFT, RIGHT, UL, UP, UR, Axes, Create, DashedLine, Dot, FadeIn, FadeOut,
                   Line, Rectangle, Scene, Text, VGroup, VMobject, config, linear, smooth)

try:
    import manimpango
    for _f in (Path(__file__).resolve().parents[3] / "assets" / "fonts").glob("*.ttf"):
        try:
            manimpango.register_font(str(_f))
        except Exception:
            pass
except Exception:
    pass

NAVY = "#050A1F"
NAVY_2 = "#0A1130"
AMBER = "#FFC000"
INK = "#F4F6FC"
INK_60 = "#9AA0B4"
INK_35 = "#5C6280"
GROUND = "#F2EFE8"
GREEN = "#10B981"
RED = "#EF4444"
HEAD = "Fraunces"
MONO = "JetBrains Mono"

STYLE = {
    "palette": {"navy": NAVY, "navy_2": NAVY_2, "amber": AMBER, "ink": INK, "ink_60": INK_60, "ink_35": INK_35,
                "ground": GROUND, "green": GREEN, "red": RED},
    "type": {"headline": HEAD, "data": MONO, "headline_size": 64, "number_size": 96, "label_size": 26, "caption_size": 22},
    "chart": {"axis_stroke": 2, "axis_color": INK_35, "data_stroke": 3, "band_opacity": 0.22, "grid_opacity": 0.0,
              "build_axes_s": 0.8, "build_data_s": 1.6, "annotation_s": 0.5, "drift_scale": 1.025},
    "cards": {"hold_s": 1.1, "texture": "procedural glow until content/assets/textures exists"},
}


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


def nice_step(lo: float, hi: float, n: int = 5) -> float:
    raw = (hi - lo) / max(1, n)
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


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
        self.camera.background_color = NAVY
        self.W = config.frame_width
        self.H = config.frame_height
        self.callout_stack = VGroup()

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

    def play(self, *anims, **kw):
        rt = kw.get("run_time") or max((getattr(a, "run_time", 1.0) for a in anims), default=1.0)
        super().play(*anims, **kw)
        self._trace(f"play {rt:.2f}")

    def wait(self, duration=1.0, **kw):
        if duration > 0.01:
            super().wait(duration, **kw)

    def wait_until(self, t: float):
        self.wait(max(0.0, t - self.clock))

    def rel(self, key: str):
        r = self.seg.get("reveals", {}).get(key)
        return None if not r else max(0.0, float(r["t"]) - float(self.seg["start"]))

    def landed(self, kind: str = "data"):
        self.events.append({"t": round(float(self.seg["start"]) + self.clock, 3), "kind": kind, "segment": self.seg.get("index")})

    # ── furniture ──
    def demo_label(self):
        lab = Text("Tarnhollow · demo data", font=MONO, font_size=18, color=INK_35).to_corner(DL, buff=0.3)
        self.add(lab)
        return lab

    def caption(self, text: str, size: int = 22):
        cap = Text(text, font=MONO, font_size=size, color=INK_60).to_corner(UL, buff=0.35)
        self.add(cap)
        return cap

    def big_number(self, value: str, label: str, size: int = 96):
        num = Text(value, font=HEAD, font_size=size, color=AMBER, weight="BOLD")
        lab = Text(label, font=MONO, font_size=24, color=INK_60)
        fit(lab, self.W * 0.8)
        return VGroup(num, lab).arrange(DOWN, buff=0.35)

    def axes(self, x_range, y_range, x_len=None, y_len=None):
        x_len = x_len or (self.W * 0.72 if not self.vertical else self.W * 0.82)
        y_len = y_len or (self.H * 0.6 if not self.vertical else self.H * 0.42)
        return Axes(x_range=x_range, y_range=y_range, x_length=x_len, y_length=y_len, tips=False,
                    axis_config={"stroke_color": INK_35, "stroke_width": STYLE["chart"]["axis_stroke"],
                                 "include_ticks": True, "tick_size": 0.06, "include_numbers": False})

    def axis_numbers(self, ax, xs, ys, xfmt=str, yfmt=money):
        g = VGroup()
        for x in xs:
            g.add(Text(xfmt(x), font=MONO, font_size=16, color=INK_35).next_to(ax.c2p(x, ax.y_range[0]), DOWN, buff=0.15))
        for y in ys:
            g.add(Text(yfmt(y), font=MONO, font_size=16, color=INK_35).next_to(ax.c2p(ax.x_range[0], y), LEFT, buff=0.15))
        return g

    def polyline(self, ax, xs, ys, color=INK, width=2.0, opacity=1.0):
        v = VMobject(stroke_color=color, stroke_width=width, stroke_opacity=opacity)
        v.set_points_as_corners([ax.c2p(x, y) for x, y in zip(xs, ys)])
        return v

    def band(self, ax, xs, lo, hi, color=AMBER, opacity=None):
        from manim import Polygon
        pts = [ax.c2p(x, y) for x, y in zip(xs, lo)] + [ax.c2p(x, y) for x, y in zip(reversed(list(xs)), reversed(list(hi)))]
        return Polygon(*pts, fill_color=color, fill_opacity=opacity or STYLE["chart"]["band_opacity"], stroke_width=0)

    def callout(self, value: str, label: str, at=None, color=AMBER):
        """A number and what it is, stacked top-right; the default way an
        unhandled spoken figure gets on screen the moment it is said."""
        block = VGroup(Text(value, font=HEAD, font_size=44, color=color, weight="BOLD"),
                       Text(label, font=MONO, font_size=18, color=INK_60)).arrange(DOWN, aligned_edge=RIGHT, buff=0.08)
        fit(block[1], self.W * 0.34)
        if len(self.callout_stack) >= 3:
            old = self.callout_stack[0]
            self.callout_stack.remove(old)
            self.play(FadeOut(old), run_time=0.25)
        self.callout_stack.add(block)
        self.callout_stack.arrange(DOWN, aligned_edge=RIGHT, buff=0.3).to_corner(UR, buff=0.4)
        self.play(FadeIn(block, shift=LEFT * 0.2), run_time=STYLE["chart"]["annotation_s"])
        self.landed("annotation")
        return block

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
            self.wait_until(t)
            fact = self.facts.get(key, {})
            if key in handlers:
                handlers[key](fact.get("value", r.get("value", "")), fact.get("label", ""))
            else:
                self.callout(fact.get("value", r.get("value", "")), fact.get("label", key))

    def finish(self, group=None):
        rest = self.length - self.clock
        if rest > 0.05:
            if group is not None:
                self.play(group.animate.scale(STYLE["chart"]["drift_scale"]), run_time=rest, rate_func=linear)
            else:
                self.wait(rest)
        ev = self.d / "events.json"
        existing = json.loads(ev.read_text(encoding="utf-8")) if ev.exists() else []
        existing = [e for e in existing if e.get("segment") != self.seg.get("index")] + self.events
        ev.write_text(json.dumps(sorted(existing, key=lambda e: e["t"])) + "\n", encoding="utf-8")
        self._trace("finish")
