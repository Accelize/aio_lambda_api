"""JSON utilities."""
from __future__ import annotations
from typing import Any as _Any, Callable as _Callable

try:
    from orjson import dumps as dumps_bytes, loads, JSONDecodeError
except ImportError:
    from json import loads, dumps, JSONDecodeError  # type: ignore

    def dumps_bytes(  # type: ignore
        value: _Any, default: _Callable[..., _Any] | None = None, **_: _Any
    ) -> bytes:
        """Serialize to bytes JSON.

        Args:
            value: Input value.
            default: Default serializer.

        Returns:
            JSON bytes.
        """
        return dumps(value, default=default).encode()

else:

    def dumps(  # type: ignore
        value: _Any, default: _Callable[..., _Any] | None = None, **_: _Any
    ) -> str:
        """Serialize to str JSON.

        Args:
            value: Input value.
            default: Default serializer.

        Returns:
            JSON string.
        """
        return dumps_bytes(value, default=default).decode()


__all__ = ("dumps", "loads", "dumps_bytes", "JSONDecodeError")
