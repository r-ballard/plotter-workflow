"""Regression tests for the cootie-catcher semantic template geometry."""

from __future__ import annotations

from collections import Counter

from imposition.objects.cootie_catcher import COOTIE_CATCHER

Point = tuple[float, float]
Edge = tuple[Point, Point]


def _canonical_point(point: Point) -> Point:
    return (round(point[0], 9), round(point[1], 9))


def _canonical_edge(first: Point, second: Point) -> Edge:
    first = _canonical_point(first)
    second = _canonical_point(second)
    return tuple(sorted((first, second)))  # type: ignore[return-value]


def _slot_edges() -> Counter[Edge]:
    counts: Counter[Edge] = Counter()
    for slot in COOTIE_CATCHER.slots:
        polygon = tuple(slot.polygon)
        for index, first in enumerate(polygon):
            second = polygon[(index + 1) % len(polygon)]
            counts[_canonical_edge(first, second)] += 1
    return counts


EXPECTED_TEMPLATE_INTERNAL_EDGES: frozenset[Edge] = frozenset(
    {
        # Outer-panel L boundaries.
        _canonical_edge((0.25, 0.0), (0.25, 0.25)),
        _canonical_edge((0.0, 0.25), (0.25, 0.25)),
        _canonical_edge((0.75, 0.0), (0.75, 0.25)),
        _canonical_edge((0.75, 0.25), (1.0, 0.25)),
        _canonical_edge((0.0, 0.75), (0.25, 0.75)),
        _canonical_edge((0.25, 0.75), (0.25, 1.0)),
        _canonical_edge((0.75, 0.75), (1.0, 0.75)),
        _canonical_edge((0.75, 0.75), (0.75, 1.0)),
        # Edge-midpoint to quarter-point diagonals.
        _canonical_edge((0.5, 0.0), (0.25, 0.25)),
        _canonical_edge((0.5, 0.0), (0.75, 0.25)),
        _canonical_edge((1.0, 0.5), (0.75, 0.25)),
        _canonical_edge((1.0, 0.5), (0.75, 0.75)),
        _canonical_edge((0.5, 1.0), (0.75, 0.75)),
        _canonical_edge((0.5, 1.0), (0.25, 0.75)),
        _canonical_edge((0.0, 0.5), (0.25, 0.75)),
        _canonical_edge((0.0, 0.5), (0.25, 0.25)),
        # Quarter-point to center diagonals.
        _canonical_edge((0.25, 0.25), (0.5, 0.5)),
        _canonical_edge((0.75, 0.25), (0.5, 0.5)),
        _canonical_edge((0.75, 0.75), (0.5, 0.5)),
        _canonical_edge((0.25, 0.75), (0.5, 0.5)),
        # Center cross.
        _canonical_edge((0.5, 0.0), (0.5, 0.5)),
        _canonical_edge((0.5, 0.5), (0.5, 1.0)),
        _canonical_edge((0.0, 0.5), (0.5, 0.5)),
        _canonical_edge((0.5, 0.5), (1.0, 0.5)),
    }
)


def test_panel_edges_match_reference_template() -> None:
    """The 20 semantic polygons must reproduce the validated flat template."""
    edge_counts = _slot_edges()
    internal_edges = {
        edge
        for edge, count in edge_counts.items()
        if count == 2
    }

    assert len(internal_edges) == 24
    assert internal_edges == EXPECTED_TEMPLATE_INTERNAL_EDGES


def test_template_has_no_nonmanifold_internal_edges() -> None:
    """No semantic boundary may be shared by more than two panel polygons."""
    edge_counts = _slot_edges()

    assert all(count in {1, 2} for count in edge_counts.values())


def test_template_outer_boundary_is_unit_square() -> None:
    """Unshared edges must collectively trace only the unit-square perimeter."""
    edge_counts = _slot_edges()
    boundary_edges = {
        edge
        for edge, count in edge_counts.items()
        if count == 1
    }

    for first, second in boundary_edges:
        assert (
            (first[0] == second[0] == 0.0)
            or (first[0] == second[0] == 1.0)
            or (first[1] == second[1] == 0.0)
            or (first[1] == second[1] == 1.0)
        )
