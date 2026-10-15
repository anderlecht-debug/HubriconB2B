"""The module `manim render` is pointed at. Manim registers only scene classes
defined in the loaded file itself, so each scene is re-declared here as a thin
subclass of its implementation in charts.py."""
from manim import config

# `-r 1080,1920` moves the pixel frame and leaves the logical one at 16:9, and the
# camera then holds frame_width and stretches frame_height to the new aspect
# (Camera.resize_frame_shape), so every px the stage is laid out in lands a third of
# its size and the whole scene sits in a 16:9 island with dead paper above and below
# it, which is what V01's vertical cuts failed on (2026-10-05). The logical frame
# follows the pixels here, before a scene is built; at 16:9 it is the value it
# already had.
config.frame_width = config.frame_height * config.pixel_width / config.pixel_height

from hubricon_content.scenes import charts as _c   # noqa: E402  (after the frame is set)


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
