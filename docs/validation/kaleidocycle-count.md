# Parameterized kaleidocycle software validation

Implementation base: `79c8f7972640564322710b1cd0d0426532b2018c`.
Branch: `feat/kaleidocycle-count`. This report accompanies the implementation
commit and its tests. Physical validation and folded-view acceptance remain
with the owner; all generated views remain provisional.

## Execution record

- Baseline affected tests: 36 passed in 11.22 seconds.
- New count regression before implementation: 19 failed in 0.16 seconds,
  due to the missing parameter/default behavior.
- Affected regression after implementation: 70 passed, one historical eight-cell
  test failed because its config omitted the count. Updated that config to eight.
- First full verification: 869 passed in 31.57 seconds.
- Final full verification after the review fix: **870 passed in 30.78 seconds**,
  exit 0, no warnings reported.
- Independent read-only review found one metadata normalization omission:
  re-exporting a legacy eight-cell profile omitted count in the new handoff.
  Regression `test_export_legacy_profile_records_explicit_count` failed with
  missing `tetrahedron_count`, then passed after the shared exporter fix.
- Changed Python files pass Ruff lint and formatting checks. A broader lint
  probe found 19 pre-existing findings in unrelated files; those were not edited.

Full pytest command (from this worktree, using the root environment):

```powershell
& ../../.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp tmp/final-suite
```

Local full output is `final-suite.log`; initial and intermediate runs are in
`baseline-tests.log`, `baseline-focused.log`, `count-red-verified.log`,
`affected-cached.log`, `full-suite.log`, `review-red.log`, and `review-green.log`.
The initial sandboxed baseline had Windows temp-directory access failures
(13 failed, 373 passed, 460 setup errors); a local-temp retry lacked its parent
directory. Baseline and final verification ran with working Windows permissions.
One intermediate run hit a transient atomic-directory rename permission failure;
the full rerun passed. The first 1000-cell probe rebuilt slots repeatedly and was
stopped; immutable slots now cache their computed geometry.

## Compatibility and artifact checks

`tmp/verify_compatibility.py` compared explicit-eight slots, tabs, guides and all
four complete layout dictionaries against base `79c8f79`: exact equality after
removing the new count setting. It also checked that six/eight/ten/twelve-cell
cut guides each form one closed boundary. Output is in `compatibility.log`.

The existing diagnostic generator produced
`output/kaleidocycle-six/panel-orientation/sheet/net-preview.svg` at 240 mm width.
It labels 24 triangular faces; state assets, construction guides and observation
templates were produced through the existing export/return/imposition pipeline.
The new diagnostic regression verifies 24 labels, six-cell metadata, and blank
observations with `not-tested` status. No hardware was operated.

## Review rulings

- Treat the legacy export metadata omission as a required contract fix, despite
  the reviewer's Minor label: new handoffs must explicitly identify topology.
  Fixed with a failing-then-passing regression and full-suite verification.
- Physical closure, folding behavior, panel ordering, assembled-view accuracy,
  plotting and paper measurements remain owner validation. Accepting these from
  software checks would misrepresent the physical result.
- External producer behavior is bounded by existing repository contract tests;
  no live producer run or producer schema change is claimed.
- Artwork retains the shared 1000-panel-per-state limit; no unbounded resource
  promise is introduced by the count parameter.
- Remote ancestry and PR state are verified separately during the handoff.

No review findings were deferred.
