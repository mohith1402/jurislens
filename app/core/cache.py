"""Pluggable Caching and Distributed State Management Primitives for JurisLens AI.

Provides bounded memory LRU caching with TTL expiration (CWE-400 / CWE-770 defense)
and an extensible Redis adapter for multi-instance horizontal scalability.
"""

from abc import ABC, abstractmethod
from collections import OrderedDict
import logging
import threading
import time
from typing import Any, Generic, Iterator, List, Optional, Tuple, TypeVar

from app.core.config import settings

logger = logging.getLogger("jurislens.cache")

KT = TypeVar("KT")
VT = TypeVar("VT")


class BaseCache(ABC, Generic[KT, VT]):
    """Abstract interface defining the cache contract for JurisLens."""

    @abstractmethod
    def get(self, key: KT, default: Optional[VT] = None) -> Optional[VT]:
        """Retrieve an item from the cache."""
        pass

    @abstractmethod
    def set(self, key: KT, value: VT, ttl_seconds: Optional[int] = None) -> None:
        """Store an item in the cache with optional TTL."""
        pass

    @abstractmethod
    def pop(self, key: KT, default: Optional[VT] = None) -> Optional[VT]:
        """Remove and return an item from cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all entries from the cache."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of active entries."""
        pass

    @abstractmethod
    def __contains__(self, key: KT) -> bool:
        """Check if key exists and is non-expired."""
        pass


