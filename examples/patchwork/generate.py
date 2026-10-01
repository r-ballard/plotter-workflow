"""Generate reproducible cluster-and-hull artwork for the DPX-3300 workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

Point = tuple[float, float]
Polygon = list[Point]


def convex_hull(points: list[Point]) -> Polygon:
    ordered = sorted(set(points))

    def cross(a: Point, b: Point, c: Point) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    lower: Polygon = []
    for point in ordered:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: Polygon = []
    for point in reversed(ordered):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def cluster_indices(points: list[Point], count: int, rng: random.Random) -> list[list[int]]:
    centroids = rng.sample(points, count)
    clusters: list[list[int]] = []
    for _ in range(10):
        clusters = [[] for _ in range(count)]
        for index, point in enumerate(points):
            closest = min(range(count), key=lambda center: math.dist(point, centroids[center]))
            clusters[closest].append(index)
        centroids = [
            (sum(points[i][0] for i in cluster) / len(cluster),
             sum(points[i][1] for i in cluster) / len(cluster)) if cluster else centroids[index]
            for index, cluster in enumerate(clusters)
        ]
    return clusters


def area(a: Point, b: Point, c: Point) -> float:
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2


def sample_inside(polygon: Polygon, count: int, rng: random.Random) -> list[Point]:
    triangles = [(polygon[0], polygon[index], polygon[index + 1])
                 for index in range(1, len(polygon) - 1)]
    weights = [area(*triangle) for triangle in triangles]
    total = sum(weights)
    if total <= 0:
        return []
    points = []
    for _ in range(count):
        target = rng.random() * total
        triangle = triangles[-1]
        for candidate, weight in zip(triangles, weights):
            target -= weight
            if target <= 0:
                triangle = candidate
                break
        a, b, c = triangle
        u = math.sqrt(rng.random())
        v = rng.random()
        points.append((round((1 - u) * a[0] + u * (1 - v) * b[0] + u * v * c[0], 3),
                       round((1 - u) * a[1] + u * (1 - v) * b[1] + u * v * c[1], 3)))
    return points


def patchwork(seed: int, count: int, clusters: int, depth: int) -> list[Polygon]:
    rng = random.Random(seed)
    points = [(round(rng.uniform(10, 190), 3), round(rng.uniform(10, 190), 3))
              for _ in range(count)]
    polygons: list[Polygon] = []

    def fracture(region_points: list[Point], remaining: int) -> None:
        while len(region_points) >= 3 * clusters:
            groups = cluster_indices(region_points, clusters, rng)
            eligible = [(len(group), index, group) for index, group in enumerate(groups)
                        if len(group) >= 3]
            if not eligible:
                break
            _, _, chosen = min(eligible)
            hull = convex_hull([region_points[index] for index in chosen])
            if len(hull) < 3:
                break
            polygons.append(hull)
            selected = set(chosen)
            region_points = [point for index, point in enumerate(region_points)
                             if index not in selected]
            if remaining:
                children = sample_inside(hull, min(250, max(100, len(chosen))), rng)
                fracture(children, remaining - 1)

    fracture(points, depth)
    return polygons


def perimeter(polygon: Polygon) -> float:
    return sum(math.dist(point, polygon[(index + 1) % len(polygon)])
               for index, point in enumerate(polygon))


def svg_text(polygons: list[Polygon]) -> str:
    paths = []
    for polygon in polygons:
        points = " L ".join(f"{x:.3f} {y:.3f}" for x, y in polygon)
        paths.append(f'      <path d="M {points} Z"/>')
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
    parser.add_argument("--points", type=int, default=2000)
    parser.add_argument("--clusters", type=int, default=3)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--max-path-mm", type=float, default=20000)
    parser.add_argument("--max-polygons", type=int, default=2500)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not 50 <= args.points <= 5000:
        parser.error("--points must be between 50 and 5000")
    if not 2 <= args.clusters <= 8:
        parser.error("--clusters must be between 2 and 8")
    if not 0 <= args.depth <= 2:
        parser.error("--depth must be between 0 and 2")
    if not math.isfinite(args.max_path_mm) or args.max_path_mm <= 0:
        parser.error("--max-path-mm must be positive and finite")
    if not 1 <= args.max_polygons <= 5000:
        parser.error("--max-polygons must be between 1 and 5000")

    names = ("patchwork.svg", "patchwork.penplan.json", "patchwork.json")
    destinations = [args.output_dir / name for name in names]
    existing = [path for path in destinations if path.exists()]
    if existing and not args.overwrite:
        parser.error(f"output already exists: {existing[0]}; use --overwrite intentionally")

    polygons = patchwork(args.seed, args.points, args.clusters, args.depth)
    if not polygons:
        parser.error("no plot-ready polygons were generated")
    path_mm = sum(perimeter(polygon) for polygon in polygons)
    if len(polygons) > args.max_polygons or path_mm > args.max_path_mm:
        parser.error(f"job exceeds limit: {len(polygons)} polygons, {path_mm:.1f} mm pen-down path")
    svg = svg_text(polygons)
    plan = {
        "schema_version": 1,
        "policy": "preserve",
        "slots": [{"slot": 1, "label": "black fine", "tool": "technical pen", "color": "black"}],
    }
    manifest = {
        "schema_version": 1,
        "algorithm": "seeded-cluster-convex-hull",
        "seed": args.seed,
        "point_count": args.points,
        "cluster_count": args.clusters,
        "depth": args.depth,
        "polygon_count": len(polygons),
        "pen_down_mm": round(path_mm, 3),
        "max_path_mm": args.max_path_mm,
        "max_polygons": args.max_polygons,
        "svg_sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
    }
    contents = (svg, json.dumps(plan, indent=2) + "\n", json.dumps(manifest, indent=2) + "\n")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path, content in zip(destinations, contents):
        path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Generated {len(polygons)} polygons, {path_mm:.1f} mm pen-down path in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
