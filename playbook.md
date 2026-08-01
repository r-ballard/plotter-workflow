# Roland DPX-3300 Operating Playbook

This document records the hardware and communication decisions selected for the
DPX-3300 project. Treat it as the baseline configuration for testing and normal
operation.

## Selected hardware

### USB-to-RS-232 adapter

- **StarTech ICUSB2321F**
- USB to RS-232 serial adapter
- FTDI-based adapter selected for reliable driver support and stable serial-port
  naming compared with low-cost, unidentified USB serial adapters.

### Serial cable

- **StarTech SCNM925FM**
- DB9 female to DB25 male null-modem cable
- Connects the DB9 side of the ICUSB2321F adapter to the DPX-3300's DB25 serial
  interface.

Do not substitute a straight-through DB9-to-DB25 cable without verifying its
pinout. The selected cable is a null-modem cable, which crosses the data and
handshake signals required for DTE-to-DTE communication.

## Agreed plotter settings

Configure the rear-panel controls before powering on the plotter:

| Setting | Selected value |
|---|---:|
| Interface | RS-232C |
| Baud-rate dial | 14 |
| Baud rate | 9600 baud |
| Data bits | 8 |
| Parity | None |
| Stop bits | 1 |
| Flow control | XON/XOFF software flow control |
| Protocol summary | 9600 8N1, XON/XOFF |

The DPX-3300 reads its DIP-switch and baud-dial configuration during power-up.
Power the plotter off before changing these settings, then power it back on.

## Computer-side serial settings

The sender in this project uses these explicit `pyserial` values:

```python
baudrate = 9600
bytesize = serial.EIGHTBITS
parity = serial.PARITY_NONE
stopbits = serial.STOPBITS_ONE
xonxoff = True
rtscts = False
dsrdtr = False
```

Do not enable RTS/CTS at the same time as XON/XOFF. The selected baseline is
software flow control.

## Finding the serial port

### macOS

Connect the adapter, then run:

```bash
ls /dev/cu.usbserial-* /dev/cu.usbmodem* 2>/dev/null
```

Prefer the `/dev/cu.*` device for an outbound serial connection.

### Linux

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

The user may need membership in the `dialout` group:

```bash
sudo usermod -aG dialout "$USER"
```

Log out and back in after changing group membership.

### Windows

Use Device Manager under **Ports (COM & LPT)** and note the assigned `COM` port,
for example `COM3`.

## uv setup

Install uv, then from the project directory run:

```bash
uv python install 3.12
uv sync
```

`uv sync` creates and manages the local environment automatically. Manual
activation is not required.

To include Chiplotle3 for experimentation:

```bash
uv sync --extra chiplotle
```

## Convert SVG to HP-GL

Create the input and output directories if they are absent:

```bash
mkdir -p input output
```

Convert a single SVG:

```bash
uv run python dpx3300_convert.py \
  --input-dir ./input \
  --output-dir ./output \
  --file test.svg \
  --page-size a3 \
  --landscape
```

Inspect the output before transmitting:

```bash
head -c 500 output/test.hpgl
```

The converter currently expects vector SVG input. Raster images must first be
traced or otherwise transformed into plotter-oriented vector linework.

## Send HP-GL to the plotter

macOS example:

```bash
uv run python send_hpgl.py \
  --port /dev/cu.usbserial-XXXXXXXX \
  output/test.hpgl
```

Linux example:

```bash
uv run python send_hpgl.py --port /dev/ttyUSB0 output/test.hpgl
```

Windows example:

```powershell
uv run python send_hpgl.py --port COM3 output/test.hpgl
```

Use `--list-ports` to display serial devices detected by pySerial:

```bash
uv run python send_hpgl.py --list-ports
```

## Safe commissioning sequence

1. Leave the pen raised or install a sacrificial pen.
2. Load inexpensive paper and secure it.
3. Confirm RS-232C is selected.
4. Confirm baud dial 14 and 9600 8N1.
5. Confirm XON/XOFF is selected.
6. Power-cycle the plotter after switch changes.
7. Connect the ICUSB2321F and SCNM925FM.
8. Confirm the operating system sees the serial port.
9. Generate a very small centered test drawing.
10. Inspect the HP-GL for `IN;`, `SP`, `PU`, and `PD` commands.
11. Send the test file while ready to pause or power off the plotter.
12. Confirm orientation, scale, origin, and pen selection before larger jobs.

## Multicolor jobs

HP-GL represents tool changes with `SPn;`, not with RGB values:

```hpgl
SP1;
...tool 1 paths...
SP2;
...tool 2 paths...
SP0;
```

For deterministic multicolor plotting, prepare one SVG/vpype layer per physical
tool slot and map layers 1 through 8 to `SP1` through `SP8`. Record the actual
pen loaded in each slot before running the job.

Suggested job sheet:

| Slot | Tool/color | Verified |
|---:|---|---|
| 1 |  |  |
| 2 |  |  |
| 3 |  |  |
| 4 |  |  |
| 5 |  |  |
| 6 |  |  |
| 7 |  |  |
| 8 |  |  |

## Troubleshooting

### Plotter receives nothing

- Confirm the correct serial port.
- Confirm RS-232C rather than the parallel interface is selected.
- Confirm the plotter was power-cycled after changing switches.
- Confirm 9600 8N1 and XON/XOFF on both ends.
- Confirm the cable is the selected SCNM925FM null-modem cable.

### Job starts and then stops

- Verify XON/XOFF is enabled on both sides.
- Ensure RTS/CTS and DSR/DTR are disabled in the sender.
- Check that no other application has opened the serial port.
- Try a smaller HP-GL file to isolate buffering or malformed-command issues.

### Plot is mirrored, rotated, or out of bounds

- Test with a small square and axis labels.
- Confirm vpype page size and orientation.
- Inspect plotter P1/P2 and origin settings.
- Do not assume the generic vpype `dxy` profile exactly matches every DPX-3300
  paper boundary.

## Docker deployment model

The container is primarily a reproducible conversion environment. It receives
source files through a read-only bind mount and writes generated HP-GL through
a writable bind mount:

```text
host ./input  -> container /app/input  (read-only)
host ./output -> container /app/output (read/write)
```

Build once after dependency or Dockerfile changes:

```bash
docker compose build
```

Run conversion jobs as short-lived containers:

```bash
docker compose run --rm converter
```

Use `docker compose run --rm converter ...` with a replacement command to
select a particular filename or page setting. Do not use `docker compose up`
as though this were a continuously running server; conversion and transmission
are finite command-line jobs.

### Serial-port deployment decision

- **Native Linux Docker Engine:** serial transmission may run in the container
  when `/dev/ttyUSB0` (or the actual device) is explicitly passed with
  `--device`. Avoid `--privileged`; the individual device mapping is narrower.
- **macOS Docker Desktop:** keep serial transmission on the macOS host using
  `/dev/cu.usbserial-*`; use Docker only for conversion.
- **Windows Docker Desktop:** keep serial transmission on the Windows host using
  the assigned `COM` port; use Docker only for conversion.

This split avoids USB/IP complexity on Docker Desktop and keeps the physical
plotter control path easy to inspect and stop.

## Repository tracking policy

`input/` and `output/` are job workspaces and are not version-controlled.
Their `.gitkeep` files are tracked so a fresh clone contains both directories.
Store durable source artwork elsewhere or deliberately move selected fixtures
into a versioned `examples/` or `tests/fixtures/` directory.

Commit `pyproject.toml`. When `uv lock` is run successfully in a networked local
environment, also commit `uv.lock` for repeatable dependency resolution. Do not
add `uv.lock` to `.gitignore` for this application repository.
