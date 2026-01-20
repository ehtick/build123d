"""Tests for geom_equal helper function."""

import pytest
from build123d import (
    Vertex,
    Edge,
    Wire,
    Spline,
    Rectangle,
    Circle,
    Ellipse,
    Bezier,
    GeomType,
)
from build123d.topology.helpers import geom_equal


class TestGeomEqualVertex:
    """Tests for Vertex comparison."""

    def test_same_vertex(self):
        v1 = Vertex(1, 2, 3)
        v2 = Vertex(1, 2, 3)
        assert geom_equal(v1, v2)

    def test_different_vertex(self):
        v1 = Vertex(1, 2, 3)
        v2 = Vertex(1, 2, 4)
        assert not geom_equal(v1, v2)

    def test_vertex_within_tolerance(self):
        v1 = Vertex(1, 2, 3)
        v2 = Vertex(1, 2, 3 + 1e-7)
        assert geom_equal(v1, v2)


class TestGeomEqualEdgeLine:
    """Tests for Edge LINE comparison."""

    def test_same_line(self):
        e1 = Edge.make_line((0, 0, 0), (1, 1, 1))
        e2 = Edge.make_line((0, 0, 0), (1, 1, 1))
        assert e1.geom_type == GeomType.LINE
        assert geom_equal(e1, e2)

    def test_different_line(self):
        e1 = Edge.make_line((0, 0, 0), (1, 1, 1))
        e2 = Edge.make_line((0, 0, 0), (1, 1, 2))
        assert not geom_equal(e1, e2)


class TestGeomEqualEdgeCircle:
    """Tests for Edge CIRCLE comparison."""

    def test_same_circle(self):
        c1 = Circle(10)
        c2 = Circle(10)
        e1 = c1.edge()
        e2 = c2.edge()
        assert e1.geom_type == GeomType.CIRCLE
        assert geom_equal(e1, e2)

    def test_different_radius(self):
        c1 = Circle(10)
        c2 = Circle(11)
        e1 = c1.edge()
        e2 = c2.edge()
        assert not geom_equal(e1, e2)

    def test_same_arc(self):
        e1 = Edge.make_circle(10, start_angle=0, end_angle=90)
        e2 = Edge.make_circle(10, start_angle=0, end_angle=90)
        assert geom_equal(e1, e2)

    def test_different_arc_angle(self):
        e1 = Edge.make_circle(10, start_angle=0, end_angle=90)
        e2 = Edge.make_circle(10, start_angle=0, end_angle=180)
        assert not geom_equal(e1, e2)

    def test_different_circle_from_revolve(self):
        """Two circles with same radius/endpoints but different center/axis."""
        from build123d import Axis, Line, RadiusArc, make_face, revolve

        f1 = make_face(RadiusArc((5, 0), (-5, 0), 15) + Line((5, 0), (-5, 0)))
        p1 = revolve(f1, Axis.X, 90)
        value1, value2 = p1.edges().filter_by(GeomType.CIRCLE)
        value2 = value2.reversed()
        # These circles have same endpoints after reversal but different center/axis
        assert not geom_equal(value1, value2)


class TestGeomEqualEdgeEllipse:
    """Tests for Edge ELLIPSE comparison."""

    def test_same_ellipse(self):
        el1 = Ellipse(10, 5)
        el2 = Ellipse(10, 5)
        e1 = el1.edge()
        e2 = el2.edge()
        assert e1.geom_type == GeomType.ELLIPSE
        assert geom_equal(e1, e2)

    def test_different_major_radius(self):
        el1 = Ellipse(10, 5)
        el2 = Ellipse(11, 5)
        e1 = el1.edge()
        e2 = el2.edge()
        assert not geom_equal(e1, e2)

    def test_different_minor_radius(self):
        el1 = Ellipse(10, 5)
        el2 = Ellipse(10, 6)
        e1 = el1.edge()
        e2 = el2.edge()
        assert not geom_equal(e1, e2)


class TestGeomEqualEdgeBezier:
    """Tests for Edge BEZIER comparison."""

    def test_same_bezier(self):
        pts = [(0, 0), (1, 1), (2, 0)]
        b1 = Bezier(*pts)
        b2 = Bezier(*pts)
        e1 = b1.edge()
        e2 = b2.edge()
        assert e1.geom_type == GeomType.BEZIER
        assert geom_equal(e1, e2)

    def test_different_bezier(self):
        b1 = Bezier((0, 0), (1, 1), (2, 0))
        b2 = Bezier((0, 0), (1, 2), (2, 0))
        e1 = b1.edge()
        e2 = b2.edge()
        assert not geom_equal(e1, e2)


