"""Inspect neutral, legacy, and generic SVG layer contracts.

Neutral logical layers are deliberately detected from their versioned root
metadata and explicit ``data-viz-layer-*`` attributes.  An SVG's ordinary
element IDs are never interpreted as logical-layer identities.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from svg_pen_contract import PenLayerContract, inspect_pen_layer_contract

NEUTRAL_CONTRACT = "viz-logical-layers/v1"
_PEN_ID_RE = re.compile(r"^pen-(\d+)$")
_NEUTRAL_GROUP_ATTRIBUTES = {
    "data-viz-layer-id",
    "data-viz-layer-ordinal",
    "data-viz-layer-label",
}
_DRAWABLE_TAGS = {
    "path",
    "line",
    "polyline",
    "polygon",
    "rect",
    "circle",
    "ellipse",
    "use",
}
_NON_RENDERING_CONTAINERS = {"defs", "clipPath", "mask", "marker", "pattern"}


class InputMode(Enum):
    """The mutually exclusive SVG input modes understood by the plotter."""

    NEUTRAL = "neutral"
    LEGACY = "legacy"
    GENERIC = "generic"


class LogicalLayerContractError(ValueError):
    """Raised when a neutral SVG contract is incomplete or invalid."""


@dataclass(frozen=True)
class LogicalLayerMetadata:
    """Validated metadata for one neutral logical layer."""

    id: str
    ordinal: int
    label: str


@dataclass(frozen=True)
class LogicalLayerContract:
    """The result of inspecting one SVG's layer metadata."""

    mode: InputMode
    layers: tuple[LogicalLayerMetadata, ...] = ()
    legacy: PenLayerContract | None = None

    @property
    def legacy_contract(self) -> PenLayerContract | None:
        """Compatibility alias for callers that name the nested contract."""

        return self.legacy


def inspect_svg_contract(path: Path) -> LogicalLayerContract:
    """Inspect ``path`` and classify it as neutral, legacy, or generic.

    Neutral metadata is validated strictly for v1.  Legacy validation remains
    owned by :func:`svg_pen_contract.inspect_pen_layer_contract`; its errors
    and return value are propagated unchanged.
    """

    svg_path = Path(path)
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError as exc:
        raise LogicalLayerContractError(
            f"Invalid SVG/XML in {svg_path}: {exc}"
        ) from exc

    if _local_name(root.tag) != "svg":
        raise LogicalLayerContractError(f"Expected an SVG root element in {svg_path}")

    top_groups = [child for child in root if _local_name(child.tag) == "g"]
    neutral_elements = [
        element
        for element in root.iter()
        if any(attribute in element.attrib for attribute in _NEUTRAL_GROUP_ATTRIBUTES)
    ]
    has_pen_groups = any(
        _PEN_ID_RE.fullmatch(group.get("id", "")) for group in top_groups
    )
    root_declaration = root.get("data-viz-layer-contract")
    neutral_groups = [
        group
        for group in top_groups
        if _looks_like_neutral_group(
            group, include_role=root_declaration == NEUTRAL_CONTRACT
        )
    ]
    has_neutral_declaration = root_declaration is not None or bool(neutral_groups)
    has_neutral_declaration = has_neutral_declaration or bool(neutral_elements)

    if root_declaration is not None and root_declaration != NEUTRAL_CONTRACT:
        raise LogicalLayerContractError(
            f"{svg_path}: unsupported neutral contract version "
            f"{root_declaration!r}; expected {NEUTRAL_CONTRACT!r}"
        )

    if has_neutral_declaration and has_pen_groups:
        raise LogicalLayerContractError(
            f"{svg_path}: mixed neutral and legacy pen-group contracts"
        )

    if root_declaration == NEUTRAL_CONTRACT:
        return _inspect_neutral(svg_path, root, neutral_groups, neutral_elements)

    if neutral_groups or neutral_elements:
        raise LogicalLayerContractError(
            f"{svg_path}: partial neutral logical-layer declaration; "
            "data-viz-layer-contract is missing"
        )

    # Keep legacy behavior and errors owned by svg_pen_contract.  In
    # particular, do not duplicate or loosen its generation metadata checks.
    legacy = inspect_pen_layer_contract(svg_path)
    if legacy is not None:
        return LogicalLayerContract(mode=InputMode.LEGACY, legacy=legacy)
    return LogicalLayerContract(mode=InputMode.GENERIC)


