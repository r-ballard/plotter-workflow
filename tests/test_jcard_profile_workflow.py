import json
from dataclasses import replace

import pytest
from imposition.artwork_io import json_bytes
from imposition.artwork_return import prepare_layout_assets
from imposition.jcard_artwork import resolve_jcard_layout, write_jcard_export
from imposition.jcard_impose import impose_jcard
from tests.test_artwork_layout_export import template
from tests.test_artwork_layout_return import producer_fixture
from tests.test_jcard_profiles import EXPECTED, profile_config

from scripts.dpx3300_convert import _neutral_context


def config_with_recipes(tmp_path, n, **controls):
    for face in ("front", "back"):
        (tmp_path / f"{face}.json").write_bytes(json_bytes(template()))
    return profile_config(tmp_path, n, **controls)


def prepared_face(tmp_path, config, face, *, blank=False):
    tmp_path.mkdir()
    _, export, producer = producer_fixture(
        tmp_path, layout=resolve_jcard_layout(config, face), blank=blank
    )
    return prepare_layout_assets(
        producer_bundle=producer,
        handoff=export / "layout-handoff.json",
        output_dir=tmp_path / "assets",
    )


@pytest.mark.parametrize("n", EXPECTED)
@pytest.mark.parametrize("mode", ["independent", "continuous"])
def test_profile_artwork_geometry_and_restore(tmp_path, n, mode):
    config = config_with_recipes(
        tmp_path,
        n,
        front_artwork={"template": "front.json", "mode": mode},
        back_artwork={"template": "back.json", "mode": mode},
    )
    out = write_jcard_export(config, tmp_path / "export")
    for face in config.selected_faces:
        layout = resolve_jcard_layout(config, face)
        assert len(layout.panels) == n
        assert layout.window[2] == pytest.approx(EXPECTED[n][1] * 96 / 25.4)
        assert layout.window[3] == 384
        assert all(p.binding["profile"] == config.profile for p in layout.panels)
        bundle = prepared_face(tmp_path / face, config, face)
        assert json.loads((bundle / "bindings.json").read_text())["complete"]
        assert (out / face / "sheet-preview.svg").exists()


@pytest.mark.parametrize("n", EXPECTED)
def test_all_profile_faces_are_selection_independent_and_convertible(tmp_path, n):
    config = config_with_recipes(
        tmp_path, n, guides={"cut": True, "fold": True, "registration": True}
    )
    pair_export = write_jcard_export(config, tmp_path / "export-pair")
    bundles = {face: prepared_face(tmp_path / face, config, face) for face in config.selected_faces}
    pair = impose_jcard(config, assets_by_face=bundles, output_dir=tmp_path / "pair")
    for face in config.selected_faces:
        single = replace(
            config, faces=face, **{f"{'back' if face == 'front' else 'front'}_artwork": None}
        )
        single_export = write_jcard_export(single, tmp_path / f"export-{face}")
        imposed = impose_jcard(
            single, assets_by_face={face: bundles[face]}, output_dir=tmp_path / f"single-{face}"
        )
        for name in (
            "artwork-job.json",
            "layout-handoff.json",
            "layout-preview.svg",
            "sheet-preview.svg",
        ):
            assert (pair_export / face / name).read_bytes() == (
                single_export / face / name
            ).read_bytes()
        for name in ("design.svg", "design.json", "design.imposition.json"):
            assert (pair / face / name).read_bytes() == (imposed / face / name).read_bytes()
        contract, digest = _neutral_context(imposed / face / "design.svg")
        assert len(contract.layers) == 5 and len(digest) == 64


def test_foreign_manufacturer_same_geometry_rejected(tmp_path):
    config = config_with_recipes(tmp_path, 8)
    source_config = replace(config, profile="nac-jcard-8-panel-v1")
    bundle = prepared_face(tmp_path / "foreign", source_config, "front")
    single = replace(config, faces="front", back_artwork=None)
    with pytest.raises(ValueError, match="profile|layout"):
        impose_jcard(single, assets_by_face={"front": bundle}, output_dir=tmp_path / "out")


def test_blank_small_profile_and_atomic_second_face_failure(tmp_path):
    config = config_with_recipes(tmp_path, 3)
    bundles = {
        face: prepared_face(tmp_path / face, config, face, blank=True)
        for face in config.selected_faces
    }
    out = impose_jcard(config, assets_by_face=bundles, output_dir=tmp_path / "out")
    previous = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    assert b"data-viz-path-id" not in (out / "front/design.svg").read_bytes()
    assert len(json.loads((out / "front/design.json").read_text())["panels"]) == 3
    (bundles["back"] / "surfaces/back-panel-1.svg").write_text("tampered")
    with pytest.raises(ValueError):
        impose_jcard(config, assets_by_face=bundles, output_dir=out, overwrite=True)
    assert previous == {
        str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()
    }
