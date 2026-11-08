# ExtrasAdapter for AINL monitor
# Provides utility checks: file_exists, docker_image_exists, http_status, newest_backup_mtime

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, List

from runtime.adapters.base import RuntimeAdapter, AdapterError

class ExtrasAdapter(RuntimeAdapter):
    def call(self, target: str, args: List[Any], context: dict) -> Any:
        if target == 'file_exists':
            if len(args) < 1:
                raise AdapterError('file_exists requires path')
            path = args[0]
            return 1 if os.path.exists(path) and os.access(path, os.X_OK) else 0
        elif target == 'docker_image_exists':
            if len(args) < 1:
                raise AdapterError('docker_image_exists requires image name')
            image = args[0]
            try:
                out = subprocess.check_output(['docker', 'images', '-q', image], text=True, timeout=5)
                return 1 if out.strip() else 0
            except (subprocess.CalledProcessError, FileNotFoundError):
                return 0
        elif target == 'http_status':
            if len(args) < 1:
                raise AdapterError('http_status requires url')
            url = str(args[0])
            hosts = [
                part.strip()
                for part in str(os.environ.get("AINL_EXTRAS_HTTP_ALLOW_HOSTS") or "").split(",")
                if part.strip()
            ]
            from runtime.adapters.http import SimpleHttpAdapter
            from runtime.net_guard import AddressRejected, require_allowed_public_url

            try:
                require_allowed_public_url(url, allow_hosts=hosts, https_only=True)
            except AddressRejected as exc:
                raise AdapterError("extras http_status host blocked by allowlist") from exc
            client = SimpleHttpAdapter(
                allow_hosts=hosts,
                https_only=True,
                status_as_value=True,
                block_private=True,
                check_redirects=True,
            )
            envelope = client.call("GET", [url], {})
            if isinstance(envelope, dict):
                return int(envelope.get("status_code") or envelope.get("status") or 0)
            return 0
        elif target == 'newest_backup_mtime':
            if len(args) < 1:
                raise AdapterError('newest_backup_mtime requires backup directory')
            backup_dir = args[0]
            try:
                files = []
                for fname in os.listdir(backup_dir):
                    if fname.endswith('.bak'):
                        path = os.path.join(backup_dir, fname)
                        mtime = os.path.getmtime(path)
                        files.append((mtime, path))
                if not files:
                    return 0
                newest = max(files, key=lambda x: x[0])[0]
                return int(newest)
            except Exception:
                return 0
        elif target == 'metrics':
            if len(args) < 1:
                raise AdapterError('metrics requires summary_path')
            raw_path = str(args[0])
            # Sandbox: restrict summaries to a configurable root, defaulting to /tmp/ainl_summaries.
            root = Path(os.getenv("AINL_SUMMARY_ROOT", "/tmp/ainl_summaries")).resolve()
            summary_path = (root / raw_path).resolve()
            if summary_path != root and root not in summary_path.parents:
                raise AdapterError("metrics summary_path escapes AINL_SUMMARY_ROOT sandbox")
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                raise AdapterError(f'metrics failed to read {summary_path!r}: {e}') from e

            if not isinstance(data, dict):
                raise AdapterError('metrics expects JSON object summary')

            run_count = int(data.get("run_count", 0) or 0)
            ok_count = int(data.get("ok_count", 0) or 0)
            error_count = int(data.get("error_count", 0) or 0)
            ok_ratio = ok_count / run_count if run_count > 0 else None

            runtime_versions = data.get("runtime_versions") or []
            if not isinstance(runtime_versions, list):
                runtime_versions = []

            result = {
                "run_count": run_count,
                "ok_count": ok_count,
                "error_count": error_count,
                "ok_ratio": ok_ratio,
                "runtime_versions": runtime_versions,
                "result_kinds": data.get("result_kinds") or {},
                "trace_op_counts": data.get("trace_op_counts") or {},
                "label_counts": data.get("label_counts") or {},
                "timestamps_present": bool(data.get("timestamps_present")),
            }
            return result
        else:
            raise AdapterError(f'extras unknown target: {target}')

# Register factory (the registry will call this)
def get_adapter():
    return ExtrasAdapter()
