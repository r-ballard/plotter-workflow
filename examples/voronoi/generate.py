"""Generate a reproducible, space-filling Voronoi drawing for the DPX-3300."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

Point = tuple[float, float]
Polygon = list[Point]
Edge = tuple[Point, Point]
ROOT: Polygon = [(10.0, 10.0), (190.0, 10.0), (190.0, 190.0), (10.0, 190.0)]


def area(polygon: Polygon) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1]
                   for a, b in zip(polygon, polygon[1:] + polygon[:1]))) / 2


def sample_inside(polygon: Polygon, rng: random.Random) -> Point:
    triangles = [(polygon[0], polygon[index], polygon[index + 1])
                 for index in range(1, len(polygon) - 1)]
    weights = [area([a, b, c]) for a, b, c in triangles]
    target = rng.random() * sum(weights)
    triangle = triangles[-1]
    for candidate, weight in zip(triangles, weights):
        target -= weight
        if target <= 0:
            triangle = candidate
            break
    a, b, c = triangle
    u, v = math.sqrt(rng.random()), rng.random()
    return ((1 - u) * a[0] + u * (1 - v) * b[0] + u * v * c[0],
            (1 - u) * a[1] + u * (1 - v) * b[1] + u * v * c[1])


def clip_halfplane(polygon: Polygon, dx: float, dy: float, threshold: float) -> Polygon:
    if not polygon:
        return []
    output: Polygon = []
    previous = polygon[-1]
    previous_side = dx * previous[0] + dy * previous[1] - threshold
    for current in polygon:
        current_side = dx * current[0] + dy * current[1] - threshold
        if (previous_side <= 1e-9) != (current_side <= 1e-9):
            fraction = previous_side / (previous_side - current_side)
            output.append((previous[0] + fraction * (current[0] - previous[0]),
                           previous[1] + fraction * (current[1] - previous[1])))
        if current_side <= 1e-9:
            output.append(current)
        previous, previous_side = current, current_side
    clean: Polygon = []
    for point in output:
        if not clean or math.dist(point, clean[-1]) > 1e-9:
            clean.append(point)
    if len(clean) > 1 and math.dist(clean[0], clean[-1]) <= 1e-9:
        clean.pop()
    return clean


def partition(parent: Polygon, sites: list[Point]) -> list[Polygon]:
    cells = []
    for index, site in enumerate(sites):
        cell = parent[:]
        for other_index, other in enumerate(sites):
            if other_index == index:
                continue
            dx, dy = other[0] - site[0], other[1] - site[1]
            threshold = (other[0] ** 2 + other[1] ** 2 - site[0] ** 2 - site[1] ** 2) / 2
            cell = clip_halfplane(cell, dx, dy, threshold)
        cells.append(cell)
    return cells


def on_boundary(a: Point, b: Point, polygon: Polygon) -> bool:
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length_squared = dx * dx + dy * dy
        if length_squared <= 1e-15:
            continue
        if all(abs(dx * (point[1] - start[1]) - dy * (point[0] - start[0])) <= 1e-6
               and -1e-6 <= (point[0] - start[0]) * dx + (point[1] - start[1]) * dy <= length_squared + 1e-6
               for point in (a, b)):
            return True
    return False


def diagram(seed: int, branch: int, depth: int) -> tuple[list[Edge], list[Polygon]]:
    rng = random.Random(seed)
    edges: set[Edge] = set()
    leaves: list[Polygon] = []

    def divide(parent: Polygon, remaining: int) -> None:
        if remaining == 0:
            leaves.append(parent)
            return
        sites = [sample_inside(parent, rng) for _ in range(branch)]
        children = partition(parent, sites)
        for child in children:
            for start, end in zip(child, child[1:] + child[:1]):
                if on_boundary(start, end, parent):
                    continue
                rounded = tuple(sorted(((round(start[0], 3), round(start[1], 3)),
                                        (round(end[0], 3), round(end[1], 3)))))
                if rounded[0] != rounded[1]:
                    edges.add(rounded)
            divide(child, remaining - 1)

    divide(ROOT, depth)
    return sorted(edges), leaves


def svg_text(edges: list[Edge]) -> str:
    paths = ['      <path d="M 10.000 10.000 L 190.000 10.000 L 190.000 190.000 L 10.000 190.000 Z"/>']
    paths.extend(f'      <path d="M {a[0]:.3f} {a[1]:.3f} L {b[0]:.3f} {b[1]:.3f}"/>'
                 for a, b in edges)
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
    parser.add_argument("--branch", type=int, default=3)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--max-path-mm", type=float, default=20000)
    parser.add_argument("--max-cells", type=int, default=2000)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not 2 <= args.branch <= 5:
        parser.error("--branch must be between 2 and 5")
    if not 1 <= args.depth <= 7:
        parser.error("--depth must be between 1 and 7")
    if not 1 <= args.max_cells <= 5000 or args.branch ** args.depth > args.max_cells:
        parser.error("requested recursion exceeds --max-cells (1-5000)")
    if not math.isfinite(args.max_path_mm) or args.max_path_mm <= 0:
        parser.error("--max-path-mm must be positive and finite")

    names = ("voronoi.svg", "voronoi.penplan.json", "voronoi.json")
    destinations = [args.output_dir / name for name in names]
    existing = [path for path in destinations if path.exists()]
    if existing and not args.overwrite:
        parser.error(f"output already exists: {existing[0]}; use --overwrite intentionally")

    edges, leaves = diagram(args.seed, args.branch, args.depth)
    area_error = abs(sum(area(cell) for cell in leaves) - area(ROOT))
    if area_error > 1e-5:
        parser.error(f"Voronoi cells do not cover the drawing area: {area_error:.6f} mm2 error")
    length = 720.0 + sum(math.dist(a, b) for a, b in edges)
    if length > args.max_path_mm:
        parser.error(f"source pen-down path {length:.1f} mm exceeds --max-path-mm")
    svg = svg_text(edges)
    plan = {
        "schema_version": 1,
        "policy": "preserve",
        "slots": [{"slot": 1, "label": "black fine", "tool": "technical pen", "color": "black"}],
    }
    manifest = {
        "schema_version": 1,
        "algorithm": "recursive-clipped-voronoi",
        "seed": args.seed,
        "branch": args.branch,
        "depth": args.depth,
        "cell_count": len(leaves),
        "edge_count": len(edges),
        "drawing_area_mm2": area(ROOT),
        "area_error_mm2": round(area_error, 9),
        "source_pen_down_mm": round(length, 3),
        "max_path_mm": args.max_path_mm,
        "svg_sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
    }
    contents = (svg, json.dumps(plan, indent=2) + "\n", json.dumps(manifest, indent=2) + "\n")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path, content in zip(destinations, contents):
        path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Generated {len(leaves)} cells, {len(edges)} internal edges in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
