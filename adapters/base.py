"""
Adapter interfaces for AI-Native Lang runtime.
Implement these to plug in real backends (Prisma, Stripe, HTTP, cache, queue, txn, auth).
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

    def query(
        self,
        entity: str,
        query: str,
        params: Any = None,
        partition: Any = None,
    ) -> List[Dict[str, Any]]:
        """Parameterized read. The query text is a source literal.

        ``params`` are bound by the host. Interpolating them into the query
        string is a contract violation. ``partition`` is the partition key,
        or the literal ``*`` when the graph asked for a cross-partition read.
        The engine caps rows and bytes before the result enters the frame.
        """
        raise NotImplementedError("db.Q")

    def merge(
        self,
        entity: str,
        id_value: Any,
        patch: Dict[str, Any],
        etag: Any = None,
    ) -> Dict[str, Any]:
        """Shallow field merge. ``etag`` is the caller's If-Match token.

        The host must not write when the token does not match. Two stages
        that share a document otherwise clobber each other.
        """
        raise NotImplementedError("db.M")


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


class CacheAdapter(ABC):
    """Backend for cache capability steps."""

    @abstractmethod
    def get(self, namespace: str, key: str) -> Any:
        """Lookup cache value by namespace+key; return None on miss."""
        pass

    @abstractmethod
    def set(self, namespace: str, key: str, value: Any, ttl_s: int = 0) -> None:
        """Store cache value with optional ttl in seconds."""
        pass


class QueueAdapter(ABC):
    """Backend for queue capability steps."""

    @abstractmethod
    def push(self, queue: str, value: Any) -> str:
        """Push value to queue and return message id."""
        pass


class TxnAdapter(ABC):
    """Backend for transaction capability steps."""

    @abstractmethod
    def begin(self, name: str) -> str:
        """Start transaction scope and return transaction id."""
        pass

    @abstractmethod
    def commit(self, name: str) -> None:
        """Commit transaction scope."""
        pass

    @abstractmethod
    def rollback(self, name: str) -> None:
        """Rollback transaction scope."""
        pass


class AuthAdapter(ABC):
    """Backend for auth capability checks."""

    @abstractmethod
    def validate(self, token_or_value: str) -> bool:
        """Return True when auth value/token is valid."""
        pass


class AdapterRegistry:
    """Holds runtime adapters. Used by ExecutionEngine."""

    def __init__(
        self,
        db: Optional[DBAdapter] = None,
        api: Optional[APIAdapter] = None,
        pay: Optional[PayAdapter] = None,
        scrape: Optional[ScrapeAdapter] = None,
        cache: Optional[CacheAdapter] = None,
        queue: Optional[QueueAdapter] = None,
        txn: Optional[TxnAdapter] = None,
        auth: Optional[AuthAdapter] = None,
    ):
        self.db = db
        self.api = api
        self.pay = pay
        self.scrape = scrape
        self.cache = cache
        self.queue = queue
        self.txn = txn
        self.auth = auth

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

    def get_cache(self) -> CacheAdapter:
        if self.cache is None:
            raise RuntimeError("No cache adapter registered")
        return self.cache

    def get_queue(self) -> QueueAdapter:
        if self.queue is None:
            raise RuntimeError("No queue adapter registered")
        return self.queue

    def get_txn(self) -> TxnAdapter:
        if self.txn is None:
            raise RuntimeError("No txn adapter registered")
        return self.txn

    def get_auth(self) -> AuthAdapter:
        if self.auth is None:
            raise RuntimeError("No auth adapter registered")
        return self.auth
