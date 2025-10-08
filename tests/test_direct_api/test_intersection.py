import pytest
from collections import Counter
from dataclasses import dataclass
from build123d import *
from build123d.topology.shape_core import Shape

INTERSECT_DEBUG = False
if INTERSECT_DEBUG:
    from ocp_vscode import show


@dataclass
class Case:
    object: Shape | Vector | Location | Axis | Plane
    target: Shape | Vector | Location | Axis | Plane
    expected: list | Vector | Location | Axis | Plane
    name: str
    xfail: None | str = None


@pytest.mark.skip
def run_test(obj, target, expected):
    if isinstance(target, list):
        result = obj.intersect(*target)
    else:
        result = obj.intersect(target)
    if INTERSECT_DEBUG:
        show([obj, target, result])
    if expected is None:
        assert result == expected, f"Expected None, but got {result}"
    else:
        e_type = ShapeList if isinstance(expected, list) else expected
        assert isinstance(result, e_type), f"Expected {e_type}, but got {result}"
        if e_type == ShapeList:
            assert len(result) == len(expected), f"Expected {len(expected)} objects, but got {len(result)}"

            actual_counts = Counter(type(obj) for obj in result)
            expected_counts = Counter(expected)
            assert all(actual_counts[t] >= count for t, count in expected_counts.items()), f"Expected {expected}, but got {[type(r) for r in result]}"


@pytest.mark.skip
def make_params(matrix):
    params = []
    for case in matrix:
        obj_type = type(case.object).__name__
        tar_type = type(case.target).__name__
        i = len(params)
        if case.xfail and not INTERSECT_DEBUG:
            marks = [pytest.mark.xfail(reason=case.xfail)]
        else:
            marks = []
        uid = f"{i} {obj_type}, {tar_type}, {case.name}"
        params.append(pytest.param(case.object, case.target, case.expected, marks=marks, id=uid))
        if tar_type != obj_type and not isinstance(case.target, list):
            uid = f"{i + 1} {tar_type}, {obj_type}, {case.name}"
            params.append(pytest.param(case.target, case.object, case.expected, marks=marks, id=uid))

    return params


# Geometric test objects
ax1 = Axis.X
ax2 = Axis.Y
ax3 = Axis((0, 0, 5), (1, 0, 0))
pl1 = Plane.YZ
pl2 = Plane.XY
pl3 = Plane.XY.offset(5)
pl4 = Plane((0, 5, 0))
pl5 = Plane.YZ.offset(1)
vl1 = Vector(2, 0, 0)
vl2 = Vector(2, 0, 5)
lc1 = Location((2, 0, 0))
lc2 = Location((2, 0, 5))
lc3 = Location((0, 0, 0), (0, 90, 90))
lc4 = Location((2, 0, 0), (0, 90, 90))

# Geometric test matrix
geometry_matrix = [
    Case(ax1, ax3, None, "parallel/skew", None),
    Case(ax1, ax1, Axis, "collinear", None),
    Case(ax1, ax2, Vector, "intersecting", None),

    Case(ax1, pl3, None, "parallel", None),
    Case(ax1, pl2, Axis, "coplanar", None),
    Case(ax1, pl1, Vector, "intersecting", None),

    Case(ax1, vl2, None, "non-coincident", None),
    Case(ax1, vl1, Vector, "coincident", None),

    Case(ax1, lc2, None, "non-coincident", None),
    Case(ax1, lc4, Location, "intersecting, co-z", None),
    Case(ax1, lc1, Vector, "intersecting", None),

    Case(pl2, pl3, None, "parallel", None),
    Case(pl2, pl4, Plane, "coplanar", None),
    Case(pl1, pl2, Axis, "intersecting", None),

    Case(pl3, ax1, None, "parallel", None),
    Case(pl2, ax1, Axis, "coplanar", None),
    Case(pl1, ax1, Vector, "intersecting", None),

    Case(pl1, vl2, None, "non-coincident", None),
    Case(pl2, vl1, Vector, "coincident", None),

    Case(pl1, lc2, None, "non-coincident", None),
    Case(pl1, lc3, Location, "intersecting, co-z", None),
    Case(pl2, lc4, Vector, "coincident", None),

    Case(vl1, vl2, None, "non-coincident", None),
    Case(vl1, vl1, Vector, "coincident", None),

    Case(vl1, lc2, None, "non-coincident", None),
    Case(vl1, lc1, Vector, "coincident", None),

    Case(lc1, lc2, None, "non-coincident", None),
    Case(lc1, lc4, Vector, "coincident", None),
    Case(lc1, lc1, Location, "coincident, co-z", None),
]

