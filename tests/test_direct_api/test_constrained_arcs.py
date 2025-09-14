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
from build123d.topology import Edge, Solid, Vertex, Wire, topo_explore_common_vertex
from build123d.geometry import Axis, Vector, TOLERANCE
from build123d.build_enums import Tangency, Sagitta, LengthMode
from OCP.BRep import BRep_Tool
from OCP.GeomAbs import GeomAbs_C1
from OCP.LocalAnalysis import LocalAnalysis_CurveContinuity

radius = 0.5
e1 = Line((-2, 0), (2, 0))
# e2 = (1, 1)
e2 = Line((0, -2), (0, 2))
e1 = CenterArc((0, 0), 1, 0, 90)
e2 = Line((1, 0), (2, 0))
e1.color = "Grey"
e2.color = "Red"


def test_constrained_arcs_arg_processing():
    """Test input error handling"""
    with pytest.raises(TypeError):
        Edge.make_constrained_arcs(Solid.make_box(1, 1, 1), (1, 0), radius=0.5)
    with pytest.raises(TypeError):
        Edge.make_constrained_arcs(
            (Vector(0, 0), Tangency.UNQUALIFIED), (1, 0), radius=0.5
        )
    with pytest.raises(TypeError):
        Edge.make_constrained_arcs(pnt1=(1, 1, 1), pnt2=(1, 0), radius=0.5)
    with pytest.raises(TypeError):
        Edge.make_constrained_arcs(radius=0.1)
    with pytest.raises(ValueError):
        Edge.make_constrained_arcs((0, 0), (0, 0.5), radius=0.5, center=(0, 0.25))
    with pytest.raises(ValueError):
        Edge.make_constrained_arcs((0, 0), (0, 0.5), radius=-0.5)


def test_tan2_rad_arcs_1():
    """2 edges & radius"""
    e1 = Line((-2, 0), (2, 0))
    e2 = Line((0, -2), (0, 2))

    tan2_rad_edges = Edge.make_constrained_arcs(
        e1, e2, radius=0.5, sagitta=Sagitta.BOTH
    )
    assert len(tan2_rad_edges) == 8

    tan2_rad_edges = Edge.make_constrained_arcs(e1, e2, radius=0.5)
    assert len(tan2_rad_edges) == 4

    tan2_rad_edges = Edge.make_constrained_arcs(
        (e1, Tangency.UNQUALIFIED), (e2, Tangency.UNQUALIFIED), radius=0.5
    )
    assert len(tan2_rad_edges) == 4


def test_tan2_rad_arcs_2():
    """2 edges & radius"""
    e1 = CenterArc((0, 0), 1, 0, 90)
    e2 = Line((1, 0), (2, 0))

    tan2_rad_edges = Edge.make_constrained_arcs(e1, e2, radius=0.5)
    assert len(tan2_rad_edges) == 1


def test_tan2_rad_arcs_3():
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


def test_tan2_rad_arcs_4():
    """edge & 1 points & radius"""
    # the point should be automatically moved after the edge
    e1 = Line((0, 0), (1, 0))
    tan2_rad_edges = Edge.make_constrained_arcs((0, 0.5), e1, radius=0.5)
    assert len(tan2_rad_edges) == 1


def test_tan2_center_on_1():
    """2 tangents & center on"""
    c1 = PolarLine((0, 0), 4, -20, length_mode=LengthMode.HORIZONTAL)
    c2 = Line((4, -2), (4, 2))
    c3_center_on = Line((3, -2), (3, 2))
    tan2_on_edge = Edge.make_constrained_arcs(
        (c1, Tangency.UNQUALIFIED),
        (c2, Tangency.UNQUALIFIED),
        center_on=c3_center_on,
    )
    assert len(tan2_on_edge) == 1


def test_tan_center_on_1():
    """1 tangent & center on"""
    c5 = PolarLine((0, 0), 4, 60)
    tan_center = Edge.make_constrained_arcs((c5, Tangency.UNQUALIFIED), center=(2, 1))
    assert len(tan_center) == 1
    assert tan_center[0].is_closed


def test_pnt_center_1():
    """pnt & center"""
    pnt_center = Edge.make_constrained_arcs((-2.5, 1.5), center=(-2, 1))
    assert len(pnt_center) == 1
    assert pnt_center[0].is_closed


def test_tan_rad_center_on_1():
    """tangent, radius, center on"""
    c1 = PolarLine((0, 0), 4, -20, length_mode=LengthMode.HORIZONTAL)
    c3_center_on = Line((3, -2), (3, 2))
    tan_rad_on = Edge.make_constrained_arcs(
        (c1, Tangency.UNQUALIFIED), radius=1, center_on=c3_center_on
    )
    assert len(tan_rad_on) == 1
    assert tan_rad_on[0].is_closed


def test_tan3_1():
    """3 tangents"""
    c5 = PolarLine((0, 0), 4, 60)
    c6 = PolarLine((0, 0), 4, 40)
    c7 = CenterArc((0, 0), 4, 0, 90)
    tan3 = Edge.make_constrained_arcs(
        (c5, Tangency.UNQUALIFIED),
        (c6, Tangency.UNQUALIFIED),
        (c7, Tangency.UNQUALIFIED),
    )
    assert len(tan3) == 1
    assert not tan3[0].is_closed


def test_eggplant():
    """complex set of 4 arcs"""
    r_left, r_right = 0.75, 1.0
    r_bottom, r_top = 6, 8
    con_circle_left = CenterArc((-2, 0), r_left, 0, 360)
    con_circle_right = CenterArc((2, 0), r_right, 0, 360)
    egg_bottom = Edge.make_constrained_arcs(
        (con_circle_right, Tangency.OUTSIDE),
        (con_circle_left, Tangency.OUTSIDE),
        radius=r_bottom,
    ).sort_by(Axis.Y)[0]
    egg_top = Edge.make_constrained_arcs(
        (con_circle_right, Tangency.ENCLOSING),
        (con_circle_left, Tangency.ENCLOSING),
        radius=r_top,
    ).sort_by(Axis.Y)[-1]
    egg_right = ThreePointArc(
        egg_bottom.vertices().sort_by(Axis.X)[-1],
        con_circle_right @ 0,
        egg_top.vertices().sort_by(Axis.X)[-1],
    )
    egg_left = ThreePointArc(
        egg_bottom.vertices().sort_by(Axis.X)[0],
        con_circle_left @ 0.5,
        egg_top.vertices().sort_by(Axis.X)[0],
    )

    egg_plant = Wire([egg_left, egg_top, egg_right, egg_bottom])
    assert egg_plant.is_closed
    egg_plant_edges = egg_plant.edges().sort_by(egg_plant)
    common_vertex_cnt = sum(
        topo_explore_common_vertex(egg_plant_edges[i], egg_plant_edges[(i + 1) % 4])
        is not None
        for i in range(4)
    )
    assert common_vertex_cnt == 4

    # C1 continuity
    assert all(
        (egg_plant_edges[i] % 1 - egg_plant_edges[(i + 1) % 4] % 0).length < TOLERANCE
        for i in range(4)
    )
