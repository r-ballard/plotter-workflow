import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import dpx3300_convert as converter
from dpx3300_convert import ConversionError, validate_hpgl
from pen_plan import LogicalAssignment, LogicalPenPlanSpec, PassSpec, PenPlanError


def neutral_job(tmp_path, count=2, geometry=None, definitions="", imposed=True):
    layers = [
        {"id": f"layer-{n}", "ordinal": n, "label": f"Layer {n}"}
        for n in range(1, count + 1)
    ]
    groups = "".join(
        f'<g data-viz-layer-id="{item["id"]}" '
        f'data-viz-layer-ordinal="{item["ordinal"]}" '
        f'data-viz-layer-label="{item["label"]}">'
        + (geometry or f'<path d="M 10 {10 + n} L 20 {10 + n}"/>')
        + "</g>"
        for n, item in enumerate(layers)
    )
    source = tmp_path / "drawing.svg"
    physical_layout = (
        'data-plotter-workflow-layout="preserve" '
        'data-plotter-workflow-page-size="a3" '
        'data-plotter-workflow-orientation="portrait" '
        if imposed
        else ""
    )
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="100" height="100" viewBox="0 0 100 100" '
        'data-viz-layer-contract="viz-logical-layers/v1" '
        + physical_layout
        + ">"
        + definitions
        + groups
        + "</svg>",
        encoding="utf-8",
    )
    manifest = tmp_path / "design.json"
    manifest.write_text(
        json.dumps(
            {
                "logical_layer_contract": "viz-logical-layers/v1",
                "logical_layers": layers,
                "surfaces": [
                    {
                        "path": "drawing.svg",
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "logical_layer_ids": [item["id"] for item in layers],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    audit = source.with_suffix(".imposition.json")
    audit.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_mode": "neutral",
                "logical_layer_contract": "viz-logical-layers/v1",
                "sheet": {"name": "a3", "orientation": "portrait"},
                "source_manifest_path": str(manifest),
                "source_manifest_sha256": hashlib.sha256(
                    manifest.read_bytes()
                ).hexdigest(),
                "logical_layers": layers,
                "logical_layer_ids": [item["id"] for item in layers],
            }
        ),
        encoding="utf-8",
    )
    return source


def two_pass_spec():
    return LogicalPenPlanSpec(
        2,
        (
            PassSpec(
                "pass-1",
                tuple(LogicalAssignment((f"layer-{n}",), 9 - n) for n in range(1, 9)),
            ),
            PassSpec("pass-2", (LogicalAssignment(("layer-9",), 3),)),
        ),
        (),
        (),
    )


def mock_vpype(monkeypatch, fail_on=None, hpgl=None):
    inputs = []

    def run(command, dry_run=False):
        if dry_run:
            return
        root = ET.parse(command[command.index("read") + 1]).getroot()
        inputs.append(root)
        if len(inputs) == fail_on:
            raise ConversionError("vpype failed")
        groups = root.findall("{http://www.w3.org/2000/svg}g")
        Path(command[-1]).write_text(
            hpgl
            or "IN;"
            + "".join(f"SP{n};PU0,0;PD10,10;PU;" for n in range(1, len(groups) + 1))
            + "SP0;",
            encoding="ascii",
        )

    monkeypatch.setattr(converter, "run_command", run)
    return inputs


def test_neutral_two_pass_artifacts_and_remapping(tmp_path, monkeypatch):
    source = neutral_job(tmp_path, 9)
    original = source.read_bytes()
    inputs = mock_vpype(monkeypatch)
    outputs = converter.convert_neutral_svg(source, two_pass_spec(), tmp_path / "out")
    assert [p.name for p in outputs] == ["drawing.pass-1.hpgl", "drawing.pass-2.hpgl"]
    assert "SP8;" in outputs[0].read_text() and "SP3;" in outputs[1].read_text()
    assert len(inputs[0].findall("{http://www.w3.org/2000/svg}g")) == 8
    assert [
        g.get("data-viz-layer-id")
        for g in inputs[1].iter()
        if g.get("data-viz-layer-id")
    ] == ["layer-9"]
    assert source.read_bytes() == original
    assert not list((tmp_path / "out").glob("*.svg"))
    payload = json.loads(outputs[1].with_suffix(".resolved.penplan.json").read_text())
    assert payload["schema_version"] == 2
    assert payload["kind"] == "resolved-dpx3300-logical-pass"
    assert (payload["pass_id"], payload["pass_number"], payload["pass_count"]) == (
        "pass-2",
        2,
        2,
    )
    assert payload["assignments"] == [{"layer_ids": ["layer-9"], "physical_slot": 3}]
    assert payload["physical_slots"] == [3]
    assert payload["source_svg"] == str(source.resolve())
    assert (
        payload["source_manifest_hash"]
        == hashlib.sha256((tmp_path / "design.json").read_bytes()).hexdigest()
    )


def test_neutral_merge_omission_and_repetition(tmp_path, monkeypatch):
    source = neutral_job(tmp_path, 4)
    spec = LogicalPenPlanSpec(
        2,
        (
            PassSpec("first", (LogicalAssignment(("layer-3", "layer-1"), 7),)),
            PassSpec("second", (LogicalAssignment(("layer-1", "layer-4"), 2),)),
        ),
        ("layer-2",),
        ("layer-1",),
    )
    inputs = mock_vpype(monkeypatch)
    outputs = converter.convert_neutral_svg(source, spec, tmp_path / "out")
    assert len(list(inputs[0])) == 1
    assert [
        g.get("data-viz-layer-id")
        for g in inputs[0].iter()
        if g.get("data-viz-layer-id")
    ] == ["layer-1", "layer-3"]
    payload = json.loads(outputs[0].with_suffix(".resolved.penplan.json").read_text())
    assert payload["omitted_layers"] == ["layer-2"]
    assert payload["repeated_layers"] == ["layer-1"]


@pytest.mark.parametrize(
    "shape,expected",
    [
        ('<rect x="0" y="0" width="10" height="10"/>', (20, 30)),
        ('<polygon points="0,0 10,0 0,10"/>', (20, 25)),
        ('<path d="M0 0 L10 0 L0 10 Z"/>', (20, 25)),
    ],
)
def test_neutral_clipping_truncates_transformed_geometry(
    tmp_path, monkeypatch, shape, expected
):
    source = neutral_job(
        tmp_path,
        1,
        geometry='<g transform="translate(20,10)"><g clip-path="url(#domain)"><path d="M-5 5 L15 5"/></g></g>',
        definitions='<defs><clipPath id="domain">' + shape + "</clipPath></defs>",
    )
    inputs = mock_vpype(monkeypatch)
    converter.convert_neutral_svg(source, None, tmp_path / "out")
    import io

    import vpype

    lines, _, _ = vpype.read_svg(
        io.StringIO(ET.tostring(inputs[0], encoding="unicode")), quantization=0.1
    )
    assert lines.bounds() == pytest.approx((expected[0], 15, expected[1], 15))
    assert all("clip-path" not in node.attrib for node in inputs[0].iter())


@pytest.mark.parametrize(
    "definitions,clip",
    [
        ("", "url(#missing)"),
        ("", "url(https://example.com/clip)"),
        ('<defs><clipPath id="c"><circle r="5"/></clipPath></defs>', "url(#c)"),
        ('<defs><clipPath id="c"><path d="M0 0 Q10 5 0 10 Z"/></clipPath></defs>', "url(#c)"),
        (
            '<defs><clipPath id="c" clipPathUnits="objectBoundingBox"><rect width="1" height="1"/></clipPath></defs>',
            "url(#c)",
        ),
    ],
)
def test_neutral_unsupported_clips_fail_before_execution(
    tmp_path, monkeypatch, definitions, clip
):
    source = neutral_job(
        tmp_path, 1, f'<path clip-path="{clip}" d="M0 0 L20 20"/>', definitions
    )
    inputs = mock_vpype(monkeypatch)
    with pytest.raises((ConversionError, ValueError), match="clip|reference|URL"):
        converter.convert_neutral_svg(source, None, tmp_path / "out")
    assert inputs == []


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "hash",
        "catalog",
        "inventory",
        "schema_bool",
        "ordinal_bool",
        "source_label",
        "sheet",
    ],
)
def test_neutral_invalid_audit_fails_before_execution(tmp_path, monkeypatch, damage):
    source = neutral_job(tmp_path)
    audit_path = source.with_suffix(".imposition.json")
    raw = json.loads(audit_path.read_text())
    if damage == "missing":
        audit_path.unlink()
    else:
        if damage == "hash":
            raw["source_manifest_sha256"] = "0" * 64
        elif damage == "catalog":
            raw["logical_layers"][0]["label"] = "Wrong"
        elif damage == "inventory":
            raw["logical_layer_ids"] = ["layer-1"]
        elif damage == "schema_bool":
            raw["schema_version"] = True
        elif damage == "ordinal_bool":
            raw["logical_layers"][0]["ordinal"] = True
        elif damage == "sheet":
            raw["sheet"]["orientation"] = "landscape"
        else:
            source.write_text(
                source.read_text().replace(
                    'data-viz-layer-label="Layer 1"', 'data-viz-layer-label="Wrong"'
                )
            )
        audit_path.write_text(json.dumps(raw))
    inputs = mock_vpype(monkeypatch)
    with pytest.raises(
        (ConversionError, ValueError), match="audit|manifest|catalog|inventory|layout"
    ):
        converter.convert_neutral_svg(source, None, tmp_path / "out")
    assert inputs == []


