"""
Neo4j 连接配置（兼容 Neo4j Aura 与本地实例）。

Aura 控制台常见变量名：
  NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE

优先级：环境变量 > config.yaml > 默认值
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    global _ENV_LOADED
    if not _ENV_LOADED:
        load_dotenv(_ROOT / ".env")
        _ENV_LOADED = True


def _load_yaml_neo4j() -> dict[str, Any]:
    config_path = _ROOT / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("neo4j", {})
    except Exception:
        return {}


def get_neo4j_settings() -> dict[str, str]:
    """返回 uri / user / password / database 四项连接配置。"""
    _ensure_env_loaded()
    cfg = _load_yaml_neo4j()

    uri = os.getenv("NEO4J_URI") or cfg.get("uri") or "bolt://localhost:7687"
    user = (
        os.getenv("NEO4J_USERNAME")
        or os.getenv("NEO4J_USER")
        or cfg.get("user")
        or "neo4j"
    )
    password = os.getenv("NEO4J_PASSWORD") or cfg.get("password") or "password"
    database = os.getenv("NEO4J_DATABASE") or cfg.get("database") or "neo4j"

    return {
        "uri": uri,
        "user": user,
        "password": password,
        "database": database,
    }
