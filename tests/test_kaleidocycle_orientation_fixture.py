import json
import xml.etree.ElementTree as ET

import pytest

from scripts.dpx3300_convert import _materialize_neutral_layers, _neutral_context
from scripts.generate_kaleidocycle_orientation_fixture import generate_fixture


def test_diagnostic_nets_use_real_imposition_and_plotter_safe_labels(tmp_path):
    output = generate_fixture(tmp_path / "diagnostics")
    for mode in ("panel-orientation", "state-continuity"):
        sheet = output / mode / "sheet" / "design.svg"
        root = ET.parse(sheet).getroot()
        assert not list(root.iter("{http://www.w3.org/2000/svg}text"))
        assert len([g for g in root.iter() if g.get("data-imposed-slot")]) == 32
        contract, _ = _neutral_context(sheet)
        assert [layer.id for layer in contract.layers] == ["diagnostic"]
        materialized = _materialize_neutral_layers(sheet)
        assert len(materialized["diagnostic"]) > 100
        audit = json.loads(sheet.with_suffix(".imposition.json").read_text())
        assert audit["validation_status"] == "provisional"
        construction = ET.parse(sheet.parent / "construction.svg").getroot()
        assert construction.get("data-plotter-workflow-layout") == "preserve"
        assert {g.get("data-guide-kind") for g in construction} == {"cut", "fold"}
        original_guides = ET.parse(sheet.parent / "guides.svg").getroot()
        assert len(construction) == len(
            [g for g in original_guides if g.get("data-guide-kind") in ("cut", "fold")]
        )
    for state in "ABCD":
        reference = ET.parse(
            output / "state-continuity" / f"expected-{state}.svg"
        ).getroot()
        assert not list(reference.iter("{http://www.w3.org/2000/svg}text"))
        assert len([g for g in reference.iter() if g.get("data-diagnostic-panel")]) == 8
    observations = json.loads(
        (output / "physical_validation.template.json").read_text()
    )
    assert len(observations["panels"]) == 32
    assert all(p["observed_state"] is None for p in observations["panels"])
    before = (output / "panel-orientation/sheet/design.svg").read_bytes()
    with pytest.raises(ValueError):
        generate_fixture(output)
    generate_fixture(output, overwrite=True)
    assert (output / "panel-orientation/sheet/design.svg").read_bytes() == before