def test_neutral_default_limit_and_dry_run(tmp_path, monkeypatch):
    source = neutral_job(tmp_path, 9)
    inputs = mock_vpype(monkeypatch)
    with pytest.raises(PenPlanError, match="explicit merge or multiple passes"):
        converter.convert_neutral_svg(source, None, tmp_path / "out", dry_run=True)
    outputs = converter.convert_neutral_svg(
        source, two_pass_spec(), tmp_path / "out", dry_run=True
    )
    assert len(outputs) == 2 and all(not p.exists() for p in outputs)
    assert not (tmp_path / "out").exists()
    assert inputs == []


@pytest.mark.parametrize("ids", [("same", "SAME"), ("a/b", "a-b"), ("same", "same")])
def test_neutral_pass_filenames_reject_collisions_and_unsafe_ids(
    tmp_path, monkeypatch, ids
):
    source = neutral_job(tmp_path)
    spec = LogicalPenPlanSpec(
        2,
        tuple(
            PassSpec(name, (LogicalAssignment((f"layer-{n}",), 1),))
            for n, name in enumerate(ids, 1)
        ),
        (),
        (),
    )
    inputs = mock_vpype(monkeypatch)
    with pytest.raises(
        (ConversionError, PenPlanError), match="pass|filename|collision"
    ):
        converter.convert_neutral_svg(source, spec, tmp_path / "out")
    assert inputs == []


