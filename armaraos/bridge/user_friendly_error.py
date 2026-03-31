from __future__ import annotations  # AINL-ARMARAOS-TOP5

# AINL-ARMARAOS-TOP5 — single-line hint aligned with docs/QUICKSTART_ARMARAOS.md pitfalls  # AINL-ARMARAOS-TOP5
INIT_INSTALL_ARMARAOS = "Run `ainl install armaraos` to initialize."  # AINL-ARMARAOS-TOP5


def user_friendly_ainl_error(e: BaseException) -> str:  # AINL-ARMARAOS-TOP5
    msg = str(e)  # AINL-ARMARAOS-TOP5
    low = msg.lower()  # AINL-ARMARAOS-TOP5
    # Table / SQLite  # AINL-ARMARAOS-TOP5
    if "no such table" in low or "table not found" in low:  # AINL-ARMARAOS-TOP5
        if "weekly_remaining_v1" in low:  # AINL-ARMARAOS-TOP5
            return "`weekly_remaining_v1` missing — " + INIT_INSTALL_ARMARAOS  # AINL-ARMARAOS-TOP5
        if "intelligencereport" in low:  # AINL-ARMARAOS-TOP5
            return "IntelligenceReport is not used by OpenFang install (reports are Markdown). " + INIT_INSTALL_ARMARAOS  # AINL-ARMARAOS-TOP5
        return "SQLite table missing — " + INIT_INSTALL_ARMARAOS  # AINL-ARMARAOS-TOP5
    # Cron — match gold-standard job names in message  # AINL-ARMARAOS-TOP5
    if ("cron" in low or "job" in low) and "not found" in low:  # AINL-ARMARAOS-TOP5
        if "weekly token trends" in low or "ainl weekly token trends" in low:  # AINL-ARMARAOS-TOP5
            return "Cron job 'AINL Weekly Token Trends' not found — " + INIT_INSTALL_ARMARAOS  # AINL-ARMARAOS-TOP5
        if "context injection" in low:  # AINL-ARMARAOS-TOP5
            return "Cron job 'AINL Context Injection' not found — " + INIT_INSTALL_ARMARAOS  # AINL-ARMARAOS-TOP5
        if "session summarizer" in low:  # AINL-ARMARAOS-TOP5
            return "Cron job 'AINL Session Summarizer' not found — " + INIT_INSTALL_ARMARAOS  # AINL-ARMARAOS-TOP5
        return "Cron job not found — " + INIT_INSTALL_ARMARAOS  # AINL-ARMARAOS-TOP5
    # RPC / bridge / gateway down  # AINL-ARMARAOS-TOP5
    if "rpcwireerror" in low or "rpc wire" in low:  # AINL-ARMARAOS-TOP5
        return "RPCWireError from host RPC. Ensure the OpenFang gateway is running, then retry (or run `ainl doctor --ainl`)."  # AINL-ARMARAOS-TOP5
    if "econnrefused" in low or "connection refused" in low:  # AINL-ARMARAOS-TOP5
        return "Connection refused — OpenFang gateway may be down. Start or restart it (`armaraos gateway restart`), then retry."  # AINL-ARMARAOS-TOP5
    # Env — bootstrap preference  # AINL-ARMARAOS-TOP5
    if "armaraos_bootstrap_prefer_session_context" in low or (  # AINL-ARMARAOS-TOP5
        "armaraos_bootstrap" in low and "prefer" in low  # AINL-ARMARAOS-TOP5
    ):  # AINL-ARMARAOS-TOP5
        return (  # AINL-ARMARAOS-TOP5
            "`ARMARAOS_BOOTSTRAP_PREFER_SESSION_CONTEXT` should be true — set in gateway `env.shellEnv`. "  # AINL-ARMARAOS-TOP5
            + INIT_INSTALL_ARMARAOS  # AINL-ARMARAOS-TOP5
        )  # AINL-ARMARAOS-TOP5
    if "not set" in low and ("env" in low or "environment" in low or "missing" in low or "required" in low):  # AINL-ARMARAOS-TOP5
        if "armaraos" in low or "ainl_memory" in low or "monitor_cache" in low:  # AINL-ARMARAOS-TOP5
            return "Required OpenFang env var missing — " + INIT_INSTALL_ARMARAOS + " Or set paths manually."  # AINL-ARMARAOS-TOP5
        return "Required environment variable missing — " + INIT_INSTALL_ARMARAOS  # AINL-ARMARAOS-TOP5
    if "workspace" in low and ("mismatch" in low or "wrong" in low):  # AINL-ARMARAOS-TOP5
        return "Workspace path mismatch — confirm `ARMARAOS_WORKSPACE` / `AINL_MEMORY_DB`; " + INIT_INSTALL_ARMARAOS  # AINL-ARMARAOS-TOP5
    return msg  # AINL-ARMARAOS-TOP5
