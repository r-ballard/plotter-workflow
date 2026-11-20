# Imposition backlog

## Kaleidocycle

The software workflow now supports named A-D assembled states, continuous
composition, and flat net imposition. Physically validate and correct the
illustrative viewing profiles using a labeled cut-and-fold sample.
This physical acceptance work is tracked separately in
[HAR-179](https://linear.app/hardcase/issue/HAR-179/physically-inspect-kaleidocycle-diagnostic-plots).

Later enhancement: directed transitions reference stable endpoint state IDs,
such as `from: A, to: B` (display label `AB`). Intermediate geometry requires
a separate motion model and is outside the initial implementation.

## Eight-page book object refactor: implemented and software verified

`imposition/objects/pocketmod8.py` now owns slots, orientation frames, placement,
guides and facing-spread semantics. `imposition/booklet_artwork.py` composes
reading spreads using the object. The CLI delegates while keeping existing
entry points and aliases. Initial verification reproduced all 12 baseline
artwork/audit/guide artifacts across four sheet sizes byte for byte. Full suite:
812 tests passed; independent review found no important issues. Evidence is in
the implementation plan. These changes are on the `feat/booklet-object` branch.
