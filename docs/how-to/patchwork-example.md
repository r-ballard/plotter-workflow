# Patchwork-inspired plotter example

This generator makes an original line drawing using seeded points, repeated
local clustering, convex hulls, and optional recursion inside each hull. The
approach follows the geometry discussed in [Matt DesLauriers's *Pen Plotter Art
& Algorithms, Part 2*](https://mattdesl.svbtle.com/pen-plotter-2); this is an
independent Python implementation, not his artwork or source code. It produces
the same strict SVG and adjacent pen-plan contract as the
[Delaunay example](first-algorithm-to-plot.md), so the conversion and preflight
steps are shared.

From the repository root, with the pinned `uv` environment installed:

```bash
uv run --frozen python examples/patchwork/generate.py \
  --output-dir output/patchwork --seed 17 --points 2000 \
  --clusters 3 --depth 2
```

If `uv` is not on PATH, invoke its installed executable by full path. In
PowerShell, use one line and the call operator: `& C:\path\to\uv.exe run
--frozen python examples/patchwork/generate.py --output-dir output/patchwork
--seed 17 --points 2000 --clusters 3 --depth 2`.

The generator writes `patchwork.svg`, `patchwork.penplan.json`, and
`patchwork.json` in the selected directory. Open the SVG and review line
density and polygon placement. The manifest records parameters, polygon count,
source pen-down path length, and the SVG hash. Identical parameters produce
byte-identical files. Change `--seed` for a different drawing, `--points` for
more sites, `--clusters` for the number of local groups, and `--depth` (0–2)
for additional polygon-local recursion. The default produces about 1,955
polygons from 2,000 starting sites. The generator refuses to replace existing
files unless you provide `--overwrite`. For a faster, lighter visual study,
try `--points 600 --depth 1`.

`--max-path-mm` (default 20,000) and `--max-polygons` (default 2,500) reject
overly dense source artwork before writing files. The source path length is
measured in the SVG's 200 mm coordinate system. The converter may rescale the
artwork, so inspect the converted HP-GL preview metrics for the actual plotted
distance. These geometric lengths are not time estimates.

Convert and inspect without opening a serial port:

```bash
uv run --frozen python dpx3300_convert.py \
  --input-dir output/patchwork --output-dir output/patchwork \
  --file patchwork.svg --page-size letter --landscape \
  --paper-position lower-left --margin 4mm --absolute
uv run --frozen python scripts/preview_hpgl.py \
  --hpgl output/patchwork/patchwork.hpgl \
  --preview output/patchwork/patchwork.preview.svg \
  --metrics output/patchwork/patchwork.metrics.json
uv run --frozen python job_preflight.py output/patchwork/patchwork.hpgl
```

Open `patchwork.preview.svg` and inspect `patchwork.metrics.json` alongside the
resolved pen plan and placement sidecar. For the default single-pen job,
preflight should report `SP1 -> SP0`, pen plan PASS, placement PASS, and
`READY TO SEND`. The seed-17 dense sample measures roughly 16.3 m pen-down
and 5.3 m pen-up after conversion, so review its actual workload before
considering a physical plot. Any parameter change requires regeneration,
conversion, preview, and preflight on the new HP-GL. Follow the [playbook](../../playbook.md)
for switch settings, physical media, keep-awake precautions, and normal sending
only after operator review. The commands above do not send a job.
