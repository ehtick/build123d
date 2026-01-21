"""Helper functions for topology operations."""

from __future__ import annotations

from build123d.geometry import Axis, Location, Plane, Vector
from build123d.topology.shape_core import Shape
from build123d.topology.zero_d import Vertex
from build123d.topology.one_d import Edge
from build123d.topology.two_d import Face


def convert_to_shapes(
    objects: tuple[Shape | Vector | Location | Axis | Plane, ...],
) -> list[Shape]:
    """Convert geometry objects to shapes.

    Args:
        objects: Tuple of geometry objects to convert

    Returns:
        List of Shape objects
    """
    results = []
    for obj in objects:
        if isinstance(obj, Vector):
            results.append(Vertex(obj))
        elif isinstance(obj, Location):
            results.append(Vertex(obj.position))
        elif isinstance(obj, Axis):
            results.append(Edge(obj))
        elif isinstance(obj, Plane):
            results.append(Face(obj))
        elif isinstance(obj, Shape):
            results.append(obj)
        else:
            raise ValueError(f"Unsupported type for intersect: {type(obj)}")
    return results
