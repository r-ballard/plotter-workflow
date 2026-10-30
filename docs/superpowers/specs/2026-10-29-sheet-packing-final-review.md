# HAR-91 final review and disposition

One fresh gpt-6-astra high reviewer inspected base `dd7c0ab` through `1a95c34`
read-only. It reviewed the whole production code, tests, design, plan, examples
and prototype, and ran small read-only probes. Its initial verdict was **with
fixes**: no Critical findings, three Important findings and three Minor findings.
There was no second review; regressions and affected checks verify the fixes.

## Important findings fixed

1. Opposite-diagonal gutter violations escaped shared final validation.
   Both occupied rectangles now receive the same positive-axis gutter expansion
   before intersection checks, matching the solver's rectangular-clearance rule.
   Regression: `test_final_validator_rejects_gutter_violations_at_all_diagonal_corners`.
   The first draft fixture used an unsupported result strategy; after correcting
   that test fixture, the opposite-diagonal cases failed for the intended missing
   rejection. All four corner/order cases now pass, including exact-gap acceptance.
2. Vertex accounting used cropped presence lines, while serialized SVG retained
   complete paths. Native preparation now counts unclipped retained shapes,
   including definitions, on a counting-only copy and caches the conservative
   count. Composition charges it before every duplicate. Actual asset regressions
   for artwork and unused definitions both failed before the fix and now pass:
   `test_retained_off_canvas_path_vertices_are_charged_before_duplication`.
3. Legal 200-character object IDs failed when expanded to 205-character instance
   IDs. Object IDs keep their documented limit; both instance records permit the
   derived suffix. `test_maximum_object_id_survives_expansion_and_packing` failed
   before the fix and now passes through actual config parsing, expansion and pack.

Focused final regressions: **7 passed in 0.72 s**. Final affected selection is
unchanged from the plan, plus these seven cases: **382 passed, three Windows
atomic-rename PermissionError failures in 6.96 s**. Those exact three nodes passed
in a fresh isolated temp directory: **3 passed in 0.69 s**. Total **385** selected
cases pass. No test warnings. Ruff check/format and diff checks passed.

Failed/retried nodes:
- `test_sheet_packing_jcard.py::test_native_preparation_has_no_sheet_dependency[back]`
- `test_jcard_artwork.py::test_native_export_and_restore[independent-front]`
- `test_jcard_profile_workflow.py::test_all_profile_faces_are_selection_independent_and_convertible[4]`

## Minor findings

- Deferred: subnormal library dimensions such as `1e-320` overflow grid capacity
  division. This boundary has no practical physical-sheet use; ordinary inputs
  and all supported J-card profiles are covered. No numeric-domain policy was
  expanded during this feature.
- Corrected documentation output table: detailed provenance/panel/instance audit
  is in `design.json`; `design.imposition.json` links that manifest by hash.
- Corrected corrupted symbols using ASCII ranges and multiplication notation.

Both real packing configurations were regenerated after the fixes. Every plot
SVG remained byte-identical to the visually inspected/converted version; only
work accounting changed (23774 vertices for two eight-panel cards, 31642 for the
mixed example). Both complete pen plans passed actual offline vpype conversion
with matching `--margin 3mm`, yielding separate artwork and guide HP-GL files.
All nine complete JSON examples match their inline documentation.

## Rulings and review limits

Ruling: Native PowerShell bookkeeping substitutes unavailable Bash skill helpers
- preserves ledger and task gates - requires manual bookkeeping care.

Ruling: Use the approved affected-scope testing policy, not generic full-suite
skill clauses - user preference - unrelated tests remain outside validation.

Final: Ruling: Correct reviewed documentation table/encoding during the approved
documentation task - user's explicit accurate self-contained plain-English
requirement - small docs-only expansion of the skill's minor-deferral policy.

Final: Ruling: Physical fit, plotting and duplex registration stay in HAR-88
- explicitly deferred by user - stock and registration remain physically unverified.

Final: Ruling: Polygon nesting, extra adapters and optimal sheet count remain
excluded - approved rectangular-first scope - unused corners and heuristic
inefficiency remain.

Final: Ruling: Accept executor visual inspection plus actual offline conversion
where reviewer sandbox could not read generated artifacts - all retained faces
and previews inspected locally - visual QA has no independent second inspection.

These last three items exhaust the reviewer's declined-to-judge list. No
Important or Critical finding remains unresolved. No hardware operations,
dependency additions, unrelated full-suite run or Linear writes were performed.
