#MenuTitle: Convert to Cubic
for glyph in Font.glyphs:
    for layer in glyph.layers:
        layer.convertToCubic()
