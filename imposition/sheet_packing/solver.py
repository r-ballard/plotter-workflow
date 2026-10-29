"""Bounded deterministic dispatch and shared final placement checks."""

from .budget import PackingBudget
from .geometry import effective_area, front_matrix, validate_placements
from .model import PackedInstance, PackingInstance, RectMM, number


def policy(item):
    f = item.footprint
    b = f.occupied_bounds
    return b.width, b.height, f.rotations


def orientations(item):
    w, h, angles = policy(item)
    return tuple((a, w, h) if a == 0 else (a, h, w) for a in angles)


def placed(item, page, angle, x, y, w, h):
    return PackedInstance(
        item.instance_id,
        page,
        angle,
        front_matrix(item.footprint, angle, (x, y)),
        RectMM(x, y, w, h),
    )


def cannot_fit(item, area):
    b = item.footprint.occupied_bounds
    return ValueError(
        f"{item.instance_id}: footprint {b.width:g}x{b.height:g} mm cannot fit "
        f"usable {area.width:g}x{area.height:g} mm; rotations {item.footprint.rotations}"
    )


def pack(instances, sheet, gutter=0, strategy="auto", budget=None):
    from .grid import _pack_grid
    from .maxrects import _pack_maxrects

    budget = budget if budget is not None else PackingBudget()
    g = number(gutter, "gutter")
    if g < 0 or strategy not in ("auto", "grid", "maxrects"):
        raise ValueError("invalid gutter or packing strategy")
    area = effective_area(sheet)
    source, seen = [], set()
    for item in instances:
        budget.reserve("instances", 1)
        if not isinstance(item, PackingInstance) or item.instance_id in seen:
            raise ValueError("packing requires unique PackingInstance records")
        seen.add(item.instance_id)
        source.append(item)
    if not source:
        raise ValueError("packing requires at least one instance")
    same = all(policy(i) == policy(source[0]) for i in source)
    if strategy == "grid" and not same:
        raise ValueError("grid requires identical occupied dimensions and rotation policy")
    if strategy == "auto":
        strategy = "grid" if same else "maxrects"
    result = (_pack_grid if strategy == "grid" else _pack_maxrects)(source, area, g, budget)
    validate_placements(source, result, sheet, g)
    return result
