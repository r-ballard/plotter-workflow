import copy

import pytest

from imposition.artwork_export import build_artwork_job, write_layout_export
from imposition.artwork_return import _load_handoff
from imposition.kaleidocycle_artwork import resolve_kaleidocycle_state


def recipe(algorithm):
    parameters = {"curve_layer_id": "curve", "region_fills": {}}
    if algorithm == "truchet-triangular":
        parameters["tile_size"] = 80.0
    else:
        parameters.update(base_tile_size=160.0, max_depth=1, split_probability=0.35)
    return {
        "schema_version": 1,
        "seed": 31,
        "domains": [],
        "passes": [
            {
                "id": "tiles",
                "algorithm": algorithm,
                "target_domain_ids": [],
                "parameters": parameters,
                "logical_layers": [
                    {"id": "curve"},
                    {"id": "vertex-fill"},
                    {"id": "interstitial-fill"},
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    "algorithm", ["truchet-triangular", "truchet-triangular-multiscale"]
)
def test_triangle_recipe_exports_replays_and_preserves_binding_hashes(
    tmp_path, algorithm
):
    layout = resolve_kaleidocycle_state("A", width_mm=213.531, tetrahedron_count=8)
    template = recipe(algorithm)
    before = copy.deepcopy(template)
    job = build_artwork_job(layout, template)
    assert template == before
    assert job["passes"][0]["algorithm"] == algorithm
    assert job["passes"][0]["parameters"]["curve_layer_id"] == "curve"
    assert "curve_layer_ids" not in job["passes"][0]["parameters"]
    assert len(job["domains"]) == len(job["composition_transforms"]) == 8
    assert build_artwork_job(layout, job) == job
    export = write_layout_export(layout, template, tmp_path / "export")
    report, restored = _load_handoff(export / "layout-handoff.json")
    assert report["producer_request"] == job
    assert restored.settings["width_mm"] == 213.531


@pytest.mark.parametrize("value", [None, "", True, [], "missing"])
def test_triangle_curve_layer_must_be_declared_scalar(value):
    p = recipe("truchet-triangular")
    p["passes"][0]["parameters"]["curve_layer_id"] = value
    with pytest.raises(ValueError, match="curve_layer_id"):
        build_artwork_job(
            resolve_kaleidocycle_state("A", width_mm=213.531, tetrahedron_count=8), p
        )


def test_triangle_rejects_classic_plural_palette():
    p = recipe("truchet-triangular")
    p["passes"][0]["parameters"]["curve_layer_ids"] = ["curve"]
    with pytest.raises(ValueError, match="curve_layer"):
        build_artwork_job(
            resolve_kaleidocycle_state("A", width_mm=213.531, tetrahedron_count=8), p
        )
