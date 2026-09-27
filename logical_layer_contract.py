"""Inspect neutral, legacy, and generic SVG layer contracts.

Neutral logical layers are deliberately detected from their versioned root
metadata and explicit ``data-viz-layer-*`` attributes.  An SVG's ordinary
element IDs are never interpreted as logical-layer identities.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from svg_pen_contract import (
    PenLayerContract,
    PenLayerContractError,
    inspect_pen_layer_contract,
)

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
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


@dataclass(frozen=True)
class LogicalLayerSurface:
    """One validated per-surface record from a neutral bundle manifest."""

    path: str
    sha256: str
    logical_layer_ids: tuple[str, ...]
    raw: dict[str, Any]


@dataclass(frozen=True)
class LogicalLayerManifest:
    """A validated neutral bundle manifest and its authoritative catalog."""

    path: Path
    layers: tuple[LogicalLayerMetadata, ...]
    surfaces: tuple[LogicalLayerSurface, ...]
    raw: dict[str, Any]


def inspect_svg_contract(
    path: Path, *, catalog: tuple[LogicalLayerMetadata, ...] | None = None
) -> LogicalLayerContract:
    """Inspect ``path`` and classify it as neutral, legacy, or generic.

    Neutral metadata is validated strictly for v1.  Legacy validation remains
    owned by :func:`svg_pen_contract.inspect_pen_layer_contract`; its errors
    and return value are propagated unchanged. An authoritative ``catalog``
    permits sparse surface/sheet subsets while validating every retained ID,
    ordinal, and label. Without one, standalone ordinals remain contiguous.
    """

    contract = _inspect_svg_contract(
        path, allow_sparse_neutral_ordinals=catalog is not None
    )
    if catalog is not None:
        if contract.mode is not InputMode.NEUTRAL:
            raise LogicalLayerContractError(f"{path}: catalog requires neutral input")
        _load_manifest_layers(Path(path), [
            {"id": layer.id, "ordinal": layer.ordinal, "label": layer.label}
            for layer in catalog
        ])
        expected = {layer.id: layer for layer in catalog}
        for layer in contract.layers:
            if expected.get(layer.id) != layer:
                raise LogicalLayerContractError(
                    f"{path}: neutral layer {layer.id!r} differs from authoritative catalog"
                )
    return contract


def _inspect_svg_contract(
    path: Path, *, allow_sparse_neutral_ordinals: bool
) -> LogicalLayerContract:

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
            f"{svg_path}: unsupported data-viz-layer-contract version "
            f"{root_declaration!r}; expected {NEUTRAL_CONTRACT!r}"
        )

    if has_neutral_declaration and has_pen_groups:
        raise LogicalLayerContractError(
            f"{svg_path}: mixed neutral and legacy pen-group contracts"
        )

    if root_declaration == NEUTRAL_CONTRACT:
        return _inspect_neutral(
            svg_path,
            root,
            neutral_groups,
            neutral_elements,
            allow_sparse_ordinals=allow_sparse_neutral_ordinals,
        )

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


def load_logical_layer_manifest(path: Path) -> LogicalLayerManifest:
    """Load and strictly validate a ``viz-logical-layers/v1`` manifest."""

    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LogicalLayerContractError(
            f"{manifest_path}: unable to read design.json manifest: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise LogicalLayerContractError(
            f"{manifest_path}: manifest root must be a JSON object"
        )

    version = payload.get("logical_layer_contract")
    if version != NEUTRAL_CONTRACT:
        raise LogicalLayerContractError(
            f"{manifest_path}: logical_layer_contract is {version!r}; "
            f"expected {NEUTRAL_CONTRACT!r}"
        )

    layers = _load_manifest_layers(manifest_path, payload.get("logical_layers"))
    surfaces = _load_manifest_surfaces(manifest_path, payload.get("surfaces"))
    return LogicalLayerManifest(
        path=manifest_path,
        layers=layers,
        surfaces=surfaces,
        raw=payload,
    )


def validate_surface_against_manifest(
    svg_path: Path,
    manifest: LogicalLayerManifest,
    expected_hash: str | None = None,
) -> LogicalLayerContract:
    """Validate one neutral SVG against its manifest catalog and inventory."""

    surface_path = Path(svg_path)
    relative_path = _manifest_relative_path(surface_path, manifest)
    matches = [surface for surface in manifest.surfaces if surface.path == relative_path]
    if not matches:
        raise LogicalLayerContractError(
            f"{surface_path}: surfaces record for manifest-relative path "
            f"{relative_path!r} is missing from {manifest.path}"
        )
    if len(matches) != 1:
        raise LogicalLayerContractError(
            f"{surface_path}: surfaces records for manifest-relative path "
            f"{relative_path!r} are ambiguous in {manifest.path}"
        )
    surface = matches[0]

    try:
        actual_hash = hashlib.sha256(surface_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise LogicalLayerContractError(
            f"{surface_path}: unable to read SVG bytes for SHA-256: {exc}"
        ) from exc
    if actual_hash != surface.sha256:
        raise LogicalLayerContractError(
            f"{surface_path}: SHA-256 differs from surfaces[].sha256; "
            f"expected {surface.sha256}, got {actual_hash}"
        )
    if expected_hash is not None:
        _require_sha256(
            expected_hash,
            manifest.path,
            "expected_hash",
        )
        if actual_hash != expected_hash:
            raise LogicalLayerContractError(
                f"{surface_path}: expected_hash differs from exact SVG bytes; "
                f"expected {expected_hash}, got {actual_hash}"
            )

    try:
        contract = _inspect_svg_contract(
            surface_path,
            allow_sparse_neutral_ordinals=True,
        )
    except PenLayerContractError as exc:
        raise LogicalLayerContractError(
            f"{surface_path}: data-viz-layer-contract requires neutral input; "
            f"malformed legacy pen contract: {exc}"
        ) from exc
    if contract.mode is not InputMode.NEUTRAL:
        raise LogicalLayerContractError(
            f"{surface_path}: data-viz-layer-contract is missing; "
            f"manifest requires {NEUTRAL_CONTRACT!r}"
        )

    catalog = {layer.id: layer for layer in manifest.layers}
    for layer in contract.layers:
        expected = catalog.get(layer.id)
        if expected is None:
            raise LogicalLayerContractError(
                f"{surface_path}: data-viz-layer-id {layer.id!r} is unknown in "
                f"{manifest.path} logical_layers"
            )
        if layer.ordinal != expected.ordinal:
            raise LogicalLayerContractError(
                f"{surface_path}: data-viz-layer-ordinal for {layer.id!r} differs "
                f"from catalog; expected {expected.ordinal}, got {layer.ordinal}"
            )
        if layer.label != expected.label:
            raise LogicalLayerContractError(
                f"{surface_path}: data-viz-layer-label for {layer.id!r} differs "
                f"from catalog; expected {expected.label!r}, got {layer.label!r}"
            )

    active_ids = tuple(layer.id for layer in contract.layers)
    if surface.logical_layer_ids != active_ids:
        raise LogicalLayerContractError(
            f"{surface_path}: surfaces[].logical_layer_ids inventory/order differs "
            f"from SVG; expected {surface.logical_layer_ids}, got {active_ids}"
        )
    return contract


def _load_manifest_layers(
    path: Path, value: object
) -> tuple[LogicalLayerMetadata, ...]:
    if not isinstance(value, list):
        raise LogicalLayerContractError(f"{path}: logical_layers must be a JSON array")

    layers: list[LogicalLayerMetadata] = []
    seen_ids: set[str] = set()
    seen_ordinals: set[int] = set()
    for index, entry in enumerate(value):
        field = f"logical_layers[{index}]"
        if not isinstance(entry, dict):
            raise LogicalLayerContractError(f"{path}: {field} must be a JSON object")
        layer_id = entry.get("id")
        ordinal = entry.get("ordinal")
        label = entry.get("label")
        if not isinstance(layer_id, str) or not layer_id:
            raise LogicalLayerContractError(
                f"{path}: {field}.id must be a non-empty string"
            )
        if type(ordinal) is not int:
            raise LogicalLayerContractError(f"{path}: {field}.ordinal must be an integer")
        if not isinstance(label, str) or not label.strip():
            raise LogicalLayerContractError(
                f"{path}: {field}.label must be a non-empty string"
            )
        if layer_id in seen_ids:
            raise LogicalLayerContractError(
                f"{path}: duplicate logical_layers id {layer_id!r}"
            )
        if ordinal in seen_ordinals:
            raise LogicalLayerContractError(
                f"{path}: duplicate logical_layers ordinal {ordinal}"
            )
        seen_ids.add(layer_id)
        seen_ordinals.add(ordinal)
        layers.append(LogicalLayerMetadata(layer_id, ordinal, label))

    actual_ordinals = tuple(layer.ordinal for layer in layers)
    expected_ordinals = tuple(range(1, len(layers) + 1))
    if actual_ordinals != expected_ordinals:
        raise LogicalLayerContractError(
            f"{path}: logical_layers ordinals must be contiguous in catalog order; "
            f"expected {expected_ordinals}, got {actual_ordinals}"
        )
    return tuple(layers)


def _load_manifest_surfaces(
    path: Path, value: object
) -> tuple[LogicalLayerSurface, ...]:
    if not isinstance(value, list):
        raise LogicalLayerContractError(f"{path}: surfaces must be a JSON array")

    surfaces: list[LogicalLayerSurface] = []
    for index, entry in enumerate(value):
        field = f"surfaces[{index}]"
        if not isinstance(entry, dict):
            raise LogicalLayerContractError(f"{path}: {field} must be a JSON object")
        surface_path = entry.get("path")
        if not isinstance(surface_path, str):
            raise LogicalLayerContractError(f"{path}: {field}.path must be a string")
        if not _is_safe_manifest_path(surface_path):
            raise LogicalLayerContractError(
                f"{path}: {field}.path has an unsafe manifest-relative spelling: "
                f"{surface_path!r}"
            )
        digest = entry.get("sha256")
        _require_sha256(digest, path, f"{field}.sha256")
        inventory = entry.get("logical_layer_ids")
        if not isinstance(inventory, list):
            raise LogicalLayerContractError(
                f"{path}: {field}.logical_layer_ids must be a JSON array"
            )
        if any(not isinstance(layer_id, str) or not layer_id for layer_id in inventory):
            raise LogicalLayerContractError(
                f"{path}: {field}.logical_layer_ids must contain non-empty strings"
            )
        surfaces.append(
            LogicalLayerSurface(
                path=surface_path,
                sha256=digest,
                logical_layer_ids=tuple(inventory),
                raw=entry,
            )
        )
    return tuple(surfaces)


def _require_sha256(value: object, path: Path, field: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise LogicalLayerContractError(
            f"{path}: {field} must be a lowercase 64-character SHA-256"
        )


def _is_safe_manifest_path(value: str) -> bool:
    if not value or "\\" in value or ":" in value or "\x00" in value:
        return False
    candidate = PurePosixPath(value)
    return (
        not candidate.is_absolute()
        and all(part not in {"", ".", ".."} for part in value.split("/"))
        and candidate.as_posix() == value
    )


def _manifest_relative_path(
    svg_path: Path, manifest: LogicalLayerManifest
) -> str:
    try:
        return svg_path.resolve().relative_to(manifest.path.parent.resolve()).as_posix()
    except ValueError as exc:
        raise LogicalLayerContractError(
            f"{svg_path}: surface path is outside manifest directory {manifest.path.parent}"
        ) from exc


def _inspect_neutral(
    path: Path,
    root: ET.Element,
    neutral_groups: list[ET.Element],
    neutral_elements: list[ET.Element],
    *,
    allow_sparse_ordinals: bool,
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

    actual_ordinals = [layer.ordinal for layer in metadata]
    if allow_sparse_ordinals:
        if any(ordinal < 1 for ordinal in actual_ordinals) or actual_ordinals != sorted(
            actual_ordinals
        ):
            raise LogicalLayerContractError(
                f"{path}: neutral layer ordinals must be positive and ordered; "
                f"got {actual_ordinals}"
            )
    else:
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
