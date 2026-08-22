# Cootie-catcher fortune-teller imposition

`cootie_impose.py` prepares plotter-ready SVG artwork for a one-sheet origami
fortune teller / cootie catcher. Imposition belongs in `plotter-workflow`
because it maps logical artwork onto physical media; it does not generate the
artwork itself.

The construction target is the familiar two-stage corner-to-center fortune
teller described by resources such as the WikiHow construction guide:

<https://www.wikihow.com/Make-a-Cootie-Catcher-(Origami-Fortune-Teller)>

The v1 implementation intentionally stands beside `booklet_impose.py` rather
than refactoring both algorithms into a shared framework. The PocketMod path is
already physically validated; a second implementation gives us evidence about
which imposition concepts are genuinely reusable before we extract common code.

## Development verification

From the repository root:

```bash
uv sync
uv run python -m pytest -v
```

Use `python -m pytest` from the repository root, matching the existing
PocketMod development workflow.

## Semantic panel model

A cootie catcher has 20 logical artwork addresses:

- `outer-1` through `outer-4`: the four outer choices;
- `selector-1` through `selector-8`: the eight intermediate choices; and
- `reveal-1` through `reveal-8`: the eight hidden outcomes.

The names describe interaction roles rather than prescribing content. An
`outer` panel does not have to contain a color, a `selector` does not have to
contain a number, and a `reveal` does not have to contain a written fortune.

`selector-N` is paired with `reveal-N` as a semantic invariant.

## Normalized square geometry

Let the origami square have side length `S`, with normalized coordinates from
0 to 1 and an SVG-like origin at the physical top-left. Define:

```text
q = 1/4
c = 1/2
```

All panel vertices occur at `0`, `q`, `c`, `3q`, or `1`.

The four outer squares are:

```text
outer-1  north-west
outer-2  north-east
outer-3  south-east
outer-4  south-west
```

The selectors are numbered clockwise, beginning with the north-west half of the
top selector band:

```text
                    physical top

                 selector-1  selector-2

        outer-1                           outer-2

 selector-8                                 selector-3
 selector-7        central reveals          selector-4

        outer-4                           outer-3

                 selector-6  selector-5
```

The eight reveal triangles fill the central first-blintz diamond. Each reveal shares the diagonal boundary of its paired selector:

```text
                 reveal-1   reveal-2

        reveal-8       \   /       reveal-3
                        \ /
                         +
                        / \
        reveal-7       /   \       reveal-4

                 reveal-6   reveal-5
```

The exact normalized vertices are code-level invariants in
`COOTIE_PANEL_POLYGONS` and are duplicated in the semantic golden fixture at
`tests/fixtures/imposition/cootie_catcher/expected.json`.

The 20 semantic panels partition the entire square: 25% outer panels, 25%
selector panels, and 50% reveal panels. The reveal regions are larger than the
selector triangles because they span from each selector diagonal to the center
of the sheet.

## Orientation status

The initial `COOTIE_PANEL_ROTATIONS` table is **provisional**. This is different
from the physically validated PocketMod orientation table.

The first implementation uses a deterministic radial convention:

```text
north-facing slots   0 degrees
right-facing slots  90 degrees
south-facing slots 180 degrees
left-facing slots  270 degrees
```

The four outer squares use the same clockwise progression from `outer-1` to
`outer-4`.

Every imposed SVG, audit sidecar, and golden fixture records:

```text
orientation_validation = provisional
```

Do not change that status merely because the software tests pass. Use the
asymmetric physical fixture described below, plot it, fold it, and then update
the orientation table based on observed folded behavior.

A manifest entry may temporarily override `rotation_degrees` in multiples of 90
to experiment without changing the default table.


### Intrinsic source orientation frames

Source orientation is independent of the slot polygon. The v1 intrinsic-canvas
contract identifies a semantic geometric anchor and a normalized direction:

```xml
data-viz-canvas-up-anchor="vertex:0"
data-viz-canvas-up-vector="0,-1"
```

`data-viz-canvas-up-anchor` accepts `vertex:N` or `edge:N`. The anchor records
which feature of the intrinsic source geometry carries the semantic orientation;
`data-viz-canvas-up-vector` records the direction that source considers "up" in
SVG y-down coordinates. The vector is not restricted to the four cardinal axes.

For example, a square whose north-west corner is semantic top may declare:

```xml
data-viz-canvas-up-anchor="vertex:0"
data-viz-canvas-up-vector="-0.7071067811865476,-0.7071067811865476"
```

When imposed into a slot whose target up-vector is `(0,-1)`, this resolves to a
45-degree clockwise rotation. The polygon itself remains an ordinary square.

Likewise, an isosceles-triangle source may use a side as its semantic reference
and orient the triangle laterally:

```xml
data-viz-canvas-up-anchor="edge:1"
data-viz-canvas-up-vector="1,0"
```

Against a `(0,-1)` target this resolves to 270 degrees clockwise, giving a
triangle with one corner up, one corner down, and the remaining corner lateral.
This does not require a different triangle polygon or a per-slot rotation hack.

The richer internal `OrientationFrame` may also carry a secondary right-vector
for handedness/reflection validation. The SVG v1 contract does not yet serialize
that secondary axis; add it only when a concrete producer/consumer requirement
needs reflection to be represented explicitly in source metadata.

## Manifest input

V1 uses an explicit manifest as the canonical input interface. This avoids
silently assigning 20 differently shaped regions based on filenames alone.

Create `input/my_catcher/cootie.json`:

```json
{
  "schema_version": 1,
  "layout": "cootie_catcher",
  "panels": [
    {"slot": "outer-1", "source": "outer-blue.svg"},
    {"slot": "outer-2", "source": "outer-green.svg"},
    {"slot": "outer-3", "source": "outer-red.svg"},
    {"slot": "outer-4", "source": "outer-yellow.svg"},

    {"slot": "selector-1", "source": "selector-1.svg"},
    {"slot": "selector-2", "source": "selector-2.svg"},
    {"slot": "selector-3", "source": "selector-3.svg"},
    {"slot": "selector-4", "source": "selector-4.svg"},
    {"slot": "selector-5", "source": "selector-5.svg"},
    {"slot": "selector-6", "source": "selector-6.svg"},
    {"slot": "selector-7", "source": "selector-7.svg"},
    {"slot": "selector-8", "source": "selector-8.svg"},

    {"slot": "reveal-1", "source": "reveal-1.svg"},
    {"slot": "reveal-2", "source": "reveal-2.svg"},
    {"slot": "reveal-3", "source": "reveal-3.svg"},
    {"slot": "reveal-4", "source": "reveal-4.svg"},
    {"slot": "reveal-5", "source": "reveal-5.svg"},
    {"slot": "reveal-6", "source": "reveal-6.svg"},
    {"slot": "reveal-7", "source": "reveal-7.svg"},
    {"slot": "reveal-8", "source": "reveal-8.svg"}
  ]
}
```

All 20 slots are required exactly once. Sources must remain inside the input
directory.

Per-panel overrides are:

- `fit`: `contain` or `cover`;
- `margin_mm`: inset from the panel boundary; and
- `rotation_degrees`: an experimental multiple-of-90 rotation override.

## Vector and pen-layer behavior

Raster images, live SVG text, `<use>`, and `<foreignObject>` are intentionally
rejected. Convert the artwork to explicit plotter-ready vector paths before
imposition.

As with PocketMod, a single cootie-catcher job may use either:

1. **generic SVG sources** — all source geometry is flattened into one logical
   output layer; or
2. **strict `pen-N` contract sources** — logical pen IDs, preview stroke
   metadata, declared generations, and `data-generation` provenance are
   retained.

Do not mix generic and strict contract sources in one v1 job. Physical carriage
assignment remains a downstream pen-plan concern; imposition does not invent or
compact physical DPX-3300 slots.

## Triangular fit and clipping

`contain` and `cover` are defined for arbitrary convex panel polygons.

For `contain`, the source SVG's full page canvas is rotated, scaled to the
largest centered rectangle of the same aspect ratio that fits inside the inset
panel polygon, and then polygon-clipped for numerical safety.

For `cover`, the rotated source canvas is scaled to cover the inset polygon's
bounding box, centered on that box, and clipped to the polygon.

The clipper operates on vpype's piecewise-linear paths one segment at a time
against the convex polygon half-planes. This keeps the implementation
deterministic and avoids adding a new repository dependency solely for triangle
clipping.

The default panel margin is 3 mm. Very large margins are rejected when they
collapse a panel's drawable polygon.

## Physical sheet and square placement

Supported landscape sheets match the PocketMod implementation:

```text
letter    279.4 x 215.9 mm
a4        297.0 x 210.0 mm
a3        420.0 x 297.0 mm
tabloid   431.8 x 279.4 mm
```

By default the square is the largest square that fits the sheet height and is
aligned left:

```bash
uv run python cootie_impose.py input/my_catcher \
  --sheet-size letter \
  --square-position left \
  --guides
```

For Letter this yields a 215.9 x 215.9 mm square at the left side of the sheet
and a 63.5 mm remainder strip. The guide therefore contains one vertical trim
line.

`--square-position` also accepts `center` and `right`. `--square-size-mm` may be
used for a smaller custom square; a smaller square is vertically centered on
the physical sheet. The guide emits every square edge that then requires a trim
cut.

## Outputs

The default output set is:

```text
output/my_catcher.imposed.svg
output/my_catcher.imposed.imposition.json
output/my_catcher.imposed.guides.svg    # only with --guides
```

The production artwork and construction guide remain separate jobs.

The imposed SVG declares the same physical-layout preservation contract used by
PocketMod:

```xml
data-plotter-workflow-layout="preserve"
data-plotter-workflow-page-size="letter"
data-plotter-workflow-orientation="landscape"
```

It additionally records:

```xml
data-imposition-layout="cootie_catcher"
data-imposition-square-size-mm="215.9"
data-imposition-square-position="left"
data-imposition-orientation-validation="provisional"
```

`dpx3300_convert.py` therefore does not need a new cootie-catcher-specific code
path. Its existing preserved-layout behavior keeps the established physical
coordinates instead of fitting and centering the imposed SVG again.

## Construction guide

The optional guide SVG uses one strict logical `pen-1` layer and four semantic
subgroups identified with `data-guide-kind`:

- `trim` — edges that must be cut to obtain the square;
- `first-blintz` — the diamond formed by folding the original square corners to
  the center;
- `second-blintz` — the central square used by the second corner-to-center fold;
- `center-prefold` — both full diagonals plus the horizontal and vertical center
  folds.

The guide is not merged into production artwork, so construction marks cannot
silently acquire a production physical carriage assignment.

If the guide is plotted, convert and preflight it as a separate job. Because
trim and prefold lines may reach physical paper edges, review placement/margins
for the guide independently of the artwork job.

## Audit sidecar

`<stem>.imposition.json` records semantic facts rather than serialized SVG
bytes:

- layout and orientation-validation status;
- physical sheet dimensions;
- square size and placement;
- generic versus strict source mode;
- vpype curve quantization;
- all 20 slot polygons, sources, fit modes, margins, and rotations;
- selector/reveal pairing; and
- the preserved-layout converter contract.

This is the intended regression level. Do not pin vpype path serialization or
generated HP-GL bytes as the imposition oracle.

## Physical golden validation

The fixture is under:

```text
tests/fixtures/imposition/cootie_catcher/
  cootie.json
  expected.json
  VALIDATION.md
  validation_panels/
```

Each validation panel is vector-only and deliberately asymmetric. Use it to
check slot assignment, folded orientation, reflection, and all eight
selector/reveal pairings.

Generate it with:

```bash
uv run python cootie_impose.py \
  tests/fixtures/imposition/cootie_catcher \
  --manifest cootie.json \
  --sheet-size letter \
  --guides \
  --output output/cootie_validation.imposed.svg \
  --overwrite
```

Review the flat imposed SVG first. Then use the normal conversion and unified
preflight workflow for a sacrificial-paper plot. Plot the guide separately if
needed. Cut and fold the square, record the observed orientations, and only
then promote the rotation table from `provisional` to a physically validated
state.

## End-to-end production path

After the orientation table has been physically validated, a normal production
job follows the same downstream path as PocketMod:

```bash
uv run python cootie_impose.py input/my_catcher \
  --sheet-size letter \
  --square-position left \
  --guides \
  --overwrite

uv run python dpx3300_convert.py \
  --input-dir ./output \
  --output-dir ./output \
  --file my_catcher.imposed.svg \
  --page-size letter \
  --landscape \
  --paper-position lower-left \
  --margin 4mm \
  --absolute \
  --overwrite

uv run python job_preflight.py output/my_catcher.imposed.hpgl
```

For a multi-pen job, physically verify the carriage against the resolved pen
plan before using the normal confirmation/send procedure. Imposition changes
logical placement on the sheet; it does not relax any existing converter,
pen-plan, placement, preflight, or hardware-send contract.