def test_neutral_later_pass_failure_preserves_existing_artifacts(tmp_path, monkeypatch):
    source = neutral_job(tmp_path, 9)
    out = tmp_path / "out"
    out.mkdir()
    existing = out / "drawing.pass-1.hpgl"
    existing.write_bytes(b"existing")
    inputs = mock_vpype(monkeypatch, fail_on=2)
    with pytest.raises(FileExistsError):
        converter.convert_neutral_svg(source, two_pass_spec(), out)
    assert inputs == []
    with pytest.raises(ConversionError, match="vpype failed"):
        converter.convert_neutral_svg(source, two_pass_spec(), out, overwrite=True)
    assert existing.read_bytes() == b"existing"
    assert list(out.iterdir()) == [existing]


def convert_job(source, out, **options):
    return converter.convert_files(
        [source],
        out,
        config_path=converter.DEFAULT_VPYPE_CONFIG,
        device="dpx3300",
        page_size="a3",
        landscape=False,
        margin="10mm",
        velocity=None,
        absolute=False,
        overwrite=False,
        send=options.pop("send", False),
        dry_run=options.pop("dry_run", False),
        **options,
    )


def test_neutral_converter_integration_and_discovered_plan(tmp_path, monkeypatch):
    source = neutral_job(tmp_path)
    source.with_suffix(".penplan.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "passes": [
                    {
                        "id": "ink",
                        "assignments": [
                            {"layer_ids": ["layer-2", "layer-1"], "physical_slot": 7}
                        ],
                    }
                ],
                "omitted_layers": [],
                "repeated_layers": [],
            }
        )
    )
    mock_vpype(monkeypatch)
    outputs = convert_job(source, tmp_path / "out")
    assert [p.name for p in outputs] == ["drawing.ink.hpgl"]
    assert "SP7;" in outputs[0].read_text()


