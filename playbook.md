# Roland DPX-3300 Operating Playbook

This playbook documents two independent ways to operate the Roland DPX-3300:

1. USB-to-parallel through the plotter's Centronics `PARALLEL IN` connector.
2. USB-to-serial through the plotter's RS-232C `SERIAL IN` connector.

Choose one connection method and follow that section from beginning to end. Do
not combine the DIP-switch settings or host commands from the two methods.

The DPX-3300 reads its DIP switches and baud-rate dial only when it is powered
on. Always turn the plotter off before changing a switch, then power it back on.

## General safety rules

- Use inexpensive paper and a sacrificial pen for the first test.
- Start with a small drawing near the center of the page.
- Inspect the HP-GL before transmitting it.
- Keep a hand near the plotter's pause control.
- Be prepared to power the plotter off if it moves outside the expected area.
- Do not assume that the generic vpype `dxy` profile exactly matches every
  DPX-3300 paper boundary or P1/P2 configuration.

---

# Connection method 1: USB-to-parallel

Use this section when the computer is connected to the DPX-3300 through a USB
printer adapter and the plotter's 36-pin Centronics `PARALLEL IN` connector.

The USB-parallel path is a printer-style, primarily one-way connection. It is
well suited to sending complete HP-GL files, but it does not provide the serial
query and software-handshake behavior available through RS-232C.

## 1. Required parallel hardware

Use a cable or adapter with these characteristics:

- Computer side: USB.
- Plotter side: 36-pin Centronics male.
- Product type: USB-to-parallel, USB printer, or USB-to-IEEE-1284 adapter.
- Host behavior: recognized as a printer interface or USB printing-support
  device.

Verify that the plotter-side connector is 36-pin Centronics. A DB25 connector,
VGA connector, serial gender changer, or passive adapter is not a substitute.

The host must send the HP-GL file without converting it to PDF, PostScript, PCL,
or a raster printer format.

## 2. Parallel DIP-switch settings

The following table gives a complete baseline for both rear DIP-switch banks.

For an A3 workflow, use the ISO-A1 paper standard by leaving SW-1 switch 7 OFF.
If the job is designed for ANSI-D coordinates, set SW-1 switch 7 ON instead.

### Parallel configuration table

| Bank | Switch | Setting | Function and reason |
|---|---:|:---:|---|
| SW-1 | 1 | OFF | Character-set bit; part of ANSI ASCII (1), set 0 |
| SW-1 | 2 | OFF | Character-set bit; part of ANSI ASCII (1), set 0 |
| SW-1 | 3 | OFF | Character-set bit; part of ANSI ASCII (1), set 0 |
| SW-1 | 4 | OFF | Character-set bit; part of ANSI ASCII (1), set 0 |
| SW-1 | 5 | **OFF** | Selects the Centronics parallel interface |
| SW-1 | 6 | OFF | Direct connection setting; serial-only behavior |
| SW-1 | 7 | **OFF for ISO-A1/A3** | Set ON only for ANSI-D paper coordinates |
| SW-1 | 8 | OFF | Timeout mode disabled for the initial baseline |
| SW-2 | 1 | OFF | Serial stop-bit control; ignored in parallel mode |
| SW-2 | 2 | OFF | Serial data-bit control; ignored in parallel mode |
| SW-2 | 3 | OFF | Serial parity sense; ignored in parallel mode |
| SW-2 | 4 | OFF | Serial parity enable; ignored in parallel mode |
| SW-2 | 5 | OFF | Serial handshake control; ignored in parallel mode |
| SW-2 | 6 | OFF | Reserved; leave OFF |
| SW-2 | 7 | OFF | Reserved; leave OFF |
| SW-2 | 8 | OFF | Parallel error output disabled; pin 32 remains high |
| Baud dial | - | Any | The baud-rate dial is ignored in parallel mode |

Roland's Chapter 5 example turns on only SW-1 switch 7, which selects ANSI-D.
That example is appropriate for ANSI-D media. For A-series media and the
project's A3 examples, SW-1 switch 7 should remain OFF.

SW-1 switch 8 enables the plotter's timeout mode. Leave it OFF until basic
communication is working. If a host queue incorrectly times out during long
plotter buffer pauses, timeout mode can be tested later.

