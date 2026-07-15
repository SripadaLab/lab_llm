#!/usr/bin/env bash
#
# uninstall.sh — remove everything setup.sh created.
#
# Deletes the private Python, the environment, caches, the downloaded tool,
# and your .env. Only the source code is left behind.
# (Deleting this whole folder does the same thing.)
#
# Usage:  ./uninstall.sh
#
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$PROJECT"

echo "This removes the private Python, the .venv environment, caches, and .env."
echo "Your source code is kept. Folder: $PROJECT"
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

# Build/run leftovers.
rm -rf "$PROJECT"/*.egg-info "$PROJECT/uv.lock"
find "$PROJECT" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true

echo "Done. Only the source code remains."
echo "To set up again:  ./setup.sh"
