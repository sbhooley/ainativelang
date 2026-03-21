"""
Single source for OpenClaw/AINL integration defaults.

Uses a high, non-well-known listen port for CRM HTTP defaults so wrappers and
adapters do not assume :3000 / :8080 / :5000. Override with CRM_API_BASE (and
frame key crm_health_url from run_wrapper_ainl) to match your real deployment.
"""

DEFAULT_CRM_HTTP_PORT = 27847

DEFAULT_CRM_API_BASE = f"http://127.0.0.1:{DEFAULT_CRM_HTTP_PORT}"

DEFAULT_CRM_HEALTH_URL = f"{DEFAULT_CRM_API_BASE}/api/health"

# Keep in sync with modules/openclaw/cron_*.ainl
CRON_SUPERVISOR = "*/15 * * * *"
CRON_CONTENT_ENGINE = "*/30 * * * *"
CRON_GITHUB_INTELLIGENCE = "15 */6 * * *"