def test_neutral_requires_imposed_preserve_layout_before_execution(
    tmp_path, monkeypatch
):
    source = neutral_job(tmp_path, 1, imposed=False)
    inputs = mock_vpype(monkeypatch)
    out = tmp_path / "out"
    with pytest.raises(ConversionError, match="preserve-layout"):
        converter.convert_neutral_svg(source, None, out)
    assert inputs == []
    assert not out.exists()


@pytest.mark.parametrize(
    "options", [{"send": True}, {"pen_policy": "compact"}, {"pen_map": "1:2"}]
)
def test_neutral_rejects_legacy_flags_and_send_before_execution(
    tmp_path, monkeypatch, options
):
    source = neutral_job(tmp_path)
    inputs = mock_vpype(monkeypatch)
    with pytest.raises((ConversionError, PenPlanError), match="neutral|Neutral"):
        convert_job(source, tmp_path / "out", **options)
    assert inputs == []


def test_neutral_cli_dry_run_is_non_mutating_and_deterministic(
    tmp_path, monkeypatch, caplog
):
    source = neutral_job(tmp_path)
    caplog.set_level("INFO")
    mock_vpype(monkeypatch)
    out = tmp_path / "out"
    first = convert_job(source, out, dry_run=True)
    first_logs = caplog.text
    caplog.clear()
    assert convert_job(source, out, dry_run=True) == first
    assert caplog.text == first_logs
    assert not out.exists()


@pytest.mark.parametrize(
    "hpgl", ["IN;SP9;PU0,0;PD10,10;SP1;SP2;SP0;", "IN;SP2;PU0,0;PD10,10;SP1;SP0;"]
)
def test_neutral_rejects_extra_or_reordered_hpgl_pens(tmp_path, monkeypatch, hpgl):
    source = neutral_job(tmp_path)
    mock_vpype(monkeypatch, hpgl=hpgl)
    with pytest.raises(ConversionError, match="pen selection|pen order"):
        converter.convert_neutral_svg(source, None, tmp_path / "out")
    assert list((tmp_path / "out").iterdir()) == []


