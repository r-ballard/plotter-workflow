# Assembled Layout Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export actual reading/assembled layouts into runnable Truchet jobs and restore their generated crops to full-canvas assets for imposition.

**Architecture:** Keep layout resolution and fitting rules in plotter-workflow, and reuse viz_virtualserver's existing JSON job/adjacency/partition contract. A return adapter restores producer-rebased crop offsets without refitting; derivative bundles get fresh hashes and explicit provenance. Booklet profiles use established geometry, while Cootie Catcher folded views require explicit provisional/validated profiles rather than inferred fold geometry.

**Tech Stack:** Python3.11-3.13, standard-library JSON/XML/dataclasses, existing vpype/imposition utilities, pytest/Ruff. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-21-assembled-layout-export-design.md`.

## Global Constraints

- plotter-workflow owns named layouts and physical placement; viz_virtualserver owns transformed adjacency, artwork generation and partitioning. No third project or duplicate adjacency detector.
- Keep intrinsic canvas, assembled/reading, and physical sheet frames distinct.
- Use SVG user units with existing `96.0 / 25.4` pixels per millimeter. Recipe lengths remain design units; never silently reinterpret them as millimeters.
- Supported booklet pairs:2-3,4-5,6-7,8-1; page8 is left of page1. Reuse actual sheet/cell definitions and crop rules.
- Preserve full-canvas dimensions and offsets for sparse/blank returned artwork. Do not apply margins, gutters, fit or orientation twice.
- Cootie default folded mapping is unavailable; explicit supplied mapping is required. Do not promote provisional physical orientation status or claim hardware acceptance.
- Original producer bundles and input manifests are read-only. Derivative manifests hash exact returned bytes and record source hashes/settings.
- New exports are atomic and deterministic; overwrite must be explicit. No plotting, transmission, fold simulation or extra package dependencies.
- Execute natively in this worktree, following session preference; one final whole-branch reviewer. File genuinely new test-performance opportunities in Linear backlog, without duplicating existing tickets.

## Review Focus

1. Blank or sparse producer surfaces must not shrink or move during return and imposition (Tasks1/4/6).
2. The8-1 reading pair must not inherit print-sheet page rotations or reverse left/right ordering (Tasks1/6).
3. A cropped producer surface is rebased; padding must restore its known intrinsic offset exactly once, including nonzero canvas origins (Tasks1/4).
4. A derivative SVG hash/catalog must match bytes and active layers, without falsely attributing adapter geometry to an unchanged producer bundle (Tasks4/5).
5. Cootie profiles with incomplete corner mappings, reflections or provisional status must not become an inferred/validated default (Tasks2/6).

## Files and Interfaces

Create `imposition/artwork_layout.py` for frozen layout records and booklet resolution;
`imposition/assembled_profiles.py` for strict explicit Cootie profile loading;
`imposition/artwork_export.py` for template adaptation, export report/preview and atomic writes;
`imposition/artwork_return.py` for crop-offset restoration and derivative neutral bundles;
`scripts/export_artwork_layout.py` and `scripts/prepare_layout_assets.py` for CLI entry points.
Update `scripts/booklet_impose.py` only to extract pure shared cell/crop calculations
if needed; existing rendering results must remain identical. Reuse
`imposition/objects/cootie_catcher.py`, `imposition/source.py` and
`logical_layer_contract.py` rather than duplicating their contracts.

New tests: `test_artwork_layout.py`, `test_assembled_profiles.py`,
`test_artwork_layout_export.py`, `test_artwork_layout_return.py`, and
`test_artwork_layout_integration.py`. New examples live under
`examples/assembled-artwork/`; new guide under
`docs/how-to/assembled-artwork-handoff.md`. Update existing booklet reference and
docs index with the new path, leaving old workflows supported.

Commands run from this worktree using the repository's existing Python environment
(discover `.venv/Scripts/python.exe` in the main checkout; do not install packages
merely because this worktree has no environment). Focused pytest runs use `-q
--tb=short -p no:cacheprovider`, fresh user-temp basetemp, and authorized Windows
staging for atomic writes. Long logs go to this plan's ignored workspace.

### Task1: Booklet layout and exact full-canvas/crop records

**Produces:** frozen `PanelLayout(panel_id:str,canvas_polygon:tuple[Point,...],crop_polygon:tuple[Point,...],assembled_matrix:tuple[float,...],binding:Mapping)` and `ArtworkLayout(profile_id:str,units:str,window:tuple[float,float,float,float],panels:tuple[PanelLayout,...],validation_status:str,settings:Mapping)`. `resolve_booklet_spread(*,sheet_size:str,pages:tuple[int,int],margin_mm:float,gutter_mm:float)->ArtworkLayout`.

- [ ] Write `test_reading_spread_geometry_and_crop`: for cell width W,height H and pixel margin M,gutter G, each full canvas is `(0,0)-(W,H)`; left crop is `(M,M)-(W-G/2,H-M)`, right crop `(G/2,M)-(W-M,H-M)`; matrices are identity and translate(W,0). Window is `(0,0,2W,H)`. Assert all4 supported pairs and8-1 left/right order. Compare these crop bounds with actual existing `_render_spread_half` operations using an operation-recording geometry fixture.
- [ ] Write `test_invalid_and_collapsed_spreads`: reject unsupported pair, duplicate pages, booleans/strings/nonfinite/negative margins, gutter>=2W and margins producing zero/negative crop. Nonzero crop origins remain part of the layout record, not erased by bounds normalization.
- [ ] Run new tests RED; implement pure geometry resolution using existing sheet and booklet definitions. If crop formulas must be factored, share one helper with current renderer and prove old output unchanged.
- [ ] Run new tests plus existing `test_booklet_impose.py` GREEN; commit `feat: resolve assembled booklet artwork layouts`.

### Task2: Explicit Cootie assembled profiles

**Produces:** `load_cootie_assembled_profile(payload:Mapping,*,square_size_mm:float)->ArtworkLayout`. Profile JSON has schema_version1, profile_id, object_id=`cootie_catcher`, view=`folded-outer`, validation_status=`provisional` or `validated`, SVG-pixel window, and panels containing slot_id, canonical intrinsic canvas and explicit six-value SVG matrix. Profile status is a declaration preserved in reports, not proof that this command performed physical validation.

- [ ] Write `test_explicit_profile_preserves_corner_maps`: profile includes exactly outer1..outer4 once; every labeled corner/up arrow follows the declared matrix and inverse. Rotation/reflection cases retain handedness. Derive intrinsic canvas size from canonical object outer-panel dimensions and chosen square size; reject a conflicting supplied canvas. Read object semantic feature anchors for orientation diagnostics.
- [ ] Write `test_missing_ambiguous_and_unsafe_profile`: absent/duplicate slots, unknown version/view/status, singular/nonfinite/ill-conditioned matrices, collapsed windows and out-of-window panels fail. An unspecified profile never falls back to synthetic producer geometry or flat corner placement. Provisional status survives unchanged.
- [ ] Run RED; implement strict standard-library validation with bounded4-panel data and explicit norm/inverse precision checks. Keep actual adjacency uncomputed. Add a labeled illustrative profile fixture clearly marked provisional, with no built-in production default.
- [ ] Run tests GREEN plus cootie object/orientation tests; commit `feat: validate explicit folded artwork profiles`.

### Task3: Runnable producer job export and audit

**Consumes:** `ArtworkLayout` from Tasks1/2 and one complete artwork-job template.
**Produces:** `build_artwork_job(layout:ArtworkLayout,template:Mapping)->dict` and `write_layout_export(layout,template,output_dir:Path,*,overwrite:bool=False)->Path` in artwork_export.py.

- [ ] Write `test_export_uses_existing_producer_schema`: preserve seed, one Truchet algorithm/pass ID, style controls and declared layers; replace domains with intrinsic crop polygons, transforms with panel assembled matrices, target IDs and composition_window with layout window. Explicitly set composition frame/continuous mode. Reject conflicting template geometry overrides rather than silently retain stale targets. Each panel's crop-bounds minimum is recorded as the return rebase offset.
- [ ] Write `test_deterministic_atomic_export`: JSON job/report and labeled SVG preview are byte-identical for identical inputs, profile settings/units are recorded, recipe dimensional values are unchanged, output cannot alias input, and failed overwrite preserves all prior bytes. Reject multiple passes/unsupported algorithms/unsafe filenames, unknown template sections, bad paths and output symlinks escaping the destination.
- [ ] Run RED; implement the exporter without importing viz_virtualserver. Write artwork-job.json, layout-handoff.json and layout-preview.svg through a staging sibling and existing atomic-write conventions. Sidecar includes schema_version1, producer job SHA256, panel IDs/canvas/crop/rebase/matrices, bindings, resolved settings and validation status. Bound JSON/preview size and identifier lengths before allocation.
- [ ] Add CLI flags `--layout booklet-spread|cootie-folded-outer`, `--sheet-size`, `--spread LEFT RIGHT`, `--margin-mm`, `--gutter-mm`, `--square-size-mm`, `--profile`, `--job-template`, `--output-dir`, `--overwrite`; reject inactive flags. Run tests GREEN and commit `feat: export assembled layout artwork jobs`.

### Task4: Restore returned crops to full canvases

**Produces:** `prepare_layout_assets(*,producer_bundle:Path,handoff:Path,output_dir:Path,overwrite:bool=False)->Path` in artwork_return.py; second CLI requires those paths explicitly. It never edits the original producer bundle.

- [ ] Write `test_restore_rebased_crops_without_refit`: source crop coordinates are rebased by the producer; translate retained vector content by the recorded crop minimum into the original full panel canvas. Output root viewport/viewBox and complete intrinsic-canvas metadata describe the full canvas. Keep top-level neutral layer groups in place; wrap their drawable children with translation so layer ordinals/IDs remain discoverable. Preserve IDs/provenance, defs and clip references without collisions. No crop offset is added twice.
- [ ] Add fixtures for sparse strokes, completely blank panels, nonzero origins, reflected assembled transforms and fractional offsets. Full canvas width/height and expected crop geometry must survive `inspect_svg_source` and booklet source loading regardless of path extents. Do not introduce invisible drawable carrier paths.
- [ ] Write `test_derivative_hashes_and_failure_are_honest`: validate every producer surface against its original manifest first; require complete one-to-one panel/domain mapping and matching handoff job hash/geometry settings. Reject modified/missing/foreign surfaces, unknown layers and unsupported SVG elements. Preserve original producer design audit as a separate immutable provenance file; create new `design.json` with existing logical-layer contract/catalog, updated surface records/hashes, and explicit adapter/source hashes. It must not masquerade as an unchanged producer geometry audit.
- [ ] Run RED; implement bounded XML/vector wrapping and canonical full-canvas metadata via existing source-contract utilities. Preserve source files bit-for-bit. Rehash exact derivative bytes and use atomic staging for all output/report writes; run strict manifest validation after writing staged outputs.
- [ ] Run tests GREEN plus logical-layer, source inspection and intrinsic-canvas tests; commit `feat: restore full canvases for generated artwork crops`.

### Task5: Bind returned assets to existing imposition

**Produces:** `build_layout_bindings(layout:ArtworkLayout,asset_paths:Mapping[str,str])->dict`, and `bindings.json` written alongside derivative assets. Booklet selected pages become individual page entries with exact full-canvas dimensions, `fit=contain`, margin_mm0 and gutter disabled; orientation remains existing page-to-sheet responsibility. Cootie bindings preserve the existing slot's sheet-orientation rules and full intrinsic canvases, without applying the assembled-view matrix again.

- [ ] Write `test_binding_avoids_double_settings`: selected spread entries map left/right assets to their original logical page numbers;8-1 is correct. Existing cell rotations/physical placement applied once. Crops remain M/G from Task1 even though return imposition margin/gutter are0. Cootie outer assignments retain original slot IDs and do not overwrite selector/reveal entries.
- [ ] Write `test_partial_binding_is_not_complete_manifest`: selected two-page and outer4-only exports are explicitly marked binding patches, with required remaining pages/slots listed. Missing assets/duplicate mappings fail. Do not emit a supposedly complete8-page or20-panel runnable manifest without all assignments. Existing full manifests stay untouched; document manual merge/explicit composition of these patches.
- [ ] Run RED; implement patch/report generation and verify applying it to a complete fixture manifest preserves unrelated assignments and the logical-layer catalog. No implicit cross-bundle catalog merge or asset copying from unrequested sources.
- [ ] Run tests GREEN plus old booklet/cootie rendering tests; commit `feat: bind assembled artwork assets without repeated fitting`.

### Task6: End-to-end reference validation, guide and PR

- [ ] Write `test_generated_crop_roundtrip_matches_resolved_spread`: a full reference authored directly in resolved assembled coordinates is split using existing crop/cell operations and compared with producer-partitioned, padded and single-page-imposed assets. Compare transformed vector geometry, not raster pixels. This is an already resolved authoring canvas; do not apply an arbitrary external source's contain/cover fit as a second reference transform. Cover nonzero margin/gutter, blank/sparse pages and8-1. Existing external full-source fitting behavior remains unchanged.
- [ ] Write `test_folded_profile_roundtrip_corner_labels`: explicit profile's labeled vectors go assembled->producer intrinsic crop->restored canvas->flat slot with correct corner/handedness and preserved provisional status. A negative matrix/offset fixture must fail deterministically. Keep fixture labels as vector strokes, not live SVG text in plotter inputs.
- [ ] Run local fixtures RED/GREEN. Add an opt-in cross-repository integration script that accepts `--viz-repo`/`--viz-python`, exports a real job, invokes merged producer CLI, prepares derivative assets, validates neutral layers and imposes a complete software fixture. Other pages/slots are explicit test fixtures, not fabricated user artwork. Do not add producer checkout/runtime dependency to normal commands or tests.
- [ ] Produce labeled assembled/crop/full-canvas/sheet SVG previews in preserved output folders and inspect rendered PNGs. Verify old booklet/cootie representative golden outputs unchanged. Document exact export->generate->prepare->bind->impose commands, units/pen-width conversion, crop offsets, provisional folded profiles and remaining page/slot assignments. Add sample recipe and explicit provisional profile under examples/assembled-artwork/.
- [ ] Run focused checks during development; request one fresh read-only whole-branch review on final code with the five Review Focus cases. Fix reproduced correctness issues with RED/GREEN. Run final full suite once after fixes, plus Ruff/diff checks. Do not repeat broad tests without material changes/failure evidence.
- [ ] Commit verified docs/examples, push feature branch and open a plotter-workflow PR against main. Preserve worktree/previews; do not merge. Report any unavailable physical orientation acceptance explicitly as deferred.

## Self-review and handoff

The approved canvas/crop ambiguity is resolved explicitly: producer domains are the
actual crop polygons, and the return adapter restores the recorded crop offset
into full intrinsic canvases. This avoids producer changes, new adjacency code,
carrier geometry and double fitting. Tasks1/4/6 prove that frame contract.
All spec sections map to Tasks1-6; each Review Focus case has an owning test.
Task2 requires an explicit profile and never supplies an unverified default.
Manifest/hash ownership is separated in Task4; incomplete bindings are labeled in
Task5. Export and preparation write derivative artifacts only. Native execution
preference is preserved. Await user review of this plan before implementation.
