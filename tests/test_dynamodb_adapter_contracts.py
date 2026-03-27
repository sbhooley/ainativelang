import os
import sys
import asyncio
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.dynamodb import DynamoDBAdapter
from runtime.adapters.base import AdapterError


class _FakeDDBClient:
    def __init__(self):
        self.tables = {"users": {}}

    def list_tables(self, Limit=100, ExclusiveStartTableName=None):
        return {"TableNames": list(self.tables.keys())[:Limit]}

    def describe_table(self, TableName):
        return {
            "Table": {
                "TableName": TableName,
                "TableStatus": "ACTIVE",
                "LatestStreamArn": f"arn:aws:dynamodb:us-east-1:1:table/{TableName}/stream/x",
            }
        }

    def get_item(self, TableName, Key, ConsistentRead=False):
        item = self.tables.get(TableName, {}).get(str(Key))
        return {"Item": item} if item else {}

    def put_item(self, TableName, Item, ReturnValues="NONE"):
        self.tables.setdefault(TableName, {})[str(Item)] = Item
        return {"Attributes": Item if ReturnValues != "NONE" else None}

    def update_item(self, **kwargs):
        return {"Attributes": {"id": {"S": "1"}, "name": {"S": "alice"}}}

    def delete_item(self, **kwargs):
        return {"Attributes": None}

    def query(self, **kwargs):
        return {"Items": [{"id": {"S": "1"}}], "Count": 1}

    def scan(self, **kwargs):
        return {"Items": [{"id": {"S": "1"}}], "Count": 1}

    def batch_get_item(self, RequestItems):
        out = {}
        for table in RequestItems.keys():
            out[table] = [{"id": {"S": "1"}}]
        return {"Responses": out}

    def batch_write_item(self, RequestItems):
        return {"UnprocessedItems": {}}

    def transact_get_items(self, TransactItems):
        return {"Responses": [{"Item": {"id": {"S": "1"}}}]}

    def transact_write_items(self, TransactItems):
        return {}


class _FakeStreamsClient:
    def describe_stream(self, StreamArn):
        return {"StreamDescription": {"Shards": [{"ShardId": "shard-0001"}]}}

    def get_shard_iterator(self, **kwargs):
        return {"ShardIterator": "it-1"}

    def get_records(self, ShardIterator, Limit=100):
        recs = [
            {
                "eventName": "INSERT",
                "eventID": "e1",
                "eventSourceARN": "arn:aws:dynamodb:us-east-1:1:table/users/stream/x",
                "dynamodb": {
                    "Keys": {"pk": {"S": "u#1"}, "sk": {"S": "profile"}},
                    "NewImage": {"pk": {"S": "u#1"}, "sk": {"S": "profile"}, "name": {"S": "alice"}},
                },
            },
            {
                "eventName": "MODIFY",
                "eventID": "e2",
                "eventSourceARN": "arn:aws:dynamodb:us-east-1:1:table/users/stream/x",
                "dynamodb": {
                    "Keys": {"pk": {"S": "u#1"}, "sk": {"S": "profile"}},
                    "OldImage": {"name": {"S": "alice"}},
                    "NewImage": {"name": {"S": "alice2"}},
                },
            },
            {
                "eventName": "REMOVE",
                "eventID": "e3",
                "eventSourceARN": "arn:aws:dynamodb:us-east-1:1:table/users/stream/x",
                "dynamodb": {
                    "Keys": {"pk": {"S": "u#1"}, "sk": {"S": "profile"}},
                    "OldImage": {"name": {"S": "alice2"}},
                },
            },
        ]
        return {"Records": recs, "NextShardIterator": None}


class _FakeSerializer:
    def serialize(self, value):
        if isinstance(value, str):
            return {"S": value}
        if isinstance(value, bool):
            return {"BOOL": value}
        if isinstance(value, int):
            return {"N": str(value)}
        if value is None:
            return {"NULL": True}
        raise ValueError("unsupported")


class _FakeDeserializer:
    def deserialize(self, value):
        if "S" in value:
            return value["S"]
        if "N" in value:
            return int(value["N"])
        if "BOOL" in value:
            return bool(value["BOOL"])
        if "NULL" in value:
            return None
        return value


def _install_fake_boto3(monkeypatch):
    fake_client = _FakeDDBClient()
    fake_streams = _FakeStreamsClient()
    fake_boto3 = SimpleNamespace(
        session=SimpleNamespace(
            Session=lambda region_name=None: SimpleNamespace(
                client=lambda name, **k: (fake_streams if name == "dynamodbstreams" else fake_client)
            )
        )
    )
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore.config", SimpleNamespace(Config=lambda **kwargs: SimpleNamespace(**kwargs)))
    monkeypatch.setitem(
        sys.modules,
        "boto3.dynamodb.types",
        SimpleNamespace(TypeSerializer=lambda: _FakeSerializer(), TypeDeserializer=lambda: _FakeDeserializer()),
    )


def test_dynamodb_basic_contract(monkeypatch):
    _install_fake_boto3(monkeypatch)
    adp = DynamoDBAdapter(region="us-east-1", allow_write=True, allow_tables=["users"])
    assert "users" in adp.call("list_tables", [], {})["tables"]
    assert adp.call("describe_table", ["users"], {})["table"]["TableName"] == "users"
    put_out = adp.call("put", ["users", {"id": "1", "name": "alice"}], {})
    assert "attributes" in put_out
    get_out = adp.call("get", ["users", {"id": "1"}], {})
    assert isinstance(get_out, dict)
    qry = adp.call("query", ["users", "id = :id", {":id": "1"}], {})
    assert qry["count"] == 1


def test_dynamodb_write_gate(monkeypatch):
    _install_fake_boto3(monkeypatch)
    adp = DynamoDBAdapter(region="us-east-1", allow_write=False, allow_tables=["users"])
    try:
        adp.call("put", ["users", {"id": "1"}], {})
        assert False, "expected write block"
    except Exception as e:
        assert isinstance(e, AdapterError)
        assert "allow_write" in str(e)


def test_dynamodb_table_allowlist(monkeypatch):
    _install_fake_boto3(monkeypatch)
    adp = DynamoDBAdapter(region="us-east-1", allow_write=True, allow_tables=["users"])
    try:
        adp.call("get", ["other", {"id": "1"}], {})
        assert False, "expected table block"
    except Exception as e:
        assert isinstance(e, AdapterError)
        assert "allowlist" in str(e)


def test_dynamodb_streams_contract_sync_and_async(monkeypatch):
    _install_fake_boto3(monkeypatch)
    adp = DynamoDBAdapter(region="us-east-1", allow_write=False, allow_tables=["users"])
    sync_out = adp.call("streams.subscribe", ["users", "LATEST", {"event_names": ["INSERT", "REMOVE"]}, 0.2, 10], {})
    assert isinstance(sync_out["events"], list)
    assert all(e["eventName"] in {"INSERT", "REMOVE"} for e in sync_out["events"])
    async_out = asyncio.run(adp.call_async("streams.subscribe", ["users", "LATEST", {"event_names": ["MODIFY"]}, 0.2, 10], {}))
    assert isinstance(async_out["events"], list)
    assert any(e["eventName"] == "MODIFY" for e in async_out["events"])
    unsub = asyncio.run(adp.call_async("streams.unsubscribe", ["users"], {}))
    assert isinstance(unsub["removed"], bool)
