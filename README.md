# DPX-3300 Plotter Project

A `uv`-managed Python project for converting SVG vector artwork to HP-GL and
sending HP-GL to a Roland DPX-3300 over RS-232.

The agreed hardware and machine settings are documented in
[`playbook.md`](playbook.md).

## Setup

```bash
uv python install 3.12
uv sync
```

## Convert

The repository includes `vpype.toml`, a DPX-3300-specific device profile with
two physical paper-placement modes:

- `--paper-position center` keeps the sheet centered around machine `(0, 0)`.
- `--paper-position lower-left` maps a supported landscape sheet to the
  lower-left corner of the DPX-3300 maximum plotting area.

The artwork is still fitted and centered *within the selected sheet*. The
placement option changes where that sheet sits on the machine bed.

For US Letter paper placed at the lower-left of the ANSI-D plotting area:

```bash
uv run python dpx3300_convert.py \
  --input-dir ./input \
  --output-dir ./output \
  --file drawing.svg \
  --page-size letter \
  --landscape \
  --paper-position lower-left \
  --margin 0.5in \
  --absolute \
  --overwrite
```

For Letter/Tabloid lower-left placement, set **SW-1 switch 7 ON** for ANSI-D.
For A4/A3 lower-left placement, set **SW-1 switch 7 OFF** for ISO-A1.

To return to the previously verified centered placement:

```bash
uv run python dpx3300_convert.py \
  --input-dir ./input \
  --output-dir ./output \
  --file drawing.svg \
  --page-size letter \
  --landscape \
  --paper-position center \
  --margin 0.5in \
  --absolute \
  --overwrite
```

`--absolute` is recommended for the first few jobs because it makes the HP-GL
coordinates easy to inspect. After the coordinate profile is verified, it may
be omitted to produce more compact relative-coordinate HP-GL.

Inspect the result before sending:

```bash
head -c 1000 output/drawing.hpgl
```

A centered Letter-landscape job with a 0.5-inch margin should normally contain
both negative and positive coordinates.

A lower-left Letter-landscape job should remain within the ANSI-D Letter paper
window `X=-17750..-6574`, `Y=-11180..-2544`. With a 0.5-inch margin, actual
drawing coordinates should remain approximately 508 plotter units inside those
edges.

Run the regression tests with:

```bash
uv run python -m pytest -v
```

Invoke pytest through `python -m` from the repository root. The project currently
uses top-level Python modules, so this keeps the repository root on the import
path consistently across platforms.

## Preflight before any hardware send

Conversion produces the HP-GL plus resolved pen-plan and placement sidecars.
Before transmitting a job, review all three together:

```bash
uv run python job_preflight.py output/drawing.hpgl
```

For a multi-pen job, physically verify the carriage against the printed plan,
then record that confirmation and write the audit report:

```bash
uv run python job_preflight.py \
  output/drawing.hpgl \
  --confirm-pen-plan \
  --write-report
```

The report is written as `output/drawing.preflight.json`. A normal hardware
send should proceed only when the report would have `ready_to_send: true`.
See [`JOB_PREFLIGHT.md`](JOB_PREFLIGHT.md) for the complete validation contract.

## Find the serial port

```bash
uv run python send_hpgl.py --list-ports
```

## Send

```bash
uv run python send_hpgl.py \
  --port /dev/cu.usbserial-XXXXXXXX \
  --confirm-pen-plan \
  output/drawing.hpgl
```

Windows example:

```powershell
uv run python send_hpgl.py `
  --port COM3 `
  --confirm-pen-plan `
  output/drawing.hpgl
```

`send_hpgl.py` re-runs unified preflight immediately before opening the serial
connection. Do not use `--allow-unvalidated-job` for normal plotter operation.

## Project files

- `dpx3300_convert.py` — SVG-to-HP-GL conversion with vpype.
- `booklet_impose.py` — physical imposition for one-sheet eight-page mini-books.
- `BOOKLET_IMPOSITION.md` — booklet layout, spread, guide, and conversion contract.
- `cootie_impose.py` — physical imposition for one-sheet cootie-catcher fortune tellers.
- `COOTIE_CATCHER_IMPOSITION.md` — cootie-catcher geometry, guide, and validation contract.
- `vpype.toml` — centered and lower-left DPX-3300 paper/coordinate profiles.
- `job_preflight.py` — unified HP-GL, pen-plan, and placement validation.
- `send_hpgl.py` — preflight-gated pySerial sender using 9600 8N1 and XON/XOFF.
- `JOB_PREFLIGHT.md` — pre-send validation and operator-confirmation contract.
- `playbook.md` — selected hardware, switch settings, operating procedure, and troubleshooting.
- `docs/HARDWARE_VALIDATION.md` — known-good physical commissioning record and golden-fixture policy.
- `pyproject.toml` — uv project metadata and dependencies.
- `input/` — source SVG files.
- `output/` — generated HP-GL files.

## Container workflow

Docker configuration is kept in `Dockerfile` and `compose.yaml`, not in
`pyproject.toml`. The Python project file declares Python metadata and
libraries; Docker files describe the operating-system image, bind mounts,
entrypoint, and optional serial-device access.

Build the image:

```bash
docker compose build
```

Convert every SVG currently in `input/`:

```bash
docker compose run --rm converter
```

Convert one SVG and override the Compose service command:

```bash
docker compose run --rm converter \
  dpx3300_convert.py \
  --input-dir /app/input \
  --output-dir /app/output \
  --file drawing.svg \
  --page-size letter \
  --landscape \
  --margin 0.5in \
  --absolute \
  --overwrite
```

The host `input/` directory is mounted read-only at `/app/input`. Generated
HP-GL is written through the `/app/output` bind mount into the host `output/`
directory. These job files are intentionally ignored by Git, while `.gitkeep`
files preserve the empty directory structure.

### Sending from a container

On native Linux, pass the serial device into the container:

```bash
docker run --rm \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  --group-add "$(stat -c '%g' /dev/ttyUSB0)" \
  --mount type=bind,src="$(pwd)/output",dst=/app/output,readonly \
  dpx3300-plotter:local \
  send_hpgl.py --port /dev/ttyUSB0 --confirm-pen-plan /app/output/drawing.hpgl
```

The optional `sender` service in `compose.yaml` demonstrates the same pattern.
Edit its device and filename first, then run:

```bash
docker compose --profile serial-linux run --rm sender
```

On macOS or Windows Docker Desktop, the USB serial device is normally attached
to the host rather than directly exposed inside ordinary containers. The
recommended workflow is therefore to run conversion in Docker and run
`send_hpgl.py` on the host with `uv`. Docker Desktop has a USB/IP mechanism,
but it is substantially more complex and requires privileged setup; it is not
the baseline workflow for this project.

## Multi-pen assignment and carriage plans

Multi-pen contract SVGs may preserve producer layer numbers, compact active
layers into the lowest DPX carriage slots, or explicitly assign logical layers
to physical slots. A user-authored `<stem>.penplan.json` next to the SVG is
discovered automatically. The converter writes a resolved sidecar next to the
HP-GL output and prints the carriage loading plan before conversion.

See [`PEN_PLAN.md`](PEN_PLAN.md) and [`penplan.schema.json`](penplan.schema.json)
for the full user-authored format, examples, and preflight rules.

