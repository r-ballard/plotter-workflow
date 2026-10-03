#!/usr/bin/env python3
"""Activate semantic source orientation in the legacy cootie-catcher CLI.

This migration keeps the existing command-line interface and rendering path in
place while changing how each panel's rotation is resolved:

* an explicit manifest ``rotation_degrees`` remains an absolute override;
* an SVG with intrinsic-canvas metadata maps its source ``up_vector`` to the
  destination slot's target ``up_vector``; and
* a generic SVG without intrinsic metadata retains the existing legacy rotation.

The script is anchor-based, idempotent, and compiles the modified module before
writing it back to disk. Apply the preceding imposition-object slices first.
"""

from __future__ import annotations

import re
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "cootie_impose.py"


def _replace_once(text: str, old: str, new: str, *, description: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(
            f"Cannot integrate {description}: expected anchor was not found."
        )
    return text.replace(old, new, 1)


def _replace_function(
    text: str,
    *,
    function_name: str,
    next_function_name: str,
    replacement: str,
    marker: str,
) -> str:
    if marker in text:
        return text
    pattern = re.compile(
        rf"^def {re.escape(function_name)}\(.*?(?=^def {re.escape(next_function_name)}\()",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        raise SystemExit(
            f"Cannot integrate {function_name}: expected function boundary was not found."
        )
    return text[: match.start()] + replacement.rstrip() + "\n\n\n" + text[match.end() :]


def integrate(text: str) -> str:
    """Return a semantically oriented version of ``cootie_impose.py`` text."""

    # The previous object migration imports these two model types on one line.
    text = _replace_once(
        text,
        "from imposition.model import ObjectPlacement, SheetSpec\n",
        "from imposition.geometry import rotated_rectangle_size\n"
        "from imposition.model import IntrinsicCanvas, ObjectPlacement, SheetSpec\n",
        description="orientation imports",
    )

    panel_entry_old = '''@dataclass(frozen=True)\nclass PanelEntry:\n    slot: str\n    source: Path\n    fit: str\n    margin_mm: float\n    rotation_degrees: int\n'''
    panel_entry_new = '''@dataclass(frozen=True)\nclass PanelEntry:\n    slot: str\n    source: Path\n    fit: str\n    margin_mm: float\n    rotation_degrees: float\n    orientation_policy: str = "legacy-default"\n    rotation_override_degrees: int | None = None\n    source_intrinsic_canvas: IntrinsicCanvas | None = None\n    target_up_vector: Point | None = None\n'''
    text = _replace_once(
        text,
        panel_entry_old,
        panel_entry_new,
        description="PanelEntry orientation fields",
    )

    rendered_old = '''@dataclass(frozen=True)\nclass RenderedPanel:\n    slot: str\n    kind: str\n    index: int\n    source: str\n    fit: str\n    margin_mm: float\n    rotation_degrees: int\n    polygon_normalized: tuple[tuple[float, float], ...]\n    polygon_mm: tuple[tuple[float, float], ...]\n'''
    rendered_new = '''@dataclass(frozen=True)\nclass RenderedPanel:\n    slot: str\n    kind: str\n    index: int\n    source: str\n    fit: str\n    margin_mm: float\n    rotation_degrees: float\n    polygon_normalized: tuple[tuple[float, float], ...]\n    polygon_mm: tuple[tuple[float, float], ...]\n    orientation_policy: str = "legacy-default"\n    rotation_override_degrees: int | None = None\n    source_intrinsic_canvas: IntrinsicCanvas | None = None\n    target_up_vector: Point | None = None\n'''
    text = _replace_once(
        text,
        rendered_old,
        rendered_new,
        description="RenderedPanel orientation audit fields",
    )

    legacy_manifest = '''        rotation_raw = raw.get("rotation_degrees", COOTIE_PANEL_ROTATIONS[slot])\n        try:\n            rotation = int(rotation_raw)\n        except (TypeError, ValueError) as exc:\n            raise ImpositionError("rotation_degrees must be an integer multiple of 90.") from exc\n        if rotation % 90:\n            raise ImpositionError("rotation_degrees must be an integer multiple of 90.")\n        rotation %= 360\n\n        entries.append(\n            PanelEntry(\n                slot=slot,\n                source=_resolve_source(input_dir, raw.get("source")),\n                fit=fit,\n                margin_mm=margin_mm,\n                rotation_degrees=rotation,\n            )\n        )\n'''
    semantic_manifest = '''        source = _resolve_source(input_dir, raw.get("source"))\n        try:\n            source_canvas = inspect_svg_source(source)\n        except ImpositionSourceError as exc:\n            raise ImpositionError(str(exc)) from exc\n\n        rotation_override: int | None = None\n        if "rotation_degrees" in raw:\n            rotation_raw = raw["rotation_degrees"]\n            try:\n                rotation_override = int(rotation_raw)\n            except (TypeError, ValueError) as exc:\n                raise ImpositionError(\n                    "rotation_degrees must be an integer multiple of 90."\n                ) from exc\n            if rotation_override % 90:\n                raise ImpositionError(\n                    "rotation_degrees must be an integer multiple of 90."\n                )\n            rotation_override %= 360\n\n        orientation = COOTIE_CATCHER.resolve_orientation(\n            slot,\n            source_canvas=source_canvas,\n            override_degrees=rotation_override,\n        )\n        # Keep legacy/explicit quarter-turns as integers in the sidecar so\n        # existing generic fixtures retain their serialized numeric form.\n        resolved_rotation = (\n            rotation_override\n            if rotation_override is not None\n            else orientation.resolved_degrees\n        )\n\n        entries.append(\n            PanelEntry(\n                slot=slot,\n                source=source,\n                fit=fit,\n                margin_mm=margin_mm,\n                rotation_degrees=resolved_rotation,\n                orientation_policy=orientation.policy,\n                rotation_override_degrees=rotation_override,\n                source_intrinsic_canvas=source_canvas,\n                target_up_vector=orientation.target_up_vector,\n            )\n        )\n'''
    text = _replace_once(
        text,
        legacy_manifest,
        semantic_manifest,
        description="manifest orientation resolution",
    )

    text = _replace_function(
        text,
        function_name="_rotated_canvas_size",
        next_function_name="_largest_centered_canvas_scale",
        marker="return rotated_rectangle_size(width, height, rotation_degrees)",
        replacement='''def _rotated_canvas_size(\n    width: float,\n    height: float,\n    rotation_degrees: float,\n) -> tuple[float, float]:\n    """Return arbitrary-angle source bounds after center rotation."""\n    try:\n        return rotated_rectangle_size(width, height, rotation_degrees)\n    except ValueError as exc:\n        raise ImpositionError(str(exc)) from exc''',
    )

    audit_marker = "rotation_override_degrees=entry.rotation_override_degrees"
    if audit_marker not in text:
        audit_pattern = re.compile(
            r"^(?P<indent>\s*)polygon_normalized=COOTIE_PANEL_POLYGONS\[entry\.slot\],\n"
            r"(?P=indent)polygon_mm=polygon_mm,\n",
            re.MULTILINE,
        )
        match = audit_pattern.search(text)
        if match is None:
            raise SystemExit(
                "Cannot integrate rendered-panel orientation audit: expected anchor "
                "was not found."
            )
        indent = match.group("indent")
        replacement = (
            f"{indent}polygon_normalized=COOTIE_PANEL_POLYGONS[entry.slot],\n"
            f"{indent}polygon_mm=polygon_mm,\n"
            f"{indent}orientation_policy=entry.orientation_policy,\n"
            f"{indent}rotation_override_degrees=entry.rotation_override_degrees,\n"
            f"{indent}source_intrinsic_canvas=entry.source_intrinsic_canvas,\n"
            f"{indent}target_up_vector=entry.target_up_vector,\n"
        )
        text = text[: match.start()] + replacement + text[match.end() :]

    return text


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    integrated = integrate(text)
    compile(integrated, str(TARGET), "exec")
    TARGET.write_text(integrated, encoding="utf-8")
    print(f"Activated semantic cootie-catcher orientation in {TARGET.name}.")


if __name__ == "__main__":
    main()
