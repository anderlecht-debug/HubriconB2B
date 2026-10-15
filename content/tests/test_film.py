"""The films (content/film/): their storyboards, the pre-publish checklist and the
teleprompter, held by the Node tests beside them so the pipeline's one test run covers
the renderer the site's charts draw."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_film_node_tests_pass():
    r = subprocess.run(["node", "--test", "content/film/"], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
