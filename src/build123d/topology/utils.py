"""
build123d topology

name: utils.py
by:   Gumyr
date: September 07, 2025

desc:

This module houses utilities used within the topology modules.

license:

    Copyright 2025 Gumyr

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

from __future__ import annotations

import copy
import itertools
import warnings
from collections.abc import Iterable
from itertools import combinations
from math import ceil, copysign, cos, floor, inf, isclose, pi, radians
from typing import Callable, TypeVar, TYPE_CHECKING, Literal
from typing import cast as tcast
from typing import overload

import numpy as np
import OCP.TopAbs as ta
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_CompCurve, BRepAdaptor_Curve
from OCP.BRepAlgoAPI import (
    BRepAlgoAPI_Common,
    BRepAlgoAPI_Section,
    BRepAlgoAPI_Splitter,
)
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_DisconnectedWire,
    BRepBuilderAPI_EmptyWire,
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeEdge2d,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeWire,
    BRepBuilderAPI_NonManifoldWire,
)
from OCP.BRepExtrema import BRepExtrema_DistShapeShape, BRepExtrema_SupportType
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet2d
from OCP.BRepGProp import BRepGProp, BRepGProp_Face
from OCP.BRepLib import BRepLib, BRepLib_FindSurface
from OCP.BRepLProp import BRepLProp
from OCP.BRepOffset import BRepOffset_MakeOffset
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
from OCP.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
from OCP.BRepProj import BRepProj_Projection
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.GC import GC_MakeArcOfCircle, GC_MakeArcOfEllipse
from OCP.GccEnt import GccEnt_unqualified, GccEnt_Position
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.Geom import (
    Geom_BezierCurve,
    Geom_BSplineCurve,
    Geom_ConicalSurface,
    Geom_CylindricalSurface,
    Geom_Line,
    Geom_Plane,
    Geom_Surface,
    Geom_TrimmedCurve,
)
from OCP.Geom2d import (
    Geom2d_CartesianPoint,
    Geom2d_Circle,
    Geom2d_Curve,
    Geom2d_Line,
    Geom2d_Point,
    Geom2d_TrimmedCurve,
)
from OCP.Geom2dAdaptor import Geom2dAdaptor_Curve
from OCP.Geom2dAPI import Geom2dAPI_InterCurveCurve
from OCP.Geom2dGcc import Geom2dGcc_Circ2d2TanRad, Geom2dGcc_QualifiedCurve
from OCP.GeomAbs import (
    GeomAbs_C0,
    GeomAbs_C1,
    GeomAbs_C2,
    GeomAbs_G1,
    GeomAbs_G2,
    GeomAbs_JoinType,
)
from OCP.GeomAdaptor import GeomAdaptor_Curve
from OCP.GeomAPI import (
    GeomAPI,
    GeomAPI_IntCS,
    GeomAPI_Interpolate,
    GeomAPI_PointsToBSpline,
    GeomAPI_ProjectPointOnCurve,
)
from OCP.GeomConvert import GeomConvert_CompCurveToBSplineCurve
from OCP.GeomFill import (
    GeomFill_CorrectedFrenet,
    GeomFill_Frenet,
    GeomFill_TrihedronLaw,
)
from OCP.GeomProjLib import GeomProjLib
from OCP.gp import (
    gp_Ax1,
    gp_Ax2,
    gp_Ax3,
    gp_Circ,
    gp_Circ2d,
    gp_Dir,
    gp_Dir2d,
    gp_Elips,
    gp_Pln,
    gp_Pnt,
    gp_Pnt2d,
    gp_Trsf,
    gp_Vec,
)
from OCP.GProp import GProp_GProps
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
from OCP.ShapeFix import ShapeFix_Shape, ShapeFix_Wireframe
from OCP.Standard import (
    Standard_ConstructionError,
    Standard_Failure,
    Standard_NoSuchObject,
)
from OCP.TColgp import TColgp_Array1OfPnt, TColgp_Array1OfVec, TColgp_HArray1OfPnt
from OCP.TColStd import (
    TColStd_Array1OfReal,
    TColStd_HArray1OfBoolean,
    TColStd_HArray1OfReal,
)
from OCP.TopAbs import TopAbs_Orientation, TopAbs_ShapeEnum
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import (
    TopoDS,
    TopoDS_Compound,
    TopoDS_Edge,
    TopoDS_Face,
    TopoDS_Shape,
    TopoDS_Shell,
    TopoDS_Vertex,
    TopoDS_Wire,
)
from OCP.TopTools import (
    TopTools_HSequenceOfShape,
    TopTools_IndexedDataMapOfShapeListOfShape,
    TopTools_IndexedMapOfShape,
    TopTools_ListOfShape,
)
from scipy.optimize import minimize_scalar
from scipy.spatial import ConvexHull
from typing_extensions import Self

from build123d.build_enums import (
    AngularDirection,
    CenterOf,
    ContinuityLevel,
    FrameMethod,
    GeomType,
    Keep,
    Kind,
    LengthConstraint,
    PositionConstraint,
    PositionMode,
    Side,
)
from build123d.geometry import (
    DEG2RAD,
    TOL_DIGITS,
    TOLERANCE,
    Axis,
    Color,
    Location,
    Plane,
    Vector,
    VectorLike,
    logger,
)

from .shape_core import (
    Shape,
    ShapeList,
    SkipClean,
    TrimmingTool,
    downcast,
    get_top_level_topods_shapes,
    shapetype,
    topods_dim,
    unwrap_topods_compound,
)
from .utils import (
    _extrude_topods_shape,
    _make_topods_face_from_wires,
    _topods_bool_op,
    isclose_b,
)
from .zero_d import Vertex, topo_explore_common_vertex

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from build123d.topology.one_d import Edge

TWrap = TypeVar("TWrap")  # whatever the factory returns (Edge or a subclass)

# Reuse a single XY plane for 3D->2D projection and for 2D-edge building
_pln_xy = gp_Pln(gp_Ax3(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0)))
_surf_xy = Geom_Plane(_pln_xy)


# ---------------------------
# Normalization utilities
# ---------------------------
def _norm_on_period(u: float, first: float, per: float) -> float:
    """Map parameter u into [first, first+per)."""
    if per <= 0.0:
        return u
    k = floor((u - first) / per)
    return u - k * per


def _forward_delta(u1: float, u2: float, first: float, period: float) -> float:
    """
    Forward (positive) delta from u1 to u2 on a periodic domain anchored at
    'first'.
    """
    u1n = _norm_on_period(u1, first, period)
    u2n = _norm_on_period(u2, first, period)
    delta = u2n - u1n
    if delta < 0.0:
        delta += period
    return delta


# ---------------------------
# Core helpers
# ---------------------------
def _edge_to_qualified_2d(
    edge: TopoDS_Edge, position_constaint: PositionConstraint
) -> tuple[Geom2dGcc_QualifiedCurve, Geom2d_Curve, float, float]:
    """Convert a TopoDS_Edge into 2d curve & extract properties"""

    # 1) Underlying curve + range (also retrieve location to be safe)
    loc = edge.Location()
    hcurve3d = BRep_Tool.Curve_s(edge, float(), float())
    first, last = BRep_Tool.Range_s(edge)

    if hcurve3d is None:
        raise ValueError("Edge has no underlying 3D curve.")

    # 2) Apply location if the edge is positioned by a TopLoc_Location
    if not loc.IsIdentity():
        trsf = loc.Transformation()
        hcurve3d = hcurve3d.Transformed(trsf)

    # 3) Convert to 2D on Plane.XY (Z-up frame at origin)
    hcurve2d = GeomAPI.To2d_s(hcurve3d, _pln_xy)  # -> Handle_Geom2d_Curve

    # 4) Wrap in an adaptor using the same parametric range
    adapt2d = Geom2dAdaptor_Curve(hcurve2d, first, last)

    # 5) Create the qualified curve (unqualified is fine here)
    qcurve = Geom2dGcc_QualifiedCurve(adapt2d, position_constaint.value)
    return qcurve, hcurve2d, first, last


def _edge_from_circle(h2d_circle: Geom2d_Circle, u1: float, u2: float) -> TopoDS_Edge:
    """Build a 3D edge on XY from a trimmed 2D circle segment [u1, u2]."""
    arc2d = Geom2d_TrimmedCurve(h2d_circle, u1, u2, True)  # sense=True
    return BRepBuilderAPI_MakeEdge(arc2d, _surf_xy).Edge()


def _param_in_trim(u: float, first: float, last: float, h2d: Geom2d_Curve) -> bool:
    """Normalize (if periodic) then test [first, last] with tolerance."""
    u = _norm_on_period(u, first, h2d.Period()) if h2d.IsPeriodic() else u
    return (u >= first - TOLERANCE) and (u <= last + TOLERANCE)


def _as_gcc_arg(
    obj: Edge | Vertex | VectorLike, constaint: PositionConstraint
) -> tuple[
    Geom2dGcc_QualifiedCurve | Geom2d_CartesianPoint,
    Geom2d_Curve | None,
    float | None,
    float | None,
    bool,
]:
    """
    Normalize input to a GCC argument.
    Returns: (q_obj, h2d, first, last, is_edge)
    - Edge -> (QualifiedCurve, h2d, first, last, True)
    - Vertex/VectorLike -> (CartesianPoint, None, None, None, False)
    """
    if isinstance(obj.wrapped, TopoDS_Edge):
        return _edge_to_qualified_2d(obj.wrapped, constaint) + (True,)

    loc_xyz = obj.position if isinstance(obj, Vertex) else Vector()
    try:
        base = Vector(obj)
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected Edge | Vertex | VectorLike") from exc

    gp_pnt = gp_Pnt2d(base.X + loc_xyz.X, base.Y + loc_xyz.Y)
    return Geom2d_CartesianPoint(gp_pnt), None, None, None, False


def _two_arc_edges_from_params(
    circ: gp_Circ2d, u1: float, u2: float
) -> ShapeList[Edge]:
    """
    Given two parameters on a circle, return both the forward (minor)
    and complementary (major) arcs as TopoDS_Edge(s).
    Uses centralized normalization utilities.
    """
    h2d_circle = Geom2d_Circle(circ)
    per = h2d_circle.Period()  # usually 2*pi

    # Minor (forward) span
    d = _forward_delta(u1, u2, 0.0, per)  # anchor at 0 for circle convenience
    u1n = _norm_on_period(u1, 0.0, per)
    u2n = _norm_on_period(u2, 0.0, per)

    # Guard degeneracy
    if d <= TOLERANCE or abs(per - d) <= TOLERANCE:
        return ShapeList()

    minor = _edge_from_circle(h2d_circle, u1n, u1n + d)
    major = _edge_from_circle(h2d_circle, u2n, u2n + (per - d))
    return ShapeList([Edge(minor), Edge(major)])


def _qstr(q) -> str:
    # Works with OCP's GccEnt enum values
    try:
        from OCP.GccEnt import (
            GccEnt_enclosed,
            GccEnt_enclosing,
            GccEnt_outside,
        )

        try:
            from OCP.GccEnt import GccEnt_unqualified
        except ImportError:
            # Some OCCT versions name this 'noqualifier'
            from OCP.GccEnt import GccEnt_noqualifier as GccEnt_unqualified
        mapping = {
            GccEnt_enclosed: "enclosed",
            GccEnt_enclosing: "enclosing",
            GccEnt_outside: "outside",
            GccEnt_unqualified: "unqualified",
        }
        return mapping.get(q, f"unknown({int(q)})")
    except Exception:
        # Fallback if enums aren't importable for any reason
        return str(int(q))


def make_tangent_edges(
    cls,
    object_1: tuple[Edge, PositionConstraint] | Vertex | VectorLike,
    object_2: tuple[Edge, PositionConstraint] | Vertex | VectorLike,
    radius: float,
    sagitta_constraint: LengthConstraint = LengthConstraint.SHORT,
    *,
    edge_factory: Callable[[TopoDS_Edge], TWrap],
) -> list[TWrap]:
    """
    Create all planar circular arcs of a given radius that are tangent/contacting
    the two provided objects on the XY plane.

    Inputs must be coplanar with ``Plane.XY``. Non-coplanar edges are not supported.

    Args:
        object_one (Edge | Vertex | VectorLike): Geometric entity to be contacted/touched
            by the circle(s)
        object_two (Edge | Vertex | VectorLike): Geometric entity to be contacted/touched
            by the circle(s)
        radius (float): Circle radius for all candidate solutions.

    Raises:
        ValueError: Invalid input
        ValueError: Invalid curve
        RuntimeError: no valid circle solutions found

    Returns:
        ShapeList[Edge]: A list of planar circular edges (on XY) representing both
            the minor and major arcs between the two tangency points for every valid
            circle solution.

    """

    if isinstance(object_1, tuple):
        object_one, object_one_constraint = object_1
    else:
        object_one = object_1
    if isinstance(object_2, tuple):
        object_two, object_two_constraint = object_2
    else:
        object_two = object_2

    # ---------------------------
    # Build inputs and GCC
    # ---------------------------
    q_o1, h_e1, e1_first, e1_last, is_edge1 = _as_gcc_arg(
        object_one, object_one_constraint
    )
    q_o2, h_e2, e2_first, e2_last, is_edge2 = _as_gcc_arg(
        object_two, object_two_constraint
    )

    # Put the Edge arg first when exactly one is an Edge (improves robustness)
    if is_edge1 ^ is_edge2:
        q_o1, q_o2 = (q_o1, q_o2) if is_edge1 else (q_o2, q_o1)

    gcc = Geom2dGcc_Circ2d2TanRad(q_o1, q_o2, radius, TOLERANCE)
    if not gcc.IsDone() or gcc.NbSolutions() == 0:
        raise RuntimeError("Unable to find a tangent arc")

    def _valid_on_arg1(u: float) -> bool:
        return True if not is_edge1 else _param_in_trim(u, e1_first, e1_last, h_e1)

    def _valid_on_arg2(u: float) -> bool:
        return True if not is_edge2 else _param_in_trim(u, e2_first, e2_last, h_e2)

    # ---------------------------
    # Solutions
    # ---------------------------
    solutions: list[Edge] = []
    for i in range(1, gcc.NbSolutions() + 1):
        circ = gcc.ThisSolution(i)  # gp_Circ2d

        # Tangency on curve 1
        p1 = gp_Pnt2d()
        u_circ1, u_arg1 = gcc.Tangency1(i, p1)
        if not _valid_on_arg1(u_arg1):
            continue

        # Tangency on curve 2
        p2 = gp_Pnt2d()
        u_circ2, u_arg2 = gcc.Tangency2(i, p2)
        if not _valid_on_arg2(u_arg2):
            continue

        qual1 = GccEnt_Position(int())
        qual2 = GccEnt_Position(int())
        gcc.WhichQualifier(i, qual1, qual2)  # returns two GccEnt_Position values
        print(
            f"Solution {i}: "
            f"arg1={_qstr(qual1)}, arg2={_qstr(qual2)} | "
            f"u_circ=({u_circ1:.6g}, {u_circ2:.6g}) "
            f"u_arg=({u_arg1:.6g}, {u_arg2:.6g})"
        )

        # Build BOTH sagitta arcs and select by LengthConstraint
        if sagitta_constraint == LengthConstraint.BOTH:
            solutions.extend(_two_arc_edges_from_params(circ, u_circ1, u_circ2))
        else:
            arcs = _two_arc_edges_from_params(circ, u_circ1, u_circ2)
            arcs = sorted(
                arcs, key=lambda e: GCPnts_AbscissaPoint.Length_s(BRepAdaptor_Curve(e))
            )
            solutions.append(arcs[sagitta_constraint.value])
    return ShapeList([edge_factory(e) for e in solutions])
