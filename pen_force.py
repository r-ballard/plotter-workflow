"""Validated physical force expectations, independent of SVG and transport."""

from dataclasses import dataclass

FORCES = (20, 35, 50, 65, 80, 95, 110, 125)


@dataclass(frozen=True)
class ForceSpec:
    mode: str
    default_gf: int | None = None
    slot_overrides: tuple[tuple[int, int], ...] = ()

    def __post_init__(self):
        if self.mode not in ("software", "panel"):
            raise ValueError("pen_force.mode must be software or panel")
        if self.default_gf is not None:
            force_code(self.default_gf)
        overrides = tuple(self.slot_overrides)
        seen = set()
        for slot, gf in overrides:
            if type(slot) is not int or not 1 <= slot <= 8 or slot in seen:
                raise ValueError("force override slots must be distinct integers 1 through 8")
            force_code(gf)
            seen.add(slot)
        if self.default_gf is None and not overrides:
            raise ValueError("pen_force requires default_gf or slot_overrides")
        object.__setattr__(self, "slot_overrides", tuple(sorted(overrides)))


def force_code(gf: int) -> int:
    if type(gf) is not int or gf not in FORCES:
        raise ValueError(f"force_gf must be one of {FORCES}, got {gf!r}")
    return 1 + 2 * FORCES.index(gf)


def force_gf(code: int) -> int:
    if type(code) is not int or not 1 <= code <= 16:
        raise ValueError("FS code must be an integer 1 through 16")
    return FORCES[(code - 1) // 2]


def effective_force(spec: ForceSpec, slot: int) -> int | None:
    if type(slot) is not int or not 1 <= slot <= 8:
        raise ValueError("physical slot must be an integer 1 through 8")
    return dict(spec.slot_overrides).get(slot, spec.default_gf)


def parse_force(raw: object) -> ForceSpec | None:
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) - {"mode", "default_gf", "slot_overrides"}:
        raise ValueError("pen_force must be a strict object")
    if "default_gf" in raw:
        force_code(raw["default_gf"])
    overrides = raw.get("slot_overrides", [])
    if not isinstance(overrides, list):
        raise ValueError("slot_overrides must be an array")
    records = []
    for entry in overrides:
        if not isinstance(entry, dict) or set(entry) != {"slot", "force_gf"}:
            raise ValueError("each force override requires exactly slot and force_gf")
        records.append((entry["slot"], entry["force_gf"]))
    return ForceSpec(raw.get("mode"), raw.get("default_gf"), tuple(records))


def force_payload(spec: ForceSpec | None) -> dict | None:
    if spec is None:
        return None
    result = {"mode": spec.mode}
    if spec.default_gf is not None:
        result["default_gf"] = spec.default_gf
    if spec.slot_overrides:
        result["slot_overrides"] = [{"slot": s, "force_gf": gf} for s, gf in spec.slot_overrides]
    return result
