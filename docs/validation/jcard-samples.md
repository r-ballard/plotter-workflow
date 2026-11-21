# J-card physical sample plots

## Standard Cassette 3–8-panel samples

The follow-on samples are retained under `output/jcard-format-samples/standard-N/`.
Each format contains `fit-proof/front/design.svg`, `artwork/front/design.svg`,
and `artwork/back/design.svg`, with converter sidecars beside each SVG. The
`export/` folder contains native and sheet previews for inspection, not plotting.

| Format | Sheet | Trim width (mm) | Trim height (mm) |
| --- | --- | ---: | ---: |
| standard-3 | Letter landscape | 103.1875 | 101.6 |
| standard-4 | A4 landscape | 168.275 | 101.6 |
| standard-5 | Letter landscape | 230.1875 | 101.6 |
| standard-6 | A3 landscape | 290.5125 | 101.6 |
| standard-7 | Tabloid landscape | 349.25 | 101.6 |
| standard-8 | A3 landscape | 406.4 | 101.6 |

All use left-right flipping and construction ink enabled. Start with the
guide-only proof. Measure trim/seams, cut and fold, then inspect stock and case
fit. For paired artwork, complete the front, idle the arm, manually flip and
register, then send the back as a separate job. Record results separately for
each profile in HAR-88; one format's proof does not verify the others.

The [complete configs, recipes and regeneration commands](../how-to/jcard-formats.md)
are tracked in Git. Generated output is ignored and retained locally; merging
does not copy it into a new checkout. Confirm the actual plotter usable area and
pen mapping. No hardware transmission has been performed.

## Original NAC eight-panel samples

All three SVGs are A3 landscape (420 x 297 mm). Trim is exactly 406.4 x 101.6 mm.

1. fit-proof/front/design.svg: guide-only cut/fold/registration proof. Plot on scrap, measure the 406.4 mm trim width and 101.6 mm height, cut, roll-fold extensions and check cassette case fit.
2. artwork/front/design.svg: continuous Truchet curves; title/spine intentionally blank.
3. artwork/back/design.svg: independent panel artwork with hatching.

The artwork pair uses LEFT-RIGHT flipping around the sheet's vertical axis. Complete the front job, idle the arm, flip/register the paper, and start the back as a separate job. Keep the sheet landscape. Registration is the asymmetric three-cross pattern.

Cut/fold/registration are separate logical channels. They are ink, not machine cutting instructions. For a one-pen proof map all wanted channels to one physical pen in your pen plan. The artwork back also contains the fill channel. Inspect each design.json catalog before conversion. Do not plot a diagnostic sheet-preview.svg.

Keep design.svg, design.json and design.imposition.json together in each face directory. Use the existing converter/preflight workflow with A3 landscape and preserved layout; do not fit to content or resize. Confirm A3 fits the configured plotter usable area. No HPGL was transmitted. These samples do not yet include dedicated vector panel-number/orientation glyphs like the cootie fixture.

Software converter dry run was checked for all three sheets. Hardware, registration and cassette-case fit remain physical acceptance tasks (HAR-88).

## Location and regeneration

The generated files are retained in the jcard-object worktree under output/jcard-physical-samples/. The output directory is ignored by Git; merging the PR does not install these generated files in another checkout.

To regenerate, follow docs/how-to/cassette-jcard.md with examples/jcard/both.json and set all three guides flags to true. Export, generate, prepare and impose the two artwork faces. For the guide-only proof, select front only, remove back_artwork, and put front-panel-1 through front-panel-8 in front_artwork.blank_panels. Reuse the complete prepared front bundle; all eight sources remain required. Keep the same A3 sheet and left-right flip convention.

Record measured trim size, fold positions, duplex offset, stock thickness and cassette-case fit in HAR-88. Physical plotting is deferred and does not block the software PR merge.


## Consolidated HAR-88 inspection pack

