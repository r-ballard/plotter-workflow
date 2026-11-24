"""Explicit provisional A-D composition profiles, separate from flat placement."""

import math

from .artwork_layout import (
    ArtworkLayout,
    PanelLayout,
    affine,
    bounds,
    finite,
    rect,
)
from .objects.kaleidocycle import Kaleidocycle


def triangle_matrix(source, target):
    """Unique affine map taking the three ordered vertices onto the target."""
    (x, y), (u, v), (s, t) = source
    (X, Y), (U, V), (S, T) = target
    ux, uy, vx, vy = u - x, v - y, s - x, t - y
    det = ux * vy - uy * vx
    a = ((U - X) * vy - (S - X) * uy) / det
    c = (ux * (S - X) - vx * (U - X)) / det
    b = ((V - Y) * vy - (T - Y) * uy) / det
    d = (ux * (T - Y) - vx * (V - Y)) / det
    return (a, b, c, d, X - a * x - c * y, Y - b * x - d * y)


def resolve_kaleidocycle_state(state, *, width_mm, tetrahedron_count=6):
    if state not in ("A", "B", "C", "D"):
        raise ValueError("state must be A, B, C, or D; transitions are deferred")
    width = finite(width_mm, "width_mm")
    if not 0 < width <= 10000:
        raise ValueError("width_mm outside supported range")
    obj = Kaleidocycle(tetrahedron_count)
    count = obj.tetrahedron_count
    # Integer canonical canvases avoid ambiguous near-gaps in the producer's
    # exact seam checks. Physical scaling is applied once by the imposer.
    radius = max(256, count * 2)
    center = (radius, radius)
    vertices = [
        (512, 256),
        (512, 512),
        (256, 512),
        (0, 512),
        (0, 256),
        (0, 0),
        (256, 0),
        (512, 0),
    ]
    if count != 8:
        # Shared integer endpoints preserve exact producer seam comparisons.
        # This fan is illustrative, not a physically derived folded view.
        vertices = [
            (
                round(radius + radius * math.cos(2 * math.pi * i / count)),
                round(radius + radius * math.sin(2 * math.pi * i / count)),
            )
            for i in range(count)
        ]
    panels = []
    for i in range(count):
        slot_id = f"column-{i + 1}-{state.lower()}"
        local = obj.local_polygon(slot_id, width)
        side = max(x for x, y in local)
        polygon = tuple(
            (round(x / side * 128), round(y / side * 128)) for x, y in local
        )
        # A viewing projection can foreshorten faces; these affine maps are an
        # illustrative declaration, not a kinematic solution or validation.
        target = (center, vertices[i], vertices[(i + 1) % count])
        panels.append(
            PanelLayout(
                slot_id,
                rect(*bounds(polygon)),
                polygon,
                triangle_matrix(polygon, target),
                {"kind": "kaleidocycle-slot", "slot": slot_id, "state": state},
            )
        )
    adjacency = [
        ((panels[i].panel_id, 2), (panels[(i + 1) % count].panel_id, 0))
        for i in range(count)
    ]
    return ArtworkLayout(
        f"kaleidocycle-{state}",
        "svg-px",
        (-1, -1, radius * 2 + 2, radius * 2 + 2),
        tuple(panels),
        "provisional",
        {
            "layout": "kaleidocycle-state",
            "state": state,
            "width_mm": width,
            "tetrahedron_count": count,
            "source_edge_units": 128,
            "source_unit_mm": width / obj.net_width * 2 / 128,
            "adjacency": adjacency,
            "validation_basis": "illustrative projection; paper fold required",
        },
    )


def validate_kaleidocycle_layout(layout):
    expected = resolve_kaleidocycle_state(
        layout.settings.get("state"),
        width_mm=layout.settings.get("width_mm"),
        tetrahedron_count=layout.settings.get("tetrahedron_count", 8),
    )
    canonical = {p.panel_id: p for p in expected.panels}
    if (
        layout.settings.get("layout") != "kaleidocycle-state"
        or {p.panel_id for p in layout.panels} != set(canonical)
        or layout.validation_status != "provisional"
    ):
        raise ValueError("invalid kaleidocycle state identity/status")
    panels = {p.panel_id: p for p in layout.panels}
    for p in layout.panels:
        q = canonical[p.panel_id]
        if (
            p.canvas_polygon != q.canvas_polygon
            or p.crop_polygon != q.crop_polygon
            or p.binding != q.binding
        ):
            raise ValueError("state panel differs from canonical intrinsic geometry")
    adjacency = layout.settings.get("adjacency")
    if not isinstance(adjacency, (tuple, list)) or len(adjacency) != len(canonical):
        raise ValueError("state requires one explicitly paired radial seam per cell")
    used = set()
    for seam in adjacency:
        if not isinstance(seam, (tuple, list)) or len(seam) != 2:
            raise ValueError("seam requires two panel-edge references")
        endpoints = []
        for ref in seam:
            if (
                not isinstance(ref, (tuple, list))
                or len(ref) != 2
                or not isinstance(ref[0], str)
                or ref[0] not in panels
                or type(ref[1]) is not int
                or ref[1] not in range(3)
                or tuple(ref) in used
            ):
                raise ValueError("invalid or repeated seam edge")
            used.add(tuple(ref))
            p = panels[ref[0]]
            endpoints.append(
                [
                    affine(p.assembled_matrix, p.crop_polygon[i % 3])
                    for i in (ref[1], ref[1] + 1)
                ]
            )
        if seam[0][0] == seam[1][0] or any(
            abs(a - b) > 1e-6
            for u, v in zip(endpoints[0], reversed(endpoints[1]))
            for a, b in zip(u, v)
        ):
            raise ValueError("declared adjacent edges do not coincide in reverse order")
    if {ref[0] for ref in used} != set(panels):
        raise ValueError("adjacency must include every panel")
