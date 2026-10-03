# Plotter workflow

Convert vector SVG artwork to HP-GL for a Roland DPX-3300, inspect and preflight
the result, then send it over RS-232. This repository owns physical paper
placement, booklet and cootie-catcher imposition, pen assignment, conversion,
and transport. [`viz_virtualserver`](https://github.com/r-ballard/viz_virtualserver)
can produce neutral design bundles for this workflow.

## Redeploy on a workstation

Install Python 3.12 and `uv`, then from this repository's root run:

```powershell
uv python install 3.12
uv sync --locked
uv run --locked python scripts/dpx3300_convert.py --help
uv run --locked python scripts/job_preflight.py --help
uv run --locked python scripts/send_hpgl.py --list-ports
```

Run commands from the repository root. Operator commands live in `scripts/`;
the former root command paths have been removed. `vpype.toml` contains the
DPX-3300 device and paper-placement profiles. Use the [operating
playbook](docs/how-to/plotter-playbook.md) to configure the plotter and terminal
before any hardware send. Keep the terminal awake for the entire plot.

## Offline conversion and preflight

Place a vector SVG in `input/`. For a Letter landscape sheet at the lower-left
of the ANSI-D bed, run:

```powershell
uv run --locked python scripts/dpx3300_convert.py `
  --input-dir input --output-dir output --file drawing.svg `
  --page-size letter --landscape --paper-position lower-left `
  --margin 0.5in --absolute --overwrite
uv run --locked python scripts/job_preflight.py output/drawing.hpgl
```

Inspect `output/drawing.hpgl`, its placement report, and the resolved pen plan.
For multi-pen jobs, verify the actual carriage against the printed plan before
recording confirmation:

```powershell
uv run --locked python scripts/job_preflight.py `
  output/drawing.hpgl --confirm-pen-plan --write-report
```

The [preflight reference](docs/reference/job-preflight.md) describes the
sidecars and send gate. [Paper placement](docs/reference/hpgl-placement.md),
the [SVG pen contract](docs/reference/svg-pen-contract.md), and the [pen-plan
contract](docs/reference/pen-plan.md) define the input and output rules.

## Send to the plotter

After reviewing the job and preparing the plotter using the
[playbook](docs/how-to/plotter-playbook.md), find the serial port and send:

```powershell
uv run --locked python scripts/send_hpgl.py --list-ports
uv run --locked python scripts/send_hpgl.py `
  --port COM3 --confirm-pen-plan output/drawing.hpgl
```

Replace `COM3` with the port shown on your workstation. The sender runs
preflight again immediately before opening the port. Use a sacrificial sheet
for the first job after redeployment.

## Docker conversion

Docker runs the converter without requiring the host Python environment:

```powershell
docker compose build
docker compose run --rm converter
```

The converter reads `input/` and writes HP-GL plus sidecars to `output/`.
The Compose default is **Letter landscape, lower-left ANSI-D placement**;
change `compose.yaml` for a different sheet or placement. On Windows and macOS,
run `scripts/send_hpgl.py` on the host for the attached serial device. The
optional Compose sender profile documents a Linux serial-device setup.

## Documentation and examples

- [Documentation map](docs/README.md) links the operator guides, contracts,
  imposition references, and physical validation records.
- [First algorithm to plot](docs/how-to/first-algorithm-to-plot.md) walks from a
  seeded generator through preview and preflight.
- [Neutral logical-layer plotting](docs/how-to/neutral-logical-layer-plotting.md)
  connects a `viz_virtualserver` bundle to imposition and multipass plotting.
- `examples/` contains tessellation, patchwork, and Voronoi generators.

## Verify a redeployment

```powershell
uv run --locked python -m pytest -q
uv run --locked ruff check .
```

These are software checks. Follow the [hardware validation
record](docs/validation/hardware-validation.md) and the playbook for a physical
commissioning plot.
