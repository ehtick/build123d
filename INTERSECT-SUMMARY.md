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

### Test Case Counts

|                       | dev branch | this branch | change |
| --------------------- | ---------: | ----------: | -----: |
| Case definitions      |        199 |         241 |    +42 |
| Parametrized tests \* |        322 |         379 |    +57 |

\* Parametrized tests include symmetry swaps (A×B also tested as B×A) where applicable

**Breakdown by matrix:**

| Matrix                | dev | this | change |
| --------------------- | --: | ---: | -----: |
| geometry_matrix       |  47 |   47 |      0 |
| shape_0d_matrix       |  20 |   20 |      0 |
| shape_1d_matrix       |  60 |   60 |      0 |
| shape_2d_matrix       |  64 |   73 |     +9 |
| shape_3d_matrix       |  65 |   96 |    +31 |
| shape_compound_matrix |  43 |   60 |    +17 |
| freecad_matrix        |  15 |   15 |      0 |
| issues_matrix         |   8 |    8 |      0 |

### Changes Summary

**Infrastructure changes:**

- Added `include_touched: bool = False` to `Case` dataclass
- Updated `run_test` to pass `include_touched` to `Shape.intersect` (geometry objects don't have it)
- Updated `make_params` to include `include_touched` in test parameters; symmetry swaps disabled for `include_touched` tests
- Updated all test function signatures and `@pytest.mark.parametrize` decorators

**New test objects:**

- `sh7`, `sh8`: Half-sphere shells for tangent touch testing
- `fc10`: Tangent face for sphere tangent contact

**New test case categories:**

- Face+Face crossing vertex: paired tests (without touch → `None`, with `include_touched` → `[Vertex]`)
- Shell+Face/Shell tangent touch: tests for tangent surface contacts
- Solid+Edge/Face/Solid boundary contacts: paired tests for corner/edge/face coincidence
- Compound+Shape with `include_touched`: tests for boundary contacts through compounds

### Behavioral: Solid boundary contacts (intersect vs touch separation)

| Test Case                        | Before     | After (no touch) | After (with touch) |
| -------------------------------- | ---------- | ---------------- | ------------------ |
| Solid + Edge, corner coincident  | `[Vertex]` | `None`           | `[Vertex]`         |
| Solid + Face, edge collinear     | `[Edge]`   | `None`           | `[Edge]`           |
| Solid + Face, corner coincident  | `[Vertex]` | `None`           | `[Vertex]`         |
| Solid + Solid, edge collinear    | `[Edge]`   | `None`           | `[Edge]`           |
| Solid + Solid, corner coincident | `[Vertex]` | `None`           | `[Vertex]`         |
| Solid + Solid, face coincident   | N/A (new)  | `None`           | `[Face]`           |

### Behavioral: Face/Shell boundary contacts (intersect vs touch separation)

| Test Case                    | Before     | After (no touch) | After (with touch) |
| ---------------------------- | ---------- | ---------------- | ------------------ |
| Face + Face, crossing vertex | `[Vertex]` | `None`           | `[Vertex]`         |
| Shell + Face, tangent touch  | N/A (new)  | `None`           | `[Vertex]`         |
| Shell + Shell, tangent touch | N/A (new)  | `None`           | `[Vertex]`         |

Two non-coplanar faces that cross at a single point (due to finite extent) now return the vertex via `touch()` rather than `intersect()`. Added `Mixin2D.touch()` method.

These represent the semantic change: boundary contacts are **not** interior intersections, so `intersect()` returns `None`. Use `include_touched=True` to get them.

### Bug fixes / xfail removals

| Test Case                      | Before                                | After                              |
| ------------------------------ | ------------------------------------- | ---------------------------------- |
| Solid + Edge, edge collinear   | `[Edge]` with xfail "duplicate edges" | `[Edge]` passing                   |
| Curve + Compound, intersecting | `[Edge, Edge]` with xfail             | `[Edge, Edge, Edge, Edge]` passing |

### Performance tests

#### Summary

| name                                                    |        dev | this branch | commit fa8e936 | this branch / dev | this branch / commit fa8e936 |
| ------------------------------------------------------- | ---------: | ----------: | -------------: | ----------------: | ---------------------------: |
| tests/test_benchmarks.py::test_mesher_benchmark[100]    |     1.5717 |      1.0907 |         1.5013 |            -30.6% |                       -27.3% |
| tests/test_benchmarks.py::test_mesher_benchmark[1000]   |     3.1709 |      2.6054 |         2.9810 |            -17.8% |                       -12.6% |
| tests/test_benchmarks.py::test_mesher_benchmark[10000]  |    18.8172 |     17.9687 |        18.5138 |             -4.5% |                        -2.9% |
| tests/test_benchmarks.py::test_mesher_benchmark[100000] |   272.6479 |    256.7096 |       349.1587 |             -5.8% |                       -26.5% |
| tests/test_benchmarks.py::test_ppp_0101                 | 2,840.2942 |    141.2135 |       146.8151 |            -95.0% |                        -3.8% |
| tests/test_benchmarks.py::test_ppp_0102                 |   183.6392 |    176.0781 |       181.5972 |             -4.1% |                        -3.0% |
| tests/test_benchmarks.py::test_ppp_0103                 |    68.3975 |     66.1329 |        68.0329 |             -3.3% |                        -2.8% |
| tests/test_benchmarks.py::test_ppp_0104                 |   114.2050 |    110.7626 |       113.0657 |             -3.0% |                        -2.0% |
| tests/test_benchmarks.py::test_ppp_0105                 |    83.0605 |     75.6668 |        80.0031 |             -8.9% |                        -5.4% |
| tests/test_benchmarks.py::test_ppp_0106                 | 9,311.8187 |     80.2450 |        82.4856 |            -99.1% |                        -2.7% |
| tests/test_benchmarks.py::test_ppp_0107                 |   308.6340 |    284.8052 |       298.2377 |             -7.7% |                        -4.5% |
| tests/test_benchmarks.py::test_ppp_0108                 |   136.9441 |     65.5078 |        82.4641 |            -52.2% |                       -20.6% |
| tests/test_benchmarks.py::test_ppp_0109                 |   113.9680 |    106.2103 |       128.6220 |             -6.8% |                       -17.4% |
| tests/test_benchmarks.py::test_ppp_0110                 |   244.0596 |    213.4498 |       222.1242 |            -12.5% |                        -3.9% |
| tests/test_benchmarks.py::test_ttt_23_02_02             |   646.0093 |    597.4992 |       631.9749 |             -7.5% |                        -5.5% |
| tests/test_benchmarks.py::test_ttt_23_T_24              |   236.9038 |    141.1910 |       146.1597 |            -40.4% |                        -3.4% |
| tests/test_benchmarks.py::test_ttt_24_SPO_06            |   150.4492 |    137.7853 |       142.6785 |             -8.4% |                        -3.4% |

Note: Changed test_ppp_0109 to use `extrude(UNITL)` instead of `extrude` as in `dev`branch and this PR

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

    ```text
    ----------------------------------------------------------------------------------------- benchmark: 17 tests ------------------------------------------------------------------------------------------
    Name (time in ms)                      Min                 Max                Mean             StdDev              Median                IQR            Outliers       OPS            Rounds  Iterations
    --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    test_mesher_benchmark[100]          1.0508 (1.0)       68.2757 (1.01)       1.8248 (1.0)       5.2479 (9.85)       1.0907 (1.0)       0.0957 (1.0)          1;35  548.0108 (1.0)         165           1
    test_mesher_benchmark[1000]         2.4724 (2.35)      79.2095 (1.17)       3.4835 (1.91)      6.5495 (12.29)      2.6054 (2.39)      0.8534 (8.92)          2;2  287.0715 (0.52)        237           1
    test_mesher_benchmark[10000]       17.3113 (16.48)     88.3289 (1.31)      28.8077 (15.79)    24.4154 (45.82)     17.9687 (16.48)     1.2889 (13.47)        9;10   34.7129 (0.06)         55           1
    test_mesher_benchmark[100000]     248.7809 (236.77)   391.4374 (5.80)     295.5854 (161.98)   62.5995 (117.48)   256.7096 (235.37)   91.1181 (952.56)        1;0    3.3831 (0.01)          5           1
    test_ppp_0101                     140.5867 (133.80)   144.5263 (2.14)     141.7358 (77.67)     1.3575 (2.55)     141.2135 (129.47)    1.3019 (13.61)         1;1    7.0554 (0.01)          7           1
    test_ppp_0102                     175.2740 (166.81)   176.7893 (2.62)     176.0563 (96.48)     0.5328 (1.0)      176.0781 (161.44)    0.5510 (5.76)          2;0    5.6800 (0.01)          6           1
    test_ppp_0103                      65.6279 (62.46)    117.7910 (1.74)      70.3553 (38.56)    13.2053 (24.78)     66.1329 (60.64)     3.0131 (31.50)         1;1   14.2136 (0.03)         15           1
    test_ppp_0104                     109.8469 (104.54)   112.9509 (1.67)     111.0283 (60.84)     0.9951 (1.87)     110.7626 (101.55)    1.2667 (13.24)         3;0    9.0067 (0.02)          9           1
    test_ppp_0105                      74.3809 (70.79)     78.5015 (1.16)      76.0421 (41.67)     1.2363 (2.32)      75.6668 (69.38)     2.2091 (23.09)         6;0   13.1506 (0.02)         14           1
    test_ppp_0106                      79.0039 (75.19)     81.5764 (1.21)      80.3973 (44.06)     0.7688 (1.44)      80.2450 (73.57)     1.1399 (11.92)         5;0   12.4382 (0.02)         13           1
    test_ppp_0107                     281.8502 (268.24)   295.8377 (4.38)     286.5148 (157.01)    5.5815 (10.48)    284.8052 (261.13)    6.6192 (69.20)         1;0    3.4902 (0.01)          5           1
    test_ppp_0108                      63.7172 (60.64)     67.5170 (1.0)       65.4839 (35.89)     1.0336 (1.94)      65.5078 (60.06)     1.3345 (13.95)         5;0   15.2709 (0.03)         15           1
    test_ppp_0109                     105.3235 (100.24)   108.3105 (1.60)     106.3213 (58.27)     0.7871 (1.48)     106.2103 (97.38)     0.5853 (6.12)          2;1    9.4055 (0.02)         10           1
    test_ppp_0110                     211.6483 (201.43)   214.4740 (3.18)     213.1039 (116.78)    1.3020 (2.44)     213.4498 (195.71)    2.4268 (25.37)         2;0    4.6925 (0.01)          5           1
    test_ttt_23_02_02                 592.4995 (563.88)   604.5713 (8.95)     597.9193 (327.67)    4.3216 (8.11)     597.4992 (547.83)    3.8224 (39.96)         2;0    1.6725 (0.00)          5           1
    test_ttt_23_T_24                  139.8359 (133.08)   142.1043 (2.10)     141.0751 (77.31)     0.8109 (1.52)     141.1910 (129.45)    0.7066 (7.39)          2;0    7.0884 (0.01)          5           1
    test_ttt_24_SPO_06                135.6548 (129.10)   144.6452 (2.14)     138.6152 (75.96)     2.9556 (5.55)     137.7853 (126.33)    3.0196 (31.57)         2;1    7.2142 (0.01)          8           1
    --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    ```

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
