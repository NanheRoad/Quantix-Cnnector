from __future__ import annotations

from typing import Any

from peewee import DatabaseProxy, MySQLDatabase, SqliteDatabase

from config.settings import settings


database_proxy = DatabaseProxy()


def build_database():
    if settings.db_type == "mysql":
        return MySQLDatabase(
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port,
            charset="utf8mb4",
        )

    return SqliteDatabase(
        settings.db_name,
        pragmas={
            "journal_mode": "wal",
            "cache_size": -1024 * 64,
            "foreign_keys": 1,
            "synchronous": 0,
        },
    )


def init_db(seed: bool = True) -> None:
    if database_proxy.obj is None:
        database_proxy.initialize(build_database())

    if database_proxy.is_closed():
        database_proxy.connect(reuse_if_open=True)

    from backend.database.models import (
        Device,
        ProtocolTemplate,
        build_default_device_code,
        normalize_device_code,
        seed_system_templates,
    )

    if not ProtocolTemplate.table_exists():
        ProtocolTemplate.create_table(safe=True)
    if not Device.table_exists():
        Device.create_table(safe=True)

    _ensure_device_code_schema(
        normalize_code=normalize_device_code,
        default_code_builder=build_default_device_code,
    )

    if seed:
        seed_system_templates()


def close_db() -> None:
    if not database_proxy.is_closed():
        database_proxy.close()


def _ensure_device_code_schema(
    normalize_code,
    default_code_builder,
) -> None:
    table_name = "devices"
    columns = {column.name for column in database_proxy.get_columns(table_name)}
    if "device_code" not in columns:
        database_proxy.execute_sql("ALTER TABLE devices ADD COLUMN device_code VARCHAR(64)")

    placeholder = "%s" if settings.db_type == "mysql" else "?"

    def fetch_rows(sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        cursor = database_proxy.execute_sql(sql, params)
        return [tuple(row) for row in cursor.fetchall()]

    def update_row(sql: str, params: tuple[Any, ...]) -> None:
        database_proxy.execute_sql(sql, params)

    rows = fetch_rows("SELECT id, device_code FROM devices ORDER BY id ASC")
    used_codes: set[str] = set()

    for row in rows:
        device_id = int(row[0])
        raw_code = row[1]

        try:
            normalized = normalize_code(raw_code)
        except Exception:
            normalized = default_code_builder(device_id)

        candidate = normalized
        suffix = 1
        while candidate in used_codes:
            suffix_text = f"-{suffix}"
            max_base_len = 64 - len(suffix_text)
            candidate = f"{normalized[:max_base_len]}{suffix_text}"
            suffix += 1

        used_codes.add(candidate)

        if raw_code != candidate:
            update_row(
                f"UPDATE devices SET device_code = {placeholder} WHERE id = {placeholder}",
                (candidate, device_id),
            )

    indexes = database_proxy.get_indexes(table_name)
    has_unique_index = any(
        set(index.columns) == {"device_code"} and bool(index.unique)
        for index in indexes
    )
    if not has_unique_index:
        database_proxy.execute_sql("CREATE UNIQUE INDEX idx_devices_device_code_unique ON devices(device_code)")
