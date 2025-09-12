"""
build123d tests

name: test_constrained_arcs.py
by:   Gumyr
date: September 12, 2025

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

import pytest
from build123d.objects_curve import (
    CenterArc,
    Line,
    PolarLine,
    JernArc,
    IntersectingLine,
    ThreePointArc,
)
from build123d.objects_sketch import Rectangle
from build123d.topology import Edge, Solid, Vertex
from build123d.geometry import Axis, Vector
from build123d.build_enums import PositionConstraint, LengthConstraint, LengthMode


radius = 0.5
e1 = Line((-2, 0), (2, 0))
# e2 = (1, 1)
e2 = Line((0, -2), (0, 2))
e1 = CenterArc((0, 0), 1, 0, 90)
e2 = Line((1, 0), (2, 0))
e1.color = "Grey"
e2.color = "Red"


def test_constrained_arcs_0():
    """Test input error handling"""
    with pytest.raises(TypeError):
        Edge.make_constrained_arcs(Solid.make_box(1, 1, 1), (1, 0), radius=0.5)
    with pytest.raises(TypeError):
        Edge.make_constrained_arcs(
            (Vector(0, 0), PositionConstraint.UNQUALIFIED), (1, 0), radius=0.5
        )
    with pytest.raises(TypeError):
        Edge.make_constrained_arcs(pnt1=(1, 1, 1), pnt2=(1, 0), radius=0.5)
    with pytest.raises(TypeError):
        Edge.make_constrained_arcs(radius=0.1)
    with pytest.raises(ValueError):
        Edge.make_constrained_arcs((0, 0), (0, 0.5), radius=0.5, center=(0, 0.25))
    with pytest.raises(ValueError):
        Edge.make_constrained_arcs((0, 0), (0, 0.5), radius=-0.5)


def test_constrained_arcs_1():
    """2 edges & radius"""
    e1 = Line((-2, 0), (2, 0))
    e2 = Line((0, -2), (0, 2))

    tan2_rad_edges = Edge.make_constrained_arcs(
        e1,
        e2,
        radius=0.5,
        sagitta_constraint=LengthConstraint.BOTH,
    )
    assert len(tan2_rad_edges) == 8

    tan2_rad_edges = Edge.make_constrained_arcs(e1, e2, radius=0.5)
    assert len(tan2_rad_edges) == 4


def test_constrained_arcs_2():
    """2 edges & radius"""
    e1 = CenterArc((0, 0), 1, 0, 90)
    e2 = Line((1, 0), (2, 0))

    tan2_rad_edges = Edge.make_constrained_arcs(e1, e2, radius=0.5)
    assert len(tan2_rad_edges) == 1


def test_constrained_arcs_3():
    """2 points & radius"""
    tan2_rad_edges = Edge.make_constrained_arcs((0, 0), (0, 0.5), radius=0.5)
    assert len(tan2_rad_edges) == 2

    tan2_rad_edges = Edge.make_constrained_arcs(
        Vertex(0, 0), Vertex(0, 0.5), radius=0.5
    )
    assert len(tan2_rad_edges) == 2

    tan2_rad_edges = Edge.make_constrained_arcs(
        Vector(0, 0), Vector(0, 0.5), radius=0.5
    )
    assert len(tan2_rad_edges) == 2


#     tan2_rad_edges = Edge.make_constrained_arcs(
#         (e1, PositionConstraint.OUTSIDE),
#         (e2, PositionConstraint.UNQUALIFIED),
#         radius=radius,
#         sagitta_constraint=LengthConstraint.SHORT,
#     )


# # 2 lines & radius

# # 2 points & radius
# p1 = Vector(0, 0, 0)
# p2 = Vector(3, 0, 0)
# tan2_rad_pnts = Edge().make_constrained_arcs(p1, p2, radius=3)

# #
# # 2 tangents & center on
# c1 = PolarLine((0, 0), 4, -20, length_mode=LengthMode.HORIZONTAL)
# c2 = Line((4, -2), (4, 2))
# c3_center_on_this_line = Line((3, -2), (3, 2))
# c4 = Line((0, 0), (0, 10))
# for c in (c1, c2, c3_center_on_this_line, c4):
#     c.color = "LightGrey"
# tan2_on_edge = Edge.make_constrained_arcs(
#     (c1, PositionConstraint.UNQUALIFIED),
#     (c2, PositionConstraint.UNQUALIFIED),
#     center_on=c3_center_on_this_line,
# )[0]
# l1 = Line(tan2_on_edge @ 0, (0, 0))
# l2 = JernArc(tan2_on_edge @ 1, tan2_on_edge % 1, tan2_on_edge.radius, 45)
# l3 = IntersectingLine(l2 @ 1, l2 % 1, c4)

# #
# # tangent & center
# c5 = PolarLine((0, 0), 4, 60)
# center1 = Vector(2, 1)
# tan_center = Edge.make_constrained_arcs(
#     (c5, PositionConstraint.UNQUALIFIED), center=center1
# )
# #
# # point & center
# p3 = Vector(-2.5, 1.5)
# center2 = Vector(-2, 1)
# pnt_center = Edge.make_constrained_arcs(p3, center=center2)

# #
# # tangent, radius, center on
# # tan_rad_on = Edge.make_constrained_arcs(
# #     (c1, PositionConstraint.UNQUALIFIED), radius=1, center_on=c3_center_on_this_line
# # )
# tan_rad_on = Edge.make_constrained_arcs(c1, radius=1, center_on=c3_center_on_this_line)

# print(f"{len(tan_rad_on)=}")

# objects = [
#     (c1, PositionConstraint.ENCLOSED),
#     (Vector(1, 2, 3), None),
#     (Edge.make_line((0, 0), (1, 0)), PositionConstraint.UNQUALIFIED),
# ]
# s = sorted(objects, key=lambda t: not issubclass(type(t[0]), Edge))
# print(f"{objects=},{s=}")
# #
# # 3 tangents
# c6 = PolarLine((0, 0), 4, 40)
# c7 = CenterArc((0, 0), 4, 0, 90)
# tan3 = Edge.make_constrained_arcs(
#     (c5, PositionConstraint.UNQUALIFIED),
#     (c6, PositionConstraint.UNQUALIFIED),
#     (c7, PositionConstraint.UNQUALIFIED),
# )
# tan3 = Edge.make_constrained_arcs(c5, c6, c7)

# # v = Vertex(1, 2, 0)
# # v.color = "Teal"
# # show(e1, e2, tan2_rad, v)

# r_left, r_right = 0.75, 1.0
# r_bottom, r_top = 6, 8
# con_circle_left = CenterArc((-2, 0), r_left, 0, 360)
# con_circle_right = CenterArc((2, 0), r_right, 0, 360)
# for c in [con_circle_left, con_circle_right]:
#     c.color = "LightGrey"
# # for con1, con2 in itertools.product(PositionConstraint, PositionConstraint):
# #     try:
# #         egg1 = Edge.make_constrained_arcs(
# #             (c8, con1),
# #             (c9, con2),
# #             radius=10,
# #         )
# #     except:
# #         print(f"{con1},{con2} failed")
# #     else:
# #         print(f"{con1},{con2} {len(egg1)=}")
# egg_bottom = Edge.make_constrained_arcs(
#     (con_circle_right, PositionConstraint.OUTSIDE),
#     (con_circle_left, PositionConstraint.OUTSIDE),
#     radius=r_bottom,
# ).sort_by(Axis.Y)[0]
# egg_top = Edge.make_constrained_arcs(
#     (con_circle_right, PositionConstraint.ENCLOSING),
#     (con_circle_left, PositionConstraint.ENCLOSING),
#     radius=r_top,
# ).sort_by(Axis.Y)[-1]
# egg_right = ThreePointArc(
#     egg_bottom.vertices().sort_by(Axis.X)[-1],
#     con_circle_right @ 0,
#     egg_top.vertices().sort_by(Axis.X)[-1],
# )
# egg_left = ThreePointArc(
#     egg_bottom.vertices().sort_by(Axis.X)[0],
#     con_circle_left @ 0.5,
#     egg_top.vertices().sort_by(Axis.X)[0],
# )

# egg_plant = Wire([egg_left, egg_top, egg_right, egg_bottom])


# make_constrained_arcs


# class TestConstrainedArcs(unittest.TestCase):
#     def test_close(self):
#         self.assertAlmostEqual(
#             Edge.make_circle(1, end_angle=180).close().length, math.pi + 2, 5
#         )
#         self.assertAlmostEqual(Edge.make_circle(1).close().length, 2 * math.pi, 5)
