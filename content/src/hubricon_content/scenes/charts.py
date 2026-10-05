"""One scene per model output. Every number drawn here came out of run.json,
which came out of the engine; nothing is typed in.

Drawn in the site's chart grammar (assets/hubricon.css .chart), at the film
stage's sizes: ink for the line that matters, ink-3 for text and the second
line, ink-4 for a cost, rule-2 for the axes, and blue only on money and the
leak. No red and no green: a loss is ink with a minus sign (BRAND.md)."""

import math
import re

import numpy as np
from manim import DOWN, LEFT, RIGHT, UP, UR, Create, Dot, FadeIn, FadeOut, GrowFromEdge, ImageMobject, Line, \
    Rectangle, VGroup, linear, smooth

from .base import (BLUE, EASE_OUT, EASE_STILL, FIGURE_HOLD_S, INK, INK_3, INK_4, RULE, S, SHOT_MIN_S, STYLE,
                   HubriconScene, at, block, ch, is_money, money, nice_step, phrases, px, stack, stroke)


def _dot(point, colour=INK, r_px=7):
    return Dot(point, color=colour, radius=r_px * px())


class ChapterCard(HubriconScene):
    """VISUAL_SPEC §8.1: a 120 px ink hairline, then the title in Inter 600 at
    96 px, on paper; no numbering."""

    def label_text(self):
        return None

    def construct(self):
        title = self.seg.get("title") or self.seg.get("name", "")
        size = STYLE["cards"]["chapter_px"] if not self.vertical else 80
        left = self.pad["side"]
        lines = block(title, size, min(self.Wpx - 2 * left, 21 * ch(size)), INK, 600, S["display_track_em"], "balance")
        height = 2 + 40 + len(lines) * 1.04 * size
        top = self.pad["top"] + (self.Hpx - self.pad["top"] - self.pad["bottom"] - height) / 2
        hair = Line(at(left, top + 1), at(left + STYLE["cards"]["hairline_px"], top + 1), color=INK,
                    stroke_width=stroke(STYLE["chart"]["line_px"]))
        t, _ = stack(lines, left, top + 42, size, 1.04)
        self.play(GrowFromEdge(hair, LEFT), run_time=0.35, rate_func=EASE_OUT)
        self.enter(t)
        self.play(run_time=0.7)
        self.landed("chapter")
        self.finish(VGroup(hair, t), about=hair)


class Kinetic(HubriconScene):
    """The narration's own sentences, each one its own shot, and a spoken figure
    taking the whole frame the moment it is said. The cadence is the spec's (§4):
    the card cuts at a sentence boundary, so the cut lands in the pause the
    narrator already takes, and nothing holds past fourteen seconds."""

    def label_text(self):
        return super().label_text() if self.seg.get("reveals") else None

    def shots(self) -> list[dict]:
        """The segment's shots in time order: a card per sentence, a figure where
        one is spoken. A card that the next shot would cut inside the minimum is
        dropped rather than flashed, and a figure keeps its own hold."""
        start = float(self.seg["start"])
        shots = [{"t": max(0.0, p["start"] - start), "text": p["text"]}
                 for p in phrases(self.seg.get("words") or [])]
        for key, r in self.seg.get("reveals", {}).items():
            fact = self.facts.get(key, {})
            shots.append({"t": max(0.0, float(r["t"]) - start), "figure": fact.get("value", r.get("value", "")),
                          "label": fact.get("label", key)})
        shots.sort(key=lambda s: (s["t"], "figure" not in s))
        if not shots:
            vo = (self.seg.get("vo") or "").strip() or self.seg.get("name", "")
            shots = [{"t": 0.0, "text": re.split(r"(?<=[.!?])\s", vo, maxsplit=1)[0]}]
        if "figure" in shots[0] and shots[0]["t"] > 0.3:
            # never a blank stage and never an early figure: the sentence the
            # figure sits in opens the segment, and the figure lands on its word
            opening = (phrases(self.seg.get("words") or []) or [{"text": self.seg.get("vo", "")}])[0]
            shots.insert(0, {"t": 0.0, "text": opening["text"]})
        kept: list[dict] = [dict(shots[0], t=0.0)]   # the picture is up from the segment's first frame
        for s in shots[1:]:
            prev = kept[-1]
            floor_s = FIGURE_HOLD_S if "figure" in prev else SHOT_MIN_S
            if s["t"] - prev["t"] < floor_s:
                # a figure is never late, so the shot it would cut into gives way to it;
                # a card that cannot hold the minimum is not shown at all. The segment's
                # opening picture stays, so the stage is never blank and no figure is early.
                if "figure" in s and len(kept) > 1:
                    kept[-1] = s
                continue
            kept.append(s)
        tail = float(self.seg["end"]) - float(self.seg["start"]) - kept[-1]["t"]
        if len(kept) > 1 and tail < (FIGURE_HOLD_S if "figure" in kept[-1] else SHOT_MIN_S):
            kept.pop()                     # the segment ends too soon to cut again: the last shot holds through
        return kept

    def construct(self):
        shots = self.shots()
        for i, s in enumerate(shots):
            self.wait_until(s["t"])
            mob = self.big_number(s["figure"], s["label"]) if "figure" in s else self.type_card(s["text"])
            until = shots[i + 1]["t"] if i + 1 < len(shots) else self.length
            self.cut_to(mob, until, about=mob[0] if "figure" in s else None)
        self.finish()


