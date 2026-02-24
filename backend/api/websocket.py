from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api.deps import verify_api_key_value
from backend.services.device_manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_stream(websocket: WebSocket) -> None:
    api_key = websocket.query_params.get("api_key")
    if not verify_api_key_value(api_key):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    queue = await manager.subscribe()

    try:
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30)
                await websocket.send_json(message)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.unsubscribe(queue)
