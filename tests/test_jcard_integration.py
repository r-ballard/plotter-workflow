from tests.test_jcard_artwork import configuration
from tests.test_jcard_impose import assets

from scripts.export_jcard_layout import main as export_main
from scripts.jcard_impose import main as impose_main


def test_cli_roundtrip(tmp_path):
    import json

    config = configuration(tmp_path, "back")
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sheet": "a3",
                "faces": "back",
                "back_artwork": {"template": "recipe.json"},
            }
        )
    )
    bundle = assets(tmp_path, config, "back")
    assert export_main(["--config", str(path), "--output-dir", str(tmp_path / "exported")]) == 0
    assert (
        impose_main(
            [
                "--config",
                str(path),
                "--back-assets",
                str(bundle),
                "--output-dir",
                str(tmp_path / "imposed"),
            ]
        )
        == 0
    )
    assert (tmp_path / "imposed/back/design.svg").is_file()


def test_imposed_face_is_accepted_by_converter(tmp_path):
    from imposition.jcard_impose import impose_jcard

    from scripts.dpx3300_convert import _neutral_context, build_vpype_command

    config = configuration(tmp_path)
    bundle = assets(tmp_path, config, "front")
    out = impose_jcard(config, assets_by_face={"front": bundle}, output_dir=tmp_path / "out")
    source = out / "front/design.svg"
    contract, manifest_hash = _neutral_context(source)
    assert len(contract.layers) == 2 and len(manifest_hash) == 64
    command = build_vpype_command(
        source,
        tmp_path / "design.hpgl",
        config_path=tmp_path / "vpype.toml",
        device="dpx3300",
        page_size="a3",
        device_page_size="a3",
        landscape=True,
        margin="0mm",
        velocity=None,
        absolute=True,
    )
    assert "layout" not in command and "--center" not in command
