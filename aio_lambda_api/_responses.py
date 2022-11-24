"""Responses."""
from __future__ import annotations
from typing import Any, Union
from jhalog import LogEvent
from aio_lambda_api.json import dumps
from aio_lambda_api.status import get_status_message


Body = Union[str, bytes, bytearray, memoryview]


class Response:
    """Response."""

    _MEDIA_TYPE: str | None = None
    charset = "utf-8"

    __slots__ = ["_content", "_status_code", "_headers", "_media_type"]

    def __init__(
        self,
        content: Any | None = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        media_type: str | None = None,
    ) -> None:
        self._content = content
        self._media_type = media_type or self._MEDIA_TYPE
        self.status_code = status_code
        self._headers = headers or dict()
        self._headers["x-request-id"] = LogEvent.from_context().id

    @property
    def headers(self) -> dict[str, str]:
        """HTTP headers.

        Returns:
            Headers.
        """
        return self._headers

    @property
    def status_code(self) -> int:
        """HTTP Status code.

        Returns:
            Status code.
        """
        return self._status_code

    @status_code.setter
    def status_code(self, value: int) -> None:
        """HTTP Status code.

        Args:
            value: Status code.
        """
        if self._content is None and value == 200:
            value = 204
        self._status_code = LogEvent.from_context().status_code = value

    @property
    def content(self) -> Any:
        """Response content.

        Returns:
            Content.
        """
        return self._content

    @content.setter
    def content(self, value: Any) -> None:
        """Response content.

        Args:
            value: Content.
        """
        self._content = value
        if value is not None and self._status_code == 204:
            self._status_code = LogEvent.from_context().status_code = 200

    async def _render(self, content: Any) -> Body:
        """Render content for response in str or bytes.

        Args:
            content: Body content.

        Returns:
            Rendered content.
        """
        return content  # type: ignore

    async def body(self) -> Body | None:
        """Body.

        Returns:
            Rendered body.
        """
        body: Body | None = None

        if self._content is None and self._status_code >= 400:
            self._content = dict(detail=get_status_message(self._status_code))

        if self._content is not None:
            body = await self._render(self._content)
            self._headers["content-length"] = str(len(body))
            if self._media_type is not None:
                self._headers["content-type"] = self._media_type

        return body


class JSONResponse(Response):
    """JSON Response."""

    _MEDIA_TYPE = "application/json"

    async def _render(self, content: Any) -> str:
        """Render content for response in JSON str.

        Args:
            content: Body content.

        Returns:
            JSON content.
        """
        return dumps(content)
