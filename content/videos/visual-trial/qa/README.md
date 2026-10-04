# One look: the Phase 0 check (VISUAL_SPEC.md §8.4, §12)

`one-look.png`: left column, the film stage (`content/film`, Chrome, the style reel's staircase
and number scenes); right column, Manim (`scenes/base.py` and `charts.py`), the cash cone and a
spoken number from the demo catalogue's engine run. Both are on `content/assets/tokens.json` and
Inter Display from `content/assets/fonts`.

Measured on 2026-10-04 at 1920×1080: the same heading, caption, number and corner set in both
renderers land on the same pixel rows and columns (heading ink 118–263 vs 117–263, columns
164–1014 in both; corner label and mark 181–1758 in both); the difference image shows only
antialiasing. The charts differ only in what they draw.

Open: the stage's own chart labels (left, top) come out near 33–35 px, because the site's SVG is
fitted to the chart frame by its height; §8.4 asks for at least 40 px at 1080p, which the Manim
charts meet. Phase 4 sizes the stage's charts to the same floor.
