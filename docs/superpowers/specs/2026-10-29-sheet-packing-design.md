# HAR-91: Reusable exact-scale sheet packing

Status: approved by the user on 2026-10-29. The user selected grid plus MaxRects, then
selected conservative rectangular bounds first with polygon-aware nesting later.
The [visual study](2026-10-29-sheet-packing-study.md) is a throwaway prototype.

## Intent and approaches

Place several whole imposition objects on physical sheets without changing their
scale, internal facets, artwork bindings or fold relationships. Start with J-card
assets. Keep the packing core independent of J-cards so booklet, cootie-catcher
and irregular-object adapters can be added later.

| Approach | Benefit | Cost | Decision |
| --- | --- | --- | --- |
| Grid only | Small implementation for identical rectangles | Poor support for mixed sizes | Not selected |
| Grid plus MaxRects with conservative bounds | Useful now; one placement/export contract | Leaves empty corners of irregular objects unused | Selected |
| Polygon-aware nesting immediately | Can recover irregular corner space | Adds polygon offsets, collision tests and search before the shared workflow exists | Deferred |

MaxRects is a heuristic. Do not claim minimum sheet count or an optimal layout.
The study's A3 examples are geometric fits, not physical plotter acceptance.

## Scope and boundaries

This belongs in `plotter-workflow`, in the isolated `sheet-packing` worktree.
No generator changes, new package dependencies, hardware commands or automatic
artwork regeneration are required. Keep the current single-J-card CLI working.

Deliver a pure packing library, a J-card adapter, a multi-object CLI, atomic
sheet/face bundles, placement previews, audits and complete operator examples.
The first CLI supports J-cards only. The pure library accepts footprints derived
from arbitrary outlines; tests and diagnostic examples include concave shapes.
Adding a production booklet/cootie-catcher/custom-SVG adapter is follow-up work.

True polygon nesting, arbitrary-angle rotation, automatic paper selection, common
cut-line merging, generated bleed, cut-path optimization and machine operation
are out of scope. Do not infer holes from empty artwork, facet gaps or fold lines.

## Shared physical-object contract

Use immutable native-mm records. Each object adapter supplies:

- Stable object-spec ID and native local datum.
- Trim geometry as regions with outer rings and optional holes, retained as
  metadata. The rectangle engine uses bounds, not ring collisions.
- A conservative occupied rectangle in the same datum containing all selected
  faces' trim, requested bleed allowance and enabled construction-mark extents.
- Explicit allowed rotations, initially subsets of `[0, 90]` only.
- Validated native face artwork and guide records, separate from the footprint.

The packing solver consumes IDs, occupied bounds, quantity-expanded instance IDs
and allowed rotations. It does not inspect artwork or choose pens. It returns
sheet index, instance ID, angle and rigid object-to-front-sheet matrix. A future
polygon strategy must return this same result type. Its collision geometry can
replace the rectangle without changing artwork bindings or duplex publication.

Native trim/guide coordinates can have nonzero or negative bounds. Preserve the
datum in the returned matrix; do not assume trim starts at the footprint origin.
Validate finite geometry and positive occupied extents at the adapter boundary.
An occupied rectangle is always authoritative for collision and fit in version 1.
Convert every selected face's occupied geometry to the shared front-native datum
before computing that rectangle. Registration marks are one set of physical
front-native positions, carried to both faces, not two independently chosen sets.

## Sheet space and clearance

Coordinates use the physical sheet's top-left origin, X right and Y down. Sheet
width and height are positive finite mm values up to 1e6. Portrait and landscape
are explicit dimensions; do not silently swap them.

Inputs include a usable rectangle, four outer margins and a nonnegative gutter.
The front usable rectangle defaults to the full sheet. The effective front area
is its intersection with the sheet inset by the four margins.
Each supplied usable rectangle must have positive finite extents and lie within
the physical sheet; collapsed margin/intersection areas fail. Resolve known
paper names/orientations from existing sheet definitions when dimensions match;
otherwise retain custom dimensions in the imposition audit. As in the current
J-card workflow, custom-size conversion still requires a supported device/page
profile. Packing does not invent or override that hardware capability.

For a paired job, permit a distinct back usable rectangle, defaulting to the
front usable rectangle in back-sheet coordinates. Intersect the effective front
area with the selected flip's inverse image of the effective back area before
packing. Apply each face's sheet margins in that face's coordinate system. This
ensures asymmetric plotter limits do not produce an unusable paired back.

Reserve all enabled cut/fold/registration geometry, including marker arms, in the
object rectangle. A per-object nonnegative `bleed_allowance_mm` expands trim
bounds for packing only; it does not create bleed artwork. Union it with actual
guide extents rather than adding unrelated clearances repeatedly. The gutter is
the required separation between these reserved rectangles, not between trim lines.
Safe-area diagnostics do not consume extra space unless their geometry extends
outside the other required bounds.