class BoundedLRUCache(BaseCache[KT, VT]):
    """
    Thread-safe Least-Recently-Used (LRU) bounded memory cache with optional TTL.

    Guarantees strict O(1) time complexity and a deterministic memory ceiling,
    preventing uncontrolled resource consumption and Out-Of-Memory denial of service.
    """

    def __init__(self, maxsize: int = 256, default_ttl_seconds: Optional[int] = None):
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self._maxsize = maxsize
        self._default_ttl = default_ttl_seconds
        # Stores: key -> (value, expires_at)
        self._store: OrderedDict[KT, Tuple[VT, Optional[float]]] = OrderedDict()
        self._lock = threading.RLock()

    @property
    def maxsize(self) -> int:
        """Maximum number of entries allowed before LRU eviction."""
        return self._maxsize

    def _is_expired(self, expires_at: Optional[float], now: float) -> bool:
        return expires_at is not None and now > expires_at

    def get(self, key: KT, default: Optional[VT] = None) -> Optional[VT]:
        """Retrieve an item from cache and refresh its recency."""
        with self._lock:
            if key not in self._store:
                return default

            value, expires_at = self._store[key]
            now = time.time()
            if self._is_expired(expires_at, now):
                del self._store[key]
                return default

            self._store.move_to_end(key)
            return value

    def set(self, key: KT, value: VT, ttl_seconds: Optional[int] = None) -> None:
        """Insert or update an entry, evicting the oldest item if at capacity."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        now = time.time()
        expires_at = (now + ttl) if ttl and ttl > 0 else None

        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, expires_at)

            # Evict least-recently-used entry if capacity is exceeded
            if len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    def pop(self, key: KT, default: Optional[VT] = None) -> Optional[VT]:
        """Remove and return an item from cache if present and non-expired."""
        with self._lock:
            if key not in self._store:
                return default
            value, expires_at = self._store.pop(key)
            if self._is_expired(expires_at, time.time()):
                return default
            return value

    def clear(self) -> None:
        """Purge all entries from the cache."""
        with self._lock:
            self._store.clear()

    def __getitem__(self, key: KT) -> VT:
        val = self.get(key)
        if val is None and key not in self:
            raise KeyError(key)
        return val  # type: ignore

    def __setitem__(self, key: KT, value: VT) -> None:
        self.set(key, value)

    def __contains__(self, key: KT) -> bool:
        with self._lock:
            if key not in self._store:
                return False
            _, expires_at = self._store[key]
            if self._is_expired(expires_at, time.time()):
                del self._store[key]
                return False
            return True

    def __len__(self) -> int:
        with self._lock:
            now = time.time()
            # Clean expired items on count inspection
            expired = [k for k, (_, exp) in self._store.items() if self._is_expired(exp, now)]
            for k in expired:
                del self._store[k]
            return len(self._store)

    def __iter__(self) -> Iterator[KT]:
        with self._lock:
            return iter(list(self.keys()))

    def keys(self) -> List[KT]:
        """Return a snapshot of active, unexpired keys in LRU order."""
        with self._lock:
            now = time.time()
            return [k for k, (_, exp) in self._store.items() if not self._is_expired(exp, now)]

    def values(self) -> List[VT]:
        """Return a snapshot of active, unexpired values in LRU order."""
        with self._lock:
            now = time.time()
            return [v for _, (v, exp) in self._store.items() if not self._is_expired(exp, now)]

    def items(self) -> List[Tuple[KT, VT]]:
        """Return a snapshot of active, unexpired (key, value) pairs."""
        with self._lock:
            now = time.time()
            return [(k, v) for k, (v, exp) in self._store.items() if not self._is_expired(exp, now)]


class RedisCacheAdapter(BaseCache[str, Any]):
    """
    Distributed Redis Cache Adapter for horizontal scaling across multi-instance clusters.
    Gracefully falls back to local in-memory BoundedLRUCache if Redis is unavailable.
    """

    def __init__(self, redis_url: str, default_ttl_seconds: int = 3600, fallback_maxsize: int = 256):
        self._fallback = BoundedLRUCache(maxsize=fallback_maxsize, default_ttl_seconds=default_ttl_seconds)
        self._redis = None
        self._connected = False
        self.default_ttl = default_ttl_seconds

        try:
            import redis
            self._redis = redis.from_url(redis_url, decode_responses=False, socket_timeout=2.0)
            self._redis.ping()
            self._connected = True
            logger.info(f"Connected to distributed Redis cache at {redis_url}")
        except Exception as e:
            logger.warning(f"Could not connect to Redis ({e}). Operating in memory-bounded fallback mode.")
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Whether the distributed Redis backend is actively connected."""
        return self._connected

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        if not self._connected or not self._redis:
            return self._fallback.get(key, default)
        try:
            import pickle
            raw = self._redis.get(f"jurislens:{key}")
            if raw is None:
                return default
            return pickle.loads(raw)
        except Exception as e:
            logger.warning(f"Redis get error for {key}: {e}. Falling back to local cache.")
            return self._fallback.get(key, default)

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        self._fallback.set(key, value, ttl_seconds)
        if self._connected and self._redis:
            try:
                import pickle
                ttl = ttl_seconds or self.default_ttl
                self._redis.setex(f"jurislens:{key}", ttl, pickle.dumps(value))
            except Exception as e:
                logger.warning(f"Redis set error for {key}: {e}")

    def pop(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        val = self._fallback.pop(key, default)
        if self._connected and self._redis:
            try:
                self._redis.delete(f"jurislens:{key}")
            except Exception as e:
                logger.warning(f"Redis delete error for {key}: {e}")
        return val

    def clear(self) -> None:
        self._fallback.clear()
        if self._connected and self._redis:
            try:
                # Clear all jurislens prefixed keys
                keys = self._redis.keys("jurislens:*")
                if keys:
                    self._redis.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        if not self._connected or not self._redis:
            return key in self._fallback
        try:
            return bool(self._redis.exists(f"jurislens:{key}"))
        except Exception:
            return key in self._fallback

    def __len__(self) -> int:
        return len(self._fallback)


# Compatibility alias: BoundedCache maps directly to BoundedLRUCache
BoundedCache = BoundedLRUCache


def get_cache_backend(
    name: str = "default",
    maxsize: Optional[int] = None,
    ttl_seconds: Optional[int] = None,
) -> BaseCache:
    """
    Factory function returning the configured cache backend.
    Enables zero-code switching between local BoundedLRUCache and distributed Redis.
    """
    effective_maxsize = maxsize or settings.CACHE_MAX_ENTRIES
    effective_ttl = ttl_seconds or settings.CACHE_DEFAULT_TTL_SECONDS

    if settings.CACHE_BACKEND.lower() == "redis" and settings.REDIS_URL:
        return RedisCacheAdapter(
            redis_url=settings.REDIS_URL,
            default_ttl_seconds=effective_ttl,
            fallback_maxsize=effective_maxsize,
        )

    return BoundedLRUCache(maxsize=effective_maxsize, default_ttl_seconds=effective_ttl)
