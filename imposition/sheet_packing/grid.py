"""Highest-capacity row-major packing of identical occupied rectangles."""

import math

from .model import EPS, PackingResult
from .solver import cannot_fit, orientations, placed


def _pack_grid(items, area, gutter, budget):
    ordered = sorted(items, key=lambda i: i.instance_id)
    choices = []
    for angle, w, h in orientations(ordered[0]):
        budget.reserve("candidates", 1)
        cols = math.floor((area.width + gutter + EPS) / (w + gutter))
        rows = math.floor((area.height + gutter + EPS) / (h + gutter))
        if cols and rows:
            choices.append((-cols * rows, angle, w, h, cols, rows))
    if not choices:
        raise cannot_fit(ordered[0], area)
    _, angle, w, h, cols, rows = min(choices)
    capacity = cols * rows
    pages = (len(ordered) + capacity - 1) // capacity
    budget.reserve("sheets", pages)
    records = tuple(
        placed(
            item,
            i // capacity,
            angle,
            area.x + (i % cols) * (w + gutter),
            area.y + ((i // cols) % rows) * (h + gutter),
            w,
            h,
        )
        for i, item in enumerate(ordered)
    )
    return PackingResult("grid", records, pages)


def pack_grid(instances, sheet, gutter, budget):
    from .solver import pack

    return pack(instances, sheet, gutter, "grid", budget)
