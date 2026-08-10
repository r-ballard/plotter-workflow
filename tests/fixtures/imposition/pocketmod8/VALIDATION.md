# Pocketmod8 physical validation fixture

`validation_pages/` contains eight generic, vector-only SVG pages for checking
one-sheet imposition on real paper. Each page has:

- a rectangular page frame;
- an upward arrow at the logical top;
- a large seven-segment page number; and
- a small downward-facing `V` near the logical bottom.

Before generating the hardware fixture, confirm the repository is green:

```bash
uv run python -m pytest -v
```

Generate the validation sheet with:

```bash
uv run python booklet_impose.py \
  tests/fixtures/imposition/pocketmod8/validation_pages \
  --sheet-size letter \
  --page-margin-mm 6 \
  --output output/pocketmod8_validation.imposed.svg \
  --guides \
  --overwrite
```

Convert the imposed artwork with the normal DPX-3300 workflow, then run unified
preflight on the resulting HP-GL:

```bash
uv run python job_preflight.py output/pocketmod8_validation.imposed.hpgl
```

Plot the guide SVG separately if desired and preflight that job independently.
After plotting, cutting, and folding the validation sheet, verify that logical
pages read 1 through 8 in order and every top arrow points toward the top edge
of the finished page.

This is a semantic/hardware golden fixture. Do not commit generated HP-GL or
pin byte-for-byte vpype output as the regression oracle.
