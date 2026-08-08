# Hilbert hardware-validation fixture

This fixture records stable invariants from the successful three-pen DPX-3300
commissioning plot documented in `docs/HARDWARE_VALIDATION.md`.

`golden.penplan.json` is intentionally semantic: it fixes compact assignment to
physical slots 1-3 and gives every used slot an operator-visible label, but it
does not require particular colors or pen models.

`expected.json` records the hardware-level behavior worth preserving. Do not
add local paths, COM-port names, generated output paths, or a permanent HP-GL
hash. Those belong in per-run `.preflight.json` audit artifacts under `output/`,
not in the golden fixture.
