"""
build123d font and text objects

name: text.py
by:   jwagenet
date: July 28th 2025

desc:
    This python module contains font and text objects.

"""

import os
import sys
from dataclasses import dataclass

from OCP.Font import (
    Font_FA_Bold,
    Font_FA_BoldItalic,
    Font_FA_Italic,
    Font_FA_Regular,
    Font_FontMgr,
    Font_SystemFont,
)
from OCP.TCollection import TCollection_AsciiString

from build123d.build_enums import FontStyle


FONT_ASPECT = {
    FontStyle.REGULAR: Font_FA_Regular,
    FontStyle.BOLD: Font_FA_Bold,
    FontStyle.ITALIC: Font_FA_Italic,
    FontStyle.BOLDITALIC: Font_FA_BoldItalic,
}


@dataclass(frozen=True)
class FontInfo:
    """Representation for registered font.

    Not immediately compatible with Font_SystemFont, which only contains a single
    style/aspect.
    """

    name: str
    styles: tuple[FontStyle, ...]

    def __repr__(self) -> str:
        style_names = tuple(s.name for s in self.styles)
        return f"Font(name={self.name!r}, styles={style_names})"


class FontManager:
    """Wrap OCP Font_FontMgr"""

    bundled_path = "data/fonts"
    bundled_fonts = [
        (
            "Relief SingleLine CAD",
            "reliefsingleline/ReliefSingleLineCAD-Regular.ttf",
            FontStyle.REGULAR,
            True,
        )
    ]

    def __init__(self):
        """Initialize FontManager

        Bundled fonts are added to global OCP instance if they haven't already
        """
        # Should clarify if this is necessary
        if sys.platform.startswith("linux"):
            os.environ["FONTCONFIG_FILE"] = "/etc/fonts/fonts.conf"
            os.environ["FONTCONFIG_PATH"] = "/etc/fonts/"

        self.manager = Font_FontMgr.GetInstance_s()

        working_path = os.path.dirname(os.path.abspath(__file__))
        for font in self.bundled_fonts:
            result = self.find_font(font[0], font[2])
            if result.FontName().ToCString() != font[0]:
                font_path = os.path.join(working_path, self.bundled_path, font[1])
                self.add_font(font[0], font_path, font[2], font[3], True)

    def add_font(
        self, name: str, path: str, style: FontStyle, single_stroke=False, override=True
    ) -> None:
        """Add font to FontManager library"""
        system_font = Font_SystemFont(TCollection_AsciiString(name))
        system_font.SetFontPath(FONT_ASPECT[style], TCollection_AsciiString(path))
        system_font.SetSingleStrokeFont(single_stroke)
        self.manager.RegisterFont(system_font, override)

    def check_font(self, path: str) -> Font_SystemFont | None:
        """Check if font exists at path and return system font"""
        return self.manager.CheckFont(path)

    def find_font(self, name: str, style: FontStyle) -> Font_SystemFont:
        """Find font in FontManager library by name and style"""
        return self.manager.FindFont(TCollection_AsciiString(name), FONT_ASPECT[style])

    def available_fonts(self) -> list[FontInfo]:
        """Get list of available fonts by name and available styles (also called aspects).
        Note: on Windows, fonts must be installed with "Install for all users" to be found.
        """

        font_aspects = {
            "REGULAR": Font_FA_Regular,
            "BOLD": Font_FA_Bold,
            "BOLDITALIC": Font_FA_BoldItalic,
            "ITALIC": Font_FA_Italic,
        }

        font_list = []
        for f in self.manager.GetAvailableFonts():
            avail_aspects = tuple(
                FontStyle[n] for n, a in font_aspects.items() if f.HasFontAspect(a)
            )
            font_list.append(FontInfo(f.FontName().ToCString(), avail_aspects))

        font_list.sort(key=lambda x: x.name)

        return font_list


available_fonts = FontManager().available_fonts