The prototype's 3 mm uniform envelope is illustrative only. Production derives
guide extents from actual adapter geometry and the explicitly requested allowance.
Do not require a trailing gutter at the usable area's right/bottom boundary.
Objects that cannot fit under any permitted rotation fail with ID, dimensions,
available dimensions and rotation policy. Do not shrink or drop them.

## Deterministic solvers

`auto` uses a grid when all expanded items share occupied dimensions and rotation
policy; otherwise it uses MaxRects. Explicit `grid` rejects incompatible mixed
footprints. Explicit `maxrects` is permitted for identical copies too.

Grid evaluates each allowed orientation and chooses the largest per-sheet
capacity. Ties prefer the lower angle. Place row-major from the effective area's
top-left, then spill to the next sheet.

MaxRects uses descending occupied area, descending maximum side, then stable
instance ID. Search existing sheets in index order. Within a sheet use best
short-side fit, then long-side fit, Y, X, angle and stable free-rectangle ordering.
Split all free rectangles intersected by a placement and prune duplicates and
contained rectangles. Open the next sheet only if no existing sheet accepts the
item. The same inputs must produce the same placement order and audit.

Assign IDs before sorting: spec `album` and quantity 2 become `album-0001` and
`album-0002`. Reordering object specs does not change IDs or placements. Adding
items may move existing instances, but must not alter prepared artwork or its
generation seeds. Each spec references fixed prepared assets; repeated copies
reuse those assets. Different artwork uses another spec ID/assets entry.

Both solvers use the same final validation: every reserved footprint lies inside
the effective area, footprints obey gutter separation, matrices have unit scale,
and each requested instance appears exactly once. Use a documented 1e-7 mm
comparison tolerance for arithmetic, not to rescale objects or repair placements.

## Duplex and native artwork

Solve front placements once. Use the existing J-card native back-face convention,
which reverses physical panel order, rather than mirroring the artwork arbitrarily.
Compose each object's native face correspondence, its selected rotation/front
placement, and the sheet reflection to derive the back matrix. Support `left-right`
and `top-bottom` flips with explicit physical sheet dimensions as their datum.
Never pack backs independently. Verify corner and physical-panel correspondence
for each rotation and flip, including different front/back usable areas.

Specifically, if M maps front-native mm to front-sheet mm and F is the sheet
reflection, the back matrix is `F * M * C`. For J-cards,
`C=(-1,0,0,1,trim_width,0)` maps back-native coordinates to front-native physical
coordinates. The existing left-right and top-bottom single-card matrices must be
recovered exactly at zero packing rotation. For native back guides, use the same
C correspondence; registration marks use its inverse to express the shared
physical marks in back-native coordinates before composition.

Version 1 jobs select `front` or `both`; a back-only run is obtained from the
published paired job's back file. Each sheet/face remains a separate plot input.
The tool does not pause, flip paper or send the resulting jobs.

Extract native prepared-face validation/rendering from `jcard_impose.render_face`
without weakening its profile, recipe, provenance, source-hash, canvas or viewport
checks. Reuse it for the single-card path and new adapter. Native fragment
preparation must not depend on a source sheet placement. Render the packed native
fragments with the full rigid matrix, including off-diagonal terms for 90-degree
rotation. The existing diagonal-only single-card transform cannot simply be reused
for those rotations. Transform all guides with the same face matrix.

## Proposed configuration and command

Add `scripts/pack_impositions.py --config packing.json --output-dir output/packed`
with explicit `--overwrite`, following the existing scripts' path conventions.
Resolve all input paths relative to the configuration file.

Proposed top-level fields:

| Field | Default | Meaning |
| --- | --- | --- |
| `schema_version` | Required, `1` | Strict configuration version |
| `sheet_mm` | Required `[width, height]` | Physical paper dimensions |
| `usable_front_mm` | Whole sheet | `[x, y, width, height]` |
| `usable_back_mm` | Front rectangle | Allowed only for `faces="both"` |
| `margins_mm` | `[0, 0, 0, 0]` | Top, right, bottom, left |
| `gutter_mm` | 0 | Separation between occupied rectangles |
| `strategy` | `auto` | `auto`, `grid`, `maxrects` |
| `faces` | `front` | `front`, `both` |
| `flip` | `left-right` for paired jobs | Reject explicit flip on front-only jobs |
| `objects` | Required nonempty list | Definitions below |
| `logical_layers` | Omitted | Explicit merged artwork catalogue when identity mapping is insufficient |

