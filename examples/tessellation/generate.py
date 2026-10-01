"""Generate a reproducible, single-pen triangle mesh for the DPX-3300 workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

Point = tuple[float, float]


def mesh(seed: int, depth: int) -> list[tuple[Point, Point]]:
    rng = random.Random(seed)
    center = (100.0, 100.0)
    ring = []
    for index in range(12):
        angle = 2 * math.pi * index / 12 + rng.uniform(-0.08, 0.08)
        radius = rng.uniform(78.0, 88.0)
        ring.append((100 + radius * math.cos(angle), 100 + radius * math.sin(angle)))

    edges: set[tuple[Point, Point]] = set()

    def add_edge(a: Point, b: Point) -> None:
        start = (round(a[0], 3), round(a[1], 3))
        end = (round(b[0], 3), round(b[1], 3))
        if start != end:
            edges.add(tuple(sorted((start, end))))

    def divide(a: Point, b: Point, c: Point, remaining: int) -> None:
        if remaining == 0:
            add_edge(a, b)
            add_edge(b, c)
            add_edge(c, a)
            return
        weights = [rng.uniform(0.2, 0.45) for _ in range(3)]
        total = sum(weights)
        inside = (
            sum(point[0] * weight for point, weight in zip((a, b, c), weights)) / total,
            sum(point[1] * weight for point, weight in zip((a, b, c), weights)) / total,
        )
        divide(a, b, inside, remaining - 1)
        divide(b, c, inside, remaining - 1)
        divide(c, a, inside, remaining - 1)

    for index in range(len(ring)):
        divide(center, ring[index], ring[(index + 1) % len(ring)], depth)
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
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.depth <= 5:
        parser.error("--depth must be between 0 and 5")

    names = ("tessellation.svg", "tessellation.penplan.json", "tessellation.json")
    destinations = [args.output_dir / name for name in names]
    existing = [path for path in destinations if path.exists()]
    if existing and not args.overwrite:
        parser.error(f"output already exists: {existing[0]}; use --overwrite intentionally")

    edges = mesh(args.seed, args.depth)
    svg = svg_text(edges)
    plan = {
        "schema_version": 1,
        "policy": "preserve",
        "slots": [{"slot": 1, "label": "black fine", "tool": "technical pen", "color": "black"}],
    }
    manifest = {
        "schema_version": 1,
        "algorithm": "seeded-triangle-subdivision",
        "seed": args.seed,
        "depth": args.depth,
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
