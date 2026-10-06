import os
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ConfigError


def required(table: dict, key: str, context: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip() or "REPLACE" in value:
        raise ConfigError(f"Configura {context}.{key}.")
    return value.strip()


def positive(table: dict, key: str, default: int) -> int:
    value = table.get(key, default)
    if type(value) is not int or value < 1:
        raise ConfigError(f"{key} debe ser un entero positivo.")
    return value


def https_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise ConfigError("Configura una URL HTTPS sin credenciales, parámetros ni fragmentos.")
    return value.rstrip("/")


def secret(table: dict, name: str, context: str) -> str:
    env = required(table, name, context)
    value = os.environ.get(env, "").strip()
    if not value:
        raise ConfigError(f"Falta la variable de entorno {env}.")
    return value


@dataclass(frozen=True)
class Config:
    raw: dict
    base: Path
    timezone: str
    start_date: date
    database: Path

    def path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.base / path


def load_config(path: Path) -> Config:
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        project = raw.get("project", {})
        timezone = project.get("timezone", "America/Lima")
        ZoneInfo(timezone)
        start = date.fromisoformat(project.get("start_date", "2026-10-06"))
        base = path.resolve().parent
        database = Path(project.get("database", "data/pilot.sqlite3")).expanduser()
        if not database.is_absolute():
            database = base / database
        return Config(raw, base, timezone, start, database)
    except (OSError, ValueError, TypeError, ZoneInfoNotFoundError):
        raise ConfigError("No se pudo leer la configuración TOML; revisa ruta, fechas y zona horaria.") from None
