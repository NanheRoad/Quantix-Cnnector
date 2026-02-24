from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_type: str = os.getenv("DB_TYPE", "sqlite").lower()
    db_name: str = os.getenv("DB_NAME", "quantix.db")
    db_user: str = os.getenv("DB_USER", "")
    db_password: str = os.getenv("DB_PASSWORD", "")
    db_host: str = os.getenv("DB_HOST", "127.0.0.1")
    db_port: int = int(os.getenv("DB_PORT", "3306"))

    api_key: str = os.getenv("API_KEY", "quantix-dev-key")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    backend_host: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))

    frontend_host: str = os.getenv("FRONTEND_HOST", "127.0.0.1")
    frontend_port: int = int(os.getenv("FRONTEND_PORT", "8050"))

    # ture表示用模拟数据，false 表示：连不上真实设备就报离线/错误，不再返回随机测试值
    # SIMULATE_ON_CONNECT_FAIL=false
    simulate_on_connect_fail: bool = os.getenv("SIMULATE_ON_CONNECT_FAIL", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


settings = Settings()
