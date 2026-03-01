from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import require_api_key
from backend.api.schemas import ProtocolTemplateCreate, ProtocolTemplateUpdate, ProtocolTestRequest, StepTestRequest
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


def is_write_action(action: str) -> bool:
    control_write_actions = {
        "modbus.write_register",
        "modbus.write_coil",
        "mqtt.publish",
    }
    return action in control_write_actions


def find_step_in_template(
    template: dict[str, Any],
    step_id: str,
    step_context: Literal["setup", "poll", "event"],
) -> dict[str, Any] | None:
    if step_context == "setup":
        for step in template.get("setup_steps", []):
            if isinstance(step, dict) and step.get("id") == step_id:
                return step
        return None

    if step_context == "event":
        handler = template.get("message_handler", {})
        if isinstance(handler, dict) and handler.get("id") == step_id:
            return handler
        return None

    for step in template.get("steps", []):
        if not isinstance(step, dict) or step.get("id") != step_id:
            continue
        if step.get("trigger", "poll") == "poll":
            return step
    return None


async def execute_single_step(
    executor: ProtocolExecutor,
    template: dict[str, Any],
    step: dict[str, Any],
    step_context: Literal["setup", "poll", "event"],
    driver,
    variables: dict[str, Any],
    test_payload: str | None = None,
    previous_steps: dict[str, Any] | None = None,
) -> dict[str, Any]:
    steps_context = previous_steps if previous_steps else {}
    context: dict[str, Any] = {"steps": steps_context, **variables}

    if step_context in {"setup", "poll"}:
        raw_result = await executor.execute_one_step(driver, step, context)
        merged_steps = {**steps_context, step["id"]: {"result": raw_result}}
        output = executor.render_output(template, {"steps": merged_steps, **variables})
        return {
            "step_result": raw_result,
            "rendered_output": output,
        }

    if not test_payload:
        raise ValueError("event 步骤测试需要提供 test_payload")

    event_context = {
        "payload": str(test_payload),
        "steps": steps_context,
        **variables,
    }
    raw_result = await executor.execute_one_step(driver, step, event_context, skip_driver=True)
    event_context["message_handler"] = {"result": raw_result}
    output = executor.render_output(template, event_context)
    return {
        "step_result": raw_result,
        "rendered_output": output,
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


@router.post("/{protocol_id}/test-step")
async def test_single_step(protocol_id: int, payload: StepTestRequest) -> dict[str, Any]:
    row = ProtocolTemplate.get_or_none(ProtocolTemplate.id == protocol_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Protocol not found")

    step = find_step_in_template(row.template, payload.step_id, payload.step_context)
    if step is None:
        raise HTTPException(status_code=404, detail=f"Step not found: {payload.step_id}")

    action = str(step.get("action", ""))
    if (not payload.allow_write) and is_write_action(action):
        return {
            "ok": False,
            "error": "写操作需要显式设置 allow_write=true",
            "action": action,
            "safety_warning": "该操作可能修改设备状态",
        }

    driver = build_driver(row.protocol_type, payload.connection_params)
    executor = ProtocolExecutor()
    try:
        connected = await driver.connect()
        if not connected:
            return {"ok": False, "error": "connect failed"}

        result = await execute_single_step(
            executor=executor,
            template=row.template,
            step=step,
            step_context=payload.step_context,
            driver=driver,
            variables=payload.template_variables,
            test_payload=payload.test_payload,
            previous_steps=payload.previous_steps,
        )
        return {
            "ok": True,
            "step_id": payload.step_id,
            "action": action,
            "step_result": result.get("step_result"),
            "rendered_output": result.get("rendered_output"),
        }
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        await driver.disconnect()
