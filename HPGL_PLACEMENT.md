# HP-GL placement validation

`plotter-workflow` treats physical placement as separate from logical SVG layers and pen assignment. After vpype writes HP-GL, `hpgl_placement.py` audits the actual coordinates before a job reaches the DPX-3300.

## What is validated

Two envelopes are checked:

1. **Addressed motion bounds** — every explicit destination in `PA`, `PR`, `PU`, and `PD` must remain inside the selected `vpype.toml` paper profile (`x_range` / `y_range`).
2. **Drawing bounds** — every pen-down segment must remain inside that profile inset by the requested `--margin`.

The parser understands both absolute (`PA`) and relative (`PR`) coordinate streams, including mixed-mode HP-GL. The check therefore remains useful if `--absolute` is later omitted.

Validation is performed on generated HP-GL, not source SVG, so it audits the coordinates the plotter will actually receive after vpype layout and device-profile mapping.

## Units and margins

The DPX-3300 profile currently uses `plotter_unit_length = "0.025mm"`, so one millimetre is 40 plotter units. A `0.5in` margin is 12.7 mm, or 508 plotter units.

The validator reads both plotter-unit length and paper ranges directly from `vpype.toml`; page limits are not duplicated in application code.

## Placement sidecar

A successful integrated conversion writes:

```text
output/drawing.hpgl
output/drawing.penplan.json
output/drawing.placement.json
```

The placement report records the selected device/page profile, requested margin converted to plotter units, configured paper and margin envelopes, actual addressed and drawing bounds, coordinate modes encountered, and point/segment counts.

The sidecar is an audit artifact. The authoritative device geometry remains the selected `vpype.toml` profile.

## Failure behavior

Conversion fails before hardware transmission if generated coordinates exceed either the configured paper envelope or requested drawing margin. A two-plotter-unit tolerance is allowed for writer rounding.

This does not replace a first pen-up or sacrificial-paper test. Software can validate coordinate intent but cannot sense the actual sheet placement on the DPX-3300 bed.
