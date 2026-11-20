"""Validated, immutable kaleidocycle artwork at its native physical datum."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from .artwork_layout import MM_TO_PX, _freeze
from .kaleidocycle_impose import render_kaleidocycle
from .model import ObjectPlacement, SheetSpec
from .native_artwork import (
    NativeFragment,
    PreparedNativeFace,
    _retained_vertices,
    digest,
)
from .objects.kaleidocycle import Kaleidocycle
from .sheet_packing.model import number


@dataclass(frozen=True)
class KaleidocycleRequest:
    width_mm: float
    states: tuple

    def __post_init__(self):
        width = number(self.width_mm, "width_mm")
        if not 0 < width <= 10000:
            raise ValueError("width_mm outside supported range")
        if len(self.states) != 4 or {s for s, p in self.states} != set("ABCD"):
            raise ValueError("kaleidocycle requires exactly states A-D")
        object.__setattr__(self, "width_mm", width)
        object.__setattr__(
            self,
            "states",
            tuple(sorted((s, Path(p).resolve()) for s, p in self.states)),
        )


def prepare_native_kaleidocycle(request):
    import vpype

    width = request.width_mm
    height = width / Kaleidocycle.aspect_ratio
    sheet = SheetSpec("custom", width, height, "landscape")
    root, catalog, records, _ = render_kaleidocycle(
        dict(request.states), ObjectPlacement(sheet, 0, 0, width, height)
    )
    fragments = []
    for layer in root:
        layer_id = layer.get("data-viz-layer-id")
        if layer_id is None:
            continue
        for wrapper in layer:
            for geometry in wrapper:
                counter = SimpleNamespace(svg=geometry, lines=vpype.LineCollection())
                fragments.append(
                    NativeFragment(
                        layer_id,
                        wrapper.get("data-imposed-slot"),
                        ET.tostring(geometry, encoding="utf-8"),
                        _retained_vertices(
                            counter, width * MM_TO_PX, height * MM_TO_PX
                        ),
                    )
                )
    return PreparedNativeFace(
        "kaleidocycle",
        "front",
        width,
        height,
        tuple(_freeze(v) for v in catalog),
        tuple(fragments),
        tuple(_freeze(v) for v in records),
        _freeze(
            {
                "validation_status": "provisional",
                "states": [
                    {
                        "state": state,
                        "source_manifest_sha256": digest(path / "design.json"),
                        "handoff_sha256": digest(path / "layout-handoff.json"),
                        "producer_design_sha256": digest(path / "producer-design.json"),
                    }
                    for state, path in request.states
                ],
            }
        ),
    )
