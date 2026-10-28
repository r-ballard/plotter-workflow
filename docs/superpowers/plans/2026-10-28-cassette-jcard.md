# Eight-Panel Cassette J-Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Native execution is already selected. Steps use checkbox syntax for tracking.

**Goal:** Export, generate, restore and impose single- or double-sided eight-panel cassette artwork as separate exact-scale plot inputs.

**Architecture:** A named J-card object owns native panel geometry. A paired placement resolver maps each face into one shared sheet datum and flip convention. Scoped adapters reuse neutral artwork export, crop restoration and logical-layer handling; per-face bundles remain separate.

**Tech Stack:** Python 3.11-3.13, frozen dataclasses, existing SVG/XML and vpype geometry, strict JSON, pytest, Ruff. No new runtime dependencies.

**Spec:** [Eight-panel cassette J-card](../specs/2026-10-28-cassette-jcard-design.md).

## Global Constraints

- Work in the isolated plotter-workflow worktree `.worktrees/jcard-object`, branch feat/jcard-object, baseline 79d619d. The directory is under the viz workspace; it is a separate Git repository. Do not implement on the stale root checkout.
- Only `nac-jcard-8-panel-v1`: trim W=406.4, H=101.6 mm; widths `[26.9875,12.7,65.0875,63.5,61.9125,60.325,58.7375,57.15]`. Preserve exact nominal constants before 96/25.4 conversion.
- Eight physical panels, sixteen possible face slots. Front order 1..8; back 8..1. Native artwork stays upright and is not mirrored.
- Faces front/back/both, default front. Required explicit sheet; centered front-reference origin unless supplied. Flip left-right/top-bottom, default left-right. No automatic scaling.
- Independent/continuous artwork separately per face, default independent. No unused opposite-side job or assignments. Same selected-face assets/bytes/seeds whether selected alone or with the other face.
- Safe inset default 1.5875 mm, guide only. Vendor bleed 3.175 mm is reference metadata, not artwork generation. Artwork clips to trim. Cut/fold/registration plot channels default off.
- Front/back remain separate producer catalogs and plot jobs, with a shared paired record. No hardware transmission, automatic paper flip, pause/resume or 3D folding implementation.
- Preserve old booklet/cootie handoffs, provenance, strict containment, blank dimensions, layer catalogs and atomic publication. No producer changes without a demonstrated generic-contract gap.
- Retain worktree/artifacts; focused RED/GREEN, affected subsystem checks, one final fresh reviewer. No mandatory full suite or hardware gate. File unrelated measured performance opportunities in Linear.

## Review Focus

1. Off-center placement must pair the same physical corners for both flip axes; centered examples alone can hide a wrong back transform (Task 2).
2. Back-only mode must produce the same back artifacts as both mode, without requiring front assets (Tasks 3-5).
3. Sparse or blank artwork must retain full physical canvas size and never trigger a new fit or centering operation (Tasks 3-4).
4. Per-face source layers can differ; no catalog merge or guide-ID collision may silently change pens/layers (Task 4).
5. A failure while building the second face must leave an existing complete published output unchanged (Tasks 3-5).

## Files and responsibility

| File | Responsibility |
| --- | --- |
| `imposition/objects/cassette_jcard.py` | Named profile, native face slots, exact constants and guides |
| `imposition/jcard_config.py` | Strict JSON selection, face recipes, sheet/placement controls |
| `imposition/jcard_placement.py` | Front datum, flip matrices, selected guides and registration |
| `imposition/jcard_artwork.py` | Per-face ArtworkLayout/job and atomic export orchestration |
| `imposition/artwork_bindings.py`, `artwork_return.py` | Scoped jcard-slot validation/restoration dispatch |
| `imposition/jcard_impose.py` | Exact-scale neutral face rendering, catalogs, paired output |
| `scripts/export_jcard_layout.py`, `scripts/jcard_impose.py` | Thin CLIs |
| `tests/test_jcard_{object,config,placement,artwork,impose,integration}.py` | Owned contracts and end-to-end checks |
| `examples/jcard/`, `docs/reference/cassette-jcard.md`, `docs/how-to/cassette-jcard.md` | Complete configs/recipes and operator workflow |