class Screenshot(HubriconScene):
    """A real screenshot, framed by a rule hairline and never a shadow, with the
    slow push a still gets (VISUAL_SPEC §3.4). The file is named in VISUAL as
    `screenshot: <file>` under videos/<slug>/assets/."""

    def label_text(self):
        return None

    def construct(self):
        m = re.search(r"screenshot:\s*([^\s,;]+)", self.seg.get("visual", ""))
        path = self.d / "assets" / m.group(1) if m else None
        if not path or not path.exists():
            # Never shipped: QA fails a film with this frame in it.
            t = block("screenshot missing: " + (m.group(1) if m else "unnamed"), 44, 1400, INK, 600)
            self.add(stack(t, self.pad["side"], 480, 44, 1.4)[0])
            self.finish()
            return
        img = ImageMobject(str(path))
        box_w, box_h = (self.Wpx - 2 * self.pad["side"]) * px(), (self.Hpx - self.pad["top"] - self.pad["bottom"]) * px()
        img.scale(min(box_w / img.width, box_h / img.height))
        img.move_to(at(self.Wpx / 2, self.pad["top"] + (self.Hpx - self.pad["top"] - self.pad["bottom"]) / 2))
        frame = Rectangle(width=img.width, height=img.height, stroke_color=RULE, stroke_width=stroke(1),
                          fill_opacity=0).move_to(img)
        self.play(FadeIn(img), FadeIn(frame), run_time=0.4)
        self.landed()
        self.reveal_loop()
        rest = self.length - self.clock
        if rest > 0.05:
            self.play(img.animate.scale(1.04), frame.animate.scale(1.04), run_time=rest, rate_func=EASE_STILL)
        self.finish()


class Waterfall(HubriconScene):
    def construct(self):
        w = self.run["waterfall"]
        self.caption("Latest month · revenue to net")
        # Revenue in ink, what it costs in ink-4, what is left is the money: blue.
        steps = [("Revenue", w["revenue"], INK), ("Amazon fees", -w["fees"], INK_4), ("Landed cost", -w["cogs"], INK_4),
                 ("Ads", -w["ads"], INK_4), ("Net", w["net"], BLUE)]
        top = w["revenue"]
        ax = self.axes([0, 5, 1], [0, top * 1.12, nice_step(0, top)], room_px=STYLE["chart"]["label_px"] * 1.25)
        self.play(Create(ax), run_time=STYLE["chart"]["build_axes_s"])
        level = 0.0
        bars, labels = VGroup(), VGroup()
        for i, (name, delta, colour) in enumerate(steps):
            if name == "Net":
                lo, hi = 0.0, delta
            else:
                lo, hi = (level, level + delta) if delta >= 0 else (level + delta, level)
                level = level + delta
            x0, x1 = ax.c2p(i + 0.18, lo), ax.c2p(i + 0.82, hi)
            bar = Rectangle(width=abs(x1[0] - x0[0]), height=max(0.02, abs(x1[1] - x0[1])), fill_color=colour,
                            fill_opacity=1, stroke_width=0).move_to([(x0[0] + x1[0]) / 2, (x0[1] + x1[1]) / 2, 0])
            slot = (ax.c2p(1, 0)[0] - ax.c2p(0, 0)[0]) / px() - 16
            size = STYLE["chart"]["label_px"]
            lab, _ = stack(block(name, size, slot, INK_3, 400), 0, 0, size, 1.25)
            lab.next_to(ax.c2p(i + 0.5, 0), DOWN, buff=16 * px())
            for ln in lab:   # each line centred under its bar
                ln.set_x(ax.c2p(i + 0.5, 0)[0])
            val = self.chart_text(money(abs(delta)) if delta >= 0 else "−" + money(abs(delta)),
                                  BLUE if name == "Net" else INK, 600).next_to(bar, UP, buff=12 * px())
            self.play(GrowFromEdge(bar, DOWN), FadeIn(lab), run_time=0.45, rate_func=EASE_OUT)
            self.play(FadeIn(val), run_time=0.15)
            self.landed()
            bars.add(bar)
            labels.add(lab, val)
        keys = {"rev_latest", "fees_latest", "cogs_latest", "ads_latest", "net_latest"}
        self.reveal_loop(skip=keys)
        self.finish(VGroup(ax, bars, labels), about=bars[-1])


