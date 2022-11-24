"""AWS Lambda tests."""
from base64 import b64decode
from json import loads, dumps
import pytest
from conftest import init_event_context
from _pytest.capture import CaptureFixture


def test_routing(capsys: CaptureFixture[str]) -> None:
    """Tests routing."""
    from aio_lambda_api import Handler

    handler = Handler()

    @handler.get("/")
    async def get() -> str:
        """get."""
        return "get"

    @handler.post("/")
    async def post() -> str:
        """post."""
        return "post"

    @handler.put("/")
    async def put() -> str:
        """put."""
        return "put"

    @handler.patch("/")
    async def patch() -> str:
        """patch."""
        return "patch"

    @handler.delete("/")
    async def delete() -> str:
        """delete."""
        return "delete"

    @handler.head("/")
    async def head() -> str:
        """head."""
        return "head"

    @handler.options("/")
    async def options() -> str:
        """options."""
        return "options"

    @handler.get("/get_only")
    async def get_only() -> str:
        """get."""
        return "get"

    with pytest.raises(ValueError):

        @handler.options("/")
        async def options_duplicate() -> str:
            """options."""
            return "options_duplicate"

    resp = handler(*init_event_context(method="GET"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "200", resp["body"]
    assert resp["body"] == '"get"'
    assert resp["headers"]["content-type"] == "application/json"
    assert resp["headers"]["content-length"] == str(len('"get"'))
    assert log["level"] == "info"
    assert log["status_code"] == 200
    assert log["path"] == "/"
    assert log["method"] == "GET"

    resp = handler(*init_event_context(method="POST"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "200", resp["body"]
    assert resp["body"] == '"post"'
    assert resp["headers"]["content-type"] == "application/json"
    assert resp["headers"]["content-length"] == str(len('"post"'))
    assert log["level"] == "info"
    assert log["status_code"] == 200
    assert log["path"] == "/"
    assert log["method"] == "POST"

    resp = handler(*init_event_context(method="PUT"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "200", resp["body"]
    assert resp["body"] == '"put"'
    assert log["level"] == "info"
    assert log["status_code"] == 200
    assert log["path"] == "/"
    assert log["method"] == "PUT"

    resp = handler(*init_event_context(method="OPTIONS"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "200", resp["body"]
    assert resp["body"] == '"options"'
    assert log["level"] == "info"
    assert log["status_code"] == 200
    assert log["path"] == "/"
    assert log["method"] == "OPTIONS"

    resp = handler(*init_event_context(method="DELETE"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "200", resp["body"]
    assert resp["body"] == '"delete"'
    assert log["level"] == "info"
    assert log["status_code"] == 200
    assert log["path"] == "/"
    assert log["method"] == "DELETE"

    resp = handler(*init_event_context(method="HEAD"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "200", resp["body"]
    assert resp["body"] == '"head"'
    assert log["level"] == "info"
    assert log["status_code"] == 200
    assert log["path"] == "/"
    assert log["method"] == "HEAD"

    resp = handler(*init_event_context(method="PATCH"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "200", resp["body"]
    assert resp["body"] == '"patch"'
    assert log["level"] == "info"
    assert log["status_code"] == 200
    assert log["path"] == "/"
    assert log["method"] == "PATCH"

    resp = handler(*init_event_context(method="PATCH", version=1))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "200", resp["body"]
    assert resp["body"] == '"patch"'
    assert log["level"] == "info"
    assert log["status_code"] == 200
    assert log["path"] == "/"
    assert log["method"] == "PATCH"

    resp = handler(*init_event_context(path="/not_exists"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "404", resp["body"]
    assert loads(resp["body"]) == {"detail": "Not Found"}
    assert log["level"] == "warning"
    assert log["status_code"] == 404
    assert log["path"] == "/not_exists"
    assert log["method"] == "GET"

    resp = handler(*init_event_context(path="/get_only", method="GET"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "200", resp["body"]
    assert log["level"] == "info"
    assert log["status_code"] == 200
    assert log["path"] == "/get_only"
    assert log["method"] == "GET"

    resp = handler(*init_event_context(path="/get_only", method="PUT"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "405", resp["body"]
    assert loads(resp["body"]) == {"detail": "Method Not Allowed"}
    assert log["level"] == "warning"
    assert log["status_code"] == 405
    assert log["path"] == "/get_only"
    assert log["method"] == "PUT"


def test_exception_handling(capsys: CaptureFixture[str]) -> None:
    """Tests exception handling."""
    from aio_lambda_api import Handler, HTTPException

    handler = Handler()

    @handler.get("/raise_400")
    async def get400() -> str:
        """Raise 400."""
        raise HTTPException(400)

    @handler.get("/raise_503")
    async def get503() -> str:
        """Raise 503."""
        raise HTTPException(503)

    @handler.get("/raise_400_with_message")
    async def get400msg() -> str:
        """Raise 400."""
        raise HTTPException(400, "Custom Error Message")

    @handler.get("/raise_400_with_detail")
    async def get400detail() -> str:
        """Raise 400."""
        raise HTTPException(400, "Custom Error Message", error_detail="detail")

    @handler.get("/raise_500")
    async def get500() -> str:
        """Raise 500."""
        raise ValueError("Invalid value.")

    @handler.get("/raise_422")
    async def get422(value: int) -> int:
        """Raise validation error."""
        return value

    resp = handler(*init_event_context(path="/raise_422", body=dict(value=1)))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "200", resp["body"]
    assert resp["body"] == "1"
    assert log["level"] == "info"

    resp = handler(*init_event_context(path="/raise_400"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "400", resp["body"]
    assert loads(resp["body"]) == {"detail": "Bad Request"}
    assert log["level"] == "warning"
    assert log["status_code"] == 400
    assert "error_detail" not in log

    resp = handler(*init_event_context(path="/raise_503"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "503", resp["body"]
    assert loads(resp["body"]) == {"detail": "Service Unavailable"}
    assert log["level"] == "error"
    assert log["status_code"] == 503
    assert "error_detail" not in log

    resp = handler(*init_event_context(path="/raise_400_with_message"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "400", resp["body"]
    assert loads(resp["body"]) == {"detail": "Custom Error Message"}
    assert log["level"] == "warning"
    assert log["status_code"] == 400
    assert log["error_detail"] == "Custom Error Message"

    resp = handler(*init_event_context(path="/raise_400_with_detail"))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "400"
    assert loads(resp["body"]) == {"detail": "Custom Error Message"}
    assert log["level"] == "warning"
    assert log["status_code"] == 400
    assert log["error_detail"] == "detail"

    with pytest.raises(ValueError):
        handler(*init_event_context(path="/raise_500"))
    log = loads(capsys.readouterr().out)
    assert log["level"] == "critical"
    assert log["status_code"] == 500
    assert log["error_detail"].startswith("Traceback (most recent call last):")

    resp = handler(*init_event_context(path="/raise_422", body=dict(value=1)))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "200", resp["body"]
    assert resp["body"] == "1"
    assert log["level"] == "info"

    resp = handler(*init_event_context(path="/raise_422", body=dict(value="a")))
    log = loads(capsys.readouterr().out)
    assert resp["statusCode"] == "422", resp["body"]
    assert "type_error.integer" in resp["body"]
    assert log["level"] == "warning"
    assert log["status_code"] == 422
    assert "type_error.integer" == log["error_detail"][0]["type"]


def test_status_code() -> None:
    """Tests status code."""
    from aio_lambda_api import Handler

    handler = Handler()

    @handler.get("/return_204")
    async def get204() -> None:
        """Raise validation error."""

    @handler.get("/return_202", status_code=202)
    async def get202() -> str:
        """Raise validation error."""
        return "test"

    resp = handler(*init_event_context(path="/return_204"))
    assert resp["statusCode"] == "204", resp["body"]

    resp = handler(*init_event_context(path="/return_202"))
    assert resp["statusCode"] == "202", resp["body"]


def test_inject_request() -> None:
    """Tests Request object injection."""
    from aio_lambda_api import Handler, Request

    handler = Handler()

    @handler.get("/")
    async def get(request: Request) -> None:
        """Raise validation error."""
        assert await request.body()

    resp = handler(*init_event_context(body="1"))
    assert resp["statusCode"] == "204", resp["body"]


def test_inject_response() -> None:
    """Tests Response object injection."""
    from aio_lambda_api import Handler, Response

    handler = Handler()

    @handler.get("/")
    async def get_400(response: Response) -> str:
        """get."""
        response.headers["test"] = "test"
        response.status_code = 400
        return "Error"

    resp = handler(*init_event_context())
    assert resp["statusCode"] == "400", resp["body"]
    assert loads(resp["body"]) == "Error"

    @handler.get("/401")
    async def get_401(response: Response) -> None:
        """get."""
        response.status_code = 401

    resp = handler(*init_event_context("/401"))
    assert resp["statusCode"] == "401", resp["body"]
    assert loads(resp["body"]) == {"detail": "Unauthorized"}


def test_binary_body() -> None:
    """Tests binary body."""
    from aio_lambda_api import Handler, Request, Response

    handler = Handler()

    data = b"test"

    @handler.post("/")
    async def post(request: Request) -> Response:
        """Raise validation error."""
        body = await request.body()
        assert body == data
        return Response(body, media_type="application/octet-stream")

    resp = handler(*init_event_context(body=data, method="POST"))
    assert resp["statusCode"] == "200", resp["body"]
    assert resp["isBase64Encoded"] is True
    assert b64decode(resp["body"].encode()) == data
    assert resp["headers"]["content-type"] == "application/octet-stream"
    assert resp["headers"]["content-length"] == str(len(data))


def test_boto3_config() -> None:
    """Test run async functions."""
    import aioboto3
    from aio_lambda_api import Handler
    from aio_lambda_api._backends.aws_lambda import Backend

    session = aioboto3.Session()
    assert Handler().enter_async_context(
        session.resource("s3", config=Backend.botocore_config())
    )

    assert Handler().enter_async_context(
        session.resource("s3", config=Backend.botocore_config())
    )


def test_get_logger() -> None:
    """Test get_logger."""
    from aio_lambda_api import Handler, get_logger

    handler = Handler()

    @handler.get("/")
    async def post() -> None:
        """Raise validation error."""
        log = get_logger()
        assert log["path"] == "/"

    assert handler(*init_event_context())["statusCode"] == "204"


def test_batch(capsys: CaptureFixture[str]) -> None:
    """Tests batch of requests."""
    from aio_lambda_api import Handler, HTTPException

    handler = Handler()

    @handler.get("/")
    async def get() -> None:
        """Get."""

    @handler.get("/raise_400")
    async def get400() -> str:
        """Raise 400."""
        raise HTTPException(400)

    @handler.get("/raise_500")
    async def get500() -> str:
        """Raise 500."""
        raise ValueError("Invalid value.")

    _req204, context = init_event_context(path="/", body=dict())
    req204 = dumps(_req204)
    req400 = dumps(init_event_context(path="/raise_400", body=dict())[0])
    req500 = dumps(init_event_context(path="/raise_500", body=dict())[0])

    # SQS
    sqs_event = dict(
        Records=[
            dict(messageId="1", body=req204, eventSource="aws:sqs"),
            dict(messageId="2", body=req400, eventSource="aws:sqs"),
            dict(messageId="3", body=req500, eventSource="aws:sqs"),
            dict(messageId="4", body=req204, eventSource="aws:sqs"),
        ]
    )
    resp = handler(sqs_event, context)
    logs = [loads(line.strip()) for line in capsys.readouterr().out.splitlines()]
    assert sorted(item["itemIdentifier"] for item in resp["batchItemFailures"]) == [
        "2",
        "3",
    ]
    assert sorted(log["status_code"] for log in logs) == [204, 204, 400, 500], logs

    sqs_event = dict(
        Records=[
            dict(messageId="1", body=req204, eventSource="aws:sqs"),
            dict(messageId="2", body=req204, eventSource="aws:sqs"),
            dict(messageId="3", body=req204, eventSource="aws:sqs"),
        ]
    )
    resp = handler(sqs_event, context)
    logs = [loads(line.strip()) for line in capsys.readouterr().out.splitlines()]
    assert resp is None, resp
    assert [log["status_code"] for log in logs] == [204, 204, 204], logs

    sqs_event = dict(Records=[])
    resp = handler(sqs_event, context)
    assert resp is None, resp

    # SNS
    sns_event = dict(
        Records=[
            dict(messageId="1", Sns=dict(Message=req204), eventSource="aws:sns"),
            dict(messageId="2", Sns=dict(Message=req204), eventSource="aws:sns"),
            dict(messageId="3", Sns=dict(Message=req204), eventSource="aws:sns"),
        ]
    )
    resp = handler(sns_event, context)
    logs = [loads(line.strip()) for line in capsys.readouterr().out.splitlines()]
    assert resp is None, resp
    assert [log["status_code"] for log in logs] == [204, 204, 204], logs

    # MQ
    mq_event = dict(
        eventSource="aws:mq",
        messages=[
            dict(messageId="1", data=req204),
            dict(messageId="2", data=req204),
            dict(messageId="3", data=req204),
        ],
    )
    resp = handler(mq_event, context)
    logs = [loads(line.strip()) for line in capsys.readouterr().out.splitlines()]
    assert resp is None, resp
    assert [log["status_code"] for log in logs] == [204, 204, 204], logs
