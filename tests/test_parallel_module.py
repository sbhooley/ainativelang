from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compiler_v2 import AICodeCompiler  # noqa: E402


def test_parallel_module_include_compiles_strict(tmp_path: Path) -> None:
    mod_src = (ROOT / "modules" / "common" / "parallel.ainl").read_text(encoding="utf-8")
    (tmp_path / "modules" / "common").mkdir(parents=True, exist_ok=True)
    (tmp_path / "modules" / "common" / "parallel.ainl").write_text(mod_src, encoding="utf-8")
    main = tmp_path / "app.ainl"
    main.write_text(
        'include modules/common/parallel.ainl as par\n'
        'L1: Set parallel_queue_name "notify" Set parallel_payloads "{}" Set parallel_count 1 Call par/ENTRY ->out J out\n',
        encoding="utf-8",
    )
    ir = AICodeCompiler(strict_mode=True).compile(main.read_text(encoding="utf-8"), source_path=str(main))
    assert not ir.get("errors"), ir.get("errors")
    assert "par/ENTRY" in ir["labels"]
