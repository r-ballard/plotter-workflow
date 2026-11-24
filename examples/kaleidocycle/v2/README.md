# Six-cell three-pack v2

The accepted artwork uses three 2D ball-and-stick compositions, each generated
once in the flat-net coordinate frame and partitioned into 24 triangular
surfaces. The styles are triangular vortex, flowing honeycomb, and irregular
connections. Each net is 161.291 × 65.30 mm on a three-up Letter landscape sheet.

The three JSON files preserve the exact producer requests, including all domain
geometry, composition transforms, seeds and parameters. Producer revision was
`a552442ac59c864c09f5dca3062fe96b280a982c`.

`generate.py` preserves the generation helper used for this iteration. Run it
from `.worktrees/kaleidocycle-count` with `PYTHONPATH=.` and the plotter Python
environment. It uses `../../../viz_virtualserver` and the previously generated
`output/six-cell-plot-pack` as its source of construction guides, diagnostics,
sheet metadata and pen assignments. Use a fresh output destination by editing
`ROOT` before regeneration. The helper expects Windows producer Python.

The prepared plotting artifacts are local under
`output/six-cell-plot-pack-v2-2d/`, packaged in
`output/six-cell-plot-pack-v2.zip`. Generation and packaging code are also
preserved in the local worktree's `tmp` directory.

The selected job is `sheet-proof/sheet-001/front/design.sample.hpgl` within that
pack. Its SHA-256 is
`6a3775dd414cc58c73c86ea5dec6cd35f3f71d65e4d262274e22a6c0e4d27de4`.
The exact HP-GL preview was visually inspected. Pen-plan and placement preflight
passed for Letter landscape lower-left, absolute coordinates, with a 4 mm margin
check. SP1 draws bonds, SP2 node outlines and SP3 construction guides. Operator
pen confirmation remains required before transmission. Force is unmanaged.

Diagnostics were copied byte-for-byte from v1. Verification confirmed three
producer jobs, 24 domains and 24 returned facet SVGs per job, composition-frame
generation, current HP-GL hash agreement with preflight, and ZIP integrity.
Ruff lint and formatting checks pass for the archived helper.

Physical plotting is the owner's next acceptance step. Folded viewing profiles
remain provisional. Follow the pack's README and the existing plotting guide
at `docs/how-to/plot-six-cell-ball-stick-kaleidocycles.md` for operator setup.