SW-2 switch 8 is the only SW-2 setting with a parallel-specific function. When
enabled, the DPX-3300 can signal an error on Centronics pin 32. Leave it OFF for
the initial USB-parallel baseline because many USB printer adapters do not make
that status behavior visible to the host.

## 3. Configure and power up the plotter for parallel operation

1. Turn the DPX-3300 off.
2. Set every switch according to the parallel configuration table.
3. Connect the 36-pin Centronics plug to `PARALLEL IN`.
4. Connect the USB end to the computer.
5. Turn the DPX-3300 on.
6. Confirm that the `SERIAL/PARALLEL` indicator is **red**.

A green interface indicator means the plotter is still configured for serial
operation. Turn the plotter off and recheck SW-1 switch 5.

## 4. Prepare the uv project

From the repository root:

```bash
uv python install 3.12
uv sync
```

Manual activation of a virtual environment is not required.

Create the job directories if they are absent:

```bash
mkdir -p input output
```

Place the plot-ready SVG in `input/`.

## 5. Convert an SVG to HP-GL for parallel transmission

Example:

```bash
uv run python dpx3300_convert.py \
  --input-dir ./input \
  --output-dir ./output \
  --file test.svg \
  --page-size a3 \
  --landscape
```

Inspect the generated file:

```bash
head -c 500 output/test.hpgl
```

A normal HP-GL file should contain commands such as:

```text
IN;
SP1;
PU...
PD...
```

The converter expects vector paths. Embedded raster images, visual-only pattern
fills, and unsupported SVG effects must be converted to actual line geometry
before this step.

## 6. Find and use the USB-parallel adapter

The adapter normally appears as a printer device, not as a serial port. Do not
use `send_hpgl.py` for the parallel connection.

### Linux: direct printer-device method

Inspect USB and printer-device discovery:

```bash
lsusb
dmesg | tail -n 50
ls -l /dev/usb/lp* 2>/dev/null
```

If the adapter appears as `/dev/usb/lp0`, send the HP-GL bytes directly:

```bash
cat output/test.hpgl > /dev/usb/lp0
```

If access is denied, add the user to the printer-device group:

```bash
sudo usermod -aG lp "$USER"
```

Log out and back in after changing group membership.

A one-time permission test may be performed with:

```bash
sudo sh -c 'cat output/test.hpgl > /dev/usb/lp0'
```

Do not make routine plotter operation depend on unrestricted root access.

### Linux: CUPS raw queue method

List queues:

```bash
lpstat -p -d
```

Send without format conversion:

```bash
lp -d DPX3300 -o raw output/test.hpgl
```

The queue must preserve the HP-GL bytes. Do not select a PostScript, PCL, PDF,
or rasterizing driver.

### macOS

Inspect the USB device and print queues:

```bash
system_profiler SPUSBDataType
lpstat -p -d
lpinfo -v 2>/dev/null | grep -i usb
```

If a raw or pass-through queue named `DPX3300` is available:

```bash
lp -d DPX3300 -o raw output/test.hpgl
```

Some current macOS/CUPS configurations do not expose a reliable raw queue. If
the queue transforms the file or rejects it, use a Linux host for the parallel
connection rather than selecting an ordinary graphics-printer driver.

### Windows

1. Connect the USB-parallel adapter.
2. Open **Printers & scanners** or **Devices and Printers**.
3. Add the printer manually if it is not detected automatically.
4. Select the adapter's USB printer port, commonly `USB001`.
5. Use **Generic / Text Only** as the temporary driver.
6. Where available, select the `WinPrint` print processor and `RAW` data type.
7. Share the local queue with a simple name such as `DPX3300Raw`.

From Command Prompt, send the file in binary mode:

```bat
copy /b output\test.hpgl \\localhost\DPX3300Raw
```

The `/b` option is required. It prevents text-mode translation of the file.

## 7. Parallel commissioning checklist

1. Confirm that the cable is connected to `PARALLEL IN`.
2. Confirm that SW-1 switch 5 is OFF.
3. Confirm that the interface indicator is red.
4. Confirm that the computer recognizes a printer device or `/dev/usb/lp0`.
5. Generate a very small centered test job.
6. Inspect the HP-GL for `IN;`, `SP`, `PU`, and `PD`.
7. Send the file through a raw queue or direct printer device.
8. Remain ready to pause or power off the plotter.
9. Confirm scale, orientation, origin, and pen selection.
10. Only then proceed to larger jobs.

