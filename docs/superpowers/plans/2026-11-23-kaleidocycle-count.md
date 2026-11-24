# Kaleidocycle Count Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Support even tetrahedron counts of at least six, defaulting to six,
through the existing artwork and physical imposition pipeline.

**Architecture:** Count determines object geometry; `width_mm` determines total
physical net width. Carry count through existing requests and handoffs, keeping
packing exact-scale and all assembled views provisional.

**Tech Stack:** Python, pytest, SVG, existing neutral artwork contracts.

**Spec:** `docs/superpowers/specs/2026-11-23-kaleidocycle-count-design.md`

## Global Constraints

- Default count 6; even integers >=6 only.
- Total-net `width_mm`; preserve triangle proportions and object-owned guides.
- Preserve explicit-eight behavior and historical handoff interpretation.
- Physical validation and provisional-view acceptance remain with the owner.
- Base implementation on `docs/triangle-plotting` at `79c8f79`, containing the
  latest local triangular-artwork and plotting changes; verify remote ancestry
  before preparing a PR. Preserve unrelated working changes.

## Review Focus

- Missing versus explicit count in legacy handoffs: historical eight is retained.
- Mixed-count states/configs: fail before publishing output.
- Custom profiles: count and requested physical width must agree.
- Packing cache/footprint: differing counts cannot share a prepared request.
- Large counts: shared seams remain exact enough for producer validation.

### Task 1: Count-dependent object and artwork layout

**Files:** `imposition/objects/kaleidocycle.py`,
`imposition/kaleidocycle_artwork.py`, `imposition/artwork_return.py`,
`tests/test_kaleidocycle.py`, new `tests/test_kaleidocycle_count.py`.

**Interfaces:** `Kaleidocycle(tetrahedron_count=6)`;
`resolve_kaleidocycle_state(state, *, width_mm, tetrahedron_count=6)`.

- [x] Add tests for 6/8/10/12 cells, invalid inputs, normalized bounds, scale,
  legacy handoffs, count-aware return assignments, and canonical seam validation.
- [x] Run new tests with the repository Python environment and observe expected
  missing-feature failures.
- [x] Implement geometry, layout metadata and validation. Retain exact existing
  eight-panel fan coordinates; use shared deterministic endpoints for other fans.
- [x] Run object, artwork export/return, and count regressions.

### Task 2: Carry count through configuration and physical consumers

**Files:** `scripts/export_artwork_layout.py`,
`imposition/kaleidocycle_impose.py`, `imposition/kaleidocycle_native.py`,
`imposition/sheet_packing/config.py`, `imposition/sheet_packing/kaleidocycle.py`,
affected CLI, imposition, native-artwork and packing tests.

**Interfaces:** CLI `--tetrahedron-count`; config `tetrahedron_count`;
`KaleidocycleRequest` includes immutable count; renderer receives the resolved
count rather than constructing an unrelated default object.

- [x] Add failing tests for default-six export/imposition, explicit-eight output,
  invalid CLI/config counts, mismatched custom profiles and states, and packed
  six/eight footprints with distinct request identities.
- [x] Implement parameter propagation and count metadata in existing audits.
- [x] Run changed tests and affected artwork, imposition and packing consumers.

### Task 3: Preserve examples, produce diagnostic, and verify

**Files:** `examples/kaleidocycle/`, existing kaleidocycle sample/fixture scripts,
`docs/how-to/kaleidocycle.md`, `docs/how-to/pack-kaleidocycles.md`, affected fixtures.

- [x] Make historical eight-cell examples and generators explicit; document the
  six-cell default, sizing contract, and legacy handoff behavior.
- [x] Generate a labeled six-cell diagnostic preview through existing code and
  inspect face counts, tabs, bounds, and provisional labeling.
- [x] Run repository pytest and appropriate lint checks, saving full output to
  local logs. Record revision, exit code, counts, duration, and limitations.
- [x] Review the whole diff for count assumptions and compatibility; address
  findings, commit verified work, then push/open a PR per the lean workflow.
