"""
Helper Utilities

name: utils.py
by:   jwagenet
date: July 28th 2025

desc:
    This python module contains helper utilities not related to object creation.

"""

from dataclasses import dataclass

from build123d.build_enums import FontStyle
from OCP.Font import (
    Font_FA_Bold,
    Font_FA_BoldItalic,
    Font_FA_Italic,
    Font_FA_Regular,
    Font_FontMgr,
)


@dataclass(frozen=True)
class FontInfo:
    name: str
    styles: tuple[FontStyle, ...]

    def __repr__(self) -> str:
        style_names = tuple(s.name for s in self.styles)
        return f"Font(name={self.name!r}, styles={style_names})"


def available_fonts() -> list[FontInfo]:
    """Get list of available fonts by name and available styles (also called aspects).
    Note: on Windows, fonts must be installed with "Install for all users" to be found.
    """

    font_aspects = {
        "REGULAR": Font_FA_Regular,
        "BOLD": Font_FA_Bold,
        "BOLDITALIC": Font_FA_BoldItalic,
        "ITALIC": Font_FA_Italic,
    }

    manager = Font_FontMgr.GetInstance_s()
    font_list = []
    for f in manager.GetAvailableFonts():
        avail_aspects = tuple(
            FontStyle[n] for n, a in font_aspects.items() if f.HasFontAspect(a)
        )
        font_list.append(FontInfo(f.FontName().ToCString(), avail_aspects))

    font_list.sort(key=lambda x: x.name)

    return font_list