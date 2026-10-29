import pytest
from imposition.objects.cassette_jcard import JCard


@pytest.mark.parametrize("face", ["front", "back"])
def test_exact_native_panels(face):
    card = JCard(face=face)
    assert card.panel_widths_mm == (26.9875, 12.7, 65.0875, 63.5, 61.9125, 60.325, 58.7375, 57.15)
    assert card.trim_size_mm == (406.4, 101.6)
    numbers = range(1, 9) if face == "front" else range(8, 0, -1)
    assert [s.slot_id for s in card.slots] == [f"{face}-panel-{i}" for i in numbers]
    previous = 0
    for slot in card.slots:
        assert slot.polygon[0][0] == pytest.approx(previous)
        previous = slot.polygon[1][0]
        assert slot.polygon[2][1] == 1
    assert previous == pytest.approx(1)
    assert len(card.native_guides()) == 8


@pytest.mark.parametrize("kwargs", [{"face": "other"}, {"profile": "four-panel"}])
def test_reject_foreign_geometry(kwargs):
    with pytest.raises(ValueError):
        JCard(**kwargs)
