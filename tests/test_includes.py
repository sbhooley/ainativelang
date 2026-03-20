"""Tests for v1 `include` / subgraph modules (compiler_v2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compiler_diagnostics import CompilationDiagnosticError, CompilerContext  # noqa: E402
from compiler_v2 import AICodeCompiler  # noqa: E402


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write_mod(isolated_cwd: Path, rel: str, text: str) -> Path:
    p = isolated_cwd / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_include_merges_prefixed_labels(isolated_cwd: Path) -> None:
    _write_mod(
        isolated_cwd,
        "modules/common/retry.ainl",
        """LENTRY:
  R core.ADD 1 1 ->x
  J x
LEXIT_OK:
  J "ok"
LEXIT_FAIL:
  J "err"
""",
    )
    main = isolated_cwd / "app.ainl"
    main.write_text(
        'include modules/common/retry.ainl as retry\n'
        "L1: R core.ADD 2 2 ->z J z\n",
        encoding="utf-8",
    )
    ir = AICodeCompiler(strict_mode=True).compile(
        main.read_text(encoding="utf-8"),
        source_path=str(main),
    )
    assert "retry/ENTRY" in ir["labels"]
    assert "retry/EXIT_OK" in ir["labels"]
    assert "retry/EXIT_FAIL" in ir["labels"]
    # Canonical label id for `L1:` is normalized to "1".
    assert "1" in ir["labels"]


def test_include_default_alias_is_path_stem(isolated_cwd: Path) -> None:
    _write_mod(
        isolated_cwd,
        "lib/wait.lang",
        """LENTRY:
  J "data"
LEXIT_OK:
  J "ok"
""",
    )
    main = isolated_cwd / "root.ainl"
    main.write_text('include lib/wait.lang\nL1: J "x"\n', encoding="utf-8")
    ir = AICodeCompiler(strict_mode=True).compile(
        main.read_text(encoding="utf-8"),
        source_path=str(main),
    )
    assert "wait/ENTRY" in ir["labels"]
    assert "wait/EXIT_OK" in ir["labels"]


def test_include_missing_file_strict(isolated_cwd: Path) -> None:
    main = isolated_cwd / "main.ainl"
    main.write_text('include modules/missing.ainl as m\nL1: J "x"\n', encoding="utf-8")
    ctx = CompilerContext()
    with pytest.raises(CompilationDiagnosticError) as ei:
        AICodeCompiler(strict_mode=True).compile(
            main.read_text(encoding="utf-8"),
            context=ctx,
            source_path=str(main),
        )
    kinds = {d.kind for d in ei.value.diagnostics}
    assert "include_failure" in kinds
    diag_text = " ".join(d.message for d in ei.value.diagnostics)
    assert "m/ENTRY" not in diag_text  # no merge of missing module


def test_include_cycle_detected(isolated_cwd: Path) -> None:
    _write_mod(
        isolated_cwd,
        "a.ainl",
        'include b.ainl as b\nLENTRY:\n  J x\nLEXIT_OK:\n  J ok\n',
    )
    _write_mod(
        isolated_cwd,
        "b.ainl",
        'include a.ainl as a\nLENTRY:\n  J x\nLEXIT_OK:\n  J ok\n',
    )
    main = isolated_cwd / "main.ainl"
    main.write_text('include a.ainl as a\nL1: J z\n', encoding="utf-8")
    ctx = CompilerContext()
    with pytest.raises(CompilationDiagnosticError):
        AICodeCompiler(strict_mode=True).compile(
            main.read_text(encoding="utf-8"),
            context=ctx,
            source_path=str(main),
        )


def test_include_strict_rejects_missing_entry_label(isolated_cwd: Path) -> None:
    _write_mod(
        isolated_cwd,
        "bad.ainl",
        """LEXIT_OK:
  J "ok"
""",
    )
    main = isolated_cwd / "main.ainl"
    main.write_text('include bad.ainl as bad\nL1: J "x"\n', encoding="utf-8")
    ctx = CompilerContext()
    with pytest.raises(CompilationDiagnosticError) as ei:
        AICodeCompiler(strict_mode=True).compile(
            main.read_text(encoding="utf-8"),
            context=ctx,
            source_path=str(main),
        )
    msg = " ".join(d.message for d in ei.value.diagnostics)
    assert "ENTRY" in msg


def test_include_strict_rejects_top_level_e_in_subgraph(isolated_cwd: Path) -> None:
    _write_mod(
        isolated_cwd,
        "ep.ainl",
        """E /x G ->L1
