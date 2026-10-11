# Unified physical pen plans and DPX-3300 force (HAR-48)

## Status and intent

Concept approved October 11, 2026; written spec awaits review. The user prioritizes robustness in a personal workflow over backward compatibility. Use one authored plan schema and one resolved pass model, rather than a wrapper around old formats. Record expected physical force, encode it or require panel setup, and validate the reviewed job before opening the port. The eight-pen Micron example requests 65 gf; other jobs do not inherit that choice.

This belongs in plotter-workflow. Intrinsic geometry, logical SVG contracts, physical layout, and serial recovery retain their existing responsibilities.

## Verified device facts

The manufacturer tables were read and visually checked in the [DPX-3300 operation manual](https://lesporteslogiques.net/materiel/plotter_roland_DPX-3300/DPX-3300_operation_manual.pdf), PDF pages 47 and 146-147 (printed 3-11 and 7-38 to 7-39). Initialization behavior was checked on PDF page 151 (printed 7-43).

| Force, gf | Accepted FS codes | Generated code |
| --- | --- | --- |
| 20 | 1, 2 | 1 |
| 35 | 3, 4 | 3 |
| 50 | 5, 6 | 5 |
| 65 | 7, 8 | 7 |
| 80 | 9, 10 | 9 |
| 95 | 11, 12 | 11 |
| 110 | 13, 14 | 13 |
| 125 | 15, 16 | 15 |

Thus 65 gf is `FS7;`, not `FS65;`. An omitted pen number applies to all eight slots; `FS7,2;` targets slot 2. Argument-free FS resets to 20 gf. AUTO on overrides software force; AUTO off permits FS control. Panel settings work in either mode. Successful host transmission cannot establish actual force or AUTO state.

## One authored schema

Make schema version 3 the sole authored format. A strict object contains:

- `schema_version`: required, exactly integer 3.
- `policy`: required, `preserve`, `compact`, or `explicit`.
- `passes`: required for explicit policy, forbidden for automatic policies.
- `slots`: optional physical tool metadata using current slot/tool/color/label/notes fields.
- `omitted_layers`, `repeated_layers`: optional arrays of distinct nonempty layer IDs.
- `pen_force`: optional object below; omission means unmanaged force.
- `notes`: optional nonempty text.

Explicit passes have exactly `id` and `assignments`. Each assignment has exactly `layer_ids` (nonempty distinct string array) and `physical_slot` (strict integer 1-8). Use this form for both legacy pen-N SVG groups and neutral catalog IDs. Inspect the SVG to determine its contract rather than requiring the author to duplicate that classification. Legacy groups retain their existing string IDs.

Automatic policies yield one pass. Compact assigns active logical layers in source/catalog order to slots 1 onward. Preserve requires unambiguous pen-N IDs in the 1-8 range and uses their numbers; otherwise fail and recommend compact or explicit. Existing geometry import paths stay separate where necessary, but their physical planning uses one immutable model. Automatic policies may declare omissions; repeated layers require explicit passes.

Require complete active-layer accounting. Omitted or repeated layers must be declared; pass IDs are unique. Within a pass each active layer occurs once and each physical slot has one assignment, which may merge several layers. Repetition across passes requires a repeated declaration. Inactive declared layers do not require slots. Reject conflicting omission/repetition, unknown layers, duplicate slots, and incomplete assignments. Preserve deterministic source/catalog ordering.

Supported CLI policy/mapping controls construct this same model, not alternative resolved schemas. Reject contradictory CLI and file assignment choices. Without an authored plan, construct a schema-3 physical plan using the current documented CLI policy defaults; do not invent force.

```json
{
  "schema_version": 3,
  "policy": "compact",
  "pen_force": {"mode": "software", "default_gf": 65},
  "notes": "Load the reviewed Micron carriage; confirm AUTO is off."
}
```

## Force specification

The strict pen_force object contains:

- `mode`: required, exactly software or panel.
- `default_gf`: optional supported strict integer, applying to all eight slots.
- `slot_overrides`: optional array, default empty; entries have exactly slot (strict integer 1-8) and force_gf (supported strict integer).

Require a default or at least one override. Overrides replace the default and are canonicalized by slot. Reject duplicates, nulls, booleans, numeric strings, fractions, unsupported forces, and unknown fields. Overrides may cover slots unused in one pass, but every slot used anywhere in a force-enabled job must have an explicit effective force. An unspecified used slot is a resolution error, not an implicit hardware default.

Use a focused physical-force module for validation, gf/code conversion, effective lookup, and HP-GL application/state checking. Neither force nor pen-plan models depend on serial I/O or producer-side generation. All passes share the reviewed job specification; per-pass force differences are deferred.

## One resolved pass artifact

Use schema version 3 and kind `resolved-dpx3300-plot-pass` for every pass, regardless of input SVG contract. Keep current resolved-sidecar suffix and single-pass filename conventions. Each emitted pass has HP-GL, placement report, and resolved sidecar.

Required audit fields are schema_version, kind, source_svg, source_svg_sha256, source_manifest_hash (null without a manifest), pass_id, pass_number, pass_count, policy, assignments, physical_slots, omitted_layers, repeated_layers, slots, hpgl_sha256, and pen_force. Assignments use the shared layer-ID/slot form; slots carry applicable tool metadata. Pen_force is null for unmanaged jobs; otherwise it includes the canonical specification and effective forces for this pass's used slots. Validate effective forces by recomputation. Preserve job-level force settings in each pass. Exact internal signatures belong in the implementation plan.

Compute hashes after force insertion and final placement validation. Preflight checks final HP-GL hash, physical pen selections/order, force state, and source identities. Compare source hashes when source files/manifests are available; a moved source file does not become a new transport requirement. Reviewed HP-GL and adjacent sidecar remain the primary send artifacts.

## Force command application and validation

Software mode emits the global setting, if present, followed by ascending overrides. Place this block after initialization and before drawing. Reapply after supported IN/DF resets so later initialization cannot lose the expectation. Every independently sent pass sets its own force. Do not change pen selections, layout, geometry, coordinate modes, or velocity.

Use command-aware HP-GL parsing that honors label terminators; do not match apparent IN/FS text inside labels by regex. Track force state and check expected force for the selected physical slot at each pen-down operation, including motion while already down. Accept equivalent paired FS codes when validating external HP-GL; generate canonical odd codes. Reject malformed, unsupported, or conflicting preexisting force commands rather than guessing whether they are harmless. Identify affected commands/slots in errors.

Panel mode inserts no FS and rejects preexisting FS that could undermine operator settings. Require AUTO on in this mode: the manual states that IN resets force when AUTO is off but leaves it unchanged when AUTO is on. The operator applies panel force with AUTO on and confirms both before send. It records expected panel force, not software-applied force. Unmanaged jobs retain ordinary HP-GL behavior and get no injected FS or force confirmation requirement.

Apply force before placement reports, hashes, and atomic publication. Placement validation treats FS as non-motion state. Dry-run describes intended commands/setup without changing files or hardware. Preserve prior output if any pass fails conversion, validation, or publication.

## Preflight and confirmation

Print expected gf beside each used slot and explicitly name the mode. Software output says FS is encoded and AUTO must be off. Panel output says AUTO must be on and the operator must apply the displayed settings. Serial write success never becomes measured or confirmed physical force.

Reuse `--confirm-pen-plan` to acknowledge the displayed carriage and force setup. Force-enabled jobs require it even with one pen. In software mode it asserts AUTO off; in panel mode it asserts AUTO on and panel settings applied. Update help to make this explicit. Review-only preflight may return an unconfirmed report with ready_to_send false; a send fails before port opening if required acknowledgement is absent.

Preflight records expected specification, effective used-slot forces, mode, and operator-confirmed-auto-off, operator-confirmed-panel-settings-auto-on, or required-before-send status. Unmanaged force is marked as such. Existing no-force single/multi-pen confirmation semantics remain. Legacy bypass flags cannot waive force checks or confirmation for a force-aware sidecar. A found invalid/stale sidecar is not treated as no sidecar. Recovery sends no artwork, applies no force, and does not authorize plotting.

## Migration and scope

Reject authored/resolved versions 1 and 2 with actionable messages. Do not maintain wrappers, silent fallbacks, or parallel old/new resolvers. Migrate repository examples and fixtures and update penplan.schema.json. Document v1 numeric assignments becoming pen-N layer IDs and v2 passes becoming the shared explicit form. Retire fallback discovery of old generated .penplan.json sidecars; authored and resolved files retain their distinct suffixes. Reconvert old jobs to obtain reviewed current artifacts. Never automatically rewrite personal files or upgrade sidecars during send.

Preserve geometry and physical placement across migration. Refactor only physical planning and validation paths needed for this contract. No new dependencies, telemetry, AUTO switching, calibration, producer changes, or physical plotter commands during development. HAR-47 remains separate; integrate its sender/recovery changes when available and retain its operational tests. Preserve worktrees and previews.

## Acceptance and validation

Test all forces/equivalent codes, strict types, override ordering, missing used-slot force, overrides across passes, assignment accounting, and both SVG modes against the same records/serializer. Pin stale-version rejection and migration examples. No wrapper or old resolved format can be mistaken for a current plan.

Conversion fixtures cover global/slot command order, reset reapplication, command-like labels, malformed/conflicting FS, panel no-FS output, unmanaged output, source/final hashes, placement invariance, dry-run, and multi-pass rollback. Audit tampering or incorrect force must fail even with an updated HP-GL hash.

Preflight/sender tests cover one/many pens, both modes, missing acknowledgement, bypass flags, stale/invalid sidecars, carriage output, and rejection before port open. Retain geometry, placement, conversion, command-layout, and HAR-47 regressions; adapt schema fixtures deliberately without weakening their assertions. Run full tests and focused lint.

Update schema, pen-plan reference, sender/converter help, and runbook. Provide eight-slot Micron software/panel examples. Explain requested, encoded, operator-confirmed, and actual force; recheck after power cycles. A small supervised line test remains separate hardware acceptance. One fresh whole-branch review follows native implementation before a PR; do not merge.
