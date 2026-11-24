import pytest

from imposition.artwork_export import build_artwork_job
from imposition.kaleidocycle_artwork import resolve_kaleidocycle_state
from scripts.generate_triangular_kaleidocycle_samples import build_recipe


def test_twelve_recipes_use_common_catalog_and_valid_triangle_handoffs():
    catalogs = []
    for style in ("curves", "light-fill", "multiscale"):
        for state in "ABCD":
            layout = resolve_kaleidocycle_state(
                state, width_mm=213.531, tetrahedron_count=8
            )
            recipe = build_recipe(style, state, layout)
            job = build_artwork_job(layout, recipe)
            catalogs.append(job["passes"][0]["logical_layers"])
            assert len(job["domains"]) == 8
            assert job["passes"][0]["algorithm"].startswith("truchet-triangular")
    assert all(c == catalogs[0] for c in catalogs)
    assert len(catalogs[0]) == 3


@pytest.mark.parametrize("style,state", [("other", "A"), ("curves", "AB")])
def test_invalid_artwork_variant_rejected(style, state):
    with pytest.raises(ValueError):
        build_recipe(style, state, None)
