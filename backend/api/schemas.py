from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
    name: str
    protocol_template_id: int
    connection_params: dict[str, Any] = Field(default_factory=dict)
    template_variables: dict[str, Any] = Field(default_factory=dict)
    poll_interval: float = 1.0
    enabled: bool = True


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    name: str | None = None
    protocol_template_id: int | None = None
    connection_params: dict[str, Any] | None = None
    template_variables: dict[str, Any] | None = None
    poll_interval: float | None = None
    enabled: bool | None = None


class ExecuteStepRequest(BaseModel):
    step_id: str
    params: dict[str, Any] = Field(default_factory=dict)


class ProtocolTestRequest(BaseModel):
    connection_params: dict[str, Any] = Field(default_factory=dict)
    template_variables: dict[str, Any] = Field(default_factory=dict)
