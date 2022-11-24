"""AWS lambda backend."""
from __future__ import annotations
from base64 import b64decode, b64encode
from os import getenv
from typing import Any, TYPE_CHECKING, Generator, Iterable
from jhalog.exception_handlers.botocore import get_status_from_botocore_error
from aio_lambda_api.json import loads
from aio_lambda_api._backends import BackendBase
from aio_lambda_api._requests import Request as _Request
from aio_lambda_api._responses import Response

if TYPE_CHECKING:  # pragma: no cover
    from botocore.client import Config


class Request(_Request):
    """AWS lambda request.

    Args:
        event: Lambda event.
        context: Lambda context.
    """

    __slots__ = ["event", "_context"]

    def __init__(
        self, event: dict[str, Any], context: Any, raises_exceptions: bool = True
    ) -> None:
        self.event = event
        self._context = context

        request_context = event["requestContext"]
        try:
            # AWS API Gateway HTTP API
            http = request_context["http"]
        except KeyError:
            # AWS API Gateway REST API
            method = request_context["httpMethod"]
            path = request_context["path"]
        else:
            method = http["method"]
            path = http["path"]
        headers = event.get("headers") or dict()
        try:
            headers.setdefault("x-request-id", event["requestContext"]["requestId"])
        except KeyError:
            pass

        _Request.__init__(
            self,
            path=path,
            method=method,
            headers=headers,
            raises_exceptions=raises_exceptions,
        )

    async def body(self) -> bytes | None:
        """Body.

        Returns:
            Body.
        """
        try:
            return self._body
        except AttributeError:
            body = self.event.get("body")
            if body is not None:
                body = body.encode()
                if self.event.get("isBase64Encoded", False):
                    body = b64decode(body)
            self._body = body
            return body  # type: ignore

    @property
    def server_id(self) -> str:
        """Server ID.

        Returns:
            Server ID.
        """
        return self._context.aws_request_id  # type: ignore


class Backend(BackendBase):
    """AWS lambda backend."""

    _botocore_config: "Config | None" = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._logger.add_exception_handler(get_status_from_botocore_error)

    async def parse_request(  # type: ignore
        self, event: dict[str, Any], context: Any
    ) -> Request | list[Request] | None:
        """Parse request(s) in AWS API Gateway format.

        The request can be alone or sent by batch using AWS SQS.

        Args:
            event: Lambda event.
            context: Lambda context.

        Returns:
            Request(s).
        """
        if "requestContext" in event:
            return Request(event, context)

        try:
            event_source = event["eventSource"]
        except KeyError:
            try:
                event_source = event["Records"][0]["eventSource"]
            except (IndexError, KeyError):
                return []
        return [
            Request(
                record_event,
                context,
                raises_exceptions=record_event.get("eventRaisesExceptions", True),
            )
            for record_event in getattr(
                self, f"_parse_event_{event_source.split(':', 1)[1]}"
            )(event)
        ]

    @staticmethod
    def _parse_event_mq(event: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
        """Parse AWS MQ event source.

        Args:
            event: MQ event with data in AWS API Gateway format.

        Returns:
            Request(s).
        """
        for record in event["messages"]:
            record_event = loads(record.pop("data"))
            record_event["eventSource"] = "aws:mq"
            record_event["eventData"] = record
            yield record_event

    @staticmethod
    def _parse_event_sqs(
        event: dict[str, Any]
    ) -> Generator[dict[str, Any], None, None]:
        """Parse AWS SQS event source.

        Args:
            event: SQS queue event with bodies in AWS API Gateway format.

        Returns:
            Request(s).
        """
        for record in event["Records"]:
            record_event = loads(record.pop("body"))
            record_event["eventSource"] = "aws:sqs"
            record_event["eventData"] = record
            record_event["eventRaisesExceptions"] = False
            yield record_event

    @staticmethod
    def _parse_event_sns(
        event: dict[str, Any]
    ) -> Generator[dict[str, Any], None, None]:
        """Parse AWS SNS event source.

        Args:
            event: SNS notification event with messages in AWS API Gateway format.

        Returns:
            Request(s).
        """
        for record in event["Records"]:
            record_event = loads(record["Sns"].pop("Message"))
            record_event["eventSource"] = "aws:sns"
            record_event["eventData"] = record
            yield record_event

    @staticmethod
    def _serialize_event_sqs(
        resp_req: Iterable[tuple[Response, Request]]
    ) -> dict[str, list[dict[str, str]]] | None:
        """AWS SQS queue event source for AWS Lambda entry point.

        Args:
            resp_req: Response & request.

        Returns:
            Lambda SQS event response.
        """
        failures = [
            request.event["eventData"]["messageId"]
            for response, request in resp_req
            if response.status_code >= 400
        ]
        if failures:
            return dict(
                batchItemFailures=[
                    dict(itemIdentifier=message_id) for message_id in failures
                ]
            )
        return None

    async def serialize_response(self, response: Response, request: _Request) -> Any:
        """Serialize response.

        Args:
            response: Response.
            request: Request.

        Returns:
            API gateways compatible response.
        """
        is_base64_encoded = False
        body = await response.body()
        if isinstance(body, (bytes, bytearray, memoryview)):
            body = b64encode(body).decode()
            is_base64_encoded = True
        return dict(
            body=body,
            statusCode=str(response.status_code),
            headers=response.headers,
            isBase64Encoded=is_base64_encoded,
        )

    async def serialize_responses(  # type: ignore
        self, resp_req: Iterable[tuple[Response, Request]]
    ) -> Any:
        """Serialize response.

        Args:
            resp_req: Response & request.

        Returns:
            Serialized response.
        """
        resp_req = tuple(resp_req)
        try:
            first_req = resp_req[0][1]
        except IndexError:
            return None
        name = f"_serialize_event_{first_req.event['eventSource'].split(':', 1)[1]}"
        try:
            method = getattr(self, name)
        except AttributeError:
            # Some services do not check returned data
            return None
        return method(resp_req)

    @classmethod
    def botocore_config(cls, speedup: bool = True) -> "Config":
        """Default Boto client/resource configuration.

        Args:
            speedup: If True, patch botocore to Speed up JSON serialization.

        Returns:
            Botocore config.
        """
        if cls._botocore_config is not None:
            return cls._botocore_config
        elif speedup:
            cls._patch_botocore()

        from botocore.client import Config
        from aio_lambda_api.settings import CONNECTION_TIMEOUT, READ_TIMEOUT

        cls._botocore_config = Config(
            connect_timeout=CONNECTION_TIMEOUT,
            read_timeout=READ_TIMEOUT,
            parameter_validation=bool(getenv("BOTO_PARAMETER_VALIDATION", "")),
            max_pool_connections=int(getenv("BOTO_MAX_POOL_CONNECTIONS", 100)),
            retries=dict(mode="standard"),
        )
        return cls._botocore_config

    @staticmethod
    def _patch_botocore() -> None:
        """Patch Botocore to speed up Botocore JSON handling."""
        from botocore import serialize, parsers
        import aio_lambda_api.json

        serialize.json = aio_lambda_api.json  # type: ignore
        parsers.json = aio_lambda_api.json  # type: ignore