LENTRY:
  J "x"
LEXIT_OK:
  J "ok"
""",
    )
    main = isolated_cwd / "main.ainl"
    main.write_text('include ep.ainl as ep\nL1: J "z"\n', encoding="utf-8")
    ctx = CompilerContext()
    with pytest.raises(CompilationDiagnosticError) as ei:
        AICodeCompiler(strict_mode=True).compile(
            main.read_text(encoding="utf-8"),
            context=ctx,
            source_path=str(main),
        )
    joined = " ".join(d.message for d in ei.value.diagnostics)
    assert "E" in joined or "endpoint" in joined.lower() or "S" in joined


def test_include_non_strict_warns_and_merges_contract_violation(isolated_cwd: Path) -> None:
    _write_mod(
        isolated_cwd,
        "bad.ainl",
        """LEXIT_OK:
  J "ok"
""",
    )
    main = isolated_cwd / "main.ainl"
    main.write_text('include bad.ainl as bad\nL1: J "x"\n', encoding="utf-8")
    ir = AICodeCompiler(strict_mode=False).compile(
        main.read_text(encoding="utf-8"),
        source_path=str(main),
    )
    assert any("include" in w.lower() or "ENTRY" in w for w in ir.get("warnings", []))
    assert "bad/EXIT_OK" in ir["labels"]


def test_include_subgraph_quoted_jump_survives_parent_lowering(isolated_cwd: Path) -> None:
    """String literal J targets in merged subgraphs stay literals after parent _steps_to_graph_all."""
    _write_mod(
        isolated_cwd,
        "modules/lib/mod.ainl",
        """LENTRY:
  R core.ADD 1 1 ->x
  J x
LEXIT_OK:
  J "result"
""",
    )
    main = isolated_cwd / "app.ainl"
    main.write_text(
        'include modules/lib/mod.ainl as mod\n'
        'L1: Call mod/ENTRY ->out J out\n',
        encoding="utf-8",
    )
    ir = AICodeCompiler(strict_mode=True).compile(
        main.read_text(encoding="utf-8"),
        source_path=str(main),
    )
    assert not ir.get("errors"), ir.get("errors")
    exit_body = ir["labels"]["mod/EXIT_OK"]
    j_nodes = [n for n in exit_body.get("nodes", []) if n.get("op") == "J"]
    assert j_nodes, "expected a J node on mod/EXIT_OK"
    assert j_nodes[0].get("reads") == [], j_nodes[0]


def test_include_strict_dataflow_error_names_prefixed_label(isolated_cwd: Path) -> None:
    """Undefined jump inside an included subgraph is reported under alias/ENTRY."""
    _write_mod(
        isolated_cwd,
        "modules/helper/badflow.ainl",
        """LENTRY:
  J totally_undefined_var
LEXIT_OK:
  J "ok"
""",
    )
    main = isolated_cwd / "main.ainl"
    main.write_text(
        'include modules/helper/badflow.ainl as helper\nL1: J "done"\n',
        encoding="utf-8",
    )
    ctx = CompilerContext()
    with pytest.raises(CompilationDiagnosticError) as ei:
        AICodeCompiler(strict_mode=True).compile(
            main.read_text(encoding="utf-8"),
            context=ctx,
            source_path=str(main),
        )
    joined = " ".join(d.message for d in ei.value.diagnostics)
    assert "helper/ENTRY" in joined
    assert "totally_undefined_var" in joined
    assert "helper" in joined


def test_shipped_retry_module_from_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    main = ROOT / "tmp_main_include_smoke.ainl"
    try:
        main.write_text(
            'include modules/common/retry.ainl as retry\nL1: Call retry/ENTRY ->out J out\n',
            encoding="utf-8",
        )
        ir = AICodeCompiler(strict_mode=True).compile(
            main.read_text(encoding="utf-8"),
            source_path=str(main),
        )
        assert not ir.get("errors"), ir.get("errors")
        assert "retry/ENTRY" in ir["labels"]
    finally:
        if main.exists():
            main.unlink()
