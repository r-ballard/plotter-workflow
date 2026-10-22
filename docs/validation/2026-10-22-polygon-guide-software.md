# Polygon-guide software acceptance ? 2026-10-22

Issue: HAR-10. Software checks pass; physical acceptance remains pending.

Validated source revisions: viz_virtualserver 7b18491 (merged PR46) and
plotter-workflow 8cf04bf (merged PR16). Documentation corrections in this branch
reflect the observed behavior. Runtime code was not changed.

## Environment and execution

Windows with the actual Git for Windows `bin/bash.exe`, portable uv 0.6.14 and
CPython 3.12.10. A fresh isolated `.venv` was created in each validation worktree
using locked dependencies (`uv sync --locked --all-packages` for artwork,
`uv sync --locked` for plotting). The portable `.tools` directory was explicitly
added to Git Bash PATH; Windows' system `bash.exe` is not the tested Git Bash.
No existing project environment was repointed.

The runnable command logs are retained under `output/guide-validation/` in each
worktree. Actual job/manifest/plan fixtures and generated bundles are retained in
`output/`; generated files are intentionally not committed. Plotter baseline:
564 tests passed in 9.31 seconds. Artwork-guide fixture regression: 1 test passed in 0.77 seconds; no new runtime code required a repeat of the 1913-test feature suite.

## Artwork generation

- `three-polygons.json` generated exactly square,triangle,pentagon surface SVGs.
- The same job generated twice produced byte-identical directory trees under
 `three-polygons-a` and `three-polygons-b` (`diff -r` exit 0).
- A repeated command without `--overwrite` failed and preserved every file hash;
 explicit overwrite regenerated the same hashes.
- `cootie-catcher.json` generated all 20 expected named surfaces.
- A custom job retained the three tutorial shapes and added an independently
 seeded square variant and arbitrary convex hexagon. A second surface reused
 the original square domain: six surface assets total. The independently named
 square domain produced different geometry; the reused domain is the same design.
- Individual source SVG polygon metadata and clip paths were checked. Each surface,
 the imposed artwork, separate guides, and neutral booklet were visually inspected.
 For a combined comparison, all embedded SVG IDs/references were namespaced to
 avoid cross-document clip-ID collisions. Source SVGs were not edited.

## Downstream software acceptance

The documented 20-surface generic cootie manifest imposed all 20 slots with 3 mm
panel margins on Letter landscape. Conversion used lower-left ANSI-D placement,
3 mm margin and absolute coordinates. Output includes artwork/guides SVGs,
imposition audit, HP-GL, placement report, schema-3 resolved pen plan and preflight
report. Imposition audit remains `orientation_validation:provisional`.

| Case | HP-GL pen order | Pen plan | Placement | Software send gate |
| --- | --- | --- | --- | --- |
| Generic cootie | SP1?SP0 | PASS | PASS | ready; unmanaged single pen |
| Neutral booklet warm | SP1?SP3?SP0 | PASS | PASS | operator confirmation required |
| Neutral booklet cool | SP2?SP4?SP0 | PASS | PASS | operator confirmation required |

The neutral case used the guide's `orbital-per-body.json` bundle and eight-page
fixture manifest. Every actual catalogue ID was assigned across two explicit
schema-3 passes. `orbits` was deliberately repeated and listed in repeated_layers;
no layers were silently omitted. Slot labels identify software fixtures, not
physically verified tools. Dry-run conversion created no HP-GL; actual conversion
created both named passes and their independent sidecars.

Preflight was run with `--write-report` and without `--confirm-pen-plan`.
The neutral reports retain `ready_to_send:false` and
`operator_confirmation_status:required-before-send`, despite successful command
exit. The generic single-pen report has undocumented carriage details and still
passes its unmanaged single-pen software gate; it is not a hardware inspection.
All HP-GL hashes were checked against the reports. Final pen selection is SP0;
these files end with `PU;SP0;IN;`, so SP0 is not literally the last instruction.

## Evidence inventory

Artwork worktree:
- `output/guide-validation/artwork-guide.sh` and `.log`.
- `output/guide-validation/artwork-validation.json`, custom job and explicit pen plan.
- `output/three-polygons*`, `output/custom-polygons`, `output/cootie-design-bundle`,
 and `output/neutral-booklet-bundle`.

Plotter-workflow worktree:
- `output/guide-validation/plotter-guide.sh`, `neutral-guide.sh` and logs.
- `output/guide-validation/software-validation.json` (hashes and gate results).
- `output/guide-validation/comparison.svg` (visual comparison).
- `output/cootie-production` and `output/neutral-booklet` (all artifacts/sidecars).

## Remaining acceptance

No serial port was opened, no pen/force confirmation was asserted, and no hardware
send or plot/fold was attempted. Folded orientation, pen pickup, real scale and
registration, repeat-job handling, force and recovery remain deferred under
HAR-10/HAR-14/HAR-26/HAR-52 as applicable. HAR-8/HAR-10 must not be marked fully
accepted from this software result alone. Docker is an optional alternative and
was not exercised; plotter runtime work remains tracked separately by HAR-9.
