"""[AI-MOD 2026-11-12] MySQL 访问封装（供 FastAPI 只读/轻写使用）。

口径与 importer 保持一致：口令只来自 app/.env 或真实环境变量，
连接按请求短开短关（本地单机、数据量小，够用且不会留下悬挂连接）。
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterable

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import Settings, load_settings

_SETTINGS: Settings | None = None


def settings() -> Settings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = load_settings()
    return _SETTINGS


def connect() -> pymysql.connections.Connection:
    s = settings()
    return pymysql.connect(
        host=s.db_host,
        port=s.db_port,
        user=s.db_user,
        password=s.db_password,
        database=s.db_name,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


@contextmanager
def cursor():
    conn = connect()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def query_all(sql: str, args: Iterable[Any] | None = None) -> list[dict]:
    with cursor() as cur:
        cur.execute(sql, tuple(args or ()))
        return list(cur.fetchall())


def query_one(sql: str, args: Iterable[Any] | None = None) -> dict | None:
    rows = query_all(sql, args)
    return rows[0] if rows else None


@contextmanager
def transaction():
    """写操作使用：正常提交，异常回滚。"""
    conn = connect()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def jloads(value: Any, default: Any = None):
    """MySQL JSON 列在 pymysql 里是 str，这里统一解码；已是对象则原样返回。"""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def jdumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def decode_row(row: dict | None, *fields: str) -> dict | None:
    """就地把指定 JSON 列解码成 Python 对象。"""
    if row is None:
        return None
    for f in fields:
        if f in row:
            row[f] = jloads(row[f])
    return row
