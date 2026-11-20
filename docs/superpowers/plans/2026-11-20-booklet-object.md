# Booklet object implementation plan

**Goal:** Make PocketMod8 a declarative object with equivalent existing outputs.
**Spec:** ../specs/2026-11-20-booklet-object-design.md
**Execution:** Inline, test-first, with final independent review.

- [x] Capture baseline outputs for all supported sheets and run relevant tests.
- [x] Add failing object tests against existing expected.json: eight slots,
  page reading frames, placement, facing spreads, guides and cell transforms.
- [x] Add `imposition/objects/pocketmod8.py`; delegate CLI constants, cell
  transforms, placement and guide geometry. Keep public entry points stable.
- [x] Add `imposition/booklet_artwork.py` using object semantics; preserve
  `artwork_layout.resolve_booklet_spread` as a compatibility wrapper and test
  that booklet geometry no longer imports a CLI module.
- [x] Add kaleidocycle fixture descriptor/index and organize physical proofs.
- [x] Compare regenerated output bytes with baseline, run booklet/shared
  regressions, lint and full repository suite; obtain independent review.

## Review focus

Check top-row 180-degree handedness, cover spread 8-1, guide units and order,
all sheet sizes, source contracts, and downstream callers importing old constants.

## Execution evidence

Initial baseline: 123 booklet/shared tests passed. Added object tests failed
before implementation; CLI-import independence test stayed red until the
reading-spread module was extracted. Final focused set: 139 passed. Full
repository suite: 812 passed. Changed-file Ruff and diff whitespace checks pass.
All 12 captured SVG/audit/guide artifacts, across Letter, A4, A3 and Tabloid,
reproduced identical SHA-256 values after the refactor.

Independent read-only review found no important issues and independently ran
34 object/artwork tests successfully. The organized inspection ZIP retains the
HAR-179 SHA-256, and original outputs and uploaded attachment remain untouched.
No plotting or physical validation occurred.
