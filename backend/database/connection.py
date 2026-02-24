from __future__ import annotations

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

    from backend.database.models import Device, ProtocolTemplate, seed_system_templates

    database_proxy.create_tables([ProtocolTemplate, Device])

    if seed:
        seed_system_templates()


def close_db() -> None:
    if not database_proxy.is_closed():
        database_proxy.close()
