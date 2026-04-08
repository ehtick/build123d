from build123d import *
from build123d import Shape
from build123d.brep_from_stl import detect_primitives
from pathlib import Path
import pytest


# Demo/support
def mesh_and_reload(shape, path: str | Path):
    mesh_path = Path(path)
    mesher = Mesher()
    mesher.add_shape(shape, linear_deflection=0.01, angular_deflection=1)
    mesher.write(mesh_path)
    return Mesher().read(mesh_path)[0]


def geom_equal(reference_shape: Shape, code_str: str):
    """Evaluate generated code and compare geometry, not strings."""
    shape: Shape = eval(code_str)
    assert (
        abs(shape.area - reference_shape.area) < 0.1
    ), f"Area mismatch: {shape.area} vs {reference_shape.area}"

    ref_bbox = reference_shape.bounding_box()
    code_bbox = shape.bounding_box()
    assert (ref_bbox.min - code_bbox.min).length < 1e-2, "Bounding Box min mismatch"
    assert (ref_bbox.max - code_bbox.max).length < 1e-2, "Bounding Box max mismatch"

    return True


def test_cylinder():
    mesh = mesh_and_reload(
        split(
            Cylinder(1, 2, align=None) + Sphere(1),
            Plane.XY.offset(1).rotated((0, 30, 0)),
            Keep.BOTTOM,
        ),
        "/tmp/surface_detection_v3_cylinder.stl",
    )
    primitives, leftovers, code_lines = detect_primitives(mesh)
    assert len(primitives.filter_by(GeomType.PLANE)) >= 1
    assert len(primitives.filter_by(GeomType.CYLINDER)) == 1
    assert len(primitives.filter_by(GeomType.SPHERE)) == 1

    for primitive, code in zip(primitives, code_lines):
        assert geom_equal(primitive, code)


def test_sphere():
    mesh = mesh_and_reload(Sphere(1), "/tmp/surface_detection_v3_sphere.stl")
    primitives, leftovers, code_lines = detect_primitives(mesh)
    assert len(primitives.filter_by(GeomType.PLANE)) == 0
    assert len(primitives.filter_by(GeomType.CYLINDER)) == 0
    assert len(primitives.filter_by(GeomType.SPHERE)) == 1
    assert len(leftovers) == 0

    for primitive, code in zip(primitives, code_lines):
        assert geom_equal(primitive, code)


def test_box():
    mesh = mesh_and_reload(
        fillet(Box(1, 1, 1).edges(), 0.1), "/tmp/surface_detection_v3_box.stl"
    )
    primitives, leftovers, code_lines = detect_primitives(mesh)
    assert len(primitives.filter_by(GeomType.PLANE)) == 6
    assert len(primitives.filter_by(GeomType.CYLINDER)) == 12
    assert len(primitives.filter_by(GeomType.SPHERE)) == 8
    assert len(leftovers) == 0

    for primitive, code in zip(primitives, code_lines):
        assert geom_equal(primitive, code)
