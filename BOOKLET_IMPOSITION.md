# One-sheet booklet imposition

`booklet_impose.py` prepares plotter-ready SVG artwork for the single-sheet,
eight-page mini-book / PocketMod-style fold. Imposition belongs in
`plotter-workflow` because it maps logical artwork onto physical media; it does
not generate the artwork itself.

## Physical layout

The v1 `pocketmod8` layout is a landscape sheet divided into four columns and
two rows:

```text
        physical top of sheet

      +-----+-----+-----+-----+
      |  5  |  4  |  3  |  2  |   rotated 180 degrees
      +-----+-----+-----+-----+
      |  6  |  7  |  8  |  1  |   upright
      +-----+-----+-----+-----+
```

The center cut runs along the row boundary from the first internal column fold
to the third internal column fold.

Supported landscape sheets are `letter`, `a4`, `a3`, and `tabloid`.

## Simple eight-file input

Put exactly eight SVG files in a directory. Natural filename order becomes
logical pages 1 through 8:

```text
input/my_book/
  01.svg
  02.svg
  03.svg
  04.svg
  05.svg
  06.svg
  07.svg
  08.svg
```

Run:

```bash
uv run python booklet_impose.py input/my_book \
  --sheet-size letter \
  --guides
```

The default output is:

```text
output/my_book.imposed.svg
output/my_book.imposed.imposition.json
output/my_book.imposed.guides.svg
```

The guide SVG is deliberately separate from the artwork. It contains fold and
cut provenance in one logical `pen-1` layer; it does not force an additional
physical carriage slot into the artwork job.

## Double-wide spreads

Use a manifest when one SVG represents two facing logical pages. A spread is
fitted once as a double-width canvas and is then cropped into its left and
right logical pages. The two halves therefore share one scale and center.

`input/my_book/booklet.json`:

```json
{
  "schema_version": 1,
  "layout": "pocketmod8",
  "pages": [
    {"page": 1, "source": "01-cover.svg"},
    {"spread": [2, 3], "source": "02-03-map.svg", "fit": "cover"},
    {"spread": [4, 5], "source": "04-05.svg"},
    {"page": 6, "source": "06.svg"},
    {"page": 7, "source": "07.svg"},
    {"page": 8, "source": "08-back.svg"}
  ]
}
```

Facing spreads supported by this fold are `2-3`, `4-5`, `6-7`, and `8-1`.
For `8-1`, page 8 is the logical left half (back cover) and page 1 is the
logical right half (front cover).

Per-entry overrides:

- `fit`: `contain` or `cover`;
- `margin_mm`: page/spread outer margin;
- `gutter_mm`: optional center crop gap for spreads only.

The manifest must account for logical pages 1 through 8 exactly once.

## Vector and pen-layer behavior

Raster images and live SVG text are intentionally rejected. Convert raster
artwork to vector linework and text to paths before imposition.

A booklet may use either:

1. **generic SVG sources** — all source geometry is flattened to one logical
   output layer; or
2. **strict `pen-N` contract SVG sources** — logical pen IDs and
   `data-generation` provenance are retained through the imposed output.

Do not mix generic and strict contract sources in one v1 booklet. Keeping the
modes homogeneous prevents a generic page from silently acquiring a physical
pen assignment.

## Physical-layout contract with the converter

The imposed SVG has this root metadata:

```xml
data-plotter-workflow-layout="preserve"
data-plotter-workflow-page-size="letter"
data-plotter-workflow-orientation="landscape"
```

`dpx3300_convert.py` recognizes that marker, verifies that `--page-size` and
`--landscape` agree with the imposed sheet metadata, and skips its normal vpype
`layout` fit/centering and HP-GL writer centering. Those operations are correct for a
normal drawing, but they would destroy the already-established fold-cell
coordinates of an imposed sheet.

The conversion workflow is otherwise unchanged. For a Letter sheet at the
lower-left ANSI-D position:

```bash
uv run python dpx3300_convert.py \
  --input-dir ./output \
  --output-dir ./output \
  --file my_book.imposed.svg \
  --page-size letter \
  --landscape \
  --paper-position lower-left \
  --margin 4mm \
  --absolute \
  --overwrite
```

For preserved-layout SVGs, `--margin` is no longer a scaling instruction. In a
repository with HP-GL placement validation integrated, it remains the required
post-conversion safety envelope for actual pen-down coordinates.

Then use the normal pen-plan, placement, unified preflight, and send workflow.

If the optional guide SVG is converted for plotting, convert it as a separate
job. Its fold lines intentionally reach the sheet boundary, so use `--margin 0mm`
for placement validation and review that guide job independently before sending.

## Audit sidecar

Every imposed sheet writes `<stem>.imposition.json`. The sidecar records stable,
semantic facts rather than generated SVG bytes:

- layout and physical sheet dimensions;
- generic versus strict pen-contract source mode;
- logical page to physical row/column/rotation mapping;
- source file and spread half for each page;
- fit, margin, and gutter settings; and
- the preserved-layout converter contract.

This is the right level for a golden regression fixture: page mapping and
orientation should remain stable even if vpype's path serialization changes.

A physical validation source set is checked in under
`tests/fixtures/imposition/pocketmod8/validation_pages/`. See the adjacent
`VALIDATION.md` for the sacrificial-paper plot, cut, fold, and page-order check.