class TestGeomEqualEdgeBSpline:
    """Tests for Edge BSPLINE comparison."""

    def test_same_spline(self):
        v = [Vertex(p) for p in ((-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0))]
        s1 = Spline(*v)
        s2 = Spline(*v)
        e1 = s1.edge()
        e2 = s2.edge()
        assert e1.geom_type == GeomType.BSPLINE
        assert geom_equal(e1, e2)

    def test_different_spline(self):
        v1 = [Vertex(p) for p in ((-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0))]
        v2 = [Vertex(p) for p in ((-2, 0), (-1, 1), (0, 0), (1, 0), (2, 0))]
        s1 = Spline(*v1)
        s2 = Spline(*v2)
        e1 = s1.edge()
        e2 = s2.edge()
        assert not geom_equal(e1, e2)

    def test_complex_spline(self):
        v = [
            Vertex(p)
            for p in (
                (-2, 0),
                (-1, 0),
                (0, 0),
                (1, 0),
                (2, 0),
                (3, 0.1),
                (4, 1),
                (5, 2.2),
                (6, 3),
                (7, 2),
                (8, -1),
            )
        ]
        s1 = Spline(*v)
        s2 = Spline(*v)
        e1 = s1.edge()
        e2 = s2.edge()
        assert geom_equal(e1, e2)


class TestGeomEqualEdgeOffset:
    """Tests for Edge OFFSET comparison."""

    def test_same_offset(self):
        v = [Vertex(p) for p in ((0, 0), (1, 1), (2, 0), (3, 1))]
        s = Spline(*v)
        w = Wire([s.edge()])
        offset_wire1 = w.offset_2d(0.1)
        offset_wire2 = w.offset_2d(0.1)

        offset_edges1 = [
            e for e in offset_wire1.edges() if e.geom_type == GeomType.OFFSET
        ]
        offset_edges2 = [
            e for e in offset_wire2.edges() if e.geom_type == GeomType.OFFSET
        ]

        assert len(offset_edges1) > 0
        assert geom_equal(offset_edges1[0], offset_edges2[0])

    def test_different_offset_value(self):
        v = [Vertex(p) for p in ((0, 0), (1, 1), (2, 0), (3, 1))]
        s = Spline(*v)
        w = Wire([s.edge()])
        offset_wire1 = w.offset_2d(0.1)
        offset_wire2 = w.offset_2d(0.2)

        offset_edges1 = [
            e for e in offset_wire1.edges() if e.geom_type == GeomType.OFFSET
        ]
        offset_edges2 = [
            e for e in offset_wire2.edges() if e.geom_type == GeomType.OFFSET
        ]

        assert not geom_equal(offset_edges1[0], offset_edges2[0])


class TestGeomEqualWire:
    """Tests for Wire comparison."""

    def test_same_rectangle_wire(self):
        r1 = Rectangle(10, 5)
        r2 = Rectangle(10, 5)
        assert geom_equal(r1.wire(), r2.wire())

    def test_different_rectangle_wire(self):
        r1 = Rectangle(10, 5)
        r2 = Rectangle(10, 6)
        assert not geom_equal(r1.wire(), r2.wire())

    def test_same_spline_wire(self):
        v = [Vertex(p) for p in ((0, 0), (1, 1), (2, 0), (3, 1))]
        s1 = Spline(*v)
        s2 = Spline(*v)
        w1 = Wire([s1.edge()])
        w2 = Wire([s2.edge()])
        assert geom_equal(w1, w2)

    def test_different_edge_count(self):
        r1 = Rectangle(10, 5)
        e = Edge.make_line((0, 0), (10, 0))
        w1 = r1.wire()
        w2 = Wire([e])
        assert not geom_equal(w1, w2)


class TestGeomEqualTypeMismatch:
    """Tests for type mismatch cases."""

    def test_edge_vs_wire(self):
        e = Edge.make_line((0, 0), (1, 1))
        w = Wire([e])
        assert not geom_equal(e, w)

    def test_different_geom_types(self):
        line = Edge.make_line((0, 0, 0), (1, 1, 1))
        circle = Circle(10).edge()
        assert not geom_equal(line, circle)
