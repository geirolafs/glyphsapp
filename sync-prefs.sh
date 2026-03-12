#!/bin/bash
# Sync Glyphs 3 plist between repo and ~/Library/Preferences
# Usage: ./sync-prefs.sh pull   (prefs → repo)
#        ./sync-prefs.sh push   (repo → prefs, quit Glyphs first!)

PLIST="com.GeorgSeifert.Glyphs3.plist"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PREFS="$HOME/Library/Preferences/$PLIST"

case "$1" in
  pull)
    cp "$PREFS" "$REPO_DIR/$PLIST"
    echo "Copied prefs → repo"
    ;;
  push)
    if pgrep -x Glyphs > /dev/null; then
      echo "Quit Glyphs first!" >&2; exit 1
    fi
    cp "$REPO_DIR/$PLIST" "$PREFS"
    echo "Copied repo → prefs"
    ;;
  *)
    echo "Usage: $0 {pull|push}" >&2; exit 1
    ;;
esac
