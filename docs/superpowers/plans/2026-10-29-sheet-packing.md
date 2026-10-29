# Reusable Sheet Packing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Preserve the user's native execution preference; use one fresh final reviewer, not per-task agents.

**Goal:** Pack complete J-card objects onto exact-scale single/paired sheets using a reusable rectangular packing core.

**Architecture:** Adapters produce immutable native-mm footprints and validated native artwork. Pure grid/MaxRects solvers return rigid front placements; a shared geometry layer derives paired back transforms. A separate publisher composes neutral artwork and guide channels and commits the entire multi-sheet job atomically. The core retains irregular outlines while packing their conservative rectangles.

**Tech Stack:** Python, frozen dataclasses, ElementTree, existing neutral SVG/vpype geometry helpers, pytest and Ruff. No dependency additions.

**Spec:** [Approved HAR-91 design](../specs/2026-10-29-sheet-packing-design.md).

## Global Constraints

- `plotter-workflow` branch `spike/har91-sheet-packing`, based on `dd7c0ab`; preserve existing worktrees and generated study outputs.
- Grid/MaxRects only; polygon nesting and additional production adapters remain later work. The initial CLI accepts `type="jcard"`; core tests accept irregular outlines.
- Native coordinates are mm, top-left origin, X right/Y down. Rigid rotations are explicit nonempty unique subsets of `[0, 90]`; no scale, auto-shrink, independent back packing or artwork generation.
- Comparison tolerance is 1e-7 mm. Sheet dimensions are finite, positive and <=1e6 mm. Validate source geometry before computing occupied bounds.
- Occupied bounds union trim plus requested bleed allowance with actual enabled guide extents, in the front-native datum. Gutter is additional separation between these occupied rectangles. Do not require an external trailing gutter.
- Paired usable area is the front area intersected with the inverse-flipped back area, including each face's margins.
- Front `M`, native J-card back correspondence `C=(-1,0,0,1,trim_width,0)`, sheet flip `F`: back matrix is `F*M*C`.
- Limits: 128 object specs, 1000 expanded instances, 256 sheets, 4096 free rectangles per sheet, 2,000,000 scored candidates, 2,000,000 output vertices, 256 MiB aggregate generated SVG bytes. Charge before corresponding work/allocation.
- Reject unknown/duplicate/inapplicable controls, nulls, Boolean/string numbers, nonfinite numbers, unknown profiles, incomplete face/layer mappings and invalid asset provenance.
- Preserve neutral logical layers, explicit physical pen choices and separate guide channels. Physical pen mapping stays in the converter/pen-plan stage.
- Publish every selected sheet/face atomically with existing input-path protection and rollback. No hardware commands or physical verification.
- Focused TDD while iterating; affected subsystem/consumer checks once at handoff, plus Ruff. No unrelated full-suite baseline. Documentation uses complete inline JSON and plain technical English.
- No Linear writes are part of this execution; keep evidence local until separately authorized.

## Review Focus

1. Negative/nonzero footprint origins must not shift trim or guide datums: Task 1 tests a negative bound and asymmetric rotated object with literal corner expectations.
2. Asymmetric back usable limits can invalidate an apparently valid front: Task 1 tests their inverse-flip intersection for both flip axes.
3. Reusing native SVG fragments must not duplicate XML IDs or cross-wire references: Task 4 composes repeated assets and checks ID/reference integrity and instance bindings.
4. Completely blank faces must still validate viewport, profile and source hashes: Task 3 tests tampered blank assets with provenance otherwise made internally consistent.
5. A late failure after another sheet/face has rendered must not replace an old job: Task 4 injects second-sheet/back failure and compares the entire previous output tree byte-for-byte.

## File map

