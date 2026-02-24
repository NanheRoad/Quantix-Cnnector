from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import devices, protocols, websocket
from backend.database.connection import close_db, init_db
from backend.services.device_manager import manager
from config.settings import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

app = FastAPI(title="Quantix Connector", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(protocols.router)
app.include_router(devices.router)
app.include_router(websocket.router)


@app.on_event("startup")
async def startup_event() -> None:
    init_db(seed=True)
    await manager.startup()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await manager.shutdown()
    close_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
