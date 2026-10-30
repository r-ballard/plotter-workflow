# Pack several J-cards on a sheet

This complete example makes two eight-panel cards on one landscape A3 sheet.
A second configuration mixes one eight-panel card and five three-panel cards
across two sheets. Both examples keep exact physical size and produce separate
front/back jobs. Run generation in viz_virtualserver and all other commands in
plotter-workflow. Use each repository's installed Python environment.

## Save the source recipes

Create `examples/sheet-packing/` in plotter-workflow. Save each JSON below under
the stated filename. The files are also tracked at those paths. The front, back
and alternate front use different deterministic seeds. `region_fills: {}` means
no region fills; the J-card handoff requires this field even when it is empty.

### front-recipe.json

```json
{
  "schema_version": 1,
  "seed": 31,
  "domains": [],
  "passes": [
    {
      "id": "tiles",
      "algorithm": "truchet",
      "target_domain_ids": [],
      "parameters": {
        "curve_layer_ids": [
          "curve"
        ],
        "tile_size": 80,
        "region_fills": {}
      },
      "logical_layers": [
        {
          "id": "curve"
        }
      ]
    }
  ]
}
```

### back-recipe.json

```json
{
  "schema_version": 1,
  "seed": 73,
  "domains": [],
  "passes": [
    {
      "id": "tiles",
      "algorithm": "truchet",
      "target_domain_ids": [],
      "parameters": {
        "curve_layer_ids": [
          "curve"
        ],
        "tile_size": 64,
        "region_fills": {}
      },
      "logical_layers": [
        {
          "id": "curve"
        }
      ]
    }
  ]
}
```

### front-alt-recipe.json

```json
{
  "schema_version": 1,
  "seed": 97,
  "domains": [],
  "passes": [
    {
      "id": "tiles",
      "algorithm": "truchet",
      "target_domain_ids": [],
      "parameters": {
        "curve_layer_ids": [
          "curve"
        ],
        "tile_size": 56,
        "region_fills": {}
      },
      "logical_layers": [
        {
          "id": "curve"
        }
      ]
    }
  ]
}
```

## Export native layouts

Save these two complete preparation configurations in the same directory.
`continuous` creates a native canvas across each card's facets. Packing also
accepts `independent` assets, prepared with that mode. Native export has a sheet
preview, but its single-card sheet placement does not control final packing.

### prepare-eight.json

```json
{
  "schema_version": 1,
  "profile": "standard-jcard-8-panel-v1",
  "faces": "both",
  "sheet": "a3",
  "margin_mm": 3,
  "guides": {
    "cut": true,
    "fold": true,
    "registration": true
  },
  "front_artwork": {
    "template": "front-recipe.json",
    "mode": "continuous"
  },
  "back_artwork": {
    "template": "back-recipe.json",
    "mode": "continuous"
  }
}
```

### prepare-three.json

```json
{
  "schema_version": 1,
  "profile": "standard-jcard-3-panel-v1",
  "faces": "both",
  "sheet": "a3",
  "margin_mm": 3,
  "guides": {
    "cut": true,
    "fold": true,
    "registration": true
  },
  "front_artwork": {
    "template": "front-alt-recipe.json",
    "mode": "continuous"
  },
  "back_artwork": {
    "template": "back-recipe.json",
    "mode": "continuous"
  }
}
```

From plotter-workflow, export both layouts:

```powershell
python scripts/export_jcard_layout.py --config examples/sheet-packing/prepare-eight.json --output-dir output/sheet-packing-production/export-eight
python scripts/export_jcard_layout.py --config examples/sheet-packing/prepare-three.json --output-dir output/sheet-packing-production/export-three
$PackingRoot = (Resolve-Path output/sheet-packing-production).Path
```

Keep the absolute value of `$PackingRoot` when you switch to viz_virtualserver.
The following loop runs there. If you use another shell/session, set
`$PackingRoot` to the absolute output path printed by the export commands.

```powershell
foreach ($Size in @('eight','three')) {
    foreach ($Face in @('front','back')) {
        python -m viz_virtualserver.cli.domain_bundle "$PackingRoot/export-$Size/$Face/artwork-job.json" --output-dir "$PackingRoot/producer-$Size/$Face"
        if ($LASTEXITCODE -ne 0) { throw 'Artwork generation failed' }
    }
}
```

