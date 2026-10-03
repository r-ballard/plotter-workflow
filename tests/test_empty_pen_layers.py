from pathlib import Path

from scripts.dpx3300_convert import validate_hpgl
from svg_pen_contract import inspect_pen_layer_contract


def test_empty_declared_pen_is_not_required_in_hpgl(tmp_path: Path):
    path = tmp_path / "plant-like.svg"
    path.write_text(
        """
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <g id="pen-1" data-pen="1" data-generations="0" fill="none" stroke="#000000">
    <g data-generation="0"></g>
  </g>
  <g id="pen-2" data-pen="2" data-generations="1" fill="none" stroke="#ff0000">
    <g data-generation="1"><path d="M 0 0 L 10 10"/></g>
  </g>
</svg>
""",
        encoding="utf-8",
    )

    contract = inspect_pen_layer_contract(path)

    assert contract is not None
    assert contract.declared_pens == (1, 2)
    assert contract.pens == (2,)

    hpgl = tmp_path / "plant-like.hpgl"
    hpgl.write_text(
        "IN;DF;SP2;PU0,0;PD10,10;PU;SP0;IN;",
        encoding="ascii",
    )
    validate_hpgl(hpgl, expected_pens=contract.pens)
