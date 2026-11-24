# Corner placement and packed kaleidocycles

Kaleidocycles now use the same exact-scale packing workflow as J-cards. Blank
glue tabs are included in every reserved footprint, even when guides are off.
The packer starts at the upper-left of the effective usable area and preserves
the configured gutters. It reserves rectangles; it does not interlock nets.

## Reproduce the Letter proofs

Activate the existing Python environment so `vpype` is on PATH, then run:

```powershell
$python = '.venv/Scripts/python.exe'
# In a linked worktree, the existing environment may be ../../.venv/Scripts/python.exe.
& $python scripts/generate_kaleidocycle_packing_samples.py
```

The script uses the committed `examples/kaleidocycle/letter-1-up.json` through
`letter-3-up.json`, generates deterministic vector diagnostic assets at the
matching physical widths, and packs the three jobs through the production
adapter. No external artwork service or plotter connection is needed for
these diagnostic examples. Existing outputs require explicit `--overwrite`.

| Copies on Letter landscape | Net size each, including tabs | Scale vs. 240 mm net |
| --- | --- | --- |
| 1 | 269.40 x 82.3853 mm | 112.25% |
| 2 | 269.40 x 82.3853 mm | 112.25% |
| 3 | 213.531 x 65.30 mm | 88.97125% |

These rectangular layouts use 5 mm margins on all sides and 5 mm gutters.
The one/two-copy layouts are limited by the 269.4 mm usable width. Three rows
are limited by `(205.9 - 2*5)/3 = 65.3 mm` height, with width `65.3*3.27`.
The examples select 0-degree rotation; the adapter also supports 90 degrees.
The packer does not calculate these scales automatically or shrink a net to fit.

Default output: `output/hardware-acceptance/kaleidocycle-letter-packing/`.
Each `letter-N-up/` contains `packing.json`, `placement-preview.svg`, and
`sheet-001/front/design.svg` plus neutral inventory and imposition audit.
`design.penplan.json` assigns artwork and cut/fold guides to one intended marking
pen in physical slot 1. It does not command a cutting/scoring tool or prescribe
force. Reference views and observation templates are retained in the generated
`full-size/` and `three-up/` fixture folders.

Convert and preflight the examples (no sending):

```powershell
$root = 'output/hardware-acceptance/kaleidocycle-letter-packing'
foreach ($copies in @(1, 2, 3)) {
  $folder = "$root/letter-$copies-up/sheet-001/front"
  & $python scripts/dpx3300_convert.py --input-dir $folder --output-dir $folder `
    --file design.svg --page-size letter --landscape --paper-position lower-left `
    --margin 5mm --absolute
  & $python scripts/job_preflight.py "$folder/design.proof.hpgl" --write-report
}
```

Stop if a command fails. The explicit 5 mm conversion margin must match the
layout; the converter's default 10 mm margin would correctly reject these jobs.
Inspect paper placement and the actual loaded pen before an attended send.

## Use generated viz artwork

Export each A-D viewing state at the chosen `width_mm` and `tetrahedron_count`, generate its artwork,
and restore it using the existing [kaleidocycle workflow](kaleidocycle.md).
Then point a packing config's `states` at those four prepared directories.
Use a common logical-layer catalog or provide an explicit output catalog and
complete `layer_map`, as described in the [packing reference](../reference/sheet-packing.md).

Minimal kaleidocycle object entry:

```json
{
  "id": "ring",
  "type": "kaleidocycle",
  "tetrahedron_count": 8,
  "quantity": 2,
  "width_mm": 269.4,
  "rotations": [0],
  "guides": {"cut": true, "fold": true},
  "states": {
    "A": "A/assets", "B": "B/assets", "C": "C/assets", "D": "D/assets"
  }
}
```

Supply that entry inside the standard schema-1 sheet-packing config. Asset paths
are resolved relative to that config. For an existing committed example after
default sample preparation, run:

```powershell
& $python scripts/pack_impositions.py --config examples/kaleidocycle/letter-2-up.json `
  --output-dir output/packed-kaleidocycle
```

Count defaults to six when omitted. The committed 1/2/3-up examples explicitly
use eight to preserve their dimensions and sheet counts. Changing count changes
the net aspect ratio; packing uses the resulting full footprint, including tabs,
without scaling it to fit.

All source handoffs must match `width_mm` and `tetrahedron_count`; re-export and prepare when changing
size. Output must not overlap source state bundles. Catalogs, source hashes,
panel provenance and unique instance/path IDs are preserved. The new object
supports front-only jobs and cut/fold guides; J-card duplex controls and
registration marks are rejected. More copies can spill onto additional sheets.

## Single-copy corner placement

The existing `scripts/kaleidocycle_impose.py` config now accepts
`"position": "top-left"`. The net starts at `(margin_mm, margin_mm)`, with
5 mm as the default margin. Omit `position` or use `"center"` for existing
centered behavior. This does not resize or recompose artwork.

HAR-180 implements software placement and packing. Folded viewing profiles
remain provisional: packed copies do not establish physical orientation or
seam continuity. Physical inspection remains separate from software checks.
