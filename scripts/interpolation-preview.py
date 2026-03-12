#MenuTitle: Interpolation Preview
# -*- coding: utf-8 -*-
__doc__ = """Preview glyph interpolation between masters with a slider."""

import traceback
from vanilla import FloatingWindow, Slider, TextBox, Group
from AppKit import (
	NSImage, NSImageView, NSColor, NSAffineTransform,
	NSMakeRect, NSRectFill, NSImageScaleProportionallyDown,
	NSView, NSBezierPath,
)
from objc import super as objc_super
from GlyphsApp import Glyphs, GSInstance


BAR_COLORS = [
	NSColor.colorWithCalibratedRed_green_blue_alpha_(0.20, 0.45, 0.85, 1),  # blue
	NSColor.colorWithCalibratedRed_green_blue_alpha_(0.90, 0.50, 0.10, 1),  # orange
	NSColor.colorWithCalibratedRed_green_blue_alpha_(0.20, 0.70, 0.35, 1),  # green
	NSColor.colorWithCalibratedRed_green_blue_alpha_(0.75, 0.25, 0.55, 1),  # purple
	NSColor.colorWithCalibratedRed_green_blue_alpha_(0.85, 0.20, 0.20, 1),  # red
]


class BarView(NSView):
	"""Horizontal fill bar: colored portion (0–1) on gray background."""

	def initWithFrame_(self, frame):
		self = objc_super(BarView, self).initWithFrame_(frame)
		if self is None:
			return None
		self._proportion = 0.0
		self._color = BAR_COLORS[0]
		return self

	def setColor_(self, color):
		self._color = color
		self.setNeedsDisplay_(True)

	def setProportion_(self, p):
		self._proportion = max(0.0, min(1.0, p))
		self.setNeedsDisplay_(True)

	def drawRect_(self, rect):
		b = self.bounds()
		NSColor.colorWithCalibratedWhite_alpha_(0.85, 1).set()
		NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(b, 3, 3).fill()
		if self._proportion > 0:
			filled = NSMakeRect(b.origin.x, b.origin.y, b.size.width * self._proportion, b.size.height)
			self._color.set()
			NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(filled, 3, 3).fill()


class InterpolationPreview:
	def __init__(self):
		font = Glyphs.font
		if not font:
			self._bail("No font open")
			return
		if not font.selectedLayers:
			self._bail("No glyph selected")
			return

		self.font = font
		self.glyph = font.selectedLayers[0].parent
		self.masters = list(font.masters)

		if len(self.masters) < 2:
			self._bail("Need at least 2 masters")
			return

		nMasters = len(self.masters)
		barAreaH = nMasters * 22 + 8
		W, H = 500, 440 + barAreaH
		self.imgW = W - 20
		self.imgH = H - 80 - barAreaH

		self.w = FloatingWindow((W, H), u"Interpolation \u2013 %s" % self.glyph.name)

		# Use a Group + raw NSImageView (more reliable than vanilla ImageView)
		self.w.previewGroup = Group((10, 10, -10, -60 - barAreaH))
		self.nsImageView = NSImageView.alloc().initWithFrame_(
			NSMakeRect(0, 0, self.imgW, self.imgH)
		)
		self.nsImageView.setImageScaling_(NSImageScaleProportionallyDown)
		self.w.previewGroup.getNSView().addSubview_(self.nsImageView)

		sliderBottom = 50 + barAreaH
		self.w.slider = Slider(
			(15, -sliderBottom, -10, 23),
			minValue=0, maxValue=1, value=0,
			continuous=True, callback=self._sliderCB,
		)

		# Per-master bar rows
		self.bars = []
		self.barLabels = []
		barY = H - 10 - barAreaH + 4
		nameW = 120
		pctW = 45
		barX = nameW + 15
		barW = W - barX - pctW - 20
		for i, m in enumerate(self.masters):
			y = barY + i * 22
			color = BAR_COLORS[i % len(BAR_COLORS)]
			attrName = "masterName%d" % i
			setattr(self.w, attrName, TextBox((15, y, nameW, 18), m.name, sizeStyle="small"))
			barView = BarView.alloc().initWithFrame_(NSMakeRect(0, 0, barW, 14))
			barView.setColor_(color)
			attrBar = "barGroup%d" % i
			setattr(self.w, attrBar, Group((barX, y + 1, barW, 14)))
			getattr(self.w, attrBar).getNSView().addSubview_(barView)
			self.bars.append(barView)
			attrPct = "pctLabel%d" % i
			setattr(self.w, attrPct, TextBox((barX + barW + 5, y, pctW, 18), "0%", alignment="right", sizeStyle="small"))
			self.barLabels.append(getattr(self.w, attrPct))

		self._updateBars(0)
		self._render(0)
		self.w.open()

	def _bail(self, msg):
		Glyphs.showMacroWindow()
		print("Interpolation Preview:", msg)

	def _sliderCB(self, sender):
		v = sender.get()
		self._updateBars(v)
		self._render(v)

	def _updateBars(self, t):
		n = len(self.masters)
		for i in range(n):
			if i == 0:
				p = 1.0 - t
			elif i == n - 1:
				p = t
			else:
				p = 0.0
			self.bars[i].setProportion_(p)
			self.barLabels[i].set("%d%%" % round(p * 100))

	def _render(self, t):
		try:
			m0, m1 = self.masters[0], self.masters[-1]

			# Create a temporary instance and add to font so interpolatedFont works
			instance = GSInstance()
			instance.manualInterpolation = True
			instance.instanceInterpolations = {m0.id: 1.0 - t, m1.id: t}
			self.font.instances.append(instance)
			try:
				interpFont = instance.interpolatedFont
			finally:
				self.font.instances.remove(instance)

			if not interpFont:
				return

			g = interpFont.glyphs[self.glyph.name]
			if not g:
				return

			layer = g.layers[0]
			bp = layer.completeBezierPath or layer.bezierPath
			if not bp:
				return

			# Render to NSImage (Cocoa coords = Y-up, same as font)
			img = NSImage.alloc().initWithSize_((self.imgW, self.imgH))
			img.lockFocus()

			NSColor.whiteColor().set()
			NSRectFill(NSMakeRect(0, 0, self.imgW, self.imgH))

			b = bp.bounds()
			if b.size.width > 0 and b.size.height > 0:
				pad = 20
				s = min(
					(self.imgW - pad * 2) / b.size.width,
					(self.imgH - pad * 2) / b.size.height,
				)
				ox = (self.imgW - b.size.width * s) / 2
				oy = (self.imgH - b.size.height * s) / 2

				xf = NSAffineTransform.transform()
				xf.translateXBy_yBy_(ox, oy)
				xf.scaleBy_(s)
				xf.translateXBy_yBy_(-b.origin.x, -b.origin.y)

				NSColor.blackColor().set()
				xf.transformBezierPath_(bp).fill()

			img.unlockFocus()
			self.nsImageView.setImage_(img)

		except:
			Glyphs.showMacroWindow()
			traceback.print_exc()


try:
	InterpolationPreview()
except:
	Glyphs.showMacroWindow()
	traceback.print_exc()
