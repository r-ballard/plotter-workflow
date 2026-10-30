"""Show conservative polygon bounds using the production packing core."""

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from imposition.sheet_packing.geometry import transform
from imposition.sheet_packing.model import (
    ObjectFootprint,
    PackingInstance,
    PolygonRegion,
    RectMM,
    SheetArea,
)
from imposition.sheet_packing.solver import pack


def main():
    outlines = (
        ((0, 0), (70, 0), (70, 20), (25, 20), (25, 60), (0, 60)),
        ((0, 0), (65, 0), (32.5, 55)),
    )
    footprints = (
        ObjectFootprint("L", (PolygonRegion(outlines[0]),), RectMM(0, 0, 70, 60), (0, 90)),
        ObjectFootprint("triangle", (PolygonRegion(outlines[1]),), RectMM(0, 0, 65, 55), (0, 90)),
    )
    items = tuple(PackingInstance(f"shape-{i}", footprints[i % 2]) for i in range(6))
    sheet = SheetArea(230, 170, RectMM(5, 5, 220, 160))
    result = pack(items, sheet, gutter=4, strategy="maxrects")
    root = ET.Element(
        "svg",
        xmlns="http://www.w3.org/2000/svg",
        width="230mm",
        height=f"{170 * result.sheet_count}mm",
        viewBox=f"0 0 230 {170 * result.sheet_count}",
    )
    lookup = {i.instance_id: i for i in items}
    for placed in result.placements:
        offset = 170 * placed.sheet_index
        bounds = placed.occupied_bounds
        ET.SubElement(
            root,
            "rect",
            x=str(bounds.x),
            y=str(bounds.y + offset),
            width=str(bounds.width),
            height=str(bounds.height),
            fill="none",
            stroke="#aaa",
            **{"stroke-width": "0.3", "stroke-dasharray": "2 1"},
        )
        for region in lookup[placed.instance_id].footprint.trim_regions:
            points = [transform(placed.front_matrix, p) for p in region.outer]
            ET.SubElement(
                root,
                "polygon",
                points=" ".join(f"{x},{y + offset}" for x, y in points),
                fill="none",
                stroke="#174b70",
                **{"stroke-width": "0.5"},
            )
    target = Path("output/sheet-packing-production/irregular-bounds.svg")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    print(target)


if __name__ == "__main__":
    main()
