#MenuTitle: Interpolation Preview
# -*- coding: utf-8 -*-
__doc__ = """Preview interpolation along the font's axes with one slider per axis. Type text to preview a string, or leave the field empty to follow the selected glyphs. Shows interpolated kerning, at a fixed size or fitted to the window."""

import sys
import traceback
import objc
from vanilla import FloatingWindow, Slider, TextBox, Group, EditText, PopUpButton, CheckBox
from AppKit import (
	NSView, NSColor, NSBezierPath, NSAffineTransform, NSMakeRect, NSMakePoint,
	NSFont, NSFontAttributeName, NSForegroundColorAttributeName,
	NSAttributedString, NSViewWidthSizable, NSViewHeightSizable,
)
from GlyphsApp import Glyphs, GSInstance, UPDATEINTERFACE, LTR


BAR_COLORS = [
	NSColor.colorWithCalibratedRed_green_blue_alpha_(0.20, 0.45, 0.85, 1),  # blue
	NSColor.colorWithCalibratedRed_green_blue_alpha_(0.90, 0.50, 0.10, 1),  # orange
	NSColor.colorWithCalibratedRed_green_blue_alpha_(0.20, 0.70, 0.35, 1),  # green
	NSColor.colorWithCalibratedRed_green_blue_alpha_(0.75, 0.25, 0.55, 1),  # purple
	NSColor.colorWithCalibratedRed_green_blue_alpha_(0.85, 0.20, 0.20, 1),  # red
]
MAX_GLYPHS = 300
# Pixels per em. None fits the text to the window.
SIZES = [None, 12, 16, 24, 36, 48, 72, 96, 144, 200]
PAD = 20
AXIS_ROW_H = 50
BAR_ROW_H = 22


# The ObjC class outlives the script run, so it only forwards drawing to a
# Python callback. Drawing code can then change without restarting Glyphs.
try:
	IPCallbackView = objc.lookUpClass("IPCallbackView")
except objc.nosuchclass_error:
	class IPCallbackView(NSView):
		def drawRect_(self, rect):
			callback = getattr(self, "drawCallback", None)
			if callback:
				callback(self)


def addCallbackView(group, callback):
	view = IPCallbackView.alloc().initWithFrame_(group.getNSView().bounds())
	view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
	view.drawCallback = callback
	group.getNSView().addSubview_(view)
	return view


def drawText(text, x, y, size=12, color=None):
	attrs = {
		NSFontAttributeName: NSFont.systemFontOfSize_(size),
		NSForegroundColorAttributeName: color or NSColor.secondaryLabelColor(),
	}
	NSAttributedString.alloc().initWithString_attributes_(text, attrs).drawAtPoint_(NSMakePoint(x, y))


def kerningBetween(left, right):
	k = left.nextKerningForLayer_direction_(right, LTR)
	# Glyphs returns a huge placeholder when a pair has no kerning at all
	return k if k is not None and abs(k) < 1e6 else 0


def wrapLines(glyphs, advances, maxWidth):
	"""Split glyph indices into lines, breaking after spaces."""
	lines, line, lineW, word, wordW = [], [], 0, [], 0
	for i, g in enumerate(glyphs):
		word.append(i)
		wordW += advances[i]
		isSpace = g.unicode == "0020"
		if isSpace or i == len(glyphs) - 1:
			visibleW = wordW - (advances[i] if isSpace else 0)
			if line and lineW + visibleW > maxWidth:
				lines.append(line)
				line, lineW = [], 0
			line += word
			lineW += wordW
			word, wordW = [], 0
	if line:
		lines.append(line)
	return lines


