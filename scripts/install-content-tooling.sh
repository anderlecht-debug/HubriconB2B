#!/usr/bin/env bash
# One-time, interactive: builds the content venv on a uv-managed Python 3.13
# (Manim CE does not run on 3.14), installs the engine beside it, and puts the
# brand fonts where Pango can see them. No sudo. Re-runnable.
set -euo pipefail
WT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WT/content"
uv python install 3.13
[ -d .venv ] || uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -e . -e ../engine
# The placeholder voice and the alignment/QA transcriber are optional: a wheel
# gap on a new Python must not block the rest of the pipeline.
uv pip install --python .venv/bin/python -e ".[voice]" || echo "voice extras unavailable; placeholder narration will be marked blocked"
mkdir -p "$HOME/.local/share/fonts"
cp assets/fonts/*.ttf "$HOME/.local/share/fonts/"
fc-cache -f >/dev/null 2>&1 || true
.venv/bin/python - <<'PY'
import importlib
for m in ("manim", "elevenlabs", "googleapiclient", "openpyxl", "hubricon_engine"):
    try:
        importlib.import_module(m); print(f"ok   {m}")
    except Exception as e:
        print(f"FAIL {m}: {e}")
for m in ("kokoro_onnx", "faster_whisper"):
    try:
        importlib.import_module(m); print(f"ok   {m} (optional)")
    except Exception as e:
        print(f"skip {m}: {type(e).__name__}")
PY
echo "content tooling ready: $WT/content/.venv"
