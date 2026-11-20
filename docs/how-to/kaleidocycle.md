# Kaleidocycle composition and imposition

The kaleidocycle uses the existing assembled-artwork export, producer,
return adapter, and neutral logical-layer contracts. Its flat net has 32
triangles in eight alternating columns. The supplied reference calls these
four segments; a segment is a pair of columns. Slots are `column-1-a` through
`column-8-d`. Glue tabs are construction geometry, never artwork slots.

**Physical validation is pending.** The built-in A-D viewing profiles are
illustrative square fan projections with explicit radial seam pairings. They
demonstrate continuous composition and orientation mapping; they are not a
derived 3D folding solution. Their panel ordering, assembled adjacency, reading
orientation, and closure must be checked with a labeled paper fold before
relying on a finished image. Do not interpret passing software checks as proof
that those views match a real folded kaleidocycle.

## Generate four states

From the feature checkout, use your existing plotter Python environment. In a
linked worktree it may be `../../.venv/Scripts/python.exe`.

```powershell
$python = '.venv/Scripts/python.exe'
$vizRepo = 'C:/path/to/viz_virtualserver'
$vizPython = "$vizRepo/.venv/Scripts/python.exe"
$demo = "$PWD/output/kaleidocycle-demo"
foreach ($state in @('A', 'B', 'C', 'D')) {
  & $python scripts/export_artwork_layout.py --layout kaleidocycle-state `
    --state $state --width-mm 240 `
    --job-template examples/assembled-artwork/truchet-recipe.json `
    --output-dir "$demo/$state/export"
  Push-Location $vizRepo
  & $vizPython -B -m viz_virtualserver.cli.domain_bundle `
    "$demo/$state/export/artwork-job.json" --output-dir "$demo/$state/producer"
  Pop-Location
  & $python scripts/prepare_layout_assets.py `
    --producer-bundle "$demo/$state/producer" `
    --handoff "$demo/$state/export/layout-handoff.json" `
    --output-dir "$demo/$state/assets"
}
Copy-Item examples/kaleidocycle/kaleidocycle.json "$demo/kaleidocycle.json"
& $python scripts/kaleidocycle_impose.py "$demo/kaleidocycle.json" `
  --output-dir "$demo/sheet"
```

Stop on an unsuccessful command before proceeding. Existing output directories
require an explicit `--overwrite` on the relevant command. Each state may use
its own recipe and seed; all four returned bundles must retain exactly the same
logical-layer catalog. No catalog renaming or implicit merge occurs.

The example config requires all four state asset directories relative to the
config. Each must contain exactly eight prepared surfaces with a matching
handoff and producer provenance. Physical width must match the export width.
Letter, A4, A3, and tabloid use the existing booklet sheet dimensions.

## Coordinates and explicit profiles

Every intrinsic source canvas is a 128 by 128 square with a triangular crop.
Integer source vertices and integer built-in transforms make shared seams exact
for the producer's precision checks. These are design coordinates, not physical
96-dpi dimensions. `settings.source_unit_mm` records the physical scale; recipe
spacing in design units scales with it. For width 240 mm, one design unit is
approximately 0.22936 mm. `width_mm` includes the left glue tabs.

The producer generates one composition in a named assembled frame and clips it
into the triangles. Preparation restores local canvases. Imposition applies the
physical scale and translation to the flat net once; it never reapplies an
assembled view transform. Original SVG curves, clips, path IDs, logical layers,
and producer metadata remain available in the imposed artwork.

To supply a corrected viewing arrangement, copy the `layout` object out of an
export's `layout-handoff.json` into a separate JSON file. Change its `profile_id`,
`window`, per-panel `assembled_matrix`, and explicit `settings.adjacency` as needed.
Keep canonical panel identities, local crop/canvas geometry, and bindings.
Each adjacency entry is `[[panel_id, edge_index], [other_panel_id, edge_index]]`;
edge indices follow the crop's ordered vertices. Eight unique edge pairs must
cover all eight panels and meet in reverse endpoint order. Keep the status
`provisional` until a future physical acceptance workflow establishes validation.

Pass this file as `--profile corrected-A.json` alongside `--state A --width-mm 240`.
The exporter validates declared seams, bounds, and invertible transforms. It does
not infer a fold state from flat sheet contact. Arbitrary profiles should use
exactly representable shared endpoints; the producer rejects ambiguous gaps.

## Outputs and acceptance

- `sheet/design.svg`: artwork only, neutral layers, preserved physical placement.
- `sheet/design.json`: hashed artwork inventory and shared layer catalog.
- `sheet/design.imposition.json`: converter-compatible audit and panel geometry.
- `sheet/guides.svg`: separate cut, fold, and diagnostic glue-tab outlines.
- `sheet/net-preview.svg`: colored, labeled flat net for inspecting and printing
  a sacrificial fold sample; this diagnostic contains text and is not plot input.

Use the [neutral plotting workflow](neutral-logical-layer-plotting.md) to assign
pens and convert `design.svg`. Glue outlines overlap some construction edges;
select guide groups intentionally before plotting or cutting them. Guides do not
encode mountain versus valley folds. Follow the reference's assembly sequence.

Before accepting a physical profile, mark triangle IDs and asymmetric up/right
arrows, cut and assemble a sacrificial net, record each visible state's panel
order and reading frame, and verify a continuous motif across closure seams.
The four built-in states cover each artwork panel once. Transitions such as
A-to-B remain deferred; their IDs can be referenced by a later transition model.

The eight-page book object refactor remains a separate backlog item.