| Files | Responsibility |
| --- | --- |
| Create `imposition/sheet_packing/__init__.py`, `model.py`, `geometry.py`, `budget.py` | Immutable records, rigid/duplex geometry and bounded work accounting |
| Create `imposition/sheet_packing/grid.py`, `maxrects.py`, `solver.py` | Strategies, deterministic dispatch and final validation |
| Create `imposition/jcard_native.py`; modify `imposition/jcard_impose.py` | Extract validated native fragments; retain the existing single-card behavior |
| Create `imposition/sheet_packing/config.py`, `jcard.py`, `layers.py` | Strict configuration, J-card footprint adapter and explicit layer maps |
| Create `imposition/sheet_packing/render.py`, `export.py`; modify `imposition/artwork_io.py` | Sheet composition, audits, atomic publication and overwrite ownership marker |
| Create `scripts/pack_impositions.py` | CLI and path handling |
| Create `tests/test_sheet_packing_geometry.py`, `test_sheet_packing_solvers.py`, `test_sheet_packing_config.py`, `test_sheet_packing_jcard.py`, `test_sheet_packing_export.py` | Meaningful geometry, policy and integration regressions |
| Modify `tests/test_jcard_impose.py` | Native extraction and blank viewport consumer regressions |
| Create `docs/reference/sheet-packing.md`, `docs/how-to/pack-jcards.md`, `examples/sheet-packing/`; modify `docs/README.md`, `docs/reference/cassette-jcard.md` | Self-contained documentation and runnable examples |

Follow these boundaries without restructuring unrelated imposition code. The prototype remains labelled a study; do not silently promote it to production.

## Task 1: Immutable physical records and paired geometry

**Interfaces:** In `model.py`, frozen `RectMM(x, y, width, height)`, `PolygonRegion(outer, holes=())`, `ObjectFootprint(object_id, trim_regions, occupied_bounds, rotations)`, `PackingInstance(instance_id, footprint)`, `SheetArea(width_mm, height_mm, usable_front, usable_back, margins, faces, flip)`, `PackedInstance(instance_id, sheet_index, rotation, front_matrix, occupied_bounds)` and `PackingResult(strategy, placements, sheet_count)`. Use immutable tuple coordinates and six-component SVG-order matrices. These are library records; no renderer/asset imports. Validate/copied tuples at construction, not just JSON boundaries.

**Interfaces:** In `geometry.py`, `effective_area(sheet: SheetArea) -> RectMM`, `front_matrix(footprint: ObjectFootprint, rotation: int, occupied_origin: tuple[float,float]) -> tuple`, `back_matrix(front: tuple, native_back_to_front: tuple, sheet: SheetArea) -> tuple`, `transform(matrix, point) -> tuple`, and `validate_placements(instances, result, sheet, gutter) -> None`. In `budget.py`, `PackingBudget.reserve(kind: str, count: int) -> None` checks integer nonnegative charges before mutation; live free-rectangle limits are checked before creating the next split record.

- [ ] Write failing geometry tests with independently calculated expectations:

```python
def test_native_negative_bounds_retain_trim_datum():
    # Rectangle -3,-5..17,5 becomes 10,20..30,30 at zero rotation.
    footprint = ObjectFootprint("x", (), RectMM(-3, -5, 20, 10), (0, 90))
    assert front_matrix(footprint, 0, (10, 20)) == (1, 0, 0, 1, 13, 25)
    assert front_matrix(footprint, 90, (10, 20)) == (0, 1, -1, 0, 15, 23)

def test_back_uses_native_panel_correspondence():
    sheet = SheetArea(500, 250, RectMM(0,0,500,250), RectMM(0,0,500,250),
                      (0,0,0,0), "both", "left-right")
    assert back_matrix((1,0,0,1,20,30), (-1,0,0,1,406.4,0), sheet) == pytest.approx((1,0,0,1,73.6,30))
```