## 8. Parallel troubleshooting

### The plotter receives nothing

- Confirm the cable is attached to `PARALLEL IN`, not `SERIAL IN`.
- Confirm SW-1 switch 5 is OFF.
- Confirm the interface indicator is red.
- Confirm the adapter appears as a printer device.
- Clear stalled jobs from the operating-system print queue.
- Test with a very small HP-GL file.

### The output is garbage or the plotter reports an error

- Confirm the queue did not convert the file to PDF, PostScript, PCL, or raster.
- Use binary or raw transmission.
- Inspect the file for valid HP-GL commands and semicolon terminators.
- Verify that the selected paper standard matches the job coordinates.
- Do not use a USB-to-VGA adapter or passive DB25 adapter in this path.

### The host reports a timeout during a long job

- First verify that the job works when it is small.
- Confirm that the queue is configured as a raw printer queue.
- After basic communication is proven, test SW-1 switch 8 ON to enable the
  DPX-3300 timeout mode.
- Return SW-1 switch 8 to OFF if it does not improve the behavior.

## 9. Parallel operation with Docker

The container is best used for conversion. On macOS and Windows, keep the
physical USB-parallel connection on the host.

Build the image:

```bash
docker compose build
```

Convert files:

```bash
docker compose run --rm converter
```

On native Linux, `/dev/usb/lp0` can be passed to a one-off container:

```bash
docker run --rm \
  --device=/dev/usb/lp0:/dev/usb/lp0 \
  --mount type=bind,src="$(pwd)/output",dst=/app/output,readonly \
  --entrypoint /bin/sh \
  dpx3300-plotter:local \
  -c 'cat /app/output/test.hpgl > /dev/usb/lp0'
```

Avoid `--privileged`. Passing only the required device is narrower and easier
to audit.

---

# Connection method 2: USB-to-serial

Use this section when the computer is connected to the DPX-3300 through an
RS-232C adapter and the plotter's DB25 `SERIAL IN` connector.

The selected project configuration is 9600 baud, 8 data bits, no parity, one
stop bit, and XON/XOFF software flow control.

## 1. Required serial hardware

### USB-to-RS-232 adapter

Selected model:

- **StarTech ICUSB2321F**
- FTDI-based USB-to-RS-232 adapter
- DB9 serial connector

The previously delivered **StarTech USB2VGAE3** is a USB-to-VGA display adapter.
It is not an RS-232 device and must not be connected to the plotter.

### Null-modem cable

Selected model:

- **StarTech SCNM925FM**
- DB9 female to DB25 male
- Null-modem wiring

Intended connection chain:

```text
Computer USB
    |
StarTech ICUSB2321F
    |
DB9 serial connection
    |
StarTech SCNM925FM null-modem cable
    |
DPX-3300 SERIAL IN
```

Do not substitute a straight-through DB9-to-DB25 cable without verifying the
pinout. The selected cable provides the crossover required for the normal
computer-to-plotter connection.

## 2. Serial DIP-switch settings

This table gives a complete configuration for 9600 8N1 with XON/XOFF software
flow control and a direct RS-232C connection.

For an A3 workflow, use the ISO-A1 paper standard by leaving SW-1 switch 7 OFF.
Set it ON only when the job is intentionally designed for ANSI-D coordinates.

### Serial configuration table

