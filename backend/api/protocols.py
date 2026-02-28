from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import require_api_key
from backend.api.schemas import ProtocolTemplateCreate, ProtocolTemplateUpdate, ProtocolTestRequest
from backend.database.models import Device, ProtocolTemplate
from backend.drivers import build_driver
from backend.services.protocol_executor import ProtocolExecutor

router = APIRouter(prefix="/api/protocols", tags=["protocols"], dependencies=[Depends(require_api_key)])


def _ensure_template_not_in_use(template_id: int) -> None:
    in_use = Device.select().where(Device.protocol_template_id == template_id).exists()
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Protocol template is referenced by existing devices and cannot be modified or deleted",
        )


@router.get("")
def list_protocols() -> list[dict[str, Any]]:
    rows = ProtocolTemplate.select().order_by(ProtocolTemplate.id.asc())
    return [row.to_dict() for row in rows]


@router.post("")
def create_protocol(payload: ProtocolTemplateCreate) -> dict[str, Any]:
    row = ProtocolTemplate.create(
        name=payload.name,
        description=payload.description,
        protocol_type=payload.protocol_type,
        template=payload.template,
        is_system=payload.is_system,
    )
    return row.to_dict()


@router.post("/import")
def import_protocol(payload: ProtocolTemplateCreate) -> dict[str, Any]:
    existing = ProtocolTemplate.get_or_none(ProtocolTemplate.name == payload.name)
    if existing:
        raise HTTPException(status_code=409, detail="Protocol name already exists")

    row = ProtocolTemplate.create(
        name=payload.name,
        description=payload.description,
        protocol_type=payload.protocol_type,
        template=payload.template,
        is_system=payload.is_system,
    )
    return row.to_dict()


@router.get("/{protocol_id}")
def get_protocol(protocol_id: int) -> dict[str, Any]:
    row = ProtocolTemplate.get_or_none(ProtocolTemplate.id == protocol_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return row.to_dict()


@router.put("/{protocol_id}")
def update_protocol(protocol_id: int, payload: ProtocolTemplateUpdate) -> dict[str, Any]:
    row = ProtocolTemplate.get_or_none(ProtocolTemplate.id == protocol_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Protocol not found")
    _ensure_template_not_in_use(row.id)

    data = payload.model_dump(exclude_none=True)
    for key, value in data.items():
        setattr(row, key, value)
    row.save()
    return row.to_dict()


@router.delete("/{protocol_id}")
def delete_protocol(protocol_id: int) -> dict[str, bool]:
    row = ProtocolTemplate.get_or_none(ProtocolTemplate.id == protocol_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Protocol not found")
    _ensure_template_not_in_use(row.id)
    if row.is_system:
        raise HTTPException(status_code=403, detail="System protocol can not be deleted")
    row.delete_instance(recursive=True)
    return {"ok": True}


@router.get("/{protocol_id}/export")
def export_protocol(protocol_id: int) -> dict[str, Any]:
    row = ProtocolTemplate.get_or_none(ProtocolTemplate.id == protocol_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return {
        "name": row.name,
        "description": row.description,
        "protocol_type": row.protocol_type,
        "template": row.template,
    }


@router.post("/{protocol_id}/test")
async def test_protocol(protocol_id: int, payload: ProtocolTestRequest) -> dict[str, Any]:
    row = ProtocolTemplate.get_or_none(ProtocolTemplate.id == protocol_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Protocol not found")

    driver = build_driver(row.protocol_type, payload.connection_params)
    executor = ProtocolExecutor()

    try:
        connected = await driver.connect()
        if not connected:
            return {"ok": False, "error": "connect failed"}

        variables = payload.template_variables
        setup = await executor.run_setup_steps(row.template, driver, variables)
        context_steps = setup

        output = None
        if row.protocol_type.lower() != "mqtt":
            context_steps = await executor.run_poll_steps(
                row.template,
                driver,
                variables,
                previous_steps=context_steps,
            )
            output = executor.render_output(row.template, {"steps": context_steps, **variables})

        return {"ok": True, "steps": context_steps, "output": output}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        await driver.disconnect()
