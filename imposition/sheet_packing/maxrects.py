"""Deterministic best-short-side-fit with bounded free rectangle splitting."""

from .model import EPS, PackingResult, RectMM
from .solver import cannot_fit, orientations, placed


def _key(r):
    return r.x, r.y, r.width, r.height


def _split(free, used, budget):
    result = []

    def add(x, y, w, h):
        if w <= EPS or h <= EPS:
            return
        if len(result) >= budget.limits["free_rectangles"]:
            raise ValueError("sheet packing free_rectangles budget exceeded")
        r = RectMM(x, y, w, h)
        if any(o.contains(r) for o in result):
            return
        result[:] = [o for o in result if not r.contains(o)]
        result.append(r)

    for r in free:
        if not r.intersects(used):
            add(r.x, r.y, r.width, r.height)
            continue
        if used.x > r.x:
            add(r.x, r.y, used.x - r.x, r.height)
        if used.right < r.right:
            add(used.right, r.y, r.right - used.right, r.height)
        if used.y > r.y:
            add(r.x, r.y, r.width, used.y - r.y)
        if used.bottom < r.bottom:
            add(r.x, used.bottom, r.width, r.bottom - used.bottom)
    return sorted(result, key=_key)


def _pack_maxrects(items, area, gutter, budget):
    # A virtual trailing gutter permits exact boundary fits, without reserving
    # unnecessary physical space outside the usable sheet.
    full = RectMM(area.x, area.y, area.width + gutter, area.height + gutter)
    pages, records = [], []
    ordered = sorted(
        items,
        key=lambda i: (
            -i.footprint.occupied_bounds.width * i.footprint.occupied_bounds.height,
            -max(i.footprint.occupied_bounds.width, i.footprint.occupied_bounds.height),
            i.instance_id,
        ),
    )
    for item in ordered:
        if budget.limits["free_rectangles"] < 1:
            raise ValueError("sheet packing free_rectangles budget exceeded")
        selected = None
        for page in range(len(pages) + 1):
            free = pages[page] if page < len(pages) else (full,)
            best = None
            for index, r in enumerate(free):
                for angle, w, h in orientations(item):
                    budget.reserve("candidates", 1)
                    dw, dh = r.width - w - gutter, r.height - h - gutter
                    if min(dw, dh) < -EPS:
                        continue
                    score = (min(dw, dh), max(dw, dh), r.y, r.x, angle, index)
                    if best is None or score < best[0]:
                        best = score, angle, r.x, r.y, w, h
            if best is not None:
                selected = page, best
                if page == len(pages):
                    budget.reserve("sheets", 1)
                    pages.append((full,))
                break
        if selected is None:
            raise cannot_fit(item, area)
        page, (_, angle, x, y, w, h) = selected
        record = placed(item, page, angle, x, y, w, h)
        pages[page] = _split(pages[page], RectMM(x, y, w + gutter, h + gutter), budget)
        records.append(record)
    return PackingResult("maxrects", tuple(records), len(pages))


def pack_maxrects(instances, sheet, gutter, budget):
    from .solver import pack

    return pack(instances, sheet, gutter, "maxrects", budget)
