import json

import pytest
from imposition.artwork_return import prepare_layout_assets
from imposition.jcard_artwork import resolve_jcard_layout
from imposition.jcard_impose import impose_jcard
from tests.test_artwork_layout_return import producer_fixture
from tests.test_jcard_artwork import configuration


def assets(tmp_path, config, face):
    directory = tmp_path / face
    directory.mkdir()
    _, export, producer = producer_fixture(directory, layout=resolve_jcard_layout(config, face))
    audit = json.loads((producer / "design.json").read_text())
    audit["logical_layers"][0]["group_values"] = {}
    (producer / "design.json").write_text(json.dumps(audit))
    return prepare_layout_assets(
        producer_bundle=producer,
        handoff=export / "layout-handoff.json",
        output_dir=directory / "prepared",
    )


@pytest.mark.parametrize("flip", ["left-right", "top-bottom"])
def test_guide_layers_and_rigid_matrix(tmp_path, flip):
    from dataclasses import replace

    config = replace(
        configuration(tmp_path, "back"), flip=flip, guides=("cut", "fold", "registration")
    )
    bundle = assets(tmp_path, config, "back")
    out = impose_jcard(config, assets_by_face={"back": bundle}, output_dir=tmp_path / "out")
    audit = json.loads((out / "back/design.json").read_text())
    assert [v["id"] for v in audit["logical_layers"]][-3:] == [
        "jcard-cut-guides",
        "jcard-fold-guides",
        "jcard-registration",
    ]
    a, b, c, d, _, _ = audit["face_matrix_mm"]
    assert a * d - b * c == 1
    assert audit["logical_layers"][0]["group_values"] == {}


@pytest.mark.parametrize("kind", ["stale", "swapped", "extra", "hash"])
def test_invalid_bundle_selection(tmp_path, kind):
    config = configuration(tmp_path, "both")
    bundles = {face: assets(tmp_path, config, face) for face in config.selected_faces}
    if kind == "stale":
        recipe = json.loads(config.front_artwork.template.read_text())
        recipe["seed"] += 1
        config.front_artwork.template.write_text(json.dumps(recipe))
    elif kind == "swapped":
        bundles = {"front": bundles["back"], "back": bundles["front"]}
    elif kind == "extra":
        bundles["other"] = bundles["front"]
    else:
        with (bundles["front"] / "surfaces/front-panel-1.svg").open("ab") as stream:
            stream.write(b" ")
    with pytest.raises(ValueError):
        impose_jcard(config, assets_by_face=bundles, output_dir=tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_single_back_and_both_identical(tmp_path):
    both = configuration(tmp_path, "both")
    bundles = {face: assets(tmp_path, both, face) for face in both.selected_faces}
    pair = impose_jcard(both, assets_by_face=bundles, output_dir=tmp_path / "pair")
    single = impose_jcard(
        configuration(tmp_path, "back"),
        assets_by_face={"back": bundles["back"]},
        output_dir=tmp_path / "single",
    )
    for name in ("design.svg", "design.json", "design.imposition.json"):
        assert (pair / "back" / name).read_bytes() == (single / "back" / name).read_bytes()
    assert not (single / "front").exists()
    assert b'data-plotter-workflow-layout="preserve"' in (single / "back/design.svg").read_bytes()


def test_failure_preserves_previous_pair(tmp_path):
    config = configuration(tmp_path, "both")
    bundles = {face: assets(tmp_path, config, face) for face in config.selected_faces}
    out = impose_jcard(config, assets_by_face=bundles, output_dir=tmp_path / "out")
    previous = (out / "jcard-jobs.json").read_bytes()
    (bundles["back"] / "surfaces/back-panel-1.svg").write_text("broken")
    with pytest.raises(ValueError):
        impose_jcard(config, assets_by_face=bundles, output_dir=out, overwrite=True)
    assert (out / "jcard-jobs.json").read_bytes() == previous


def test_blank_mask_still_requires_valid_sources(tmp_path):
    from dataclasses import replace

    config = configuration(tmp_path)
    config = replace(
        config,
        front_artwork=replace(
            config.front_artwork, blank_panels=tuple(f"front-panel-{i}" for i in range(1, 9))
        ),
    )
    bundle = assets(tmp_path, config, "front")
    out = impose_jcard(config, assets_by_face={"front": bundle}, output_dir=tmp_path / "out")
    assert b"data-viz-path-id" not in (out / "front/design.svg").read_bytes()
    manifest = json.loads((out / "front/design.json").read_text())
    assert len(manifest["panels"]) == 8
    (bundle / "surfaces/front-panel-1.svg").unlink()
    with pytest.raises((ValueError, OSError)):
        impose_jcard(config, assets_by_face={"front": bundle}, output_dir=tmp_path / "invalid")
