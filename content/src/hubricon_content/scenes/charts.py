"""One scene per model output. Every number drawn here came out of run.json,
which came out of the engine; nothing is typed in."""

import math
import re

import numpy as np
from manim import (DOWN, LEFT, RIGHT, UP, UL, UR, DL, Create, DashedLine, Dot, FadeIn, FadeOut, GrowFromEdge, Line,
                   Rectangle, Text, VGroup, Write, linear, smooth, Circle, ImageMobject)

from .base import (AMBER, GREEN, HEAD, INK, INK_35, INK_60, MONO, NAVY_2, RED, STYLE, HubriconScene, fit, money, nice_step)


class ChapterCard(HubriconScene):
    def construct(self):
        title = self.seg.get("title") or self.seg.get("name", "")
        kicker = Text("HUBRICON", font=MONO, font_size=16, color=INK_35).to_corner(UL, buff=0.5)
        hair = Line(LEFT * self.W * 0.42, RIGHT * self.W * 0.42, color=INK_35, stroke_width=1).shift(UP * self.H * 0.14)
        t = Text(title, font=HEAD, font_size=66 if not self.vertical else 56, color=INK, weight="BOLD")
        fit(t, self.W * 0.78)
        t.next_to(hair, DOWN, buff=0.55)
        rule = Line(LEFT * 0.7, RIGHT * 0.7, color=AMBER, stroke_width=3).next_to(t, DOWN, buff=0.45)
        self.add(kicker, hair)
        self.play(FadeIn(t, shift=UP * 0.1), run_time=0.4, rate_func=smooth)
        self.play(GrowFromEdge(rule, LEFT), run_time=0.3, rate_func=smooth)
        self.landed("chapter")
        self.finish(VGroup(t, rule))


class Kinetic(HubriconScene):
    """Numbers and phrases landing as they are spoken."""
    def construct(self):
        vo = self.seg.get("vo", "")
        first = re.split(r"(?<=[.!?])\s", vo, maxsplit=1)[0] if vo else self.seg.get("name", "")
        reveals = sorted(self.seg.get("reveals", {}).items(), key=lambda kv: kv[1]["t"])
        if not reveals:
            t = Text(first, font=HEAD, font_size=54 if not self.vertical else 48, color=INK, weight="BOLD", line_spacing=1.1)
            fit(t, self.W * 0.8)
            self.play(Write(t), run_time=min(2.2, max(0.8, self.length * 0.4)))
            self.landed("annotation")
            self.finish(t)
            return
        cap = Text(re.sub(r"\{\{.*?\}\}", "…", first), font=MONO, font_size=19, color=INK_35, line_spacing=1.15)
        fit(cap, self.W * 0.72).to_edge(UP, buff=0.7)
        self.play(FadeIn(cap), run_time=0.4)
        shown = None
        for key, r in reveals:
            self.wait_until(max(0.0, float(r["t"]) - float(self.seg["start"])))
            fact = self.facts.get(key, {})
            block = self.big_number(fact.get("value", r.get("value", "")), fact.get("label", key),
                                    size=110 if not self.vertical else 84)
            fit(block, self.W * 0.86)
            if shown is not None:
                self.play(FadeOut(shown, shift=UP * 0.3), run_time=0.25)
            self.play(FadeIn(block, scale=0.96), run_time=0.5, rate_func=smooth)
            self.landed()
            shown = block
        self.finish(shown)


class Screenshot(HubriconScene):
    """A real screenshot with a slow push (the archival-footage equivalent).
    The file is named in VISUAL as `screenshot: <file>` under videos/<slug>/assets/."""
    def construct(self):
        m = re.search(r"screenshot:\s*([^\s,;]+)", self.seg.get("visual", ""))
        path = self.d / "assets" / m.group(1) if m else None
        if not path or not path.exists():
            t = Text("screenshot missing: " + (m.group(1) if m else "unnamed"), font=MONO, font_size=28, color=RED)
            self.add(t)
            self.finish()
            return
        img = ImageMobject(str(path))
        img.set_width(self.W * 0.9) if not self.vertical else img.set_width(self.W * 0.95)
        self.play(FadeIn(img), run_time=0.4)
        self.landed()
        self.reveal_loop()
        rest = self.length - self.clock
        if rest > 0.05:
            self.play(img.animate.scale(1.06), run_time=rest, rate_func=linear)
        self.finish()


