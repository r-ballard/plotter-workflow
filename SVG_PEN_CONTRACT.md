# SVG pen-layer contract

`plotter-workflow` accepts ordinary SVG files as before. It also recognizes a
stricter multi-pen SVG contract used by `viz-virtualserver` L-system exports.

## Authoritative mapping

Each physical pen is represented by one **top-level** SVG group:

```xml
<g id="pen-3"
   data-pen="3"
   data-generations="4,5"
   fill="none"
   stroke="#1f77b4">
  <g data-generation="4">...</g>
  <g data-generation="5">...</g>
</g>
```

The `id="pen-N"` value is authoritative. vpype imports top-level SVG groups as
layers and derives the layer ID from the first contiguous digits in the group
ID, so `pen-3` becomes vpype layer 3. With the DPX-3300 profile's eight-pen
configuration, vpype writes layer 3 using `SP3;`.

`data-pen` is a redundant assertion used to catch producer/consumer drift.
`stroke` is preview metadata only; physical pen selection must not be inferred
from color. In particular, do not replace the normal vpype `read` with
`read --attr stroke` for contract SVGs, because color encounter order is not a
physical pen number.

## Generation metadata

`data-generations` and nested `data-generation` values preserve L-system
provenance. `plotter-workflow` validates their consistency but does not use
them for HP-GL generation. Multiple generations assigned to the same pen are
therefore optimized and plotted as one vpype layer.

## Coordinate ownership

SVG coordinates, width, height, and viewBox are design-space values. They are
not physical DPX-3300 coordinates. `plotter-workflow` remains responsible for:

- target paper size and orientation;
- fit-to-margin scaling;
- centered versus lower-left physical placement;
- conversion to DPX-3300 plotter units; and
- HP-GL serialization and transport.

This keeps `viz-virtualserver` responsible for *what is drawn* and
`plotter-workflow` responsible for *how it is physically plotted*.

## Validation rules

When at least one top-level `pen-N` group is present, the SVG is treated as a
contract SVG and all of the following are required:

- `N` is unique and within 1 through 8;
- `data-pen` agrees with `N`;
- `fill="none"` and a stroke color are present;
- `data-generations` agrees with nested generation groups; and
- no other top-level group contains drawable geometry.

After conversion, `plotter-workflow` verifies that every expected pen occurs as
an `SPN;` selection in the generated HP-GL. SVGs without `pen-N` groups bypass
these contract-specific checks and retain the existing generic SVG workflow.
