# J-card Format Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Native execution is the user's preserved choice. Steps use checkbox syntax for tracking.

**Goal:** Add verified 3–7-panel manufacturer J-card formats to the existing eight-panel workflow.

**Architecture:** Immutable named profile data owns dimensions and provenance. The existing object, configuration, placement, artwork and imposition paths consume one resolved profile rather than hardcoded eight-panel constants. All faces continue through the existing neutral producer and converter contracts.

**Tech Stack:** Existing Python, frozen dataclasses, Decimal/rational geometry, pytest, Ruff, SVG/XML and vpype. No new runtime dependencies.

**Spec:** [Approved profile design](../specs/2026-10-28-jcard-format-profiles.md).

## Execution evidence and rulings

The user supplied https://standardcassette.com/templates and kept TLS verification
strict. Six two-page PDFs downloaded with verification enabled; all twelve faces
were rendered and visually checked. New records use `standard-jcard-3-panel-v1`
through `standard-jcard-8-panel-v1`, preserving the NAC eight-panel default. The
[source record](../../reference/jcard-profile-sources.md) contains exact dimensions,
source hashes, rounded-label interpretation and guide allowance limitations.
This explicitly supersedes the planned NAC names for the new records below.

Native geometry/config and workflow tasks are committed at 30a13e2 and 555dc5f.
Final affected scope: **336 tests passed in 5.41 seconds**. Real unchanged viz
revision `6f992ae112e34c5d462c9059263f53f686a71c3a` generated both faces for all six
formats, restored/imposed with fit proofs under `output/jcard-format-samples/`.
Smaller-profile off-center flips and distinct front/back catalogs were also
checked. Physical sample plotting remains HAR-88; unrelated HAR-89 stays deferred.
One final fresh branch review follows; no hardware transmission occurred.

## Global Constraints

- HAR-90; plotter-workflow branch `feat/jcard-format-profiles`, retained isolated worktree `viz_virtualserver/.worktrees/jcard-object`, merged base `e3f3cb0`; design commit `29df920`.
- Explicit IDs `nac-jcard-3-panel-v1` through `nac-jcard-8-panel-v1`. No arbitrary panel-count option or truncation rule. Retain eight-panel default and current valid configs.
- No new profile is enabled until both manufacturer faces have been visually checked and its nominal geometry and reference allowances recorded. Do not infer PDF page dimensions as trim dimensions.
- Native front/back/both, independent/continuous artwork per face, fixed physical scale, both paper flips, optional guide ink, separate catalogs, blank masking and paired atomic publication stay intact.
- Derive panel count, trim W/H, safe limits, slots, seams, layout window and source coverage from the selected profile. Preserve all converter-required files and physical metadata.
- No physical/hardware gate, no unrelated HAR-89 work. Preserve worktree/artifacts; use scoped tests and one final fresh branch reviewer.

## Review Focus

1. A three-panel source must not acquire the eight-panel flap width even though most panel roles match; check geometry and reject cross-profile bundles.
2. Back-only and paired exports must remain byte-identical for every selected format, including sheet previews and converter sidecars.
3. Small-profile Letter/A4 fit must depend on enabled registration extrema and margins, not panel count or a hardcoded A3 assumption.
4. Every physical back panel must pair correctly after an off-center flip for both axes when total trim width changes.
5. A second-face error in a smaller format must preserve the prior full pair; empty/sparse artwork must retain its configured canvas and authoritative channels.

## Files and interfaces

| File | Responsibility |
| --- | --- |
| `docs/reference/jcard-profile-sources.md` | Independently checked nominal dimensions, face ordering, allowances, URLs/hashes and measurement evidence |
| `imposition/jcard_profiles.py` | Frozen `JCardProfile`, immutable records and strict `get_jcard_profile(profile_id)` |
| `imposition/objects/cassette_jcard.py` | Profile-driven native slots, dimensions and construction guides |
| `imposition/jcard_config.py`, `jcard_placement.py` | Profile selection, valid blanks/safe inset and profile-sized rigid placement |
| `imposition/jcard_artwork.py` | Profile-sized native canvases, validation, previews and stable requests |
| `imposition/jcard_impose.py` | Selected-profile source coverage, strict identity and exact-scale output |
| Existing `artwork_bindings.py`, `artwork_return.py` | Preserve generic dispatch; change only a demonstrated hardcoded J-card dependency |
| `tests/test_jcard_profiles.py`, existing `test_jcard_*.py` | Owned geometry/config/handoff/converter regressions |
| `examples/jcard/`, existing J-card docs/checklist | Complete configs, source table and physical sample instructions |

