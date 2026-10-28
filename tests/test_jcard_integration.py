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
