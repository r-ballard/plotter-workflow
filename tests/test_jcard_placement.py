import pytest
from imposition.jcard_config import load_jcard_config
from imposition.jcard_placement import resolve_jcard_placement


def config(tmp_path, **overrides):
    return load_jcard_config(
        {
            "schema_version": 1,
            "sheet": {"width_mm": 500, "height_mm": 250},
            "faces": "both",
            "origin_mm": [20, 30],
            "front_artwork": {"template": "f.json"},
            "back_artwork": {"template": "b.json"},
        }
        | overrides,
        base_dir=tmp_path,
    )


@pytest.mark.parametrize(
    "flip,expected",
    [("left-right", (1, 0, 0, 1, 73.6, 30)), ("top-bottom", (-1, 0, 0, -1, 426.4, 220))],
)
def test_off_center_pair(tmp_path, flip, expected):
    placement = resolve_jcard_placement(config(tmp_path, flip=flip))
    assert placement.face_matrix("front") == (1, 0, 0, 1, 20, 30)
    assert placement.face_matrix("back") == pytest.approx(expected)
    a, b, c, d, _, _ = placement.face_matrix("back")
    assert a * d - b * c == 1
    assert placement.face_guides("front") == ()


@pytest.mark.parametrize(
    "overrides",
    [
        {"sheet": "a4"},
        {"origin_mm": [100, 30]},
        {"margin_mm": 25},
        {"origin_mm": [1, 1], "guides": {"registration": True}},
    ],
)
def test_no_silent_fit(tmp_path, overrides):
    with pytest.raises(ValueError):
        resolve_jcard_placement(config(tmp_path, **overrides))


def test_guide_channels(tmp_path):
    placement = resolve_jcard_placement(
        config(tmp_path, guides={"cut": True, "fold": True, "registration": True})
    )
    guides = placement.face_guides("front")
    assert len([g for g in guides if g.kind == "cut"]) == 1
    assert len([g for g in guides if g.kind == "fold"]) == 7
    assert len([g for g in guides if g.kind == "registration"]) == 6
