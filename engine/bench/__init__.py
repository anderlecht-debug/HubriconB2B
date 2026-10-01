"""The engine against planted truths: six synthetic worlds, the whole
pipeline, a month simulated from the truth, and a ten-criterion rubric.

    cd engine && uv run python -m bench.run --tests 3

Everything here is outside the pytest suite on purpose: one world takes
about a minute, and a test is six of them. The criteria, their thresholds and
why each threshold is where it is live in `bench/rubric.py` and in
MATH_SCORECARD.md ("The Simons–Thorp–Griffin test"); they were written down
before the engine was changed to meet them, and a threshold is never moved to
make a run pass.
"""
