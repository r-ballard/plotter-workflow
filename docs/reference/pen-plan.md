# Unified DPX-3300 physical pen plans

Use authored schema **3** for legacy pen-N SVGs and neutral logical-layer SVGs. Both resolve to the same physical-pass audit format. Logical IDs describe artwork; physical slots 1-8 describe carriage positions. Force belongs here, not in viz_virtualserver geometry or SVG layer metadata.

## Files and policies

For input/drawing.svg, the authored plan is input/drawing.penplan.json, or supply it with --pen-plan. Conversion produces HP-GL, placement JSON, and a .resolved.penplan.json audit. Automatic single passes use drawing.hpgl; explicit passes use drawing.<pass-id>.hpgl. Authored and resolved files are distinct formats and suffixes.

```json
{
  "schema_version": 3,
  "policy": "compact",
  "slots": [{"slot": 1, "tool": "Micron", "label": "black fine"}]
}
```

Policies:

- preserve uses physical numbers only for unambiguous pen-N identities in 1-8.
- compact assigns active layers in source/catalog order to slots 1 onward.
- explicit requires passes with layer-ID assignments, allows merging and multiple passes.

Empty declared layers do not consume slots. Over eight active layers require explicit merging or multiple passes. Without an authored plan, legacy pen-N input preserves numbers; neutral/generic input compacts. CLI --pen-policy/--pen-map construct the same model and cannot conflict with an authored plan. Neutral input uses JSON plans rather than legacy numeric CLI maps.

```json
{
  "schema_version": 3,
  "policy": "explicit",
  "passes": [
    {"id": "warm", "assignments": [
      {"layer_ids": ["orbit", "accent"], "physical_slot": 1},
      {"layer_ids": ["body-warm"], "physical_slot": 3}
    ]},
    {"id": "cool", "assignments": [
      {"layer_ids": ["body-cool"], "physical_slot": 2},
      {"layer_ids": ["orbit"], "physical_slot": 4}
    ]}
  ],
  "omitted_layers": ["registration-guide"],
  "repeated_layers": ["orbit"]
}
```

Every active layer must be assigned or explicitly omitted. Repeated layers across passes must be declared. No layer appears twice within one pass; each physical slot has one assignment per pass, possibly merging several layers. IDs and slots must be valid, unique where required, and present in the source. Optional slots record tool, color, label, and notes. JSON duplicate keys and unknown fields fail.

The formal [schema](../../penplan.schema.json) describes the JSON shape; runtime additionally checks source accounting, strict numeric forms, and duplicate slot identities.

## Optional pen force

```json
"pen_force": {
  "mode": "software",
  "default_gf": 65,
  "slot_overrides": [{"slot": 2, "force_gf": 50}]
}
```

Default applies to all eight slots; overrides are physical-slot settings shared across passes. When force is enabled, every used slot must have an explicit effective force. No default plus incomplete overrides is an error. Omit pen_force for unmanaged force; there is no automatic 65-gf default for unrelated jobs.

| Nominal gf | Generated FS code | Equivalent accepted code |
| --- | --- | --- |
| 20 | 1 | 2 |
| 35 | 3 | 4 |
| 50 | 5 | 6 |
| 65 | 7 | 8 |
| 80 | 9 | 10 |
| 95 | 11 | 12 |
| 110 | 13 | 14 |
| 125 | 15 | 16 |

65 gf encodes FS7; FS7,2 targets slot 2. FS65 is incorrect. Values must be supported integers; strings, booleans, fractions, nulls, duplicate overrides, and unsupported forces fail.

Software mode encodes FS after initialization/resets and before drawing. Confirm AUTO is **off**. The force-state checker requires an explicit setting at every drawing operation, even for 20 gf; it does not assume a hardware default. Conflicting FS, unsupported drawing commands, and unsafe pen changes fail. Command-like text inside labels is tokenized correctly; convert text to vector paths before force-managed HP-GL drawing.

Panel mode emits no FS. Set AUTO **on** and apply the requested panel forces, then confirm both. The manufacturer states IN can reset force when AUTO is off, while AUTO on preserves it. Panel jobs containing FS are rejected.

`--confirm-pen-plan` acknowledges carriage loading and this mode/setup. Force-aware jobs require it even with one pen; bypass flags do not waive it. Preflight reports expected/encoded/operator-confirmed force, never measured force. The sender cannot read actual AUTO state or pressure.

See [software Micron example](../../examples/penplans/micron-eight-software.penplan.json) and [panel example](../../examples/penplans/micron-eight-panel.penplan.json). Both document eight tools with one job-wide 65-gf setting. Recheck setup after power cycling and run a small sacrificial line before a full job.

Source: [DPX-3300 operation manual](https://lesporteslogiques.net/materiel/plotter_roland_DPX-3300/DPX-3300_operation_manual.pdf#page=146), PDF pp.47,146-147,151. Nominal force is not a measurement of contact pressure or a recommendation for every pen/paper.

## Resolved audits and preflight

Each resolved audit uses schema3 and kind resolved-dpx3300-plot-pass. It records source SVG/hash, nullable source-manifest hash, pass identity/count, shared assignments and physical slot order, omission/repetition, applicable tool metadata, final HP-GL hash, and optional force spec/effective-slot values.

Preflight recomputes HP-GL hash, pen order and force state; matching hashes alone do not excuse wrong force. Available source SVG/manifest hashes are checked. Current placement is independently revalidated against the report. Moved source files are not a new requirement for sending reviewed HP-GL/audits.

```powershell
python scripts/job_preflight.py output/drawing.hpgl --confirm-pen-plan --write-report
python scripts/send_hpgl.py --port COM4 --confirm-pen-plan output/drawing.hpgl
```

Port recovery sends no artwork and sets no force. It does not authorize restarting a partially drawn job.

## Migrate old plans

Versions 1 and 2 are rejected; regenerate resolved audits by reconverting the SVG. No runtime wrapper or fallback reader is retained. Do not edit a sidecar version number to disguise an old payload.

For v1 authored plans, set schema_version 3. Preserve/compact policies and tool slot metadata keep their meaning. Replace explicit numeric assignments with a passes array and layer_ids strings: logical_layer 2 becomes layer_ids ["pen-2"]. Choose a pass ID such as plot.

For v2 authored plans, set schema_version 3 and policy explicit; keep passes, logical string IDs, omissions, and repetition. Add slot/tool metadata and optional force deliberately. The repository example plans are already migrated.

Old generated .penplan.json sidecars are not discovered as resolved audits. Remove/archive them yourself when appropriate and reconvert into .resolved.penplan.json. Found stale/invalid files fail explicitly. Personal files are not automatically rewritten by conversion or sending.

The supported HP-GL subset uses explicit semicolon termination, finite numeric motion/control arguments, and label terminators. Implicit mnemonic termination and embedded commands are rejected rather than interpreted incompletely.
