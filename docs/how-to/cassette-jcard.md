# Generate and plot a cassette J-card

Run plotter commands from the plotter-workflow checkout. Use its Python environment.
Run generator commands from a current viz_virtualserver checkout with its own
Python environment. In the commands below, `python` means the Python for the
repository in which the command runs. Replace the absolute example path
`C:/art/jcard` with your selected output directory.

## Save complete recipes and configuration

Save each recipe next to the configuration. The front recipe draws curves; the
back recipe adds hatching. The two faces retain separate logical layer catalogs.
These recipes can also be used with either face alone.

Save as `front-recipe.json`:

```json
{
  "domains": [],
  "passes": [
    {
      "algorithm": "truchet",
      "id": "tiles",
      "logical_layers": [
        {
          "id": "curve"
        },
        {
          "id": "fill"
        }
      ],
      "parameters": {
        "curve_layer_ids": [
          "curve"
        ],
        "region_fills": {},
        "tile_size": 48.0
      },
      "target_domain_ids": []
    }
  ],
  "schema_version": 1,
  "seed": 31
}
```

Save as `back-recipe.json`:

```json
{
  "domains": [],
  "passes": [
    {
      "algorithm": "truchet",
      "id": "tiles",
      "logical_layers": [
        {
          "id": "curve"
        },
        {
          "id": "fill"
        }
      ],
      "parameters": {
        "curve_layer_ids": [
          "curve"
        ],
        "region_fills": {
          "painted": {
            "effect": "parallel-hatch",
            "layer_id": "fill",
            "parameters": {
              "spacing": 12.0
            }
          }
        },
        "tile_size": 64.0
      },
      "target_domain_ids": []
    }
  ],
  "schema_version": 1,
  "seed": 67
}
```

### Front selection

Save as `front.json`:

```json
{
  "faces": "front",
  "flip": "left-right",
  "front_artwork": {
    "blank_panels": [
      "front-panel-2"
    ],
    "mode": "continuous",
    "template": "front-recipe.json"
  },
  "guides": {
    "cut": false,
    "fold": false,
    "registration": false
  },
  "margin_mm": 3,
  "profile": "nac-jcard-8-panel-v1",
  "safe_inset_mm": 1.5875,
  "schema_version": 1,
  "sheet": "a3"
}
```

### Back selection

Save as `back.json`:

```json
{
  "back_artwork": {
    "blank_panels": [],
    "mode": "independent",
    "template": "back-recipe.json"
  },
  "faces": "back",
  "flip": "left-right",
  "guides": {
    "cut": false,
    "fold": false,
    "registration": false
  },
  "margin_mm": 3,
  "profile": "nac-jcard-8-panel-v1",
  "safe_inset_mm": 1.5875,
  "schema_version": 1,
  "sheet": "a3"
}
```

### Both selection

Save as `both.json`:

```json
{
  "back_artwork": {
    "blank_panels": [],
    "mode": "independent",
    "template": "back-recipe.json"
  },
  "faces": "both",
  "flip": "left-right",
  "front_artwork": {
    "blank_panels": [
      "front-panel-2"
    ],
    "mode": "continuous",
    "template": "front-recipe.json"
  },
  "guides": {
    "cut": false,
    "fold": false,
    "registration": false
  },
  "margin_mm": 3,
  "profile": "nac-jcard-8-panel-v1",
  "safe_inset_mm": 1.5875,
  "schema_version": 1,
  "sheet": "a3"
}
```

The front example deliberately leaves the title/spine artwork blank. Its source
panel is still generated and validated. Remove `front-panel-2` from `blank_panels`
to draw there. Do not assign artwork to a face that is not selected.

For tabloid paper, set `"sheet": "tabloid"`. To compare flips with an off-center
custom sheet, replace the sheet setting and add these complete controls:

```json
{
  "sheet": {"width_mm": 500.0, "height_mm": 250.0},
  "origin_mm": [20.0, 30.0],
  "flip": "top-bottom",
  "guides": {"cut": true, "fold": true, "registration": true}
}
```

This block replaces the corresponding controls in a full config; it is not a
standalone config. All guide channels become plotted ink. Set their flags to
`false` to omit them. The fixed safe inset is diagnostic and does not crop art.

