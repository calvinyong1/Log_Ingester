import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.logging_config import request_id_var

logger = logging.getLogger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"
# Same shape as event_id: a client-supplied id is echoed into responses and logs,
# so it must not be able to carry whitespace, newlines or unbounded text.
_VALID_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope["headers"]:
        if name == b"x-request-id":
            candidate = value.decode("latin-1")
            return candidate if _VALID_ID.match(candidate) else None
    return None


class RequestContextMiddleware:
    """Gives each request an id, returns it in a header, and logs one access line.

    Pure ASGI rather than BaseHTTPMiddleware so responses aren't buffered.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        # Stays 500 if the app raises before sending a response.
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            # Starlette's outer handler and uvicorn log this too, but only after the
            # request id has been reset, so the traceback would carry no id.
            logger.exception("Unhandled error in %s %s", scope["method"], scope["path"])
            raise
        finally:
            # Logged before the reset so the line carries the request id.
            logger.info(
                "%s %s %s",
                scope["method"],
                scope["path"],
                status_code,
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_var.reset(token)
