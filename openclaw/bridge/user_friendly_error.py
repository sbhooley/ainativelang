from __future__ import annotations  # AINL-OPENCLAW-TOP5

# AINL-OPENCLAW-TOP5 — single-line hint aligned with docs/QUICKSTART_OPENCLAW.md pitfalls  # AINL-OPENCLAW-TOP5
INIT_INSTALL_OPENCLAW = "Run `ainl install openclaw` to initialize."  # AINL-OPENCLAW-TOP5


def user_friendly_ainl_error(e: BaseException) -> str:  # AINL-OPENCLAW-TOP5
    msg = str(e)  # AINL-OPENCLAW-TOP5
    low = msg.lower()  # AINL-OPENCLAW-TOP5
    # Table / SQLite  # AINL-OPENCLAW-TOP5
    if "no such table" in low or "table not found" in low:  # AINL-OPENCLAW-TOP5
        if "weekly_remaining_v1" in low:  # AINL-OPENCLAW-TOP5
            return "`weekly_remaining_v1` missing — " + INIT_INSTALL_OPENCLAW  # AINL-OPENCLAW-TOP5
        if "intelligencereport" in low:  # AINL-OPENCLAW-TOP5
            return "IntelligenceReport is not used by OpenClaw install (reports are Markdown). " + INIT_INSTALL_OPENCLAW  # AINL-OPENCLAW-TOP5
        return "SQLite table missing — " + INIT_INSTALL_OPENCLAW  # AINL-OPENCLAW-TOP5
    # Cron — match gold-standard job names in message  # AINL-OPENCLAW-TOP5
    if ("cron" in low or "job" in low) and "not found" in low:  # AINL-OPENCLAW-TOP5
        if "weekly token trends" in low or "ainl weekly token trends" in low:  # AINL-OPENCLAW-TOP5
            return "Cron job 'AINL Weekly Token Trends' not found — " + INIT_INSTALL_OPENCLAW  # AINL-OPENCLAW-TOP5
        if "context injection" in low:  # AINL-OPENCLAW-TOP5
            return "Cron job 'AINL Context Injection' not found — " + INIT_INSTALL_OPENCLAW  # AINL-OPENCLAW-TOP5
        if "session summarizer" in low:  # AINL-OPENCLAW-TOP5
            return "Cron job 'AINL Session Summarizer' not found — " + INIT_INSTALL_OPENCLAW  # AINL-OPENCLAW-TOP5
        return "Cron job not found — " + INIT_INSTALL_OPENCLAW  # AINL-OPENCLAW-TOP5
    # RPC / bridge / gateway down  # AINL-OPENCLAW-TOP5
    if "rpcwireerror" in low or "rpc wire" in low:  # AINL-OPENCLAW-TOP5
        return "RPCWireError from host RPC. Ensure the OpenClaw gateway is running, then retry (or run `ainl doctor --ainl`)."  # AINL-OPENCLAW-TOP5
    if "econnrefused" in low or "connection refused" in low:  # AINL-OPENCLAW-TOP5
        return "Connection refused — OpenClaw gateway may be down. Start or restart it (`openclaw gateway restart`), then retry."  # AINL-OPENCLAW-TOP5
    # Env — bootstrap preference  # AINL-OPENCLAW-TOP5
    if "openclaw_bootstrap_prefer_session_context" in low or (  # AINL-OPENCLAW-TOP5
        "openclaw_bootstrap" in low and "prefer" in low  # AINL-OPENCLAW-TOP5
    ):  # AINL-OPENCLAW-TOP5
        return (  # AINL-OPENCLAW-TOP5
            "`OPENCLAW_BOOTSTRAP_PREFER_SESSION_CONTEXT` should be true — set in gateway `env.shellEnv`. "  # AINL-OPENCLAW-TOP5
            + INIT_INSTALL_OPENCLAW  # AINL-OPENCLAW-TOP5
        )  # AINL-OPENCLAW-TOP5
    if "not set" in low and ("env" in low or "environment" in low or "missing" in low or "required" in low):  # AINL-OPENCLAW-TOP5
        if "openclaw" in low or "ainl_memory" in low or "monitor_cache" in low:  # AINL-OPENCLAW-TOP5
            return "Required OpenClaw env var missing — " + INIT_INSTALL_OPENCLAW + " Or set paths manually."  # AINL-OPENCLAW-TOP5
        return "Required environment variable missing — " + INIT_INSTALL_OPENCLAW  # AINL-OPENCLAW-TOP5
    if "workspace" in low and ("mismatch" in low or "wrong" in low):  # AINL-OPENCLAW-TOP5
        return "Workspace path mismatch — confirm `OPENCLAW_WORKSPACE` / `AINL_MEMORY_DB`; " + INIT_INSTALL_OPENCLAW  # AINL-OPENCLAW-TOP5
    return msg  # AINL-OPENCLAW-TOP5
