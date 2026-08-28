#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 "$ROOT/tools/release_gate.py" --root "$ROOT"
python3 "$ROOT/tools/bootstrap.py" --root "$ROOT" --action serve
