#!/bin/zsh
set -eu
GLGMESH_ROOT="${0:A:h}"
export PYTHONPATH="$GLGMESH_ROOT${PYTHONPATH:+:$PYTHONPATH}"
PY="${GLGMESH_PYTHON:-python3.12}"
if ! command -v "$PY" >/dev/null 2>&1; then
  print -u2 'GLGMesh requires Python 3.12. Install it on PATH or set GLGMESH_PYTHON.'
  exit 127
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else "GLGMesh requires Python 3.12; check GLGMESH_PYTHON.")'
exec "$PY" -m glgmesh "$@"
