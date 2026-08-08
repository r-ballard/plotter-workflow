"""Validate the multi-pen SVG contract consumed by ``plotter-workflow``.

The contract is structural: a top-level SVG group named ``pen-N`` maps to
vpype layer ``N`` and therefore to DPX-3300 physical pen ``SPN``. Stroke color
is retained for preview/documentation but is not used to select a physical pen.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET

PEN_ID_RE = re.compile(r"^pen-(\d+)$")
MAX_DPX_PENS = 8
_DRAWABLE_TAGS = {
    "path",
    "line",
    "polyline",
    "polygon",
    "rect",
    "circle",
    "ellipse",
}


class PenLayerContractError(ValueError):
    """Raised when an SVG looks pen-layered but violates the contract."""


@dataclass(frozen=True)
class PenLayerContract:
    """Validated physical pen IDs present in an SVG."""

    pens: tuple[int, ...]


def inspect_pen_layer_contract(path: Path) -> PenLayerContract | None:
    """Return the validated pen contract, or ``None`` for a generic SVG.

    Generic SVG files remain supported. Contract validation activates only when
    at least one top-level group has an ``id`` matching ``pen-N``.
    """

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise PenLayerContractError(f"Invalid SVG/XML in {path}: {exc}") from exc

    if _local_name(root.tag) != "svg":
        raise PenLayerContractError(f"Expected an SVG root element in {path}")

    top_groups = [child for child in root if _local_name(child.tag) == "g"]
    matched: list[tuple[ET.Element, int]] = []
    for group in top_groups:
        match = PEN_ID_RE.fullmatch(group.get("id", ""))
        if match:
            matched.append((group, int(match.group(1))))

    if not matched:
        return None

    pens: list[int] = []
    seen: set[int] = set()

    for group, pen in matched:
        if not 1 <= pen <= MAX_DPX_PENS:
            raise PenLayerContractError(
                f"{path}: pen-{pen} is outside the DPX-3300 pen range 1-{MAX_DPX_PENS}"
            )
        if pen in seen:
            raise PenLayerContractError(f"{path}: duplicate pen layer pen-{pen}")
        seen.add(pen)

        if group.get("data-pen") != str(pen):
            raise PenLayerContractError(
                f"{path}: pen-{pen} must declare data-pen=\"{pen}\""
            )
        if not group.get("stroke"):
            raise PenLayerContractError(
                f"{path}: pen-{pen} must retain a stroke color for preview metadata"
            )
        if group.get("fill") != "none":
            raise PenLayerContractError(f"{path}: pen-{pen} must use fill=\"none\"")

        declared_generations = _parse_generation_list(
            group.get("data-generations", ""), path=path, pen=pen
        )
        nested_generations: list[int] = []
        for child in group:
            if _local_name(child.tag) != "g":
                if _local_name(child.tag) in _DRAWABLE_TAGS:
                    raise PenLayerContractError(
                        f"{path}: pen-{pen} drawable geometry must be inside a generation group"
                    )
                continue

            raw_generation = child.get("data-generation")
            if raw_generation is None:
                if _contains_drawable(child):
                    raise PenLayerContractError(
                        f"{path}: pen-{pen} contains a drawable group without data-generation"
                    )
                continue
            try:
                nested_generations.append(int(raw_generation))
            except ValueError as exc:
                raise PenLayerContractError(
                    f"{path}: pen-{pen} has non-integer data-generation={raw_generation!r}"
                ) from exc

        if tuple(nested_generations) != declared_generations:
            raise PenLayerContractError(
                f"{path}: pen-{pen} data-generations does not match nested generation groups"
            )

        pens.append(pen)

    matched_groups = {id(group) for group, _ in matched}
    for group in top_groups:
        if id(group) not in matched_groups and _contains_drawable(group):
            raise PenLayerContractError(
                f"{path}: drawable top-level groups must use id=\"pen-N\""
            )

    return PenLayerContract(pens=tuple(sorted(pens)))


def _parse_generation_list(raw: str, *, path: Path, pen: int) -> tuple[int, ...]:
    if not raw:
        raise PenLayerContractError(
            f"{path}: pen-{pen} must declare data-generations metadata"
        )
    try:
        return tuple(int(value) for value in raw.split(","))
    except ValueError as exc:
        raise PenLayerContractError(
            f"{path}: pen-{pen} has invalid data-generations={raw!r}"
        ) from exc


def _contains_drawable(element: ET.Element) -> bool:
    return any(_local_name(child.tag) in _DRAWABLE_TAGS for child in element.iter())


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
