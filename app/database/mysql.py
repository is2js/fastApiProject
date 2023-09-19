from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, text


class MySQL:
    query_set_format_map: dict = {
        "exists_user": "SELECT EXISTS(SELECT 1 FROM mysql.user WHERE user = '{user}');",
        "create_user": "CREATE USER '{user}'@'{host}' IDENTIFIED BY '{password}'",
        "is_user_granted": (
            "SELECT * FROM information_schema.schema_privileges "
            "WHERE table_schema = '{database}' AND grantee = '{user}';"
        ),
        "grant_user": "GRANT {grant} ON {on} TO '{to_user}'@'{user_host}'",

        "is_db_exists": "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{database}';",
        "create_db": "CREATE DATABASE {database} CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;",
        "drop_db": "DROP DATABASE {database};",
    }

    @staticmethod
    def execute(query: str, engine: Engine, scalar: bool = False) -> Any | None:
        with engine.connect() as conn:
            cursor = conn.execute(
                text(query + ";" if not query.endswith(";") else query)
            )
            return cursor.scalar() if scalar else None

    @classmethod
    def exists_user(cls, user: str, engine: Engine) -> bool:
        return bool(
            cls.execute(
                cls.query_set_format_map["exists_user"].format(user=user),
                engine,
                scalar=True,
            )
        )

    @classmethod
    def create_user(cls, user: str, password: str, host: str, engine: Engine) -> None:
        return cls.execute(
            cls.query_set_format_map["create_user"].format(
                user=user, password=password, host=host
            ),
            engine,
        )

    @classmethod
    def is_user_granted(cls, user: str, database: str, engine: Engine) -> bool:
        return bool(
            cls.execute(
                cls.query_set_format_map["is_user_granted"].format(user=user, database=database),
                engine,
                scalar=True,
            )
        )

    @classmethod
    def grant_user(
            cls,
            grant: str,
            on: str,
            to_user: str,
            user_host: str,
            engine: Engine
    ) -> None:
        return cls.execute(
            cls.query_set_format_map["grant_user"].format(
                grant=grant, on=on, to_user=to_user, user_host=user_host
            ),
            engine,
        )

    @classmethod
    def drop_db(cls, database: str, engine: Engine) -> None:
        return cls.execute(
            cls.query_set_format_map["drop_db"].format(database=database),
            engine,
        )

    @classmethod
    def create_db(cls, database: str, engine: Engine) -> None:
        return cls.execute(
            cls.query_set_format_map["create_db"].format(database=database),
            engine,
        )
