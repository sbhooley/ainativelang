# Cron orchestration: OpenClaw, AINL, and system schedulers

When the same work can be triggered from **OpenClaw cron**, **AINL `S core cron`**, and **OS-level cron / launchd / systemd**, you need a small **governance layer** so agents and humans know what is authoritative, what is documentation-only, and when things have drifted.

The model is **portable**: it applies to **any** OpenClaw install and **any** repository that ships a JSON registry and (optionally) AINL sources. Nothing here assumes a particular username, disk path, or job title.

This repo ships **three coordinated artifacts** (no automatic writes to OpenClaw or crontab):

1. **A cron registry JSON file** — default `tooling/cron_registry.json`; override with **`CRON_REGISTRY_PATH`**.
2. **`scripts/cron_drift_check.py`** — read-only report: registry vs AINL schedule modules vs `openclaw cron list --json`.
3. **AINL sources** (optional for your project) — e.g. `modules/openclaw/cron_*.ainl` + `adapters/openclaw_defaults.py`.

---

## Any OpenClaw deployment

- **OpenClaw’s contract** is the CLI JSON: `openclaw cron list --json` → `jobs[]` with `name`, `schedule.expr`, `payload.message` (or similar text fields). That shape is the same for every user; only the **content** of names and payloads differs.
- **Your fingerprints** are **yours**: each registry row’s `openclaw_match.payload_contains` should be a **stable substring** copied from **your** scheduled job payload (or from a convention your team agrees on). Do not rely on someone else’s directory layout or script names unless you adopt them on purpose.
- **Other repos / forks**: copy the pattern, not necessarily this file’s `jobs` list. Point `CRON_REGISTRY_PATH` at your registry, or maintain `tooling/cron_registry.json` in your tree.
- **`OPENCLAW_BIN`**: optional. If unset, the drift script uses **`shutil.which("openclaw")`** so any PATH-based install works. No baked-in home-directory paths.
- **Untracked-job heuristic** is **opt-in**: controlled by `meta.untracked_payload_substrings` in the registry and/or **`CRON_DRIFT_UNTRACKED_SUBSTRINGS`** (comma-separated). If both are absent/empty, **no** “untracked OpenClaw job” warnings are emitted — safe for unrelated OpenClaw users who only run the script against a minimal registry. This repo lists a few substrings so maintainers can spot extra wrapper/intelligence jobs; **remove or replace** them for your deployment.

---

## Lanes: who does what

| Lane | Responsibility |
|------|----------------|
| **OpenClaw (execution)** | When `execution_owner` is `openclaw`, the clock that matters lives in the OpenClaw cron store. Agents should create/update/disable jobs here (CLI or UI), not duplicate the same runner in crontab. |
| **System (execution)** | When `execution_owner` is `system`, launchd/crontab/systemd owns the schedule. OpenClaw and AINL should not also fire the same command without an explicit handoff in the registry. |
| **AINL (declaration)** | `S core cron` in `.ainl` (often via `include`) is primarily **declarative**: IR / emit / documentation / drift detection. It is **not** a second execution engine unless you deliberately run an emitted cron target. |

**Golden rule:** For each logical `id` in the registry, pick **one** execution owner. Everything else is mirror or documentation.

---

## What AI agents should do

1. **Before adding a schedule**, read the **effective** registry (`CRON_REGISTRY_PATH` or default) and inspect OpenClaw (`openclaw cron list --json`) for an existing job that already runs the same command.
2. **Run drift checks** after edits:

   ```bash
   cd /path/to/your/checkout
   python3 scripts/cron_drift_check.py
   python3 scripts/cron_drift_check.py --json
   ```

3. **Strict CI / gating** (fail on compile errors or schedule mismatches):

   ```bash
   CRON_DRIFT_STRICT=1 python3 scripts/cron_drift_check.py
   ```

   Set per-job `"openclaw_required": true` when a job **must** exist in OpenClaw (missing job is then `severity: error`). Default is `false` so fresh clones without those jobs do not fail.

   Optional: fail when heuristic “untracked” jobs appear:

   ```bash
   CRON_DRIFT_FAIL_ON_UNTRACKED=1 python3 scripts/cron_drift_check.py
   ```

4. **Migration (system → OpenClaw)**  
   - Disable the system timer / crontab line.  
   - Add an OpenClaw job whose payload runs the same command (document in `runner_hint`).  
   - Add or update a registry row with `execution_owner: "openclaw"` and `openclaw_match.payload_contains` set to a **stable substring** of that payload.  
   - Run `cron_drift_check.py`.

5. **Migration (duplicate OpenClaw jobs)**  
   - Pick one job to keep; disable or delete the duplicate.  
   - Ensure a single registry row points at the surviving job (via `payload_contains`).

6. **Untracked OpenClaw jobs** — Only if you enabled substrings (registry meta or env). Then either **add a registry row** for each real job or **narrow/remove** substrings so harmless jobs are not flagged.

---

## What AINL (this repo) handles

- Schedule text in `modules/openclaw/cron_*.ainl`, programs under `scripts/wrappers/`, and `adapters/openclaw_defaults.py` (`CRON_*`) for tooling alignment.

When you change a wrapper schedule here:

1. Edit `modules/openclaw/cron_<name>.ainl`.
2. Update `adapters/openclaw_defaults.py` (`CRON_*`).
3. Update the registry `schedule_cron`.
4. Update the OpenClaw job expression (or system timer) to match.
5. Run `python3 scripts/cron_drift_check.py`.

---

## Limitations (by design)

- **No auto-sync** into OpenClaw or `/etc/crontab` — avoids surprise mutations; agents produce diffs and human-approved CLI steps.
- **System cron** is not parsed yet; extend `cron_drift_check.py` if you want `crontab -l` correlation.
- **AINL IR `crons`** may be empty when `S core cron` lives only in an **included** file; the drift script reads `schedule_module` text for the expression.

---

## Related docs

- [`docs/ainl_openclaw_unified_integration.md`](ainl_openclaw_unified_integration.md) — wrapper runners, ports, example OpenClaw `cron add` commands.
- [`tooling/cron_registry.json`](../tooling/cron_registry.json) — default registry for this repo (replace or override path for other deployments).