Each object has unique `id`, `type="jcard"`, `profile`, integer `quantity` default
1, `rotations` default `[0]`, `bleed_allowance_mm` default 0, `guides` with strict
cut/fold/registration booleans, and exactly the job's selected face entries.
Each face entry has `assets`, `template`, `mode` (`independent` or `continuous`),
`blank_panels` default empty, and optional `layer_map` from source to output IDs.
The face fields reuse native J-card artwork validation. Physical sheet/origin
fields from single-card configurations are not accepted as native face controls.

For example, `objects[0]` can reference one prepared front/back asset pair with
quantity 2, while another spec supplies different artwork and profile. Preparation
remains the existing generate/prepare handoff; the packer consumes those validated
assets and does not invoke a generator. Documentation supplies all necessary
source recipes, preparation configuration and packing configuration inline.

Reject unknown fields, duplicate IDs/JSON keys, nulls, Boolean or string numbers,
nonfinite values, invalid rotations, missing faces/assets and inapplicable fields.
Omitted defaults have a single meaning; do not silently ignore source controls.

## Logical layers and pen mappings

Preserve neutral logical-layer identity. If every input face has the identical
catalogue, omitted maps use identity and retain that catalogue. Otherwise require
an explicit output catalogue and complete per-face maps covering every source
artwork layer. Reject unmapped IDs, unknown targets and conflicting metadata.
Maps may intentionally merge artwork into a named output layer; never merge by
ordinal or display label implicitly.

Keep guides in reserved output IDs `sheet-cut-guides`, `sheet-fold-guides` and
`sheet-registration`, appended deterministically after artwork. Reject artwork
collisions with enabled reserved IDs. A single guide channel can contain several
instances, with instance metadata on their wrappers. Do not deduplicate coincident
guides or modify explicit physical pen choices. Physical pen mapping remains in
the existing converter/pen-plan stage and is tested with explicit mappings.

## Output, provenance and limits

Publish one directory containing `packing.json`, a diagnostic placement SVG,
`sheet-001/front/`, optional `sheet-001/back/`, and further numbered sheets.
Each plot directory includes `design.svg`, `design.json` and
`design.imposition.json` using the neutral/preserved-layout contract. The root
audit lists all plot jobs and hashes, input hashes, requested/resolved controls,
object-instance bindings, native/front/back matrices, reserved bounds, trim and
reserved areas, usable area, unused area and selected strategy. Do not label
bounding-box utilization as polygon nesting efficiency. Mark previews diagnostic.

Validate/preflight inputs, fit and work limits before publishing. Bound input
specs to 128, expanded instances to 1000, sheets to 256, free rectangles per sheet
to 4096, scored candidates to 2,000,000, and composed output vertices to 2,000,000.
Use existing individual source guards and a 256 MiB aggregate generated SVG-byte
cap. These are author-proposed initial limits; fail before the corresponding
allocation/search/output, with no partial final job. Internal factoring is left
to the implementation plan.

Use the existing atomic-directory staging/rollback helper for the entire job,
not one face at a time. Add `packing.json` as a recognized overwrite ownership
marker. Reject output paths overlapping any assets, templates or configuration.
Validate every selected face and SVG contract before rename. A late failure must
preserve an existing output byte-for-byte and publish no incomplete new job.

## Validation and documentation

Use small direct solver fixtures while iterating. Cover identical/mixed objects,
both permitted angles, ties, reversed input order, exact edge fits, gutter-only
space, asymmetric/native-negative bounds, impossible sizes, overflow and all work
caps. Irregular fixtures prove rectangular envelopes remain conservative without
claiming true nesting. Verify no scaling and polygon edge-length preservation.

Integration covers actual prepared J-card assets, different profiles and artwork,
complete layer-map validation, guide-channel separation, both flips/rotations,
paired usable-area intersection, stale recipes/hashes, blank faces/viewports,
existing single-J-card behavior and converter preserved-layout/explicit-pen-map
consumption. Failure injection covers late second-face/second-sheet validation,
budget limits and overwrite rollback. No hardware test is required.

Run affected packing/J-card/layer-contract/preserved-layout/export tests plus
Ruff; do not run an unrelated full suite by default. Retain readable SVG/PNG
samples for two eight-panel cards, mixed-format overflow, differing artwork and
irregular bounds. The runbook uses plain technical English, parameter tables,
coordinate/duplex diagrams and complete inline JSON/commands.

## Approval and follow-ups

The selected approach and rectangular-first sequence are agreed. Proposed API
names, limits, catalogue merge rules and the J-card-only initial CLI were approved
with this design. Internal implementation factoring remains a builder choice.
The fresh builder check reported no important unanswered questions.
Physical fit/duplex registration remains HAR-88. Polygon nesting and additional
object adapters are later features. No Linear writes are authorized as part of
this local design draft.