The current local handoff is `output/hardware-acceptance/jcard-inspection/`
in the plotter-workflow checkout. It contains all 21 jobs, `jobs.json`,
`verification.json`, and `physical-inspection.template.json`. Each job keeps
its authoritative SVG, manifest and imposition audit beside the explicit pen
plan, HP-GL, resolved plan, placement report and preflight report. Generated
files remain local; Linear records observations and links to repository
instructions. An archive upload is not required.

Start with `standard-3/fit-proof/front/design.svg` and its
`design.proof.hpgl`: Letter landscape, expected trim 103.1875 x 101.6 mm.
Copy the measurement template to an observations file, then record measured
trim/fold positions, stock, pen, case fit, duplex offset and photographs in
HAR-88. Inspect each profile separately. The prepared jobs cover left-right
flips; top-bottom/off-center coverage from HAR-88 remains outstanding.

### Prepare a regenerated job's proof plan

Regenerate the original samples using the instructions above. Keep the three
`design.*` source files together and preserve their bytes when collecting jobs
in the consolidated directory. From the repository root, run this Python
snippet with the virtual environment after setting `source` to one face SVG.
Repeat for each fit/front/back job. It uses the same drawable-layer inspector
as the converter: a catalog entry or SVG group can exist without drawable ink.
Assigning such an inactive layer to the proof pass fails preflight.

```python
import json
from pathlib import Path
from pen_plan import inspect_plan_layers
from scripts.dpx3300_convert import _neutral_context

source = Path("output/hardware-acceptance/jcard-inspection/standard-3/fit-proof/front/design.svg")
contract, _ = _neutral_context(source)
layers = inspect_plan_layers(source, catalog=contract.layers)
active = [layer.id for layer in layers if layer.active]
assert active, "No drawable layers in proof"
plan = {
    "schema_version": 3,
    "policy": "explicit",
    "passes": [{"id": "proof", "assignments": [
        {"layer_ids": active, "physical_slot": 1}
    ]}],
    "slots": [{"slot": 1, "tool": "Inspection marking pen",
               "label": "Single-pen paper proof"}],
    "omitted_layers": [layer.id for layer in layers if not layer.active],
    "repeated_layers": [],
    "notes": "Verify actual pen and sheet registration. Guides are marking ink. Force unmanaged.",
}
source.with_suffix(".penplan.json").write_text(
    json.dumps(plan, indent=2) + "\n", encoding="utf-8"
)
```

Confirm the actual marking pen occupies slot 1. Guide channels are ink;
this plan supplies no cutting, scoring or force setting.

### Convert and recheck the retained pack

Run from the repository root with the virtual environment activated (including
its converter dependencies on `PATH`). `jobs.json` supplies each job's sheet
size; preserve landscape orientation and scale. The explicit 3 mm margin
accommodates the existing registration marks on the widest A3 samples. The
`--overwrite` flag replaces generated conversion outputs in each job folder.

```powershell
$packRoot = (Resolve-Path output/hardware-acceptance/jcard-inspection).Path
$inspectionJobs = Get-Content "$packRoot/jobs.json" -Raw | ConvertFrom-Json
foreach ($job in $inspectionJobs.jobs) {
    $jobFolder = Join-Path $packRoot $job.folder
    python scripts/dpx3300_convert.py --input-dir $jobFolder --output-dir $jobFolder --file design.svg --page-size $job.sheet --landscape --paper-position lower-left --margin 3mm --absolute --overwrite
    if ($LASTEXITCODE -ne 0) { throw "Conversion failed: $($job.folder)" }
    python scripts/job_preflight.py "$jobFolder/design.proof.hpgl" --write-report
    if ($LASTEXITCODE -ne 0) { throw "Preflight failed: $($job.folder)" }
}
```

These commands convert and inspect files; they do not send them. Recheck after
any artifact or pen-plan change and before an attended plot. All 21 retained
jobs passed conversion and pen-plan, placement and intended-tool documentation
preflight during preparation on 2026-11-20. No serial connection or plotter
transmission occurred. Physical trim, folding, case fit and duplex registration
remain unverified.
