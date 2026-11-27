import copy

import pytest

from imposition.artwork_export import build_artwork_job, write_layout_export
from imposition.artwork_return import _load_handoff
from imposition.kaleidocycle_artwork import resolve_kaleidocycle_state


@pytest.mark.parametrize("algorithm", ["ball-stick", "ball-stick-3d"])
def test_ball_stick_export_replays_without_truchet_controls(tmp_path, algorithm):
    layout = resolve_kaleidocycle_state("A", width_mm=161.291)
    recipe = {
        "schema_version": 1,
        "seed": 23,
        "passes": [
            {
                "id": "network",
                "algorithm": algorithm,
                "target_domain_ids": [],
                "parameters": {"rows": 5, "columns": 5},
                "logical_layers": [{"id": "sticks"}, {"id": "balls"}],
            }
        ],
    }
    before = copy.deepcopy(recipe)
    job = build_artwork_job(layout, recipe)
    assert recipe == before
    assert len(job["domains"]) == 6
    assert job["passes"][0]["parameters"] == before["passes"][0]["parameters"]
    assert job["passes"][0]["composition"]["mode"] == "shared"
    assert build_artwork_job(layout, job) == job
    out = write_layout_export(layout, recipe, tmp_path / "export")
    report, _ = _load_handoff(out / "layout-handoff.json")
    assert report["producer_request"] == job


def test_sample_recipes_are_distinct_and_use_six_cell_transport():
    from scripts.generate_ball_stick_kaleidocycle_samples import (
        STYLES,
        WIDTH_MM,
        build_recipe,
    )

    layout = resolve_kaleidocycle_state("A", width_mm=WIDTH_MM)
    recipes = [build_recipe(style, "A") for style in STYLES]
    assert WIDTH_MM * 5 / 12.35 == pytest.approx(65.3)
    assert len({r["seed"] for r in recipes}) == 3
    assert recipes[1]["passes"][0]["parameters"]["lattice"] == "honeycomb"
    assert "deformation" in recipes[2]["passes"][0]["parameters"]
    for recipe in recipes:
        job = build_artwork_job(layout, recipe)
        assert len(job["domains"]) == 6
        assert [v["id"] for v in job["passes"][0]["logical_layers"]] == [
            "sticks",
            "balls",
        ]
