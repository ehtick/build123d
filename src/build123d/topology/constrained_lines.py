"""
build123d topology

name: constrained_lines.py
by:   Gumyr
date: September 07, 2025

desc:

This module generates lines and arcs that are constrained against other objects.

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

from math import floor
from typing import TYPE_CHECKING, Callable, TypeVar
from typing import cast as tcast

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.Geom import Geom_Plane
from OCP.Geom2d import (
    Geom2d_CartesianPoint,
    Geom2d_Circle,
    Geom2d_Curve,
    Geom2d_TrimmedCurve,
)
from OCP.Geom2dAdaptor import Geom2dAdaptor_Curve
from OCP.Geom2dAPI import Geom2dAPI_ProjectPointOnCurve
from OCP.Geom2dGcc import (
    Geom2dGcc_Circ2d2TanOn,
    Geom2dGcc_Circ2d2TanOnGeo,
    Geom2dGcc_Circ2d2TanRad,
    Geom2dGcc_Circ2d3Tan,
    Geom2dGcc_Circ2dTanCen,
    Geom2dGcc_Circ2dTanOnRad,
    Geom2dGcc_Circ2dTanOnRadGeo,
    Geom2dGcc_QualifiedCurve,
)
from OCP.GeomAbs import GeomAbs_CurveType
from OCP.GeomAPI import GeomAPI, GeomAPI_ProjectPointOnCurve
from OCP.gp import (
    gp_Ax2d,
    gp_Ax3,
    gp_Circ2d,
    gp_Dir,
    gp_Dir2d,
    gp_Pln,
    gp_Pnt,
    gp_Pnt2d,
)
from OCP.TopoDS import TopoDS_Edge

from build123d.build_enums import LengthConstraint, PositionConstraint
from build123d.geometry import TOLERANCE, Vector, VectorLike
from .zero_d import Vertex
from .shape_core import ShapeList

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
    return qcurve, hcurve2d, first, last, adapt2d


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
        return _edge_to_qualified_2d(obj.wrapped, constaint)[0:4] + (True,)

    loc_xyz = obj.position if isinstance(obj, Vertex) else Vector()
    try:
        base = Vector(obj)
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected Edge | Vertex | VectorLike") from exc

    gp_pnt = gp_Pnt2d(base.X + loc_xyz.X, base.Y + loc_xyz.Y)
    return Geom2d_CartesianPoint(gp_pnt), None, None, None, False


def _two_arc_edges_from_params(
    circ: gp_Circ2d, u1: float, u2: float
) -> list[TopoDS_Edge]:
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
    return [minor, major]


def _qstr(q) -> str:
    # Works with OCP's GccEnt enum values
    try:
        from OCP.GccEnt import GccEnt_enclosed, GccEnt_enclosing, GccEnt_outside

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


def _make_2tan_rad_arcs(
    *tangencies: tuple[Edge, PositionConstraint] | Edge | Vertex | VectorLike,  # 2
    radius: float,
    sagitta_constraint: LengthConstraint = LengthConstraint.SHORT,
    edge_factory: Callable[[TopoDS_Edge], TWrap],
) -> list[Edge]:
    """
    Create all planar circular arcs of a given radius that are tangent/contacting
    the two provided objects on the XY plane.

    Inputs must be coplanar with ``Plane.XY``. Non-coplanar edges are not supported.

    Args:
        tangencies (tuple[Edge, PositionConstraint] | Edge | Vertex | VectorLike:
            Geometric entity to be contacted/touched by the circle(s)
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

    # Unpack optional per-edge qualifiers (default UNQUALIFIED)
    tangent_tuples = [
        t if isinstance(t, tuple) else (t, PositionConstraint.UNQUALIFIED)
        for t in tangencies
    ]

    # Build inputs for GCC
    q_o, h_e, e_first, e_last, is_edge = [[None] * 2 for _ in range(5)]
    for i in range(len(tangent_tuples)):
        q_o[i], h_e[i], e_first[i], e_last[i], is_edge[i] = _as_gcc_arg(
            *tangent_tuples[i]
        )

    gcc = Geom2dGcc_Circ2d2TanRad(*q_o, radius, TOLERANCE)
    if not gcc.IsDone() or gcc.NbSolutions() == 0:
        raise RuntimeError("Unable to find a tangent arc")

    def _ok(i: int, u: float) -> bool:
        """Does the given parameter value lie within the edge range?"""
        return (
            True if not is_edge[i] else _param_in_trim(u, e_first[i], e_last[i], h_e[i])
        )

    # ---------------------------
    # Solutions
    # ---------------------------
    solutions: list[Edge] = []
    for i in range(1, gcc.NbSolutions() + 1):
        circ = gcc.ThisSolution(i)  # gp_Circ2d

        # Tangency on curve 1
        p1 = gp_Pnt2d()
        u_circ1, u_arg1 = gcc.Tangency1(i, p1)
        if not _ok(0, u_arg1):
            continue

        # Tangency on curve 2
        p2 = gp_Pnt2d()
        u_circ2, u_arg2 = gcc.Tangency2(i, p2)
        if not _ok(1, u_arg2):
            continue

        # qual1 = GccEnt_Position(int())
        # qual2 = GccEnt_Position(int())
        # gcc.WhichQualifier(i, qual1, qual2)  # returns two GccEnt_Position values
        # print(
        #     f"Solution {i}: "
        #     f"arg1={_qstr(qual1)}, arg2={_qstr(qual2)} | "
        #     f"u_circ=({u_circ1:.6g}, {u_circ2:.6g}) "
        #     f"u_arg=({u_arg1:.6g}, {u_arg2:.6g})"
        # )

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


def _make_2tan_on_arcs(
    *tangencies: tuple[Edge, PositionConstraint] | Edge | Vertex | VectorLike,  # 2
    center_on: Edge,
    sagitta_constraint: LengthConstraint = LengthConstraint.SHORT,
    edge_factory: Callable[[TopoDS_Edge], TWrap],
) -> ShapeList[Edge]:
    """
    Create all planar circular arcs whose circle is tangent to two objects and whose
    CENTER lies on a given locus (line/circle/curve) on the XY plane.

    Notes
    -----
    - `center_on` is treated as a **center locus** (not a tangency target).
    """

    # Unpack optional per-edge qualifiers (default UNQUALIFIED)
    tangent_tuples = [
        t if isinstance(t, tuple) else (t, PositionConstraint.UNQUALIFIED)
        for t in tangencies
    ]

    # Build inputs for GCC
    q_o, h_e, e_first, e_last, is_edge = [[None] * 3 for _ in range(5)]
    for i in range(len(tangent_tuples)):
        q_o[i], h_e[i], e_first[i], e_last[i], is_edge[i] = _as_gcc_arg(
            *tangent_tuples[i]
        )

    # Build center locus ("On") input
    _, h_on2d, e_first[2], e_last[2], adapt_on = _edge_to_qualified_2d(
        center_on.wrapped, PositionConstraint.UNQUALIFIED
    )
    is_edge[2] = True

    # Provide initial middle guess parameters for all of the edges
    guesses = [(e_last[i] - e_first[i]) / 2 + e_first[i] for i in range(len(is_edge))]

    if sum(is_edge) > 1:
        gcc = Geom2dGcc_Circ2d2TanOn(*q_o[0:2], adapt_on, TOLERANCE, *guesses)
    else:
        gcc = Geom2dGcc_Circ2d2TanOn(*q_o[0:2], adapt_on, TOLERANCE)

    if not gcc.IsDone() or gcc.NbSolutions() == 0:
        raise RuntimeError("Unable to find a tangent arc with center_on constraint")

    def _ok(i: int, u: float) -> bool:
        """Does the given parameter value lie within the edge range?"""
        return (
            True if not is_edge[i] else _param_in_trim(u, e_first[i], e_last[i], h_e[i])
        )

    # ---------------------------
    # Solutions
    # ---------------------------
    solutions: list[TopoDS_Edge] = []
    for i in range(1, gcc.NbSolutions() + 1):
        circ = gcc.ThisSolution(i)  # gp_Circ2d

        # Tangency on curve 1
        p1 = gp_Pnt2d()
        u_circ1, u_arg1 = gcc.Tangency1(i, p1)
        if not _ok(0, u_arg1):
            continue

        # Tangency on curve 2
        p2 = gp_Pnt2d()
        u_circ2, u_arg2 = gcc.Tangency2(i, p2)
        if not _ok(1, u_arg2):
            continue

        # Center must lie on the trimmed center_on curve segment
        center2d = circ.Location()  # gp_Pnt2d

        # Project center onto the (trimmed) 2D locus
        proj = Geom2dAPI_ProjectPointOnCurve(center2d, h_on2d)
        if proj.NbPoints() == 0:
            continue  # no projection -> reject

        u_on = proj.Parameter(1)
        # Optional: make sure it's actually on the curve (not just near)
        if proj.Distance(1) > TOLERANCE:
            continue

        # Respect the trimmed interval (handles periodic curves too)
        if not _param_in_trim(u_on, e_first[2], e_last[2], h_on2d):
            continue

        # Build sagitta arc(s) and select by LengthConstraint
        if sagitta_constraint == LengthConstraint.BOTH:
            solutions.extend(_two_arc_edges_from_params(circ, u_circ1, u_circ2))
        else:
            arcs = _two_arc_edges_from_params(circ, u_circ1, u_circ2)
            if not arcs:
                continue
            arcs = sorted(
                arcs, key=lambda e: GCPnts_AbscissaPoint.Length_s(BRepAdaptor_Curve(e))
            )
            solutions.append(arcs[sagitta_constraint.value])

    return ShapeList([edge_factory(e) for e in solutions])


def _make_3tan_arcs(
    *tangencies: tuple[Edge, PositionConstraint] | Edge | Vertex | VectorLike,  # 3
    sagitta_constraint: LengthConstraint = LengthConstraint.SHORT,
    edge_factory: Callable[[TopoDS_Edge], TWrap],
) -> ShapeList[Edge]:
    """
    Create planar circular arc(s) on XY tangent to three provided objects.

    The circle is determined by the three tangency constraints; the returned arc(s)
    are trimmed between the two tangency points corresponding to `tangencies[0]` and
    `tangencies[1]`. Use `sagitta_constraint` to select the shorter/longer (or both) arc.
    Inputs must be representable on Plane.XY.
    """

    # Unpack optional per-edge qualifiers (default UNQUALIFIED)
    tangent_tuples = [
        t if isinstance(t, tuple) else (t, PositionConstraint.UNQUALIFIED)
        for t in tangencies
    ]

    # Build inputs for GCC
    q_o, h_e, e_first, e_last, is_edge = [[None] * 3 for _ in range(5)]
    for i in range(len(tangent_tuples)):
        q_o[i], h_e[i], e_first[i], e_last[i], is_edge[i] = _as_gcc_arg(
            *tangent_tuples[i]
        )

    # Provide initial middle guess parameters for all of the edges
    guesses = [(e_last[i] - e_first[i]) / 2 + e_first[i] for i in range(len(is_edge))]

    # Generate all valid circles tangent to the 3 inputs
    gcc = Geom2dGcc_Circ2d3Tan(*q_o, TOLERANCE, *guesses)

    if not gcc.IsDone() or gcc.NbSolutions() == 0:
        raise RuntimeError("Unable to find a circle tangent to all three objects")

    def _ok(i: int, u: float) -> bool:
        """Does the given parameter value lie within the edge range?"""
        return (
            True if not is_edge[i] else _param_in_trim(u, e_first[i], e_last[i], h_e[i])
        )

    # ---------------------------
    # Enumerate solutions
    # ---------------------------
    out_topos: list[TopoDS_Edge] = []
    for i in range(1, gcc.NbSolutions() + 1):
        circ = gcc.ThisSolution(i)  # gp_Circ2d

        # Tangency on curve 1 (arc endpoint A)
        p1 = gp_Pnt2d()
        u_circ1, u_arg1 = gcc.Tangency1(i, p1)
        if not _ok(0, u_arg1):
            continue

        # Tangency on curve 2 (arc endpoint B)
        p2 = gp_Pnt2d()
        u_circ2, u_arg2 = gcc.Tangency2(i, p2)
        if not _ok(1, u_arg2):
            continue

        # Tangency on curve 3 (validates circle; does not define arc endpoints)
        p3 = gp_Pnt2d()
        _u_circ3, u_arg3 = gcc.Tangency3(i, p3)
        if not _ok(2, u_arg3):
            continue

        # Build arc(s) between u_circ1 and u_circ2 per LengthConstraint
        if sagitta_constraint == LengthConstraint.BOTH:
            out_topos.extend(_two_arc_edges_from_params(circ, u_circ1, u_circ2))
        else:
            arcs = _two_arc_edges_from_params(circ, u_circ1, u_circ2)
            if not arcs:
                continue
            arcs = sorted(
                arcs,
                key=lambda e: GCPnts_AbscissaPoint.Length_s(BRepAdaptor_Curve(e)),
            )
            out_topos.append(arcs[sagitta_constraint.value])

    return ShapeList([edge_factory(e) for e in out_topos])


def _make_tan_cen_arcs(
    tangency: tuple[Edge, PositionConstraint] | Edge | Vertex | VectorLike,
    *,
    center: VectorLike | Vertex,
    edge_factory: Callable[[TopoDS_Edge], TWrap],
) -> ShapeList[Edge]:
    """
    Create planar circle(s) on XY whose center is fixed and that are tangent/contacting
    a single object.

    Notes
    -----
    - With a **fixed center** and a single tangency constraint, the natural geometric
      result is a full circle; there are no second endpoints to define an arc span.
      This routine therefore returns closed circular edges (full 2π trims).
    - If the tangency target is a point (Vertex/VectorLike), the circle is the one
      centered at `center` and passing through that point (built directly).
    """

    # Unpack optional qualifier on the tangency arg (edges only)
    if isinstance(tangency, tuple):
        object_one, obj1_qual = tangency
    else:
        object_one, obj1_qual = tangency, PositionConstraint.UNQUALIFIED

    # ---------------------------
    # Build fixed center (gp_Pnt2d)
    # ---------------------------
    if isinstance(center, Vertex):
        loc_xyz = center.position
        base = Vector(center)
        c2d = gp_Pnt2d(base.X + loc_xyz.X, base.Y + loc_xyz.Y)
    else:
        v = Vector(center)
        c2d = gp_Pnt2d(v.X, v.Y)

    # ---------------------------
    # Tangency input
    # ---------------------------
    q_o1, h_e1, e1_first, e1_last, is_edge1 = _as_gcc_arg(object_one, obj1_qual)

    solutions_topo: list[TopoDS_Edge] = []

    # Case A: tangency target is a point -> circle passes through that point
    if not is_edge1 and isinstance(q_o1, Geom2d_CartesianPoint):
        p = q_o1.Pnt2d()
        # radius = distance(center, point)
        dx, dy = p.X() - c2d.X(), p.Y() - c2d.Y()
        r = (dx * dx + dy * dy) ** 0.5
        if r <= TOLERANCE:
            # Center coincides with point: no valid circle
            return ShapeList([])
        # Build full circle
        circ = gp_Circ2d(gp_Ax2d(c2d, gp_Dir2d(1.0, 0.0)), r)
        h2d = Geom2d_Circle(circ)
        per = h2d.Period()
        solutions_topo.append(_edge_from_circle(h2d, 0.0, per))

    else:
        # Case B: tangency target is a curve/edge (qualified curve)
        gcc = Geom2dGcc_Circ2dTanCen(q_o1, Geom2d_CartesianPoint(c2d), TOLERANCE)
        if not gcc.IsDone() or gcc.NbSolutions() == 0:
            raise RuntimeError(
                "Unable to find circle(s) tangent to target with fixed center"
            )

        for i in range(1, gcc.NbSolutions() + 1):
            circ = gcc.ThisSolution(i)  # gp_Circ2d

            # Validate tangency lies on trimmed span if the target is an Edge
            p1 = gp_Pnt2d()
            _u_on_circ, u_on_arg = gcc.Tangency1(i, p1)
            if is_edge1 and not _param_in_trim(u_on_arg, e1_first, e1_last, h_e1):
                continue

            # Emit full circle (2π trim)
            h2d = Geom2d_Circle(circ)
            per = h2d.Period()
            solutions_topo.append(_edge_from_circle(h2d, 0.0, per))

    return ShapeList([edge_factory(e) for e in solutions_topo])


def _make_tan_on_rad_arcs(
    tangency: tuple[Edge, PositionConstraint] | Edge | Vertex | VectorLike,
    *,
    center_on: Edge,
    radius: float,
    edge_factory: Callable[[TopoDS_Edge], TWrap],
) -> ShapeList[Edge]:
    """
    Create planar circle(s) on XY that:
      - are tangent/contacting a single object, and
      - have a fixed radius, and
      - have their CENTER constrained to lie on a given locus curve.

    Notes
    -----
    - The center locus must be a 2D curve (line/circle/any Geom2d curve) — i.e. an Edge
      after projection to XY.
    - With only one tangency, the natural geometric result is a full circle; arc cropping
      would require an additional endpoint constraint. This routine therefore returns
      closed circular edges (2π trims) for each valid solution.
    """

    # --- unpack optional qualifier on the tangency arg (edges only) ---
    if isinstance(tangency, tuple):
        object_one, obj1_qual = tangency
    else:
        object_one, obj1_qual = tangency, PositionConstraint.UNQUALIFIED

    # --- build tangency input (point/edge) ---
    q_o1, h_e1, e1_first, e1_last, is_edge1 = _as_gcc_arg(object_one, obj1_qual)

    # --- center locus ('center_on') must be a curve; ignore any qualifier there ---
    on_obj = center_on[0] if isinstance(center_on, tuple) else center_on
    if not isinstance(on_obj.wrapped, TopoDS_Edge):
        raise TypeError("center_on must be an Edge (line/circle/curve) for TanOnRad.")

    # Project the center locus Edge to 2D (XY)
    _, h_on2d, on_first, on_last, adapt_on = _edge_to_qualified_2d(
        on_obj.wrapped, PositionConstraint.UNQUALIFIED
    )
    gcc = Geom2dGcc_Circ2dTanOnRad(q_o1, adapt_on, radius, TOLERANCE)

    if not gcc.IsDone() or gcc.NbSolutions() == 0:
        raise RuntimeError("Unable to find circle(s) for TanOnRad constraints")

    def _ok1(u: float) -> bool:
        return True if not is_edge1 else _param_in_trim(u, e1_first, e1_last, h_e1)

    # --- enumerate solutions; emit full circles (2π trims) ---
    out_topos: list[TopoDS_Edge] = []
    for i in range(1, gcc.NbSolutions() + 1):
        circ = gcc.ThisSolution(i)  # gp_Circ2d

        # Validate tangency lies on trimmed span when the target is an Edge
        p = gp_Pnt2d()
        _u_on_circ, u_on_arg = gcc.Tangency1(i, p)
        if not _ok1(u_on_arg):
            continue

        # Center must lie on the trimmed center_on curve segment
        center2d = circ.Location()  # gp_Pnt2d

        # Project center onto the (trimmed) 2D locus
        proj = Geom2dAPI_ProjectPointOnCurve(center2d, h_on2d)
        if proj.NbPoints() == 0:
            continue  # no projection -> reject

        u_on = proj.Parameter(1)
        # Optional: make sure it's actually on the curve (not just near)
        if proj.Distance(1) > TOLERANCE:
            continue

        # Respect the trimmed interval (handles periodic curves too)
        if not _param_in_trim(u_on, on_first, on_last, h_on2d):
            continue

        h2d = Geom2d_Circle(circ)
        per = h2d.Period()
        out_topos.append(_edge_from_circle(h2d, 0.0, per))

    return ShapeList([edge_factory(e) for e in out_topos])
