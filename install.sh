#!/usr/bin/env bash
# Install the skills into a host skill directory.
#
#   ./install.sh                                   # symlink to ~/.claude/skills
#   ./install.sh --target ~/.codex/skills          # symlink elsewhere
#   ./install.sh --copy                            # copy instead of symlink
#   ./install.sh --list                            # show what is here
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${HOME}/.claude/skills"
MODE="link"

usage() {
  sed -n '2,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --target)
      [ $# -ge 2 ] || { echo "error: --target needs a path" >&2; exit 1; }
      TARGET="$2"
      shift 2
      ;;
    --copy)
      MODE="copy"
      shift
      ;;
    --list)
      for d in "$ROOT"/skills/*/; do printf '%s\n' "$(basename "$d")"; done
      exit 0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument '$1'" >&2
      usage >&2
      exit 1
      ;;
  esac
done

mkdir -p "$TARGET"

installed=0
skipped=0

for src in "$ROOT"/skills/*/; do
  name="$(basename "$src")"
  dest="$TARGET/$name"

  if [ -L "$dest" ]; then
    rm "$dest"
  elif [ -e "$dest" ]; then
    echo "skip  $name (exists at $dest, not a symlink; remove it manually to replace)"
    skipped=$((skipped + 1))
    continue
  fi

  if [ "$MODE" = "copy" ]; then
    cp -R "$src" "$dest"
    echo "copied $name -> $dest"
  else
    ln -s "$src" "$dest"
    echo "linked $name -> $dest"
  fi
  installed=$((installed + 1))
done

echo
echo "done: $installed installed, $skipped skipped (target: $TARGET)"
echo "restart the host or reload skills if it does not pick them up automatically."
