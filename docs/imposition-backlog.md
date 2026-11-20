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

## Eight-page book object refactor

Extract `pocketmod8` layout from `scripts/booklet_impose.py` into a declarative
object in `imposition/objects/`, reusing shared slots, orientation, placement,
guides, and assembled composition mechanisms. Retain the existing CLI and
manifest behavior, page order and rotations, supported spreads, sheet sizing,
logical layers, provenance, and output contracts. Verify equivalence against
the existing booklet fixtures. This remains separate backlog work.
