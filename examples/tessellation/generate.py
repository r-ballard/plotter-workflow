"""Generate a reproducible, distributed Delaunay mesh for the DPX-3300 workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

Point = tuple[float, float]


def sites(seed: int, count: int) -> list[Point]:
    rng = random.Random(seed)
    boundary_count = min(18, count // 4)
    points = []
    for index in range(boundary_count):
        angle = 2 * math.pi * (index + rng.uniform(-0.12, 0.12)) / boundary_count
        radius = rng.uniform(82.0, 88.0)
        points.append((100 + radius * math.cos(angle), 100 + radius * math.sin(angle)))
    for _ in range(count - boundary_count):
        angle = rng.uniform(0, 2 * math.pi)
        radius = 80 * math.sqrt(rng.random())
        points.append((100 + radius * math.cos(angle), 100 + radius * math.sin(angle)))
    return [(round(x, 3), round(y, 3)) for x, y in points]


def in_circumcircle(a: Point, b: Point, c: Point, p: Point) -> bool:
    ax, ay = a[0] - p[0], a[1] - p[1]
    bx, by = b[0] - p[0], b[1] - p[1]
    cx, cy = c[0] - p[0], c[1] - p[1]
    det = ((ax * ax + ay * ay) * (bx * cy - cx * by)
           - (bx * bx + by * by) * (ax * cy - cx * ay)
           + (cx * cx + cy * cy) * (ax * by - bx * ay))
    orientation = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return det * orientation > 0


def mesh(seed: int, count: int) -> list[tuple[Point, Point]]:
    points = sites(seed, count)
    # Bowyer-Watson triangulation. The supertriangle is outside the 200 mm art.
    all_points = points + [(-1000.0, -1000.0), (100.0, 1200.0), (1200.0, -1000.0)]
    super_ids = (count, count + 1, count + 2)
    triangles = [super_ids]
    for point_id in range(count):
        point = all_points[point_id]
        bad = [triangle for triangle in triangles if in_circumcircle(
            *(all_points[index] for index in triangle), point,
        )]
        boundary: dict[tuple[int, int], int] = {}
        for a, b, c in bad:
            for edge in ((a, b), (b, c), (c, a)):
                edge = tuple(sorted(edge))
                boundary[edge] = boundary.get(edge, 0) + 1
        triangles = [triangle for triangle in triangles if triangle not in bad]
        triangles.extend((a, b, point_id) for (a, b), frequency in boundary.items()
                         if frequency == 1)
    edges = set()
    for a, b, c in triangles:
        if any(index in super_ids for index in (a, b, c)):
            continue
        edges.update(tuple(sorted((all_points[start], all_points[end])))
                     for start, end in ((a, b), (b, c), (c, a)))
    return sorted(edges)


def svg_text(edges: list[tuple[Point, Point]]) -> str:
    paths = [
        f'      <path d="M {a[0]:.3f} {a[1]:.3f} L {b[0]:.3f} {b[1]:.3f}"/>'
        for a, b in edges
    ]
    return "\n".join([
        '<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="200mm" viewBox="0 0 200 200">',
        '  <g id="pen-1" data-pen="1" data-generations="0" fill="none" stroke="#202020" stroke-width="0.25">',
        '    <g data-generation="0">',
        *paths,
        "    </g>",
        "  </g>",
        "</svg>",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=17)
    density = parser.add_mutually_exclusive_group()
    density.add_argument("--points", type=int, help="number of distributed sites (20-1000)")
    density.add_argument("--depth", type=int, help="legacy density shortcut, 0-5")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.depth is not None and not 0 <= args.depth <= 5:
        parser.error("--depth must be between 0 and 5")
    point_count = args.points if args.points is not None else 50 * (1 + (args.depth if args.depth is not None else 3))
    if not 20 <= point_count <= 1000:
        parser.error("--points must be between 20 and 1000")

    names = ("tessellation.svg", "tessellation.penplan.json", "tessellation.json")
    destinations = [args.output_dir / name for name in names]
    existing = [path for path in destinations if path.exists()]
    if existing and not args.overwrite:
        parser.error(f"output already exists: {existing[0]}; use --overwrite intentionally")

    edges = mesh(args.seed, point_count)
    svg = svg_text(edges)
    plan = {
        "schema_version": 1,
        "policy": "preserve",
        "slots": [{"slot": 1, "label": "black fine", "tool": "technical pen", "color": "black"}],
    }
    manifest = {
        "schema_version": 1,
        "algorithm": "seeded-delaunay-triangulation",
        "seed": args.seed,
        "depth": args.depth,
        "point_count": point_count,
        "edge_count": len(edges),
        "svg_sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
    }
    contents = (svg, json.dumps(plan, indent=2) + "\n", json.dumps(manifest, indent=2) + "\n")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path, content in zip(destinations, contents):
        path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Generated {len(edges)} edges in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
