from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from hpgl_placement import Bounds, PlacementValidationError, validate_hpgl_placement
from pen_plan import (
    PenPlanError,
    ResolvedPenPlan,
    discover_resolved_pen_plan_path,
    physical_pens_in_hpgl,
    plan_has_documented_tools,
    validate_resolved_pen_plan_for_hpgl,
)


class JobPreflightError(ValueError):
    """Raised when an HP-GL job is not safe/consistent enough to send."""


@dataclass(frozen=True)
class JobPreflightReport:
    hpgl_file: str
    hpgl_sha256: str
    physical_pen_order: tuple[int, ...]
    pen_plan_file: str | None
    placement_report_file: str
    device: str
    page_profile: str
    margin: str
    paper_bounds: Bounds
    margin_bounds: Bounds
    drawing_bounds: Bounds
    addressed_bounds: Bounds
    coordinate_modes: tuple[str, ...]
    pen_plan_status: str
    placement_status: str
    tool_documentation_status: str
    operator_confirmation_status: str
    ready_to_send: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise JobPreflightError(f"Invalid JSON in {label} {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise JobPreflightError(f"{label} {path} must contain a JSON object")
    return raw


def _bounds_from_json(raw: object, *, label: str) -> Bounds:
    if not isinstance(raw, dict):
        raise JobPreflightError(f"{label} must be an object")
    try:
        return Bounds(
            min_x=float(raw["min_x"]),
            min_y=float(raw["min_y"]),
            max_x=float(raw["max_x"]),
            max_y=float(raw["max_y"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise JobPreflightError(f"{label} contains invalid bounds") from exc


def _bounds_close(left: Bounds, right: Bounds, tolerance: float = 2.0) -> bool:
    return all(
        abs(a - b) <= tolerance
        for a, b in zip(
            (left.min_x, left.min_y, left.max_x, left.max_y),
            (right.min_x, right.min_y, right.max_x, right.max_y),
        )
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_and_revalidate_placement(
    hpgl_path: Path,
    placement_path: Path,
    *,
    config_path: Path,
) -> tuple[dict[str, Any], Any]:
    if not placement_path.is_file():
        raise JobPreflightError(
            f"Placement report does not exist: {placement_path}. "
            "Re-run dpx3300_convert.py before sending."
        )
    raw = _load_json_object(placement_path, label="placement report")
    if raw.get("status") != "pass":
        raise JobPreflightError(
            f"Placement report {placement_path} does not have status='pass'"
        )
    if raw.get("source_hpgl") not in (None, "", hpgl_path.name):
        raise JobPreflightError(
            f"Placement report was generated for {raw.get('source_hpgl')!r}, "
            f"not {hpgl_path.name!r}"
        )

    try:
        device = str(raw["device"])
        page_profile = str(raw["page_profile"])
        margin = str(raw["margin"])
    except KeyError as exc:
        raise JobPreflightError(
            f"Placement report {placement_path} is missing {exc.args[0]!r}"
        ) from exc

    try:
        current = validate_hpgl_placement(
            hpgl_path,
            config_path=config_path,
            device=device,
            page_profile=page_profile,
            margin=margin,
        )
    except PlacementValidationError as exc:
        raise JobPreflightError(f"Current HP-GL fails placement validation: {exc}") from exc

    stored_drawing = _bounds_from_json(raw.get("drawing_bounds"), label="drawing_bounds")
    stored_addressed = _bounds_from_json(raw.get("addressed_bounds"), label="addressed_bounds")
    if not _bounds_close(stored_drawing, current.drawing_bounds):
        raise JobPreflightError(
            "Placement report is stale: stored drawing bounds do not match current HP-GL"
        )
    if not _bounds_close(stored_addressed, current.addressed_bounds):
        raise JobPreflightError(
            "Placement report is stale: stored addressed bounds do not match current HP-GL"
        )

    stored_modes = tuple(str(value) for value in raw.get("coordinate_modes", []))
    if stored_modes and stored_modes != current.coordinate_modes:
        raise JobPreflightError(
            "Placement report is stale: coordinate modes do not match current HP-GL"
        )
    return raw, current


def run_job_preflight(
    hpgl_path: Path,
    *,
    config_path: Path,
    pen_plan_path: Path | None = None,
    placement_report_path: Path | None = None,
    require_operator_confirmation: bool = False,
    operator_confirmed: bool = False,
) -> tuple[JobPreflightReport, ResolvedPenPlan | None]:
    hpgl_path = Path(hpgl_path).expanduser().resolve()
    config_path = Path(config_path).expanduser().resolve()
    if not hpgl_path.is_file() or hpgl_path.stat().st_size == 0:
        raise JobPreflightError(f"HP-GL file is missing or empty: {hpgl_path}")
    if not config_path.is_file():
        raise JobPreflightError(f"vpype configuration does not exist: {config_path}")

    physical_pens = physical_pens_in_hpgl(hpgl_path)
    if not physical_pens:
        raise JobPreflightError("HP-GL contains no physical SP1..SP8 pen selection")

    if placement_report_path is None:
        placement_report_path = hpgl_path.with_suffix(".placement.json")
    else:
        placement_report_path = Path(placement_report_path).expanduser().resolve()
    _, placement = _load_and_revalidate_placement(
        hpgl_path, placement_report_path, config_path=config_path
    )

    resolved_plan: ResolvedPenPlan | None = None
    if pen_plan_path is None:
        candidate = discover_resolved_pen_plan_path(hpgl_path)
    else:
        candidate = Path(pen_plan_path).expanduser().resolve()

    if candidate.is_file():
        try:
            resolved_plan = validate_resolved_pen_plan_for_hpgl(hpgl_path, candidate)
        except PenPlanError as exc:
            raise JobPreflightError(str(exc)) from exc
        pen_plan_status = "pass"
        documented = plan_has_documented_tools(resolved_plan)
        tool_status = "pass" if documented else "fail"
        if len(physical_pens) > 1 and not documented:
            raise JobPreflightError(
                "Multi-pen job requires a tool or label for every used physical slot"
            )
        pen_plan_file: str | None = str(candidate)
    else:
        if len(physical_pens) > 1:
            raise JobPreflightError(
                f"Multi-pen job uses {physical_pens} but resolved pen plan is missing: {candidate}"
            )
        pen_plan_status = "not-required-single-pen"
        tool_status = "not-required-single-pen"
        pen_plan_file = None

    needs_confirmation = len(physical_pens) > 1
    if needs_confirmation and require_operator_confirmation and not operator_confirmed:
        raise JobPreflightError(
            "Multi-pen send requires --confirm-pen-plan after physically checking carriage loading"
        )
    confirmation_status = (
        "confirmed"
        if needs_confirmation and operator_confirmed
        else "required-before-send"
        if needs_confirmation
        else "not-required-single-pen"
    )
    ready_to_send = not needs_confirmation or operator_confirmed

    report = JobPreflightReport(
        hpgl_file=str(hpgl_path),
        hpgl_sha256=_sha256(hpgl_path),
        physical_pen_order=physical_pens,
        pen_plan_file=pen_plan_file,
        placement_report_file=str(placement_report_path),
        device=placement.device,
        page_profile=placement.page_profile,
        margin=placement.margin,
        paper_bounds=placement.paper_bounds,
        margin_bounds=placement.margin_bounds,
        drawing_bounds=placement.drawing_bounds,
        addressed_bounds=placement.addressed_bounds,
        coordinate_modes=placement.coordinate_modes,
        pen_plan_status=pen_plan_status,
        placement_status="pass",
        tool_documentation_status=tool_status,
        operator_confirmation_status=confirmation_status,
        ready_to_send=ready_to_send,
    )
    return report, resolved_plan


def format_job_preflight(
    report: JobPreflightReport, plan: ResolvedPenPlan | None = None
) -> str:
    lines = [
        "DPX-3300 JOB PREFLIGHT",
        f"File: {Path(report.hpgl_file).name}",
        f"HPGL SHA-256: {report.hpgl_sha256}",
        f"Device/profile: {report.device} / {report.page_profile}",
        f"Margin: {report.margin}",
        f"Coordinate modes: {', '.join(report.coordinate_modes)}",
        (
            "Drawing bounds: "
            f"X={report.drawing_bounds.min_x:.0f}..{report.drawing_bounds.max_x:.0f}, "
            f"Y={report.drawing_bounds.min_y:.0f}..{report.drawing_bounds.max_y:.0f}"
        ),
        (
            "Addressed bounds: "
            f"X={report.addressed_bounds.min_x:.0f}..{report.addressed_bounds.max_x:.0f}, "
            f"Y={report.addressed_bounds.min_y:.0f}..{report.addressed_bounds.max_y:.0f}"
        ),
        "HPGL pen order: " + " -> ".join([*(f"SP{pen}" for pen in report.physical_pen_order), "SP0"]),
    ]
    if plan is not None:
        lines.append("Carriage:")
        for assignment in plan.assignments:
            description = " / ".join(
                value
                for value in (assignment.label, assignment.tool, assignment.color)
                if value
            ) or "<not documented>"
            lines.append(
                f"  SP{assignment.physical_slot}: logical {assignment.logical_layer} "
                f"(generations {','.join(map(str, assignment.generations)) or '-'}) - {description}"
            )
    lines.extend(
        [
            f"Pen plan: {report.pen_plan_status.upper()}",
            f"Placement: {report.placement_status.upper()}",
            f"Carriage documentation: {report.tool_documentation_status.upper()}",
            f"Operator confirmation: {report.operator_confirmation_status}",
            "READY TO SEND" if report.ready_to_send else "VALIDATED - OPERATOR CONFIRMATION REQUIRED",
        ]
    )
    return "\n".join(lines)


def write_preflight_report(report: JobPreflightReport, destination: Path) -> Path:
    destination = Path(destination)
    destination.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return destination


def _existing_file(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"File does not exist: {path}")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a DPX-3300 HP-GL job, resolved pen plan, and placement report."
    )
    parser.add_argument("hpgl", type=_existing_file)
    parser.add_argument(
        "--vpype-config",
        type=_existing_file,
        default=Path(__file__).resolve().with_name("vpype.toml"),
    )
    parser.add_argument("--pen-plan", type=_existing_file)
    parser.add_argument("--placement-report", type=_existing_file)
    parser.add_argument(
        "--confirm-pen-plan",
        action="store_true",
        help="Record that the physical multi-pen carriage loading has been checked.",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write <hpgl-stem>.preflight.json beside the HP-GL file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report, plan = run_job_preflight(
            args.hpgl,
            config_path=args.vpype_config,
            pen_plan_path=args.pen_plan,
            placement_report_path=args.placement_report,
            operator_confirmed=args.confirm_pen_plan,
        )
    except (JobPreflightError, PenPlanError, PlacementValidationError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print(format_job_preflight(report, plan))
    if args.write_report:
        path = args.hpgl.with_suffix(".preflight.json")
        write_preflight_report(report, path)
        print(f"Preflight report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
