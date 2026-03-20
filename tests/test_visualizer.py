from pathlib import Path

from compiler_v2 import AICodeCompiler
from scripts.visualize_ainl import generate_mermaid, render_mermaid_to_image


def test_smoke_export_png_svg(tmp_path: Path):
    code = "L1: R core.ADD 2 3 ->x J x\n"
    ir = AICodeCompiler(strict_mode=True).compile(code, emit_graph=True)
    assert not ir.get("errors"), ir.get("errors")

    mermaid = generate_mermaid(ir, with_clusters=True, labels_only=False)

    png = render_mermaid_to_image(mermaid, format="png", width=800, height=600)
    svg = render_mermaid_to_image(mermaid, format="svg", width=800, height=600)

    png_path = tmp_path / "diagram.png"
    svg_path = tmp_path / "diagram.svg"
    png_path.write_bytes(png)
    svg_path.write_bytes(svg)

    assert png_path.exists()
    assert svg_path.exists()
    assert png_path.stat().st_size > 0
    assert svg_path.stat().st_size > 0
