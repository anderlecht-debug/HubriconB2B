"""Hubricon's content pipeline.

Every figure that reaches a viewer comes from an engine run (`facts.py`), every
chart is a Manim scene driven by that run (`scenes/`), and nothing renders or
uploads without the founder's approval (`state.py`). The package is deliberately
a set of small idempotent steps, because the unattended runner re-enters cold
from `queue.json` after every usage-limit reset.
"""

__version__ = "0.1.0"
