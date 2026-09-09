import shutil
from pathlib import Path

from cootie_impose import EXPECTED_SLOTS, impose, load_manifest, square_placement

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_MANIFEST = REPO_ROOT / "examples" / "cootie-bundle" / "cootie.json"
VALIDATION_PANELS = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "imposition"
    / "cootie_catcher"
    / "validation_panels"
)
VIZ_SURFACE = REPO_ROOT / "tests" / "fixtures" / "viz_virtualserver_surface.svg"


def test_example_manifest_accepts_viz_virtualserver_surface_bundle(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "cootie-design-bundle"
    surfaces_dir = bundle_dir / "surfaces"
    surfaces_dir.mkdir(parents=True)
    for slot in EXPECTED_SLOTS:
        shutil.copyfile(VALIDATION_PANELS / f"{slot}.svg", surfaces_dir / f"{slot}.svg")
    shutil.copyfile(EXAMPLE_MANIFEST, bundle_dir / "cootie.json")

    entries = load_manifest(
        bundle_dir,
        bundle_dir / "cootie.json",
        default_fit="contain",
        default_margin_mm=3.0,
    )

    assert tuple(entry.slot for entry in entries) == EXPECTED_SLOTS
    assert tuple(entry.source.relative_to(bundle_dir).as_posix() for entry in entries) == tuple(
        f"surfaces/{slot}.svg" for slot in EXPECTED_SLOTS
    )


def test_example_manifest_imposes_representative_viz_virtualserver_surfaces(
    tmp_path: Path,
) -> None:
    bundle_dir = tmp_path / "cootie-design-bundle"
    surfaces_dir = bundle_dir / "surfaces"
    surfaces_dir.mkdir(parents=True)
    for slot in EXPECTED_SLOTS:
        shutil.copyfile(VIZ_SURFACE, surfaces_dir / f"{slot}.svg")
    shutil.copyfile(EXAMPLE_MANIFEST, bundle_dir / "cootie.json")
    entries = load_manifest(
        bundle_dir,
        bundle_dir / "cootie.json",
        default_fit="contain",
        default_margin_mm=3.0,
    )

    root, rendered, source_mode = impose(
        entries,
        sheet_size="letter",
        placement=square_placement("letter", position="left"),
        quantization_mm=0.1,
    )

    assert source_mode == "generic"
    assert len(rendered) == 20
    assert root.find("{http://www.w3.org/2000/svg}g").get("data-source-mode") == "generic"