| Bank | Switch | Setting | Function and reason |
|---|---:|:---:|---|
| SW-1 | 1 | OFF | Character-set bit; part of ANSI ASCII (1), set 0 |
| SW-1 | 2 | OFF | Character-set bit; part of ANSI ASCII (1), set 0 |
| SW-1 | 3 | OFF | Character-set bit; part of ANSI ASCII (1), set 0 |
| SW-1 | 4 | OFF | Character-set bit; part of ANSI ASCII (1), set 0 |
| SW-1 | 5 | **ON** | Selects the RS-232C serial interface |
| SW-1 | 6 | **OFF** | Selects the normal direct serial connection |
| SW-1 | 7 | **OFF for ISO-A1/A3** | Set ON only for ANSI-D paper coordinates |
| SW-1 | 8 | OFF | Timeout mode disabled for the initial baseline |
| SW-2 | 1 | **OFF** | Selects 1 stop bit |
| SW-2 | 2 | **OFF** | Selects 8 data bits |
| SW-2 | 3 | OFF | Odd/even selector; ignored because parity is disabled |
| SW-2 | 4 | **OFF** | Disables parity |
| SW-2 | 5 | **ON** | Selects XON/XOFF software flow control |
| SW-2 | 6 | OFF | Reserved; leave OFF |
| SW-2 | 7 | OFF | Reserved; leave OFF |
| SW-2 | 8 | OFF | Parallel error output; irrelevant in serial mode |
| Baud dial | 14 | **9600 baud** | Matches the project sender configuration |

SW-1 switch 6 should remain OFF for ordinary direct RS-232C operation. Set it ON
only when deliberately implementing the DPX-3300's specialized Y-connection
mode.

The manual's basic serial example uses SW-2 switch 5 OFF, which selects hardware
handshake. This project instead uses XON/XOFF, so SW-2 switch 5 must be ON and
the host sender must also enable XON/XOFF.

## 3. Configure and power up the plotter for serial operation

1. Turn the DPX-3300 off.
2. Set every switch according to the serial configuration table.
3. Set the baud-rate dial to position 14.
4. Connect the null-modem cable to `SERIAL IN`.
5. Connect the USB-to-RS-232 adapter to the computer.
6. Turn the DPX-3300 on.
7. Confirm that the `SERIAL/PARALLEL` indicator is **green**.

A red interface indicator means the plotter is still configured for parallel
operation. Turn the plotter off and recheck SW-1 switch 5.

## 4. Computer-side serial settings

The computer and plotter must use identical communication settings:

```text
Baud rate:   9600
Data bits:   8
Parity:      None
Stop bits:   1
Flow control: XON/XOFF
```

The project's `send_hpgl.py` uses these pySerial values:

```python
baudrate = 9600
bytesize = serial.EIGHTBITS
parity = serial.PARITY_NONE
stopbits = serial.STOPBITS_ONE
xonxoff = True
rtscts = False
dsrdtr = False
```

Do not enable RTS/CTS or DSR/DTR at the same time as the selected XON/XOFF
configuration.

## 5. Prepare the uv project

From the repository root:

```bash
uv python install 3.12
uv sync
```

To install the optional Chiplotle3 dependency for experimentation:

```bash
uv sync --extra chiplotle
```

Create the job directories if they are absent:

```bash
mkdir -p input output
```

Place the plot-ready SVG in `input/`.

## 6. Convert an SVG to HP-GL for serial transmission

Example:

```bash
uv run python dpx3300_convert.py \
  --input-dir ./input \
  --output-dir ./output \
  --file test.svg \
  --page-size a3 \
  --landscape
```

Inspect the generated file:

```bash
head -c 500 output/test.hpgl
```

Confirm that it contains expected commands such as `IN;`, `SP`, `PU`, and `PD`
before sending it to the plotter.

## 7. Find the serial port

### macOS

```bash
ls /dev/cu.usbserial-* /dev/cu.usbmodem* 2>/dev/null
```

Prefer the `/dev/cu.*` device for an outbound connection.

### Linux

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

If required, add the user to the serial-device group:

```bash
sudo usermod -aG dialout "$USER"
```

Log out and back in afterward.

### Windows

Open **Device Manager**, expand **Ports (COM & LPT)**, and note the assigned COM
port, such as `COM3`.

The project can also ask pySerial to list detected ports:

```bash
uv run python send_hpgl.py --list-ports
```

## 8. Send HP-GL over serial

### macOS

```bash
uv run python send_hpgl.py \
  --port /dev/cu.usbserial-XXXXXXXX \
  output/test.hpgl
```

### Linux

```bash
uv run python send_hpgl.py \
  --port /dev/ttyUSB0 \
  output/test.hpgl
```

### Windows PowerShell

```powershell
uv run python send_hpgl.py `
  --port COM3 `
  output/test.hpgl
```

