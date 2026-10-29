"""Exact quadrant transforms and physical-sheet correspondence."""

import math

from .model import EPS, RectMM, number


def transform(m, p):
    a, b, c, d, e, f = m
    x, y = p
    return a * x + c * y + e, b * x + d * y + f


def compose(a, b):
    aa, ab, ac, ad, ae, af = a
    ba, bb, bc, bd, be, bf = b
    return (
        aa * ba + ac * bb,
        ab * ba + ad * bb,
        aa * bc + ac * bd,
        ab * bc + ad * bd,
        aa * be + ac * bf + ae,
        ab * be + ad * bf + af,
    )


def sheet_flip(sheet):
    if sheet.faces != "both":
        raise ValueError("back transform requires paired faces")
    return (
        (-1, 0, 0, 1, sheet.width_mm, 0)
        if sheet.flip == "left-right"
        else (1, 0, 0, -1, 0, sheet.height_mm)
    )


def rect_transform(m, r):
    points = [
        transform(m, p) for p in ((r.x, r.y), (r.right, r.y), (r.right, r.bottom), (r.x, r.bottom))
    ]
    xs, ys = zip(*points)
    return RectMM(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def intersection(a, b):
    x, y = max(a.x, b.x), max(a.y, b.y)
    if min(a.right, b.right) <= x or min(a.bottom, b.bottom) <= y:
        raise ValueError("drawable area is empty after margins/paired intersection")
    return RectMM(x, y, min(a.right, b.right) - x, min(a.bottom, b.bottom) - y)


def effective_area(sheet):
    top, right, bottom, left = sheet.margins
    inset = RectMM(left, top, sheet.width_mm - left - right, sheet.height_mm - top - bottom)
    front = intersection(sheet.usable_front, inset)
    if sheet.faces == "both":
        back = intersection(sheet.usable_back, inset)
        front = intersection(front, rect_transform(sheet_flip(sheet), back))
    return front


def front_matrix(footprint, rotation, occupied_origin):
    if type(rotation) is not int or rotation not in footprint.rotations:
        raise ValueError("rotation not permitted")
    b = footprint.occupied_bounds
    x, y = (number(v, "occupied origin") for v in occupied_origin)
    return (1, 0, 0, 1, x - b.x, y - b.y) if rotation == 0 else (0, 1, -1, 0, x + b.bottom, y - b.x)


def back_matrix(front, native_back_to_front, sheet):
    return compose(sheet_flip(sheet), compose(front, native_back_to_front))


def validate_placements(instances, result, sheet, gutter):
    g = number(gutter, "gutter")
    if g < 0:
        raise ValueError("gutter must be nonnegative")
    lookup = {i.instance_id: i for i in instances}
    records = result.placements
    if (
        len(lookup) != len(instances)
        or len(records) != len(instances)
        or {p.instance_id for p in records} != set(lookup)
    ):
        raise ValueError("packing must contain every unique instance exactly once")
    if set(p.sheet_index for p in records) != set(range(result.sheet_count)):
        raise ValueError("invalid packed sheet assignments")
    area = effective_area(sheet)
    for index, p in enumerate(records):
        item = lookup[p.instance_id]
        b = p.occupied_bounds
        expected = front_matrix(item.footprint, p.rotation, (b.x, b.y))
        if (
            any(
                not math.isclose(v, w, abs_tol=EPS, rel_tol=0)
                for v, w in zip(expected, p.front_matrix)
            )
            or not area.contains(b)
            or not b.contains(rect_transform(p.front_matrix, item.footprint.occupied_bounds))
            or not rect_transform(p.front_matrix, item.footprint.occupied_bounds).contains(b)
        ):
            raise ValueError("invalid rigid placement or out-of-bounds footprint")
        expanded = RectMM(b.x, b.y, b.width + g, b.height + g)
        for other in records[index + 1 :]:
            if other.sheet_index == p.sheet_index and (
                expanded.intersects(other.occupied_bounds)
                or RectMM(
                    other.occupied_bounds.x,
                    other.occupied_bounds.y,
                    other.occupied_bounds.width + g,
                    other.occupied_bounds.height + g,
                ).intersects(b)
            ):
                raise ValueError("packed footprints overlap or violate gutter")
