"""Pytest configuration."""
from __future__ import annotations
from base64 import b64encode
from json import dumps
from typing import Any
from secrets import token_hex


class _Context:
    """Lambda context."""

    aws_request_id = token_hex(8)


def init_event_context(
    path: str = "/",
    method: str = "GET",
    body: Any | None = None,
    headers: dict[str, str] | None = None,
    version: int = 2,
) -> tuple[dict[str, Any], Any]:
    """Init a mocked event context.

    Args:
        path: HTTP path.
        method: HTTP method.
        body: Body.
        headers: HTTP headers.
        version: Event version.

    Returns:
        Event, context.
    """
    context = _Context()
    encoded = False
    if isinstance(body, bytes):
        body = b64encode(body).decode()
        encoded = True
    elif body is not None:
        body = dumps(body)
    if headers is None:
        headers = dict()

    if version == 1:
        event = {
            "resource": path,
            "path": path,
            "httpMethod": method,
            "headers": headers,
            "requestContext": {
                "resourcePath": path,
                "httpMethod": method,
                "path": path,
                "requestId": token_hex(8),
            },
            "body": body,
            "isBase64Encoded": encoded,
        }
    elif version == 2:
        event = {
            "version": "2.0",
            "rawPath": path,
            "headers": headers,
            "requestContext": {
                "http": {
                    "method": method,
                    "path": path,
                },
                "requestId": token_hex(8),
            },
            "isBase64Encoded": encoded,
            "body": body,
        }
    else:
        raise ValueError("Invalid version.")
    return event, context
