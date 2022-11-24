"""API base."""
from __future__ import annotations
from asyncio import new_event_loop, wait_for, gather
from contextlib import AsyncExitStack
from inspect import signature
from typing import (
    Any,
    AsyncContextManager,
    TypeVar,
    Callable,
    Iterable,
    Coroutine,
    Type,
)
from jhalog import LogEvent

try:
    from pydantic import validate_arguments
except ImportError:
    validate_arguments = None  # type: ignore

from aio_lambda_api.exceptions import HTTPException, ValidationError
from aio_lambda_api._responses import Response, JSONResponse
from aio_lambda_api._requests import Request
from aio_lambda_api.settings import FUNCTION_TIMEOUT
from aio_lambda_api._backends import get_backend


_T = TypeVar("_T")

_VALIDATOR_CONFIG = dict(arbitrary_types_allowed=True)


class _APIRoute:
    """API route."""

    __slots__ = ["status_code", "func", "params"]

    def __init__(
        self,
        func: Callable[..., Any],
        status_code: int,
        params: dict[str, Type[Any]],
    ) -> None:
        self.status_code = status_code
        self.func = func
        self.params = params


def get_logger() -> LogEvent:
    """Get current logger.

    Returns:
        Log Event.
    """
    return LogEvent.from_context()


class Handler:
    """Serverless function handler."""

    __slots__ = ["_loop", "_exit_stack", "_routes", "_backend"]

    def __init__(
        self, backend: str | None = None, jhalog_config: dict[str, Any] | None = None
    ) -> None:
        self._loop = new_event_loop()
        self._exit_stack = AsyncExitStack()
        self._routes: dict[str, dict[str, _APIRoute]] = dict()
        self._backend = self.enter_async_context(
            get_backend(backend)(jhalog_config=jhalog_config)
        )

    def __del__(self) -> None:
        self.run_async(self._exit_stack.__aexit__(None, None, None))

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Entry point.

        Returns:
            Serialized response.
        """
        return self.run_async(self.__acall__(*args, **kwargs))

    async def __acall__(self, *args: Any, **kwargs: Any) -> Any:
        """Async entry point.

        Returns:
            Serialized response.
        """
        parsed = await self._backend.parse_request(*args, **kwargs)
        if isinstance(parsed, Request):
            return await self._backend.serialize_response(
                await self._handle_request(parsed), parsed
            )
        return await self._backend.serialize_responses(
            zip(await self._handle_requests(parsed), parsed)
        )

    async def _handle_requests(self, requests: Iterable[Request]) -> Iterable[Response]:
        """Handle multiples requests.

        Args:
            requests: Requests.

        Returns:
            Responses.
        """
        return await gather(*(self._handle_request(request) for request in requests))

    async def _handle_request(self, request: Request) -> Response:
        """Handle a single request.

        Args:
            request: Request.

        Returns:
            Response.
        """
        with self._backend.logger.create_event(
            method=request.method,
            path=request.path,
            id=request.headers.get("x-request-id"),
            user_agent=request.headers.get("user-agent"),
        ) as event:
            try:
                response, func = await self._prepare_request(request)
                return await self._call_route_function(func, response)

            except HTTPException as exception:
                event.error_detail = exception.error_detail
                event.status_code = exception.status_code
                return JSONResponse(
                    content=(
                        None
                        if exception.detail is None
                        else dict(detail=exception.detail)
                    ),
                    status_code=exception.status_code,
                )

            except ValidationError as exception:
                errors = exception.errors()
                event.error_detail = errors
                event.status_code = 422
                return JSONResponse(content=dict(detail=errors), status_code=422)

            except Exception as exception:
                status_code, message = event.status_code_from_exception(exception)
                response = JSONResponse(status_code=status_code, content=message)
                if request.raises_exceptions:
                    raise
                return response

    async def _prepare_request(
        self, request: Request
    ) -> tuple[Response, Coroutine[Any, Any, Any]]:
        """Prepare the request.

        Args:
            request: Request.

        Returns:
            Default response object, Route function coroutine.
        """
        try:
            path_routes = self._routes[request.path]
        except KeyError:
            raise HTTPException(404)
        try:
            route = path_routes[request.method]
        except KeyError:
            raise HTTPException(405)

        response = JSONResponse(status_code=route.status_code)

        body = await request.json()
        kwargs = body.copy() if isinstance(body, dict) else dict()
        for param_name, param_cls in route.params.items():
            if param_cls == Request:
                kwargs[param_name] = request
            elif param_cls == Response:
                kwargs[param_name] = response

        return response, route.func(**kwargs)

    async def _call_route_function(
        self, func: Coroutine[Any, Any, Any], response: Response
    ) -> Response:
        """Call the route function and returns its response.

        Args:
            func: Route function.
            response: Response.

        Returns:
            Response.
        """
        content = await wait_for(func, FUNCTION_TIMEOUT)
        if isinstance(content, Response):
            response = content
        else:
            response.content = content
        return response

    def enter_async_context(self, context: AsyncContextManager[_T]) -> _T:
        """Initialize an async context manager.

        The context manager will be exited properly on API object destruction.

        Args:
            context: Async Object to initialize.

        Returns:
            Initialized object.
        """
        return self._loop.run_until_complete(
            self._exit_stack.enter_async_context(context)
        )

    def run_async(self, task: Coroutine[Any, Any, _T]) -> _T:
        """Run an async task in the sync context.

        This can be used to call initialization functions outside the serverless
        function itself.

        Args:
            task: Async task.

        Returns:
            Task result.
        """
        return self._loop.run_until_complete(task)

    def _api_route(
        self,
        path: str,
        method: str,
        *,
        status_code: int | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register API route.

        Args:
            path: HTTP path.
            method: HTTP method.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            """Decorator.

            Args:
                func: Route function.

            Returns:
                Route function.
            """
            params = self._check_signature(func)
            if validate_arguments is not None:
                func = validate_arguments(  # type: ignore
                    func, config=_VALIDATOR_CONFIG
                )
            try:
                path_routes = self._routes[path]
            except KeyError:
                path_routes = self._routes[path] = dict()
            try:
                path_routes[method]
            except KeyError:
                path_routes[method] = _APIRoute(
                    func=func, status_code=status_code or 200, params=params
                )
            else:
                raise ValueError(f'Route already registered: {method} "{path}".')
            return func

        return decorator

    @staticmethod
    def _check_signature(func: Callable[..., Any]) -> dict[str, Type[Any]]:
        """Check function signature and returns parameters to inject in functions calls.

        Args:
            func: Route function.

        Returns:
            Parameters to inject.
        """
        params: dict[str, Type[Any]] = dict()
        for param in signature(func).parameters.values():
            annotation = param.annotation
            if isinstance(annotation, type) and issubclass(annotation, Request):
                params[param.name] = Request
            elif isinstance(annotation, type) and issubclass(annotation, Response):
                params[param.name] = Response
        return params

    def delete(
        self, path: str, *, status_code: int | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a DELETE route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="DELETE", status_code=status_code)

    def get(
        self, path: str, *, status_code: int | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a GET route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="GET", status_code=status_code)

    def head(
        self, path: str, *, status_code: int | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a HEAD route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="HEAD", status_code=status_code)

    def options(
        self, path: str, *, status_code: int | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a OPTIONS route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="OPTIONS", status_code=status_code)

    def patch(
        self, path: str, *, status_code: int | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a PATCH route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="PATCH", status_code=status_code)

    def post(
        self, path: str, *, status_code: int | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a POST route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="POST", status_code=status_code)

    def put(
        self, path: str, *, status_code: int | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a PUT route.

        Args:
            path: HTTP path.
            status_code: HTTP status code.

        Returns:
            Decorator.
        """
        return self._api_route(path=path, method="PUT", status_code=status_code)