- [ ] Add literal paired-area intersection cases for both flips and asymmetric usable rectangles/margins; reject empty intersections, outside-sheet inputs and collapsed margins. Check all physical panel corners at 0/90 degrees and both flips, unit determinant, unchanged edge lengths and no missing/duplicate instances.
- [ ] Add frozen/copy validation, concave/holed outline metadata, conservative occupied bounds, malformed/nonfinite/Boolean geometry, and small injected work-limit failures. Reject an occupied box that excludes trim-region outer bounds; holes do not reduce the box.
- [ ] Run `python -m pytest tests/test_sheet_packing_geometry.py -q -p no:cacheprovider`; expect missing-resource failures. Implement the records and exact quadrant matrices, avoiding trigonometric rounding for permitted angles. Reflection occurs in physical sheet coordinates.
- [ ] Rerun the file; expect pass. Run Ruff on changed files and commit.

## Task 2: Grid and deterministic MaxRects

**Interfaces:** `grid.pack_grid(instances, sheet, gutter, budget) -> PackingResult`, `maxrects.pack_maxrects(instances, sheet, gutter, budget) -> PackingResult`, `solver.pack(instances, sheet, gutter=0, strategy="auto", budget=None) -> PackingResult`. `auto` selects grid only for identical occupied dimensions and rotation policy; footprint origins/shapes can differ because each result retains its datum.

- [ ] Write failing solver tests in `test_sheet_packing_solvers.py`: two 412.4x107.6 occupied boxes fit A3 with 3 mm margins and 4 mm gutter; seven 109.1875x107.6 boxes spill from a six-copy grid to sheet 2. Verify the chosen orientation, row-major order and literal coordinates, not only sheet counts.
- [ ] Add hand-sized mixed fixtures exercising every free-rectangle split direction and containment pruning, a case requiring 90-degree rotation, forbidden-rotation failure, equal-score tie ordering, exact edge fits without a trailing gutter, and zero/nonzero gutters. Reversal of input order must preserve the full result. Explicit grid must reject incompatible sizes/rotation policies.
- [ ] Add irregular shapes whose bounds are packed conservatively; use actual outlines only to verify containment/rigid edge lengths. Include multi-sheet overflow, impossible-item diagnostics, page/candidate/free-rectangle caps and no partial returned result. Probe limit failures with small injected budgets rather than creating huge fixtures.
- [ ] Run the solver file and confirm missing implementations fail. Implement the design's area/max-side/ID sorting, existing-sheet order and short-side/long-side/Y/X/angle tie rules. Reserve candidate work before evaluating each free rectangle/orientation. Maintain the live free list within its cap, including temporary split records; fail instead of allocating an unbounded intermediate list.
- [ ] Apply Task 1 final validation to every strategy result. Run geometry and solver files; expect pass. Run Ruff and commit.

## Task 3: Native J-card assets, strict config and layer policy

**Interfaces:** In `jcard_native.py`, frozen `NativeFaceRequest(profile, face, assets, template, mode, blank_panels)`, `NativeFragment(layer_id, panel_id, svg_bytes)` and `PreparedNativeFace(profile, face, width_mm, height_mm, catalog, fragments, panel_audit, provenance)`. `prepare_native_face(request) -> PreparedNativeFace` validates and crops each source before any blank suppression, and returns standalone native-px fragments. Store immutable audit/provenance records; serialize them at publication. Parse each unique request once, then reuse immutable bytes across copies.

**Interfaces:** `config.load_packing_config(payload, *, base_dir) -> PackingConfig`; `jcard.prepare_objects(config, budget) -> tuple[PreparedPackingObject,...]`; `layers.resolve_catalog(objects, requested_catalog) -> ResolvedCatalog`. A `PreparedPackingObject` binds the spec ID, quantity, footprint, native faces, native back correspondence, physical guide records and layer maps. The solver consumes only its expanded `PackingInstance` records.

