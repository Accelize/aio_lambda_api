"""Exceptions."""
from __future__ import annotations
from typing import Any as _Any

__all__ = ("HTTPException", "ValidationError")


try:
    from pydantic import ValidationError
except ImportError:

    class ValidationError(Exception):  # type: ignore
        """Validation Error."""

        __slots__ = ["_errors"]

        def __init__(self, errors: _Any) -> None:
            self._errors = errors

        def errors(self) -> _Any:
            """Returns errors.

            Returns:
                Errors.
            """
            return self._errors


class HTTPException(Exception):
    """Exception returned as result to client with an HTTP return code."""

    __slots__ = ["status_code", "_error_detail", "_detail", "headers"]

    def __init__(
        self,
        status_code: int,
        detail: _Any = None,
        headers: dict[str, _Any] | None = None,
        *,
        error_detail: _Any | None = None,
    ) -> None:
        self.status_code = int(status_code)
        self._detail = detail
        self.headers = headers
        self._error_detail = error_detail
        Exception.__init__(self)

    @property
    def detail(self) -> _Any:
        """Error detail.

        Returns:
            Error detail.
        """
        return self._detail

    @property
    def error_detail(self) -> str | None:
        """Internal error details.

        Shown in logs, but not returned to caller.

        Returns:
            Message.
        """
        if self._error_detail:
            return str(self._error_detail)
        elif self._detail:
            return str(self._detail)
        return None
