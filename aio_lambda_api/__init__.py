"""Async AWS Lambda handler."""
from aio_lambda_api._core import Handler, get_logger
from aio_lambda_api.exceptions import HTTPException
from aio_lambda_api.json import loads, dumps
from aio_lambda_api._requests import Request
from aio_lambda_api._responses import JSONResponse, Response

__all__ = (
    "Handler",
    "HTTPException",
    "loads",
    "dumps",
    "settings",
    "get_logger",
    "JSONResponse",
    "Response",
    "Request",
)

try:
    import uvloop as _uvloop  # noqa
except ImportError:  # pragma: no cover
    pass
else:
    _uvloop.install()
