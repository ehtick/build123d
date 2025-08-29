"""
build123d imports

name: test_color.py
by:   Gumyr
date: January 22, 2025

desc:
    This python module contains tests for the build123d project.

license:

    Copyright 2025 Gumyr

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

import copy
import unittest

import numpy as np
from build123d.geometry import Color
from OCP.Quantity import Quantity_ColorRGBA


class TestColor(unittest.TestCase):
    # name + alpha overload
    def test_name1(self):
        c = Color("blue")
        np.testing.assert_allclose(tuple(c), (0, 0, 1, 1), 1e-5)

    def test_name2(self):
        c = Color("blue", alpha=0.5)
        np.testing.assert_allclose(tuple(c), (0, 0, 1, 0.5), 1e-5)

    def test_name3(self):
        c = Color("blue", 0.5)
        np.testing.assert_allclose(tuple(c), (0, 0, 1, 0.5), 1e-5)

    # red + green + blue + alpha overload
    def test_rgb0(self):
        c = Color(0.0, 1.0, 0.0)
        np.testing.assert_allclose(tuple(c), (0, 1, 0, 1), 1e-5)

    def test_rgba1(self):
        c = Color(1.0, 1.0, 0.0, 0.5)
        self.assertEqual(c.wrapped.GetRGB().Red(), 1.0)
        self.assertEqual(c.wrapped.GetRGB().Green(), 1.0)
        self.assertEqual(c.wrapped.GetRGB().Blue(), 0.0)
        self.assertEqual(c.wrapped.Alpha(), 0.5)

    def test_rgba2(self):
        c = Color(1.0, 1.0, 0.0, alpha=0.5)
        np.testing.assert_allclose(tuple(c), (1, 1, 0, 0.5), 1e-5)

    def test_rgba3(self):
        c = Color(red=0.1, green=0.2, blue=0.3, alpha=0.5)
        np.testing.assert_allclose(tuple(c), (0.1, 0.2, 0.3, 0.5), 1e-5)

    # hex (int) + alpha overload
    def test_hex(self):
        c = Color(0x996692)
        np.testing.assert_allclose(
            tuple(c), (0x99 / 0xFF, 0x66 / 0xFF, 0x92 / 0xFF, 1), 5
        )

        c = Color(0x006692, 0x80)
        np.testing.assert_allclose(
            tuple(c), (0, 0x66 / 0xFF, 0x92 / 0xFF, 0x80 / 0xFF), 5
        )

        c = Color(0x006692, alpha=0x80)
        np.testing.assert_allclose(tuple(c), (0, 102 / 255, 146 / 255, 128 / 255), 1e-5)

        c = Color(color_code=0x996692, alpha=0xCC)
        np.testing.assert_allclose(
            tuple(c), (153 / 255, 102 / 255, 146 / 255, 204 / 255), 5
        )

        c = Color(0.0, 0.0, 1.0, 1.0)
        np.testing.assert_allclose(tuple(c), (0, 0, 1, 1), 1e-5)

        c = Color(0, 0, 1, 1)
        np.testing.assert_allclose(tuple(c), (0, 0, 1, 1), 1e-5)

    # Methods
    def test_to_tuple(self):
        c = Color("blue", alpha=0.5)
        np.testing.assert_allclose(tuple(c), (0, 0, 1, 0.5), 1e-5)

    def test_copy(self):
        c = Color(0.1, 0.2, 0.3, alpha=0.4)
        c_copy = copy.copy(c)
        np.testing.assert_allclose(tuple(c_copy), (0.1, 0.2, 0.3, 0.4), 1e-5)

    def test_str_repr(self):
        c = Color(1, 0, 0)
        self.assertEqual(str(c), "Color: (1.0, 0.0, 0.0, 1.0) is 'RED'")
        self.assertEqual(repr(c), "Color(1.0, 0.0, 0.0, 1.0)")

        c = Color(1, .5, 0)
        self.assertEqual(str(c), "Color: (1.0, 0.5, 0.0, 1.0) near 'DARKGOLDENROD1'")
        self.assertEqual(repr(c), "Color(1.0, 0.5, 0.0, 1.0)")

    def test_tuple(self):
        c = Color((0.1,))
        np.testing.assert_allclose(tuple(c), (0.1, 1.0, 1.0, 1.0), 1e-5)
        c = Color((0.1, 0.2))
        np.testing.assert_allclose(tuple(c), (0.1, 0.2, 1.0, 1.0), 1e-5)
        c = Color((0.1, 0.2, 0.3))
        np.testing.assert_allclose(tuple(c), (0.1, 0.2, 0.3, 1.0), 1e-5)
        c = Color((0.1, 0.2, 0.3, 0.4))
        np.testing.assert_allclose(tuple(c), (0.1, 0.2, 0.3, 0.4), 1e-5)
        c = Color(color_like=(0.1, 0.2, 0.3, 0.4))
        np.testing.assert_allclose(tuple(c), (0.1, 0.2, 0.3, 0.4), 1e-5)

    # color_like overload
    def test_color_like(self):
        red_color_likes = [
            Quantity_ColorRGBA(1, 0, 0, 1),
            "red",
            "red ",
            ("red",),
            ("red", 1),
            "#ff0000",
            " #ff0000 ",
            ("#ff0000",),
            ("#ff0000", 1),
            0xff0000,
            (0xff0000),
            (0xff0000, 0xff),
            (1, 0, 0),
            (1, 0, 0, 1),
            (1., 0., 0.),
            (1., 0., 0., 1.)
            ]
        expected = (1, 0, 0, 1)
        for cl in red_color_likes:
            np.testing.assert_allclose(tuple(Color(cl)), expected, 1e-5)
            np.testing.assert_allclose(tuple(Color(color_like=cl)), expected, 1e-5)

        incomplete_color_likes = [
            (Color(), (1, 1, 1, 1)),
            (1., (1, 1, 1, 1)),
            ((1.,), (1, 1, 1, 1)),
            ((1., 0.), (1, 0, 1, 1)),
            ]
        for cl, expected in incomplete_color_likes:
            np.testing.assert_allclose(tuple(Color(cl)), expected, 1e-5)
            np.testing.assert_allclose(tuple(Color(color_like=cl)), expected, 1e-5)

        alpha_color_likes = [
            Quantity_ColorRGBA(1, 0, 0, 0.6),
            ("red", 0.6),
            ("#ff0000", 0.6),
            (0xff0000, 153),
            (1., 0., 0., 0.6)
            ]
        expected = (1, 0, 0, 0.6)
        for cl in alpha_color_likes:
            np.testing.assert_allclose(tuple(Color(cl)), expected, 1e-5)
            np.testing.assert_allclose(tuple(Color(color_like=cl)), expected, 1e-5)

    # Exceptions
    def test_bad_color_name(self):
        with self.assertRaises(ValueError):
            Color("build123d")

    def test_bad_color_type(self):
        with self.assertRaises(TypeError):
            Color(dict({"name": "red", "alpha": 1}))

        with self.assertRaises(TypeError):
            Color("red", "blue")

        with self.assertRaises(TypeError):
            Color(1., "blue")

        with self.assertRaises(TypeError):
            Color(1, "blue")

if __name__ == "__main__":
    unittest.main()