- [ ] Record representative existing single-J-card geometry/catalog/audit snapshots before extraction. Write failing native-preparer tests using `tests.test_jcard_impose.assets` and existing small producer fixtures. Cover valid front/back profiles, stale recipe/mode/hash, swapped face/profile, missing/extra panels, malformed native canvas and blank source with a wrong viewport even when no geometry group exists.
- [ ] Extract common preparation from `render_face`. Existing `impose_jcard` delegates to it and preserves geometry, single-back versus paired-back equality, catalogs and audits. Validate source viewport independently of iteration over nonempty logical layers. Do not weaken provenance guards or use a dummy sheet to prepare native artwork.
- [ ] Add failing config tests for every field from the design, default/inapplicable controls, duplicate object IDs/JSON keys, integer quantities, rotations, exact face selection, path resolution, all proposed limits and immutable output. Use `front`/`back` object fields; unknown single-card physical placement fields fail.
- [ ] Implement config parsing with existing bounded JSON readers. Expand IDs before sorting: `album-0001`, `album-0002`. Objects and face asset bindings are independent of list order. The allowed face modes/blank physical panel IDs retain existing J-card rules.
- [ ] Derive trim and fold geometry from verified profiles. Registration marks are the existing three shared front-native centers with their actual arms; map those same physical marks to native back coordinates. Union actual selected-face guide bounds, trim and requested bleed allowance before packing. Do not reuse the study's uniform 3 mm assumption.
- [ ] Add layer tests: identical complete catalogs use identity; otherwise require explicit output catalog and complete per-face source-to-output maps. Explicit target metadata is authoritative under a supplied map; conflicting source metadata blocks implicit identity. Reject unknown/missing targets, duplicate ordinals/IDs and enabled reserved-guide collisions. Multiple source IDs may merge only through explicit maps.
- [ ] Run native/config/J-card tests plus existing `test_jcard_impose.py`, `test_jcard_artwork.py`, `test_jcard_config.py`, `test_jcard_placement.py`, `test_jcard_profiles.py`, `test_jcard_profile_workflow.py`. Compare the pre-extraction geometry/catalog/audit snapshots. Expect pass; run Ruff and commit.

## Task 4: Rigid composition, atomic jobs and CLI

**Interfaces:** `render.render_sheet_face(config, prepared_objects, result, sheet_index, face, catalog, budget) -> RenderedFace` returns immutable SVG/audit bytes and catalog. `export.pack_impositions(config, *, output_dir, overwrite=False) -> Path` owns preparation, packing, full-job staging and publication. `scripts.pack_impositions.main(argv=None) -> int` loads the strict config, protects all inputs and prints root audit plus plot-job paths. No command invokes generation, conversion or sending implicitly.