Return to plotter-workflow. Restore each producer bundle to its native canvas:

```powershell
foreach ($Size in @('eight','three')) {
    foreach ($Face in @('front','back')) {
        python scripts/prepare_layout_assets.py --producer-bundle "output/sheet-packing-production/producer-$Size/$Face" --handoff "output/sheet-packing-production/export-$Size/$Face/layout-handoff.json" --output-dir "output/sheet-packing-production/prepared-$Size/$Face"
        if ($LASTEXITCODE -ne 0) { throw 'Asset preparation failed' }
    }
}
```

## Pack two eight-panel cards

Save as `examples/sheet-packing/two-eight-panel.json`. Asset and recipe paths
are relative to this file. Each `quantity` copy reuses its selected native art.
To use different art on two cards, prepare separate recipes/assets, then use two
object definitions with different IDs and `quantity: 1`.

```json
{
  "schema_version": 1,
  "sheet_mm": [
    420,
    297
  ],
  "usable_front_mm": [
    0,
    0,
    420,
    297
  ],
  "usable_back_mm": [
    0,
    0,
    420,
    297
  ],
  "margins_mm": [
    3,
    3,
    3,
    3
  ],
  "gutter_mm": 4,
  "strategy": "auto",
  "faces": "both",
  "flip": "left-right",
  "objects": [
    {
      "id": "album",
      "type": "jcard",
      "profile": "standard-jcard-8-panel-v1",
      "quantity": 2,
      "rotations": [
        0,
        90
      ],
      "guides": {
        "cut": true,
        "fold": true,
        "registration": true
      },
      "front": {
        "assets": "../../output/sheet-packing-production/prepared-eight/front",
        "template": "front-recipe.json",
        "mode": "continuous"
      },
      "back": {
        "assets": "../../output/sheet-packing-production/prepared-eight/back",
        "template": "back-recipe.json",
        "mode": "continuous"
      }
    }
  ]
}
```

```powershell
python scripts/pack_impositions.py --config examples/sheet-packing/two-eight-panel.json --output-dir output/sheet-packing-production/two-eight-panel
```

The resolved strategy is `grid`, with two cards on one sheet. Open
`output/sheet-packing-production/two-eight-panel/placement-preview.svg` to inspect
the reserved rectangles. Open `sheet-001/front/design.svg` and
`sheet-001/back/design.svg` beneath that directory to inspect actual artwork.
These two SVGs are separate plot inputs. Do not plot the placement preview.

## Mix profiles and artwork

Save this complete configuration as `examples/sheet-packing/mixed.json`.
The three-panel front uses the alternate seed and tile size. Explicit maps merge
the source `curve` layers into the output `art` layer. The result uses MaxRects
and two A3 sheets. This is a repeatable heuristic result, not an optimality claim.

```json
{
  "schema_version": 1,
  "sheet_mm": [
    420,
    297
  ],
  "usable_front_mm": [
    0,
    0,
    420,
    297
  ],
  "usable_back_mm": [
    0,
    0,
    420,
    297
  ],
  "margins_mm": [
    3,
    3,
    3,
    3
  ],
  "gutter_mm": 4,
  "strategy": "auto",
  "faces": "both",
  "flip": "left-right",
  "objects": [
    {
      "id": "long",
      "type": "jcard",
      "profile": "standard-jcard-8-panel-v1",
      "quantity": 1,
      "rotations": [
        0,
        90
      ],
      "guides": {
        "cut": true,
        "fold": true,
        "registration": true
      },
      "front": {
        "assets": "../../output/sheet-packing-production/prepared-eight/front",
        "template": "front-recipe.json",
        "mode": "continuous",
        "layer_map": {
          "curve": "art"
        }
      },
      "back": {
        "assets": "../../output/sheet-packing-production/prepared-eight/back",
        "template": "back-recipe.json",
        "mode": "continuous",
        "layer_map": {
          "curve": "art"
        }
      }
    },
    {
      "id": "short",
      "type": "jcard",
      "profile": "standard-jcard-3-panel-v1",
      "quantity": 5,
      "rotations": [
        0,
        90
      ],
      "guides": {
        "cut": true,
        "fold": true,
        "registration": true
      },
      "front": {
        "assets": "../../output/sheet-packing-production/prepared-three/front",
        "template": "front-alt-recipe.json",
        "mode": "continuous",
        "layer_map": {
          "curve": "art"
        }
      },
      "back": {
        "assets": "../../output/sheet-packing-production/prepared-three/back",
        "template": "back-recipe.json",
        "mode": "continuous",
        "layer_map": {
          "curve": "art"
        }
      }
    }
  ],
  "logical_layers": [
    {
      "id": "art",
      "ordinal": 1,
      "label": "Artwork"
    }
  ]
}
```

