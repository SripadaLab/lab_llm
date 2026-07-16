#!/usr/bin/env bash
#
# uninstall.sh — remove the local install created by setup.sh.
#
# Deletes the private Python, the environment, caches, the downloaded tool,
# and your .env. Source code and run outputs stay.
# (Deleting the whole folder removes those too.)
#
# Usage:  ./scripts/uninstall.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PROJECT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT"

echo "This removes the private Python, the .venv environment, caches, and .env."
echo "Source code and run outputs stay. Folder: $PROJECT"
printf "Continue? [y/N] "
read -r reply
case "$reply" in
  [yY]|[yY][eE][sS]) ;;
  *) echo "Cancelled."; exit 0 ;;
esac

# Installed-in-folder artifacts (safe to delete; setup.sh recreates them).
rm -rf "$PROJECT/.bin" \
       "$PROJECT/.python" \
       "$PROJECT/.cache" \
       "$PROJECT/.venv" \
       "$PROJECT/.env"

# Build and cache leftovers.
rm -rf "$PROJECT"/*.egg-info "$PROJECT/uv.lock"
find "$PROJECT" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true

echo "Done. Source code and run outputs remain."
echo "To set up again:  ./scripts/setup.sh"
