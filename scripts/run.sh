#!/usr/bin/env bash
#
# run.sh — run a workshop example using the private environment.
#
# You do NOT need to activate anything. This uses the Python installed
# by ./setup.sh, inside this folder.
#
# Usage:
#   ./scripts/run.sh                                  # runs modules/01_first_call/example.py
#   ./scripts/run.sh modules/02_ratings_at_scale/example.py   # run a specific file
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PROJECT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT"

PYTHON="$PROJECT/.venv/bin/python"
TARGET="${1:-modules/01_first_call/example.py}"

if [ ! -x "$PYTHON" ]; then
  echo "The environment isn't set up yet."
  echo "Run this first:  ./scripts/setup.sh"
  exit 1
fi

exec "$PYTHON" "$TARGET"
