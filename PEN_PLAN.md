# DPX-3300 pen plans

`plotter-workflow` distinguishes **logical SVG layers** from **physical DPX-3300
pen slots**.

A `viz-virtualserver` SVG may declare logical layers such as `pen-1`, `pen-2`,
and `pen-6`. These identifiers describe the producer's layer organization. The
physical carriage still has slots 1 through 8, and a plot job may preserve the
logical numbers, compact active layers into the lowest slots, or explicitly map
logical layers to chosen physical slots.

This separation is important when a declared logical layer contains no drawable
geometry. For example, the plant L-system can declare logical `pen-1` for
initial generation 0 even though that generation contains only the rewrite
symbol `X`. There is then no reason to consume physical slot 1 unless the user
chooses a compact or explicit assignment that puts some active layer there.

## Pen-plan filenames

For an SVG named:

```text
input/plant_test_drawing.svg
```

an adjacent, user-authored plan is automatically discovered at:

```text
input/plant_test_drawing.penplan.json
```

You may instead provide a plan explicitly with:

```bash
--pen-plan path/to/job.penplan.json
```

After successful conversion, the converter writes the **resolved audit
sidecar** beside the HPGL output:

```text
output/plant_test_drawing.hpgl
output/plant_test_drawing.penplan.json
```

The output sidecar records the exact logical-to-physical mapping used, inactive
logical layers, expected tool metadata, and unused physical slots. It is an
audit artifact; the input format documented below is intentionally smaller and
simpler for a person to prepare.

## Input schema

The formal JSON Schema is [`penplan.schema.json`](penplan.schema.json).

A user-authored plan has this general shape:

```json
{
  "schema_version": 1,
  "policy": "compact",
  "slots": [
    {
      "slot": 1,
      "label": "black fine",
      "tool": "Sakura Pigma Micron 03",
      "color": "black",
      "notes": "0.35 mm"
    }
  ],
  "notes": "Load and test all pens before sending the job."
}
```

### `schema_version`

Required for user-authored plans. The current value is `1`.

### `policy`

One of:

- `preserve`
- `compact`
- `explicit`

The policy controls only physical pen selection. It does not alter drawing
geometry, page placement, scaling, or SVG colors.

### `slots`

Optional for conversion, but strongly recommended. Each entry documents what
the user intends to load in a physical DPX slot.

Supported fields are:

| Field | Required | Meaning |
| --- | --- | --- |
| `slot` | yes | Physical DPX carriage slot, 1 through 8 |
| `label` | no | Short human-facing identifier such as `black fine` |
| `tool` | no | Pen/tool model or type |
| `color` | no | Human-facing ink/color description |
| `notes` | no | Nib size, adapter, pressure notes, etc. |

`label` and `tool` are especially useful because `plotter-workflow` cannot
physically detect which pen is loaded in a slot. The preflight report compares
the resolved drawing assignment with this declared carriage plan.

### `assignments`

Used only with `policy: "explicit"`.

Every **active** logical layer must be assigned exactly once, and every physical
slot may be assigned to at most one active logical layer for a single job.

```json
{
  "schema_version": 1,
  "policy": "explicit",
  "assignments": [
    {"logical_layer": 2, "physical_slot": 8},
    {"logical_layer": 3, "physical_slot": 4},
    {"logical_layer": 4, "physical_slot": 1}
  ]
}
```

Inactive logical layers must **not** be listed. They contain no drawable
geometry and therefore do not generate an HPGL `SPn;` selection.

## Policy behavior

Assume an SVG declares logical layers 1 through 6, but logical layer 1 is empty:

```text
logical layer     active?
1                 no
2                 yes
3                 yes
4                 yes
5                 yes
6                 yes
```

### Preserve

```json
{
  "schema_version": 1,
  "policy": "preserve"
}
```

Resolution:

```text
logical 2 -> physical SP2
logical 3 -> physical SP3
logical 4 -> physical SP4
logical 5 -> physical SP5
logical 6 -> physical SP6
```

