from __future__ import annotations

import os
import time
import inspect
import asyncio
import contextlib
import json
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

from adapters.postgres import PostgresAdapter
from runtime.adapters.base import AdapterError, RuntimeAdapter


class SupabaseAdapter(RuntimeAdapter):
    """
    Supabase convenience wrapper.

    DB/table verbs delegate to PostgresAdapter where possible.
    Auth/storage/realtime verbs use Supabase REST endpoints.
    """

    _DB_VERBS = {"from", "query", "select", "insert", "update", "upsert", "delete", "rpc"}
    _AUTH_VERBS = {
        "auth_sign_up",
        "auth_sign_in_with_password",
        "auth_sign_out",
        "auth_get_user",
        "auth_reset_password_for_email",
    }
    _STORAGE_VERBS = {
        "storage_upload",
        "storage_download",
        "storage_list",
        "storage_remove",
        "storage_get_public_url",
    }
    _REALTIME_VERBS = {
        "realtime_subscribe",
        "realtime_unsubscribe",
        "realtime_broadcast",
        "realtime_replay",
        "realtime_get_cursor",
        "realtime_ack",
    }
    _ALL_VERBS = _DB_VERBS | _AUTH_VERBS | _STORAGE_VERBS | _REALTIME_VERBS

    def __init__(
        self,
        *,
        db_url: Optional[str] = None,
        supabase_url: Optional[str] = None,
        anon_key: Optional[str] = None,
        service_role_key: Optional[str] = None,
        timeout_s: float = 8.0,
        allow_write: bool = False,
        allow_tables: Optional[Iterable[str]] = None,
        allow_buckets: Optional[Iterable[str]] = None,
        allow_channels: Optional[Iterable[str]] = None,
    ):
        self.db_url = (db_url or os.environ.get("AINL_SUPABASE_DB_URL") or os.environ.get("AINL_POSTGRES_URL") or "").strip() or None
        self.supabase_url = (supabase_url or os.environ.get("AINL_SUPABASE_URL") or "").strip().rstrip("/")
        self.anon_key = (anon_key or os.environ.get("AINL_SUPABASE_ANON_KEY") or "").strip() or None
        self.service_role_key = (service_role_key or os.environ.get("AINL_SUPABASE_SERVICE_ROLE_KEY") or "").strip() or None
        self.timeout_s = float(timeout_s)
        self.allow_write = bool(allow_write)
        self.allow_tables = {str(t).strip() for t in (allow_tables or []) if str(t).strip()}
        self.allow_buckets = {str(b).strip() for b in (allow_buckets or []) if str(b).strip()}
        self.allow_channels = {str(c).strip() for c in (allow_channels or []) if str(c).strip()}
        self._httpx: Any = None
        self._http: Any = None
        self._http_async: Any = None
        self._websockets: Any = None
        self._postgres: Optional[PostgresAdapter] = None
        self._channels: Dict[str, Dict[str, Any]] = {}
        self._realtime_history: Dict[str, List[Dict[str, Any]]] = {}
        self._realtime_cursors: Dict[str, Dict[str, Any]] = {}
        self._realtime_groups: Dict[str, Dict[str, Any]] = {}
        self._realtime_ref = 1
        self._init_clients()

    def _init_clients(self) -> None:
        try:
            import httpx
        except Exception as e:  # pragma: no cover
            raise AdapterError("supabase adapter requires httpx. Install with: pip install 'httpx>=0.27.0'") from e
        self._httpx = httpx
        self._http = httpx.Client(timeout=self.timeout_s)
        async_ctor = getattr(httpx, "AsyncClient", None)
        self._http_async = async_ctor(timeout=self.timeout_s) if callable(async_ctor) else self._http
        # Lazily required for non-db verbs; db verbs require postgres url.
        if self.db_url:
            self._postgres = PostgresAdapter(dsn=self.db_url, allow_write=self.allow_write, allow_tables=self.allow_tables)
        try:
            import websockets  # type: ignore

            self._websockets = websockets
        except Exception:
            self._websockets = None

    def _require_postgres(self) -> PostgresAdapter:
        if self._postgres is None:
            raise AdapterError("supabase db operations require AINL_SUPABASE_DB_URL or AINL_POSTGRES_URL")
        return self._postgres

    def _require_supabase_http(self) -> None:
        if not self.supabase_url:
            raise AdapterError("supabase url is required for auth/storage/realtime operations (AINL_SUPABASE_URL)")
        if not (self.service_role_key or self.anon_key):
            raise AdapterError("supabase api key missing (set AINL_SUPABASE_SERVICE_ROLE_KEY or AINL_SUPABASE_ANON_KEY)")

    def _auth_headers(self, *, use_service: bool = False, bearer: Optional[str] = None) -> Dict[str, str]:
        key = self.service_role_key if use_service and self.service_role_key else (self.service_role_key or self.anon_key or "")
        headers = {"apikey": key}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        else:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _check_write(self, verb: str) -> None:
        if verb in {"insert", "update", "upsert", "delete", "auth_sign_out", "storage_upload", "storage_remove", "realtime_broadcast", "realtime_ack"} and not self.allow_write:
            raise AdapterError("supabase write blocked: allow_write is false")

    def _check_table_allowed(self, table: str) -> None:
        if self.allow_tables and table not in self.allow_tables:
            raise AdapterError(f"supabase table blocked by allowlist: {table}")

    def _check_bucket_allowed(self, bucket: str) -> None:
        if self.allow_buckets and bucket not in self.allow_buckets:
            raise AdapterError(f"supabase bucket blocked by allowlist: {bucket}")

    def _check_channel_allowed(self, channel: str) -> None:
        if self.allow_channels and channel not in self.allow_channels:
            raise AdapterError(f"supabase channel blocked by allowlist: {channel}")

    def _next_ref(self) -> str:
        self._realtime_ref += 1
        return str(self._realtime_ref)

    def _realtime_ws_url(self) -> str:
        self._require_supabase_http()
        if self.supabase_url.startswith("https://"):
            base = "wss://" + self.supabase_url[len("https://") :]
        elif self.supabase_url.startswith("http://"):
            base = "ws://" + self.supabase_url[len("http://") :]
        else:
            raise AdapterError("supabase url must start with http:// or https://")
        key = self.service_role_key or self.anon_key or ""
        return f"{base}/realtime/v1/websocket?apikey={quote(key)}&vsn=1.0.0"

    def _normalize_rt_event(self, payload: Dict[str, Any], fallback_table: Optional[str] = None) -> Dict[str, Any]:
        data = payload.get("data") if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            data = {}
        event = str(data.get("type") or payload.get("eventType") or payload.get("event") or "MESSAGE").upper()
        record = data.get("record")
        old_record = data.get("old_record")
        schema = str(data.get("schema") or "public")
        table = str(data.get("table") or fallback_table or "")
        seq = data.get("commit_timestamp") or data.get("commit_ts") or data.get("sequence") or payload.get("ref")
        ts = data.get("commit_timestamp") or payload.get("timestamp")
        return {
            "event": event,
            "schema": schema,
            "table": table,
            "record": record if isinstance(record, dict) else record,
            "old_record": old_record if isinstance(old_record, dict) else old_record,
            "sequence": str(seq) if seq is not None else None,
            "timestamp": str(ts) if ts is not None else None,
            "raw": payload,
        }

    def _cursor_key(self, channel: str, group: str, consumer: str) -> str:
        return f"{channel}::{group}::{consumer}"

    def _history_slice(self, channel: str, replay_from: Any, max_events: int) -> List[Dict[str, Any]]:
        hist = list(self._realtime_history.get(channel) or [])
        if not hist:
            return []
        if replay_from in (None, "", "latest"):
            return hist[-max_events:]
        if replay_from == "earliest":
            return hist[:max_events]
        rf = str(replay_from)
        out = [e for e in hist if str(e.get("sequence") or "") >= rf or str(e.get("timestamp") or "") >= rf]
        return out[:max_events]

    async def _realtime_loop(self, channel: str) -> None:
        ch = self._channels.get(channel)
        if not ch:
            return
        queue = ch["queue"]
        table = ch.get("table")
        event_types = ch.get("event_types") or ["*"]
        flt = ch.get("filter")
        ws = None
        hb_task = None
        try:
            if self._websockets is None:
                await queue.put({"event": "ERROR", "schema": "public", "table": table or "", "record": None, "old_record": None, "raw": {"message": "websockets dependency not installed"}})
                return
            ws = await self._websockets.connect(self._realtime_ws_url())
            ch["ws"] = ws
            join_payload = {
                "config": {
                    "broadcast": {"self": True},
                    "presence": {"key": ""},
                    "postgres_changes": [
                        {
                            "event": et,
                            "schema": "public",
                            "table": table,
                            **({"filter": flt} if flt else {}),
                        }
                        for et in event_types
                    ],
                }
            }
            await ws.send(
                json.dumps(
                    {
                        "topic": f"realtime:{channel}",
                        "event": "phx_join",
                        "payload": join_payload,
                        "ref": self._next_ref(),
                    }
                )
            )

            async def _heartbeat():
                while True:
                    await asyncio.sleep(25.0)
                    if ws is None:
                        return
                    await ws.send(json.dumps({"topic": "phoenix", "event": "heartbeat", "payload": {}, "ref": self._next_ref()}))

            hb_task = asyncio.create_task(_heartbeat())
            while True:
                raw = await ws.recv()
                msg = json.loads(raw) if isinstance(raw, str) else {}
                event = str(msg.get("event") or "")
                payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
                if event in {"postgres_changes", "broadcast", "system"}:
                    norm = self._normalize_rt_event(payload, fallback_table=table)
                    self._realtime_history.setdefault(channel, []).append(norm)
                    if len(self._realtime_history[channel]) > 500:
                        self._realtime_history[channel] = self._realtime_history[channel][-500:]
                    await queue.put(norm)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            with contextlib.suppress(Exception):
                await queue.put({"event": "ERROR", "schema": "public", "table": table or "", "record": None, "old_record": None, "raw": {"message": str(e)}})
        finally:
            if hb_task is not None:
                hb_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await hb_task
            if ws is not None:
                with contextlib.suppress(Exception):
                    await ws.close()

    def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json_body: Any = None, headers: Optional[Dict[str, str]] = None) -> Any:
        self._require_supabase_http()
        url = f"{self.supabase_url}{path}"
        req_headers = dict(headers or {})
        max_attempts = 3
        for i in range(max_attempts):
            try:
                resp = self._http.request(method, url, params=params, json=json_body, headers=req_headers)
                if resp.status_code in {429, 500, 502, 503, 504} and i < max_attempts - 1:
                    time.sleep(0.2 * (2**i))
                    continue
                if resp.status_code >= 400:
                    return {"ok": False, "error": {"status": resp.status_code, "message": resp.text}, "data": None}
                data = resp.json() if resp.content else None
                return {"ok": True, "data": data, "error": None}
            except Exception as e:
                if i < max_attempts - 1:
                    time.sleep(0.2 * (2**i))
                    continue
                return {"ok": False, "error": {"status": None, "message": str(e)}, "data": None}

    def _db_select(self, table: str, where: Optional[Dict[str, Any]] = None, columns: Optional[List[str]] = None) -> Any:
        self._check_table_allowed(table)
        cols = ", ".join(columns) if columns else "*"
        sql = f"SELECT {cols} FROM {table}"
        params: List[Any] = []
        if where:
            parts = []
            for k, v in where.items():
                parts.append(f"{k} = %s")
                params.append(v)
            sql += " WHERE " + " AND ".join(parts)
        return self._require_postgres().call("query", [sql, params], {})

    def _db_insert(self, table: str, payload: Dict[str, Any]) -> Any:
        self._check_table_allowed(table)
        keys = list(payload.keys())
        vals = [payload[k] for k in keys]
        cols = ", ".join(keys)
        placeholders = ", ".join(["%s"] * len(keys))
        sql = f"INSERT INTO {table}({cols}) VALUES ({placeholders})"
        return self._require_postgres().call("execute", [sql, vals], {})

    def _db_update(self, table: str, fields: Dict[str, Any], where: Dict[str, Any]) -> Any:
        self._check_table_allowed(table)
        set_keys = list(fields.keys())
        where_keys = list(where.keys())
        set_clause = ", ".join([f"{k} = %s" for k in set_keys])
        where_clause = " AND ".join([f"{k} = %s" for k in where_keys])
        params = [fields[k] for k in set_keys] + [where[k] for k in where_keys]
        sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        return self._require_postgres().call("execute", [sql, params], {})

    def _db_delete(self, table: str, where: Dict[str, Any]) -> Any:
        self._check_table_allowed(table)
        where_keys = list(where.keys())
        where_clause = " AND ".join([f"{k} = %s" for k in where_keys])
        params = [where[k] for k in where_keys]
        sql = f"DELETE FROM {table} WHERE {where_clause}"
        return self._require_postgres().call("execute", [sql, params], {})

    async def _request_async(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        self._require_supabase_http()
        url = f"{self.supabase_url}{path}"
        req_headers = dict(headers or {})
        max_attempts = 3
        for i in range(max_attempts):
            try:
                maybe = self._http_async.request(method, url, params=params, json=json_body, headers=req_headers)
                resp = await maybe if inspect.isawaitable(maybe) else maybe
                if resp.status_code in {429, 500, 502, 503, 504} and i < max_attempts - 1:
                    time.sleep(0.2 * (2**i))
                    continue
                if resp.status_code >= 400:
                    return {"ok": False, "error": {"status": resp.status_code, "message": resp.text}, "data": None}
                data = resp.json() if resp.content else None
                return {"ok": True, "data": data, "error": None}
            except Exception as e:
                if i < max_attempts - 1:
                    time.sleep(0.2 * (2**i))
                    continue
                return {"ok": False, "error": {"status": None, "message": str(e)}, "data": None}

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower().replace(".", "_")
        if verb not in self._ALL_VERBS:
            raise AdapterError(f"unsupported supabase target: {target}")
        self._check_write(verb)

        # DB wrapper section (delegates to Postgres).
        if verb == "from":
            if not args:
                raise AdapterError("supabase from requires table argument")
            table = str(args[0])
            self._check_table_allowed(table)
            return {"ok": True, "table": table}
        if verb in {"query", "select"}:
            if not args:
                raise AdapterError("supabase select/query requires table argument")
            table = str(args[0])
            where = args[1] if len(args) > 1 and isinstance(args[1], dict) else None
            columns = args[2] if len(args) > 2 and isinstance(args[2], list) else None
            data = self._db_select(table, where=where, columns=columns)
            return {"data": data, "error": None}
        if verb == "insert":
            if len(args) < 2 or not isinstance(args[1], dict):
                raise AdapterError("supabase insert requires table and payload object")
            out = self._db_insert(str(args[0]), args[1])
            return {"data": out, "error": None}
        if verb == "update":
            if len(args) < 3 or not isinstance(args[1], dict) or not isinstance(args[2], dict):
                raise AdapterError("supabase update requires table, fields object, and where object")
            out = self._db_update(str(args[0]), args[1], args[2])
            return {"data": out, "error": None}
        if verb == "upsert":
            if len(args) < 3 or not isinstance(args[1], dict) or not isinstance(args[2], dict):
                raise AdapterError("supabase upsert requires table, payload object, and key fields object")
            table = str(args[0])
            payload = dict(args[1])
            key_fields = dict(args[2])
            found = self._db_select(table, where=key_fields, columns=list(key_fields.keys()))
            if found:
                fields = {k: v for k, v in payload.items() if k not in key_fields}
                out = self._db_update(table, fields, key_fields) if fields else {"rows_affected": 0, "lastrowid": None}
                return {"ok": True, "action": "updated", "data": out, "error": None}
            out = self._db_insert(table, payload)
            return {"ok": True, "action": "inserted", "data": out, "error": None}
        if verb == "delete":
            if len(args) < 2 or not isinstance(args[1], dict):
                raise AdapterError("supabase delete requires table and where object")
            out = self._db_delete(str(args[0]), args[1])
            return {"data": out, "error": None}
        if verb == "rpc":
            if not args:
                raise AdapterError("supabase rpc requires function name")
            fn = str(args[0])
            fn_args = args[1] if len(args) > 1 else {}
            if fn_args is None:
                fn_args = {}
            if not isinstance(fn_args, dict):
                raise AdapterError("supabase rpc args must be object")
            keys = list(fn_args.keys())
            placeholders = ", ".join([f"{k} => %s" for k in keys])
            sql = f"SELECT * FROM {fn}({placeholders})" if placeholders else f"SELECT * FROM {fn}()"
            params = [fn_args[k] for k in keys]
            rows = self._require_postgres().call("query", [sql, params], {})
            return {"data": rows, "error": None}

        # Auth section.
        if verb == "auth_sign_up":
            if len(args) < 2:
                raise AdapterError("supabase auth.sign_up requires email and password")
            body = {"email": str(args[0]), "password": str(args[1])}
            return self._request("POST", "/auth/v1/signup", json_body=body, headers=self._auth_headers())
        if verb == "auth_sign_in_with_password":
            if len(args) < 2:
                raise AdapterError("supabase auth.sign_in_with_password requires email and password")
            body = {"email": str(args[0]), "password": str(args[1])}
            return self._request("POST", "/auth/v1/token", params={"grant_type": "password"}, json_body=body, headers=self._auth_headers())
        if verb == "auth_sign_out":
            access_token = str(args[0]) if args else ""
            return self._request("POST", "/auth/v1/logout", headers=self._auth_headers(bearer=access_token or None))
        if verb == "auth_get_user":
            access_token = str(args[0]) if args else ""
            return self._request("GET", "/auth/v1/user", headers=self._auth_headers(bearer=access_token or None))
        if verb == "auth_reset_password_for_email":
            if not args:
                raise AdapterError("supabase auth.reset_password_for_email requires email")
            body = {"email": str(args[0])}
            return self._request("POST", "/auth/v1/recover", json_body=body, headers=self._auth_headers())

        # Storage section.
        if len(args) < 1:
            raise AdapterError(f"supabase {verb} requires bucket argument")
        bucket = str(args[0])
        if verb.startswith("storage_"):
            self._check_bucket_allowed(bucket)
        if verb == "storage_upload":
            if len(args) < 3:
                raise AdapterError("supabase storage.upload requires bucket, path, content")
            path = str(args[1]).lstrip("/")
            content = args[2]
            if isinstance(content, str):
                content = content.encode("utf-8")
            if not isinstance(content, (bytes, bytearray)):
                raise AdapterError("supabase storage.upload content must be bytes or string")
            self._require_supabase_http()
            url = f"{self.supabase_url}/storage/v1/object/{quote(bucket, safe='')}/{quote(path, safe='/')}"
            resp = self._http.post(url, content=content, headers=self._auth_headers(use_service=True))
            if resp.status_code >= 400:
                return {"ok": False, "error": {"status": resp.status_code, "message": resp.text}, "data": None}
            return {"ok": True, "data": resp.json() if resp.content else {"path": path}, "error": None}
        if verb == "storage_download":
            if len(args) < 2:
                raise AdapterError("supabase storage.download requires bucket and path")
            path = str(args[1]).lstrip("/")
            self._require_supabase_http()
            url = f"{self.supabase_url}/storage/v1/object/{quote(bucket, safe='')}/{quote(path, safe='/')}"
            resp = self._http.get(url, headers=self._auth_headers(use_service=True))
            if resp.status_code >= 400:
                return {"ok": False, "error": {"status": resp.status_code, "message": resp.text}, "data": None}
            return {"ok": True, "data": {"content": resp.content.decode('utf-8', errors='replace')}, "error": None}
        if verb == "storage_list":
            prefix = str(args[1]) if len(args) > 1 else ""
            body = {"prefix": prefix}
            return self._request("POST", f"/storage/v1/object/list/{quote(bucket, safe='')}", json_body=body, headers=self._auth_headers(use_service=True))
        if verb == "storage_remove":
            paths = args[1] if len(args) > 1 else []
            if not isinstance(paths, list):
                raise AdapterError("supabase storage.remove requires list of paths")
            return self._request("DELETE", f"/storage/v1/object/{quote(bucket, safe='')}", json_body={"prefixes": paths}, headers=self._auth_headers(use_service=True))
        if verb == "storage_get_public_url":
            if len(args) < 2:
                raise AdapterError("supabase storage.get_public_url requires bucket and path")
            path = str(args[1]).lstrip("/")
            self._require_supabase_http()
            pub = f"{self.supabase_url}/storage/v1/object/public/{quote(bucket, safe='')}/{quote(path, safe='/')}"
            return {"ok": True, "data": {"publicUrl": pub}, "error": None}

        # Realtime section (lightweight; no websocket runtime).
        channel = str(args[0]) if args else ""
        if verb.startswith("realtime_"):
            self._check_channel_allowed(channel)
        if verb == "realtime_subscribe":
            event = str(args[1]) if len(args) > 1 else "*"
            self._channels[channel] = {"event": event, "subscribed_at": time.time()}
            return {"ok": True, "result": {"channel": channel, "event": event}}
        if verb == "realtime_replay":
            from_seq = args[1] if len(args) > 1 else "latest"
            max_events = int(args[2]) if len(args) > 2 and args[2] is not None else 50
            return {"ok": True, "result": {"channel": channel, "events": self._history_slice(channel, from_seq, max_events)}}
        if verb == "realtime_get_cursor":
            group = str(args[1]) if len(args) > 1 and args[1] is not None else "default"
            consumer = str(args[2]) if len(args) > 2 and args[2] is not None else "consumer"
            ck = self._cursor_key(channel, group, consumer)
            return {"ok": True, "result": {"channel": channel, "group": group, "consumer": consumer, "cursor": self._realtime_cursors.get(ck)}}
        if verb == "realtime_ack":
            if len(args) < 2:
                raise AdapterError("supabase realtime.ack requires channel and cursor")
            group = str(args[2]) if len(args) > 2 and args[2] is not None else "default"
            consumer = str(args[3]) if len(args) > 3 and args[3] is not None else "consumer"
            ck = self._cursor_key(channel, group, consumer)
            self._realtime_cursors[ck] = {"cursor": str(args[1]), "acked_at": time.time()}
            return {"ok": True, "result": {"channel": channel, "group": group, "consumer": consumer, "cursor": self._realtime_cursors[ck]}}
        if verb == "realtime_broadcast":
            # Sync path: acknowledge shape without attempting long-lived websocket usage.
            event_name = str(args[1]) if len(args) > 1 else "message"
            payload = args[2] if len(args) > 2 else {}
            return {"ok": True, "result": {"channel": channel, "event": event_name, "payload": payload, "queued": False}}
        # realtime_unsubscribe
        group = str(args[1]) if len(args) > 1 and args[1] is not None else None
        consumer = str(args[2]) if len(args) > 2 and args[2] is not None else None
        if group and consumer:
            grp = self._realtime_groups.get(channel) or {}
            consumers = grp.get(group)
            if consumers and consumer in consumers:
                consumers.discard(consumer)
            if consumers is not None and len(consumers) == 0:
                grp.pop(group, None)
            if len(grp) == 0:
                self._realtime_groups.pop(channel, None)
        removed = self._channels.pop(channel, None) is not None
        return {"ok": True, "result": {"channel": channel, "removed": removed}}

    async def call_async(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower().replace(".", "_")
        if verb not in self._ALL_VERBS:
            raise AdapterError(f"unsupported supabase target: {target}")
        self._check_write(verb)
        if verb == "from":
            if not args:
                raise AdapterError("supabase from requires table argument")
            table = str(args[0])
            self._check_table_allowed(table)
            return {"ok": True, "table": table}
        if verb in {"query", "select"}:
            table = str(args[0])
            where = args[1] if len(args) > 1 and isinstance(args[1], dict) else None
            columns = args[2] if len(args) > 2 and isinstance(args[2], list) else None
            self._check_table_allowed(table)
            cols = ", ".join(columns) if columns else "*"
            sql = f"SELECT {cols} FROM {table}"
            params: List[Any] = []
            if where:
                parts = []
                for k, v in where.items():
                    parts.append(f"{k} = %s")
                    params.append(v)
                sql += " WHERE " + " AND ".join(parts)
            rows = await self._require_postgres().call_async("query", [sql, params], context)
            return {"data": rows, "error": None}
        if verb in {"insert", "update", "delete", "upsert", "rpc"}:
            # Keep behavior equivalent by reusing sync logic where shape handling is already covered.
            return self.call(target, args, context)
        if verb == "auth_sign_up":
            return await self._request_async("POST", "/auth/v1/signup", json_body={"email": str(args[0]), "password": str(args[1])}, headers=self._auth_headers())
        if verb == "auth_sign_in_with_password":
            return await self._request_async(
                "POST",
                "/auth/v1/token",
                params={"grant_type": "password"},
                json_body={"email": str(args[0]), "password": str(args[1])},
                headers=self._auth_headers(),
            )
        if verb == "auth_sign_out":
            access_token = str(args[0]) if args else ""
            return await self._request_async("POST", "/auth/v1/logout", headers=self._auth_headers(bearer=access_token or None))
        if verb == "auth_get_user":
            access_token = str(args[0]) if args else ""
            return await self._request_async("GET", "/auth/v1/user", headers=self._auth_headers(bearer=access_token or None))
        if verb == "auth_reset_password_for_email":
            return await self._request_async("POST", "/auth/v1/recover", json_body={"email": str(args[0])}, headers=self._auth_headers())
        if verb == "realtime_subscribe":
            if not args:
                raise AdapterError("supabase realtime.subscribe requires channel")
            channel = str(args[0])
            self._check_channel_allowed(channel)
            table = str(args[1]) if len(args) > 1 and args[1] is not None else None
            if table:
                self._check_table_allowed(table)
            event_types = args[2] if len(args) > 2 else ["*"]
            if isinstance(event_types, str):
                event_types = [event_types]
            if not isinstance(event_types, list) or not event_types:
                raise AdapterError("supabase realtime.subscribe event_types must be non-empty list|string")
            flt = str(args[3]) if len(args) > 3 and args[3] is not None else None
            timeout_s = float(args[4]) if len(args) > 4 and args[4] is not None else 0.05
            max_events = int(args[5]) if len(args) > 5 and args[5] is not None else 10
            replay_from = args[6] if len(args) > 6 else None
            fanout_group = str(args[7]) if len(args) > 7 and args[7] is not None else "default"
            consumer = str(args[8]) if len(args) > 8 and args[8] is not None else "consumer"
            ch = self._channels.get(channel)
            if ch is None:
                ch = {
                    "table": table,
                    "event_types": [str(x).upper() for x in event_types],
                    "filter": flt,
                    "queue": asyncio.Queue(),
                    "task": None,
                    "ws": None,
                    "subscribed_at": time.time(),
                }
                self._channels[channel] = ch
            grp = self._realtime_groups.setdefault(channel, {})
            grp.setdefault(fanout_group, set()).add(consumer)
            if ch.get("task") is None or ch["task"].done():
                ch["task"] = asyncio.create_task(self._realtime_loop(channel))
            events: List[Dict[str, Any]] = []
            if replay_from is not None:
                events.extend(self._history_slice(channel, replay_from, max_events))
            end = time.time() + max(0.0, timeout_s)
            while len(events) < max_events and time.time() <= end:
                remaining = max(0.0, end - time.time())
                if remaining <= 0:
                    break
                try:
                    evt = await asyncio.wait_for(ch["queue"].get(), timeout=remaining)
                    events.append(evt)
                except asyncio.TimeoutError:
                    break
            return {
                "ok": True,
                "result": {
                    "channel": channel,
                    "events": events[:max_events],
                    "active": True,
                    "fanout_group": fanout_group,
                    "consumer": consumer,
                },
            }
        if verb == "realtime_unsubscribe":
            if not args:
                raise AdapterError("supabase realtime.unsubscribe requires channel")
            channel = str(args[0])
            self._check_channel_allowed(channel)
            fanout_group = str(args[1]) if len(args) > 1 and args[1] is not None else None
            consumer = str(args[2]) if len(args) > 2 and args[2] is not None else None
            if fanout_group and consumer:
                grp = self._realtime_groups.get(channel) or {}
                consumers = grp.get(fanout_group)
                if consumers and consumer in consumers:
                    consumers.discard(consumer)
                if consumers is not None and len(consumers) == 0:
                    grp.pop(fanout_group, None)
                if len(grp) == 0:
                    self._realtime_groups.pop(channel, None)
            ch = self._channels.pop(channel, None)
            if ch and ch.get("task") is not None:
                ch["task"].cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await ch["task"]
            if ch and ch.get("ws") is not None:
                with contextlib.suppress(Exception):
                    await ch["ws"].close()
            return {"ok": True, "result": {"channel": channel, "removed": ch is not None}}
        if verb == "realtime_replay":
            if not args:
                raise AdapterError("supabase realtime.replay requires channel")
            channel = str(args[0])
            self._check_channel_allowed(channel)
            from_seq = args[1] if len(args) > 1 else "latest"
            max_events = int(args[2]) if len(args) > 2 and args[2] is not None else 50
            timeout_s = float(args[3]) if len(args) > 3 and args[3] is not None else 0.01
            if timeout_s > 0:
                await asyncio.sleep(min(timeout_s, 0.05))
            return {"ok": True, "result": {"channel": channel, "events": self._history_slice(channel, from_seq, max_events)}}
        if verb == "realtime_get_cursor":
            if not args:
                raise AdapterError("supabase realtime.get_cursor requires channel")
            channel = str(args[0])
            self._check_channel_allowed(channel)
            group = str(args[1]) if len(args) > 1 and args[1] is not None else "default"
            consumer = str(args[2]) if len(args) > 2 and args[2] is not None else "consumer"
            ck = self._cursor_key(channel, group, consumer)
            return {"ok": True, "result": {"channel": channel, "group": group, "consumer": consumer, "cursor": self._realtime_cursors.get(ck)}}
        if verb == "realtime_ack":
            if len(args) < 2:
                raise AdapterError("supabase realtime.ack requires channel and cursor")
            channel = str(args[0])
            self._check_channel_allowed(channel)
            group = str(args[2]) if len(args) > 2 and args[2] is not None else "default"
            consumer = str(args[3]) if len(args) > 3 and args[3] is not None else "consumer"
            ck = self._cursor_key(channel, group, consumer)
            self._realtime_cursors[ck] = {"cursor": str(args[1]), "acked_at": time.time()}
            return {"ok": True, "result": {"channel": channel, "group": group, "consumer": consumer, "cursor": self._realtime_cursors[ck]}}
        if verb == "realtime_broadcast":
            if len(args) < 2:
                raise AdapterError("supabase realtime.broadcast requires channel and event")
            channel = str(args[0])
            self._check_channel_allowed(channel)
            event_name = str(args[1])
            payload = args[2] if len(args) > 2 else {}
            if not isinstance(payload, dict):
                raise AdapterError("supabase realtime.broadcast payload must be object")
            if self._websockets is None:
                raise AdapterError("supabase realtime websocket requires websockets package")
            ws = None
            try:
                ws = await self._websockets.connect(self._realtime_ws_url())
                await ws.send(
                    json.dumps(
                        {
                            "topic": f"realtime:{channel}",
                            "event": "phx_join",
                            "payload": {"config": {"broadcast": {"self": True}, "presence": {"key": ""}, "postgres_changes": []}},
                            "ref": self._next_ref(),
                        }
                    )
                )
                await ws.send(
                    json.dumps(
                        {
                            "topic": f"realtime:{channel}",
                            "event": "broadcast",
                            "payload": {"event": event_name, "payload": payload},
                            "ref": self._next_ref(),
                        }
                    )
                )
                return {"ok": True, "result": {"channel": channel, "event": event_name, "payload": payload}}
            finally:
                if ws is not None:
                    with contextlib.suppress(Exception):
                        await ws.close()
        return self.call(target, args, context)

    # Async-ready note: DB delegation remains through postgres contracts while
    # auth/storage/realtime use async-capable HTTP/WebSocket clients.
