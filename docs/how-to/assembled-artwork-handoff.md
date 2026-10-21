# Assembled artwork handoff

Use this workflow to author one image across reading-layout neighbors and retain
individual assets for later physical imposition. `plotter-workflow` exports layout
geometry; `viz_virtualserver` detects transformed adjacency, generates artwork,
and partitions the composition. No plotter connection is used by these commands.

## Export a booklet spread

From an updated plotter-workflow checkout, use its existing Python environment:

```powershell
$python = '.venv/Scripts/python.exe'
& $python scripts/export_artwork_layout.py --layout booklet-spread --sheet-size letter `
  --spread 8 1 --margin-mm 3 --gutter-mm 2 `
  --job-template examples/assembled-artwork/truchet-recipe.json `
  --output-dir output/spread-export
```

Supported facing pairs are 2–3, 4–5, 6–7 and 8–1. In the last pair, page 8 is the
left half and page 1 the right half. The exported `artwork-job.json` uses the
existing producer job schema. `layout-preview.svg` shows the assembled canvases,
crop boxes and labeled corners. It is a diagnostic image, not a plotter input.
The sample recipe is a template; do not run its empty domain list directly.

Geometry uses SVG pixels: **96 / 25.4 units per millimeter**. A physical pen width
of 0.3 mm corresponds to approximately 1.133858 design units at this resolved scale.
Recipe spacing, pen width, and clearance numbers are not automatically converted
from millimeters. Adjust the recipe intentionally for the exported physical size.

## Generate and restore full canvases

Use a producer checkout containing merged PR45 (or newer), and its environment:

```powershell
$vizRepo = 'C:/path/to/viz_virtualserver'
$vizPython = "$vizRepo/.venv/Scripts/python.exe"
$job = (Resolve-Path output/spread-export/artwork-job.json).Path
$producerOutput = "$PWD/output/spread-producer"
Push-Location $vizRepo
& $vizPython -B -m viz_virtualserver.cli.domain_bundle $job --output-dir $producerOutput
Pop-Location

& $python scripts/prepare_layout_assets.py `
  --producer-bundle output/spread-producer `
  --handoff output/spread-export/layout-handoff.json `
  --output-dir output/spread-assets
```

The producer returns each cropped domain rebased to its own origin. Preparation
restores the recorded crop offset inside the full original page canvas. Sparse
and blank pages retain their dimensions; no invisible carrier paths are added.
Crop clipping moves with its strokes, and each logical layer remains a top-level
neutral layer. No spread fit, margin, gutter, or assembled matrix is applied again.

The prepared folder contains surface SVGs, a new hashed `design.json`, exact
`producer-design.json` provenance, `layout-handoff.json`, `asset-preparation.json`,
and `bindings.json`. Original producer files remain untouched. A changed input
hash, mismatched job/layout, foreign surface, or unsupported SVG aborts preparation.
Each output directory requires explicit `--overwrite` to replace its prior export.

## Bind to physical imposition

`bindings.json` is an explicit **partial assignment patch**, not a complete booklet
or Cootie Catcher manifest. Selected booklet pages use `fit: contain`, `margin_mm:0`
and `gutter_mm:0` because the crop was resolved before generation. Existing logical
page-to-sheet rotations still apply once. Do not reuse the original nonzero
margin/gutter settings when imposing these returned single-page assets.

The pure `imposition.artwork_bindings.apply_layout_bindings(manifest, patch)` helper
replaces selected assignments while retaining unrelated ones. It does not write
or validate a complete production manifest. Supply all other pages or slots,
keep paths relative to the intended input directory, and validate the complete
bundle's logical catalog and hashes. Neutral imposition requires **one authoritative
bundle manifest**; this feature does not automatically merge different producer
catalogs or copy unrelated artwork. Do not point a partial prepared bundle at the
imposer and assume its missing assignments have been filled.

Once you have a complete valid bundle and booklet manifest:

```powershell
& $python scripts/booklet_impose.py output/complete-booklet --manifest booklet.json `
  --sheet-size letter --margin-mm 0 --gutter-mm 0 --output output/booklet.imposed.svg
```

Use the existing [booklet reference](../reference/booklet-imposition.md) and
[neutral logical-layer plotting guide](neutral-logical-layer-plotting.md) for
complete-manifest and conversion details. Existing full-source spread imposition
is still supported; this workflow is for separately retained generated page assets.

## Explicit Cootie Catcher folded views

Flat-sheet corner slots do not define the adjoining folded view. Supply a named
profile declaring each outer panel's assembled transform and full intrinsic
canvas. No folded profile is inferred or selected by default.

```powershell
& $python scripts/export_artwork_layout.py --layout cootie-folded-outer `
  --square-size-mm 100 --profile examples/assembled-artwork/illustrative-folded-outer.json `
  --job-template examples/assembled-artwork/truchet-recipe.json `
  --output-dir output/cootie-export
```

The included profile is **illustrative and provisional**, sized for a 100 mm square.
It demonstrates an explicit reflection and adjoining outer panels; it is not a
verified physical fold derivation. For another square size, supply a profile whose
intrinsic canvas dimensions and window match that size. Export rejects mismatched
canonical dimensions. Existing slot reading frames remain provisional where marked.
Profile validation status is a declaration carried into the handoff, not a new
physical verification by the exporter. Review labeled corner/up diagnostics before
relying on a mapping. Physical acceptance remains deferred.

Generate and prepare as above. The patch assigns outer-1 through outer-4 only; the other 16
selector/reveal assignments remain required. Physical slot rotation stays with the
existing Cootie imposer; do not reapply the assembled-view matrix. Neutral Cootie
imposition now preserves channels, vector geometry, local clip references and
source provenance, and rejects mixed neutral/generic/legacy contracts. Existing
generic and strict pen-contract behavior is unchanged.

## Software-only integration check

```powershell
& $python scripts/validate_assembled_artwork.py --viz-repo $vizRepo `
  --viz-python $vizPython --output-dir output/assembled-artwork-validation
```

This opt-in command exports jobs, invokes the producer, restores canvases, validates
layer hashes, and creates imposed booklet and Cootie SVGs. It explicitly fills the
remaining 6 booklet pages and 16 Cootie slots with **blank validation fixtures** to
exercise complete imposition. Those blanks are not user artwork and are never
silently added by export/preparation. `validation.json` records the counts and
provisional profile status; no physical plotting or transmission occurs.

Inspect each case's export preview, producer assembled SVG, restored surfaces and
`sheet.svg`. Keep assembled/reading neighbors distinct from physical print-sheet
neighbors. The producer remains responsible for gaps, shared edges, overlap-copy
policy, outer union clearance and optional internal seam margins.
