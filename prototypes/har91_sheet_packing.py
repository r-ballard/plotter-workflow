"""Throwaway HAR-91 geometry study. Not a plot-ready exporter or public API."""

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from imposition.jcard_profiles import get_jcard_profile

SHEET = (420.0, 297.0)
MARGIN = 3.0
GUTTER = 4.0
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)


@dataclass(frozen=True, order=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    def contains(self, other):
        return (
            self.x <= other.x
            and self.y <= other.y
            and self.x + self.w >= other.x + other.w - 1e-9
            and self.y + self.h >= other.y + other.h - 1e-9
        )

    def overlaps(self, other):
        return (
            self.x < other.x + other.w - 1e-9
            and other.x < self.x + self.w - 1e-9
            and self.y < other.y + other.h - 1e-9
            and other.y < self.y + self.h - 1e-9
        )


@dataclass(frozen=True)
class Item:
    instance_id: str
    shape: tuple
    size: tuple
    keepout: float = 3.0
    rotations: tuple = (0, 90)
    folds: tuple = ()

    @property
    def footprint(self):
        return self.size[0] + 2 * self.keepout, self.size[1] + 2 * self.keepout


def jcards(panels, count):
    profile = get_jcard_profile(f"standard-jcard-{panels}-panel-v1")
    w, h = profile.trim_size_mm
    folds = tuple(sum(profile.panel_widths_mm[:i]) for i in range(1, panels))
    return [
        Item(f"jcard-{panels}-{i:03}", ((0, 0), (w, 0), (w, h), (0, h)), (w, h), folds=folds)
        for i in range(1, count + 1)
    ]


def orientations(item):
    w, h = item.footprint
    return [(angle, w, h) if angle == 0 else (angle, h, w) for angle in item.rotations]


def split_free(free, used):
    pieces = []
    for r in free:
        if not r.overlaps(used):
            pieces.append(r)
            continue
        if used.x > r.x:
            pieces.append(Rect(r.x, r.y, used.x - r.x, r.h))
        if used.x + used.w < r.x + r.w:
            pieces.append(Rect(used.x + used.w, r.y, r.x + r.w - used.x - used.w, r.h))
        if used.y > r.y:
            pieces.append(Rect(r.x, r.y, r.w, used.y - r.y))
        if used.y + used.h < r.y + r.h:
            pieces.append(Rect(r.x, used.y + used.h, r.w, r.y + r.h - used.y - used.h))
    unique = sorted(set(r for r in pieces if r.w > 1e-9 and r.h > 1e-9))
    return [r for r in unique if not any(o != r and o.contains(r) for o in unique)]


def maxrects(items):
    pages, placed = [], []
    usable = Rect(MARGIN, MARGIN, SHEET[0] - 2 * MARGIN + GUTTER, SHEET[1] - 2 * MARGIN + GUTTER)
    for item in sorted(
        items, key=lambda i: (-math.prod(i.footprint), -max(i.footprint), i.instance_id)
    ):
        selected = None
        for page, free in enumerate(pages + [[usable]]):
            candidates = []
            for r in free:
                for angle, w, h in orientations(item):
                    if w + GUTTER <= r.w + 1e-9 and h + GUTTER <= r.h + 1e-9:
                        score = (
                            min(r.w - w - GUTTER, r.h - h - GUTTER),
                            max(r.w - w - GUTTER, r.h - h - GUTTER),
                            r.y,
                            r.x,
                            angle,
                        )
                        candidates.append((score, angle, Rect(r.x, r.y, w, h)))
            if candidates:
                _, angle, box = min(candidates)
                selected = page, angle, box
                if page == len(pages):
                    pages.append([usable])
                break
        if selected is None:
            raise ValueError(
                f"{item.instance_id}: footprint {item.footprint} cannot fit usable sheet"
            )
        page, angle, box = selected
        pages[page] = split_free(pages[page], Rect(box.x, box.y, box.w + GUTTER, box.h + GUTTER))
        placed.append((item, page, angle, box))
    return placed


def grid(items):
    ordered = sorted(items, key=lambda i: i.instance_id)
    assert ordered and all(
        i.footprint == ordered[0].footprint and i.rotations == ordered[0].rotations for i in ordered
    )
    candidates = []
    for angle, w, h in orientations(ordered[0]):
        cols = math.floor((SHEET[0] - 2 * MARGIN + GUTTER) / (w + GUTTER))
        rows = math.floor((SHEET[1] - 2 * MARGIN + GUTTER) / (h + GUTTER))
        if rows * cols:
            candidates.append((-rows * cols, angle, w, h, cols, rows))
    if not candidates:
        raise ValueError("identical footprint cannot fit usable sheet")
    _, angle, w, h, cols, rows = min(candidates)
    return [
        (
            item,
            i // (cols * rows),
            angle,
            Rect(
                MARGIN + (i % cols) * (w + GUTTER),
                MARGIN + ((i // cols) % rows) * (h + GUTTER),
                w,
                h,
            ),
        )
        for i, item in enumerate(ordered)
    ]


def matrix(item, angle, box):
    _, h = item.footprint
    a, b, c, d, e, f = (1, 0, 0, 1, box.x, box.y) if angle == 0 else (0, 1, -1, 0, box.x + h, box.y)
    k = item.keepout
    return (a, b, c, d, e + a * k + c * k, f + b * k + d * k)


def flip(matrix, axis="left-right"):
    a, b, c, d, e, f = matrix
    return (
        (-a, b, -c, d, SHEET[0] - e, f) if axis == "left-right" else (a, -b, c, -d, e, SHEET[1] - f)
    )


def transform(m, p):
    a, b, c, d, e, f = m
    return a * p[0] + c * p[1] + e, b * p[0] + d * p[1] + f


def area(points):
    return abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(points, points[1:] + points[:1]))) / 2


def verify(placements):
    usable = Rect(MARGIN, MARGIN, SHEET[0] - 2 * MARGIN, SHEET[1] - 2 * MARGIN)
    ids = [i.instance_id for i, *_ in placements]
    assert len(ids) == len(set(ids))
    for index, (item, page, angle, box) in enumerate(placements):
        assert usable.contains(box)
        m = matrix(item, angle, box)
        assert m[0] * m[3] - m[1] * m[2] == 1  # rigid, exact scale
        for p, q in zip(item.shape, item.shape[1:] + item.shape[:1]):
            assert math.isclose(math.dist(p, q), math.dist(transform(m, p), transform(m, q)))
        for axis in ("left-right", "top-bottom"):
            assert all(
                math.isclose(v, w, abs_tol=1e-9) for v, w in zip(flip(flip(m, axis), axis), m)
            )
            for p in item.shape:
                front, back = transform(m, p), transform(flip(m, axis), p)
                expected = (
                    (SHEET[0] - front[0], front[1])
                    if axis == "left-right"
                    else (front[0], SHEET[1] - front[1])
                )
                assert all(math.isclose(v, w, abs_tol=1e-9) for v, w in zip(back, expected))
        for _, other_page, _, other in placements[index + 1 :]:
            if page == other_page:
                assert not Rect(box.x, box.y, box.w + GUTTER, box.h + GUTTER).overlaps(other)


def element(parent, name, **attrs):
    return ET.SubElement(
        parent, f"{{{NS}}}{name}", {k.replace("_", "-"): str(v) for k, v in attrs.items()}
    )


def svg(placements, title, path):
    pages = max(p for _, p, _, _ in placements) + 1
    root = ET.Element(
        f"{{{NS}}}svg",
        dict(width="920", height=str(60 + pages * 340), viewBox=f"0 0 920 {60 + pages * 340}"),
    )
    element(root, "rect", width=920, height=60 + pages * 340, fill="white")
    element(root, "text", x=10, y=20, font_size=15).text = title
    element(root, "text", x=10, y=40, font_size=10).text = (
        "Study only: blue trim, orange conservative keepout, green usable area. "
        "Back shows physical correspondence, not prepared back artwork."
    )
    for page in range(pages):
        for face in (0, 1):
            group = element(root, "g", transform=f"translate({10 + face * 450},{80 + page * 340})")
            element(
                group, "text", x=0, y=-8, font_size=12
            ).text = f"Sheet {page + 1} — {'front' if face == 0 else 'paired back (left-right)'}"
            element(
                group,
                "rect",
                x=0,
                y=0,
                width=SHEET[0],
                height=SHEET[1],
                fill="#fafafa",
                stroke="#333",
                stroke_width=0.4,
            )
            element(
                group,
                "rect",
                x=MARGIN,
                y=MARGIN,
                width=SHEET[0] - 2 * MARGIN,
                height=SHEET[1] - 2 * MARGIN,
                fill="none",
                stroke="#36994d",
                stroke_width=0.4,
            )
            for item, p, angle, box in placements:
                if p != page:
                    continue
                x = box.x if face == 0 else SHEET[0] - box.x - box.w
                element(
                    group,
                    "rect",
                    x=x,
                    y=box.y,
                    width=box.w,
                    height=box.h,
                    fill="#fff2df",
                    stroke="#c88921",
                    stroke_width=0.3,
                )
                m = matrix(item, angle, box)
                m = m if face == 0 else flip(m)
                points = [transform(m, v) for v in item.shape]
                element(
                    group,
                    "polygon",
                    points=" ".join(f"{x},{y}" for x, y in points),
                    fill="#dceaf8",
                    stroke="#27639d",
                    stroke_width=0.5,
                )
                for fold in item.folds:
                    p1, p2 = transform(m, (fold, 0)), transform(m, (fold, item.size[1]))
                    element(
                        group,
                        "line",
                        x1=p1[0],
                        y1=p1[1],
                        x2=p2[0],
                        y2=p2[1],
                        stroke="#738dac",
                        stroke_width=0.35,
                        stroke_dasharray="2 2",
                    )
                element(
                    group, "text", x=x + 5, y=box.y + 12, font_size=8
                ).text = f"{item.instance_id} / {angle}°"
    ET.ElementTree(root).write(path, encoding="unicode")


def run():
    out = Path("output/har91-sheet-packing")
    out.mkdir(parents=True, exist_ok=True)
    triangle = ((0, 0), (120, 0), (60, 100))
    irregular = [Item(f"triangle-{i}", triangle, (120, 100)) for i in range(1, 4)]
    irregular += [
        Item(f"L-{i}", ((0, 0), (140, 0), (140, 40), (60, 40), (60, 100), (0, 100)), (140, 100))
        for i in range(1, 4)
    ]
    cases = [
        ("two-eight-panel", jcards(8, 2), grid),
        ("three-panel-grid", jcards(3, 8), grid),
        ("mixed-profiles", jcards(8, 1) + jcards(4, 2) + jcards(3, 2), maxrects),
        ("mixed-overflow", jcards(8, 2) + jcards(4, 3) + jcards(3, 3), maxrects),
        ("irregular-conservative", irregular, maxrects),
    ]
    audit = {}
    for name, items, packer in cases:
        placed = packer(items)
        verify(placed)
        assert placed == packer(list(reversed(items)))
        pages = max(p for _, p, _, _ in placed) + 1
        trim = sum(area(i.shape) for i in items)
        footprint = sum(math.prod(i.footprint) for i in items)
        audit[name] = dict(
            algorithm="grid" if packer == grid else "MaxRects best-short-side-fit",
            sheet_mm=SHEET,
            margin_mm=MARGIN,
            gutter_mm=GUTTER,
            envelope_note=(
                "3 mm each side: illustrative guide/bleed reservation; not generated bleed"
            ),
            sheets=pages,
            objects=len(items),
            trim_area_mm2=trim,
            reserved_area_mm2=footprint,
            unused_usable_area_mm2=pages * (SHEET[0] - 2 * MARGIN) * (SHEET[1] - 2 * MARGIN)
            - footprint,
            bounding_waste_mm2=footprint - trim,
            placements=[
                dict(
                    instance_id=i.instance_id,
                    sheet=p + 1,
                    rotation=a,
                    footprint_mm=asdict(b),
                    trim_polygon_mm=i.shape,
                    front_matrix=matrix(i, a, b),
                    paired_back_matrix=flip(matrix(i, a, b)),
                )
                for i, p, a, b in placed
            ],
        )
        svg(placed, name, out / (name + ".svg"))
        print(
            f"{name}: {len(items)} objects, {pages} sheets; "
            f"reserved/trim area {footprint:.1f}/{trim:.1f} mm2"
        )
    try:
        maxrects(
            jcards(8, 1)[0:1]
            + [Item("oversize", ((0, 0), (500, 0), (500, 400), (0, 400)), (500, 400))]
        )
    except ValueError as error:
        audit["expected_fit_failure"] = str(error)
    else:
        raise AssertionError("oversize object accepted")
    (out / "study.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
