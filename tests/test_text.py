"""
build123d Helper Utilities tests

name: test_utils.py
by:   jwagenet
date: July 28th 2025

desc: Unit tests for the build123d helper utilities module
"""

import unittest

from build123d import *
from build123d.utils import FontInfo


class TestFontHelpers(unittest.TestCase):
    """Tests for font helpers."""

    def test_font_info(self):
        """Test expected FontInfo repr."""
        name = "Arial"
        styles = tuple(member for member in FontStyle)
        font = FontInfo(name, styles)

        self.assertEqual(
            repr(font), f"Font(name={name!r}, styles={tuple(s.name for s in styles)})"
        )

    def test_available_fonts(self):
        """Test expected output for available fonts."""
        fonts = available_fonts()
        self.assertIsInstance(fonts, list)
        for font in fonts:
            self.assertIsInstance(font, FontInfo)
            self.assertIsInstance(font.name, str)
            self.assertIsInstance(font.styles, tuple)
            for style in font.styles:
                self.assertIsInstance(style, FontStyle)

        names = [font.name for font in fonts]
        self.assertEqual(names, sorted(names))


if __name__ == "__main__":
    unittest.main()
