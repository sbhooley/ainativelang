"""
Adapter interface for AI-Native Lang runtime.
Implement these to plug in real backends (Prisma, Stripe, HTTP, etc.).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class DBAdapter(ABC):
    """Backend for db.F (find), db.G (get one), db.P (create), db.D (delete)."""

    @abstractmethod
    def find(self, entity: str, fields: str = "*") -> List[Dict[str, Any]]:
        """Return list of entities (e.g. db.F Product *)."""
        pass

    def get(self, entity: str, id_value: Any) -> Optional[Dict[str, Any]]:
        """Return one entity by id (e.g. db.G Product 1)."""
        rows = self.find(entity, "*")
        for r in rows:
            if r.get("id") == id_value:
                return r
        return None

    def create(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create one entity (e.g. db.P Order {...})."""
        raise NotImplementedError("db.P")

    def delete(self, entity: str, id_value: Any) -> bool:
        """Delete one entity (e.g. db.D Order 1)."""
        raise NotImplementedError("db.D")


class APIAdapter(ABC):
    """Backend for api.G (GET), api.P (POST), etc."""

    @abstractmethod
    def get(self, path: str) -> Any:
        """HTTP GET path -> response body."""
        pass

    def post(self, path: str, body: Optional[Dict] = None) -> Any:
        """HTTP POST path with body."""
        raise NotImplementedError("api.P")


class PayAdapter(ABC):
    """Backend for P (payment intent)."""

    @abstractmethod
    def create_intent(
        self,
        name: str,
        amount: str,
        currency: str,
        desc: str = "",
    ) -> Dict[str, Any]:
        """Create payment intent; return { client_secret, ... }."""
        pass


class ScrapeAdapter(ABC):
    """Backend for Sc (scrape)."""

    @abstractmethod
    def scrape(self, name: str, url: str, selectors: Dict[str, str]) -> Dict[str, Any]:
        """Run scraper; return dict of field -> value."""
        pass


class AdapterRegistry:
    """Holds db, api, pay, scrape adapters. Used by ExecutionEngine."""

    def __init__(
        self,
        db: Optional[DBAdapter] = None,
        api: Optional[APIAdapter] = None,
        pay: Optional[PayAdapter] = None,
        scrape: Optional[ScrapeAdapter] = None,
    ):
        self.db = db
        self.api = api
        self.pay = pay
        self.scrape = scrape

    def get_db(self) -> DBAdapter:
        if self.db is None:
            raise RuntimeError("No db adapter registered")
        return self.db

    def get_api(self) -> APIAdapter:
        if self.api is None:
            raise RuntimeError("No api adapter registered")
        return self.api

    def get_pay(self) -> PayAdapter:
        if self.pay is None:
            raise RuntimeError("No pay adapter registered")
        return self.pay

    def get_scrape(self) -> ScrapeAdapter:
        if self.scrape is None:
            raise RuntimeError("No scrape adapter registered")
        return self.scrape
