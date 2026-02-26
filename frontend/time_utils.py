from __future__ import annotations

from datetime import datetime
from typing import Any


def format_timestamp(value: Any) -> str:
    if value in (None, ""):
        return "-"

    raw = str(value).strip()
    if not raw:
        return "-"

    normalized = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return raw

    if dt.tzinfo is not None:
        dt = dt.astimezone()

    return dt.strftime("%Y-%m-%d %H:%M:%S")
