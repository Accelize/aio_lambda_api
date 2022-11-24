"""Backends."""
from __future__ import annotations
from abc import abstractmethod, ABC
from asyncio import gather
from importlib import import_module
from typing import Any, Iterable, Type
from jhalog import AsyncLogger
from aio_lambda_api.json import dumps
from aio_lambda_api._requests import Request
from aio_lambda_api._responses import Response
from aio_lambda_api.settings import BACKEND


class BackendBase(ABC):
    """Backend base."""

    __slots__ = ("_logger",)

    DEFAULT_JHALOG_BACKEND_CONFIG = dict(
        calculate_uptime=False, backend="stdout", json_dumps=dumps
    )

    def __init__(self, jhalog_config: dict[str, Any] | None = None) -> None:
        """Initialize instance."""
        kwargs: dict[str, Any] = self.DEFAULT_JHALOG_BACKEND_CONFIG.copy()
        if jhalog_config:
            kwargs.update(jhalog_config)
        self._logger = AsyncLogger(**kwargs)

    async def __aenter__(self) -> "BackendBase":
        await self._logger.__aenter__()
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Asynchronous context manager exit."""
        await self._logger.__aexit__()

    @property
    def logger(self) -> AsyncLogger:
        """Logger.

        Returns:
            Logger.
        """
        return self._logger

    @abstractmethod
    async def parse_request(self, *args: Any, **kwargs: Any) -> Request | list[Request]:
        """Parse request(s).

        Returns:
            Request(s).
        """

    @abstractmethod
    async def serialize_response(self, response: Response, request: Request) -> Any:
        """Serialize response.

        Args:
            response: Response.
            request: Request.

        Returns:
            Serialized response.
        """

    async def serialize_responses(
        self, resp_req: Iterable[tuple[Response, Request]]
    ) -> Any:
        """Serialize response.

        Args:
            resp_req: Response & request.

        Returns:
            Serialized response.
        """
        return gather(
            *(
                self.serialize_response(response, request)
                for response, request in resp_req
            )
        )


def get_backend(name: str | None) -> Type[BackendBase]:
    """Import backend.

    Args:
        name: Backend name.

    Returns:
        Backend class.
    """
    name = name or BACKEND
    element = f"{__name__}.{name}"
    try:
        module = import_module(element)
    except ImportError:
        from importlib.util import find_spec

        if find_spec(element) is not None:  # pragma: no cover
            raise
        raise NotImplementedError(f"Unsupported backend: {name}")
    return getattr(module, "Backend")  # type: ignore
