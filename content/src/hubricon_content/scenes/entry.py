"""The module `manim render` is pointed at. Manim registers only scene classes
defined in the loaded file itself, so each scene is re-declared here as a thin
subclass of its implementation in charts.py."""
from hubricon_content.scenes import charts as _c


class ChapterCard(_c.ChapterCard):
    pass


class Kinetic(_c.Kinetic):
    pass


class Screenshot(_c.Screenshot):
    pass


class Waterfall(_c.Waterfall):
    pass


class CashCone(_c.CashCone):
    pass


class Paths(_c.Paths):
    pass


class Elasticity(_c.Elasticity):
    pass


class Newsvendor(_c.Newsvendor):
    pass


class SampleSize(_c.SampleSize):
    pass