@pytest.mark.parametrize("obj, target, expected", make_params(geometry_matrix))
def test_geometry(obj, target, expected):
    run_test(obj, target, expected)


# Shape test matrices
vt1 = Vertex(2, 0, 0)
vt2 = Vertex(2, 0, 5)

shape_0d_matrix = [
    Case(vt1, vt2, None, "non-coincident", None),
    Case(vt1, vt1, [Vertex], "coincident", None),

    Case(vt1, vl2, None, "non-coincident", None),
    Case(vt1, vl1, [Vertex], "coincident", None),

    Case(vt1, lc2, None, "non-coincident", None),
    Case(vt1, lc1, [Vertex], "coincident", None),

    Case(vt2, ax1, None, "non-coincident", None),
    Case(vt1, ax1, [Vertex], "coincident", None),

    Case(vt2, pl1, None, "non-coincident", None),
    Case(vt1, pl2, [Vertex], "coincident", None),

    Case(vt1, [vt2, lc1], None, "multi to_intersect, non-coincident", None),
    Case(vt1, [vt1, lc1], [Vertex], "multi to_intersect, coincident", None),
]

@pytest.mark.parametrize("obj, target, expected", make_params(shape_0d_matrix))
def test_shape_0d(obj, target, expected):
    run_test(obj, target, expected)


ed1 = Line((0, 0), (5, 0)).edge()
ed2 = Line((0, -1), (5, 1)).edge()
ed3 = Line((0, 0, 5), (5, 0, 5)).edge()
ed4 = CenterArc((3, 1), 2, 0, 360).edge()
ed5 = CenterArc((3, 1), 5, 0, 360).edge()

ed6 = Edge.make_line((0, -1), (2, 1))
ed7 = Edge.make_line((0, 1), (2, -1))
ed8 = Edge.make_line((0, 0), (2, 0))

wi1 = Wire() + [Line((0, 0), (1, 0)), RadiusArc((1, 0), (3, 1.5), 2)]
wi2 = wi1 + Line((3, 1.5), (3, -1))
wi3 = Wire() + [Line((0, 0), (1, 0)), RadiusArc((1, 0), (3, 0), 2), Line((3, 0), (5, 0))]
wi4 = Wire() + [Line((0, 1), (2, -1)) , Line((2, -1), (3, -1))]
wi5 = wi4 + Line((3, -1), (4, 1))
wi6 = Wire() + [Line((0, 1, 1), (2, -1, 1)), Line((2, -1, 1), (4, 1, 1))]

shape_1d_matrix = [
    Case(ed1, vl2, None, "non-coincident", None),
    Case(ed1, vl1, [Vertex], "coincident", None),

    Case(ed1, lc2, None, "non-coincident", None),
    Case(ed1, lc1, [Vertex], "coincident", None),

    Case(ed3, ax1, None, "parallel/skew", None),
    Case(ed2, ax1, [Vertex], "intersecting", None),
    Case(ed1, ax1, [Edge], "collinear", None),
    Case(ed4, ax1, [Vertex, Vertex], "multi intersect", None),

    Case(ed1, pl3, None, "parallel/skew", None),
    Case(ed1, pl1, [Vertex], "intersecting", None),
    Case(ed1, pl2, [Edge], "collinear", None),
    Case(ed5, pl1, [Vertex, Vertex], "multi intersect", None),

    Case(ed1, vt2, None, "non-coincident", None),
    Case(ed1, vt1, [Vertex], "coincident", None),

    Case(ed3, ed1, None, "parallel/skew", None),
    Case(ed2, ed1, [Vertex], "intersecting", None),
    Case(ed1, ed1, [Edge], "collinear", None),
    Case(ed4, ed1, [Vertex, Vertex], "multi intersect", None),

    Case(ed6, [ed7, ed8], [Vertex], "multi to_intersect, intersect", None),
    Case(ed6, [ed7, pl5], [Vertex], "multi to_intersect, intersect", None),
    Case(ed6, [ed7, Vector(1, 0)], [Vertex], "multi to_intersect, intersect", None),

    Case(wi6, ax1, None, "parallel/skew", None),
    Case(wi4, ax1, [Vertex], "intersecting", None),
    Case(wi1, ax1, [Edge], "collinear", None),
    Case(wi5, ax1, [Vertex, Vertex], "multi intersect", None),
    Case(wi2, ax1, [Vertex, Edge], "intersect + collinear", None),
    Case(wi3, ax1, [Edge, Edge], "2 collinear", None),

    Case(wi6, ed1, None, "parallel/skew", None),
    Case(wi4, ed1, [Vertex], "intersecting", None),
    Case(wi1, ed1, [Edge], "collinear", None),
    Case(wi5, ed1, [Vertex, Vertex], "multi intersect", None),
    Case(wi2, ed1, [Vertex, Edge], "intersect + collinear", None),
    Case(wi3, ed1, [Edge, Edge], "2 collinear", None),

    Case(wi5, [ed1, Vector(1, 0)], [Vertex], "multi to_intersect, multi intersect", None),
]

