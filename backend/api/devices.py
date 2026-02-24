from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import require_api_key
from backend.api.schemas import DeviceCreate, DeviceUpdate, ExecuteStepRequest
from backend.database.models import Device, ProtocolTemplate
from backend.services.device_manager import manager

router = APIRouter(prefix="/api/devices", tags=["devices"], dependencies=[Depends(require_api_key)])


@router.get("")
async def list_devices() -> list[dict[str, Any]]:
    rows = Device.select().order_by(Device.id.asc())
    result: list[dict[str, Any]] = []
    for row in rows:
        item = row.to_dict()
        runtime = await manager.runtime_snapshot(row.id)
        item["runtime"] = runtime
        result.append(item)
    return result


@router.post("")
async def create_device(payload: DeviceCreate) -> dict[str, Any]:
    template = ProtocolTemplate.get_or_none(ProtocolTemplate.id == payload.protocol_template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Protocol template not found")

    row = Device.create(
        name=payload.name,
        protocol_template=payload.protocol_template_id,
        connection_params=payload.connection_params,
        template_variables=payload.template_variables,
        poll_interval=payload.poll_interval,
        enabled=payload.enabled,
    )

    await manager.reload_device(row.id)
    return row.to_dict()


@router.get("/{device_id}")
async def get_device(device_id: int) -> dict[str, Any]:
    row = Device.get_or_none(Device.id == device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")

    item = row.to_dict()
    item["runtime"] = await manager.runtime_snapshot(row.id)
    return item


@router.put("/{device_id}")
async def update_device(device_id: int, payload: DeviceUpdate) -> dict[str, Any]:
    row = Device.get_or_none(Device.id == device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")

    data = payload.model_dump(exclude_none=True)
    if "protocol_template_id" in data:
        template = ProtocolTemplate.get_or_none(ProtocolTemplate.id == data["protocol_template_id"])
        if template is None:
            raise HTTPException(status_code=404, detail="Protocol template not found")
        row.protocol_template = data.pop("protocol_template_id")

    for key, value in data.items():
        setattr(row, key, value)

    row.save()
    await manager.reload_device(row.id)
    return row.to_dict()


@router.delete("/{device_id}")
async def delete_device(device_id: int) -> dict[str, bool]:
    row = Device.get_or_none(Device.id == device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")

    await manager.remove_device(row.id)
    row.delete_instance()
    return {"ok": True}


@router.post("/{device_id}/enable")
async def enable_device(device_id: int) -> dict[str, Any]:
    row = Device.get_or_none(Device.id == device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")

    row.enabled = True
    row.save()
    await manager.reload_device(row.id)
    return row.to_dict()


@router.post("/{device_id}/disable")
async def disable_device(device_id: int) -> dict[str, Any]:
    row = Device.get_or_none(Device.id == device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")

    row.enabled = False
    row.save()
    await manager.reload_device(row.id)
    return row.to_dict()


@router.post("/{device_id}/execute")
async def execute_step(device_id: int, payload: ExecuteStepRequest) -> dict[str, Any]:
    row = Device.get_or_none(Device.id == device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")

    if not row.enabled:
        raise HTTPException(status_code=400, detail="Device is disabled")

    try:
        return await manager.execute_manual_step(device_id, payload.step_id, payload.params)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
