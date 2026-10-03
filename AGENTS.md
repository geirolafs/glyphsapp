# AGENTS.md

Guidance for coding agents working in this repository.

## Overview

Glyphs 3 scripts and sample strings. Scripts run inside Glyphs 3's embedded Python (not standalone). No external deps — only `GlyphsApp`, `vanilla`, `AppKit`/`objc`.

Prefs plist lives in separate private repo (`glyphs-prefs`).

## Symlinks

`~/Library/Application Support/Glyphs 3/Scripts/hallo` → `scripts/` (live symlink, edits go straight to repo).

## Scripts

All in `scripts/`, each starts with `#MenuTitle:` for Glyphs Script menu registration. Use:
- `GlyphsApp` module (Glyphs, GSInstance, GetSaveFile)
- `vanilla` for UI (FloatingWindow, Slider, TextBox, EditText, Button)
- `AppKit`/`objc` for Cocoa rendering (NSImage, NSBezierPath, NSView)

## Strings.plist

Sample/proof strings for Glyphs 3 (spacing, kerning, punctuation, etc.).
