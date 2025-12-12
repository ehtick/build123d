"""
build123d Helper Utilities tests

name: test_text.py
by:   jwagenet
date: July 28th 2025

desc: Unit tests for the build123d font and text module
"""

import unittest
import os

from build123d import available_fonts, FontStyle
from build123d.text import FONT_ASPECT, FontInfo, FontManager


class TestFontManager(unittest.TestCase):
    """Tests for FontManager."""

    def test_add_font(self):
        """Expected to return system font with matching name if it exists"""
        manager = FontManager()
        manager.manager.ClearFontDataBase()
        working_path = os.path.dirname(os.path.abspath(__file__))
        font = manager.bundled_fonts[0]
        font_path = os.path.join(working_path, manager.bundled_path, font[1])
        manager.add_font(font[0], font_path, font[2], font[3], True)

        result = manager.find_font(font[0], font[2])
        self.assertEqual(font[0], result.FontName().ToCString())

    def test_check_font(self):
        """Expected to return system font with matching path if it exists or None"""
        manager = FontManager()
        working_path = os.path.dirname(os.path.abspath(__file__))
        font_path = manager.bundled_fonts[0][1]
        src_path = "src/build123d"

        good_path = os.path.join(working_path, "..", src_path, manager.bundled_path, font_path)
        good_font = manager.check_font(good_path)
        bad_font = manager.check_font(font_path)
        aspect = FONT_ASPECT[FontStyle.REGULAR]

        self.assertEqual(good_path, good_font.FontPath(aspect).ToCString())
        self.assertEqual(None, bad_font)

    def test_find_font(self):
        """Expected to return font with matching name if it exists"""
        manager = FontManager()
        good_name = manager.bundled_fonts[0][0]
        good_font = manager.find_font(good_name, FontStyle.REGULAR)
        bad_font = manager.find_font("build123d", FontStyle.REGULAR)

        self.assertEqual(good_name, good_font.FontName().ToCString())
        self.assertNotEqual("build123d", bad_font.FontName().ToCString())


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
