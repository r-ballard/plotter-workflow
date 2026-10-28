import pytest
from imposition.jcard_config import load_jcard_config


def payload():
    return {"schema_version": 1, "sheet": "a3", "front_artwork": {"template": "front.json"}}


def test_defaults_and_paths(tmp_path):
    config = load_jcard_config(payload(), base_dir=tmp_path)
    assert config.selected_faces == ("front",)
    assert config.flip == "left-right"
    assert config.safe_inset_mm == 1.5875
    assert config.front_artwork.template == tmp_path / "front.json"
    assert config.front_artwork.mode == "independent"


@pytest.mark.parametrize(
    "update",
    [
        {"unknown": 1},
        {"schema_version": True},
        {"faces": "all"},
        {"margin_mm": True},
        {"margin_mm": float("nan")},
        {"origin_mm": None},
        {"safe_inset_mm": 6.35},
        {"guides": {"cut": 1}},
        {"back_artwork": {"template": "b.json"}},
        {"front_artwork": {"template": "x", "blank_panels": ["back-panel-1"]}},
        {"front_artwork": {"template": "x", "blank_panels": ["front-panel-1"] * 2}},
    ],
)
def test_strict_controls(tmp_path, update):
    with pytest.raises(ValueError):
        load_jcard_config(payload() | update, base_dir=tmp_path)


def test_back_only(tmp_path):
    config = load_jcard_config(
        {
            "schema_version": 1,
            "faces": "back",
            "sheet": {"width_mm": 500, "height_mm": 200},
            "back_artwork": {"template": "b.json"},
        },
        base_dir=tmp_path,
    )
    assert config.selected_faces == ("back",)
    assert config.front_artwork is None
