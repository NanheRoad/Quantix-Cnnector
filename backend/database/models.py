from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from peewee import (
    AutoField,
    BooleanField,
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    Model,
    TextField,
)

from backend.database.connection import database_proxy


DEVICE_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def normalize_device_code(value: Any) -> str:
    code = str(value or "").strip().upper()
    if not code:
        raise ValueError("device_code is required")
    if not DEVICE_CODE_PATTERN.fullmatch(code):
        raise ValueError("device_code must match ^[A-Z0-9][A-Z0-9_-]{0,63}$")
    return code


def build_default_device_code(device_id: int) -> str:
    return f"DEV-{int(device_id):06d}"


class JSONField(TextField):
    """Portable JSON field backed by TEXT."""

    def db_value(self, value: Any) -> str:
        if value is None:
            return "{}"
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def python_value(self, value: Any) -> Any:
        if value in (None, ""):
            return {}
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}


class BaseModel(Model):
    class Meta:
        database = database_proxy


class ProtocolTemplate(BaseModel):
    id = AutoField()
    name = CharField(max_length=100, unique=True)
    description = TextField(null=True)
    protocol_type = CharField(max_length=50)
    template = JSONField()
    is_system = BooleanField(default=False)
    created_at = DateTimeField(default=utcnow)
    updated_at = DateTimeField(default=utcnow)

    class Meta:
        table_name = "protocol_templates"

    def save(self, *args: Any, **kwargs: Any) -> int:
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "protocol_type": self.protocol_type,
            "template": self.template,
            "is_system": self.is_system,
            "created_at": to_iso(self.created_at),
            "updated_at": to_iso(self.updated_at),
        }


class Device(BaseModel):
    id = AutoField()
    device_code = CharField(max_length=64, unique=True)
    name = CharField(max_length=100, unique=True)
    protocol_template = ForeignKeyField(ProtocolTemplate, backref="devices", on_delete="CASCADE")
    connection_params = JSONField()
    template_variables = JSONField()
    poll_interval = FloatField(default=1.0)
    enabled = BooleanField(default=True)
    created_at = DateTimeField(default=utcnow)
    updated_at = DateTimeField(default=utcnow)

    class Meta:
        table_name = "devices"

    def save(self, *args: Any, **kwargs: Any) -> int:
        self.device_code = normalize_device_code(self.device_code)
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "device_code": self.device_code,
            "name": self.name,
            "protocol_template_id": self.protocol_template_id,
            "connection_params": self.connection_params,
            "template_variables": self.template_variables,
            "poll_interval": self.poll_interval,
            "enabled": self.enabled,
            "created_at": to_iso(self.created_at),
            "updated_at": to_iso(self.updated_at),
        }


def system_templates() -> list[dict[str, Any]]:
    return [
        {
            "name": "标准 Modbus 电子台秤",
            "description": "适用于大多数支持 Modbus TCP 的电子台秤",
            "protocol_type": "modbus_tcp",
            "template": {
                "name": "标准 Modbus 电子台秤",
                "protocol_type": "modbus_tcp",
                "variables": [
                    {"name": "slave_id", "type": "int", "default": 1, "label": "从站地址"},
                    {"name": "address", "type": "int", "default": 0, "label": "数据地址"},
                ],
                "steps": [
                    {
                        "id": "read_weight",
                        "name": "读取重量",
                        "trigger": "poll",
                        "action": "modbus.read_input_registers",
                        "params": {
                            "slave_id": "${slave_id}",
                            "address": "${address}",
                            "count": 2,
                        },
                        "parse": {
                            "type": "expression",
                            "expression": "registers[0] * 65536 + registers[1]",
                        },
                    }
                ],
                "output": {"weight": "${steps.read_weight.result}", "unit": "kg"},
            },
        },
        {
            "name": "MQTT 重量传感器",
            "description": "通过 MQTT 接收重量数据（推送模式）",
            "protocol_type": "mqtt",
            "template": {
                "name": "MQTT 重量传感器",
                "protocol_type": "mqtt",
                "variables": [
                    {"name": "topic", "type": "string", "default": "sensor/weight", "label": "主题"}
                ],
                "setup_steps": [
                    {
                        "id": "subscribe",
                        "name": "订阅重量主题",
                        "trigger": "setup",
                        "action": "mqtt.subscribe",
                        "params": {"topic": "${topic}", "qos": 1},
                    }
                ],
                "message_handler": {
                    "id": "handle_message",
                    "name": "处理接收到的消息",
                    "trigger": "event",
                    "action": "mqtt.on_message",
                    "parse": {
                        "type": "regex",
                        "pattern": "\"weight\"\\s*:\\s*([-+]?[0-9]*\\.?[0-9]+)",
                        "group": 1,
                    },
                },
                "output": {"weight": "${message_handler.result}", "unit": "kg"},
            },
        },
    ]


def seed_system_templates() -> None:
    for item in system_templates():
        row, created = ProtocolTemplate.get_or_create(
            name=item["name"],
            defaults={
                "description": item["description"],
                "protocol_type": item["protocol_type"],
                "template": item["template"],
                "is_system": True,
            },
        )

        # Compatibility migration for legacy MQTT system template parse config.
        if created or not row.is_system or row.protocol_type.lower() != "mqtt":
            continue

        template = row.template if isinstance(row.template, dict) else {}
        message_handler = template.get("message_handler")
        if not isinstance(message_handler, dict):
            continue

        parse_config = message_handler.get("parse")
        if not isinstance(parse_config, dict):
            continue
        if parse_config.get("type") != "expression":
            continue
        if str(parse_config.get("expression", "")).strip() != "float(payload)":
            continue

        migrated_template = dict(template)
        migrated_handler = dict(message_handler)
        migrated_handler["parse"] = {
            "type": "regex",
            "pattern": "\"weight\"\\s*:\\s*([-+]?[0-9]*\\.?[0-9]+)",
            "group": 1,
        }
        migrated_template["message_handler"] = migrated_handler
        row.template = migrated_template
        row.save()
