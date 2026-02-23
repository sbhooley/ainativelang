"""Mock adapters for development; return sample data based on entity/type."""
from typing import Any, Dict, List, Optional

from .base import APIAdapter, AdapterRegistry, DBAdapter, PayAdapter, ScrapeAdapter


class MockDBAdapter(DBAdapter):
    """Returns sample rows; optionally accept types for field names."""

    def __init__(self, types: Optional[Dict[str, Dict[str, Any]]] = None):
        self.types = types or {}

    def _sample_row(self, entity: str) -> Dict[str, Any]:
        fields = self.types.get(entity, {}).get("fields", {})
        row = {}
        for k, v in (list(fields.items())[:8] if fields else [("id", "I"), ("name", "S")]):
            if v and ("I" in v or "F" in v):
                row[k] = 1
            else:
                row[k] = "sample"
        return row

    def find(self, entity: str, fields: str = "*") -> List[Dict[str, Any]]:
        return [self._sample_row(entity), self._sample_row(entity)]

    def get(self, entity: str, id_value: Any) -> Optional[Dict[str, Any]]:
        r = self._sample_row(entity)
        r["id"] = id_value
        return r

    def create(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        r = self._sample_row(entity)
        r.update(data)
        return r


class MockAPIAdapter(APIAdapter):
    def get(self, path: str) -> Any:
        return {"data": []}


class MockPayAdapter(PayAdapter):
    def create_intent(
        self,
        name: str,
        amount: str,
        currency: str,
        desc: str = "",
    ) -> Dict[str, Any]:
        return {"client_secret": "mock_secret", "id": "mock_pi"}


class MockScrapeAdapter(ScrapeAdapter):
    def scrape(self, name: str, url: str, selectors: Dict[str, str]) -> Dict[str, Any]:
        return {k: "mock_value" for k in selectors}


def mock_registry(types: Optional[Dict[str, Dict[str, Any]]] = None) -> AdapterRegistry:
    """Default registry with mock adapters; pass ir['types'] for entity-aware mocks."""
    return AdapterRegistry(
        db=MockDBAdapter(types),
        api=MockAPIAdapter(),
        pay=MockPayAdapter(),
        scrape=MockScrapeAdapter(),
    )