Existing artwork_export, artwork_layout and neutral fragment helpers are reused; modify them only for a bounded demonstrated need. Do not refactor the general SVG engine or old CLIs in this feature.

Test environment found during planning: `C:/Users/hardcase/Documents/developer/codex-repos/plotter-workflow/.venv/Scripts/python.exe`, with pytest/vpype/Ruff available. Commands below abbreviate this interpreter as `python`; use the resolved path in execution and the adjacent ruff.exe for linting. No pytest run is needed for this documentation-only plan.

## Configuration and artifact decisions

Use strict config schema_version=1 with keys `profile`, `faces`, `sheet`, `margin_mm`, optional `origin_mm`, `flip`, `safe_inset_mm`, `guides`, `front_artwork`, `back_artwork`.

- `sheet` is an existing named landscape sheet string or `{width_mm,height_mm}` with finite positive dimensions <=1e6. Resolve to SheetSpec. `margin_mm` defaults 0 and must leave a drawable rectangle. `origin_mm` is an explicit front-reference XY pair; reject partial/null/Boolean controls.
- `guides` has booleans `cut`, `fold`, `registration`, all false by default. Unknown keys fail.
- Selected `front_artwork`/`back_artwork` objects have `mode` (independent/continuous, default independent), `template` (config-relative recipe file) and `blank_panels` (default empty list of that face's slot IDs). Reject unselected-face objects, duplicate/foreign blanks and missing selected recipes.
- An explicit blank_panel suppresses that panel's artwork during imposition while retaining its canvas and source provenance. Every selected face still requires a complete eight-surface prepared bundle. Do not interpret a missing file as blank. Document this deliberate masking policy; no blank-producer special case is needed.
- Per-face exports: `front/` and/or `back/` each contain existing layout export artifacts. Their content/settings exclude global face selection and opposite-face data. Root `jcard-export.json` lists selected faces, hashes, profile and shared placement/flip. Publish the selected tree atomically.
- Final imposition uses selected `front/` and/or `back/` with `design.svg` and `design.json`, plus root `jcard-jobs.json`. Per-face manifests preserve their catalog/source/layout hashes and resolved physical placement; root record references both side files/hashes when both are selected. No empty opposite folder.

## Task 1: Named geometry and strict configuration

**Interfaces:** `JCard(face="front", profile="nac-jcard-8-panel-v1")` in cassette_jcard exposes object_id/schema_version, eight native normalized Slot records, exact `panel_widths_mm`, `trim_size_mm`, and `native_guides()` in trim-mm coordinates. Implement existing ImpositionObject placement/guide entry points for a native unflipped face; paired workflow uses Task 2 matrices, not implicit back fitting. `load_jcard_config(payload, *, base_dir) -> JCardConfig` in jcard_config returns frozen resolved fields and per-face recipe/blank records; `selected_faces -> tuple[str,...]` is stable front then back.

- [ ] Write geometry assertions for all widths, starts, W/H, front order, reversed back starts `W-x_i-w_i`, stable physical ID/role and face-specific slot IDs. Assert area sums, adjacent seams, no overlaps within a face and rejection of other profiles/count substitutions.
- [ ] Write strict config tests for front/back/both, named/custom sheets, default selection/flip/guides and relative recipe resolution. Reject unknown/malformed/Boolean/nonfinite controls, bad bounds, duplicate/foreign blanks, missing selected recipes and unselected-face assignments.
- [ ] Run `python -m pytest tests/test_jcard_object.py tests/test_jcard_config.py -q -p no:cacheprovider` with an existing plotter-workflow test interpreter. Expected: missing interfaces fail. Locate and record an existing environment containing pytest/vpype/Ruff; do not change packaging or use the viz-only environment by assumption.
- [ ] Implement profile and frozen config records. Use integer sixteenths of an inch times exact 25.4 mm constants as canonical geometry; convert once for floats/SVG. Do not depend on vendor PDF page dimensions or commit downloaded PDFs. Validate bounded shape/identities before copying; no universal profile registry.
- [ ] Run new files plus `tests/test_imposition_model.py`, `test_imposition_geometry.py`, `test_cootie_object.py`. Expected: all pass. Commit.

## Task 2: Shared sheet datum, flip matrices and guide channels

**Interfaces:** `resolve_jcard_placement(config) -> JCardPlacement` exposes front-reference ObjectPlacement, selected per-face affine matrices in mm, and immutable guide records. `face_matrix(face) -> tuple[float,...]` maps native trim mm into sheet mm. `face_guides(face) -> tuple[Guide,...]` supplies only enabled plot strokes; diagnostic guides are available separately.

- [ ] Write corner-set tests for all eight panels on centered/off-center A3, tabloid and custom non-square sheets. Left-right matrix is `(1,0,0,1,Sx-X-W,Y)`; top-bottom is `(-1,0,0,-1,X+W,Sy-Y)`. Front is translation `(X,Y)`. Assert determinant +1, exact scale, corner identity against physical paper flips and transform round trips. Back-only resolves the identical matrix as both.
- [ ] Test letter/A4 and insufficient margins rejection, explicit origin fit, safe inset collapsing the 12.7 mm spine, and guide/mark fit failures. No shrink, recenter or source-bounds fit. Test native asymmetric stroke/letter orientation rather than only bounding boxes.
- [ ] Run `tests/test_jcard_placement.py`; expected missing resolver failure. Implement pure arithmetic resolution with current finite/matrix checks.
- [ ] Define registration crosses with 1 mm half-arms at front sheet centers `(X-2,Y-2)`, `(X+W+2,Y-2)`, `(X-2,Y+H+2)`; map centers through the chosen physical flip for back. The three-corner pattern is asymmetric. All stroke extrema must fit drawable bounds, otherwise fail. Marks do not silently move. Diagnostic A/B/C text is preview-only.
- [ ] Native cut guide is one trim outline; fold guides are seven unique seams. Apply resolved face matrix once. Reserve neutral guide IDs `jcard-cut-guides`, `jcard-fold-guides`, `jcard-registration` only when enabled; reject enabled collisions with source layers in Task 4. Safe/bleed reference boxes are diagnostic only, never hidden plot ink.
- [ ] Run new object/config/placement files and existing geometry/orientation/source tests. Expected: all pass. Commit geometry controls and tests.

## Task 3: Per-face artwork export, bindings and crop restoration

**Interfaces:** `resolve_jcard_layout(config, face) -> ArtworkLayout`, `build_jcard_artwork_job(layout, template, *, mode) -> dict`, `write_jcard_export(config, output_dir, *, overwrite=False) -> Path` in jcard_artwork. Binding kind `jcard-slot` records profile, face, physical_panel_id and slot. Extend build_layout_bindings/apply_layout_bindings and return validation only for this family; old payloads remain exact.

- [ ] Write tests for eight local rectangular canvases per selected face, front/back native order, full-face continuous window, independent-domain mode, exact px/mm scale and stable surface/binding IDs. Assert front/back never share a producer canvas. Layout metadata must distinguish native face layout from later sheet placement.
- [ ] Test front-alone versus front-in-both and back-alone versus back-in-both byte/seed equality for each face export; opposite-face recipe must not enter the selected face identity. Reject wrong profiles/faces, stale hashes, foreign paths and mismatched bindings. Build a second-face failure and assert atomic preservation of an existing complete output tree.
- [ ] Run `tests/test_jcard_artwork.py`; expected missing export/binding behavior fails. Implement scoped cassette adapter: reuse current supported continuous Truchet recipe path; independent mode adjusts the standard domain-frame job recipe without weakening old build_artwork_job validation. Reject unsupported recipes explicitly.
- [ ] Extend binding/return dispatch with strict complete jcard face coverage and source/path/hash checks. Reuse prepare_layout_assets crop restoration and full-canvas dimensions; no scaling or sheet flip in this stage. Blank/sparse producer surfaces still restore dimensions and layer catalog. Physical blank declarations are applied only at Task 4.
- [ ] Reuse atomic_directory for one selected-face tree, protecting configs/templates/source dirs. Emit jcard-export.json hashes and reject unselected outputs. Existing producer/design/layout provenance remains authoritative.
- [ ] Run new artwork tests plus `test_artwork_layout.py`, `test_artwork_layout_export.py`, `test_artwork_layout_return.py`, `test_artwork_layout_bindings.py`, `test_artwork_layout_integration.py`. Expected: all pass. Commit.

## Task 4: Exact-scale neutral imposition and paired outputs

**Interfaces:** `impose_jcard(config, *, assets_by_face, output_dir, overwrite=False) -> Path` in jcard_impose. Each asset directory is the complete prepared neutral bundle for one selected face. Reuse existing logical-layer inspection and neutral SVG/vector fragment pair; do not introduce a second SVG parser. Return no hardware/HPGL transmission effects.

- [ ] Write tests that source canvas widths/heights match profile within 1e-6 mm, selected assets cover exactly eight face slots and each prepared bundle has one authoritative catalog. Reject foreign profile/face, swapped assets, stale hashes, dimensions or extra/unselected asset dirs. No general contain/cover scaling: correct source dimensions receive scale 1 plus resolved rigid transforms only.
- [ ] Pin sparse/all-blank dimensions, explicit blank masking, missing-file failure, single back requiring no front assets, both flips and same-side-alone/both SVG/manifest bytes. Use asymmetric local test strokes to assert upright native art and rotation without reflection on sheet. Preserve source/path IDs, logical channels and producer/layout lineage.
- [ ] Test different front/back catalogs without merging; preserve empty channels. Enabled guide-ID collisions fail. Guide stroke layers are appended deterministically only when selected; cut/fold/registration flags do not alter artwork geometry. Diagnostic text/bleed/safe boxes must not leak into design.svg.
- [ ] Run `tests/test_jcard_impose.py`; expected missing imposition fails. Implement exact-scale rendering with existing fragment helpers, trim clipping for both raw SVG and vector output, preserved layout marker/physical sheet units and canonical numeric serialization. No hidden carrier geometry for empty jobs.
- [ ] Build all selected face files before atomic publication. Root jcard-jobs.json records profile, flip, front-reference placement, selected face paths/hashes and each face manifest hash. Tampering or second-face build failure must leave prior files unchanged. Impose no unselected face and never start plotter transport.
- [ ] Run new impose tests plus neutral booklet/cootie and preserved-physical-layout consumers. Expected: all pass. Commit.

## Task 5: CLI workflow and real producer integration

**Interfaces:** `scripts/export_jcard_layout.py --config FILE --output-dir DIR [--overwrite]`; `scripts/jcard_impose.py --config FILE [--front-assets DIR] [--back-assets DIR] --output-dir DIR [--overwrite]`. Both expose main(argv=None), use config-relative recipe paths and delegate logic to modules. Reuse scripts/prepare_layout_assets.py separately per face.

- [ ] Write CLI tests for front, back and both, strict inactive flags, errors, protected paths, no partial publication and no unused side outputs. Export CLI prints selected per-face artwork-job paths; impose CLI prints selected plot inputs and root job record.
- [ ] Run `tests/test_jcard_integration.py` focused CLI nodes; expected missing commands fail. Implement thin CLIs and preserve existing command conventions. Do not add serial controls, a pause macro or a recipe orchestrator that automatically runs the second plot.
- [ ] Run actual viz_virtualserver generation using its retained current environment and merged source, then prepare assets and impose front/back/both. Cover independent and continuous modes, distinct face recipes, front-reference off-center placement, both flips, deliberate blanks, neutral pen channels and crossing-seam continuity. Record both repository revisions; no producer dependency install into plotter environment.
- [ ] Verify raw returned/imposed strokes remain in panel trim and artwork dimensions are exact. Add malformed producer hash/layout/side tests and second-face failure through the CLI. If a generic producer contract gap appears, record a narrow ruling before touching producer code; no cassette-specific generator.
- [ ] Run new integration file plus `tests/test_command_layout.py` and existing artwork return/integration tests. Expected: all pass. Commit CLIs and integration fixtures.

## Task 6: Complete docs, previews and deferred physical proof

- [ ] Add complete config/recipe examples for single front, single back and both (different recipes/modes), using explicit A3/tabloid sheet settings and optional off-center custom sheet. Include a valid blank-panel example and invalid small-sheet/foreign-face examples. No undocumented dependency on other example files: guides include their full JSON and exact commands.
- [ ] Write reference tables for exact dimensions, face/flip/mode controls, nominal safe guide and bleed limitation; explain eight panels versus sixteen possible surfaces. Add native panel diagrams, labeled asymmetric front/back sheet previews, both flip diagrams and guide-only previews. Record vendor URLs/hashes, never redistribute PDFs.
- [ ] Write end-to-end runbook: export, generate selected faces, restore assets, impose, inspect layer/pen mapping, finish first plot, idle arm, manually flip/register and send the second job. Explain that paper registration and case fit are not software-verified; no mid-job pause required. Guides are optional ink, not automatic cutting/folding.
- [ ] Execute all valid examples, invalid examples for stated reasons, inline JSON and local links. Render/inspect previews at physical scale and compare native panel/order/flip diagnostics to manufacturer PDFs. Confirm selected-face determinism, not only image similarity. No physical test run.
- [ ] Add a separate Linear backlog acceptance ticket for duplex registration, stock/folds and cassette-case fit, linked to HAR-87. Keep other J-card formats as future measured profiles; do not start them. Commit docs/examples and verification summary.

## Final verification and publication

- [ ] Run all new tests/test_jcard_*.py plus tests/test_imposition_model.py, test_imposition_geometry.py, test_imposition_source.py, test_preserved_physical_layout.py, test_logical_layer_contract.py and existing artwork_layout* files, test_booklet_impose.py, test_cootie_impose.py, test_cootie_object.py, test_cootie_object_integration.py, test_command_layout.py. Confirm exact filenames before constructing the command. Follow any newly changed neutral helper's callers to add affected tests; no mandatory transport/whole-suite run.
- [ ] Run relevant viz domain generation/partition/bundle checks only if producer code changes. For unchanged producer, real cross-repository fixture/examples provide handoff evidence; do not rerun its entire algorithm suite.
- [ ] Ruff check/format changed Python files and git diff --check. Record actual commands/counts/durations/warnings and omissions; scoped checks should be green before commit/publication claims.
- [ ] Request one fresh whole-branch review, supplying plan/spec, Review Focus, ledger rulings and both-repository verification evidence. Resolve material findings with focused failing regressions and repeat only checks invalidated by fixes. Preserve artifacts and ledger.
- [ ] Push feat/jcard-object and create a plotter-workflow PR against main, no merge. Update HAR-87 with PR, evidence and deferred physical acceptance ticket; keep In Progress until merge. Ball-and-stick algorithm work stays parked.

## Self-review

Checked spec coverage against six tasks: exact named geometry and strict selection; paired flips/guides; per-face handoff/restoration; exact-scale atomic imposition; CLI/real producer integration; self-contained operator documentation and deferred physical proof. Review Focus has tests in each owning task. Physical/native/producer coordinates are distinct, face identity is stable, and shared helper changes stay scoped. Blank handling is an explicit imposition mask, with all prepared source provenance retained. Native method and focused verification follow user preferences; wait for plan review before implementation.
