"""Golden / unit tests for tooling.ainl_get_started wizard helpers."""

from __future__ import annotations

import pytest

from tooling.ainl_get_started import (
    get_started,
    initialize_wizard_state,
    step_examples,
)


class TestGetStartedGolden:
    """Checkpoint expectations aligned with plan ``ainl_wizard_and_validation_depth``."""

    def test_run_existing_style_goal_has_core_path(self) -> None:
        out = get_started("Run hello.ainl from the examples folder")
        assert out.get("ok") is True
        ws = out.get("wizard_state") or {}
        assert "can_author_now" in ws
        assert out.get("formal_stage")

    def test_adapter_heavy_goal_lists_missing_checkpoints(self) -> None:
        out = get_started(
            "Scrape leads from URLs, enrich with HTTP, save CSV to disk",
        )
        assert out.get("ok") is True
        ws = out.get("wizard_state") or {}
        missing = ws.get("missing_checkpoints") or []
        assert isinstance(missing, list)
        assert len(missing) >= 1

    def test_step_examples_fs_topic_returns_snippets_and_ok_shape(self) -> None:
        out = step_examples(
            current_step="incremental_authoring",
            request_examples_for="fs write csv",
            example_count=2,
        )
        assert out.get("wizard_stage") == "incremental_authoring"
        assert out.get("matched_adapter") == "fs"
        ex = out.get("examples") or []
        assert len(ex) >= 1
        assert any("fs.write" in (e.get("code") or "") for e in ex)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-q"])