class InterpolationPreview:
	def __init__(self):
		self.closed = False
		font = Glyphs.font
		if not font:
			self._bail("No font open")
			return
		if len(font.masters) < 2:
			self._bail("Need at least 2 masters")
			return

		self.font = font
		self.masters = list(font.masters)
		self.axes = list(font.axes)
		self.ranges = [
			(min(m.axes[i] for m in self.masters), max(m.axes[i] for m in self.masters))
			for i in range(len(self.axes))
		]
		self.namedInstances = [i for i in font.instances if getattr(i, "type", 0) == 0]

		# One detached instance for the whole session. Setting .font without
		# adding it to font.instances leaves the document unchanged.
		self.instance = GSInstance()
		self.instance.font = font
		self.instance.axes = list(self.masters[0].axes)

		nAxes, nMasters = len(self.axes), len(self.masters)
		bottomH = 10 + 30 + nAxes * AXIS_ROW_H + nMasters * BAR_ROW_H + 8
		W, H = 560, 380 + bottomH
		self.w = FloatingWindow((W, H), "Interpolation – %s" % font.familyName, minSize=(480, 200 + bottomH))

		self.w.text = EditText(
			(10, 10, -10, 22), "",
			placeholder="Type text or /glyphname, or leave empty to follow the selection",
			callback=self._changedCB,
		)
		self.w.previewGroup = Group((10, 42, -10, -bottomH))
		self.preview = addCallbackView(self.w.previewGroup, self._drawPreview)

		# Axis sliders, each with a value label and instance tick marks
		self.sliders, self.axisLabels, self.tickViews = [], [], []
		y = -bottomH + 8
		for i, axis in enumerate(self.axes):
			lo, hi = self.ranges[i]
			label = TextBox((15, y, -10, 17), "", sizeStyle="small")
			slider = Slider(
				(15, y + 16, -10, 23),
				minValue=lo, maxValue=hi, value=self.instance.axes[i],
				continuous=True, callback=self._changedCB,
			)
			ticks = Group((15, y + 38, -10, 6))
			setattr(self.w, "axisLabel%d" % i, label)
			setattr(self.w, "axisSlider%d" % i, slider)
			setattr(self.w, "axisTicks%d" % i, ticks)
			self.axisLabels.append(label)
			self.sliders.append(slider)
			self.tickViews.append(addCallbackView(ticks, lambda v, i=i: self._drawTicks(v, i)))
			y += AXIS_ROW_H

		self.w.instancePopup = PopUpButton(
			(15, y, 220, 22),
			["Jump to instance…"] + [inst.name for inst in self.namedInstances],
			sizeStyle="small", callback=self._instanceCB,
		)
		self.w.sizePopup = PopUpButton(
			(245, y, 100, 22),
			["Size: Fit" if v is None else "Size: %d px" % v for v in SIZES],
			sizeStyle="small", callback=self._changedCB,
		)
		self.w.kerning = CheckBox((360, y, 100, 22), "Kerning", value=True, sizeStyle="small", callback=self._changedCB)
		y += 30

		# Per-master bars show each master's share of the current mix
		self.bars, self.barLabels, self.shares = [], [], [0.0] * nMasters
		nameW, pctW = 120, 45
		for i, m in enumerate(self.masters):
			setattr(self.w, "masterName%d" % i, TextBox((15, y, nameW, 18), m.name, sizeStyle="small"))
			barGroup = Group((nameW + 15, y + 1, -(pctW + 20), 14))
			setattr(self.w, "barGroup%d" % i, barGroup)
			self.bars.append(addCallbackView(barGroup, lambda v, i=i: self._drawBar(v, i)))
			pct = TextBox((-(pctW + 15), y, pctW, 18), "0%", alignment="right", sizeStyle="small")
			setattr(self.w, "pctLabel%d" % i, pct)
			self.barLabels.append(pct)
			y += BAR_ROW_H

		self.w.bind("close", self._windowClosed)
		Glyphs.addCallback(self._interfaceUpdated, UPDATEINTERFACE)
		self._update()
		self.w.open()

	def _bail(self, msg):
		self.closed = True
		Glyphs.showMacroWindow()
		print("Interpolation Preview:", msg)

	def _windowClosed(self, sender):
		self.closed = True
		Glyphs.removeCallback(self._interfaceUpdated, UPDATEINTERFACE)

	# Callbacks

	def _changedCB(self, sender):
		self._update()

	def _interfaceUpdated(self, info):
		# Fires on selection changes and outline edits
		self.preview.setNeedsDisplay_(True)

	def _instanceCB(self, sender):
		index = sender.get()
		if index > 0:
			values = self.namedInstances[index - 1].axes
			for slider, value in zip(self.sliders, values):
				slider.set(value)
			sender.set(0)
			self._update()

	def _update(self):
		self.instance.axes = [s.get() for s in self.sliders]
		for i, axis in enumerate(self.axes):
			self.axisLabels[i].set("%s  %g" % (axis.name, round(self.sliders[i].get(), 1)))
		mix = dict(self.instance.instanceInterpolations)
		self.shares = [max(0.0, min(1.0, mix.get(m.id, 0.0))) for m in self.masters]
		for i, share in enumerate(self.shares):
			self.barLabels[i].set("%d%%" % round(share * 100))
			self.bars[i].setNeedsDisplay_(True)
		self.preview.setNeedsDisplay_(True)

	# Glyph lookup

	def _sourceGlyphs(self):
		"""Glyphs to preview, from the text field or else the current selection."""
		text = self.w.text.get()
		if not text:
			return [l.parent for l in (self.font.selectedLayers or [])][:MAX_GLYPHS]
		glyphs, i = [], 0
		while i < len(text) and len(glyphs) < MAX_GLYPHS:
			if text[i] == "/":
				j = i + 1
				while j < len(text) and text[j] not in " /":
					j += 1
				glyph = self.font.glyphs[text[i + 1:j]]
				i = j + 1 if j < len(text) and text[j] == " " else j
			else:
				glyph = self.font.glyphForCharacter_(ord(text[i]))
				i += 1
			if glyph:
				glyphs.append(glyph)
		return glyphs

	# Drawing

	def _drawPreview(self, view):
		try:
			self._drawPreviewUnsafe(view)
		except Exception:
			Glyphs.showMacroWindow()
			traceback.print_exc()

	def _drawPreviewUnsafe(self, view):
		b = view.bounds()
		W, H = b.size.width, b.size.height
		NSColor.textBackgroundColor().set()
		NSBezierPath.fillRect_(b)

		glyphs = self._sourceGlyphs()
		if not glyphs:
			drawText("Select a glyph or type text.", PAD, H / 2)
			return
		incompatible = [g.name for g in glyphs if not g.mastersCompatible]
		if incompatible:
			drawText("Masters are not compatible: %s" % ", ".join(sorted(set(incompatible))), PAD, H / 2,
				color=NSColor.systemRedColor())
			return

		desc = min(m.descender for m in self.masters)
		asc = max(max(m.ascender, m.capHeight) for m in self.masters)
		proxy = self.instance.interpolatedFontProxy
		layers = [proxy.glyphs[g.name].layers[0] for g in glyphs]
		kern = self.w.kerning.get()
		advances = [
			layer.width + (kerningBetween(layer, layers[i + 1]) if kern and i + 1 < len(layers) else 0)
			for i, layer in enumerate(layers)
		]
		guide = NSColor.tertiaryLabelColor()
		size = SIZES[self.w.sizePopup.get()]

		if size is None:
			# Scale from fixed metrics and the widest master widths, so the
			# preview keeps its scale while the slider moves.
			maxW = sum(max(g.layers[m.id].width for m in self.masters) for g in glyphs)
			s = min((W - 2 * PAD) / max(maxW, 1), (H - 2 * PAD) / (asc - desc))
			x0 = (W - maxW * s) / 2
			baseY = (H - (asc - desc) * s) / 2 - desc * s
			lines = [list(range(len(layers)))]
		else:
			s = size / float(self.font.upm)
			x0 = PAD
			baseY = H - PAD - asc * s
			lines = wrapLines(glyphs, advances, (W - 2 * PAD) / s)
		lineH = (asc - desc) * s * 1.2

		for line in lines:
			if baseY + desc * s < 0:
				break
			guide.set()
			NSBezierPath.fillRect_(NSMakeRect(PAD / 2, baseY, W - PAD, 1))
			x = x0
			NSColor.textColor().set()
			for i in line:
				path = layers[i].completeBezierPath
				if path:
					xf = NSAffineTransform.transform()
					xf.translateXBy_yBy_(x, baseY)
					xf.scaleBy_(s)
					xf.transformBezierPath_(path).fill()
				x += advances[i] * s
			if size is None:
				# Advance width markers at the start and end of the run
				guide.set()
				for gx in (x0, x):
					NSBezierPath.fillRect_(NSMakeRect(gx, baseY + desc * s, 1, (asc - desc) * s))
			baseY -= lineH

	def _drawTicks(self, view, axisIndex):
		lo, hi = self.ranges[axisIndex]
		if hi <= lo:
			return
		b = view.bounds()
		# Match the slider's knob travel, which stops half a knob from each end
		try:
			inset = self.sliders[axisIndex].getNSSlider().cell().knobThickness() / 2
		except AttributeError:
			inset = 10
		NSColor.secondaryLabelColor().set()
		for inst in self.namedInstances:
			v = inst.axes[axisIndex]
			x = inset + (v - lo) / (hi - lo) * (b.size.width - 2 * inset)
			NSBezierPath.fillRect_(NSMakeRect(round(x), 0, 1, b.size.height))

	def _drawBar(self, view, i):
		b = view.bounds()
		NSColor.quaternaryLabelColor().set()
		NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(b, 3, 3).fill()
		if self.shares[i] > 0:
			filled = NSMakeRect(b.origin.x, b.origin.y, b.size.width * self.shares[i], b.size.height)
			BAR_COLORS[i % len(BAR_COLORS)].set()
			NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(filled, 3, 3).fill()


previous = getattr(sys, "_ip_instance", None)
if previous is not None and getattr(previous, "w", None) and previous.w.getNSWindow() is not None:
	previous.w.close()

try:
	sys._ip_instance = InterpolationPreview()
except Exception:
	Glyphs.showMacroWindow()
	traceback.print_exc()
