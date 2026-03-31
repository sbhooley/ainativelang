from __future__ import annotations  # AINL-OPENFANG-TOP5

# AINL-OPENFANG-TOP5 — single-line hint aligned with docs/QUICKSTART_OPENFANG.md pitfalls  # AINL-OPENFANG-TOP5
INIT_INSTALL_OPENFANG = "Run `ainl install openfang` to initialize."  # AINL-OPENFANG-TOP5


def user_friendly_ainl_error(e: BaseException) -> str:  # AINL-OPENFANG-TOP5
    msg = str(e)  # AINL-OPENFANG-TOP5
    low = msg.lower()  # AINL-OPENFANG-TOP5
    # Table / SQLite  # AINL-OPENFANG-TOP5
    if "no such table" in low or "table not found" in low:  # AINL-OPENFANG-TOP5
        if "weekly_remaining_v1" in low:  # AINL-OPENFANG-TOP5
            return "`weekly_remaining_v1` missing — " + INIT_INSTALL_OPENFANG  # AINL-OPENFANG-TOP5
        if "intelligencereport" in low:  # AINL-OPENFANG-TOP5
            return "IntelligenceReport is not used by OpenFang install (reports are Markdown). " + INIT_INSTALL_OPENFANG  # AINL-OPENFANG-TOP5
        return "SQLite table missing — " + INIT_INSTALL_OPENFANG  # AINL-OPENFANG-TOP5
    # Cron — match gold-standard job names in message  # AINL-OPENFANG-TOP5
    if ("cron" in low or "job" in low) and "not found" in low:  # AINL-OPENFANG-TOP5
        if "weekly token trends" in low or "ainl weekly token trends" in low:  # AINL-OPENFANG-TOP5
            return "Cron job 'AINL Weekly Token Trends' not found — " + INIT_INSTALL_OPENFANG  # AINL-OPENFANG-TOP5
        if "context injection" in low:  # AINL-OPENFANG-TOP5
            return "Cron job 'AINL Context Injection' not found — " + INIT_INSTALL_OPENFANG  # AINL-OPENFANG-TOP5
        if "session summarizer" in low:  # AINL-OPENFANG-TOP5
            return "Cron job 'AINL Session Summarizer' not found — " + INIT_INSTALL_OPENFANG  # AINL-OPENFANG-TOP5
        return "Cron job not found — " + INIT_INSTALL_OPENFANG  # AINL-OPENFANG-TOP5
    # RPC / bridge / gateway down  # AINL-OPENFANG-TOP5
    if "rpcwireerror" in low or "rpc wire" in low:  # AINL-OPENFANG-TOP5
        return "RPCWireError from host RPC. Ensure the OpenFang gateway is running, then retry (or run `ainl doctor --ainl`)."  # AINL-OPENFANG-TOP5
    if "econnrefused" in low or "connection refused" in low:  # AINL-OPENFANG-TOP5
        return "Connection refused — OpenFang gateway may be down. Start or restart it (`openfang gateway restart`), then retry."  # AINL-OPENFANG-TOP5
    # Env — bootstrap preference  # AINL-OPENFANG-TOP5
    if "openfang_bootstrap_prefer_session_context" in low or (  # AINL-OPENFANG-TOP5
        "openfang_bootstrap" in low and "prefer" in low  # AINL-OPENFANG-TOP5
    ):  # AINL-OPENFANG-TOP5
        return (  # AINL-OPENFANG-TOP5
            "`OPENFANG_BOOTSTRAP_PREFER_SESSION_CONTEXT` should be true — set in gateway `env.shellEnv`. "  # AINL-OPENFANG-TOP5
            + INIT_INSTALL_OPENFANG  # AINL-OPENFANG-TOP5
        )  # AINL-OPENFANG-TOP5
    if "not set" in low and ("env" in low or "environment" in low or "missing" in low or "required" in low):  # AINL-OPENFANG-TOP5
        if "openfang" in low or "ainl_memory" in low or "monitor_cache" in low:  # AINL-OPENFANG-TOP5
            return "Required OpenFang env var missing — " + INIT_INSTALL_OPENFANG + " Or set paths manually."  # AINL-OPENFANG-TOP5
        return "Required environment variable missing — " + INIT_INSTALL_OPENFANG  # AINL-OPENFANG-TOP5
    if "workspace" in low and ("mismatch" in low or "wrong" in low):  # AINL-OPENFANG-TOP5
        return "Workspace path mismatch — confirm `OPENFANG_WORKSPACE` / `AINL_MEMORY_DB`; " + INIT_INSTALL_OPENFANG  # AINL-OPENFANG-TOP5
    return msg  # AINL-OPENFANG-TOP5