@pytest.mark.parametrize("obj, target, expected", make_params(shape_1d_matrix))
def test_shape_1d(obj, target, expected):
    run_test(obj, target, expected)


# FreeCAD issue example
c1 = CenterArc((0, 0), 10, 0, 360).edge()
c2 = CenterArc((19, 0), 10, 0, 360).edge()
skew = Line((-12, 0), (30, 10)).edge()
vert = Line((10, 0), (10, 20)).edge()
horz = Line((0, 10), (30, 10)).edge()
e1 = EllipticalCenterArc((5, 0), 5, 10, 0, 360).edge()

freecad_matrix = [
    Case(c1, skew, [Vertex, Vertex], "circle, skew, intersect", None),
    Case(c2, skew, [Vertex, Vertex], "circle, skew, intersect", None),
    Case(c1, e1, [Vertex, Vertex, Vertex], "circle, ellipse, intersect + tangent", None),
    Case(c2, e1, [Vertex, Vertex], "circle, ellipse, intersect", None),
    Case(skew, e1, [Vertex, Vertex], "skew, ellipse, intersect", None),
    Case(skew, horz, [Vertex], "skew, horizontal, coincident", None),
    Case(skew, vert, [Vertex], "skew, vertical, intersect", None),
    Case(horz, vert, [Vertex], "horizontal, vertical, intersect", None),
    Case(vert, e1, [Vertex], "vertical, ellipse, tangent", None),
    Case(horz, e1, [Vertex], "horizontal, ellipse, tangent", None),

    Case(c1, c2, [Vertex, Vertex], "circle, skew, intersect", "Should return 2 Vertices"),
    Case(c1, horz, [Vertex], "circle, horiz, tangent", None),
    Case(c2, horz, [Vertex], "circle, horiz, tangent", None),
    Case(c1, vert, [Vertex], "circle, vert, tangent", None),
    Case(c2, vert, [Vertex], "circle, vert, intersect", None),
]

@pytest.mark.parametrize("obj, target, expected", make_params(freecad_matrix))
def test_freecad(obj, target, expected):
    run_test(obj, target, expected)


# Issue tests
t = Sketch() + GridLocations(5, 0, 2, 1) * Circle(2)
s = Circle(10).face()
l = Line(-20, 20).edge()
a = Rectangle(10,10).face()
b = (Plane.XZ * a).face()
e1 = Edge.make_line((-1, 0), (1, 0))
w1 = Wire.make_circle(0.5)
f1 = Face(Wire.make_circle(0.5))

issues_matrix = [
    Case(t, t, [Face, Face], "issue #1015", "Returns Compound"),
    Case(l, s, [Edge], "issue #945", "Edge.intersect only takes 1D"),
    Case(a, b, [Edge], "issue #918", "Returns empty Compound"),
    Case(e1, w1, [Vertex, Vertex], "issue #697"),
    Case(e1, f1, [Edge], "issue #697", "Edge.intersect only takes 1D"),
]

@pytest.mark.parametrize("obj, target, expected", make_params(issues_matrix))
def test_issues(obj, target, expected):
    run_test(obj, target, expected)


# Exceptions
exception_matrix = [
    Case(vt1, Color(), None, "Unsupported type", None),
    Case(ed1, Color(), None, "Unsupported type", None),
]

@pytest.mark.skip
def make_exception_params(matrix):
    params = []
    for case in matrix:
        obj_type = type(case.object).__name__
        tar_type = type(case.target).__name__
        i = len(params)
        uid = f"{i} {obj_type}, {tar_type}, {case.name}"
        params.append(pytest.param(case.object, case.target, case.expected, id=uid))

    return params

@pytest.mark.parametrize("obj, target, expected", make_exception_params(exception_matrix))
def test_exceptions(obj, target, expected):
    with pytest.raises(Exception):
        obj.intersect(target)