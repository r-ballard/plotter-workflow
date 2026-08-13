from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "integrate_cootie_orientation.py"


def _load_integrator():
    spec = importlib.util.spec_from_file_location("integrate_cootie_orientation", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _representative_cootie_source() -> str:
    return '''from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from imposition.model import ObjectPlacement, SheetSpec
from imposition.objects.cootie_catcher import COOTIE_CATCHER, CootieCatcherError
from imposition.source import ImpositionSourceError, inspect_svg_source

Point = tuple[float, float]
COOTIE_PANEL_ROTATIONS = {"selector-3": 90}
COOTIE_PANEL_POLYGONS = {"selector-3": ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))}


class ImpositionError(ValueError):
    pass


@dataclass(frozen=True)
class PanelEntry:
    slot: str
    source: Path
    fit: str
    margin_mm: float
    rotation_degrees: int


@dataclass(frozen=True)
class RenderedPanel:
    slot: str
    kind: str
    index: int
    source: str
    fit: str
    margin_mm: float
    rotation_degrees: int
    polygon_normalized: tuple[tuple[float, float], ...]
    polygon_mm: tuple[tuple[float, float], ...]


def _resolve_source(input_dir: Path, raw: object) -> Path:
    return input_dir / str(raw)


def load_manifest(input_dir: Path, raw_panels: list[dict[str, Any]]) -> list[PanelEntry]:
    entries: list[PanelEntry] = []
    for raw in raw_panels:
        slot = raw["slot"]
        fit = "contain"
        margin_mm = 3.0
        rotation_raw = raw.get("rotation_degrees", COOTIE_PANEL_ROTATIONS[slot])
        try:
            rotation = int(rotation_raw)
        except (TypeError, ValueError) as exc:
            raise ImpositionError("rotation_degrees must be an integer multiple of 90.") from exc
        if rotation % 90:
            raise ImpositionError("rotation_degrees must be an integer multiple of 90.")
        rotation %= 360

        entries.append(
            PanelEntry(
                slot=slot,
                source=_resolve_source(input_dir, raw.get("source")),
                fit=fit,
                margin_mm=margin_mm,
                rotation_degrees=rotation,
            )
        )
    return entries


def _rotated_canvas_size(width: float, height: float, rotation_degrees: int) -> tuple[float, float]:
    return (height, width) if rotation_degrees % 180 else (width, height)


def _largest_centered_canvas_scale() -> float:
    return 1.0


def record(entry: PanelEntry, polygon_mm: tuple[tuple[float, float], ...]) -> RenderedPanel:
    return RenderedPanel(
        slot=entry.slot,
        kind="selector",
        index=3,
        source=entry.source.name,
        fit=entry.fit,
        margin_mm=entry.margin_mm,
        rotation_degrees=entry.rotation_degrees,
        polygon_normalized=COOTIE_PANEL_POLYGONS[entry.slot],
        polygon_mm=polygon_mm,
    )
'''


def test_orientation_integrator_adds_policy_and_arbitrary_angle_fit() -> None:
    integrator = _load_integrator()
    updated = integrator.integrate(_representative_cootie_source())

    assert "orientation_policy: str = \"legacy-default\"" in updated
    assert "source_intrinsic_canvas: IntrinsicCanvas | None = None" in updated
    assert "COOTIE_CATCHER.resolve_orientation(" in updated
    assert "rotation_override_degrees=entry.rotation_override_degrees" in updated
    assert "return rotated_rectangle_size(width, height, rotation_degrees)" in updated
    compile(updated, "cootie_impose.py", "exec")


def test_orientation_integrator_is_idempotent() -> None:
    integrator = _load_integrator()
    once = integrator.integrate(_representative_cootie_source())
    twice = integrator.integrate(once)
    assert twice == once
