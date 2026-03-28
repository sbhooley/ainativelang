"""Retry decorator with exponential backoff for LLM adapters."""

import time
import functools
from typing import Any, Callable, Tuple
import httpx

def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retry_statuses: Tuple[int, ...] = (429, 500, 502, 503, 504),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that retries on HTTP errors with exponential backoff."""
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except httpx.HTTPError as e:
                    status = getattr(e.response, "status_code", None) if hasattr(e, "response") else None
                    if status not in retry_statuses or attempt >= max_attempts - 1:
                        raise
                    attempt += 1
                    delay = base_delay * (2 ** (attempt - 1))
                    time.sleep(delay)
        return wrapper
    return decorator
