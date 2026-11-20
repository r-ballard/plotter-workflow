# Kaleidocycle physical orientation diagnostics

Generate the diagnostic set from the kaleidocycle feature checkout:

```powershell
$python = '../../.venv/Scripts/python.exe' # linked worktree; otherwise .venv/Scripts/python.exe
& $python scripts/generate_kaleidocycle_orientation_fixture.py
```

The default destination is `output/kaleidocycle_orientation_validation`.
Use `--width-mm` to choose another net width and `--overwrite` to deliberately
regenerate the set. Default width is 240 mm on landscape Letter. These fixtures
use deterministic vector paths, including the existing cootie diagnostic glyphs;
no fonts, SVG text, raster images, or external generator service are needed.

## Plot 1: panel identification and orientation

Open `panel-orientation/sheet/design.svg` and the separate `construction.svg`.
The construction proof includes cut/fold lines and blank glue tabs. It excludes
the duplicate glue-area diagnostic outlines retained in `guides.svg`.
Each triangle contains:

- A two-part identifier such as `3B`: column 3, proposed state B.
- A long up arrow and a short right arrow with `R`, to expose reflections.
- An inset triangular border to check clipping and fold clearance.
- Vertex labels A, B, C in local polygon order (indices 0, 1, 2).
- One, two, or three short ticks on edges 0, 1, or 2 respectively.

Uppercase A-D in the main identifier denote the **proposed** viewing group;
small vertex A-C labels identify source geometry independently. Up/right arrows
on this first net describe the local flat panel frame, not a proven folded frame.
For example, `3B` corresponds to stable slot `column-3-b`.

Plot or print the guide layer in registration, cut and glue the net, and rotate
it through its views. Record which IDs actually appear together, their reading
directions, and which edges become neighbors. Do not assume state membership
from the main identifier alone. Photograph each observed view with a consistent
up direction, including the glued closure seam.

## Plot 2: declared assembled seam continuity

Open `state-continuity/sheet/design.svg`. Its source marks were authored in the
declared assembled frame and mapped back through each panel's inverse transform
before normal imposition. This exercises orientation and seam composition.

The proposed views contain a large up/right arrow frame, asymmetric crossing
lines, state letters A-D, and column numbers 1-8. Compare the assembled paper
with `state-continuity/expected-A.svg` through `expected-D.svg`. Those reference
views show software predictions, **not** physical ground truth. If the arrows,
numbers, or line continuations differ after assembly, record the mismatch and
correct the state profiles rather than altering the observation to fit them.

## Convert and preflight

Each net includes `sheet/design.penplan.json`, assigning its one `diagnostic`
logical layer to physical slot 1. From the feature checkout:

```powershell
$root = 'output/kaleidocycle_orientation_validation'
foreach ($mode in @('panel-orientation', 'state-continuity')) {
  & $python scripts/dpx3300_convert.py --input-dir "$root/$mode/sheet" `
    --output-dir "$root/$mode/sheet" --file design.svg `
    --page-size letter --landscape --paper-position lower-left --absolute
  & $python scripts/job_preflight.py "$root/$mode/sheet/design.diagnostic.hpgl" `
    --write-report
  & $python scripts/dpx3300_convert.py --input-dir "$root/$mode/sheet" `
    --output-dir "$root/$mode/sheet" --file construction.svg `
    --page-size letter --landscape `
    --paper-position lower-left --absolute
  & $python scripts/job_preflight.py "$root/$mode/sheet/construction.hpgl" `
    --write-report
}
```

This creates local HP-GL files; it does not transmit them. The adjacent plan is
discovered automatically. Check pen-plan and placement results before plotting.
The Python environment's `Scripts` directory must be on `PATH` so the converter
can launch `vpype`; activate that environment before running conversion.
Construction guides remain separate so they can be plotted with the intended
tool or printed as a cutting reference. `net-preview.svg` contains display text
and is not the plot input. The actual `design.svg` diagnostics use only paths.

## Record the physical result

Copy `physical_validation.template.json` to a separate observation file and fill
in each panel's observed state, top and right feature, left/right neighbors, and
notes. `validation.json` preserves the provisional declared seam pairs for
comparison. Leave the template untouched for repeatable future checks.

The fixture source audit explicitly records `algorithm_executed:false` and its
diagnostic generator. The shared recipe exporter is used only as a validated
handoff envelope; the artwork is deliberately constructed diagnostic geometry,
not a Truchet result. Both nets pass through the ordinary return adapter,
kaleidocycle imposer, neutral-layer catalog checks, and converter clipping.

A passing software test does not promote physical validation status. Resolve
panel membership, adjacency, orientation, and closure against the folded sample
before accepting any profile. Mountain/valley assignments and the assembly
sequence still follow the supplied reference.

Physical inspection is tracked separately in
[HAR-179](https://linear.app/hardcase/issue/HAR-179/physically-inspect-kaleidocycle-diagnostic-plots).
It does not block the software PR. Plot the diagnostic artwork and construction
proof as separate pen passes without moving the sheet between them. Both jobs
are marking/cutting-reference geometry; they do not command a cutter or scorer.
The construction plan documents an intended marking pen in slot 1; verify the
actual loaded pen before use. It does not prescribe a force setting.

## Software verification, 2026-11-20

Both generated artwork SVGs were rendered and visually inspected, and the A
reference view was checked. Both HP-GL jobs passed pen-plan and placement
preflight using physical slot 1, Letter landscape, and lower-left placement.
No transmission occurred. The full repository suite passed (685 tests), lint
passed, and independent review found no important issues. The diagnostic test
checks 32 imposed panels per net, vector-only labels, converter materialization,
eight panels per reference, blank observation fields, and deterministic
regeneration with explicit overwrite. Physical fold acceptance remains pending.

## Prepared inspection jobs

A fresh retained set is in `output/kaleidocycle-physical-inspection/`. It contains
both diagnostic impositions, four A-D references, an observation template, and
two preflighted jobs per sheet: `design.diagnostic.hpgl` and `construction.hpgl`.
All four jobs passed pen-plan and placement checks; construction tool
documentation also passed. The original diagnostic folder remains available.
To regenerate this set, add `--output-dir output/kaleidocycle-physical-inspection`
to the generator command and use that root in the conversion commands.

Keep the sheet registered while plotting artwork and construction as separate
jobs. Inspect the SVGs, intended slot-1 pen and paper placement before sending.
No job has been transmitted. Generated outputs are ignored and are not copied
to another checkout by merging; regenerate them from the tracked scripts.