`JCardProfile` fields: `profile_id: str`, `widths_inch: tuple[Fraction, ...]`,
`height_inch: Fraction`, `roles: tuple[str,...]`, `safe_inset_mm: Decimal`,
`bleed_reference_mm: Decimal`, `source_urls: tuple[str,str]`,
`source_sha256: tuple[str,str] | None`. Derived read-only properties:
`panel_widths_mm: tuple[float,...]`, `trim_size_mm: tuple[float,float]`,
`panel_count: int`. A missing download hash is explicit, not invented.
`get_jcard_profile(profile_id: str) -> JCardProfile` raises ValueError for unknown
or non-string identities. Existing `PROFILE` can remain an eight-panel default
alias. `JCard(face="front", profile=PROFILE)` remains the public constructor;
dimensions become resolved instance properties. Update class-level consumers.

## Task 1: Complete authoritative measurement evidence

- [x] Retrieve/render both faces for 3–7 panels using the official URLs in the spec. Keep normal TLS verification. Browser-hosted authoritative renders are acceptable when local downloads fail; record the retrieval method and absent hashes honestly. Do not add PDF tooling as an application dependency.
- [x] Visually compare labels with trim/fold/safe/bleed geometry and reverse face ordering. Record per-profile widths, height, allowances and source provenance in `docs/reference/jcard-profile-sources.md`. Cross-check sums against labeled total extents. Investigate any rounding discrepancy instead of averaging it into nominal constants.
- [x] Pin known distinctions: three-panel labels are `[1, 1/2, 41/16]` inches, totaling `103.1875 mm`; four-panel labels `[17/16,1/2,41/16,40/16]` total `168.275 mm`; five-panel labels `[17/16,1/2,41/16,40/16,39/16]` total `230.1875 mm`. Verify heights/allowances visually too. Six/seven individual widths are not yet verified; the seven-panel front labels total `13.75 × 4` inches, which is a cross-check, not a substitute for seam measurements.
- [x] Gate: the evidence document must contain an explicit checked record for every new profile before Task 2 fixes constants. If an authoritative template remains unreadable or contradicts labels, continue unaffected measurement work and report the specific missing evidence; do not silently ship guessed values or reduce scope.
- [x] Review evidence links and arithmetic; commit the verified source record. No pytest is needed for this research-only task.

## Task 2: Profile registry, native geometry and physical controls

Consumes Task 1's checked dimensions; produces `get_jcard_profile()` and the
profile-driven existing `JCard`/configuration/placement interfaces above.

- [x] Add failing tests in `test_jcard_profiles.py` and existing object/config/placement files. Pin exact measured widths and totals from the evidence as literal expected values. Example: `JCard(profile="nac-jcard-3-panel-v1").trim_size_mm == (103.1875,101.6)` after height confirmation; ensure its first panel is `25.4 mm`, while eight-panel first panel remains `26.9875 mm`.
- [x] Cover all profile IDs and both faces: count, adjacency/no overlap, summed area, native IDs/roles and reversed back starts. Reject unknown IDs and nonexistent blank slots. Validate safe inset against the narrowest resolved panel and height. Test an off-center corner identity for every format and both flip axes.
- [x] Add Letter/A4 fitting cases and guide-extrema failures with the same trim; confirm no automatic sheet choice or scaling. Keep eight-panel Letter/A4 rejection.
- [x] Run the focused new nodes and observe unsupported-profile failures. Implement immutable checked records and derive geometry/validation/placement from them. Do not change generic booklet/cootie semantics.
- [x] Run `test_jcard_profiles.py`, `test_jcard_object.py`, `test_jcard_config.py`, `test_jcard_placement.py` plus `test_imposition_model.py` and `test_imposition_geometry.py`. Expected all pass; commit.

