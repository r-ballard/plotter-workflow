from imposition.model import OrientationTarget, Slot


def test_slot_keeps_semantic_orientation_separate_from_geometry() -> None:
    slot = Slot(
        slot_id="selector-1",
        family="selector",
        polygon=((0.0, 0.0), (0.5, 0.0), (0.25, 0.25)),
        target_orientation=OrientationTarget(up_vector=(0.0, -1.0)),
    )

    assert slot.slot_id == "selector-1"
    assert slot.family == "selector"
    assert slot.default_fit == "contain"
    assert slot.target_orientation.up_vector == (0.0, -1.0)
