import asyncio
import json
import logging
import threading
from collections.abc import Callable

from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.engine import Engine


logger = logging.getLogger(__name__)
_listeners_lock = threading.Lock()
_listener_loops: dict[asyncio.Queue, asyncio.AbstractEventLoop] = {}

hotspot_listeners: list[asyncio.Queue] = []
post_listeners: list[asyncio.Queue] = []


def stream(listeners: list[asyncio.Queue], snapshot: Callable[[], list[dict]]) -> StreamingResponse:
    listener: asyncio.Queue = asyncio.Queue(maxsize=256)

    async def generator():
        loop = asyncio.get_running_loop()
        with _listeners_lock:
            listeners.append(listener)
            _listener_loops[listener] = loop
        try:
            initial_snapshot = await run_in_threadpool(snapshot)
            yield f"data: {json.dumps({'type': 'snapshot', 'data': initial_snapshot}, default=str)}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(listener.get(), timeout=25)
                    if message.get("type") == "_resync":
                        message = {"type": "snapshot", "data": await run_in_threadpool(snapshot)}
                    yield f"data: {json.dumps(message, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield 'data: {"type": "keepalive"}\n\n'
        finally:
            with _listeners_lock:
                if listener in listeners:
                    listeners.remove(listener)
                _listener_loops.pop(listener, None)

    return StreamingResponse(
        generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


def publish(listeners: list[asyncio.Queue], payload: dict) -> None:
    with _listeners_lock:
        targets = [(listener, _listener_loops.get(listener)) for listener in listeners]

    for listener, loop in targets:
        if loop is None or loop.is_closed():
            continue
        try:
            loop.call_soon_threadsafe(_enqueue, listener, payload)
        except RuntimeError:
            logger.debug("SSE listener closed before an event could be queued")


def _enqueue(listener: asyncio.Queue, payload: dict) -> None:
    if listener.full():
        while not listener.empty():
            listener.get_nowait()
        listener.put_nowait({"type": "_resync"})
        logger.warning("SSE listener queue filled; requesting a fresh snapshot")
        return
    listener.put_nowait(payload)


def start_postgres_listener(
    engine: Engine,
    on_notification: Callable[[], None],
) -> tuple[threading.Event, threading.Thread] | None:
    if engine.dialect.name != "postgresql":
        return None

    stop_event = threading.Event()
    thread = threading.Thread(
        target=_listen_for_postgres_changes,
        args=(engine, stop_event, on_notification),
        daemon=True,
        name="bluesignal-postgres-notifications",
    )
    thread.start()
    return stop_event, thread


def stop_postgres_listener(
    listener: tuple[threading.Event, threading.Thread] | None,
) -> None:
    if listener is None:
        return
    stop_event, thread = listener
    stop_event.set()
    thread.join(timeout=5)


def _listen_for_postgres_changes(
    engine: Engine,
    stop_event: threading.Event,
    on_notification: Callable[[], None],
) -> None:
    while not stop_event.is_set():
        raw_connection = None
        try:
            raw_connection = engine.raw_connection()
            connection = raw_connection.driver_connection
            connection.execute("LISTEN bluesignal_changes")
            connection.commit()
            while not stop_event.is_set():
                notifications = connection.notifies(timeout=1, stop_after=1)
                for _notification in notifications:
                    on_notification()
        except Exception:
            if not stop_event.is_set():
                logger.exception("PostgreSQL SSE listener failed; reconnecting")
                stop_event.wait(1)
        finally:
            if raw_connection is not None:
                raw_connection.close()
