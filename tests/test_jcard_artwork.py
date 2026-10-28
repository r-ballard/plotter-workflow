import json

import pytest
from imposition.artwork_return import prepare_layout_assets
from imposition.jcard_artwork import (
    build_jcard_artwork_job,
    resolve_jcard_layout,
    write_jcard_export,
)
from imposition.jcard_config import load_jcard_config
from tests.test_artwork_layout_export import template
from tests.test_artwork_layout_return import producer_fixture


def configuration(tmp_path, faces="front", mode="independent"):
    (tmp_path / "recipe.json").write_text(json.dumps(template()))
    payload = {"schema_version": 1, "sheet": "a3", "faces": faces}
    for face in ("front", "back") if faces == "both" else (faces,):
        payload[f"{face}_artwork"] = {"template": "recipe.json", "mode": mode}
    return load_jcard_config(payload, base_dir=tmp_path)


@pytest.mark.parametrize("face", ["front", "back"])
@pytest.mark.parametrize("mode", ["independent", "continuous"])
def test_native_export_and_restore(tmp_path, face, mode):
    config = configuration(tmp_path, face, mode)
    layout = resolve_jcard_layout(config, face)
    assert len(layout.panels) == 8
    job = build_jcard_artwork_job(layout, template(), mode=mode)
    assert job["passes"][0]["parameters"]["coordinate_frame"] == (
        "domain" if mode == "independent" else "composition"
    )
    _, export, producer = producer_fixture(tmp_path, layout=layout)
    prepared = tmp_path / "prepared"
    prepare_layout_assets(
        producer_bundle=producer, handoff=export / "layout-handoff.json", output_dir=prepared
    )
    bindings = json.loads((prepared / "bindings.json").read_text())
    assert bindings["kind"] == "jcard" and bindings["complete"]


@pytest.mark.parametrize("face", ["front", "back"])
def test_face_bytes_are_selection_independent(tmp_path, face):
    single = write_jcard_export(configuration(tmp_path, face), tmp_path / "single")
    both = write_jcard_export(configuration(tmp_path, "both"), tmp_path / "both")
    for name in (
        "artwork-job.json",
        "layout-handoff.json",
        "layout-preview.svg",
        "sheet-preview.svg",
    ):
        assert (single / face / name).read_bytes() == (both / face / name).read_bytes()


@pytest.mark.parametrize(
    "bad", [{"passes": [None]}, {"coordinate_frame": False}, {"composition_mode": {}}]
)
def test_malformed_recipe_controls_are_rejected(tmp_path, bad):
    layout = resolve_jcard_layout(configuration(tmp_path), "front")
    recipe = template()
    if "passes" in bad:
        recipe.update(bad)
    else:
        recipe["passes"][0]["parameters"].update(bad)
    with pytest.raises(ValueError):
        build_jcard_artwork_job(layout, recipe, mode="independent")


def test_export_contains_sheet_safe_and_registration_preview(tmp_path):
    from dataclasses import replace

    config = replace(configuration(tmp_path), guides=("registration",))
    out = write_jcard_export(config, tmp_path / "out")
    preview = (out / "front/sheet-preview.svg").read_text()
    assert "safe" in preview and "registration" in preview
    assert "front-panel-1" in preview
