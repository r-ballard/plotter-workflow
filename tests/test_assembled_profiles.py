import copy
import pytest
from imposition.artwork_layout import MM_TO_PX, rect, affine


def profile():
    side = 100 * MM_TO_PX / 4
    return dict(
        schema_version=1,
        profile_id="example-folded",
        object_id="cootie_catcher",
        view="folded-outer",
        validation_status="provisional",
        units="svg-px",
        window=[0, 0, side * 2, side * 2],
        panels=[
            dict(
                slot_id=f"outer-{i + 1}",
                canvas_polygon=rect(0, 0, side, side),
                matrix=[1, 0, 0, 1, i % 2 * side, i // 2 * side],
            )
            for i in range(4)
        ],
    )


def test_explicit_profile_preserves_corner_maps():
    from imposition.assembled_profiles import load_cootie_assembled_profile

    p = profile()
    s = 100 * MM_TO_PX / 4
    p["panels"][1]["matrix"] = [-1, 0, 0, 1, 2 * s, 0]
    layout = load_cootie_assembled_profile(p, square_size_mm=100.0)
    assert layout.validation_status == "provisional" and len(layout.panels) == 4
    assert affine(layout.panels[1].assembled_matrix, (0, 0)) == (2 * s, 0)
    assert layout.panels[0].binding["slot"] == "outer-1"
    assert "up_vector" in layout.panels[0].binding


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(schema_version=True),
        lambda p: p.update(view="flat-sheet"),
        lambda p: p.update(validation_status="guessed"),
        lambda p: p["panels"].pop(),
        lambda p: p["panels"][0].update(slot_id="outer-2"),
        lambda p: p["panels"][0].update(matrix=[0, 0, 0, 0, 0, 0]),
        lambda p: p["panels"][0].update(matrix=[1, 0, 0, 1, float("inf"), 0]),
        lambda p: p["panels"][0].update(canvas_polygon=rect(0, 0, 10, 10)),
        lambda p: p.update(window=[0, 0, 1, 1]),
        lambda p: p.update(unknown=1),
    ],
)
def test_missing_ambiguous_and_unsafe_profile(change):
    from imposition.assembled_profiles import load_cootie_assembled_profile

    p = copy.deepcopy(profile())
    change(p)
    with pytest.raises(ValueError):
        load_cootie_assembled_profile(p, square_size_mm=100.0)