class Waterfall(HubriconScene):
    def construct(self):
        w = self.run["waterfall"]
        self.demo_label()
        self.caption("Latest month · revenue to net")
        steps = [("Revenue", w["revenue"], AMBER), ("Amazon fees", -w["fees"], INK_60), ("Landed cost", -w["cogs"], INK_60),
                 ("Ads", -w["ads"], INK_60), ("Net", w["net"], GREEN)]
        top = w["revenue"]
        ax = self.axes([0, 5, 1], [0, top * 1.08, nice_step(0, top)], y_len=self.H * 0.55)
        ax.shift(DOWN * 0.3)
        self.play(Create(ax), run_time=STYLE["chart"]["build_axes_s"])
        level = 0.0
        bars, labels = VGroup(), VGroup()
        for i, (name, delta, color) in enumerate(steps):
            if name == "Net":
                lo, hi = 0.0, delta
            else:
                lo, hi = (level, level + delta) if delta >= 0 else (level + delta, level)
                level = level + delta
            x0, x1 = ax.c2p(i + 0.15, lo), ax.c2p(i + 0.85, hi)
            bar = Rectangle(width=abs(x1[0] - x0[0]), height=max(0.02, abs(x1[1] - x0[1])), fill_color=color,
                            fill_opacity=0.72 if color != AMBER else 0.9, stroke_width=0).move_to([(x0[0] + x1[0]) / 2, (x0[1] + x1[1]) / 2, 0])
            lab = Text(name, font=MONO, font_size=18, color=INK_60).next_to(ax.c2p(i + 0.5, 0), DOWN, buff=0.2)
            val = Text(money(abs(delta)), font=MONO, font_size=20, color=INK).next_to(bar, UP, buff=0.12)
            self.play(GrowFromEdge(bar, DOWN), FadeIn(lab), run_time=0.45)
            self.play(FadeIn(val), run_time=0.15)
            self.landed()
            bars.add(bar); labels.add(lab, val)
        keys = {"rev_latest", "fees_latest", "cogs_latest", "ads_latest", "net_latest"}
        self.reveal_loop(skip=keys)
        self.finish(VGroup(ax, bars, labels))


