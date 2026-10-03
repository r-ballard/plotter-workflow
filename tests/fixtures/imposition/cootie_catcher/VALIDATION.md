# Cootie-catcher physical validation fixture

This fixture exists to determine the final folded orientation table for the
`cootie_catcher` imposition. The current table is intentionally marked
`provisional`; passing software tests does not make the rotations physically
validated.

Each of the 20 vector-only source panels contains asymmetric geometry:

- a top arrow;
- a right-side marker;
- a bottom `V` marker;
- a kind glyph for outer, selector, or reveal; and
- a large vector digit identifying the slot index.

The asymmetry is intended to expose rotation, reflection, and selector/reveal
pairing errors after folding.

Before generating the hardware fixture, confirm the repository is green:

```bash
uv run python -m pytest -v
```

Generate a Letter validation sheet and separate construction guide with:

```bash
uv run python scripts/cootie_impose.py \
  tests/fixtures/imposition/cootie_catcher \
  --manifest cootie.json \
  --sheet-size letter \
  --square-position left \
  --guides \
  --output output/cootie_validation.imposed.svg \
  --overwrite
```

First inspect `output/cootie_validation.imposed.svg` and its
`.imposition.json` sidecar on screen. Confirm that all 20 semantic slots are
present and that artwork is clipped to its declared square or triangle.

Then convert and preflight the imposed SVG with the normal DPX-3300 workflow.
The guide SVG is a separate job and should remain separate from production
artwork. On a default Letter sheet the guide has exactly one trim line: the
right edge of the 215.9 mm square.

After plotting, cut the square out, construct the fortune teller, and record for
every semantic slot whether:

1. the expected slot appears in the expected physical location;
2. the top arrow is upright in the intended viewing state;
3. the right-side marker is not reflected; and
4. `selector-N` reveals `reveal-N` for all eight pairs.

Only after that physical check should `COOTIE_PANEL_ROTATIONS`, `expected.json`,
and `ORIENTATION_VALIDATION` be changed from provisional to a dated validated
state. Keep the fixture semantic; do not pin generated SVG serialization or
HP-GL bytes as the regression oracle.
