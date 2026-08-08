import json
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "hardware_validation" / "hilbert"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_golden_pen_plan_matches_commissioning_invariants() -> None:
    plan = _load("golden.penplan.json")
    expected = _load("expected.json")

    assert plan["schema_version"] == 1
    assert plan["policy"] == expected["assignment_policy"] == "compact"

    slots = plan["slots"]
    slot_numbers = [slot["slot"] for slot in slots]
    assert slot_numbers == expected["expected_physical_pen_order"]
    assert len(slot_numbers) == expected["expected_active_pen_count"]
    assert len(set(slot_numbers)) == len(slot_numbers)

    for slot in slots:
        assert slot.get("tool") or slot.get("label")


def test_commissioning_fixture_records_terminal_deselect() -> None:
    expected = _load("expected.json")
    assert expected["hardware"] == "Roland DPX-3300"
    assert expected["result"] == "pass"
    assert expected["expected_terminal_pen"] == 0