class CashCone(HubriconScene):
    def construct(self):
        c = self.run["cash"]; det = c["details"]
        p5, p50, p95 = det["p5"], det["p50"], det["p95"]
        days = list(range(1, len(p5) + 1))
        self.demo_label()
        self.caption(f"Cash, next {len(p5)} days · {c['n_paths']:,} paths")
        lo = min(min(p5), 0) * 1.05; hi = max(p95) * 1.08
        ax = self.axes([0, len(p5), 15], [lo, hi, nice_step(lo, hi)])
        ax.shift(DOWN * 0.2)
        nums = self.axis_numbers(ax, list(range(0, len(p5) + 1, 30)), [0, hi * 0.5 // 1000 * 1000, hi * 0.95 // 1000 * 1000], xfmt=lambda x: f"d{int(x)}")
        self.play(Create(ax), FadeIn(nums), run_time=STYLE["chart"]["build_axes_s"])
        zero = DashedLine(ax.c2p(0, 0), ax.c2p(len(p5), 0), color=INK_35, dash_length=0.12)
        self.add(zero)
        band = self.band(ax, days, p5, p95)
        mid = self.polyline(ax, days, p50, AMBER, 3)
        self.play(FadeIn(band), run_time=0.6)
        self.play(Create(mid), run_time=STYLE["chart"]["build_data_s"], rate_func=smooth)
        self.landed()
        ticks = VGroup(*[Line(ax.c2p(w["day"], lo), ax.c2p(w["day"], lo + (hi - lo) * 0.035), color=INK_60, stroke_width=1.5)
                         for w in det["wires"] if 0 <= w["day"] < len(p5)])
        self.play(FadeIn(ticks), run_time=0.3)
        self.landed()
        group = VGroup(ax, nums, zero, band, mid, ticks)

        def trough(value, label):
            d = c["min_p5_day"]
            dot = Dot(ax.c2p(d, c["min_p5"]), color=INK, radius=0.07)
            t = Text(f"{value} on day {d}", font=MONO, font_size=20, color=INK).next_to(dot, DOWN + RIGHT, buff=0.15)
            self.play(FadeIn(dot), FadeIn(t), run_time=0.4); self.landed("annotation"); group.add(dot, t)

        def wire(value, label):
            big = max(det["wires"], key=lambda x: x["amount"]) if det["wires"] else None
            if big:
                ln = Line(ax.c2p(big["day"], lo), ax.c2p(big["day"], hi * 0.6), color=RED, stroke_width=3)
                t = Text(f"{value} wire", font=MONO, font_size=20, color=RED).next_to(ln, UP, buff=0.1)
                self.play(Create(ln), FadeIn(t), run_time=0.4); self.landed("annotation"); group.add(ln, t)

        self.reveal_loop({"min_p5": trough, "trough_p5": trough, "largest_wire": wire})
        self.finish(group)


class Paths(HubriconScene):
    """Every path of one strategy; then the ones that finished on top."""
    def construct(self):
        p = self.run.get("paths_year") or self.run["paths"]
        sample = np.array(p["sample"], dtype=float)
        H = int(p["horizon_days"])
        step = max(1, H // 120)
        xs = list(range(0, H, step))
        self.demo_label()
        self.caption(f"{sample.shape[0]} of {p['n']:,} paths · one strategy · {H} days")
        lo = min(sample.min(), 0) * 1.05; hi = sample.max() * 1.06
        ax = self.axes([0, H, max(1, H // 6)], [lo, hi, nice_step(lo, hi)])
        ax.shift(DOWN * 0.2)
        nums = self.axis_numbers(ax, list(range(0, H + 1, max(30, H // 4))), [0, hi * 0.5 // 1000 * 1000, hi * 0.95 // 1000 * 1000], xfmt=lambda x: f"d{int(x)}")
        self.play(Create(ax), FadeIn(nums), run_time=STYLE["chart"]["build_axes_s"])
        lines = VGroup(*[self.polyline(ax, xs, row[xs], INK, 1.0, 0.13) for row in sample])
        chunks = np.array_split(np.arange(len(lines)), 5)
        for ch in chunks:
            self.play(*[Create(lines[i]) for i in ch], run_time=0.5, rate_func=linear)
        self.landed()
        ranks = p["sample_terminal_rank"]
        top_idx = [i for i in range(len(sample)) if ranks[i] < max(1, len(sample) // 10)]
        group = VGroup(ax, nums, lines)

        def survivors(value, label):
            self.play(*[lines[i].animate.set_stroke(AMBER, opacity=0.9, width=2.0) for i in top_idx], run_time=0.8, rate_func=smooth)
            t = Text(f"top tenth · {value}", font=MONO, font_size=20, color=AMBER).next_to(ax.c2p(H, sample[top_idx, -1].mean()), LEFT, buff=0.2).shift(UP * 0.3)
            self.play(FadeIn(t), run_time=0.3); self.landed("annotation"); group.add(t)

        def median(value, label):
            y = float(np.median(sample[:, -1]))
            ln = DashedLine(ax.c2p(0, y), ax.c2p(H, y), color=INK_60, dash_length=0.1)
            t = Text(f"median · {value}", font=MONO, font_size=20, color=INK_60).next_to(ax.c2p(H * 0.02, y), UP, buff=0.1, aligned_edge=LEFT)
            self.play(Create(ln), FadeIn(t), run_time=0.5); self.landed("annotation"); group.add(ln, t)

        def spread(value, label):
            y1, y2 = np.quantile(sample[:, -1], 0.1), np.quantile(sample[:, -1], 0.9)
            br = Line(ax.c2p(H * 0.985, y1), ax.c2p(H * 0.985, y2), color=AMBER, stroke_width=4)
            t = Text(value, font=HEAD, font_size=40, color=AMBER, weight="BOLD").next_to(br, LEFT, buff=0.2)
            self.play(Create(br), FadeIn(t), run_time=0.5); self.landed("annotation"); group.add(br, t)

        self.reveal_loop({"year_top_decile": survivors, "top_decile_terminal": survivors, "year_top_vs_median": survivors,
                          "year_terminal_p50": median, "terminal_p50": median,
                          "year_luck_spread": spread, "year_luck_spread_pct": spread})
        self.finish(group)


class Elasticity(HubriconScene):
    def construct(self):
        curves = self.run.get("elasticity_curves") or []
        want = self.facts.get("el_sku", {}).get("value")
        cv = next((c for c in curves if c["sku"] == want), curves[0] if curves else None)
        self.demo_label()
        if not cv:
            self.add(Text("no elasticity curve in this run", font=MONO, font_size=28, color=RED)); self.finish(); return
        self.caption(f"Demand vs price · {cv['sku']}")
        pts = cv["points"]; curve = cv["curve"]; band = cv["band"]
        xs = [q["p"] for q in curve]; ys = [q["u"] for q in curve]
        lo_u = min(min(b["lo"] for b in band), min(q["u"] for q in pts)) * 0.85
        hi_u = max(max(b["hi"] for b in band), max(q["u"] for q in pts)) * 1.12
        ax = self.axes([min(xs) * 0.98, max(xs) * 1.02, nice_step(min(xs), max(xs))], [lo_u, hi_u, nice_step(lo_u, hi_u)])
        ax.shift(DOWN * 0.2)
        nums = self.axis_numbers(ax, [round(min(xs)), round(max(xs))], [round(lo_u), round(hi_u)], xfmt=lambda x: f"${x:.0f}", yfmt=lambda y: f"{y:,.0f}u")
        self.play(Create(ax), FadeIn(nums), run_time=STYLE["chart"]["build_axes_s"])
        dots = VGroup(*[Dot(ax.c2p(q["p"], q["u"]), color=INK, radius=0.07) for q in pts])
        self.play(FadeIn(dots, lag_ratio=0.1), run_time=0.8); self.landed()
        bnd = self.band(ax, [b["p"] for b in band], [b["lo"] for b in band], [b["hi"] for b in band])
        line = self.polyline(ax, xs, ys, AMBER, 3)
        self.play(FadeIn(bnd), run_time=0.5)
        self.play(Create(line), run_time=STYLE["chart"]["build_data_s"], rate_func=smooth); self.landed()
        group = VGroup(ax, nums, dots, bnd, line)

        def eps(value, label):
            t = Text(f"ε = {value}", font=HEAD, font_size=48, color=AMBER, weight="BOLD").next_to(ax.c2p(xs[-1], ys[-1]), UR, buff=0.2)
            t.shift(LEFT * 1.2)
            self.play(FadeIn(t), run_time=0.4); self.landed("annotation"); group.add(t)

        def ci(value, label):
            self.play(bnd.animate.set_fill(opacity=0.45), run_time=0.3)
            t = Text(f"{value} · {label}", font=MONO, font_size=18, color=INK_60).next_to(ax.c2p(xs[0], band[0]["hi"]), UP, buff=0.15, aligned_edge=LEFT)
            fit(t, self.W * 0.5)
            self.play(FadeIn(t), run_time=0.3); self.landed("annotation"); group.add(t)

        self.reveal_loop({"el_point": eps, "el_ci_low": ci, "el_ci_high": ci, "el_ci_width": ci})
        self.finish(group)


class Newsvendor(HubriconScene):
    """The two marginal costs cross at the service level the SKU's own margin justifies."""
    def construct(self):
        rows = self.run.get("invecon_rows") or []
        want = self.facts.get("nv_sku", {}).get("value")
        r = next((x for x in rows if x.get("sku") == want), rows[0] if rows else None)
        self.demo_label()
        if not r:
            self.add(Text("no newsvendor row in this run", font=MONO, font_size=28, color=RED)); self.finish(); return
        cu, co, qstar = float(r["c_u"]), float(r["c_o"]), float(r["critical_fractile"])
        self.caption(f"Cost of the last unit · {r['sku']}")
        qs = np.linspace(0.5, 0.995, 60)
        under = cu * (1 - qs)      # expected cost of being short, falling as service rises
        over = co * qs             # expected cost of the unit sitting unsold, rising with service
        hi = max(under.max(), over.max()) * 1.15
        ax = self.axes([0.5, 1.0, 0.1], [0, hi, nice_step(0, hi)])
        ax.shift(DOWN * 0.2)
        nums = self.axis_numbers(ax, [0.5, 0.75, 0.95], [hi * 0.9], xfmt=lambda x: f"{x * 100:.0f}%", yfmt=lambda y: f"${y:.2f}")
        self.play(Create(ax), FadeIn(nums), run_time=STYLE["chart"]["build_axes_s"])
        l1 = self.polyline(ax, qs, under, AMBER, 3); l2 = self.polyline(ax, qs, over, INK, 3)
        t1 = Text("short one unit", font=MONO, font_size=18, color=AMBER).next_to(ax.c2p(0.52, under[2]), UR, buff=0.1)
        t2 = Text("one unit too many", font=MONO, font_size=18, color=INK).next_to(ax.c2p(0.97, over[-3]), UL, buff=0.1)
        self.play(Create(l1), FadeIn(t1), run_time=1.0, rate_func=linear); self.landed()
        self.play(Create(l2), FadeIn(t2), run_time=1.0, rate_func=linear); self.landed()
        group = VGroup(ax, nums, l1, l2, t1, t2)

        def star(value, label):
            x = qstar
            ln = DashedLine(ax.c2p(x, 0), ax.c2p(x, hi * 0.8), color=AMBER, dash_length=0.1)
            t = Text(f"{value} · this SKU's own number", font=MONO, font_size=20, color=AMBER).next_to(ln, UP, buff=0.1)
            self.play(Create(ln), FadeIn(t), run_time=0.5); self.landed("annotation"); group.add(ln, t)

        def flat(value, label):
            ln = DashedLine(ax.c2p(0.95, 0), ax.c2p(0.95, hi * 0.6), color=RED, dash_length=0.1)
            t = Text(f"{value} · the flat default", font=MONO, font_size=20, color=RED).next_to(ln, DOWN, buff=0.1)
            self.play(Create(ln), FadeIn(t), run_time=0.5); self.landed("annotation"); group.add(ln, t)

        self.reveal_loop({"nv_fractile": star, "nv_low_fractile": star, "service_level_default": flat, "nv_fractile_median": star})
        self.finish(group)


class SampleSize(HubriconScene):
    """How the standard error of an estimate shrinks with periods observed."""
    def construct(self):
        se0 = float(self.facts.get("el_se", {}).get("value", "0.5") or 0.5)
        n0 = int(self.facts.get("el_periods", {}).get("value", "12") or 12)
        self.demo_label()
        self.caption("Standard error vs periods observed · same fit, more data")
        ns = np.arange(3, 121)
        se = se0 * np.sqrt(n0 / ns)
        hi = se.max() * 1.1
        ax = self.axes([0, 120, 20], [0, hi, nice_step(0, hi)])
        ax.shift(DOWN * 0.2)
        nums = self.axis_numbers(ax, [12, 60, 120], [round(hi, 1)], xfmt=lambda x: f"{int(x)} periods", yfmt=lambda y: f"±{y:.2f}")
        self.play(Create(ax), FadeIn(nums), run_time=STYLE["chart"]["build_axes_s"])
        line = self.polyline(ax, ns, se, AMBER, 3)
        self.play(Create(line), run_time=STYLE["chart"]["build_data_s"], rate_func=smooth); self.landed()
        dot = Dot(ax.c2p(n0, se0), color=INK, radius=0.08)
        t0 = Text(f"today: {n0} periods, ±{se0:.2f}", font=MONO, font_size=18, color=INK).next_to(dot, UR, buff=0.12)
        self.play(FadeIn(dot), FadeIn(t0), run_time=0.4); self.landed()
        group = VGroup(ax, nums, line, dot, t0)

        def need(target):
            def h(value, label):
                n = float(value.replace(",", ""))
                if n > 120:
                    t = Text(f"{value} periods for ±{target:g}", font=MONO, font_size=20, color=RED).to_corner(DL, buff=0.9)
                    self.play(FadeIn(t), run_time=0.4); self.landed("annotation"); group.add(t); return
                ln = DashedLine(ax.c2p(n, 0), ax.c2p(n, se0 * math.sqrt(n0 / n)), color=INK_60, dash_length=0.1)
                t = Text(f"{value} periods → ±{target:g}", font=MONO, font_size=18, color=INK_60).next_to(ln, UP, buff=0.1)
                self.play(Create(ln), FadeIn(t), run_time=0.4); self.landed("annotation"); group.add(ln, t)
            return h

        self.reveal_loop({"n_for_se_half": need(0.5), "n_for_se_quarter": need(0.25), "n_for_se_tenth": need(0.1)}, skip={"el_se", "el_periods"})
        self.finish(group)
