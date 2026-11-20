# PocketMod8 object refactor

Extract the existing eight-page booklet's physical semantics into a peer of
the cootie catcher, cassette J-card and kaleidocycle objects. This implements
the previously agreed backlog item without changing artwork or operator behavior.

The object owns normalized page slots, semantic up/right frames, the logical
page-to-cell map, full-sheet landscape placement, facing spread pairs, cell
placement operations, and cut/fold guides. Keep `scripts/booklet_impose.py` as
the compatibility CLI and retain its exported constants as aliases. Source
validation, SVG/vector serialization and logical-layer handling stay in their
current code. Move reading-spread composition into `imposition/booklet_artwork.py`
using the object; retain the existing artwork-layout function as a wrapper.

Approach: delegating the existing renderer is smaller and safer than replacing
it with a new generic renderer. A constants-only move would leave object
ownership incomplete. Use delegation plus regression checks against the current
outputs, including all four sheet sizes and the existing diagnostics.

Preserve page order, rotations, margins, gutters, generic/pen/neutral sources,
facing-spread behavior, provenance, audits, physical preserve-layout metadata,
CLI controls, filenames and separate guide layer/generation structure. Keep
imposition modules independent of CLI imports for booklet geometry and spreads.
Do not introduce new layouts, folds or paper-sizing behavior.

Organize kaleidocycle diagnostics with existing fixtures under
`tests/fixtures/imposition/kaleidocycle/` and physical proof output under
`output/hardware-acceptance/kaleidocycle/`. Retain existing files and the HAR-179
attachment; generated plot files stay ignored. Add a shared fixture index.