- [ ] Write failing export tests in `test_sheet_packing_export.py` with real prepared assets: identical and different artwork, mixed profiles, 90-degree instances, front-only/paired, both flips and asymmetric back usable limits. Compare physical panel corners and transformed path geometry with independently transformed native fixtures. Ensure rendering does not mutate cached fragments across copies/faces.
- [ ] Include repeated source XML IDs/reference fixtures. Namespace copied SVG IDs and their references deterministically by instance/face/panel; assert unique IDs, valid references and instance-to-artwork provenance. Preserve native face panel IDs as metadata without treating them as globally unique XML IDs.
- [ ] Render one root neutral group per resolved layer, separate reserved guide groups and full affine wrappers in px. Apply `F*M*C` to back-native fragments; do not independently mirror per-panel artwork. Transform guides in mm, then convert to px once. Validate full output SVG contracts and actual plotted bounds.
- [ ] Write `packing.json`, diagnostic `placement-preview.svg` and numbered `sheet-001/front|back/` plot folders, each with `design.svg`, `design.json`, `design.imposition.json`. Root job records include hashes, native/placed transforms, IDs, mappings, footprints, strategies, area accounting and work usage. SVG roots identify preserved physical layout and resolved known paper/orientation or custom dimensions.
- [ ] Charge composed vertices before duplicating fragments and serialized SVG bytes before accumulation/write. Count repeated copies, not only unique assets. Fail atomically at small injected vertex/byte limits. Support reserved empty layers/catalog entries consistently with the existing neutral contract.
- [ ] Use `atomic_directory` once for the complete job and recognize `packing.json` as its overwrite marker. Add tests for overlapping inputs/config paths, unsupported overwrite roots, first-write failure, and failure injected after sheet 1 or the second face. Entire prior output must remain byte-identical; no final directory on first-write failure.
- [ ] Implement CLI parity with existing scripts: explicit overwrite, relative input paths and actionable parser errors. Add CLI tests for valid jobs and failure codes without sending hardware commands.
- [ ] Verify a generated packed SVG through the existing converter with explicit pen mapping and preserved layout. Assert no relayout/centering, layer-to-pen choices unchanged and guide channels separate. Unsupported custom device/page conversion remains an explicit operator error, not silent fit.
- [ ] Run export tests plus `test_preserved_physical_layout.py`, `test_logical_layer_contract.py`, `test_empty_pen_layers.py`, `test_svg_pen_contract.py`, `test_hpgl_pen_mapping.py`, `test_pen_plan_sidecar_paths.py`, `test_jcard_integration.py` and `test_jcard_impose.py`. Expect pass; Ruff/diff checks, then commit.

## Task 5: Complete documentation, samples and final validation

- [ ] Add `sheet-packing.md` with the complete parameter table, native datum/occupied-bounds/gutter diagram, paired usable-area and `F*M*C` diagram, deterministic solver rules, limits, audits and irregular-bounds limitation. State the actual production guide reservation instead of the study's illustrative envelope.
- [ ] Add `pack-jcards.md` with complete inline source recipes, native preparation config, generate/prepare commands and packing JSON. Include two eight-panel copies on A3, mixed profiles/overflow, different artwork, explicit catalog maps and separate front/back plot jobs. Put matching runnable files under `examples/sheet-packing/`; do not make readers infer fields from another document. Keep physical plotting in HAR-88.
- [ ] Run all changed complete recipes through their actual consumers and generate retained output under `output/sheet-packing-production/`. Render readable front/back and multi-sheet previews. Include a pure-core irregular-object diagnostic clearly distinguished from the J-card-only production CLI. Inspect all changed visual artifacts.
- [ ] Before handoff run the five new packing files, all `tests/test_jcard*.py`, changed atomic/artwork return consumers, `test_imposition_geometry.py`, logical-layer/SVG/empty-layer/preserved-layout and converter pen-mapping tests. Record the exact file selection, counts, time, warnings and omitted scope in this plan. Run affected Ruff and `git diff --check`.
- [ ] Use 30–60 second waits for long tests. Do not repeat passing scopes without invalidating changes. If Windows atomic rename or sandbox temp permissions fail, record the failure and retry only the affected node in a new checked temp directory; do not alter product retry policy to mask the environment.
- [ ] Request one fresh final whole-branch reviewer using the native execution skill and the Review Focus list above. Fix Important/Critical findings with failing regressions and affected checks; record deferred minors and all rulings. No redundant full-suite baseline or per-task review agents.
- [ ] Commit execution evidence and preserve the worktree, study and production outputs. Use finishing-a-development-branch for the user's integration choice; no merge/push or external ticket writes are implied by this plan.

## Plan self-review

The spec's footprint/datum/duplex rules map to Task 1; solver/determinism to Task 2; strict assets/catalogs/real guide extents to Task 3; full rigid rendering, IDs, preserved pen mappings and whole-job atomicity to Task 4; complete docs, consumer verification and retained samples to Task 5. Each Review Focus item has a concrete owning test. The proposed API names above are consistent across tasks. The prototype is not a production dependency. No hardware, dependency or test-selection changes are planned.

## Execution evidence

Pending user plan review. Production implementation has not started.