def test_neutral_real_imposition_and_vpype_pipeline(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from vpype_cli import cli

    from booklet_impose import PageEntry, render_booklet

    surface_dir = tmp_path / "surfaces"
    surface_dir.mkdir()
    source = neutral_job(
        surface_dir,
        2,
        '<g clip-path="url(#domain)"><path d="M-5 25 L80 25"/></g>',
        '<defs><clipPath id="domain" clipPathUnits="userSpaceOnUse">'
        '<path d="M0 0 L50 0 L0 50 Z"/></clipPath></defs>',
        imposed=False,
    )
    payload = json.loads((surface_dir / "design.json").read_text())
    payload["surfaces"][0]["path"] = "surfaces/drawing.svg"
    (tmp_path / "design.json").write_text(json.dumps(payload))
    imposed, _, _ = render_booklet(
        [PageEntry((1,), source, "contain", 0, 0)],
        tmp_path / "sheet.svg",
        sheet_name="a3",
        quantization_mm=0.1,
        write_guides=False,
        overwrite=False,
    )
    commands = []

    def real_vpype(command, dry_run=False):
        commands.append(command)
        result = CliRunner().invoke(cli, command[1:])
        assert result.exit_code == 0, result.output

    monkeypatch.setattr(converter, "run_command", real_vpype)
    outputs = converter.convert_neutral_svg(
        imposed, None, tmp_path / "out", landscape=True
    )
    assert outputs[0].exists()
    assert "layout" not in commands[0]
    assert "--center" not in commands[0]
    assert "SP1;" in outputs[0].read_text() and "SP2;" in outputs[0].read_text()
    assert (
        json.loads(outputs[0].with_suffix(".resolved.penplan.json").read_text())[
            "source_manifest_hash"
        ]
        == hashlib.sha256((tmp_path / "design.json").read_bytes()).hexdigest()
    )


def test_neutral_nested_svg_viewbox_and_intersecting_clips(tmp_path, monkeypatch):
    source = neutral_job(
        tmp_path,
        1,
        '<g transform="translate(10,20)" clip-path="url(#crop)">'
        '<svg width="40" height="40" viewBox="0 0 20 20">'
        '<g transform="translate(2,0)" clip-path="url(#domain)">'
        '<path d="M-10 5 L20 5"/></g></svg></g>',
        '<defs><clipPath id="crop"><rect width="20" height="40"/></clipPath>'
        '<clipPath id="domain" transform="translate(1,0)"><path d="M0 0 L10 0 L0 10 Z"/></clipPath></defs>',
    )
    inputs = mock_vpype(monkeypatch)
    converter.convert_neutral_svg(source, None, tmp_path / "out")
    import io

    import vpype

    lines, _, _ = vpype.read_svg(
        io.StringIO(ET.tostring(inputs[0], encoding="unicode")), quantization=0.1
    )
    assert lines.bounds() == pytest.approx((16, 30, 26, 30))


@pytest.mark.parametrize("value", ["stroke-dasharray:1,2", "clip-path:url(#missing)"])
def test_neutral_unsupported_inline_rendering_fails_before_execution(
    tmp_path, monkeypatch, value
):
    source = neutral_job(tmp_path, 1, f'<path style="{value}" d="M0 0 L10 10"/>')
    inputs = mock_vpype(monkeypatch)
    with pytest.raises(ConversionError, match="style|clip"):
        converter.convert_neutral_svg(source, None, tmp_path / "out")
    assert inputs == []


def test_neutral_snapshot_keeps_source_svg_hash_consistent(tmp_path, monkeypatch):
    source = neutral_job(tmp_path)
    run = converter.run_command
    calls = []

    def change_source(command, dry_run=False):
        source.write_text(source.read_text().replace("L 20", "L 30"))
        calls.append(command)
        Path(command[-1]).write_text("IN;SP1;PU0,0;PD10,10;SP2;PU0,0;PD10,10;SP0;")

    monkeypatch.setattr(converter, "run_command", change_source)
    with pytest.raises(ConversionError, match="changed"):
        converter.convert_neutral_svg(source, None, tmp_path / "out")
    assert len(calls) == 1
    assert list((tmp_path / "out").iterdir()) == []
    monkeypatch.setattr(converter, "run_command", run)


def test_neutral_nested_svg_viewport_clips_crossing_geometry(tmp_path, monkeypatch):
    source = neutral_job(
        tmp_path,
        1,
        '<g transform="translate(10,20)"><svg x="2" y="3" width="20" height="40" '
        'viewBox="0 0 10 20"><path d="M-10 5 L20 5"/></svg></g>',
    )
    inputs = mock_vpype(monkeypatch)
    converter.convert_neutral_svg(source, None, tmp_path / "out")
    import io

    import vpype

    lines, _, _ = vpype.read_svg(
        io.StringIO(ET.tostring(inputs[0], encoding="unicode")), quantization=0.1
    )
    assert lines.bounds() == pytest.approx((12, 33, 32, 33))


def test_neutral_nested_svg_without_viewbox_translates_geometry_and_crop(
    tmp_path, monkeypatch
):
    source = neutral_job(
        tmp_path,
        1,
        '<g transform="translate(10,20)"><svg x="20" y="10" width="40" height="40">'
        '<path d="M-10 5 L20 5"/></svg></g>',
    )
    inputs = mock_vpype(monkeypatch)
    converter.convert_neutral_svg(source, None, tmp_path / "out")
    import io

    import vpype

    lines, _, _ = vpype.read_svg(
        io.StringIO(ET.tostring(inputs[0], encoding="unicode")), quantization=0.1
    )
    assert lines.bounds() == pytest.approx((30, 35, 50, 35))


@pytest.mark.parametrize("x", ["20%", "20% "])
def test_neutral_nested_svg_percent_offset_uses_parent_viewport(
    tmp_path, monkeypatch, x
):
    source = neutral_job(
        tmp_path,
        1,
        f'<svg x="{x}" y="10" width="40" height="40">'
        '<path d="M-10 5 L20 5"/></svg>',
    )
    inputs = mock_vpype(monkeypatch)
    converter.convert_neutral_svg(source, None, tmp_path / "out")
    import io

    import vpype

    lines, _, _ = vpype.read_svg(
        io.StringIO(ET.tostring(inputs[0], encoding="unicode")), quantization=0.1
    )
    assert lines.bounds() == pytest.approx((20, 15, 40, 15))


@pytest.mark.parametrize("count", [1, 8])
def test_neutral_preserve_default_and_output_metadata(tmp_path, monkeypatch, count):
    source = neutral_job(tmp_path, count)
    inputs = mock_vpype(monkeypatch)
    outputs = converter.convert_neutral_svg(source, None, tmp_path / "out")
    assert outputs[0].name == "drawing.preserve.hpgl"
    assert inputs[0].get("width") == "100"
    assert inputs[0].get("height") == "100"
    assert inputs[0].get("viewBox") == "0 0 100 100"
    payload = json.loads(outputs[0].with_suffix(".resolved.penplan.json").read_text())
    assert payload["physical_slots"] == list(range(1, count + 1))


def test_neutral_rejects_legacy_input_plan(tmp_path, monkeypatch):
    source = neutral_job(tmp_path)
    source.with_suffix(".penplan.json").write_text('{"schema_version":1,"policy":"preserve"}')
    inputs = mock_vpype(monkeypatch)
    with pytest.raises(PenPlanError, match="schema_version=2"):
        convert_job(source, tmp_path / "out")
    assert inputs == []


def test_neutral_existing_sidecar_is_not_overwritten(tmp_path, monkeypatch):
    source = neutral_job(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    sidecar = out / "drawing.preserve.resolved.penplan.json"
    sidecar.write_bytes(b"previous")
    inputs = mock_vpype(monkeypatch)
    with pytest.raises(FileExistsError):
        converter.convert_neutral_svg(source, None, out)
    assert inputs == []
    assert sidecar.read_bytes() == b"previous"


def test_validate_hpgl_accepts_expected_pen_selections(tmp_path: Path):
    path = tmp_path / "drawing.hpgl"
    path.write_text(
        "IN;DF;SP1;PU0,0;PD10,10;PU;SP3;PU20,20;PD30,30;PU;SP0;IN;",
        encoding="ascii",
    )
    validate_hpgl(path, expected_pens=(1, 3))


def test_validate_hpgl_rejects_missing_expected_pen(tmp_path: Path):
    path = tmp_path / "drawing.hpgl"
    path.write_text(
        "IN;DF;SP1;PU0,0;PD10,10;PU;SP0;IN;",
        encoding="ascii",
    )
    with pytest.raises(ConversionError, match="SP3"):
        validate_hpgl(path, expected_pens=(1, 3))