## Task 3: Profile-aware artwork, restoration and plot outputs

Consumes the resolved profile from Task 2. Existing public signatures
`resolve_jcard_layout`, `build_jcard_artwork_job`, `write_jcard_export` and
`impose_jcard` remain unchanged.

- [x] Write failing export/return/impose/integration tests for each new profile: native full canvas sizes and composition window, exact selected panel coverage, profile/face binding metadata, and correct rigid transform. Use at least one pair with different catalogs. Assert cross-profile source rejection even when some local panel dimensions agree.
- [x] Pin face-alone versus paired bytes for request, handoff, native/sheet previews, final SVG, design.json and design.imposition.json. Test sparse/all-blank selected faces, invalid source/hash and stale request failures. A second-face build failure must leave prior paired outputs unchanged.
- [x] Observe RED, then replace eight-panel constants and panel counts in J-card layout validation, diagnostics and imposition with the selected record. Keep strict canonical reconstruction of profile bindings and source dimensions. Retain neutral request adapters and the source/catalog/hash validation chain.
- [x] Run affected J-card artwork/impose/integration files and all existing `test_artwork_layout*.py`, preserved-layout and logical-layer contract checks. Confirm the existing converter accepts new-format jobs and preserves physical sheet placement. Commit.

## Task 4: Reproducible examples, operator documentation and final verification

- [ ] Add full JSON configuration examples for 3–7 panels using existing recipe files and complete inline recipes in the operator documentation. Show fitting smaller formats on Letter/A4, larger formats on A3/tabloid, both artwork modes, front/back/both, guide controls and blank assignments. Include exact per-profile table and labeled native/flip diagrams.
- [ ] Run actual unchanged viz generation, restoration and imposition for each new format. Generate guide-only proofs and paired artwork samples, render/inspect SVGs, and check conversion dry runs without transmission. Use an off-center smaller profile for both flip conventions. Record both repository revisions and retained output paths.
- [ ] Extend `docs/validation/jcard-samples.md` and HAR-88 with format-specific physical acceptance: measured trim/seams, stock/folds, orientation, duplex offset and case fit. Keep HAR-89 separate. Verify inline JSON, commands and local links; record that ignored output artifacts must be regenerated in another checkout.
- [ ] Final test scope: all `tests/test_jcard_*.py`, `test_artwork_layout*.py`, `test_imposition_model.py`, `test_imposition_geometry.py`, `test_imposition_source.py`, `test_preserved_physical_layout.py`, `test_logical_layer_contract.py`, `test_booklet_impose.py`, `test_cootie_impose.py`, `test_cootie_object.py`, `test_cootie_object_integration.py`, `test_command_layout.py`. Broaden only for actual changed consumers, not a full transport/generator baseline.
- [ ] Use existing plotter Python `C:/Users/hardcase/Documents/developer/codex-repos/plotter-workflow/.venv/Scripts/python.exe` and adjacent Ruff. Use a fresh retained output basetemp; elevated scoped runs may be necessary for observed Windows ACL failures. Record actual counts/durations/warnings. Run Ruff check/format for changed files and `git diff --check`.
- [ ] One fresh whole-branch review after implementation, scoped regressions for material findings, then push and open a plotter-workflow PR against main. Update HAR-90 with evidence and HAR-88 physical follow-up. Do not merge; retain worktree/artifacts.

## Self-review

The source-verification gate precedes every new geometry constant. The profile
record is the sole owner of widths/count/height; native and sheet coordinates
remain separate. All five Review Focus cases have owned tests. Generic artwork,
converter and transport contracts are reused, not redesigned. Physical proof and
the unrelated blank-viewport issue remain explicit backlog work. Native execution
and scoped verification preserve the user's existing workflow preferences.
