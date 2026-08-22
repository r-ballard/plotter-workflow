from __future__ import annotations

import json
from pathlib import Path

from imposition.objects.cootie_catcher import EXPECTED_SLOTS

SPEC = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "imposition"
    / "cootie_catcher"
    / "orientation_validation"
    / "desired_orientation.json"
)


def _payload() -> dict[str, object]:
    return json.loads(SPEC.read_text(encoding="utf-8"))


def test_desired_orientation_spec_covers_all_twenty_slots() -> None:
    payload = _payload()
    slots = payload["slots"]

    assert payload["schema_version"] == 1
    assert payload["layout"] == "cootie_catcher"
    assert payload["status"] == "design-target"
    assert [item["slot"] for item in slots] == list(EXPECTED_SLOTS)


def test_desired_orientation_features_exist_for_each_shape() -> None:
    payload = _payload()
    feature_maps = payload["feature_maps"]

    for item in payload["slots"]:
        shape = item["shape"]
        valid_features = set(feature_maps[shape]["vertices"]) | set(
            feature_maps[shape]["edges"]
        )

        assert item["desired_top_feature"] in valid_features
        assert item["desired_right_feature"] in valid_features
        assert item["desired_top_feature"] != item["desired_right_feature"]


def test_desired_orientation_rules_have_four_stable_patterns() -> None:
    payload = _payload()
    by_slot = {item["slot"]: item for item in payload["slots"]}

    for index in range(1, 5):
        item = by_slot[f"outer-{index}"]
        assert (
            item["desired_top_feature"],
            item["desired_right_feature"],
        ) == ("C", "D")

    for index in range(1, 9):
        item = by_slot[f"selector-{index}"]
        expected = ("CA", "AB") if index % 2 else ("AB", "BC")
        assert (
            item["desired_top_feature"],
            item["desired_right_feature"],
        ) == expected

    for index in range(1, 9):
        item = by_slot[f"reveal-{index}"]
        expected = ("B", "BC") if index % 2 else ("C", "A")
        assert (
            item["desired_top_feature"],
            item["desired_right_feature"],
        ) == expected
