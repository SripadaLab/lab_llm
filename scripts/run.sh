#!/usr/bin/env bash
#
# run.sh — run a workshop example using the private environment.
#
# You do NOT need to activate anything. This uses the Python installed
# by ./scripts/setup.sh, inside this folder.
#
# Usage:
#   ./scripts/run.sh modules/01_first_call/example.py
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PROJECT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT"

PYTHON="$PROJECT/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "The environment isn't set up yet."
  echo "Run this first:  ./scripts/setup.sh"
  exit 1
fi

if [ "$#" -lt 1 ]; then
  echo "Usage: ./scripts/run.sh <path-to-example>"
  echo "Example: ./scripts/run.sh modules/01_first_call/example.py"
  exit 1
fi

exec "$PYTHON" "$1"
