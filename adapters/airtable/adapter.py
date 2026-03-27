from __future__ import annotations

import asyncio
import base64
import inspect
import os
import time
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote, urlparse

from runtime.adapters.base import AdapterError, RuntimeAdapter


class AirtableAdapter(RuntimeAdapter):
    _READ_VERBS = {
        "list",
        "find",
        "get_table",
        "list_tables",
        "list_bases",
        "attachment_download",
        "webhook_list",
    }
    _WRITE_VERBS = {
        "create",
        "update",
        "delete",
        "upsert",
        "attachment_upload",
        "webhook_create",
        "webhook_delete",
    }
    _ALL_VERBS = _READ_VERBS | _WRITE_VERBS

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_id: Optional[str] = None,
        timeout_s: float = 8.0,
        allow_write: bool = False,
        allow_tables: Optional[Iterable[str]] = None,
        allow_attachment_hosts: Optional[Iterable[str]] = None,
        max_page_size: int = 100,
    ):
        self.api_key = (api_key or os.environ.get("AINL_AIRTABLE_API_KEY") or "").strip() or None
        self.base_id = (base_id or os.environ.get("AINL_AIRTABLE_BASE_ID") or "").strip() or None
        self.timeout_s = float(timeout_s)
        self.allow_write = bool(allow_write)
        self.allow_tables = {str(t).strip() for t in (allow_tables or []) if str(t).strip()}
        self.allow_attachment_hosts = {
            str(h).strip().lower()
            for h in (
                allow_attachment_hosts
                or (os.environ.get("AINL_AIRTABLE_ALLOW_ATTACHMENT_HOST") or "").split(",")
            )
            if str(h).strip()
        }
        self.max_page_size = max(1, min(100, int(max_page_size)))
        self._client: Any = None
        self._async_client: Any = None
        self._validate_config()
        self._init_client()

    def _validate_config(self) -> None:
        missing = []
        if not self.api_key:
            missing.append("api_key")
        if not self.base_id:
            missing.append("base_id")
        if missing:
            raise AdapterError(
                f"airtable configuration missing required values: {', '.join(missing)} "
                "(set AINL_AIRTABLE_API_KEY and AINL_AIRTABLE_BASE_ID or pass explicit args)"
            )

    def _load_httpx(self) -> Any:
        try:
            import httpx
        except Exception as e:  # pragma: no cover
            raise AdapterError("airtable adapter requires httpx. Install with: pip install 'httpx'") from e
        return httpx

    def _init_client(self) -> None:
        httpx = self._load_httpx()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        self._client = httpx.Client(timeout=self.timeout_s, headers=headers)
        async_ctor = getattr(httpx, "AsyncClient", None)
        self._async_client = async_ctor(timeout=self.timeout_s, headers=headers) if callable(async_ctor) else self._client

    def _check_write(self, verb: str) -> None:
        if verb in self._WRITE_VERBS and not self.allow_write:
            raise AdapterError("airtable write blocked: allow_write is false")

    def _check_table_allowed(self, table: str) -> None:
        if self.allow_tables and table not in self.allow_tables:
            raise AdapterError(f"airtable table blocked by allowlist: {table}")

    def _check_attachment_url_allowed(self, url: str) -> None:
        if not self.allow_attachment_hosts:
            return
        host = (urlparse(url).hostname or "").strip().lower()
        if host not in self.allow_attachment_hosts:
            raise AdapterError(f"airtable attachment url host blocked by allowlist: {host}")

    def _tbl_path(self, table: str) -> str:
        return f"/v0/{self.base_id}/{quote(str(table), safe='')}"

    def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json_body: Any = None, content: Any = None) -> Any:
        c = self._client
        if c is None:
            self._init_client()
            c = self._client
        max_attempts = 3
        for i in range(max_attempts):
            try:
                resp = c.request(method, f"https://api.airtable.com{path}", params=params, json=json_body, content=content)
                if resp.status_code in {429, 500, 502, 503, 504} and i < max_attempts - 1:
                    time.sleep(0.2 * (2**i))
                    continue
                if resp.status_code >= 400:
                    raise AdapterError(f"airtable http error {resp.status_code}: {resp.text}")
                return resp.json() if getattr(resp, "content", None) else {}
            except AdapterError:
                raise
            except Exception as e:
                if i < max_attempts - 1:
                    time.sleep(0.2 * (2**i))
                    continue
                raise AdapterError(f"airtable transport error: {e}") from e

    async def _request_async(
        self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json_body: Any = None, content: Any = None
    ) -> Any:
        c = self._async_client
        if c is None:
            self._init_client()
            c = self._async_client
        max_attempts = 3
        for i in range(max_attempts):
            try:
                maybe = c.request(method, f"https://api.airtable.com{path}", params=params, json=json_body, content=content)
                resp = await maybe if inspect.isawaitable(maybe) else maybe
                if resp.status_code in {429, 500, 502, 503, 504} and i < max_attempts - 1:
                    await asyncio.sleep(0.2 * (2**i))
                    continue
                if resp.status_code >= 400:
                    raise AdapterError(f"airtable http error {resp.status_code}: {resp.text}")
                return resp.json() if getattr(resp, "content", None) else {}
            except AdapterError:
                raise
            except Exception as e:
                if i < max_attempts - 1:
                    await asyncio.sleep(0.2 * (2**i))
                    continue
                raise AdapterError(f"airtable transport error: {e}") from e

    def _normalize_record(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        return {"id": rec.get("id"), "fields": rec.get("fields") or {}, "createdTime": rec.get("createdTime")}

    def _list_records(self, table: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._check_table_allowed(table)
        data = self._request("GET", self._tbl_path(table), params=params or {})
        out = {"records": [self._normalize_record(r) for r in (data.get("records") or [])]}
        if data.get("offset"):
            out["offset"] = data.get("offset")
        return out

    def _find_formula(self, field: str, value: Any) -> str:
        val = str(value).replace("'", "\\'")
        return f"{{{field}}}='{val}'"

    def _webhook_body(self, table_or_view: str, actions: List[str], notification_url: str) -> Dict[str, Any]:
        return {
            "notificationUrl": notification_url,
            "specification": {
                "options": {"filters": {"dataTypes": ["tableData"], "recordChangeScope": table_or_view, "changeTypes": [str(a).lower() for a in actions]}}
            },
        }

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower().replace(".", "_")
        if verb not in self._ALL_VERBS:
            raise AdapterError(f"unsupported airtable target: {target}")
        self._check_write(verb)

        if verb == "list_bases":
            data = self._request("GET", "/v0/meta/bases")
            return {"bases": list(data.get("bases") or []), "offset": data.get("offset")}
        if verb == "list_tables":
            data = self._request("GET", f"/v0/meta/bases/{self.base_id}/tables")
            return {"tables": list(data.get("tables") or [])}
        if verb == "webhook_list":
            data = self._request("GET", f"/v0/bases/{quote(self.base_id, safe='')}/webhooks")
            return {"webhooks": list(data.get("webhooks") or [])}
        if verb == "get_table":
            if not args:
                raise AdapterError("airtable get_table requires table name argument")
            table = str(args[0])
            self._check_table_allowed(table)
            tables = self.call("list_tables", [], context).get("tables", [])
            for t in tables:
                if str(t.get("name")) == table or str(t.get("id")) == table:
                    return {"table": t}
            return {"table": None}
        if len(args) < 1:
            raise AdapterError(f"airtable {verb} requires table argument")
        table = str(args[0])
        self._check_table_allowed(table)

        if verb == "list":
            params = dict(args[1]) if len(args) > 1 and isinstance(args[1], dict) else {}
            if "pageSize" in params:
                params["pageSize"] = max(1, min(self.max_page_size, int(params["pageSize"])))
            return self._list_records(table, params=params)
        if verb == "find":
            if len(args) < 2:
                raise AdapterError("airtable find requires filter formula or {field,value} object")
            finder = args[1]
            params: Dict[str, Any] = {}
            if isinstance(finder, str):
                params["filterByFormula"] = finder
            elif isinstance(finder, dict):
                if "formula" in finder:
                    params["filterByFormula"] = str(finder["formula"])
                elif "field" in finder and "value" in finder:
                    params["filterByFormula"] = self._find_formula(str(finder["field"]), finder["value"])
                else:
                    raise AdapterError("airtable find dict must provide formula or field/value")
                if finder.get("view"):
                    params["view"] = str(finder["view"])
            else:
                raise AdapterError("airtable find requires string formula or object")
            params["pageSize"] = 100
            return self._list_records(table, params=params)
        if verb == "create":
            if len(args) < 2:
                raise AdapterError("airtable create requires record or records")
            payload = args[1]
            if isinstance(payload, dict):
                data = self._request("POST", self._tbl_path(table), json_body={"fields": dict(payload)})
                return self._normalize_record(data)
            if isinstance(payload, list):
                records = [{"fields": dict(p)} for p in payload]
                data = self._request("POST", self._tbl_path(table), json_body={"records": records})
                return {"records": [self._normalize_record(r) for r in (data.get("records") or [])]}
            raise AdapterError("airtable create payload must be object or list")
        if verb == "update":
            if len(args) < 2:
                raise AdapterError("airtable update requires payload")
            payload = args[1]
            if isinstance(payload, dict):
                rec_id = str(payload.get("id") or "")
                fields = payload.get("fields")
                if not rec_id or not isinstance(fields, dict):
                    raise AdapterError("airtable update single payload requires {id, fields}")
                data = self._request("PATCH", f"{self._tbl_path(table)}/{quote(rec_id, safe='')}", json_body={"fields": fields})
                return self._normalize_record(data)
            if isinstance(payload, list):
                records = []
                for p in payload:
                    if not isinstance(p, dict) or not p.get("id") or not isinstance(p.get("fields"), dict):
                        raise AdapterError("airtable update batch payload entries require {id, fields}")
                    records.append({"id": str(p["id"]), "fields": dict(p["fields"])})
                data = self._request("PATCH", self._tbl_path(table), json_body={"records": records})
                return {"records": [self._normalize_record(r) for r in (data.get("records") or [])]}
            raise AdapterError("airtable update payload must be object or list")
        if verb == "delete":
            if len(args) < 2:
                raise AdapterError("airtable delete requires record id or ids")
            payload = args[1]
            if isinstance(payload, str):
                data = self._request("DELETE", f"{self._tbl_path(table)}/{quote(payload, safe='')}")
                return {"id": data.get("id"), "deleted": bool(data.get("deleted"))}
            if isinstance(payload, list):
                params = [("records[]", str(rid)) for rid in payload]
                resp = self._client.request("DELETE", f"https://api.airtable.com{self._tbl_path(table)}", params=params)
                if resp.status_code >= 400:
                    raise AdapterError(f"airtable http error {resp.status_code}: {resp.text}")
                data = resp.json()
                return {"records": list(data.get("records") or [])}
            raise AdapterError("airtable delete payload must be record id string or list")
        if verb == "attachment_upload":
            if len(args) < 4:
                raise AdapterError("airtable attachment.upload requires table, record_id, field_name, file_path_or_bytes, filename?")
            record_id = str(args[1])
            field_name = str(args[2])
            payload = args[3]
            filename = str(args[4]) if len(args) > 4 and args[4] is not None else "upload.bin"
            if isinstance(payload, (bytes, bytearray)):
                file_bytes = bytes(payload)
            elif isinstance(payload, str):
                if payload.startswith("http://") or payload.startswith("https://"):
                    self._check_attachment_url_allowed(payload)
                    data = self._request("PATCH", f"{self._tbl_path(table)}/{quote(record_id, safe='')}", json_body={"fields": {field_name: [{"url": payload, "filename": filename}]}})
                    out = self._normalize_record(data)
                    return {"record": out, "attachments": out.get("fields", {}).get(field_name, [])}
                with open(payload, "rb") as fh:
                    file_bytes = fh.read()
                filename = filename or (os.path.basename(payload) or "upload.bin")
            else:
                raise AdapterError("airtable attachment.upload payload must be bytes, URL string, or file path string")
            data = self._request(
                "POST",
                f"/v0/{self.base_id}/{quote(record_id, safe='')}/{quote(field_name, safe='')}/uploadAttachment",
                json_body={"contentType": "application/octet-stream", "filename": filename, "file": base64.b64encode(file_bytes).decode("ascii")},
            )
            return {"attachment": data, "ok": True}
        if verb == "attachment_download":
            if len(args) < 2:
                raise AdapterError("airtable attachment.download requires table and attachment_url")
            url = str(args[1])
            self._check_attachment_url_allowed(url)
            resp = self._client.request("GET", url)
            if resp.status_code >= 400:
                raise AdapterError(f"airtable attachment download http error {resp.status_code}: {resp.text}")
            out_path = str(args[2]) if len(args) > 2 and args[2] is not None else ""
            if out_path:
                with open(out_path, "wb") as fh:
                    fh.write(resp.content)
                return {"path": out_path, "size": len(resp.content)}
            return {"bytes_b64": base64.b64encode(resp.content).decode("ascii"), "size": len(resp.content)}
        if verb == "webhook_create":
            if len(args) < 4:
                raise AdapterError("airtable webhook.create requires table, table_or_view, actions, notification_url")
            self._check_table_allowed(str(args[0]))
            data = self._request(
                "POST",
                f"/v0/bases/{quote(self.base_id, safe='')}/webhooks",
                json_body=self._webhook_body(str(args[1]), args[2] if isinstance(args[2], list) else [args[2]], str(args[3])),
            )
            return {
                "webhook_id": data.get("id"),
                "expiration_time": data.get("expirationTime"),
                "mac_secret_base64": data.get("macSecretBase64"),
                "specification": data.get("specification"),
            }
        if verb == "webhook_delete":
            if len(args) < 2:
                raise AdapterError("airtable webhook.delete requires table and webhook_id")
            self._check_table_allowed(str(args[0]))
            webhook_id = str(args[1])
            data = self._request("DELETE", f"/v0/bases/{quote(self.base_id, safe='')}/webhooks/{quote(webhook_id, safe='')}")
            return {"id": data.get("id", webhook_id), "deleted": bool(data.get("deleted", True))}
        if len(args) < 4:
            raise AdapterError("airtable upsert requires key_field, key_value, fields")
        key_field = str(args[1])
        key_value = args[2]
        fields = args[3]
        if not isinstance(fields, dict):
            raise AdapterError("airtable upsert fields must be object")
        found = self.call("find", [table, {"field": key_field, "value": key_value}], context)
        records = found.get("records") or []
        if records:
            rid = records[0].get("id")
            updated = self.call("update", [table, {"id": rid, "fields": fields}], context)
            return {"ok": True, "action": "updated", "record": updated}
        created = self.call("create", [table, fields], context)
        return {"ok": True, "action": "created", "record": created}

    async def call_async(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower().replace(".", "_")
        if verb not in self._ALL_VERBS:
            raise AdapterError(f"unsupported airtable target: {target}")
        self._check_write(verb)
        if verb in {"list", "find", "create", "update", "delete", "upsert", "get_table", "list_tables", "list_bases"}:
            return await asyncio.to_thread(self.call, target, args, context)
        if verb == "attachment_download":
            if len(args) < 2:
                raise AdapterError("airtable attachment.download requires table and attachment_url")
            url = str(args[1])
            self._check_attachment_url_allowed(url)
            maybe = self._async_client.request("GET", url)
            resp = await maybe if inspect.isawaitable(maybe) else maybe
            if resp.status_code >= 400:
                raise AdapterError(f"airtable attachment download http error {resp.status_code}: {resp.text}")
            out_path = str(args[2]) if len(args) > 2 and args[2] is not None else ""
            if out_path:
                with open(out_path, "wb") as fh:
                    fh.write(resp.content)
                return {"path": out_path, "size": len(resp.content)}
            return {"bytes_b64": base64.b64encode(resp.content).decode("ascii"), "size": len(resp.content)}
        if verb == "attachment_upload":
            return await asyncio.to_thread(self.call, target, args, context)
        if verb == "webhook_list":
            data = await self._request_async("GET", f"/v0/bases/{quote(self.base_id, safe='')}/webhooks")
            return {"webhooks": list(data.get("webhooks") or [])}
        if verb == "webhook_create":
            if len(args) < 4:
                raise AdapterError("airtable webhook.create requires table, table_or_view, actions, notification_url")
            self._check_table_allowed(str(args[0]))
            data = await self._request_async(
                "POST",
                f"/v0/bases/{quote(self.base_id, safe='')}/webhooks",
                json_body=self._webhook_body(str(args[1]), args[2] if isinstance(args[2], list) else [args[2]], str(args[3])),
            )
            return {
                "webhook_id": data.get("id"),
                "expiration_time": data.get("expirationTime"),
                "mac_secret_base64": data.get("macSecretBase64"),
                "specification": data.get("specification"),
            }
        if verb == "webhook_delete":
            if len(args) < 2:
                raise AdapterError("airtable webhook.delete requires table and webhook_id")
            self._check_table_allowed(str(args[0]))
            webhook_id = str(args[1])
            data = await self._request_async("DELETE", f"/v0/bases/{quote(self.base_id, safe='')}/webhooks/{quote(webhook_id, safe='')}")
            return {"id": data.get("id", webhook_id), "deleted": bool(data.get("deleted", True))}
        return await asyncio.to_thread(self.call, target, args, context)