def _inspect_neutral(
    path: Path,
    root: ET.Element,
    neutral_groups: list[ET.Element],
    neutral_elements: list[ET.Element],
) -> LogicalLayerContract:
    neutral_group_ids = {id(group) for group in neutral_groups}
    if any(id(element) not in neutral_group_ids for element in neutral_elements):
        raise LogicalLayerContractError(
            f"{path}: partial neutral layer declaration; layer metadata must "
            "be on top-level logical-layer groups"
        )

    metadata: list[LogicalLayerMetadata] = []
    seen_ids: set[str] = set()
    seen_ordinals: set[int] = set()

    for group in neutral_groups:
        layer_id = group.get("data-viz-layer-id")
        ordinal_raw = group.get("data-viz-layer-ordinal")
        label = group.get("data-viz-layer-label")

        if not layer_id or ordinal_raw is None or label is None:
            raise LogicalLayerContractError(
                f"{path}: partial neutral layer declaration; each layer group "
                "requires data-viz-layer-id, data-viz-layer-ordinal, and "
                "data-viz-layer-label"
            )
        if not label.strip():
            raise LogicalLayerContractError(
                f"{path}: neutral layer {layer_id!r} must declare a non-empty label"
            )
        if layer_id in seen_ids:
            raise LogicalLayerContractError(
                f"{path}: duplicate neutral layer ID {layer_id!r}"
            )
        try:
            ordinal = int(ordinal_raw)
        except ValueError as exc:
            raise LogicalLayerContractError(
                f"{path}: neutral layer {layer_id!r} has a non-integer ordinal "
                f"{ordinal_raw!r}"
            ) from exc
        if ordinal in seen_ordinals:
            raise LogicalLayerContractError(
                f"{path}: duplicate ordinal {ordinal} in neutral layers"
            )

        seen_ids.add(layer_id)
        seen_ordinals.add(ordinal)
        metadata.append(
            LogicalLayerMetadata(id=layer_id, ordinal=ordinal, label=label)
        )

    expected_ordinals = set(range(1, len(metadata) + 1))
    if seen_ordinals != expected_ordinals:
        actual = sorted(seen_ordinals)
        raise LogicalLayerContractError(
            f"{path}: neutral layer ordinals must be contiguous starting at 1; "
            f"got {actual}"
        )

    _validate_drawable_ownership(path, root, neutral_groups)
    metadata.sort(key=lambda layer: layer.ordinal)
    return LogicalLayerContract(mode=InputMode.NEUTRAL, layers=tuple(metadata))


def _looks_like_neutral_group(group: ET.Element, *, include_role: bool) -> bool:
    return (
        any(attribute in group.attrib for attribute in _NEUTRAL_GROUP_ATTRIBUTES)
        or (include_role and group.get("data-viz-role") == "logical-layer")
    )


def _validate_drawable_ownership(
    path: Path,
    root: ET.Element,
    neutral_groups: list[ET.Element],
) -> None:
    owned_groups = {id(group) for group in neutral_groups}
    for child in root:
        if _local_name(child.tag) in _NON_RENDERING_CONTAINERS:
            continue
        if id(child) in owned_groups:
            continue
        if _contains_drawable(child):
            raise LogicalLayerContractError(
                f"{path}: drawable geometry must be owned by a neutral layer"
            )


def _contains_drawable(element: ET.Element) -> bool:
    if _local_name(element.tag) in _DRAWABLE_TAGS:
        return True
    for child in element:
        local_name = _local_name(child.tag)
        if local_name in _NON_RENDERING_CONTAINERS:
            continue
        if local_name in _DRAWABLE_TAGS or _contains_drawable(child):
            return True
    return False


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
