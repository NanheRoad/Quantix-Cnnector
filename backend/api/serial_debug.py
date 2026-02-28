from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.api.deps import require_api_key
from backend.services.serial_debug_service import serial_debug_service

router = APIRouter(prefix="/api/serial-debug", tags=["serial-debug"], dependencies=[Depends(require_api_key)])


class SerialOpenRequest(BaseModel):
    port: str
    baudrate: int = 9600
    bytesize: int = Field(default=8)
    parity: Literal["N", "E", "O", "M", "S"] = "N"
    stopbits: float = 1.0
    timeout_ms: int = Field(default=300, ge=0, le=60000)


class SerialSendRequest(BaseModel):
    data: str
    data_format: Literal["text", "hex"] = "text"
    encoding: str = "utf-8"
    line_ending: Literal["none", "cr", "lf", "crlf"] = "none"


@router.get("/ports")
async def list_serial_ports() -> dict[str, Any]:
    ports = await serial_debug_service.list_ports()
    return {"ok": True, "ports": ports}


@router.get("/status")
async def get_serial_debug_status() -> dict[str, Any]:
    return await serial_debug_service.status()


@router.post("/open")
async def open_serial_debug(payload: SerialOpenRequest) -> dict[str, Any]:
    try:
        return await serial_debug_service.open(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/close")
async def close_serial_debug() -> dict[str, Any]:
    return await serial_debug_service.close()


@router.post("/send")
async def send_serial_debug(payload: SerialSendRequest) -> dict[str, Any]:
    try:
        return await serial_debug_service.send(**payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/read")
async def read_serial_debug(
    max_bytes: int = Query(default=1024, ge=1, le=65536),
    timeout_ms: int = Query(default=30, ge=0, le=10000),
    encoding: str = Query(default="utf-8"),
) -> dict[str, Any]:
    try:
        return await serial_debug_service.read(max_bytes=max_bytes, timeout_ms=timeout_ms, encoding=encoding)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/logs")
async def get_serial_debug_logs(
    last_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    try:
        return await serial_debug_service.pull_logs(last_seq=last_seq, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
