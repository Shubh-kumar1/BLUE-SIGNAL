import asyncio
import json
import queue
from collections.abc import Callable

from fastapi.responses import StreamingResponse


hotspot_listeners: list[asyncio.Queue] = []
post_listeners: list[asyncio.Queue] = []


def stream(listeners: list[asyncio.Queue], snapshot: Callable[[], list[dict]]) -> StreamingResponse:
    listener: asyncio.Queue = asyncio.Queue()

    async def generator():
        listeners.append(listener)
        try:
            yield f"data: {json.dumps({'type': 'snapshot', 'data': snapshot()}, default=str)}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(listener.get(), timeout=25)
                    yield f"data: {json.dumps(message, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield 'data: {"type": "keepalive"}\n\n'
        finally:
            if listener in listeners:
                listeners.remove(listener)

    return StreamingResponse(
        generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


def publish(listeners: list[asyncio.Queue], payload: dict) -> None:
    for listener in listeners:
        listener.put_nowait(payload)
