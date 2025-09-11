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
            assert len(result) >= len(expected), f"Expected {len(expected)} objects, but got {len(result)}"

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
    Case(e1, w1, [Vertex, Vertex], "issue #697", "Returns None"),
    Case(e1, f1, [Edge], "issue #697", "Edge.intersect only takes 1D"),
]

@pytest.mark.parametrize("obj, target, expected", make_params(issues_matrix))
def test_issues(obj, target, expected):
    run_test(obj, target, expected)