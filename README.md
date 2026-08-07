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

Run the centered-origin regression tests with:

```bash
uv run python -m unittest discover -s tests -v
```

## Find the serial port

```bash
uv run python send_hpgl.py --list-ports
```

## Send

```bash
uv run python send_hpgl.py --port /dev/cu.usbserial-XXXXXXXX output/drawing.hpgl
```

Windows example:

```powershell
uv run python send_hpgl.py --port COM3 output/drawing.hpgl
```

## Project files

- `dpx3300_convert.py` — SVG-to-HP-GL conversion with vpype.
- `vpype.toml` — centered and lower-left DPX-3300 paper/coordinate profiles.
- `send_hpgl.py` — explicit pySerial sender using 9600 8N1 and XON/XOFF.
- `playbook.md` — selected hardware, switch settings, operating procedure, and troubleshooting.
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
  send_hpgl.py --port /dev/ttyUSB0 /app/output/drawing.hpgl
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
