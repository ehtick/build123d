"""Helper functions for topology operations."""

from __future__ import annotations

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge

from build123d.build_enums import GeomType
from build123d.geometry import Axis, Location, Plane, Vector
from build123d.topology.shape_core import Shape
from build123d.topology.zero_d import Vertex
from build123d.topology.one_d import Edge, Wire
from build123d.topology.two_d import Face


def convert_to_shapes(
    shape: Shape,
    objects: tuple[Shape | Vector | Location | Axis | Plane, ...],
) -> list[Shape]:
    """Convert geometry objects to shapes.

    Args:
        shape: The shape context (used for bounding box when converting Axis)
        objects: Tuple of geometry objects to convert

    Returns:
        List of Shape objects
    """
    results = []
    for obj in objects:
        if isinstance(obj, Vector):
            results.append(Vertex(obj.X, obj.Y, obj.Z))
        elif isinstance(obj, Location):
            pos = obj.position
            results.append(Vertex(pos.X, pos.Y, pos.Z))
        elif isinstance(obj, Axis):
            # Convert to finite edge based on bounding box
            bbox = shape.bounding_box(optimal=False)
            dist = shape.distance_to(obj.position)
            # Be sure to avoid zero length edge for vertex on axis intersection
            half_length = max(bbox.diagonal, 1) * max(dist, 1)
            results.append(
                Edge.make_line(
                    obj.position - obj.direction * half_length,
                    obj.position + obj.direction * half_length,
                )
            )
        elif isinstance(obj, Plane):
            results.append(Face(obj))
        elif isinstance(obj, Shape):
            results.append(obj)
        else:
            raise ValueError(f"Unsupported type for intersect: {type(obj)}")
    return results


def geom_equal(
    value1: Vector | Location | Vertex | Edge | Wire,
    value2: Vector | Location | Vertex | Edge | Wire,
    tol: float = 1e-6,
    num_interpolation_points: int = 5,
) -> bool:
    """Compare two geometric objects for equality within tolerance."""
    # Type must match
    if type(value1) != type(value2):
        return False

    # NOTE: == for Vector and Location values is tolerance based equality!

    if isinstance(value1, Vector):
        return value1 == value2

    elif isinstance(value1, Vertex):
        return Vector(value1) == Vector(value2)

    elif isinstance(value1, Location):
        return value1 == value2

    elif isinstance(value1, Wire) and isinstance(value2, Wire):
        edges1 = value1.edges()
        edges2 = value2.edges()
        if len(edges1) != len(edges2):
            return False
        return all(geom_equal(e1, e2, tol) for e1, e2 in zip(edges1, edges2))

    elif isinstance(value1, Edge) and isinstance(value2, Edge):
        # geom_type and location must match
        if value1.geom_type != value2.geom_type:
            return False

        if value1.location != value2.location:
            return False

        # Common: start and end points
        if (value1 @ 0) != (value2 @ 0) or (value1 @ 1) != (value2 @ 1):
            return False

        ga1 = value1.geom_adaptor()
        ga2 = value2.geom_adaptor()

        match value1.geom_type:
            case GeomType.LINE:
                # Line: fully defined by endpoints (already checked)
                return True

            case GeomType.CIRCLE:
                return abs(ga1.Circle().Radius() - ga2.Circle().Radius()) < tol

            case GeomType.ELLIPSE:
                e1, e2 = ga1.Ellipse(), ga2.Ellipse()
                return (
                    abs(e1.MajorRadius() - e2.MajorRadius()) < tol
                    and abs(e1.MinorRadius() - e2.MinorRadius()) < tol
                )

            case GeomType.HYPERBOLA:
                h1, h2 = ga1.Hyperbola(), ga2.Hyperbola()
                return (
                    abs(h1.MajorRadius() - h2.MajorRadius()) < tol
                    and abs(h1.MinorRadius() - h2.MinorRadius()) < tol
                )

            case GeomType.PARABOLA:
                return abs(ga1.Parabola().Focal() - ga2.Parabola().Focal()) < tol

            case GeomType.BEZIER:
                b1, b2 = ga1.Bezier(), ga2.Bezier()
                if b1.Degree() != b2.Degree() or b1.NbPoles() != b2.NbPoles():
                    return False
                for i in range(1, b1.NbPoles() + 1):
                    if Vector(b1.Pole(i)) != Vector(b2.Pole(i)):
                        return False
                    if b1.IsRational() and abs(b1.Weight(i) - b2.Weight(i)) >= tol:
                        return False
                return True

            case GeomType.BSPLINE:
                s1, s2 = ga1.BSpline(), ga2.BSpline()
                if s1.Degree() != s2.Degree():
                    return False
                if s1.IsPeriodic() != s2.IsPeriodic():
                    return False
                if s1.NbPoles() != s2.NbPoles() or s1.NbKnots() != s2.NbKnots():
                    return False
                for i in range(1, s1.NbPoles() + 1):
                    if Vector(s1.Pole(i)) != Vector(s2.Pole(i)):
                        return False
                    if s1.IsRational() and abs(s1.Weight(i) - s2.Weight(i)) >= tol:
                        return False
                for i in range(1, s1.NbKnots() + 1):
                    if abs(s1.Knot(i) - s2.Knot(i)) >= tol:
                        return False
                    if s1.Multiplicity(i) != s2.Multiplicity(i):
                        return False
                return True

            case GeomType.OFFSET:
                oc1, oc2 = ga1.OffsetCurve(), ga2.OffsetCurve()
                # Compare offset values and directions
                if abs(oc1.Offset() - oc2.Offset()) >= tol:
                    return False
                if Vector(oc1.Direction()) != Vector(oc2.Direction()):
                    return False
                # Compare basis curves (recursive)
                basis1 = Edge(BRepBuilderAPI_MakeEdge(oc1.BasisCurve()).Edge())
                basis2 = Edge(BRepBuilderAPI_MakeEdge(oc2.BasisCurve()).Edge())
                return geom_equal(basis1, basis2, tol)

            case _:
                # OTHER/unknown: compare sample points
                for i in range(1, num_interpolation_points + 1):
                    t = i / (num_interpolation_points + 1)
                    if (value1 @ t) != (value2 @ t):
                        return False
                return True

    return False
