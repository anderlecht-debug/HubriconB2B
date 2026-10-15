"""The committed demo catalogue is exactly what the generator writes: a change
to either without the other is a change to published numbers."""
from pathlib import Path

from hubricon_content import demo


def test_generator_matches_committed_files(tmp_path):
    demo.generate(out=tmp_path)
    committed = sorted(p.name for p in demo.DEMO_DIR.glob("*.csv"))
    fresh = sorted(p.name for p in tmp_path.glob("*.csv"))
    assert committed == fresh
    for name in committed:
        assert (tmp_path / name).read_bytes() == (demo.DEMO_DIR / name).read_bytes(), name


def test_manifest_labels_demo():
    import json
    m = json.loads((demo.DEMO_DIR / "manifest.json").read_text())
    assert "demo data" in m["label"]
    assert m["seed"] == demo.SEED and len(m["files"]) == 35
