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

- Define "real" intersections and distinguish them from touches (single point touch for faces, edge touch for solids, tangential touch, ...)
    - The definition of intersect should be based on "what a CAD user expects", e.g. solid-solid = solid, face-face = face|edge, ...
- Calculate intersect in the most efficient way, specifically for each shape type combination.
    - No use of n x m comparisions with faces involved (note that comparisions of edges are significantly cheaper, in some test 5-15 times faster)
    - For every costly OCCT method when filtering results, a non-optimal bounding box comparision should be done as early exit (no bbox overlap => no need to do the costly calculation)
- Separate touch methods that calculate all possible touch results for the faces and solids
    - intersect methods get a parameter `include_touched` that add touch results to the intersect results

### Intersect vs Touch

The distinction between `intersect` and `touch` is based on result dimension:

- **Intersect**: Returns results down to a minimum dimension (interior overlap or crossing)
- **Touch**: Returns boundary contacts with dimension below the minimum intersect dimension, filtered to the highest dimension at each contact location

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

- Two boxes sharing a face: `touch` → `[Face]` (not the 4 edges and 4 vertices of that face)
- Two boxes sharing an edge: `touch` → `[Edge]` (not the 2 endpoint vertices)
- Two boxes sharing only a corner: `touch` → `[Vertex]`
- Two faces with coplanar overlap AND crossing curve: `intersect` → `[Face, Edge]`

### Multi-object and Compound handling

| Routine                                                                                      | Semantics       |
| -------------------------------------------------------------------------------------------- | --------------- |
| BRepAlgoAPI_Common(c.wrapped, [c1.wrapped, c2.wrapped]).                                     | OR, partitioned |
| BRepAlgoAPI_Common(c.wrapped, [TopoDS_Compound([c1.wrapped, c2.wrapped])]), with c1 ∩ c2 = ∅ | OR \*           |
| c.intersect(c1, c2)                                                                          | AND             |
| c.intersect(Compound([c1, c2]))                                                              | OR              |
| c.intersect(Compound(children=[c1, c2]))                                                     | OR              |

Key:

- AND: c ∩ c1 ∩ c2
- OR: c ∩ (c1 ∪ c2)

\* A compound as tool shall not have overlapping solids according to OCCT docs

### Tangent Contact Validation

For tangent contacts (surfaces touching at a point), the `touch()` method validates:

1. **Edge boundary check**: Points near edges of both faces (within `tolerance`) are filtered out as edge-edge intersections, not vertex touches. Users should increase tolerance if BRepExtrema returns inaccurate points near edges.

2. **Normal direction check**: For points in the interior of both faces, normals must be parallel (dot ≈ 1) or anti-parallel (dot ≈ -1), meaning surfaces are tangent. This filters out false positives where surfaces cross at an angle.

3. **Crossing vertices**: Points on an edge of one face meeting the interior of another (perpendicular normals) are valid crossing vertices.

## Call Flow

Legend:

- → handle: handles directly
- → delegate: calls `other._intersect(self, ...)`
- → distribute: iterates elements, calls `elem._intersect(...)`
- `t`: `include_touched` passed through

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

- `Edge._intersect(Solid, t)` → `Solid._intersect(Edge, t)` → handle
- `Vertex._intersect(Face, t)` → `Face._intersect(Vertex, t)` → handle
- `Face._intersect(Solid, t)` → `Solid._intersect(Face, t)` → handle
- `Edge._intersect(Compound, t)` → `Compound._intersect(Edge, t)` → distribute

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

