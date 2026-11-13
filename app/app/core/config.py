"""[AI-MOD 2026-11-12] 后端配置加载。

所有数据库口令只来自 `app/.env` 或真实环境变量，**不写死在代码里**。
优先级：真实环境变量 > .env 文件 > 代码缺省值（便于本地开发用 .env、部署用环境变量覆盖）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]   # ex/app
WORKSPACE_ROOT = APP_DIR.parent                 # ex
DEFAULT_ENV_FILE = APP_DIR / ".env"


def _read_env_file(path: Path) -> dict:
    """极简 .env 解析（KEY=VALUE，支持 # 注释与成对引号），不引入额外依赖。"""
    if not path.is_file():
        return {}
    out = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key.strip()] = val
    return out


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    artifact_root: str
    api_host: str
    api_port: int
    workspace_root: Path
    env_file: Path

    def dsn(self) -> str:
        """日志用的连接串，不含口令。"""
        return "mysql://%s@%s:%d/%s" % (self.db_user, self.db_host, self.db_port, self.db_name)


def load_settings(env_file: str | Path | None = None) -> Settings:
    ef = Path(env_file) if env_file else DEFAULT_ENV_FILE
    file_vals = _read_env_file(ef)

    def get(key: str, default: str = "") -> str:
        if os.environ.get(key):
            return os.environ[key]
        return file_vals.get(key, default)

    password = get("RSFUZZ_DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "RSFUZZ_DB_PASSWORD 未设置：请在 %s 中填写，或设置同名环境变量" % ef
        )
    return Settings(
        db_host=get("RSFUZZ_DB_HOST", "127.0.0.1"),
        db_port=int(get("RSFUZZ_DB_PORT", "3306")),
        db_name=get("RSFUZZ_DB_NAME", "rsfuzz"),
        db_user=get("RSFUZZ_DB_USER", "root"),
        db_password=password,
        artifact_root=get("RSFUZZ_ARTIFACT_ROOT", ""),
        api_host=get("RSFUZZ_API_HOST", "127.0.0.1"),
        api_port=int(get("RSFUZZ_API_PORT", "8000")),
        workspace_root=WORKSPACE_ROOT,
        env_file=ef,
    )
