from __future__ import annotations

from pathlib import Path


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--postgres-url",
        action="store",
        default="",
        help="Optional PostgreSQL DSN for postgres integration tests (fallback: AINL_POSTGRES_URL).",
    )
    parser.addoption(
        "--mysql-url",
        action="store",
        default="",
        help="Optional MySQL DSN for mysql integration tests (fallback: AINL_MYSQL_URL).",
    )
    parser.addoption(
        "--redis-url",
        action="store",
        default="",
        help="Optional Redis URL for redis integration tests (fallback: AINL_REDIS_URL).",
    )
    parser.addoption(
        "--dynamodb-url",
        action="store",
        default="",
        help="Optional DynamoDB endpoint URL for dynamodb integration tests (fallback: AINL_DYNAMODB_URL).",
    )
    parser.addoption(
        "--airtable-api-key",
        action="store",
        default="",
        help="Optional Airtable API key for airtable integration tests (fallback: AINL_AIRTABLE_API_KEY).",
    )
    parser.addoption(
        "--airtable-base-id",
        action="store",
        default="",
        help="Optional Airtable base id for airtable integration tests (fallback: AINL_AIRTABLE_BASE_ID).",
    )
    parser.addoption(
        "--supabase-url",
        action="store",
        default="",
        help="Optional Supabase project URL for supabase integration tests (fallback: AINL_SUPABASE_URL).",
    )
    parser.addoption(
        "--supabase-service-role-key",
        action="store",
        default="",
        help="Optional Supabase service role key for supabase integration tests (fallback: AINL_SUPABASE_SERVICE_ROLE_KEY).",
    )


def pytest_configure(config) -> None:
    """
    Syrupy resolves snapshot_dirname relative to each test file. Conformance snapshots
    live under tests/snapshots/conformance; this must run from the root tests conftest
    so it applies even when the full suite is collected (nested conftest hooks can run
    too late for the first conformance parametrizations).
    """
    if hasattr(config.option, "snapshot_dirname"):
        config.option.snapshot_dirname = "../snapshots/conformance"


def pytest_collection_modifyitems(config, items):
    """
    Auto-mark slower/runtime-heavy suites as integration so default profile
    (`not integration and not emits and not lsp`) stays stable.
    """
    integration_name_prefixes = (
        "test_runtime_",
        "test_runner_service",
        "test_replay_determinism",
        "test_capability_contracts",
    )
    integration_exact = {
        "test_conformance.py",
        "test_lossless.py",
    }

    for item in items:
        p = Path(str(item.fspath))
        name = p.name
        # Property tests and runtime-heavy suites are integration profile.
        if "tests/property/" in str(p).replace("\\", "/"):
            item.add_marker("integration")
            continue
        if name in integration_exact or name.startswith(integration_name_prefixes):
            item.add_marker("integration")
