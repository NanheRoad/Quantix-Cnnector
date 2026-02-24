from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RuntimeState:
    device_id: int
    device_name: str
    status: str = "offline"
    weight: float | None = None
    unit: str = "kg"
    last_update: str | None = None
    error: str | None = None
    step_results: dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> dict[str, Any]:
        return {
            "type": "weight_update",
            "device_id": self.device_id,
            "device_name": self.device_name,
            "weight": self.weight,
            "unit": self.unit,
            "timestamp": self.last_update,
            "status": self.status,
            "error": self.error,
        }

    def mark_online(self, weight: float | None, unit: str) -> None:
        self.status = "online"
        self.weight = weight
        self.unit = unit
        self.error = None
        self.last_update = datetime.now(timezone.utc).isoformat()

    def mark_offline(self, error: str | None = None) -> None:
        self.status = "offline"
        self.error = error
        self.last_update = datetime.now(timezone.utc).isoformat()

    def mark_error(self, error: str) -> None:
        self.status = "error"
        self.error = error
        self.last_update = datetime.now(timezone.utc).isoformat()
