"""Requests."""
from __future__ import annotations
from typing import Any
from aio_lambda_api.json import loads, JSONDecodeError


class Request:
    """Request."""

    __slots__ = ["_headers", "_body", "_json", "_path", "_method", "_raises_exceptions"]

    def __init__(
        self,
        path: str,
        method: str,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        raises_exceptions: bool = False,
    ) -> None:
        self._headers = (
            {key.lower(): value for key, value in headers.items()}
            if headers
            else dict()
        )
        if body is not None:
            self._body = body
        self._path = path
        self._method = method
        self._raises_exceptions = raises_exceptions

    @property
    def path(self) -> str:
        """HTTP route path.

        Returns:
            Path.
        """
        return self._path

    @property
    def method(self) -> str:
        """HTTP method.

        Returns:
            Method.
        """
        return self._method

    @property
    def headers(self) -> dict[str, str]:
        """HTTP headers.

        Returns:
            Headers.
        """
        return self._headers

    async def body(self) -> bytes | None:
        """Body.

        Returns:
            Body.
        """
        try:
            return self._body
        except AttributeError:
            return None

    async def json(self) -> Any:
        """JSON body.

        Returns:
            JSON deserialized body.
        """
        try:
            return self._json
        except AttributeError:
            body = await self.body()
            if body is not None:
                try:
                    body = loads(body)
                except JSONDecodeError:
                    pass
            self._json: Any = body
            return body

    @property
    def server_id(self) -> str | None:
        """Server ID.

        Returns:
            Server ID.
        """
        return None

    @property
    def raises_exceptions(self) -> bool:
        """If True, raises exceptions.

        Returns:
            Boolean.
        """
        return self._raises_exceptions