class CashCone(HubriconScene):
    def construct(self):
        c = self.run["cash"]
        det = c["details"]
        p5, p50, p95 = det["p5"], det["p50"], det["p95"]
        days = list(range(1, len(p5) + 1))
        self.caption(f"Cash, next {len(p5)} days · {c['n_paths']:,} paths")
        lo = min(min(p5), 0) * 1.05
        hi = max(p95) * 1.08
        ax = self.axes([0, len(p5), 15], [lo, hi, nice_step(lo, hi)])
        nums = self.axis_numbers(ax, list(range(0, len(p5) + 1, 30)), [0, hi * 0.5 // 1000 * 1000, hi * 0.95 // 1000 * 1000],
                                 xfmt=lambda x: f"d{int(x)}")
        self.play(Create(ax), FadeIn(nums), run_time=STYLE["chart"]["build_axes_s"])
        zero = self.dashed(ax.c2p(0, 0), ax.c2p(len(p5), 0))
        self.add(zero)
        band = self.band(ax, days, p5, p95)
        mid = self.leak_line(ax, days, p50)
        self.play(FadeIn(band), run_time=0.6)
        self.play(Create(mid), run_time=STYLE["chart"]["build_data_s"], rate_func=smooth)
        self.landed()
        ticks = VGroup(*[Line(ax.c2p(w["day"], lo), ax.c2p(w["day"], lo + (hi - lo) * 0.035), color=INK_3,
                              stroke_width=stroke(STYLE["chart"]["hair_px"]))
                         for w in det["wires"] if 0 <= w["day"] < len(p5)])
        self.play(FadeIn(ticks), run_time=0.3)
        self.landed()
        group = VGroup(ax, nums, zero, band, mid, ticks)

        def trough(value, label):
            d = c["min_p5_day"]
            dot = _dot(ax.c2p(d, c["min_p5"]))
            t = self.chart_text(f"{value} on day {d}", INK, 600).next_to(dot, DOWN + RIGHT, buff=12 * px())
            self.play(FadeIn(dot), FadeIn(t), run_time=0.4)
            self.landed("annotation")
            group.add(dot, t)

        def wire(value, label):
            big = max(det["wires"], key=lambda x: x["amount"]) if det["wires"] else None
            if big:
                ln = Line(ax.c2p(big["day"], lo), ax.c2p(big["day"], hi * 0.6), color=INK,
                          stroke_width=stroke(STYLE["chart"]["line_px"]))
                t = self.chart_text(f"{value} wire", INK, 600).next_to(ln.get_top(), RIGHT, buff=12 * px())
                self.play(Create(ln), FadeIn(t), run_time=0.4)
                self.landed("annotation")
                group.add(ln, t)

        self.reveal_loop({"min_p5": trough, "trough_p5": trough, "largest_wire": wire})
        self.finish(group, about=mid)


class Paths(HubriconScene):
    """Every path of one strategy; then the ones that finished on top."""

    def construct(self):
        p = self.run.get("paths_year") or self.run["paths"]
        sample = np.array(p["sample"], dtype=float)
        H = int(p["horizon_days"])
        step = max(1, H // 120)
        xs = list(range(0, H, step))
        self.caption(f"{sample.shape[0]} of {p['n']:,} paths · one strategy · {H} days")
        lo = min(sample.min(), 0) * 1.05
        hi = sample.max() * 1.06
        ax = self.axes([0, H, max(1, H // 6)], [lo, hi, nice_step(lo, hi)])
        nums = self.axis_numbers(ax, list(range(0, H + 1, max(30, H // 4))), [0, hi * 0.5 // 1000 * 1000, hi * 0.95 // 1000 * 1000],
                                 xfmt=lambda x: f"d{int(x)}")
        self.play(Create(ax), FadeIn(nums), run_time=STYLE["chart"]["build_axes_s"])
        # The site's Monte Carlo: each path draws at --mc-path-draw, then settles to --mc-path-rest.
        draw, rest = STYLE["chart"]["path_draw_opacity"], STYLE["chart"]["path_opacity"]
        lines = VGroup(*[self.polyline(ax, xs, row[xs], BLUE, stroke(STYLE["chart"]["hair_px"]), draw) for row in sample])
        for chunk in np.array_split(np.arange(len(lines)), 5):
            self.play(*[Create(lines[i]) for i in chunk], run_time=0.5, rate_func=linear)
        self.play(*[ln.animate.set_stroke(opacity=rest) for ln in lines], run_time=0.4)
        self.landed()
        ranks = p["sample_terminal_rank"]
        top_idx = [i for i in range(len(sample)) if ranks[i] < max(1, len(sample) // 10)]
        group = VGroup(ax, nums, lines)

        def survivors(value, label):
            self.play(*[lines[i].animate.set_stroke(BLUE, opacity=1.0, width=stroke(STYLE["chart"]["line_px"]))
                        for i in top_idx], run_time=0.8, rate_func=smooth)
            t = self.chart_text(f"top tenth · {value}", BLUE if is_money(value) else INK, 600)
            t.next_to(ax.c2p(H, sample[top_idx, -1].mean()), LEFT, buff=16 * px()).shift(UP * 30 * px())
            self.play(FadeIn(t), run_time=0.3)
            self.landed("annotation")
            group.add(t)

        def median(value, label):
            y = float(np.median(sample[:, -1]))
            ln = self.dashed(ax.c2p(0, y), ax.c2p(H, y), INK)
            t = self.chart_text(f"median · {value}", INK, 600).next_to(ax.c2p(H * 0.02, y), UP, buff=10 * px(),
                                                                       aligned_edge=LEFT)
            self.play(Create(ln), FadeIn(t), run_time=0.5)
            self.landed("annotation")
            group.add(ln, t)

        def spread(value, label):
            # The bracket is drawn once and its figure replaces itself: the gap and
            # the gap as a share of the median are the same annotation said twice, and
            # the label sits inside the plot, never in the right column where the
            # callouts live.
            y1, y2 = np.quantile(sample[:, -1], 0.1), np.quantile(sample[:, -1], 0.9)
            new, old = [], getattr(self, "_spread_text", None)
            br = getattr(self, "_spread_bracket", None)
            if br is None:
                br = Line(ax.c2p(H * 0.985, y1), ax.c2p(H * 0.985, y2), color=INK,
                          stroke_width=stroke(STYLE["chart"]["leak_px"]))
                self._spread_bracket = br
                new.append(br)
                group.add(br)
            t = self.chart_text(value, BLUE if is_money(value) else INK, 600).next_to(br, LEFT, buff=16 * px())
            self._spread_text = t
            anims = [Create(x) for x in new] + [FadeIn(t)] + ([FadeOut(old)] if old is not None else [])
            self.play(*anims, run_time=0.5)
            if old is not None:
                group.remove(old)
            self.landed("annotation")
            group.add(t)

        self.reveal_loop({"year_top_decile": survivors, "top_decile_terminal": survivors, "year_top_vs_median": survivors,
                          "year_terminal_p50": median, "terminal_p50": median,
                          "year_luck_spread": spread, "year_luck_spread_pct": spread})
        self.finish(group)


class Elasticity(HubriconScene):
    def construct(self):
        curves = self.run.get("elasticity_curves") or []
        want = self.facts.get("el_sku", {}).get("value")
        cv = next((c for c in curves if c["sku"] == want), curves[0] if curves else None)
        if not cv:
            self.caption("no elasticity curve in this run")
            self.finish()
            return
        self.caption(f"Demand vs price · {cv['sku']}")
        pts, curve, band = cv["points"], cv["curve"], cv["band"]
        xs = [q["p"] for q in curve]
        ys = [q["u"] for q in curve]
        lo_u = min(min(b["lo"] for b in band), min(q["u"] for q in pts)) * 0.85
        hi_u = max(max(b["hi"] for b in band), max(q["u"] for q in pts)) * 1.12
        ax = self.axes([min(xs) * 0.98, max(xs) * 1.02, nice_step(min(xs), max(xs))], [lo_u, hi_u, nice_step(lo_u, hi_u)])
        nums = self.axis_numbers(ax, [round(min(xs)), round(max(xs))], [round(lo_u), round(hi_u)],
                                 xfmt=lambda x: f"${x:.0f}", yfmt=lambda y: f"{y:,.0f}u")
        self.play(Create(ax), FadeIn(nums), run_time=STYLE["chart"]["build_axes_s"])
        dots = VGroup(*[_dot(ax.c2p(q["p"], q["u"])) for q in pts])
        self.play(FadeIn(dots, lag_ratio=0.1), run_time=0.8)
        self.landed()
        bnd = self.band(ax, [b["p"] for b in band], [b["lo"] for b in band], [b["hi"] for b in band])
        line = self.polyline(ax, xs, ys, INK)
        self.play(FadeIn(bnd), run_time=0.5)
        self.play(Create(line), run_time=STYLE["chart"]["build_data_s"], rate_func=smooth)
        self.landed()
        group = VGroup(ax, nums, dots, bnd, line)

        def eps(value, label):
            t = self.chart_text(f"ε = {value}", INK, 600).next_to(ax.c2p(xs[-1], ys[-1]), UR, buff=16 * px())
            t.shift(LEFT * 160 * px())
            self.play(FadeIn(t), run_time=0.4)
            self.landed("annotation")
            group.add(t)

        def ci(value, label):
            self.play(bnd.animate.set_fill(opacity=STYLE["chart"]["band_opacity"] * 2.5), run_time=0.3)
            t = self.chart_text(f"{value} · {label}").next_to(ax.c2p(xs[0], band[0]["hi"]), UP, buff=12 * px(),
                                                              aligned_edge=LEFT)
            if t.width > (self.Wpx * 0.5) * px():
                t.scale_to_fit_width(self.Wpx * 0.5 * px())
            self.play(FadeIn(t), run_time=0.3)
            self.landed("annotation")
            group.add(t)

        self.reveal_loop({"el_point": eps, "el_ci_low": ci, "el_ci_high": ci, "el_ci_width": ci})
        self.finish(group)


class Newsvendor(HubriconScene):
    """The two marginal costs cross at the service level the SKU's own margin justifies."""

    def construct(self):
        rows = self.run.get("invecon_rows") or []
        want = self.facts.get("nv_sku", {}).get("value")
        r = next((x for x in rows if x.get("sku") == want), rows[0] if rows else None)
        if not r:
            self.caption("no newsvendor row in this run")
            self.finish()
            return
        cu, co, qstar = float(r["c_u"]), float(r["c_o"]), float(r["critical_fractile"])
        self.caption(f"Cost of the last unit · {r['sku']}")
        qs = np.linspace(0.5, 0.995, 60)
        under = cu * (1 - qs)      # expected cost of being short, falling as service rises
        over = co * qs             # expected cost of the unit sitting unsold, rising with service
        hi = max(under.max(), over.max()) * 1.15
        ax = self.axes([0.5, 1.0, 0.1], [0, hi, nice_step(0, hi)])
        nums = self.axis_numbers(ax, [0.5, 0.75, 0.95], [hi * 0.9], xfmt=lambda x: f"{x * 100:.0f}%",
                                 yfmt=lambda y: f"${y:.2f}")
        self.play(Create(ax), FadeIn(nums), run_time=STYLE["chart"]["build_axes_s"])
        # Running short is the margin that leaks: blue. Too many is a cost: ink.
        l1, l2 = self.leak_line(ax, qs, under), self.polyline(ax, qs, over, INK)
        t1 = self.chart_text("short one unit", BLUE, 600).next_to(ax.c2p(0.52, under[2]), UR, buff=10 * px())
        t2 = self.chart_text("one unit too many", INK, 600).next_to(ax.c2p(0.6, over[20]), UP, buff=12 * px(),
                                                                     aligned_edge=LEFT)
        self.play(Create(l1), FadeIn(t1), run_time=1.0, rate_func=linear)
        self.landed()
        self.play(Create(l2), FadeIn(t2), run_time=1.0, rate_func=linear)
        self.landed()
        group = VGroup(ax, nums, l1, l2, t1, t2)

        def star(value, label):
            ln = self.dashed(ax.c2p(qstar, 0), ax.c2p(qstar, hi * 0.8), INK)
            t = self.chart_text(f"{value} · this SKU's own number", INK, 600).next_to(ln, UP, buff=10 * px())
            self.play(Create(ln), FadeIn(t), run_time=0.5)
            self.landed("annotation")
            group.add(ln, t)

        def flat(value, label):
            ln = self.dashed(ax.c2p(0.95, 0), ax.c2p(0.95, hi * 0.6))
            t = self.chart_text(f"{value} · the flat default").next_to(ln.get_top(), UP + LEFT, buff=10 * px())
            self.play(Create(ln), FadeIn(t), run_time=0.5)
            self.landed("annotation")
            group.add(ln, t)

        self.reveal_loop({"nv_fractile": star, "nv_low_fractile": star, "service_level_default": flat, "nv_fractile_median": star})
        self.finish(group, about=l1)


class SampleSize(HubriconScene):
    """How the standard error of an estimate shrinks with periods observed."""

    def construct(self):
        se0 = float(self.facts.get("el_se", {}).get("value", "0.5") or 0.5)
        n0 = int(self.facts.get("el_periods", {}).get("value", "12") or 12)
        self.caption("Standard error vs periods observed · same fit, more data")
        ns = np.arange(3, 121)
        se = se0 * np.sqrt(n0 / ns)
        hi = se.max() * 1.1
        ax = self.axes([0, 120, 20], [0, hi, nice_step(0, hi)])
        nums = self.axis_numbers(ax, [12, 60, 120], [round(hi, 1)], xfmt=lambda x: f"{int(x)} periods",
                                 yfmt=lambda y: f"±{y:.2f}")
        self.play(Create(ax), FadeIn(nums), run_time=STYLE["chart"]["build_axes_s"])
        line = self.polyline(ax, ns, se, INK)
        self.play(Create(line), run_time=STYLE["chart"]["build_data_s"], rate_func=smooth)
        self.landed()
        dot = _dot(ax.c2p(n0, se0))
        t0 = self.chart_text(f"today: {n0} periods, ±{se0:.2f}", INK, 600).next_to(dot, UR, buff=12 * px())
        self.play(FadeIn(dot), FadeIn(t0), run_time=0.4)
        self.landed()
        group = VGroup(ax, nums, line, dot, t0)

        def need(target):
            def h(value, label):
                n = float(value.replace(",", ""))
                if n > 120:
                    left, top, right, bottom = self.plot_box()
                    t = self.chart_text(f"{value} periods for ±{target:g}", INK, 600)
                    t.move_to(at(left + 40 + t.width / px() / 2, top + 40))
                    self.play(FadeIn(t), run_time=0.4)
                    self.landed("annotation")
                    group.add(t)
                    return
                ln = self.dashed(ax.c2p(n, 0), ax.c2p(n, se0 * math.sqrt(n0 / n)))
                t = self.chart_text(f"{value} periods → ±{target:g}").next_to(ln, UP, buff=10 * px())
                self.play(Create(ln), FadeIn(t), run_time=0.4)
                self.landed("annotation")
                group.add(ln, t)
            return h

        self.reveal_loop({"n_for_se_half": need(0.5), "n_for_se_quarter": need(0.25), "n_for_se_tenth": need(0.1)},
                         skip={"el_se", "el_periods"})
        self.finish(group)
