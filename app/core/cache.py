"""Bounded thread-safe caching primitives for JurisLens AI.

Guarantees strict O(1) time complexity and bounded memory consumption (CWE-400 / CWE-770).
"""

from collections import OrderedDict
import threading
from typing import Generic, Iterator, List, Optional, Tuple, TypeVar

KT = TypeVar("KT")
VT = TypeVar("VT")


class BoundedCache(Generic[KT, VT]):
    """
    Thread-safe Least-Recently-Used (LRU) bounded memory cache.

    Guarantees strict O(1) access and insertion while preventing
    uncontrolled resource consumption and memory exhaustion.
    """

    def __init__(self, maxsize: int = 128):
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self._maxsize = maxsize
        self._store: OrderedDict[KT, VT] = OrderedDict()
        self._lock = threading.RLock()

    @property
    def maxsize(self) -> int:
        """Maximum number of entries allowed before LRU eviction."""
        return self._maxsize

    def get(self, key: KT, default: Optional[VT] = None) -> Optional[VT]:
        """Retrieve an item from cache and mark it as recently accessed."""
        with self._lock:
            if key not in self._store:
                return default
            self._store.move_to_end(key)
            return self._store[key]

    def set(self, key: KT, value: VT) -> None:
        """Insert or update an item, evicting the oldest entry if at capacity."""
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = value
            if len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    def pop(self, key: KT, default: Optional[VT] = None) -> Optional[VT]:
        """Remove and return an item from cache if present."""
        with self._lock:
            return self._store.pop(key, default)

    def __getitem__(self, key: KT) -> VT:
        with self._lock:
            if key not in self._store:
                raise KeyError(key)
            self._store.move_to_end(key)
            return self._store[key]

    def __setitem__(self, key: KT, value: VT) -> None:
        self.set(key, value)

    def __contains__(self, key: KT) -> bool:
        with self._lock:
            return key in self._store

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def __iter__(self) -> Iterator[KT]:
        with self._lock:
            return iter(list(self._store.keys()))

    def clear(self) -> None:
        """Empty the cache."""
        with self._lock:
            self._store.clear()

    def keys(self) -> List[KT]:
        """Return a copy of cache keys in LRU order."""
        with self._lock:
            return list(self._store.keys())

    def values(self) -> List[VT]:
        """Return a copy of cache values in LRU order."""
        with self._lock:
            return list(self._store.values())

    def items(self) -> List[Tuple[KT, VT]]:
        """Return a copy of cache (key, value) pairs."""
        with self._lock:
            return list(self._store.items())
