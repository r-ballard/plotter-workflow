# HAR-180 packing verification

Base revision: `ef9b298` (merged booklet object PR22).

- Full repository tests: 834 passed; 22 new HAR-180 checks.
- Changed Python files pass Ruff; diff whitespace checks pass.
- Independent read-only review found no actionable issues.
- Real one-, two- and three-copy neutral jobs passed HP-GL conversion and
  pen-plan, placement and tool-documentation preflight. The actual three-copy
  SVG was rendered and visually inspected. No transmission occurred.

The committed `examples/kaleidocycle/letter-N-up.json` files and
`scripts/generate_kaleidocycle_packing_samples.py` reproduce the previously
untracked study through the production packer. Test coverage checks the exact
physical widths, 0/90-degree materialized strokes, tabs, layer catalogs and
source contracts rather than pinning generated HP-GL bytes.

Prepared local jobs are retained in the original checkout at
`output/hardware-acceptance/har180-letter-packing/letter-N-up/sheet-001/front/`:
`design.svg`, `design.json`, imposition audit, pen plan, `design.proof.hpgl`,
resolved pen plan, placement report and preflight report. Generated output is
ignored and is not copied into other checkouts when merging.

## Windows output-root limitation

Three source-run sample generation attempts hit WinError 5 during existing
atomic directory publication: one initial worktree output root, its explicit
overwrite retry, and a fresh shared output root. Tests in fresh temporary
directories passed. A fresh temporary root also completed all real samples;
that successful pack was retained in the shared output location, and all three
jobs were converted/preflighted there. No automatic retry or publisher change
was added. Use a fresh explicit `--output-dir` if the local directory setup
prevents publication, and distinguish that error from packing failure.

## Validation limits

Packing uses rectangular occupied bounds and 0/90-degree rotations. It does not
interlock nets, infer physical folded orientation, or silently rescale assets.
Each width requires matching exported/prepared state assets. Centered single
output remains the default; top-left positioning is an explicit option.
Kaleidocycle duplex and registration guides are outside the front-only adapter.
