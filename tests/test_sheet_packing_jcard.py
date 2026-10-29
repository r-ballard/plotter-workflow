import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import FrozenInstanceError

import pytest
from imposition.jcard_native import NativeFaceRequest, prepare_native_face
from tests.test_jcard_artwork import configuration
from tests.test_jcard_impose import assets


@pytest.mark.parametrize("face", ["front", "back"])
def test_native_preparation_has_no_sheet_dependency(tmp_path, face):
    config = configuration(tmp_path, face)
    bundle = assets(tmp_path, config, face)
    request = NativeFaceRequest(
        config.profile,
        face,
        bundle,
        config.front_artwork.template if face == "front" else config.back_artwork.template,
        "independent",
        (),
    )
    prepared = prepare_native_face(request)
    assert (prepared.width_mm, prepared.height_mm) == (406.4, 101.6)
    assert len(prepared.panel_audit) == 8
    assert prepared.fragments
    assert all(isinstance(f.svg_bytes, bytes) and f.vertices > 0 for f in prepared.fragments)
    with pytest.raises(FrozenInstanceError):
        prepared.face = "other"
    with pytest.raises(TypeError):
        prepared.catalog[0]["label"] = "changed"


def test_blank_assets_still_validate_viewport_without_layer_groups(tmp_path):
    config = configuration(tmp_path)
    bundle = assets(tmp_path, config, "front")
    manifest_file = bundle / "design.json"
    manifest = json.loads(manifest_file.read_text())
    for record in manifest["surfaces"]:
        source = bundle / record["path"]
        tree = ET.parse(source)
        root = tree.getroot()
        for child in list(root):
            if child.get("data-viz-layer-id") is not None:
                root.remove(child)
        if record["domain_id"] == "front-panel-1":
            root.set("width", "999")
        tree.write(source, encoding="utf-8", xml_declaration=True)
        record["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        record["logical_layer_ids"] = []
    manifest_file.write_text(json.dumps(manifest))
    request = NativeFaceRequest(
        config.profile,
        "front",
        bundle,
        config.front_artwork.template,
        "independent",
        tuple(f"front-panel-{i}" for i in range(1, 9)),
    )
    with pytest.raises(ValueError, match="viewport"):
        prepare_native_face(request)


def test_real_registration_extents_and_stable_instance_ids(tmp_path):
    from imposition.sheet_packing.budget import PackingBudget
    from imposition.sheet_packing.config import load_packing_config
    from imposition.sheet_packing.jcard import instances, prepare_objects

    config = configuration(tmp_path)
    bundle = assets(tmp_path, config, "front")
    data = dict(
        schema_version=1,
        sheet_mm=[420, 297],
        objects=[
            dict(
                id="album",
                type="jcard",
                profile=config.profile,
                quantity=2,
                rotations=[90, 0],
                guides=dict(registration=True),
                front=dict(assets=str(bundle), template=str(config.front_artwork.template)),
            )
        ],
    )
    prepared = prepare_objects(load_packing_config(data, base_dir=tmp_path), PackingBudget())
    box = prepared[0].footprint.occupied_bounds
    assert (box.x, box.y, box.width, box.height) == (-3, -3, 412.4, 107.6)
    assert [i.instance_id for i in instances(prepared)] == ["album-0001", "album-0002"]
    assert len(prepared[0].physical_guides) == 6
