from __future__ import annotations

import asyncio
import contextlib
import os
import time
from typing import Any, Dict, Iterable, List, Optional

from runtime.adapters.base import AdapterError, RuntimeAdapter


class DynamoDBAdapter(RuntimeAdapter):
    """
    DynamoDB runtime adapter.

    Verbs:
    - get, put, update, delete
    - query, scan
    - batch_get, batch_write
    - transact_get, transact_write
    - describe_table, list_tables
    """

    _READ_VERBS = {
        "get",
        "query",
        "scan",
        "batch_get",
        "transact_get",
        "describe_table",
        "list_tables",
        "streams_subscribe",
        "streams_unsubscribe",
    }
    _WRITE_VERBS = {"put", "update", "delete", "batch_write", "transact_write"}
    _ALL_VERBS = _READ_VERBS | _WRITE_VERBS

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        region: Optional[str] = None,
        timeout_s: float = 5.0,
        allow_write: bool = False,
        allow_tables: Optional[Iterable[str]] = None,
        consistent_read: bool = False,
    ):
        self.url = (url or os.environ.get("AINL_DYNAMODB_URL") or "").strip() or None
        self.region = (region or os.environ.get("AINL_DYNAMODB_REGION") or "us-east-1").strip()
        self.timeout_s = float(timeout_s)
        self.allow_write = bool(allow_write)
        self.allow_tables = {str(t).strip() for t in (allow_tables or []) if str(t).strip()}
        self.consistent_read = bool(consistent_read)
        self._client: Any = None
        self._streams_client: Any = None
        self._serializer: Any = None
        self._deserializer: Any = None
        self._async_stream_subscriptions: Dict[str, Dict[str, Any]] = {}
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._init_client()

    def _load_boto3(self) -> Any:
        try:
            import boto3
        except Exception as e:  # pragma: no cover
            raise AdapterError("dynamodb adapter requires boto3. Install with: pip install 'boto3>=1.34.0'") from e
        return boto3

    def _load_botocore(self) -> Any:
        try:
            from botocore.config import Config
        except Exception as e:  # pragma: no cover
            raise AdapterError("dynamodb adapter requires botocore (installed with boto3)") from e
        return Config

    def _load_types(self) -> Any:
        try:
            from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
        except Exception as e:  # pragma: no cover
            raise AdapterError("dynamodb adapter missing boto3.dynamodb.types helpers") from e
        return TypeSerializer, TypeDeserializer

    def _init_client(self) -> None:
        boto3 = self._load_boto3()
        Config = self._load_botocore()
        TypeSerializer, TypeDeserializer = self._load_types()
        try:
            session = boto3.session.Session(region_name=self.region)
            cfg = Config(connect_timeout=self.timeout_s, read_timeout=self.timeout_s, retries={"max_attempts": 2})
            kwargs: Dict[str, Any] = {"config": cfg}
            if self.url:
                kwargs["endpoint_url"] = self.url
            self._client = session.client("dynamodb", **kwargs)
            self._streams_client = session.client("dynamodbstreams", **kwargs)
            self._serializer = TypeSerializer()
            self._deserializer = TypeDeserializer()
        except Exception as e:
            raise AdapterError(f"dynamodb client init error: {e}") from e

    def _require_client(self) -> Any:
        if self._client is None:
            self._init_client()
        return self._client

    def _require_streams_client(self) -> Any:
        if self._streams_client is None:
            self._init_client()
        return self._streams_client

    def _check_write(self, verb: str) -> None:
        if verb in self._WRITE_VERBS and not self.allow_write:
            raise AdapterError("dynamodb write blocked: allow_write is false")

    def _check_table_allowed(self, table: str) -> None:
        if not self.allow_tables:
            return
        if table not in self.allow_tables:
            raise AdapterError(f"dynamodb table blocked by allowlist: {table}")

    def _normalize_stream_record(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        ddb = rec.get("dynamodb") if isinstance(rec, dict) else {}
        if not isinstance(ddb, dict):
            ddb = {}
        keys = self._deserialize_item(ddb.get("Keys") if isinstance(ddb.get("Keys"), dict) else None) or {}
        new_image = self._deserialize_item(ddb.get("NewImage") if isinstance(ddb.get("NewImage"), dict) else None)
        old_image = self._deserialize_item(ddb.get("OldImage") if isinstance(ddb.get("OldImage"), dict) else None)
        return {
            "eventName": str(rec.get("eventName") or "").upper() or "UNKNOWN",
            "eventID": rec.get("eventID"),
            "eventSourceARN": rec.get("eventSourceARN"),
            "dynamodb": {
                "Keys": keys,
                "NewImage": new_image,
                "OldImage": old_image,
                "SequenceNumber": ddb.get("SequenceNumber"),
            },
            "raw": rec,
        }

    def _stream_table_arn(self, table: str) -> str:
        self._check_table_allowed(table)
        c = self._require_client()
        try:
            t = c.describe_table(TableName=table).get("Table") or {}
            arn = str(t.get("LatestStreamArn") or "").strip()
            if not arn:
                raise AdapterError(f"dynamodb streams not enabled for table: {table}")
            return arn
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(f"dynamodb streams describe_table error: {e}") from e

    def _stream_first_shard(self, stream_arn: str) -> str:
        s = self._require_streams_client()
        try:
            resp = s.describe_stream(StreamArn=stream_arn)
            shards = ((resp.get("StreamDescription") or {}).get("Shards") or [])
            if not shards:
                raise AdapterError("dynamodb stream has no shards")
            shard_id = str((shards[0] or {}).get("ShardId") or "").strip()
            if not shard_id:
                raise AdapterError("dynamodb stream shard id missing")
            return shard_id
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(f"dynamodb streams describe_stream error: {e}") from e

    def _stream_subscribe_sync(
        self,
        table: str,
        iterator_type: str,
        filter_spec: Optional[Dict[str, Any]],
        timeout_s: float,
        max_events: int,
    ) -> Dict[str, Any]:
        stream_arn = self._stream_table_arn(table)
        shard_id = self._stream_first_shard(stream_arn)
        s = self._require_streams_client()
        kwargs: Dict[str, Any] = {
            "StreamArn": stream_arn,
            "ShardId": shard_id,
            "ShardIteratorType": iterator_type,
        }
        if iterator_type == "AT_SEQUENCE_NUMBER":
            seq = str((filter_spec or {}).get("sequence_number") or "").strip()
            if not seq:
                raise AdapterError("dynamodb streams.subscribe AT_SEQUENCE_NUMBER requires filter.sequence_number")
            kwargs["SequenceNumber"] = seq
        it = s.get_shard_iterator(**kwargs).get("ShardIterator")
        events: List[Dict[str, Any]] = []
        start = time.time()
        allow_events = {str(x).upper() for x in ((filter_spec or {}).get("event_names") or [])}
        while it and len(events) < max_events and (time.time() - start) <= timeout_s:
            out = s.get_records(ShardIterator=it, Limit=min(100, max_events - len(events)))
            it = out.get("NextShardIterator")
            for raw in (out.get("Records") or []):
                norm = self._normalize_stream_record(raw)
                if allow_events and norm["eventName"] not in allow_events:
                    continue
                events.append(norm)
                if len(events) >= max_events:
                    break
            if not out.get("Records"):
                time.sleep(0.2)
        return {"table": table, "events": events, "active": False}

    async def _streams_loop(
        self,
        key: str,
        table: str,
        iterator_type: str,
        filter_spec: Optional[Dict[str, Any]],
        queue: asyncio.Queue,
    ) -> None:
        allow_events = {str(x).upper() for x in ((filter_spec or {}).get("event_names") or [])}
        try:
            stream_arn = await asyncio.to_thread(self._stream_table_arn, table)
            shard_id = await asyncio.to_thread(self._stream_first_shard, stream_arn)
            kwargs: Dict[str, Any] = {
                "StreamArn": stream_arn,
                "ShardId": shard_id,
                "ShardIteratorType": iterator_type,
            }
            if iterator_type == "AT_SEQUENCE_NUMBER":
                seq = str((filter_spec or {}).get("sequence_number") or "").strip()
                if not seq:
                    raise AdapterError("dynamodb streams.subscribe AT_SEQUENCE_NUMBER requires filter.sequence_number")
                kwargs["SequenceNumber"] = seq
            s = self._require_streams_client()
            it = (await asyncio.to_thread(s.get_shard_iterator, **kwargs)).get("ShardIterator")
            while True:
                if not it:
                    await asyncio.sleep(0.2)
                    continue
                out = await asyncio.to_thread(s.get_records, ShardIterator=it, Limit=100)
                it = out.get("NextShardIterator")
                recs = out.get("Records") or []
                if not recs:
                    await asyncio.sleep(0.2)
                    continue
                for raw in recs:
                    norm = self._normalize_stream_record(raw)
                    if allow_events and norm["eventName"] not in allow_events:
                        continue
                    await queue.put(norm)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            with contextlib.suppress(Exception):
                await queue.put({"eventName": "ERROR", "dynamodb": {"Keys": {}, "NewImage": None, "OldImage": None}, "raw": {"message": str(e)}})
        finally:
            self._async_stream_subscriptions.pop(key, None)

    async def _streams_subscribe_async(
        self,
        table: str,
        iterator_type: str,
        filter_spec: Optional[Dict[str, Any]],
        timeout_s: float,
        max_events: int,
    ) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        if self._async_loop is not None and self._async_loop is not loop:
            for sub in list(self._async_stream_subscriptions.values()):
                t = sub.get("task")
                if t is not None:
                    t.cancel()
            self._async_stream_subscriptions.clear()
        self._async_loop = loop

        key = str(table)
        sub = self._async_stream_subscriptions.get(key)
        if sub is None:
            q: asyncio.Queue = asyncio.Queue()
            task = asyncio.create_task(self._streams_loop(key, table, iterator_type, filter_spec, q))
            sub = {"queue": q, "task": task, "table": table}
            self._async_stream_subscriptions[key] = sub
        q = sub["queue"]
        events: List[Dict[str, Any]] = []
        end = time.time() + max(0.0, timeout_s)
        while len(events) < max_events and time.time() <= end:
            remaining = max(0.0, end - time.time())
            if remaining <= 0:
                break
            try:
                evt = await asyncio.wait_for(q.get(), timeout=remaining)
                events.append(evt)
            except asyncio.TimeoutError:
                break
        return {"table": table, "events": events, "active": True}

    async def _streams_unsubscribe_async(self, table: str) -> Dict[str, Any]:
        self._check_table_allowed(table)
        sub = self._async_stream_subscriptions.pop(table, None)
        if not sub:
            return {"table": table, "removed": False}
        task = sub.get("task")
        if task is not None:
            task.cancel()
            same_loop = True
            with contextlib.suppress(Exception):
                same_loop = task.get_loop() is asyncio.get_running_loop()
            if same_loop:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        return {"table": table, "removed": True}

    def _serialize_value(self, value: Any) -> Dict[str, Any]:
        return self._serializer.serialize(value)

    def _serialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(item, dict) or not item:
            raise AdapterError("dynamodb item must be non-empty object")
        return {k: self._serialize_value(v) for k, v in item.items()}

    def _deserialize_attr(self, value: Dict[str, Any]) -> Any:
        return self._deserializer.deserialize(value)

    def _deserialize_item(self, item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not item:
            return None
        return {k: self._deserialize_attr(v) for k, v in item.items()}

    def _serialize_expr_values(self, values: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if values is None:
            return None
        if not isinstance(values, dict):
            raise AdapterError("dynamodb expression attribute values must be object when provided")
        return {k: self._serialize_value(v) for k, v in values.items()}

    def _wrap_items_result(self, resp: Dict[str, Any]) -> Dict[str, Any]:
        out = {
            "items": [self._deserialize_item(i) for i in (resp.get("Items") or [])],
            "count": int(resp.get("Count") or 0),
        }
        if "LastEvaluatedKey" in resp and resp.get("LastEvaluatedKey"):
            out["last_evaluated_key"] = self._deserialize_item(resp.get("LastEvaluatedKey"))
        return out

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower().replace(".", "_")
        if verb not in self._ALL_VERBS:
            raise AdapterError(f"unsupported dynamodb target: {target}")
        self._check_write(verb)
        c = self._require_client()

        if verb == "list_tables":
            limit = int(args[0]) if args else 100
            last = str(args[1]) if len(args) > 1 and args[1] is not None else None
            resp = c.list_tables(Limit=limit, ExclusiveStartTableName=last) if last else c.list_tables(Limit=limit)
            out = {"tables": list(resp.get("TableNames") or [])}
            if resp.get("LastEvaluatedTableName"):
                out["last_evaluated_table_name"] = resp["LastEvaluatedTableName"]
            return out

        if verb == "describe_table":
            if not args:
                raise AdapterError("dynamodb describe_table requires table argument")
            table = str(args[0])
            self._check_table_allowed(table)
            resp = c.describe_table(TableName=table)
            return {"table": resp.get("Table")}

        if verb == "streams_subscribe":
            if not args:
                raise AdapterError("dynamodb streams.subscribe requires table_name")
            table = str(args[0])
            self._check_table_allowed(table)
            iterator_type = str(args[1]) if len(args) > 1 and args[1] is not None else "LATEST"
            iterator_type = iterator_type.upper()
            if iterator_type not in {"LATEST", "TRIM_HORIZON", "AT_SEQUENCE_NUMBER"}:
                raise AdapterError("dynamodb streams.subscribe shard_iterator_type must be LATEST|TRIM_HORIZON|AT_SEQUENCE_NUMBER")
            filter_spec = args[2] if len(args) > 2 and isinstance(args[2], dict) else None
            timeout_s = float(args[3]) if len(args) > 3 and args[3] is not None else 1.0
            max_events = int(args[4]) if len(args) > 4 and args[4] is not None else 10
            return self._stream_subscribe_sync(table, iterator_type, filter_spec, timeout_s, max_events)

        if verb == "streams_unsubscribe":
            if not args:
                raise AdapterError("dynamodb streams.unsubscribe requires table_name")
            table = str(args[0])
            self._check_table_allowed(table)
            return {"table": table, "removed": False}

        if verb in {"get", "put", "update", "delete", "query", "scan"}:
            if len(args) < 1:
                raise AdapterError(f"dynamodb {verb} requires table argument")
            table = str(args[0])
            self._check_table_allowed(table)

            if verb == "get":
                if len(args) < 2:
                    raise AdapterError("dynamodb get requires key object")
                key = self._serialize_item(args[1])
                consistent = bool(args[2]) if len(args) > 2 else self.consistent_read
                resp = c.get_item(TableName=table, Key=key, ConsistentRead=consistent)
                return {"item": self._deserialize_item(resp.get("Item"))}

            if verb == "put":
                if len(args) < 2:
                    raise AdapterError("dynamodb put requires item object")
                item = self._serialize_item(args[1])
                return_values = str(args[2]) if len(args) > 2 and args[2] is not None else "NONE"
                resp = c.put_item(TableName=table, Item=item, ReturnValues=return_values)
                return {"attributes": self._deserialize_item(resp.get("Attributes"))}

            if verb == "update":
                if len(args) < 3:
                    raise AdapterError("dynamodb update requires key object and update_expression")
                key = self._serialize_item(args[1])
                update_expression = str(args[2])
                expr_values = self._serialize_expr_values(args[3] if len(args) > 3 else None)
                expr_names = args[4] if len(args) > 4 else None
                return_values = str(args[5]) if len(args) > 5 and args[5] is not None else "ALL_NEW"
                kwargs: Dict[str, Any] = {
                    "TableName": table,
                    "Key": key,
                    "UpdateExpression": update_expression,
                    "ReturnValues": return_values,
                }
                if expr_values:
                    kwargs["ExpressionAttributeValues"] = expr_values
                if expr_names:
                    kwargs["ExpressionAttributeNames"] = dict(expr_names)
                resp = c.update_item(**kwargs)
                return {"attributes": self._deserialize_item(resp.get("Attributes"))}

            if verb == "delete":
                if len(args) < 2:
                    raise AdapterError("dynamodb delete requires key object")
                key = self._serialize_item(args[1])
                return_values = str(args[2]) if len(args) > 2 and args[2] is not None else "NONE"
                resp = c.delete_item(TableName=table, Key=key, ReturnValues=return_values)
                return {"attributes": self._deserialize_item(resp.get("Attributes"))}

            if verb == "query":
                if len(args) < 2:
                    raise AdapterError("dynamodb query requires key_condition_expression")
                key_condition = str(args[1])
                expr_values = self._serialize_expr_values(args[2] if len(args) > 2 else None)
                filter_expression = str(args[3]) if len(args) > 3 and args[3] is not None else None
                limit = int(args[4]) if len(args) > 4 and args[4] is not None else None
                start_key = self._serialize_item(args[5]) if len(args) > 5 and args[5] is not None else None
                kwargs = {"TableName": table, "KeyConditionExpression": key_condition, "ConsistentRead": self.consistent_read}
                if expr_values:
                    kwargs["ExpressionAttributeValues"] = expr_values
                if filter_expression:
                    kwargs["FilterExpression"] = filter_expression
                if limit is not None:
                    kwargs["Limit"] = limit
                if start_key is not None:
                    kwargs["ExclusiveStartKey"] = start_key
                resp = c.query(**kwargs)
                return self._wrap_items_result(resp)

            # scan
            filter_expression = str(args[1]) if len(args) > 1 and args[1] is not None else None
            expr_values = self._serialize_expr_values(args[2] if len(args) > 2 else None)
            limit = int(args[3]) if len(args) > 3 and args[3] is not None else None
            start_key = self._serialize_item(args[4]) if len(args) > 4 and args[4] is not None else None
            kwargs = {"TableName": table, "ConsistentRead": self.consistent_read}
            if filter_expression:
                kwargs["FilterExpression"] = filter_expression
            if expr_values:
                kwargs["ExpressionAttributeValues"] = expr_values
            if limit is not None:
                kwargs["Limit"] = limit
            if start_key is not None:
                kwargs["ExclusiveStartKey"] = start_key
            resp = c.scan(**kwargs)
            return self._wrap_items_result(resp)

        if verb == "batch_get":
            if not args:
                raise AdapterError("dynamodb batch_get requires request object")
            req = args[0]
            if not isinstance(req, dict):
                raise AdapterError("dynamodb batch_get request must be object")
            request_items: Dict[str, Any] = {}
            for table, spec in req.items():
                self._check_table_allowed(str(table))
                if not isinstance(spec, dict) or not isinstance(spec.get("keys"), list):
                    raise AdapterError("dynamodb batch_get request table spec must include keys list")
                request_items[str(table)] = {
                    "Keys": [self._serialize_item(k) for k in spec["keys"]],
                    "ConsistentRead": bool(spec.get("consistent_read", self.consistent_read)),
                }
            resp = c.batch_get_item(RequestItems=request_items)
            out: Dict[str, Any] = {"responses": {}}
            for table, items in (resp.get("Responses") or {}).items():
                out["responses"][table] = [self._deserialize_item(i) for i in items]
            return out

        if verb == "batch_write":
            if not args:
                raise AdapterError("dynamodb batch_write requires request object")
            req = args[0]
            if not isinstance(req, dict):
                raise AdapterError("dynamodb batch_write request must be object")
            request_items: Dict[str, Any] = {}
            for table, ops in req.items():
                self._check_table_allowed(str(table))
                if not isinstance(ops, list):
                    raise AdapterError("dynamodb batch_write table value must be list")
                table_ops = []
                for op in ops:
                    if not isinstance(op, dict):
                        raise AdapterError("dynamodb batch_write op must be object")
                    if "put_request" in op:
                        item = self._serialize_item(op["put_request"].get("item"))
                        table_ops.append({"PutRequest": {"Item": item}})
                    elif "delete_request" in op:
                        key = self._serialize_item(op["delete_request"].get("key"))
                        table_ops.append({"DeleteRequest": {"Key": key}})
                    else:
                        raise AdapterError("dynamodb batch_write op must be put_request or delete_request")
                request_items[str(table)] = table_ops
            resp = c.batch_write_item(RequestItems=request_items)
            return {"ok": True, "unprocessed_items": resp.get("UnprocessedItems") or {}}

        if verb == "transact_get":
            if not args or not isinstance(args[0], list) or not args[0]:
                raise AdapterError("dynamodb transact_get requires non-empty list")
            t_items = []
            for op in args[0]:
                if not isinstance(op, dict):
                    raise AdapterError("dynamodb transact_get op must be object")
                table = str(op.get("table") or "")
                self._check_table_allowed(table)
                key = self._serialize_item(op.get("key"))
                t_items.append({"Get": {"TableName": table, "Key": key}})
            resp = c.transact_get_items(TransactItems=t_items)
            out = []
            for it in (resp.get("Responses") or []):
                out.append({"item": self._deserialize_item(it.get("Item"))})
            return {"ok": True, "results": out}

        # transact_write
        if not args or not isinstance(args[0], list) or not args[0]:
            raise AdapterError("dynamodb transact_write requires non-empty list")
        t_items = []
        for op in args[0]:
            if not isinstance(op, dict):
                raise AdapterError("dynamodb transact_write op must be object")
            action = str(op.get("action") or "").lower()
            table = str(op.get("table") or "")
            self._check_table_allowed(table)
            if action == "put":
                t_items.append({"Put": {"TableName": table, "Item": self._serialize_item(op.get("item"))}})
            elif action == "delete":
                t_items.append({"Delete": {"TableName": table, "Key": self._serialize_item(op.get("key"))}})
            elif action == "update":
                kwargs: Dict[str, Any] = {
                    "TableName": table,
                    "Key": self._serialize_item(op.get("key")),
                    "UpdateExpression": str(op.get("update_expression") or ""),
                }
                expr_values = self._serialize_expr_values(op.get("expression_attribute_values"))
                if expr_values:
                    kwargs["ExpressionAttributeValues"] = expr_values
                if op.get("expression_attribute_names"):
                    kwargs["ExpressionAttributeNames"] = dict(op["expression_attribute_names"])
                t_items.append({"Update": kwargs})
            else:
                raise AdapterError(f"unsupported dynamodb transact_write action: {action}")
        c.transact_write_items(TransactItems=t_items)
        return {"ok": True, "results": []}

    async def call_async(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower().replace(".", "_")
        if verb not in self._ALL_VERBS:
            raise AdapterError(f"unsupported dynamodb target: {target}")
        if verb == "streams_subscribe":
            if not args:
                raise AdapterError("dynamodb streams.subscribe requires table_name")
            table = str(args[0])
            self._check_table_allowed(table)
            iterator_type = str(args[1]) if len(args) > 1 and args[1] is not None else "LATEST"
            iterator_type = iterator_type.upper()
            if iterator_type not in {"LATEST", "TRIM_HORIZON", "AT_SEQUENCE_NUMBER"}:
                raise AdapterError("dynamodb streams.subscribe shard_iterator_type must be LATEST|TRIM_HORIZON|AT_SEQUENCE_NUMBER")
            filter_spec = args[2] if len(args) > 2 and isinstance(args[2], dict) else None
            timeout_s = float(args[3]) if len(args) > 3 and args[3] is not None else 0.5
            max_events = int(args[4]) if len(args) > 4 and args[4] is not None else 10
            return await self._streams_subscribe_async(table, iterator_type, filter_spec, timeout_s, max_events)
        if verb == "streams_unsubscribe":
            if not args:
                raise AdapterError("dynamodb streams.unsubscribe requires table_name")
            return await self._streams_unsubscribe_async(str(args[0]))
        return await asyncio.to_thread(self.call, target, args, context)

