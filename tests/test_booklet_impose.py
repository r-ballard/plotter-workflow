from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import booklet_impose as booklet
from logical_layer_contract import (
    InputMode,
    LogicalLayerContractError,
    inspect_svg_contract,
    load_logical_layer_manifest,
)


class PocketmodLayoutTests(unittest.TestCase):
    def test_mapping_matches_golden_fixture(self) -> None:
        fixture_path = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "imposition"
            / "pocketmod8"
            / "expected.json"
        )
        expected = json.loads(fixture_path.read_text(encoding="utf-8"))
        actual = {
            str(page): {
                "row": row,
                "column": column,
                "rotation_degrees": rotation,
            }
            for page, (row, column, rotation) in booklet.POCKETMOD8_CELLS.items()
        }
        self.assertEqual(actual, expected["logical_to_physical"])
        self.assertEqual(
            {tuple(pair) for pair in expected["facing_spreads"]},
            booklet.ALLOWED_SPREADS,
        )

    def test_physical_validation_fixture_has_eight_vector_pages(self) -> None:
        fixture_dir = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "imposition"
            / "pocketmod8"
            / "validation_pages"
        )
        pages = sorted(fixture_dir.glob("*.svg"))
        self.assertEqual([page.name for page in pages], [f"{n:02d}.svg" for n in range(1, 9)])
        for page in pages:
            text = page.read_text(encoding="utf-8")
            self.assertIn("<path", text)
            self.assertNotIn("<text", text)
            self.assertNotIn("<image", text)

    def test_automatic_mode_uses_natural_filename_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for number in (8, 2, 1, 7, 3, 6, 4, 5):
                (root / f"page-{number}.svg").write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
                )
            entries = booklet.discover_automatic_pages(root, fit="contain", margin_mm=4.0)
            self.assertEqual(
                [entry.source.name for entry in entries],
                [f"page-{number}.svg" for number in range(1, 9)],
            )
            self.assertEqual([entry.pages for entry in entries], [(n,) for n in range(1, 9)])

    def test_manifest_spread_covers_pages_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("cover.svg", "spread.svg", "p4.svg", "p5.svg", "p6.svg", "p7.svg", "p8.svg"):
                (root / name).write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
                )
            manifest = root / "booklet.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "layout": "pocketmod8",
                        "pages": [
                            {"page": 1, "source": "cover.svg"},
                            {"spread": [2, 3], "source": "spread.svg"},
                            {"page": 4, "source": "p4.svg"},
                            {"page": 5, "source": "p5.svg"},
                            {"page": 6, "source": "p6.svg"},
                            {"page": 7, "source": "p7.svg"},
                            {"page": 8, "source": "p8.svg"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            entries = booklet.load_manifest(
                root,
                manifest,
                default_fit="contain",
                default_margin_mm=4.0,
                default_gutter_mm=0.0,
            )
            self.assertEqual(entries[1].pages, (2, 3))
            self.assertTrue(entries[1].is_spread)

    def test_manifest_rejects_nonfacing_spread(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.svg"
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
            manifest = root / "booklet.json"
            manifest.write_text(
                json.dumps(
                    {
                        "pages": [
                            {"spread": [1, 2], "source": "source.svg"},
                            {"page": 3, "source": "source.svg"},
                            {"page": 4, "source": "source.svg"},
                            {"page": 5, "source": "source.svg"},
                            {"page": 6, "source": "source.svg"},
                            {"page": 7, "source": "source.svg"},
                            {"page": 8, "source": "source.svg"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(booklet.ImpositionError, "not a facing"):
                booklet.load_manifest(
                    root,
                    manifest,
                    default_fit="contain",
                    default_margin_mm=4.0,
                    default_gutter_mm=0.0,
                )


    def test_cell_transform_rotates_top_row_geometry(self) -> None:
        class FakeLines:
            def __init__(self) -> None:
                self.points = [0 + 0j, 10 + 20j]

            def scale(self, sx: float, sy: float | None = None) -> None:
                sy = sx if sy is None else sy
                self.points = [complex(p.real * sx, p.imag * sy) for p in self.points]

            def translate(self, dx: float, dy: float) -> None:
                self.points = [complex(p.real + dx, p.imag + dy) for p in self.points]

        upright = FakeLines()
        booklet._place_in_cell(upright, 1, 100.0, 200.0)
        self.assertEqual(upright.points, [300 + 200j, 310 + 220j])

        upside_down = FakeLines()
        booklet._place_in_cell(upside_down, 5, 100.0, 200.0)
        self.assertEqual(upside_down.points, [100 + 200j, 90 + 180j])

    def test_pen_contract_rejects_stray_top_level_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "bad.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg">'
                '<g id="pen-1" data-pen="1" data-generations="0" fill="none" stroke="#000">'
                '<g data-generation="0"><path d="M0,0 L1,1"/></g></g>'
                '<path d="M2,2 L3,3"/></svg>',
                encoding="utf-8",
            )
            entry = booklet.PageEntry((1,), source, "contain", 4.0, 0.0)
            with self.assertRaisesRegex(booklet.ImpositionError, "top-level drawable"):
                booklet.determine_source_mode([entry])

    def test_guide_svg_uses_one_logical_pen_and_two_generation_kinds(self) -> None:
        # Replace contract inspection so this unit test does not require the
        # repository module to parse generated content twice.
        original = booklet.inspect_pen_layer_contract
        booklet.inspect_pen_layer_contract = lambda path: object()
        try:
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "guides.svg"
                booklet.write_guide_svg(path, sheet_name="letter")
                text = path.read_text(encoding="utf-8")
                self.assertIn('id="pen-1"', text)
                self.assertIn('data-generations="1,2"', text)
                self.assertIn('data-guide-kind="fold"', text)
                self.assertIn('data-guide-kind="cut"', text)
                self.assertIn('data-plotter-workflow-layout="preserve"', text)
                self.assertIn('data-plotter-workflow-page-size="letter"', text)
                self.assertIn('data-plotter-workflow-orientation="landscape"', text)
        finally:
            booklet.inspect_pen_layer_contract = original


NEUTRAL_FIXTURES = Path(__file__).parent / "fixtures/imposition/logical_layers"
SVG = "{http://www.w3.org/2000/svg}"


def write_neutral_bundle(tmp_path):
    surfaces = tmp_path / "surfaces"
    surfaces.mkdir(parents=True)
    catalog = [
        {"id": "orbit", "ordinal": 1, "label": "Orbits"},
        {"id": "unused", "ordinal": 2, "label": "Unused"},
        {"id": "body-1", "ordinal": 3, "label": "Body One"},
        {"id": "body-2", "ordinal": 4, "label": "Body Two"},
    ]
    records = []
    for number, inventory in ((1, ["orbit", "body-1"]), (2, ["orbit", "body-2"])):
        source = surfaces / f"page-{number:02d}.svg"
        source.write_bytes((NEUTRAL_FIXTURES / source.name).read_bytes())
        records.append({
            "path": f"surfaces/{source.name}",
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "logical_layer_ids": inventory,
        })
    payload = {
        "logical_layer_contract": "viz-logical-layers/v1",
        "logical_layers": catalog,
        "surfaces": records,
    }
    manifest_path = tmp_path / "design.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    entries = [
        booklet.PageEntry((n,), surfaces / f"page-{n:02d}.svg", "contain", 0, 0)
        for n in (1, 2)
    ]
    return entries, manifest_path, payload


def render_neutral(entries, output):
    return booklet.render_booklet(
        entries, output, sheet_name="letter", quantization_mm=0.1,
        write_guides=False, overwrite=False,
    )


def test_neutral_imposition_coalesces_heterogeneous_catalog_subsets(tmp_path):
    entries, manifest_path, _ = write_neutral_bundle(tmp_path)
    output, audit, _ = render_neutral(entries, tmp_path / "sheet.svg")
    root = ET.parse(output).getroot()
    groups = root.findall(f"{SVG}g")
    assert root.get("data-viz-layer-contract") == "viz-logical-layers/v1"
    assert [g.get("data-viz-layer-id") for g in groups] == ["orbit", "body-1", "body-2"]
    assert [g.get("data-viz-layer-ordinal") for g in groups] == ["1", "3", "4"]
    assert [g.get("data-viz-layer-label") for g in groups] == ["Orbits", "Body One", "Body Two"]
    paths = [p for p in groups[0].iter(f"{SVG}path") if p.get("data-viz-path-id")]
    assert [p.get("data-viz-path-id") for p in paths] == ["p1-orbit", "p2-orbit"]
    assert [p.get("data-viz-domain-id") for p in paths] == ["page-01", "page-02"]
    assert paths[0].get("data-viz-attr-system_index") == "0"
    page_groups = list(groups[0])
    assert [g.get("data-imposed-page") for g in page_groups] == ["1", "2"]
    assert [g.get("data-source") for g in page_groups] == ["page-01.svg", "page-02.svg"]
    assert not any((e.get("id") or "").startswith("pen-") or "data-pen" in e.attrib for e in root.iter())
    manifest = load_logical_layer_manifest(manifest_path)
    contract = inspect_svg_contract(output, catalog=manifest.layers)
    assert contract.mode is InputMode.NEUTRAL
    assert [layer.id for layer in contract.layers] == ["orbit", "body-1", "body-2"]
    report = json.loads(audit.read_text())
    assert report["source_mode"] == "neutral"
    assert report["logical_layer_contract"] == "viz-logical-layers/v1"
    assert report["source_manifest_path"] == manifest_path.resolve().as_posix()
    assert report["source_manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert report["logical_layers"] == json.loads(manifest_path.read_text())["logical_layers"]
    assert report["logical_layer_ids"] == ["orbit", "body-1", "body-2"]


def test_neutral_imposition_keeps_references_local_and_unique(tmp_path):
    entries, _, _ = write_neutral_bundle(tmp_path)
    output, _, _ = render_neutral(entries, tmp_path / "sheet.svg")
    root = ET.parse(output).getroot()
    ids = [element.get("id") for element in root.iter() if element.get("id")]
    assert len(ids) == len(set(ids))
    clips = [e for e in root.iter() if e.get("clip-path")]
    assert len(clips) >= 2
    for element in clips:
        reference = re.fullmatch(r"url\(#(.+)\)", element.get("clip-path")).group(1)
        assert reference in ids
    source_clips = [c for c in root.iter(f"{SVG}clipPath") if next(iter(c)).tag == f"{SVG}path"]
    assert len(source_clips) >= 2


@pytest.mark.parametrize("other_mode", ["generic", "legacy"])
def test_neutral_imposition_rejects_mixed_input_before_publication(tmp_path, other_mode):
    entries, _, _ = write_neutral_bundle(tmp_path)
    other = tmp_path / "other.svg"
    content = '<path d="M0 0 L1 1"/>'
    if other_mode == "legacy":
        content = ('<g id="pen-1" data-pen="1" data-generations="1" stroke="#000" fill="none">'
                   '<g data-generation="1">' + content + '</g></g>')
    other.write_text('<svg xmlns="http://www.w3.org/2000/svg">' + content + '</svg>')
    entries[1] = booklet.PageEntry((2,), other, "contain", 0, 0)
    output = tmp_path / "sheet.svg"
    with pytest.raises(booklet.ImpositionError, match="mix"):
        render_neutral(entries, output)
    assert not output.exists()


@pytest.mark.parametrize("corruption", ["missing", "hash", "inventory", "label", "version"])
def test_neutral_imposition_rejects_invalid_bundle_before_publication(tmp_path, corruption):
    entries, manifest, payload = write_neutral_bundle(tmp_path)
    if corruption == "missing":
        manifest.unlink()
    else:
        if corruption == "hash":
            payload["surfaces"][0]["sha256"] = "0" * 64
        elif corruption == "inventory":
            payload["surfaces"][0]["logical_layer_ids"] = ["orbit"]
        elif corruption == "label":
            payload["logical_layers"][0]["label"] = "Wrong"
        else:
            payload["logical_layer_contract"] = "viz-logical-layers/v99"
        manifest.write_text(json.dumps(payload))
    output = tmp_path / "sheet.svg"
    with pytest.raises(booklet.ImpositionError):
        render_neutral(entries, output)
    assert not output.exists()


def test_neutral_imposition_rejects_incompatible_bundle_catalogs(tmp_path):
    entries, _, _ = write_neutral_bundle(tmp_path / "first")
    other, manifest, payload = write_neutral_bundle(tmp_path / "second")
    payload["logical_layers"][1]["label"] = "Different unused catalog entry"
    manifest.write_text(json.dumps(payload))
    with pytest.raises(booklet.ImpositionError, match="catalog"):
        render_neutral([entries[0], other[1]], tmp_path / "sheet.svg")
    assert not (tmp_path / "sheet.svg").exists()


def test_neutral_imposition_rejects_conflicting_catalog_semantics(tmp_path):
    entries, _, _ = write_neutral_bundle(tmp_path / "first")
    other, manifest, payload = write_neutral_bundle(tmp_path / "second")
    payload["logical_layers"][0]["group_values"] = {"system_index": 99}
    manifest.write_text(json.dumps(payload))
    with pytest.raises(booklet.ImpositionError, match="catalog"):
        render_neutral([entries[0], other[1]], tmp_path / "sheet.svg")


def test_neutral_imposition_requires_one_authoritative_bundle(tmp_path):
    entries, _, _ = write_neutral_bundle(tmp_path / "first")
    other, _, _ = write_neutral_bundle(tmp_path / "second")
    with pytest.raises(booklet.ImpositionError, match="one authoritative.*manifest"):
        render_neutral([entries[0], other[1]], tmp_path / "sheet.svg")
    assert not (tmp_path / "sheet.svg").exists()


def test_neutral_placement_matches_hand_calculated_page_coordinates(tmp_path):
    entries, _, _ = write_neutral_bundle(tmp_path)
    output, _, _ = render_neutral(entries, tmp_path / "sheet.svg")
    lines, width, height = booklet._read_generic(output, quantization=1)
    assert (width, height) == pytest.approx((1056, 816))
    endpoints = [
        tuple((round(p.real, 1), round(p.imag, 1)) for p in (line[0], line[-1]))
        for line in lines
    ]
    assert endpoints == [
        ((818.4, 532.8), (1029.6, 532.8)),
        ((1029.6, 124.8), (818.4, 124.8)),
        ((871.2, 585.6), (897.6, 612.0)),
        ((897.6, 204.0), (871.2, 177.6)),
    ]


def test_neutral_spread_crops_empty_halves_without_losing_layer_order(tmp_path):
    entries, _, _ = write_neutral_bundle(tmp_path)
    spread = booklet.PageEntry((2, 3), entries[0].source, "contain", 0, 6)
    output, audit, _ = render_neutral([spread], tmp_path / "sheet.svg")
    groups = ET.parse(output).getroot().findall(f"{SVG}g")
    assert [g.get("data-viz-layer-id") for g in groups] == ["orbit", "body-1"]
    assert [g.get("data-imposed-page") for g in groups[0]] == ["2", "3"]
    assert [g.get("data-imposed-page") for g in groups[1]] == ["2"]
    pages = json.loads(audit.read_text())["pages"]
    assert [p["source_part"] for p in pages] == ["left", "right"]
    assert [p["gutter_mm"] for p in pages] == [6, 6]


@pytest.mark.parametrize("change", ["dangling", "duplicate", "stylesheet", "use", "switch"])
def test_neutral_imposition_rejects_unsafe_reference_constructs(tmp_path, change):
    entries, manifest, payload = write_neutral_bundle(tmp_path)
    source = entries[0].source
    text = source.read_text()
    if change == "dangling":
        text = text.replace("url(#surface-clip)", "url(#missing)")
    elif change == "duplicate":
        text = text.replace('id="segment"', 'id="surface-clip"')
    elif change == "stylesheet":
        text = text.replace("<defs>", "<style>#segment {stroke:red}</style><defs>")
    elif change == "use":
        text = text.replace('<path id="segment"', '<use href="#segment"/><path id="segment"')
    else:
        text = text.replace('<path id="segment"', '<switch><path id="segment"')
        text = text.replace('d="M10 20 L90 20"/>', 'd="M10 20 L90 20"/></switch>')
    source.write_text(text)
    payload["surfaces"][0]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(payload))
    with pytest.raises(booklet.ImpositionError):
        render_neutral(entries, tmp_path / "sheet.svg")
    assert not (tmp_path / "sheet.svg").exists()


def test_catalog_aware_inspection_does_not_relax_standalone_or_metadata_validation(tmp_path):
    entries, manifest_path, _ = write_neutral_bundle(tmp_path)
    manifest = load_logical_layer_manifest(manifest_path)
    with pytest.raises(LogicalLayerContractError, match="contiguous"):
        inspect_svg_contract(entries[0].source)
    assert len(inspect_svg_contract(entries[0].source, catalog=manifest.layers).layers) == 2
    invalid = tmp_path / "invalid.svg"
    invalid.write_text(entries[0].source.read_text().replace('label="Orbits"', 'label="Other"'))
    with pytest.raises(LogicalLayerContractError, match="catalog"):
        inspect_svg_contract(invalid, catalog=manifest.layers)


def update_neutral_source(entries, manifest, payload, transform):
    source = entries[0].source
    source.write_text(transform(source.read_text()), encoding="utf-8")
    payload["surfaces"][0]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("target,attribute", [
    ("<svg ", "onload"), ("<g id=", "onclick"), ("<defs>", "OnLoad"),
    ('<clipPath id=', "ONPOINTERDOWN"), ('<path id=', "onfocus"),
])
def test_neutral_imposition_rejects_event_handlers_everywhere(tmp_path, target, attribute):
    entries, manifest, payload = write_neutral_bundle(tmp_path)

    def inject(text):
        replacement = target[:-1] + f' {attribute}="alert(1)">' if target.endswith(">") else (
            target.split(" ")[0] + f' {attribute}="alert(1)" ' + target.split(" ", 1)[1]
        )
        return text.replace(target, replacement, 1)

    update_neutral_source(entries, manifest, payload, inject)
    with pytest.raises(booklet.ImpositionError, match="event-handler"):
        render_neutral(entries, tmp_path / "sheet.svg")
    assert not (tmp_path / "sheet.svg").exists()


@pytest.mark.parametrize("container", ["defs", "metadata", "clipPath", "nested-defs-group"])
def test_neutral_imposition_rejects_scripts_inside_nonrendering_containers(tmp_path, container):
    entries, manifest, payload = write_neutral_bundle(tmp_path)
    script = '<script>alert(1)</script>'
    if container == "metadata":
        injection = lambda text: text.replace("<defs>", f"<metadata>{script}</metadata><defs>")
    elif container == "nested-defs-group":
        injection = lambda text: text.replace("<defs>", f"<defs><g>{script}</g>")
    else:
        injection = lambda text: text.replace(f"</{container}>", f"{script}</{container}>")
    update_neutral_source(entries, manifest, payload, injection)
    with pytest.raises(booklet.ImpositionError, match="unsupported.*element"):
        render_neutral(entries, tmp_path / "sheet.svg")
    assert not (tmp_path / "sheet.svg").exists()


@pytest.mark.parametrize("attribute", [
    'src="https://example.invalid/resource"',
    'xml:base="https://example.invalid/base/"',
    'style="stroke:URL(https://example.invalid/paint)"',
    r'style="stroke:u\72l(https://example.invalid/paint)"',
    'style="stroke:u/**/rl(https://example.invalid/paint)"',
])
def test_neutral_imposition_rejects_resource_loading_attributes(tmp_path, attribute):
    entries, manifest, payload = write_neutral_bundle(tmp_path)
    update_neutral_source(entries, manifest, payload,
                          lambda text: text.replace('<g id=', f'<g {attribute} id=', 1))
    with pytest.raises(booklet.ImpositionError, match="external|resource"):
        render_neutral(entries, tmp_path / "sheet.svg")
    assert not (tmp_path / "sheet.svg").exists()


@pytest.mark.parametrize("attribute", ["marker-start", "marker-mid", "marker-end", "color-profile"])
@pytest.mark.parametrize("value", [r"u\72l(https://example.invalid/paint)", "u/**/rl(https://example.invalid/paint)"])
def test_neutral_imposition_rejects_obscured_resources_in_other_attributes(tmp_path, attribute, value):
    entries, manifest, payload = write_neutral_bundle(tmp_path)
    update_neutral_source(entries, manifest, payload,
                          lambda text: text.replace('<g id=', f'<g {attribute}="{value}" id=', 1))
    with pytest.raises(booklet.ImpositionError, match="resource|unsupported"):
        render_neutral(entries, tmp_path / "sheet.svg")
    assert not (tmp_path / "sheet.svg").exists()


@pytest.mark.parametrize("attribute", ["marker-start", "marker-mid", "marker-end"])
def test_neutral_imposition_rejects_marker_presentation_attributes(tmp_path, attribute):
    entries, manifest, payload = write_neutral_bundle(tmp_path)
    update_neutral_source(entries, manifest, payload,
                          lambda text: text.replace('<g id=', f'<g {attribute}="url(#surface-clip)" id=', 1))
    with pytest.raises(booklet.ImpositionError, match="unsupported.*marker"):
        render_neutral(entries, tmp_path / "sheet.svg")
    assert not (tmp_path / "sheet.svg").exists()


def test_neutral_imposition_rejects_marker_properties_in_inline_style(tmp_path):
    entries, manifest, payload = write_neutral_bundle(tmp_path)
    update_neutral_source(entries, manifest, payload,
                          lambda text: text.replace('<g id=', '<g style="marker-start:url(#surface-clip)" id=', 1))
    with pytest.raises(booklet.ImpositionError, match="unsupported.*marker"):
        render_neutral(entries, tmp_path / "sheet.svg")
    assert not (tmp_path / "sheet.svg").exists()


@pytest.mark.parametrize("construct", ["linearGradient", "pattern", "filter", "marker", "mask"])
def test_neutral_imposition_rejects_unsupported_definitions(tmp_path, construct):
    entries, manifest, payload = write_neutral_bundle(tmp_path)
    update_neutral_source(entries, manifest, payload,
                          lambda text: text.replace('<defs>', f'<defs><{construct} id="extra"/>'))
    with pytest.raises(booklet.ImpositionError, match="unsupported.*element"):
        render_neutral(entries, tmp_path / "sheet.svg")
    assert not (tmp_path / "sheet.svg").exists()


@pytest.mark.parametrize("function", ["URL", "Url", "uRL"])
def test_neutral_imposition_rewrites_case_insensitive_local_css_urls(tmp_path, function):
    entries, manifest, payload = write_neutral_bundle(tmp_path)
    update_neutral_source(entries, manifest, payload,
                          lambda text: text.replace('url(#surface-clip)', f'{function}(#surface-clip)'))
    output, _, _ = render_neutral(entries, tmp_path / "sheet.svg")
    root = ET.parse(output).getroot()
    ids = {e.get("id") for e in root.iter() if e.get("id")}
    for element in root.iter():
        clip = element.get("clip-path")
        if clip is not None:
            target = re.fullmatch(r"url\(#(.+)\)", clip, re.IGNORECASE).group(1)
            assert target in ids
            assert target != "surface-clip"


@pytest.mark.parametrize("attribute", ["data-viz-layer-label", "data-viz-domain-id", "data-viz-attr-note"])
@pytest.mark.parametrize("value", ["artist@example.org", r"source\chapter", "notes/*draft*/", "URL(#surface-clip)"])
def test_neutral_imposition_preserves_inert_semantic_metadata(tmp_path, attribute, value):
    entries, manifest, payload = write_neutral_bundle(tmp_path)
    for entry in entries:
        root = ET.parse(entry.source).getroot()
        if attribute == "data-viz-layer-label":
            root.find(f"{SVG}g").set(attribute, value)
        else:
            root.find(f"{SVG}g/{SVG}path").set(attribute, value)
        ET.ElementTree(root).write(entry.source, encoding="utf-8")
    if attribute == "data-viz-layer-label":
        payload["logical_layers"][0]["label"] = value
    for index, entry in enumerate(entries):
        payload["surfaces"][index]["sha256"] = hashlib.sha256(entry.source.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    output, _, _ = render_neutral(entries, tmp_path / "sheet.svg")
    root = ET.parse(output).getroot()
    if attribute == "data-viz-layer-label":
        assert root.find(f"{SVG}g").get(attribute) == value
    else:
        paths = [p for p in root.iter(f"{SVG}path") if p.get("data-viz-path-id") in {"p1-orbit", "p2-orbit"}]
        assert [p.get(attribute) for p in paths] == [value, value]


@pytest.mark.parametrize("legacy", [False, True])
def test_existing_modes_keep_their_output_structure_and_audit_mode(tmp_path, legacy):
    source = tmp_path / "source.svg"
    content = '<path d="M10 20 L90 20"/>'
    if legacy:
        content = ('<g id="pen-2" data-pen="2" data-generations="7" fill="none" stroke="#000">'
                   '<g data-generation="7">' + content + '</g></g>')
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
                      + content + '</svg>')
    entries = [booklet.PageEntry((1,), source, "contain", 0, 0)]
    output, audit, _ = render_neutral(entries, tmp_path / "sheet.svg")
    root = ET.parse(output).getroot()
    assert root.get("data-viz-layer-contract") is None
    group = root.find(f"{SVG}g")
    assert group.get("id") == ("pen-2" if legacy else "content")
    assert json.loads(audit.read_text())["source_mode"] == ("pen-contract" if legacy else "generic")
    if legacy:
        assert group.get("data-generations") == "7"
        assert group.find(f"{SVG}g").get("data-generation") == "7"


@pytest.mark.parametrize("empty_pages", [(1,), (1, 2)])
def test_neutral_empty_surfaces_do_not_create_false_inventory(tmp_path, empty_pages):
    entries, manifest, payload = write_neutral_bundle(tmp_path)
    for n in empty_pages:
        source = entries[n - 1].source
        source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" '
                          'data-viz-layer-contract="viz-logical-layers/v1"/>')
        payload["surfaces"][n - 1]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        payload["surfaces"][n - 1]["logical_layer_ids"] = []
    manifest.write_text(json.dumps(payload))
    output = tmp_path / "sheet.svg"
    if len(empty_pages) == 2:
        with pytest.raises(booklet.ImpositionError, match="no plottable"):
            render_neutral(entries, output)
        assert not output.exists()
    else:
        render_neutral(entries, output)
        root = ET.parse(output).getroot()
        assert [g.get("data-viz-layer-id") for g in root.findall(f"{SVG}g")] == ["orbit", "body-2"]


if __name__ == "__main__":
    unittest.main()
