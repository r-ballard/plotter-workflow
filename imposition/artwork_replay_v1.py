"""Frozen schema-v1 replay used only when reading historical artwork handoffs."""

import copy

from .artwork_io import MAX_BYTES, json_bytes
from .artwork_layout import ID_RE


def replay_v1_job(layout, template):
    if layout.settings.get("layout") == "cassette-jcard":
        return _replay_jcard_job(layout, template, mode=layout.settings["mode"])
    return _build_standard_artwork_job(layout, template)


def _build_standard_artwork_job(layout, template):
    if not isinstance(template, dict) or set(template) - {
        "schema_version",
        "seed",
        "domains",
        "surfaces",
        "groups",
        "relations",
        "composition_transforms",
        "passes",
    }:
        raise ValueError("unknown artwork template fields")
    if (
        type(template.get("schema_version")) is not int
        or template["schema_version"] != 1
        or type(template.get("seed")) is not int
    ):
        raise ValueError("artwork template requires schema_version1 and integer seed")
    if template.get("groups") or template.get("relations"):
        raise ValueError("template cannot retain stale groups/relations")
    passes = template.get("passes")
    if not isinstance(passes, list) or len(passes) != 1:
        raise ValueError("template requires exactly one pass")
    p = copy.deepcopy(passes[0])
    if not isinstance(p, dict) or set(p) - {
        "id",
        "algorithm",
        "target_domain_ids",
        "parameters",
        "logical_layers",
        "depends_on",
        "group_context_ids",
        "relation_context_ids",
    }:
        raise ValueError("invalid template pass fields")
    if p.get("algorithm") not in (
        "truchet",
        "truchet-multiscale",
        "truchet-triangular",
        "truchet-triangular-multiscale",
        "ball-stick",
        "ball-stick-3d",
    ) or not ID_RE.fullmatch(p.get("id", "")):
        raise ValueError("template requires a supported artwork pass with safe ID")
    if any(
        p.get(k) for k in ("depends_on", "group_context_ids", "relation_context_ids")
    ):
        raise ValueError("template cannot retain pass dependencies")
    triangular = p["algorithm"] in (
        "truchet-triangular",
        "truchet-triangular-multiscale",
    )
    curve_key = "curve_layer_id" if triangular else "curve_layer_ids"
    parameters = p.get("parameters")
    truchet = p["algorithm"].startswith("truchet")
    if not isinstance(parameters, dict):
        raise ValueError("template requires structured parameters")  # noqa: TRY004 -- export validation API
    if truchet and (
        not isinstance(parameters.get("region_fills"), dict)
        or not parameters.get(curve_key)
    ):
        raise ValueError(f"template requires structured region_fills and {curve_key}")
    if (
        parameters.get("coordinate_frame", "composition") != "composition"
        or parameters.get("composition_mode", "continuous") != "continuous"
    ):
        raise ValueError("template requires continuous composition")
    layers = p.get("logical_layers")
    if (
        not isinstance(layers, list)
        or not layers
        or any(
            not isinstance(v, dict) or not ID_RE.fullmatch(v.get("id", ""))
            for v in layers
        )
        or len({v["id"] for v in layers}) != len(layers)
    ):
        raise ValueError("template requires unique safe logical layer IDs")
    parameters["coordinate_frame"] = "composition"
    if truchet:
        if triangular and "curve_layer_ids" in parameters:
            raise ValueError(
                "triangular recipes use curve_layer_id, not curve_layer_ids"
            )
        palette = [parameters[curve_key]] if triangular else parameters[curve_key]
        declared = {v["id"] for v in layers}
        if (
            not isinstance(palette, list)
            or not palette
            or any(not isinstance(v, str) or v not in declared for v in palette)
            or len(set(palette)) != len(palette)
        ):
            raise ValueError(f"{curve_key} requires unique declared logical layer IDs")
        x, y, w, h = layout.window
        parameters.update(
            composition_mode="continuous",
            composition_window={"x": x, "y": y, "width": w, "height": h},
        )
    p["target_domain_ids"] = [v.panel_id for v in layout.panels]
    job = {
        "schema_version": 1,
        "seed": template["seed"],
        "domains": [
            {"id": v.panel_id, "vertices": [list(q) for q in v.crop_polygon]}
            for v in layout.panels
        ],
        "composition_transforms": [
            {"domain_id": v.panel_id, "matrix": list(v.assembled_matrix)}
            for v in layout.panels
        ],
        "passes": [p],
    }
    if len(json_bytes(job)) > MAX_BYTES:
        raise ValueError("artwork job exceeds size limit")
    return job


def _replay_jcard_job(layout, template, *, mode):
    if mode != layout.settings["mode"]:
        raise ValueError("Artwork mode differs from layout")
    adapted = copy.deepcopy(template)
    # Standard validation still owns supported algorithms/catalogs. Normalize only
    # the scoped frame controls before applying the selected native face mode.
    if (
        isinstance(adapted, dict)
        and isinstance(adapted.get("passes"), list)
        and len(adapted["passes"]) == 1
    ):
        if not isinstance(adapted["passes"][0], dict):
            raise ValueError("Artwork pass must be an object")
        params = adapted["passes"][0].get("parameters")
        if isinstance(params, dict):
            if "coordinate_frame" in params and params["coordinate_frame"] not in (
                "domain",
                "composition",
            ):
                raise ValueError("Unsupported coordinate_frame")
            if "composition_mode" in params and params["composition_mode"] not in (
                "continuous",
                "independent-panels",
            ):
                raise ValueError("Unsupported composition_mode")
            params["coordinate_frame"] = "composition"
            params["composition_mode"] = "continuous"
    job = _build_standard_artwork_job(layout, adapted)
    if mode == "independent":
        params = job["passes"][0]["parameters"]
        params["coordinate_frame"] = "domain"
        for key in ("composition_mode", "composition_window", "seam_margin"):
            params.pop(key, None)
        job.pop("composition_transforms")
    return job
