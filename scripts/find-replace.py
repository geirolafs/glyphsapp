#MenuTitle: Find & Replace Glyph Names
# -*- coding: utf-8 -*-
__doc__ = """
Find/replace and suffix selected glyph names.
"""

from vanilla import FloatingWindow, TextBox, EditText, Button

class FindReplaceDialog:
	def __init__(self):
		self.w = FloatingWindow((300, 170), "Rename Glyphs")
		self.w.findLabel = TextBox((10, 12, 80, 17), "Find:")
		self.w.findField = EditText((90, 10, -10, 22))
		self.w.replaceLabel = TextBox((10, 42, 80, 17), "Replace:")
		self.w.replaceField = EditText((90, 40, -10, 22))
		self.w.suffixLabel = TextBox((10, 72, 80, 17), "Suffix:")
		self.w.suffixField = EditText((90, 70, -10, 22), placeholder=".ss01")
		self.w.button = Button((90, 120, -10, 20), "Apply", callback=self.apply)
		self.w.open()

	def apply(self, sender):
		old = self.w.findField.get() or ""
		new = self.w.replaceField.get() or ""
		suffix = self.w.suffixField.get() or ""
		count = 0
		for layer in Font.selectedLayers:
			name = layer.parent.name
			if old and old in name:
				name = name.replace(old, new)
			if suffix:
				name = name + suffix
			if name != layer.parent.name:
				layer.parent.name = name
				count += 1
		print(f"Renamed {count} glyphs")
		self.w.close()

FindReplaceDialog()
