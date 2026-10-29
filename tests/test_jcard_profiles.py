from dataclasses import FrozenInstanceError

import pytest
from imposition.jcard_config import load_jcard_config
from imposition.jcard_placement import resolve_jcard_placement, transform
from imposition.jcard_profiles import get_jcard_profile
from imposition.objects.cassette_jcard import JCard

EXPECTED = {
    3: ((25.4, 12.7, 65.0875), 103.1875),
    4: ((26.9875, 12.7, 65.0875, 63.5), 168.275),
    5: ((26.9875, 12.7, 65.0875, 63.5, 61.9125), 230.1875),
    6: ((26.9875, 12.7, 65.0875, 63.5, 61.9125, 60.325), 290.5125),
    7: ((26.9875, 12.7, 65.0875, 63.5, 61.9125, 60.325, 58.7375), 349.25),
    8: ((26.9875, 12.7, 65.0875, 63.5, 61.9125, 60.325, 58.7375, 57.15), 406.4),
}


def profile_config(tmp_path, n, **overrides):
    return load_jcard_config(
        {
            "schema_version": 1,
            "profile": f"standard-jcard-{n}-panel-v1",
            "faces": "both",
            "sheet": "a3",
            "front_artwork": {"template": "front.json"},
            "back_artwork": {"template": "back.json"},
        }
        | overrides,
        base_dir=tmp_path,
    )


@pytest.mark.parametrize("n", EXPECTED)
@pytest.mark.parametrize("face", ["front", "back"])
def test_checked_profile_geometry(n, face):
    identifier = f"standard-jcard-{n}-panel-v1"
    profile = get_jcard_profile(identifier)
    card = JCard(face, identifier)
    assert profile.panel_widths_mm == card.panel_widths_mm == EXPECTED[n][0]
    assert profile.trim_size_mm == card.trim_size_mm == (EXPECTED[n][1], 101.6)
    assert len(profile.roles) == profile.panel_count == len(card.slots) == n
    assert len(profile.source_sha256[0]) == 64
    assert len(card.native_guides()) == n
    previous = 0
    for i, slot in enumerate(card.slots):
        number = i + 1 if face == "front" else n - i
        assert slot.slot_id == f"{face}-panel-{number}"
        assert slot.polygon[0][0] == pytest.approx(previous)
        assert (slot.polygon[1][0] - previous) * card.trim_size_mm[0] == pytest.approx(
            EXPECTED[n][0][number - 1]
        )
        previous = slot.polygon[1][0]
    assert previous == 1
    with pytest.raises(FrozenInstanceError):
        profile.profile_id = "other"


@pytest.mark.parametrize(
    "value", [None, True, 3, {}, "standard-jcard-2-panel-v1", "nac-jcard-3-panel-v1"]
)
def test_only_explicit_verified_records(value):
    with pytest.raises(ValueError):
        get_jcard_profile(value)


@pytest.mark.parametrize("n", EXPECTED)
@pytest.mark.parametrize("flip", ["left-right", "top-bottom"])
def test_profile_flip_pairs_all_panel_corners(tmp_path, n, flip):
    config = profile_config(
        tmp_path, n, sheet={"width_mm": 500, "height_mm": 250}, origin_mm=[20, 30], flip=flip
    )
    placement = resolve_jcard_placement(config)
    w, h = EXPECTED[n][1], 101.6
    assert placement.front_reference.width_mm == w
    front = JCard("front", config.profile).slots
    for back_slot in JCard("back", config.profile).slots:
        number = int(back_slot.slot_id.rsplit("-", 1)[1])
        f = [
            transform(placement.face_matrix("front"), (x * w, y * h))
            for x, y in front[number - 1].polygon
        ]
        expected = {
            (
                round(500 - x if flip == "left-right" else x, 7),
                round(y if flip == "left-right" else 250 - y, 7),
            )
            for x, y in f
        }
        actual = {
            tuple(round(v, 7) for v in transform(placement.face_matrix("back"), (x * w, y * h)))
            for x, y in back_slot.polygon
        }
        assert actual == expected


@pytest.mark.parametrize("n", [3, 4, 5])
@pytest.mark.parametrize("sheet", ["letter", "a4"])
def test_small_profile_sheet_fit(tmp_path, n, sheet):
    config = profile_config(tmp_path, n, sheet=sheet, margin_mm=3, guides={"registration": True})
    assert resolve_jcard_placement(config).front_reference.width_mm == EXPECTED[n][1]


def test_marks_do_not_silently_recenter_small_profile(tmp_path):
    config = profile_config(
        tmp_path, 3, sheet="letter", origin_mm=[3, 3], margin_mm=3, guides={"registration": True}
    )
    with pytest.raises(ValueError, match="registration"):
        resolve_jcard_placement(config)


def test_blank_slots_follow_profile_count(tmp_path):
    with pytest.raises(ValueError, match="blank"):
        profile_config(
            tmp_path, 3, front_artwork={"template": "f.json", "blank_panels": ["front-panel-4"]}
        )


def test_existing_nac_default_preserved():
    assert JCard().profile == "nac-jcard-8-panel-v1"
    assert get_jcard_profile(JCard().profile).panel_widths_mm == EXPECTED[8][0]
