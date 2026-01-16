# Intersection Refactoring Summary

## Current Implementation

The current implementation uses the (simplified) pattern

```python
result = BRepAlgoAPI_Section() + BRepAlgoAPI_Common()
filter_shapes_by_order(result, [Vertex, Edge, Face, Solid])
```

Unfortunately, filtering of found objects up to the highest order is not trivial in OCCT and can take a significant time per comparision, especially when solids with curved surfaces are involved.
And given the apporach, n x m comparisions are needed in the filter function (performance details see see https://github.com/gumyr/build123d/issues/1147).

## Goal of the new apporach

-   Define "real" intersections and distinguish them from touches (single point touch for faces, edge touch for solids, tangential touch, ...)
    -   The definition of intersect should be based on "what a CAD user expects", e.g. solid-solid = solid, face-face = face|edge, ...
-   Calculate intersect in the most efficient way, specifically for each shape type combination.
    -   No use of n x m comparisions with faces involved (note that comparisions of edges are significantly cheaper, in some test 5-15 times faster)
    -   For every costly OCCT method when filtering results, a non-optimal bounding box comparision should be done as early exit (no bbox overlap => no need to do the costly calculation)
-   Separate touch methods that calculate all possible touch results for the faces and solids
    -   intersect methods get a parameter `include_touched` that add touch results to the intersect results

### Intersect vs Touch

The distinction between `intersect` and `touch` is based on result dimension:

-   **Intersect**: Returns results down to a minimum dimension (interior overlap or crossing)
-   **Touch**: Returns boundary contacts with dimension below the minimum intersect dimension, filtered to the highest dimension at each contact location

| Combination     | Intersect result dims | Touch dims                   |
| --------------- | --------------------- | ---------------------------- |
| Solid + Solid   | 3 (Solid)             | 0, 1, 2 (Vertex, Edge, Face) |
| Solid + Face    | 2 (Face)              | 0, 1 (Vertex, Edge)          |
| Solid + Edge    | 1 (Edge)              | 0 (Vertex)                   |
| Solid + Vertex  | 0 (Vertex)            | —                            |
| Face + Face     | 1, 2 (Edge, Face)     | 0 (Vertex)                   |
| Face + Edge     | 0, 1 (Vertex, Edge)   | —                            |
| Face + Vertex   | 0 (Vertex)            | —                            |
| Edge + Edge     | 0, 1 (Vertex, Edge)   | —                            |
| Edge + Vertex   | 0 (Vertex)            | —                            |
| Vertex + Vertex | 0 (Vertex)            | —                            |

**Touch filtering**: At each contact location, only the highest-dimensional shape is returned. Lower-dimensional shapes that are boundaries of higher-dimensional contacts are filtered out. Note that this can get more expensive than the intersect implementation.

**Examples**:

-   Two boxes sharing a face: `touch` → `[Face]` (not the 4 edges and 4 vertices of that face)
-   Two boxes sharing an edge: `touch` → `[Edge]` (not the 2 endpoint vertices)
-   Two boxes sharing only a corner: `touch` → `[Vertex]`
-   Two faces with coplanar overlap AND crossing curve: `intersect` → `[Face, Edge]`

### Multi-object and Compound handling

| Routine                                                                                      | Semantics       |
| -------------------------------------------------------------------------------------------- | --------------- |
| BRepAlgoAPI_Common(c.wrapped, [c1.wrapped, c2.wrapped]).                                     | OR, partitioned |
| BRepAlgoAPI_Common(c.wrapped, [TopoDS_Compound([c1.wrapped, c2.wrapped])]), with c1 ∩ c2 = ∅ | OR \*           |
| c.intersect(c1, c2)                                                                          | AND             |
| c.intersect(Compound([c1, c2]))                                                              | OR              |
| c.intersect(Compound(children=[c1, c2]))                                                     | OR              |

Key:

-   AND: c ∩ c1 ∩ c2
-   OR: c ∩ (c1 ∪ c2)

\* A compound as tool shall not have overlapping solids according to OCCT docs

### Tangent Contact Validation

For tangent contacts (surfaces touching at a point), the `touch()` method validates:

1. **Edge boundary check**: Points near edges of both faces (within `tolerance`) are filtered out as edge-edge intersections, not vertex touches. Users should increase tolerance if BRepExtrema returns inaccurate points near edges.

2. **Normal direction check**: For points in the interior of both faces, normals must be parallel (dot ≈ 1) or anti-parallel (dot ≈ -1), meaning surfaces are tangent. This filters out false positives where surfaces cross at an angle.

3. **Crossing vertices**: Points on an edge of one face meeting the interior of another (perpendicular normals) are valid crossing vertices.

## Call Flow

Legend:

-   → handle: handles directly
-   → delegate: calls `other._intersect(self, ...)`
-   → distribute: iterates elements, calls `elem._intersect(...)`
-   `t`: `include_touched` passed through

### intersect() Call Flow

| Vertex.\_intersect(other)       |                                |
| ------------------------------- | ------------------------------ |
| `_intersect(Vertex, Vertex,  )` | → handle (distance check)      |
| `_intersect(Vertex, *, t)`      | → other.\_intersect(Vertex, t) |

| Mixin1D.\_intersect(other) [Edge, Wire] |                               |
| --------------------------------------- | ----------------------------- |
| `_intersect(Edge, Edge,  )`             | → handle (Common + Section)   |
| `_intersect(Edge, Wire,  )`             | → handle (Common + Section)   |
| `_intersect(Edge, Vertex,  )`           | → handle (distance check)     |
| `_intersect(Edge, *, t)`                | → `other._intersect(Edge, t)` |
| `_intersect(Wire, ...,  )`              | → same as Edge                |

| Mixin2D.\_intersect(other) [Face, Shell] |                                |
| ---------------------------------------- | ------------------------------ |
| `_intersect(Face, Face,  )`              | → handle (Common + Section)    |
| `_intersect(Face, Shell,  )`             | → handle (Common + Section)    |
| `_intersect(Face, Edge,  )`              | → handle (Section)             |
| `_intersect(Face, Wire,  )`              | → handle (Section)             |
| `_intersect(Face, Vertex,  )`            | → handle (distance check)      |
| `_intersect(Face, *, t)`                 | → `other._intersect(Face, t)`  |
| `_intersect(Shell, ...,  )`              | → same as Face                 |
| If `include_touched==True`:              | also calls `self.touch(other)` |

| Mixin3D.\_intersect(other) [Solid] |                                |
| ---------------------------------- | ------------------------------ |
| `_intersect(Solid, Solid,  )`      | → handle (Common)              |
| `_intersect(Solid, Face,  )`       | → handle (Common)              |
| `_intersect(Solid, Shell,  )`      | → handle (Common)              |
| `_intersect(Solid, Edge,  )`       | → handle (Common)              |
| `_intersect(Solid, Wire,  )`       | → handle (Common)              |
| `_intersect(Solid, Vertex,  )`     | → handle (is_inside)           |
| `_intersect(Solid, *, t)`          | → `other._intersect(Solid, t)` |
| If `include_touched==True`:        | also calls `self.touch(other)` |

| Compound.\_intersect(other)         |                         |
| ----------------------------------- | ----------------------- |
| `_intersect(Compound, Compound, t)` | → distribute all-vs-all |
| `_intersect(Compound, *, t)`        | → distribute over self  |

**Delegation chains** (examples):

-   `Edge._intersect(Solid, t)` → `Solid._intersect(Edge, t)` → handle
-   `Vertex._intersect(Face, t)` → `Face._intersect(Vertex, t)` → handle
-   `Face._intersect(Solid, t)` → `Solid._intersect(Face, t)` → handle
-   `Edge._intersect(Compound, t)` → `Compound._intersect(Edge, t)` → distribute

### touch() Call Flow

| Shape.touch(other) |                                            |
| ------------------ | ------------------------------------------ |
| `touch(Shape, *)`  | → returns empty `ShapeList()` (base impl.) |

| Mixin2D.touch(other) [Face, Shell] |                                       |
| ---------------------------------- | ------------------------------------- |
| `touch(Face, Face)`                | → handle (BRepExtrema + normal check) |
| `touch(Face, Shell)`               | → handle (BRepExtrema + normal check) |
| `touch(Face, *)`                   | → `other.touch(self)` (delegate)      |

| Mixin3D.touch(other) [Solid] |                                                          |
| ---------------------------- | -------------------------------------------------------- |
| `touch(Solid, Solid)`        | → handle (Common faces/edges/vertices)                   |
|                              | + `<self face>.touch(<other face>)` for tangent contacts |
| `touch(Solid, Face)`         | → handle (Common edges + BRepExtrema)                    |
| `touch(Solid, Edge)`         | → handle (Common vertices + BRepExtrema)                 |
| `touch(Solid, Vertex)`       | → handle (distance check to faces)                       |
| `touch(Solid, *)`            | → `other.touch(self)` (delegate)                         |

| Compound.touch(other) |                        |
| --------------------- | ---------------------- |
| `touch(Compound, *)`  | → distribute over self |

**Code reuse**: `Mixin3D.touch()` calls `Mixin2D.touch()` (via `<self face>.touch(<other face>)`) for Solid+Solid tangent vertex detection, ensuring consistent edge boundary and normal direction validation.

## Comparison Optimizations with non-optimal Bounding Boxes

### 1. Early Exit with Bounding Box Overlap

In `touch()` and `_intersect()`, we compare many shape pairs (faces×faces, edges×edges). Before calling `BRepAlgoAPI_Common` or other expensive methods, we want to early detect pairs that don't need to be checked (early exit)
This can be done with `distance_to()` calls (which use `BRepExtrema_DistShapeShape`), or checking bounding boxes overlap:

```python
# sf = <self face>, of = <other face>
# Option 1
if sf.distance_to(of) > tolerance:
    continue

# Option 2
if not sf_bb.overlaps(of_bb, tolerance):
    continue
```

`BoundBox.overlaps()` uses OCCT's `Bnd_Box.Distance()` method. Option 2 (bbox) is less accurate but significantly faster, see below.

### 2. Non-Optimal Bounding Boxes

`Shape.bounding_box(optimal=True)` computes precise bounds but is slow for curved geometry. For early-exit filtering, we use `optimal=False`:

| Object      | Faces | Edges | optimal=True | optimal=False | Speedup  |
| ----------- | ----- | ----- | ------------ | ------------- | -------- |
| ttt-ppp0102 | 10    | 17    | 86.7 ms      | 0.12 ms       | **729x** |
| ttt-ppp0107 | 44    | 95    | 59.7 ms      | 0.16 ms       | **373x** |
| ttt-ppp0104 | 23    | 62    | 12.6 ms      | 0.05 ms       | **252x** |
| ttt-ppp0106 | 32    | 89    | 12.2 ms      | 0.08 ms       | **153x** |
| ttt-ppp0101 | 32    | 84    | 0.3 ms       | 0.08 ms       | 4x       |
| ttt-ppp0105 | 18    | 40    | 0.04 ms      | 0.04 ms       | 1x       |

**Accuracy trade-off** (non-optimal bbox expansion):

| Object      | Solid Expansion | Max Face Expansion |
| ----------- | --------------- | ------------------ |
| ttt-ppp0107 | 7.7%            | 109.9%             |
| ttt-ppp0106 | 0.0%            | 65.5%              |
| ttt-ppp0104 | 4.8%            | 25.8%              |
| ttt-ppp0102 | 0.0%            | 8.3%               |
| ttt-ppp0101 | 0.0%            | 0.0%               |

Larger bboxes cause more false-positive overlaps → extra `BRepExtrema` checks, but the 100-800x speedup will most of the time outweigh this cost.

### 3. Pre-calculate and Cache Bounding Boxes

Without caching, nested loops recalculate bboxes n×m times:

```python
# sf = <self face>, of = <other face>
# Before: bbox computed 32×32×2 = 2048 times for 32-face solids
for sf in self.faces():
    for of in other.faces():
        if not sf.bounding_box().overlaps(of.bounding_box(), tolerance):

# After: bbox computed once per face
self_faces = [(f, f.bounding_box(optimal=False)) for f in self.faces()]
other_faces = [(f, f.bounding_box(optimal=False)) for f in other.faces()]
for sf, sf_bb in self_faces:
    for of, of_bb in other_faces:
        if not sf_bb.overlaps(of_bb, tolerance):
```

### 4. Performance Comparison

Face×face pair comparisons using ttt-ppp01\* examples:

| Object      | Faces | Pairs | bbox (build+distance_to) | distance_to for all | Speedup     |
| ----------- | ----- | ----- | ------------------------ | ------------------- | ----------- |
| ttt-ppp0107 | 44    | 1936  | 1.11 ms                  | 71,854 ms           | **65,019x** |
| ttt-ppp0102 | 10    | 100   | 0.33 ms                  | 6,629 ms            | **20,094x** |
| ttt-ppp0101 | 32    | 1024  | 0.59 ms                  | 5,119 ms            | **8,684x**  |
| ttt-ppp0106 | 32    | 1024  | 0.59 ms                  | 3,529 ms            | **5,963x**  |
| ttt-ppp0104 | 23    | 529   | 0.36 ms                  | 1,815 ms            | **4,982x**  |
| ttt-ppp0105 | 18    | 324   | 0.33 ms                  | 1,277 ms            | **3,885x**  |
| ttt-ppp0108 | 37    | 1369  | 0.79 ms                  | 2,938 ms            | **3,705x**  |

Edge×edge pair comparisons using ttt-ppp01\* examples:

| Object      | Edges | Pairs  | bbox (build+distance_to) | distance_to for all | Speedup     |
| ----------- | ----- | ------ | ------------------------ | ------------------- | ----------- |
| ttt-ppp0107 | 95    | 9,025  | 2.98 ms                  | 45,254 ms           | **15,203x** |
| ttt-ppp0102 | 17    | 289    | 0.39 ms                  | 4,801 ms            | **12,188x** |
| ttt-ppp0101 | 84    | 7,056  | 2.40 ms                  | 6,200 ms            | **2,584x**  |
| ttt-ppp0104 | 62    | 3,844  | 1.45 ms                  | 2,320 ms            | **1,597x**  |
| ttt-ppp0108 | 101   | 10,201 | 3.16 ms                  | 3,476 ms            | **1,100x**  |
| ttt-ppp0105 | 40    | 1,600  | 0.84 ms                  | 723 ms              | **859x**    |

The bbox approach is in any case significantly faster, making it essential for n×m pair operations in `touch()` and `_intersect()`.

## Typing Workaround

### Problem: Circular Dependencies

```
shape_core.py (Shape, ShapeList)
       ↑ imports
       │
   ┌───┴───┬───────┬───────┬──────────┐
   │       │       │       │          │
zero_d   one_d   two_d   three_d   composite
(Vertex) (Edge)  (Face)  (Solid)   (Compound)
         (Wire)  (Shell)
```

`shape_core.py` defines base classes, but intersection logic needs to check types (`isinstance(x, Wire)`), call methods (`shape.faces()`), etc. Direct imports would cause circular import errors.

### Solution: helpers.py as a Leaf Module

**helpers.py** imports everything at module level (it's a leaf - no one imports from it at module level):

```python
from build123d.topology.shape_core import Shape
from build123d.topology.one_d import Edge
from build123d.topology.two_d import Face
```

**Other modules** do runtime imports from helpers:

```python
# In shape_core.py Shape.intersect()
def intersect(self, ...):
    from build123d.topology.helpers import convert_to_shapes
```

Runtime imports happen after all modules are loaded, breaking the cycle.

## Tests

### Infrastructure Changes (support for `include_touched`)

-   Added `include_touched: bool = False` to `Case` dataclass
-   Updated `run_test` to pass `include_touched` to `Shape.intersect` (geometry objects don't have it)
-   Updated `make_params` to include `include_touched` in test parameters
-   Updated all test function signatures and `@pytest.mark.parametrize` decorators

### Behavioral: Solid boundary contacts (intersect vs touch separation)

| Test Case                        | Before     | After (no touch) | After (with touch) |
| -------------------------------- | ---------- | ---------------- | ------------------ |
| Solid + Edge, corner coincident  | `[Vertex]` | `None`           | `[Vertex]`         |
| Solid + Face, edge collinear     | `[Edge]`   | `None`           | `[Edge]`           |
| Solid + Face, corner coincident  | `[Vertex]` | `None`           | `[Vertex]`         |
| Solid + Solid, edge collinear    | `[Edge]`   | `None`           | `[Edge]`           |
| Solid + Solid, corner coincident | `[Vertex]` | `None`           | `[Vertex]`         |
| Solid + Solid, face coincident   | N/A (new)  | `None`           | `[Face]`           |
| Solid + Solid, tangential point  | N/A (new)  | `None`           | `[Vertex]`         |

### Behavioral: Face boundary contacts (intersect vs touch separation)

| Test Case                    | Before     | After (no touch) | After (with touch) |
| ---------------------------- | ---------- | ---------------- | ------------------ |
| Face + Face, crossing vertex | `[Vertex]` | `None`           | `[Vertex]`         |

Two non-coplanar faces that cross at a single point (due to finite extent) now return the vertex via `touch()` rather than `intersect()`. Added `Mixin2D.touch()` method.

These represent the semantic change: boundary contacts are **not** interior intersections, so `intersect()` returns `None`. Use `include_touched=True` to get them.

### Behavioral: Tangent edge (Edge lying on Solid surface)

| Test Case                  | Result   | Notes                                       |
| -------------------------- | -------- | ------------------------------------------- |
| Solid + Edge, tangent edge | `[Edge]` | Edge on cylinder surface is an intersection |

A tangent edge (lying ON a solid's surface) is treated as an **intersection** (1D result), not a touch. This is because `touch` for Solid+Edge only returns Vertex (0D). The edge is returned by `BRepAlgoAPI_Common` since it's "common" to both shapes.

### New test cases: Common + Section (mixed overlap and crossing)

| Test Case                          | Result           | Description                                      |
| ---------------------------------- | ---------------- | ------------------------------------------------ |
| Edge + Edge, spline common+section | `[Edge, Vertex]` | Spline with collinear segment and crossing point |
| Face + Face, common+section        | `[Face, Edge]`   | Face with coplanar overlap and crossing curve    |

These test cases verify correct handling when both `BRepAlgoAPI_Common` (overlap) and `BRepAlgoAPI_Section` (crossing) return results for the same shape pair.

### Bug fixes / xfail removals

| Test Case                      | Before                                | After                              |
| ------------------------------ | ------------------------------------- | ---------------------------------- |
| Solid + Edge, edge collinear   | `[Edge]` with xfail "duplicate edges" | `[Edge]` passing                   |
| Curve + Compound, intersecting | `[Edge, Edge]` with xfail             | `[Edge, Edge, Edge, Edge]` passing |

### New test: edge tolerance filtering

Added `test_touch_edge_tolerance()` to test filtering of false positive vertices:

-   Tests torus (fillet) surface vs cylinder surface where BRepExtrema finds a point near edges of both faces
-   With `tolerance=1e-3`, the point is detected as on both edges and filtered out
-   `touch(tolerance=1e-3)` returns empty, `intersect(include_touched=True, tolerance=1e-3)` returns only `[Edge]`

### Performance tests

#### Summary

| name                                                    |        dev | this branch | commit fa8e936 | this branch / dev | this branch / commit fa8e936 |
| ------------------------------------------------------- | ---------: | ----------: | -------------: | ----------------: | ---------------------------: |
| tests/test_benchmarks.py::test_mesher_benchmark[100]    |     1.5717 |      1.1761 |         1.5013 |           -25.17% |                      -21.66% |
| tests/test_benchmarks.py::test_mesher_benchmark[1000]   |     3.1709 |      2.6653 |         2.9810 |           -15.95% |                      -10.59% |
| tests/test_benchmarks.py::test_mesher_benchmark[10000]  |    18.8172 |     18.3698 |        18.5138 |            -2.38% |                       -0.78% |
| tests/test_benchmarks.py::test_mesher_benchmark[100000] |   272.6479 |    260.0706 |       349.1587 |            -4.61% |                      -25.51% |
| tests/test_benchmarks.py::test_ppp_0101                 | 2,840.2942 |    147.7914 |       146.8151 |           -94.80% |                       +0.66% |
| tests/test_benchmarks.py::test_ppp_0102                 |   183.6392 |    182.4804 |       181.5972 |            -0.63% |                       +0.49% |
| tests/test_benchmarks.py::test_ppp_0103                 |    68.3975 |     68.1508 |        68.0329 |            -0.36% |                       +0.17% |
| tests/test_benchmarks.py::test_ppp_0104                 |   114.2050 |    113.7093 |       113.0657 |            -0.43% |                       +0.57% |
| tests/test_benchmarks.py::test_ppp_0105                 |    83.0605 |     80.7737 |        80.0031 |            -2.75% |                       +0.96% |
| tests/test_benchmarks.py::test_ppp_0106                 | 9,311.8187 |     82.1598 |        82.4856 |           -99.12% |                       -0.40% |
| tests/test_benchmarks.py::test_ppp_0107                 |   308.6340 |    296.7623 |       298.2377 |            -3.85% |                       -0.49% |
| tests/test_benchmarks.py::test_ppp_0108                 |   136.9441 |     83.1816 |        82.4641 |           -39.25% |                       +0.87% |
| tests/test_benchmarks.py::test_ppp_0109                 |   113.9680 |    109.5960 |       128.6220 |            -3.84% |                      -14.79% |
| tests/test_benchmarks.py::test_ppp_0110                 |   244.0596 |    223.9091 |       222.1242 |            -8.26% |                       +0.80% |
| tests/test_benchmarks.py::test_ttt_23_02_02             |   646.0093 |    628.2953 |       631.9749 |            -2.74% |                       -0.58% |
| tests/test_benchmarks.py::test_ttt_23_T_24              |   236.9038 |    148.0144 |       146.1597 |           -37.52% |                       +1.27% |
| tests/test_benchmarks.py::test_ttt_24_SPO_06            |   150.4492 |    144.2704 |       142.6785 |            -4.11% |                       +1.12% |

\* Changed to use `extrude(UNTIL)` as in dev

#### Details

-   **Against dev ()**

    ```text
    ---------------------------------------------------------------------------------------------- benchmark: 17 tests ----------------------------------------------------------------------------------------------
    Name (time in ms)                        Min                   Max                  Mean             StdDev                Median                 IQR            Outliers       OPS            Rounds  Iterations
    -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    test_mesher_benchmark[100]            1.4136 (1.0)         79.2088 (1.15)         2.6825 (1.0)       7.8029 (14.67)        1.5717 (1.0)        0.3249 (1.0)          1;18  372.7835 (1.0)          99           1
    test_mesher_benchmark[1000]           2.8029 (1.98)        93.6249 (1.35)         3.9942 (1.49)      7.2583 (13.64)        3.1709 (2.02)       0.8664 (2.67)          2;2  250.3631 (0.67)        302           1
    test_mesher_benchmark[10000]         18.0781 (12.79)      108.9087 (1.58)        30.7976 (11.48)    28.3765 (53.34)       18.8172 (11.97)      0.6993 (2.15)          8;8   32.4701 (0.09)         51           1
    test_mesher_benchmark[100000]       262.4835 (185.68)     350.2263 (5.07)       299.1632 (111.52)   42.1747 (79.28)      272.6479 (173.48)    73.7383 (226.95)        1;0    3.3427 (0.01)          5           1
    test_ppp_0101                     2,837.7637 (>1000.0)  2,842.9180 (41.12)    2,840.0422 (>1000.0)   2.0992 (3.95)     2,840.2942 (>1000.0)    3.3399 (10.28)         2;0    0.3521 (0.00)          5           1
    test_ppp_0102                       182.9260 (129.40)     185.0174 (2.68)       183.7750 (68.51)     0.7393 (1.39)       183.6392 (116.84)     0.8202 (2.52)          2;0    5.4414 (0.01)          6           1
    test_ppp_0103                        66.9251 (47.34)       69.1312 (1.0)         68.3137 (25.47)     0.5320 (1.0)         68.3975 (43.52)      0.5088 (1.57)          4;1   14.6384 (0.04)         15           1
    test_ppp_0104                       112.7356 (79.75)      115.8168 (1.68)       114.0572 (42.52)     0.9064 (1.70)       114.2050 (72.66)      1.0003 (3.08)          3;0    8.7675 (0.02)          9           1
    test_ppp_0105                        80.5439 (56.98)      101.4349 (1.47)        84.6426 (31.55)     5.5137 (10.36)       83.0605 (52.85)      3.3439 (10.29)         1;1   11.8144 (0.03)         13           1
    test_ppp_0106                     9,240.8689 (>1000.0)  9,385.3153 (135.76)   9,312.1906 (>1000.0)  65.8610 (123.80)   9,311.8187 (>1000.0)  124.3155 (382.61)        2;0    0.1074 (0.00)          5           1
    test_ppp_0107                       301.7400 (213.45)     314.9581 (4.56)       308.1962 (114.89)    5.5353 (10.40)      308.6340 (196.37)     9.5510 (29.40)         2;0    3.2447 (0.01)          5           1
    test_ppp_0108                       135.0608 (95.54)      140.0305 (2.03)       136.7690 (50.99)     1.5956 (3.00)       136.9441 (87.13)      1.7559 (5.40)          3;1    7.3116 (0.02)          8           1
    test_ppp_0109                       111.1487 (78.63)      116.3623 (1.68)       113.8869 (42.46)     1.4392 (2.71)       113.9680 (72.51)      1.4837 (4.57)          2;0    8.7806 (0.02)          9           1
    test_ppp_0110                       242.1086 (171.27)     247.1587 (3.58)       244.1418 (91.01)     1.8841 (3.54)       244.0596 (155.29)     2.0497 (6.31)          2;0    4.0960 (0.01)          5           1
    test_ttt_23_02_02                   632.3757 (447.34)     672.3315 (9.73)       652.9795 (243.42)   16.8402 (31.65)      646.0093 (411.03)    26.8589 (82.66)         2;0    1.5314 (0.00)          5           1
    test_ttt_24_SPO_06                  222.7247 (157.56)     240.4287 (3.48)       232.5369 (86.69)     7.9419 (14.93)      236.9038 (150.73)    13.4055 (41.26)         1;0    4.3004 (0.01)          5           1
    test_ttt_23_T_24                    148.6132 (105.13)     153.2385 (2.22)       150.9910 (56.29)     1.9488 (3.66)       150.4492 (95.73)      3.2687 (10.06)         2;0    6.6229 (0.02)          5           1
    -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    ```

-   **With this PR**

    ```text
    ----------------------------------------------------------------------------------------- benchmark: 17 tests ------------------------------------------------------------------------------------------
    Name (time in ms)                      Min                 Max                Mean             StdDev              Median                IQR            Outliers       OPS            Rounds  Iterations
    --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    test_mesher_benchmark[100]          1.0956 (1.0)       69.3311 (1.0)        1.9552 (1.0)       5.4247 (8.91)       1.1761 (1.0)       0.2108 (1.0)          1;30  511.4671 (1.0)         159           1
    test_mesher_benchmark[1000]         2.5016 (2.28)      81.8406 (1.18)       3.4415 (1.76)      5.3939 (8.86)       2.6653 (2.27)      1.1725 (5.56)          2;2  290.5734 (0.57)        351           1
    test_mesher_benchmark[10000]       17.9532 (16.39)     87.1914 (1.26)      30.6284 (15.67)    25.7683 (42.34)     18.3698 (15.62)     0.5098 (2.42)        10;10   32.6494 (0.06)         53           1
    test_mesher_benchmark[100000]     253.4639 (231.35)   403.4200 (5.82)     300.8966 (153.90)   65.6729 (107.91)   260.0706 (221.12)   92.8300 (440.36)        1;0    3.3234 (0.01)          5           1
    test_ppp_0101                     146.7774 (133.97)   149.4735 (2.16)     147.9447 (75.67)     0.8912 (1.46)     147.7914 (125.66)    1.1141 (5.29)          2;0    6.7593 (0.01)          7           1
    test_ppp_0102                     180.5352 (164.78)   185.5049 (2.68)     182.7296 (93.46)     1.8601 (3.06)     182.4804 (155.15)    3.0510 (14.47)         2;0    5.4726 (0.01)          6           1
    test_ppp_0103                      67.2411 (61.37)    124.2962 (1.79)      72.2580 (36.96)    14.5204 (23.86)     68.1508 (57.95)     1.1235 (5.33)          1;2   13.8393 (0.03)         15           1
    test_ppp_0104                     111.7916 (102.04)   115.5179 (1.67)     113.7953 (58.20)     1.2992 (2.13)     113.7093 (96.68)     1.9166 (9.09)          4;0    8.7877 (0.02)          9           1
    test_ppp_0105                      71.0350 (64.84)     87.2390 (1.26)      80.2263 (41.03)     4.7796 (7.85)      80.7737 (68.68)     7.4897 (35.53)         5;0   12.4647 (0.02)         13           1
    test_ppp_0106                      78.6643 (71.80)     83.4581 (1.20)      81.7541 (41.81)     1.4432 (2.37)      82.1598 (69.86)     1.8966 (9.00)          5;0   12.2318 (0.02)         12           1
    test_ppp_0107                     290.1933 (264.88)   302.6345 (4.37)     296.2779 (151.54)    5.0355 (8.27)     296.7623 (252.32)    8.2492 (39.13)         2;0    3.3752 (0.01)          5           1
    test_ppp_0108                      82.7089 (75.49)     85.0884 (1.23)      83.5954 (42.76)     0.8842 (1.45)      83.1816 (70.73)     1.5849 (7.52)          4;0   11.9624 (0.02)         12           1
    test_ppp_0109                     108.6753 (99.19)    110.3898 (1.59)     109.6267 (56.07)     0.6086 (1.0)      109.5960 (93.18)     0.7843 (3.72)          4;0    9.1219 (0.02)         10           1
    test_ppp_0110                     221.1847 (201.89)   226.9487 (3.27)     224.2491 (114.70)    2.2437 (3.69)     223.9091 (190.38)    3.3070 (15.69)         2;0    4.4593 (0.01)          5           1
    test_ttt_23_02_02                 627.2946 (572.57)   639.3529 (9.22)     630.5674 (322.51)    4.9883 (8.20)     628.2953 (534.21)    4.1876 (19.86)         1;1    1.5859 (0.00)          5           1
    test_ttt_23_T_24                  146.2842 (133.52)   149.4915 (2.16)     147.9576 (75.68)     1.2978 (2.13)     148.0144 (125.85)    2.1337 (10.12)         2;0    6.7587 (0.01)          5           1
    test_ttt_24_SPO_06                143.4400 (130.93)   145.8922 (2.10)     144.6000 (73.96)     1.0524 (1.73)     144.2704 (122.67)    2.0361 (9.66)          4;0    6.9156 (0.01)          7           1
    --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    ```

-   **Before all intersect PR (commit fa8e936)**

    ```text
    ----------------------------------------------------------------------------------------- benchmark: 17 tests ------------------------------------------------------------------------------------------
    Name (time in ms)                      Min                 Max                Mean             StdDev              Median                IQR            Outliers       OPS            Rounds  Iterations
    --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    test_mesher_benchmark[100]          1.4098 (1.0)       74.0287 (16.20)      2.5949 (1.0)       7.4405 (12.63)      1.5013 (1.0)       0.1877 (1.0)          1;18  385.3707 (1.0)          95           1
    test_mesher_benchmark[1000]         2.8225 (2.00)       4.5707 (1.0)        3.3640 (1.30)      0.5890 (1.0)        2.9810 (1.99)      1.2073 (6.43)         61;0  297.2643 (0.77)        185           1
    test_mesher_benchmark[10000]       18.2586 (12.95)     96.1952 (21.05)     31.0653 (11.97)    28.0866 (47.68)     18.5138 (12.33)     0.4388 (2.34)          9;9   32.1902 (0.08)         53           1
    test_mesher_benchmark[100000]     267.0532 (189.42)   350.7605 (76.74)    317.7271 (122.44)   44.4738 (75.50)    349.1587 (232.57)   80.6410 (429.56)        2;0    3.1474 (0.01)          5           1
    test_ppp_0101                     145.2433 (103.02)   149.5188 (32.71)    147.0663 (56.68)     1.3792 (2.34)     146.8151 (97.79)     1.4942 (7.96)          2;0    6.7997 (0.02)          7           1
    test_ppp_0102                     178.8649 (126.87)   184.7600 (40.42)    181.7531 (70.04)     1.9309 (3.28)     181.5972 (120.96)    1.4921 (7.95)          2;1    5.5020 (0.01)          6           1
    test_ppp_0103                      66.1185 (46.90)     68.7325 (15.04)     67.7935 (26.13)     0.7213 (1.22)      68.0329 (45.32)     0.8712 (4.64)          4;0   14.7507 (0.04)         15           1
    test_ppp_0104                     111.4481 (79.05)    114.5727 (25.07)    113.1267 (43.60)     1.0848 (1.84)     113.0657 (75.31)     1.5002 (7.99)          4;0    8.8396 (0.02)          9           1
    test_ppp_0105                      75.2770 (53.39)     86.6317 (18.95)     80.6485 (31.08)     3.1719 (5.38)      80.0031 (53.29)     3.3093 (17.63)         3;0   12.3995 (0.03)         12           1
    test_ppp_0106                      80.9383 (57.41)     83.6762 (18.31)     82.3659 (31.74)     0.8217 (1.39)      82.4856 (54.94)     1.0667 (5.68)          4;0   12.1409 (0.03)         12           1
    test_ppp_0107                     291.7345 (206.93)   302.4655 (66.17)    297.8876 (114.80)    4.0816 (6.93)     298.2377 (198.65)    5.4786 (29.18)         2;0    3.3570 (0.01)          5           1
    test_ppp_0108                      80.2130 (56.90)     86.2986 (18.88)     82.6410 (31.85)     1.5109 (2.57)      82.4641 (54.93)     1.1424 (6.09)          2;2   12.1005 (0.03)         12           1
    test_ppp_0109                     126.3475 (89.62)    129.0997 (28.24)    128.2563 (49.43)     0.9785 (1.66)     128.6220 (85.67)     1.2114 (6.45)          2;0    7.7969 (0.02)          8           1
    test_ppp_0110                     219.2367 (155.51)   223.5040 (48.90)    221.4452 (85.34)     1.9318 (3.28)     222.1242 (147.95)    3.4878 (18.58)         2;0    4.5158 (0.01)          5           1
    test_ttt_23_02_02                 613.0934 (434.87)   645.0137 (141.12)   631.2053 (243.25)   12.1928 (20.70)    631.9749 (420.94)   16.7976 (89.48)         2;0    1.5843 (0.00)          5           1
    test_ttt_23_T_24                  143.7815 (101.98)   148.1351 (32.41)    146.1890 (56.34)     1.6663 (2.83)     146.1597 (97.35)     2.3439 (12.49)         2;0    6.8405 (0.02)          5           1
    test_ttt_24_SPO_06                139.9076 (99.24)    144.1027 (31.53)    142.3341 (54.85)     1.4964 (2.54)     142.6785 (95.03)     2.3097 (12.30)         2;0    7.0257 (0.02)          7           1
    --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    ```

    Note: Changed test_ppp_0109 to use `extrude(UNITL)` instead of `extrude` as in `dev`branch and this PR

    ```diff
    diff --git a/docs/assets/ttt/ttt-ppp0109.py b/docs/assets/ttt/ttt-ppp0109.py
    index b00b0bc..82a4260 100644
    --- a/docs/assets/ttt/ttt-ppp0109.py
    +++ b/docs/assets/ttt/ttt-ppp0109.py
    @@ -47,9 +47,10 @@ with BuildPart() as ppp109:
            split(bisect_by=Plane.YZ)
        extrude(amount=6)
        f = ppp109.faces().filter_by(Axis((0, 0, 0), (-1, 0, 1)))[0]
    -    # extrude(f, until=Until.NEXT) # throws a warning
    -    extrude(f, amount=10)
    -    fillet(ppp109.edge(Select.NEW), 16)
    +    extrude(f, until=Until.NEXT)
    +    fillet(ppp109.edges().filter_by(Axis.Y).sort_by(Axis.Z)[2], 16)
    +    # extrude(f, amount=10)
    +    # fillet(ppp109.edge(Select.NEW), 16)
    ```
