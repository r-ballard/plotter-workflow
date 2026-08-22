from __future__ import annotations

import importlib.util
from pathlib import Path

GENERATOR = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "generate_cootie_orientation_fixture.py"
)


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_cootie_orientation_fixture_features",
        GENERATOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_square_fixture_labels_vertices_and_declares_edge_map() -> None:
    generator = _load_generator()
    svg = generator.source_svg("outer-1")

    assert (
        'data-validation-vertex-map="'
        'A=vertex:0;B=vertex:1;C=vertex:2;D=vertex:3"'
    ) in svg
    assert (
        'data-validation-edge-map="'
        'AB=edge:0;BC=edge:1;CD=edge:2;DA=edge:3"'
    ) in svg
    for label in ("A", "B", "C", "D"):
        assert f'data-validation-feature="vertex:{label}"' in svg
    assert "<text" not in svg


def test_triangle_fixture_labels_vertices_and_declares_edge_map() -> None:
    generator = _load_generator()
    svg = generator.source_svg("reveal-1")

    assert (
        'data-validation-vertex-map="A=vertex:0;B=vertex:1;C=vertex:2"'
    ) in svg
    assert (
        'data-validation-edge-map="AB=edge:0;BC=edge:1;CA=edge:2"'
    ) in svg
    for label in ("A", "B", "C"):
        assert f'data-validation-feature="vertex:{label}"' in svg
    assert "<text" not in svg


def test_observation_template_records_feature_based_orientation() -> None:
    generator = _load_generator()
    payload = generator.observation_template()

    assert payload["schema_version"] == 2
    assert payload["feature_maps"]["square"] == generator.SQUARE_FEATURE_MAP
    assert payload["feature_maps"]["triangle"] == generator.TRIANGLE_FEATURE_MAP
    assert len(payload["slots"]) == 20

    outer = next(item for item in payload["slots"] if item["slot"] == "outer-1")
    reveal = next(item for item in payload["slots"] if item["slot"] == "reveal-1")

    assert outer["shape"] == "square"
    assert reveal["shape"] == "triangle"

    for item in (outer, reveal):
        assert item["desired_top_feature"] is None
        assert item["desired_right_feature"] is None
        assert item["observed_top_feature_after_fold"] is None
        assert item["observed_right_feature_after_fold"] is None
        assert item["mirrored_after_fold"] is None
        assert "upright_after_fold" not in item
        assert "required_rotation_correction_degrees" not in item