Physical slot 1 remains unused. This is backward-compatible with the original
SVG `pen-N` semantics.

### Compact

```json
{
  "schema_version": 1,
  "policy": "compact"
}
```

Resolution:

```text
logical 2 -> physical SP1
logical 3 -> physical SP2
logical 4 -> physical SP3
logical 5 -> physical SP4
logical 6 -> physical SP5
```

This is the convenient policy when you prefer to load the lowest carriage slots
without losing a slot to an empty logical generation.

### Explicit

```json
{
  "schema_version": 1,
  "policy": "explicit",
  "assignments": [
    {"logical_layer": 2, "physical_slot": 8},
    {"logical_layer": 3, "physical_slot": 6},
    {"logical_layer": 4, "physical_slot": 4},
    {"logical_layer": 5, "physical_slot": 2},
    {"logical_layer": 6, "physical_slot": 1}
  ]
}
```

This is useful when specific physical slots are already loaded with particular
pens or adapters.

## CLI-only assignment

A JSON plan is recommended for repeatable physical jobs, but policies can be
selected directly at the command line for experimentation:

```bash
--pen-policy compact
```

or:

```bash
--pen-policy explicit \
--pen-map 2:8,3:6,4:4,5:2,6:1
```

Do not combine `--pen-plan` with `--pen-policy` or `--pen-map`. An adjacent
`*.penplan.json` file is also authoritative; remove/rename it if you want to use
CLI-only assignment for that SVG.

## Preflight output

Before conversion, a multi-pen job prints a carriage-oriented plan similar to:

```text
Pen assignment policy: compact
Logical  Generations  ->  DPX slot  Expected tool / color
-------  -----------      --------  ---------------------
      2  1            ->         1  black fine / Micron 03 / black
      3  2            ->         2  red fine / Micron 03 / red
      4  3            ->         3  blue fine / Micron 03 / blue
      5  4            ->         4  green fine / Micron 03 / green
      6  5            ->         5  violet fine / Micron 03 / violet
Inactive logical layers (no drawable geometry): 1
```

Treat this as the carriage loading checklist. The program can validate that its
configuration is internally consistent, but **it cannot sense the tool actually
installed in a physical DPX slot**.

## Sending safety

For a contract SVG using more than one physical pen, `dpx3300_convert.py --send`
requires:

1. every used physical slot to have a `tool` or `label` in the pen-plan JSON;
2. `--confirm-pen-plan` on the command line.

This is intentionally stricter than conversion. You may always generate and
inspect HPGL with undocumented slots, but an automated multi-pen send should not
proceed without an explicit carriage plan.

Example:

```bash
uv run python dpx3300_convert.py \
  --input-dir ./input \
  --output-dir ./output \
  --file plant_test_drawing.svg \
  --page-size letter \
  --landscape \
  --margin 0.5in \
  --absolute \
  --overwrite \
  --send \
  --confirm-pen-plan
```

The adjacent `input/plant_test_drawing.penplan.json` is discovered automatically.

## Resolved output sidecar

The generated `output/<stem>.penplan.json` includes fields such as:

```json
{
  "schema_version": 1,
  "kind": "resolved-dpx3300-pen-plan",
  "source_svg": "plant_test_drawing.svg",
  "policy": "compact",
  "logical_layers": [
    {
      "logical_layer": 1,
      "active": false,
      "generations": [0],
      "preview_color": "#1f77b4"
    }
  ],
  "assignments": [
    {
      "logical_layer": 2,
      "physical_slot": 1,
      "generations": [1],
      "preview_color": "#ff7f0e",
      "tool": "Sakura Pigma Micron 03",
      "color": "black",
      "label": "black fine",
      "notes": null
    }
  ],
  "unused_physical_slots": [6, 7, 8]
}
```

The SVG preview color and the physical ink color are deliberately separate.
`preview_color` describes the producer's logical layer; `color` describes the
physical tool the user intends to load.
