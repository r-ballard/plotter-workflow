from pathlib import Path

import pytest

from pen_force import effective_force
from pen_plan_io import load_pen_plan
from pen_plan_models import LayerInfo
from pen_plan_resolution import resolve_plot_passes

ROOT = Path(__file__).resolve().parents[1]
PLANS = tuple(sorted((ROOT / "examples/penplans").glob("*.penplan.json")))


@pytest.mark.parametrize("path", PLANS, ids=lambda p: p.name)
def test_repository_examples_use_current_schema_and_resolve(path):
    spec = load_pen_plan(path)
    if spec.policy == "explicit":
        ids = list(
            dict.fromkeys(
                layer for p in spec.passes for a in p.assignments for layer in a.layer_ids
            )
        )
        ids.extend(layer for layer in spec.omitted_layers if layer not in ids)
    else:
        ids = [f"pen-{i}" for i in range(1, 9 if spec.pen_force else 6)]
    passes = resolve_plot_passes(
        tuple(LayerInfo(layer, True, i) for i, layer in enumerate(ids, 1)), spec
    )
    assert passes
    if spec.pen_force:
        assert all(effective_force(spec.pen_force, s) == 65 for s in range(1, 9))
        assert len(spec.slots) == 8 and not spec.pen_force.slot_overrides
