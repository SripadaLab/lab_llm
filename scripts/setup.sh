#!/usr/bin/env bash
#
# setup.sh — one-command setup for macOS / Linux.
#
# Installs a private Python and all dependencies INSIDE this folder.
# Nothing is installed on your system. Deleting this folder (or running
# ./uninstall.sh) removes every trace.
#
# Usage:  ./scripts/setup.sh
#
set -euo pipefail

# Resolve the project root (one level up from this scripts/ folder).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PROJECT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT"

BIN="$PROJECT/.bin"

# Keep uv's Python, cache, and the virtual environment all inside the project.
export UV_INSTALL_DIR="$BIN"
export INSTALLER_NO_MODIFY_PATH=1
export UV_PYTHON_INSTALL_DIR="$PROJECT/.python"
export UV_CACHE_DIR="$PROJECT/.cache"

PYTHON_VERSION="3.12"

echo "==> Setting up in: $PROJECT"
echo "    Everything installs inside this folder. Your system stays untouched."
echo

# 1. Get uv (a small, self-contained tool) into ./.bin if it isn't there yet.
if [ ! -x "$BIN/uv" ]; then
  echo "==> Downloading uv (the installer tool)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
else
  echo "==> uv already present, skipping download."
fi

UV="$BIN/uv"

# 2. Download a private Python, just for this project.
echo "==> Installing a private Python $PYTHON_VERSION (this may take a minute)..."
"$UV" python install "$PYTHON_VERSION"

# 3. Create the environment and install the workshop package + dependencies.
echo "==> Creating the environment (.venv) and installing packages..."
"$UV" venv "$PROJECT/.venv" --python "$PYTHON_VERSION"
VIRTUAL_ENV="$PROJECT/.venv" "$UV" pip install -e "$PROJECT"

# 4. Create a .env for your API key if you don't have one yet.
if [ ! -f "$PROJECT/.env" ]; then
  cp "$PROJECT/.env.example" "$PROJECT/.env"
  echo "==> Created .env — open it and paste your OpenAI key."
fi

echo
echo "Done. Next steps:"
echo "  1. Open .env and paste your OpenAI API key."
echo "  2. Run the first example:  ./scripts/run.sh"
echo
echo "To remove everything later:  ./scripts/uninstall.sh  (or just delete this folder)."