- Added `include_touched: bool = False` to `Case` dataclass
- Updated `run_test` to pass `include_touched` to `Shape.intersect` (geometry objects don't have it)
- Updated `make_params` to include `include_touched` in test parameters
- Updated all test function signatures and `@pytest.mark.parametrize` decorators

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

- Tests torus (fillet) surface vs cylinder surface where BRepExtrema finds a point near edges of both faces
- With `tolerance=1e-3`, the point is detected as on both edges and filtered out
- `touch(tolerance=1e-3)` returns empty, `intersect(include_touched=True, tolerance=1e-3)` returns only `[Edge]`

### Performance tests

#### Summary

| name                                                    |        dev | this branch | commit fa8e936 | this branch / dev | this branch / commit fa8e936 |
| ------------------------------------------------------- | ---------: | ----------: | -------------: | ----------------: | ---------------------------: |
| tests/test_benchmarks.py::test_mesher_benchmark[100]    |     1.5717 |      1.1397 |         1.5013 |            -27.5% |                       -24.1% |
| tests/test_benchmarks.py::test_mesher_benchmark[1000]   |     3.1709 |      2.5261 |         2.9810 |            -20.3% |                       -15.3% |
| tests/test_benchmarks.py::test_mesher_benchmark[10000]  |    18.8172 |     17.6889 |        18.5138 |             -6.0% |                        -4.5% |
| tests/test_benchmarks.py::test_mesher_benchmark[100000] |   272.6479 |    254.8131 |       349.1587 |             -6.5% |                       -27.0% |
| tests/test_benchmarks.py::test_ppp_0101                 | 2,840.2942 |    148.3832 |       146.8151 |            -94.8% |                        +1.1% |
| tests/test_benchmarks.py::test_ppp_0102                 |   183.6392 |    176.3687 |       181.5972 |             -4.0% |                        -2.9% |
| tests/test_benchmarks.py::test_ppp_0103                 |    68.3975 |     69.5209 |        68.0329 |             +1.6% |                        +2.2% |
| tests/test_benchmarks.py::test_ppp_0104                 |   114.2050 |    115.6945 |       113.0657 |             +1.3% |                        +2.3% |
| tests/test_benchmarks.py::test_ppp_0105                 |    83.0605 |     78.0547 |        80.0031 |             -6.0% |                        -2.4% |
| tests/test_benchmarks.py::test_ppp_0106                 | 9,311.8187 |     85.0790 |        82.4856 |            -99.1% |                        +3.1% |
| tests/test_benchmarks.py::test_ppp_0107                 |   308.6340 |    286.2196 |       298.2377 |             -7.3% |                        -4.0% |
| tests/test_benchmarks.py::test_ppp_0108                 |   136.9441 |     69.9309 |        82.4641 |            -48.9% |                       -15.2% |
| tests/test_benchmarks.py::test_ppp_0109                 |   113.9680 |    111.8273 |       128.6220 |             -1.9% |                       -13.1% |
| tests/test_benchmarks.py::test_ppp_0110                 |   244.0596 |    217.1883 |       222.1242 |            -11.0% |                        -2.2% |
| tests/test_benchmarks.py::test_ttt_23_02_02             |   646.0093 |    620.3012 |       631.9749 |             -4.0% |                        -1.8% |
| tests/test_benchmarks.py::test_ttt_23_T_24              |   236.9038 |    147.6732 |       146.1597 |            -37.7% |                        +1.0% |
| tests/test_benchmarks.py::test_ttt_24_SPO_06            |   150.4492 |    144.6859 |       142.6785 |             -3.8% |                        +1.4% |

\* Changed to use `extrude(UNTIL)` as in dev

#### Details

- **Against dev ()**

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

- **With this PR**

    ````text
    ----------------------------------------------------------------------------------------- benchmark: 17 tests ------------------------------------------------------------------------------------------
    Name (time in ms)                      Min                 Max                Mean             StdDev              Median                IQR            Outliers       OPS            Rounds  Iterations
    --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    test_mesher_benchmark[100]          1.0574 (1.0)       70.4643 (1.0)        1.8813 (1.0)       5.4627 (8.54)       1.1397 (1.0)       0.2145 (1.06)         1;30  531.5461 (1.0)         162           1
    test_mesher_benchmark[1000]         2.4607 (2.33)      77.6734 (1.10)       3.2727 (1.74)      5.4347 (8.50)       2.5261 (2.22)      0.9649 (4.76)          2;2  305.5623 (0.57)        379           1
    test_mesher_benchmark[10000]       17.5591 (16.61)     80.8897 (1.15)      27.3925 (14.56)    23.6991 (37.06)     17.6889 (15.52)     0.2028 (1.0)           2;2   36.5064 (0.07)         13           1
    test_mesher_benchmark[100000]     251.0655 (237.44)   392.6514 (5.57)     296.1126 (157.40)   62.7306 (98.09)    254.8131 (223.57)   89.8318 (443.07)        1;0    3.3771 (0.01)          5           1
    test_ppp_0101                     145.0982 (137.22)   149.1414 (2.12)     147.7855 (78.55)     1.4913 (2.33)     148.3832 (130.19)    2.0036 (9.88)          1;0    6.7666 (0.01)          7           1
    test_ppp_0102                     175.2033 (165.70)   178.3188 (2.53)     176.4481 (93.79)     1.0492 (1.64)     176.3687 (154.75)    0.7466 (3.68)          2;1    5.6674 (0.01)          6           1
    test_ppp_0103                      67.6037 (63.94)    120.4952 (1.71)      72.7045 (38.65)    13.2495 (20.72)     69.5209 (61.00)     1.0713 (5.28)          1;2   13.7543 (0.03)         15           1
    test_ppp_0104                     114.5725 (108.36)   116.3083 (1.65)     115.5820 (61.44)     0.6395 (1.0)      115.6945 (101.51)    0.9241 (4.56)          4;0    8.6519 (0.02)          9           1
    test_ppp_0105                      75.7650 (71.65)     79.4025 (1.13)      77.9072 (41.41)     1.0489 (1.64)      78.0547 (68.49)     1.7325 (8.54)          2;0   12.8358 (0.02)         13           1
    test_ppp_0106                      84.4754 (79.89)     86.6812 (1.23)      85.3290 (45.36)     0.6590 (1.03)      85.0790 (74.65)     1.0335 (5.10)          3;0   11.7193 (0.02)         12           1
    test_ppp_0107                     285.1950 (269.72)   288.7532 (4.10)     286.7046 (152.40)    1.3588 (2.12)     286.2196 (251.13)    1.7592 (8.68)          2;0    3.4879 (0.01)          5           1
    test_ppp_0108                      65.4866 (61.93)     70.9025 (1.01)      69.5202 (36.95)     1.3768 (2.15)      69.9309 (61.36)     0.8998 (4.44)          3;2   14.3843 (0.03)         15           1
    test_ppp_0109                     110.2980 (104.31)   113.0410 (1.60)     111.7263 (59.39)     0.7629 (1.19)     111.8273 (98.12)     0.4203 (2.07)          3;3    8.9504 (0.02)          9           1
    test_ppp_0110                     214.6389 (202.99)   218.8224 (3.11)     217.1718 (115.44)    1.7101 (2.67)     217.1883 (190.56)    2.6129 (12.89)         1;0    4.6046 (0.01)          5           1
    test_ttt_23_02_02                 617.3580 (583.86)   623.1470 (8.84)     620.1268 (329.63)    2.1388 (3.34)     620.3012 (544.25)    2.6976 (13.30)         2;0    1.6126 (0.00)          5           1
    test_ttt_23_T_24                  145.4708 (137.58)   148.7882 (2.11)     147.1501 (78.22)     1.3564 (2.12)     147.6732 (129.57)    2.1137 (10.43)         2;0    6.7958 (0.01)          5           1
    test_ttt_24_SPO_06                143.1023 (135.34)   147.4160 (2.09)     144.8468 (76.99)     1.3698 (2.14)     144.6859 (126.95)    1.3559 (6.69)          2;1    6.9038 (0.01)          7           1
    -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- ```

    ````

- **Before all intersect PR (commit fa8e936)**

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
