from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


DEVICE_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")


def _normalize_device_code(value: Any) -> str:
    code = str(value or "").strip().upper()
    if not code:
        raise ValueError("device_code is required")
    if not DEVICE_CODE_PATTERN.fullmatch(code):
        raise ValueError("device_code must match ^[A-Z0-9][A-Z0-9_-]{0,63}$")
    return code


class ProtocolTemplateBase(BaseModel):
    name: str
    description: str | None = None
    protocol_type: str
    template: dict[str, Any]


class ProtocolTemplateCreate(ProtocolTemplateBase):
    is_system: bool = False


class ProtocolTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    protocol_type: str | None = None
    template: dict[str, Any] | None = None


class DeviceBase(BaseModel):
    device_code: str
    name: str
    protocol_template_id: int
    connection_params: dict[str, Any] = Field(default_factory=dict)
    template_variables: dict[str, Any] = Field(default_factory=dict)
    poll_interval: float = 1.0
    enabled: bool = True


class DeviceCreate(DeviceBase):
    @field_validator("device_code", mode="before")
    @classmethod
    def validate_device_code(cls, value: Any) -> str:
        return _normalize_device_code(value)


class DeviceUpdate(BaseModel):
    device_code: str | None = None
    name: str | None = None
    protocol_template_id: int | None = None
    connection_params: dict[str, Any] | None = None
    template_variables: dict[str, Any] | None = None
    poll_interval: float | None = None
    enabled: bool | None = None

    @field_validator("device_code", mode="before")
    @classmethod
    def validate_device_code(cls, value: Any) -> str | None:
        if value is None:
            return None
        return _normalize_device_code(value)


class ExecuteStepRequest(BaseModel):
    step_id: str
    params: dict[str, Any] = Field(default_factory=dict)


class ProtocolTestRequest(BaseModel):
    connection_params: dict[str, Any] = Field(default_factory=dict)
    template_variables: dict[str, Any] = Field(default_factory=dict)
