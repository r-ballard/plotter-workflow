"""Explicit partial asset assignments; physical placement stays with the imposer."""

import copy
from pathlib import PurePosixPath

from .objects.cootie_catcher import EXPECTED_SLOTS


def _safe_asset(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("asset path must be safe relative SVG path")
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in ("..", ".") for x in p.parts) or p.suffix.lower() != ".svg":
        raise ValueError("asset path must be safe relative SVG path")
    return str(p)


def build_layout_bindings(layout, asset_paths):
    if set(asset_paths) != {p.panel_id for p in layout.panels}:
        raise ValueError("asset mapping must match layout panels exactly")
    paths = {k: _safe_asset(v) for k, v in asset_paths.items()}
    if len({v.casefold() for v in paths.values()}) != len(paths):
        raise ValueError("asset paths must be unique")
    kinds = {p.binding.get("kind") for p in layout.panels}
    if kinds == {"booklet-page"}:
        kind = "booklet"
        all_ids = {f"page-{i}" for i in range(1, 9)}
        entries = []
        for p in layout.panels:
            page = p.binding.get("page")
            if type(page) is not int or page not in range(1, 9) or p.panel_id != f"page-{page}":
                raise ValueError("invalid logical page binding")
            entries.append(
                {
                    "page": page,
                    "source": paths[p.panel_id],
                    "fit": "contain",
                    "margin_mm": 0.0,
                    "gutter_mm": 0.0,
                }
            )
    elif kinds == {"cootie-slot"}:
        kind = "cootie"
        all_ids = set(EXPECTED_SLOTS)
        entries = []
        for p in layout.panels:
            slot = p.binding.get("slot")
            if slot not in EXPECTED_SLOTS or slot != p.panel_id:
                raise ValueError("invalid cootie slot binding")
            entries.append(
                {"slot": slot, "source": paths[p.panel_id], "fit": "contain", "margin_mm": 0.0}
            )
    elif kinds == {"jcard-slot"}:
        from .jcard_artwork import validate_jcard_layout

        validate_jcard_layout(layout)
        kind = "jcard"
        all_ids = {p.panel_id for p in layout.panels}
        entries = [{**dict(p.binding), "source": paths[p.panel_id]} for p in layout.panels]
    else:
        raise ValueError("unsupported layout binding family")
    remaining = sorted(all_ids - set(paths))
    return {
        "schema_version": 1,
        "artifact_type": "assembled-artwork-binding-patch",
        "kind": kind,
        "profile_id": layout.profile_id,
        "validation_status": layout.validation_status,
        "asset_manifest": "design.json",
        "complete": not remaining,
        "remaining_assignments": remaining,
        "entries": entries,
        "placement_policy": (
            "existing physical page/slot placement; assembled transform is not reapplied"
        ),
        "catalog_policy": (
            "validate all complete-manifest assets against a common catalog; "
            "no implicit catalog merge"
        ),
    }


def apply_layout_bindings(manifest, patch):
    """Pure merge helper; caller still validates completeness and layer catalogs."""
    if (
        not isinstance(manifest, dict)
        or not isinstance(patch, dict)
        or type(patch.get("schema_version")) is not int
        or patch["schema_version"] != 1
        or patch.get("artifact_type") != "assembled-artwork-binding-patch"
    ):
        raise ValueError("unsupported binding patch")
    result = copy.deepcopy(manifest)
    kind = patch.get("kind")
    entries = patch.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("empty binding patch")
    if kind == "booklet":
        rows = result.get("pages")
        if not isinstance(rows, list):
            raise ValueError("booklet manifest requires pages")
        replacements = {e["page"]: copy.deepcopy(e) for e in entries}
        if len(replacements) != len(entries):
            raise ValueError("duplicate page binding")
        output = []
        seen = set()
        for row in rows:
            pages = row.get("spread", [row.get("page")])
            overlap = set(pages) & set(replacements)
            if overlap:
                if not set(pages) <= set(replacements) or seen & overlap:
                    raise ValueError(
                        "patch only partially replaces or duplicates spread assignment"
                    )
                for page in pages:
                    output.append(replacements[page])
                    seen.add(page)
            else:
                output.append(row)
        if seen != set(replacements):
            raise ValueError("manifest missing selected page assignment")
        result["pages"] = output
    elif kind in ("cootie", "jcard"):
        rows = result.get("panels")
        if not isinstance(rows, list):
            raise ValueError("cootie manifest requires panels")
        replacements = {e["slot"]: e for e in entries}
        if len(replacements) != len(entries):
            raise ValueError("duplicate slot binding")
        seen = set()
        for row in rows:
            slot = row.get("slot")
            if slot in replacements:
                if slot in seen:
                    raise ValueError("duplicate original slot assignment")
                row.update(copy.deepcopy(replacements[slot]))
                seen.add(slot)
        if seen != set(replacements):
            raise ValueError("manifest missing selected slot assignment")
    else:
        raise ValueError("unsupported binding family")
    return result
