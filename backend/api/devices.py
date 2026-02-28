from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from peewee import IntegrityError

from backend.api.deps import require_api_key
from backend.api.schemas import DeviceCreate, DeviceUpdate, ExecuteStepRequest
from backend.database.models import Device, ProtocolTemplate, normalize_device_code
from backend.services.device_manager import manager

router = APIRouter(prefix="/api/devices", tags=["devices"], dependencies=[Depends(require_api_key)])


@router.get("")
async def list_devices() -> list[dict[str, Any]]:
    rows = Device.select().order_by(Device.id.asc())
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(await _device_payload(row))
    return result


@router.post("")
async def create_device(payload: DeviceCreate) -> dict[str, Any]:
    template = ProtocolTemplate.get_or_none(ProtocolTemplate.id == payload.protocol_template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Protocol template not found")

    try:
        row = Device.create(
            device_code=payload.device_code,
            name=payload.name,
            protocol_template=payload.protocol_template_id,
            connection_params=payload.connection_params,
            template_variables=payload.template_variables,
            poll_interval=payload.poll_interval,
            enabled=payload.enabled,
        )
    except IntegrityError as exc:
        _raise_conflict_from_integrity_error(exc)

    await manager.reload_device(row.id)
    return row.to_dict()


@router.get("/by-code/{device_code}")
async def get_device_by_code(device_code: str) -> dict[str, Any]:
    row = _get_device_by_code_or_404(device_code)
    return await _device_payload(row)


@router.put("/by-code/{device_code}")
async def update_device_by_code(device_code: str, payload: DeviceUpdate) -> dict[str, Any]:
    row = _get_device_by_code_or_404(device_code)
    return await _update_device_row(row, payload)


@router.delete("/by-code/{device_code}")
async def delete_device_by_code(device_code: str) -> dict[str, bool]:
    row = _get_device_by_code_or_404(device_code)
    await manager.remove_device(row.id)
    row.delete_instance()
    return {"ok": True}


@router.post("/by-code/{device_code}/enable")
async def enable_device_by_code(device_code: str) -> dict[str, Any]:
    row = _get_device_by_code_or_404(device_code)
    row.enabled = True
    row.save()
    await manager.reload_device(row.id)
    return row.to_dict()


@router.post("/by-code/{device_code}/disable")
async def disable_device_by_code(device_code: str) -> dict[str, Any]:
    row = _get_device_by_code_or_404(device_code)
    row.enabled = False
    row.save()
    await manager.reload_device(row.id)
    return row.to_dict()


@router.post("/by-code/{device_code}/execute")
async def execute_step_by_code(device_code: str, payload: ExecuteStepRequest) -> dict[str, Any]:
    row = _get_device_by_code_or_404(device_code)
    if not row.enabled:
        raise HTTPException(status_code=400, detail="Device is disabled")
    return await _execute_manual(row.id, payload)


@router.get("/{device_id}")
async def get_device(device_id: int) -> dict[str, Any]:
    row = _get_device_by_id_or_404(device_id)
    return await _device_payload(row)


@router.put("/{device_id}")
async def update_device(device_id: int, payload: DeviceUpdate) -> dict[str, Any]:
    row = _get_device_by_id_or_404(device_id)
    return await _update_device_row(row, payload)


@router.delete("/{device_id}")
async def delete_device(device_id: int) -> dict[str, bool]:
    row = _get_device_by_id_or_404(device_id)
    await manager.remove_device(row.id)
    row.delete_instance()
    return {"ok": True}


@router.post("/{device_id}/enable")
async def enable_device(device_id: int) -> dict[str, Any]:
    row = _get_device_by_id_or_404(device_id)
    row.enabled = True
    row.save()
    await manager.reload_device(row.id)
    return row.to_dict()


@router.post("/{device_id}/disable")
async def disable_device(device_id: int) -> dict[str, Any]:
    row = _get_device_by_id_or_404(device_id)
    row.enabled = False
    row.save()
    await manager.reload_device(row.id)
    return row.to_dict()


@router.post("/{device_id}/execute")
async def execute_step(device_id: int, payload: ExecuteStepRequest) -> dict[str, Any]:
    row = _get_device_by_id_or_404(device_id)
    if not row.enabled:
        raise HTTPException(status_code=400, detail="Device is disabled")
    return await _execute_manual(device_id, payload)


def _get_device_by_id_or_404(device_id: int) -> Device:
    row = Device.get_or_none(Device.id == device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return row


def _get_device_by_code_or_404(device_code: str) -> Device:
    try:
        normalized_code = normalize_device_code(device_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row = Device.get_or_none(Device.device_code == normalized_code)
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return row


async def _device_payload(row: Device) -> dict[str, Any]:
    item = row.to_dict()
    item["runtime"] = await manager.runtime_snapshot(row.id)
    return item


async def _update_device_row(row: Device, payload: DeviceUpdate) -> dict[str, Any]:
    data = payload.model_dump(exclude_none=True)

    if "protocol_template_id" in data:
        template = ProtocolTemplate.get_or_none(ProtocolTemplate.id == data["protocol_template_id"])
        if template is None:
            raise HTTPException(status_code=404, detail="Protocol template not found")
        row.protocol_template = data.pop("protocol_template_id")

    for key, value in data.items():
        setattr(row, key, value)

    try:
        row.save()
    except IntegrityError as exc:
        _raise_conflict_from_integrity_error(exc)

    await manager.reload_device(row.id)
    return row.to_dict()


async def _execute_manual(device_id: int, payload: ExecuteStepRequest) -> dict[str, Any]:
    try:
        return await manager.execute_manual_step(device_id, payload.step_id, payload.params)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _raise_conflict_from_integrity_error(exc: IntegrityError) -> None:
    text = str(exc).lower()
    if "device_code" in text:
        raise HTTPException(status_code=409, detail="Device code already exists") from exc
    if "name" in text:
        raise HTTPException(status_code=409, detail="Device name already exists") from exc
    raise HTTPException(status_code=409, detail="Device unique constraint violated") from exc