```powershell
python scripts/pack_impositions.py --config examples/sheet-packing/mixed.json --output-dir output/sheet-packing-production/mixed
```

Inspect the placement preview and both faces of `sheet-001` and `sheet-002`.
The root `packing.json` records instance IDs, rotations, exact mm transforms,
source hashes and all output paths. Preserve each SVG's adjacent JSON files.

For a single-sided job, set `faces` to `front`, remove `flip` and
`usable_back_mm`, and remove every object's `back`. Keep the complete `front`
definition. To test a different duplex flip, set `flip` to `top-bottom` and
regenerate the packed job. Do not flip or reposition the back SVG manually.

## Select pen slots and convert

Save both complete pen plans below. The artwork uses slot 1; cut, fold and
registration guides use slots 2, 3 and 4. Select slots that match your loaded
pens. These plans preserve separate artwork and guide passes.

### pens-two.json

```json
{
  "schema_version": 3,
  "policy": "explicit",
  "passes": [
    {
      "id": "artwork",
      "assignments": [
        {
          "layer_ids": [
            "curve"
          ],
          "physical_slot": 1
        }
      ]
    },
    {
      "id": "guides",
      "assignments": [
        {
          "layer_ids": [
            "sheet-cut-guides"
          ],
          "physical_slot": 2
        },
        {
          "layer_ids": [
            "sheet-fold-guides"
          ],
          "physical_slot": 3
        },
        {
          "layer_ids": [
            "sheet-registration"
          ],
          "physical_slot": 4
        }
      ]
    }
  ]
}
```

### pens-mixed.json

```json
{
  "schema_version": 3,
  "policy": "explicit",
  "passes": [
    {
      "id": "artwork",
      "assignments": [
        {
          "layer_ids": [
            "art"
          ],
          "physical_slot": 1
        }
      ]
    },
    {
      "id": "guides",
      "assignments": [
        {
          "layer_ids": [
            "sheet-cut-guides"
          ],
          "physical_slot": 2
        },
        {
          "layer_ids": [
            "sheet-fold-guides"
          ],
          "physical_slot": 3
        },
        {
          "layer_ids": [
            "sheet-registration"
          ],
          "physical_slot": 4
        }
      ]
    }
  ]
}
```

Use the converter's schema-3 `--pen-plan` option for these neutral SVGs. Do not
use `--pen-map`. The imposition metadata preserves the physical A3 layout; do not
fit or centre the visible strokes. Use `--margin 3mm` to match these packing
configs; the converter defaults to 10 mm and rejects strokes inside that larger
margin. Convert each sheet/face as a separate job
with the matching pen plan. For example, convert the first front without sending:

```powershell
python scripts/dpx3300_convert.py --input-dir output/sheet-packing-production/two-eight-panel/sheet-001/front --file design.svg --output-dir output/sheet-packing-production/hpgl-two-front --page-size a3 --landscape --margin 3mm --pen-plan examples/sheet-packing/pens-two.json
```

For the mixed sample use `pens-mixed.json` and its sheet/face directory.
Conversion and sending remain explicit operator
steps; packing starts neither.

For repeated local generation, add `--overwrite` to the relevant commands only
when you intend to replace their existing generated directory. Do not move the
output into an input asset directory. No sample has been physically validated.
Plot scrap proofs and check cuts, folds and duplex registration under HAR-88.

## Irregular objects in the reusable core

Run `python examples/sheet-packing/irregular_bounds.py` from plotter-workflow.
It writes `output/sheet-packing-production/irregular-bounds.svg`. The solid
outlines are actual trim polygons; dashed boxes are their occupied bounds.
The core reserves each whole box. It does not fit a triangle into an L-shaped
object's unused corner. This diagnostic uses the production Python solver;
the production packing CLI currently accepts only J-card objects.

See the [complete packing reference](../reference/sheet-packing.md) for every
field, limits, guide bounds, solver rules and paired-coordinate transforms.
