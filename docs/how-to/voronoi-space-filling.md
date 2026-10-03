# Space-filling Voronoi plotter example

The [Patchwork-inspired generator](patchwork-example.md) draws convex hulls
around selected point clusters. Those hulls can leave open space. This example
uses a different construction: at each level, it samples sites inside a
bounded polygon, clips their Voronoi cells to that polygon, and divides each
resulting cell again. The underlying leaf cells partition the full 180 × 180 mm
drawing area. Each drawn cell is inset, leaving intentional white gutters, and
its corners are rounded with quadratic SVG curves. Two very small cells in the
default seed-17 drawing collapse under the inset and are omitted. The cells
are separate closed paths, so shared boundaries are not deliberately retraced.

This is an original Voronoi alternative for comparing compositions, not the
algorithm in [Matt DesLauriers's Patchwork article](https://mattdesl.svbtle.com/pen-plotter-2).
His [published example code](https://github.com/mattdesl/pen-plotter-blog-post/blob/master/code/patchwork.js)
draws straight segments; the inset gutters and rounded corners here are
explicit choices in this generator.
The separate [Delaunay example](first-algorithm-to-plot.md) triangulates
distributed sites inside their convex hull.

From the `plotter-workflow` repository root, with the pinned `uv` environment:

```bash
uv run --frozen python examples/voronoi/generate.py \
  --output-dir output/voronoi --seed 17 --branch 3 --depth 5
```

If `uv` is not on PATH, use the full path to your installed `uv.exe`. In
PowerShell, prefix that executable with `&` and enter the command on one line.
The generator writes `voronoi.svg`, `voronoi.penplan.json`, and `voronoi.json`.
Open the SVG to inspect the filled composition. The default has 243 final
underlying cells, of which 241 are drawn after the default 0.7 mm inset.
`--seed` changes the boundaries, `--branch` controls divisions per parent,
and `--depth` controls the number of recursive levels. `--inset-mm` controls
the white space between cell outlines; `--corner-radius-mm` rounds corners.
Set both to `0` for abutting, straight cell outlines. For a lighter study,
try `--depth 4` (81 cells). The generator refuses to overwrite files without
`--overwrite` and rejects requests above `--max-cells` or `--max-path-mm`.

The manifest records cell and edge counts, source SVG path length, the SVG
hash, and the numerical error in summed *un-inset* cell area. That error checks
the underlying partition; the visible gutters are intentional. The source
path-length safeguard uses an upper bound before layout and corner rounding;
the converted HP-GL metrics are the physical path measurement. These
distances are not time estimates.

Convert, preview, and preflight the exact generated job:

```bash
uv run --frozen python scripts/dpx3300_convert.py \
  --input-dir output/voronoi --output-dir output/voronoi \
  --file voronoi.svg --page-size letter --landscape \
  --paper-position lower-left --margin 4mm --absolute
uv run --frozen python scripts/preview_hpgl.py \
  --hpgl output/voronoi/voronoi.hpgl \
  --preview output/voronoi/voronoi.preview.svg \
  --metrics output/voronoi/voronoi.metrics.json
uv run --frozen python scripts/job_preflight.py output/voronoi/voronoi.hpgl
```

Inspect the preview, metrics, resolved pen plan, and placement sidecar. The
default seed-17 conversion measures about 10.8 m pen-down and 3.21 m pen-up.
For the single-pen job, expect `SP1 -> SP0`, pen plan PASS, placement PASS,
and `READY TO SEND`. Follow the [playbook](../../playbook.md) for hardware
setup and keep-awake precautions before any physical plot. The commands above
do not open a serial port.