## Export face requests

In plotter-workflow, after saving the files above in your working directory:

```powershell
python scripts/export_jcard_layout.py --config both.json --output-dir C:/art/jcard/export
```

Inspect `front/layout-preview.svg` and `back/layout-preview.svg`. Check the native
panel order and which face uses continuous artwork. Inspect each face's
`sheet-preview.svg` for placement, flip, safe guides and enabled registration
marks. This diagnostic includes text and is not a plot input. The exporter does not launch
the generator. For a single face, use `front.json` or `back.json` and run only the
corresponding steps below.

## Generate artwork

From viz_virtualserver:

```powershell
python -m viz_virtualserver.cli.domain_bundle C:/art/jcard/export/front/artwork-job.json --output-dir C:/art/jcard/front-producer
python -m viz_virtualserver.cli.domain_bundle C:/art/jcard/export/back/artwork-job.json --output-dir C:/art/jcard/back-producer
```

Use the exported job files without editing them. If you change a recipe, export
and generate again. Restoration checks that the producer matches the request.

## Restore canvases and impose

Back in plotter-workflow:

```powershell
python scripts/prepare_layout_assets.py --producer-bundle C:/art/jcard/front-producer --handoff C:/art/jcard/export/front/layout-handoff.json --output-dir C:/art/jcard/front-assets
python scripts/prepare_layout_assets.py --producer-bundle C:/art/jcard/back-producer --handoff C:/art/jcard/export/back/layout-handoff.json --output-dir C:/art/jcard/back-assets
python scripts/jcard_impose.py --config both.json --front-assets C:/art/jcard/front-assets --back-assets C:/art/jcard/back-assets --output-dir C:/art/jcard/jobs
```

For front only, omit `--back-assets` and use `front.json`. For back only, omit
`--front-assets` and use `back.json`. Inactive asset arguments fail validation.
No opposite-face assets or empty second job are needed.

The final inputs are `jobs/front/design.svg` and `jobs/back/design.svg`.
`jobs/jcard-jobs.json` records the pair, hashes, flip and front-reference placement.
Each face also has `design.json` with its catalog and source provenance. Artwork
must remain beside `design.imposition.json`, which the converter requires. Keep
all three files together. For custom sheets, configure a matching converter/device
paper profile; J-card imposition does not create hardware paper profiles. Artwork
keeps its physical size even when sparse or completely blank. Do not apply a
fit-to-content operation in Inkscape or the plot conversion pipeline.

## Inspect and plot

1. Inspect both SVGs at the configured sheet size. Confirm front/back orientation,
   panel order, blank panels, and any guide ink.
2. Check each face's logical layer catalog. Apply your pen plan separately to each
   face. The examples use `curve` and `fill`; enabled guide channels need their own
   explicit pen-plan decisions. Use the existing conversion and plot workflow with
   its preserved-layout setting. These commands do not create or transmit HPGL.
3. Plot the first SVG as one complete job. Wait for completed state and idle the
   drawing arm before handling the sheet.
4. Flip the paper using the configured left-right or top-bottom convention. Align
   it to the same physical registration datum. Use a paper proof to confirm the
   flip and marks before producing final stock.
5. Start the other SVG as a new job. A mid-job pause is not required. This feature
   does not automatically start the second job.
6. Cut and fold a paper proof. Check the stock thickness, inward extensions, and
   cassette-case fit. Software checks do not prove these physical properties.

## Invalid configurations

- `"sheet": "a4"` or `"sheet": "letter"`: the 406.4 mm trim does not fit.
- Front artwork with `"blank_panels": ["back-panel-1"]`: wrong face slot.
- `"origin_mm": null`: omit the field to center instead.
- `"safe_inset_mm": 6.35`: the inset collapses the title/spine safe area.
- Enabled registration crosses outside the drawable margin: increase sheet space
  or choose a valid explicit origin; the program will not move the marks.

All eight source files are required even when panels are blank. Missing or edited
source files, stale recipes, and swapped front/back bundles fail validation before
publication. To replace a complete recognized output, add `--overwrite`. A failed
second face preserves the previous complete pair.

See the [parameter and dimension reference](../reference/cassette-jcard.md) for
exact geometry, transformations, guide channels and vendor source hashes.
