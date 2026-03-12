#MenuTitle: Export Tab SVG
# -*- coding: utf-8 -*-
__doc__ = """Export current edit view tab as a composed SVG."""

import traceback
from GlyphsApp import Glyphs, GetSaveFile


def layer_to_svg_d(layer, x_off, asc):
	"""Convert all contours in a layer to a single SVG path d string."""
	try:
		decomposed = layer.copyDecomposedLayer()
	except:
		decomposed = layer

	def pt(n):
		return "%g %g" % (n.position.x + x_off, asc - n.position.y)

	parts = []
	for path in decomposed.paths:
		nodes = list(path.nodes)
		if not nodes:
			continue

		start = next((j for j, n in enumerate(nodes) if n.type != "offcurve"), None)
		if start is None:
			continue

		ordered = nodes[start:] + nodes[:start]
		d = ["M " + pt(ordered[0])]

		offcurves = []
		for n in ordered[1:]:
			if n.type == "offcurve":
				offcurves.append(n)
			elif n.type == "curve":
				if len(offcurves) >= 2:
					d.append("C %s %s %s" % (pt(offcurves[-2]), pt(offcurves[-1]), pt(n)))
				offcurves = []
			elif n.type == "line":
				d.append("L " + pt(n))
				offcurves = []
			else:
				offcurves = []

		if offcurves and len(offcurves) >= 2:
			d.append("C %s %s %s" % (pt(offcurves[-2]), pt(offcurves[-1]), pt(ordered[0])))

		d.append("Z")
		parts.append(" ".join(d))

	return " ".join(parts)


def get_kern(font, master_id, left, right):
	"""Kerning lookup: glyph > group, both sides."""
	kerning = font.kerning.get(master_id, {})
	if not kerning:
		return 0

	lid = left.id if hasattr(left, "id") else left.name
	rid = right.id if hasattr(right, "id") else right.name
	lg = ("@MMK_L_%s" % left.rightKerningGroup) if left.rightKerningGroup else None
	rg = ("@MMK_R_%s" % right.leftKerningGroup) if right.leftKerningGroup else None

	for l_key in [lid, lg]:
		if not l_key or l_key not in kerning:
			continue
		for r_key in [rid, rg]:
			if r_key and r_key in kerning[l_key]:
				return kerning[l_key][r_key]

	return 0


def export_tab_svg():
	font = Glyphs.font
	if not font:
		print("No font open.")
		return

	tab = font.currentTab
	if not tab:
		print("No edit tab open.")
		return

	layers = tab.layers
	if not layers:
		print("Tab has no layers.")
		return

	master = font.selectedFontMaster
	ascender = master.ascender
	descender = master.descender
	total_h = ascender - descender

	# Collect (x_offset, layer, glyph) tuples
	entries = []
	x = 0
	for i, layer in enumerate(layers):
		if layer is None or not hasattr(layer, "width"):
			continue
		glyph = layer.parent
		if i > 0 and entries and glyph:
			prev_glyph = entries[-1][2]
			if prev_glyph:
				x += get_kern(font, master.id, prev_glyph, glyph)
		entries.append((x, layer, glyph))
		x += layer.width

	if x == 0:
		print("Nothing to export.")
		return

	paths = []
	for x_off, layer, _ in entries:
		d = layer_to_svg_d(layer, x_off, ascender)
		if d:
			paths.append('  <path d="%s"/>' % d)

	svg = (
		'<?xml version="1.0" encoding="UTF-8"?>\n'
		'<svg xmlns="http://www.w3.org/2000/svg" '
		'viewBox="0 0 %g %g" width="%g" height="%g">\n'
		'%s\n'
		'</svg>'
	) % (x, total_h, x, total_h, "\n".join(paths))

	filepath = GetSaveFile("Save SVG", "export.svg", ["svg"])
	if not filepath:
		return

	with open(filepath, "w") as f:
		f.write(svg)

	print("Saved:", filepath)
	Glyphs.showNotification("Export Tab SVG", "Saved to %s" % filepath)


try:
	export_tab_svg()
except:
	Glyphs.showMacroWindow()
	traceback.print_exc()