Replace the example device name with the actual port detected on the computer.

## 9. Serial commissioning checklist

1. Confirm that the cable is connected to `SERIAL IN`.
2. Confirm that SW-1 switch 5 is ON.
3. Confirm that SW-1 switch 6 is OFF for direct connection.
4. Confirm that SW-2 switch 5 is ON for XON/XOFF.
5. Confirm that the baud-rate dial is set to 14.
6. Power-cycle the plotter after setting the switches.
7. Confirm that the interface indicator is green.
8. Confirm that the operating system sees the serial adapter.
9. Generate and inspect a very small centered test job.
10. Send the file while ready to pause or power off the plotter.
11. Confirm scale, orientation, origin, and pen selection.
12. Only then proceed to larger jobs.

## 10. Serial troubleshooting

### The plotter receives nothing

- Confirm the correct serial port.
- Confirm that the cable is attached to `SERIAL IN`.
- Confirm that SW-1 switch 5 is ON.
- Confirm that the interface indicator is green.
- Confirm the baud-rate dial is set to 14.
- Confirm 9600 8N1 on both ends.
- Confirm XON/XOFF on both ends.
- Confirm that the cable is the null-modem SCNM925FM.
- Confirm that no other application has the serial port open.

### The job starts and then stops

- Confirm SW-2 switch 5 is ON.
- Confirm `xonxoff=True` in the sender.
- Confirm `rtscts=False` and `dsrdtr=False`.
- Try a smaller HP-GL file.
- Inspect the file for malformed or unsupported commands.
- Reconnect the USB adapter and recheck its assigned device name.

### Characters or commands are corrupted

- Recheck the baud-rate dial.
- Recheck data bits, parity, and stop bits.
- Confirm that the host has not enabled a second flow-control mode.
- Confirm that the USB device is actually an RS-232 adapter and not the
  USB2VGAE3 display adapter.

## 11. Serial operation with Docker

Use Docker primarily for SVG-to-HP-GL conversion:

```bash
docker compose build
docker compose run --rm converter
```

On macOS and Windows, run `send_hpgl.py` on the host because Docker Desktop does
not expose host serial ports as simply as native Linux.

On native Linux, the serial device may be passed explicitly:

```bash
docker run --rm \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  --mount type=bind,src="$(pwd)/output",dst=/app/output,readonly \
  dpx3300-plotter:local \
  send_hpgl.py \
  --port /dev/ttyUSB0 \
  /app/output/test.hpgl
```

Avoid `--privileged`. Pass only the serial device required by the job.

---

# Common plotting notes

## Multicolor jobs

HP-GL represents a tool change with `SPn;`, not with an RGB color value:

```hpgl
SP1;
...tool 1 paths...
SP2;
...tool 2 paths...
SP0;
```

For deterministic multicolor plotting, prepare one SVG or vpype layer per
physical tool slot and map layers 1 through 8 to `SP1` through `SP8`.

Record the actual tool loaded in each slot:

| Slot | Tool or color | Verified |
|---:|---|:---:|
| 1 |  |  |
| 2 |  |  |
| 3 |  |  |
| 4 |  |  |
| 5 |  |  |
| 6 |  |  |
| 7 |  |  |
| 8 |  |  |

## Plot is mirrored, rotated, or out of bounds

- Test with a small square and labeled axes.
- Confirm vpype page size and orientation.
- Confirm the SW-1 switch 7 paper standard.
- Inspect the DPX-3300 P1/P2 and origin settings.
- Do not assume that SVG page dimensions alone define the safe machine area.

## Repository tracking policy

`input/` and `output/` are local job workspaces and are not version-controlled.
Their `.gitkeep` files are tracked so a fresh clone retains both directories.

Store durable source artwork in a deliberately versioned directory such as
`examples/`, `reference-art/`, or `tests/fixtures/`.

Commit `pyproject.toml` and `uv.lock`. Do not add `uv.lock` to `.gitignore` for
this application repository.

## Primary references

- Roland DPX-3300 Operation Manual:
  <https://lesporteslogiques.net/materiel/plotter_roland_DPX-3300/DPX-3300_operation_manual.pdf>
- Project repository:
  <https://github.com/r-ballard/plotter-workflow>
