import os
import re
import shlex
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ConfigError


def load_env(path):
    """Load single-line KEY=value entries without executing shell code."""
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        raise ConfigError("No se pudo leer .env; revisa permisos y codificación UTF-8.") from None
    values = {}
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ConfigError(f"Formato inválido en .env, línea {number}; usa NOMBRE=valor.")
        try:
            parts = shlex.split(value, comments=True, posix=True)
        except ValueError:
            raise ConfigError(f"Comillas inválidas en .env, línea {number}.") from None
        values[key] = " ".join(parts)
    for key, value in values.items():
        os.environ.setdefault(key, value)


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
        reporting = raw.get('reporting', {})
        if not isinstance(reporting, dict):
            raise ConfigError('Configura reporting como una sección TOML.')
        if type(reporting.get('include_date_parts', True)) is not bool:
            raise ConfigError('reporting.include_date_parts debe ser true o false.')
        if reporting.get('sheet_layout', 'compact') not in ('compact', 'full'):
            raise ConfigError('reporting.sheet_layout debe ser compact o full.')
        overrides = reporting.get('sheet_columns', {})
        if not isinstance(overrides, dict):
            raise ConfigError('reporting.sheet_columns debe contener listas por conjunto.')
        from .models import DATASETS, report_headers
        for dataset, names in overrides.items():
            if dataset not in DATASETS or not isinstance(names, list) or not names or any(not isinstance(n,str) for n in names):
                raise ConfigError('Configura reporting.sheet_columns con listas de nombres de columnas.')
            if 'record_id' not in names or len(set(names)) != len(names) or any(n not in report_headers(dataset, reporting) for n in names):
                raise ConfigError('Las columnas de Sheets deben existir, ser únicas e incluir record_id.')
        for name in ('material_types', 'attendance_statuses'):
            catalog = reporting.get(name, {})
            if not isinstance(catalog, dict) or any(not isinstance(k,str) or not k or not isinstance(v,str) or not v for k,v in catalog.items()):
                raise ConfigError(f'Configura reporting.{name} como pares de código y nombre no vacíos.')
        if any(v not in ('Sí','No','-') for v in reporting.get('attendance_statuses', {}).values()):
            raise ConfigError('reporting.attendance_statuses solo admite Sí, No o - como resultado.')
        timezone = project.get("timezone", "America/Lima")
        ZoneInfo(timezone)
        start = date.fromisoformat(project.get("start_date", "2026-10-06"))
        base = path.resolve().parent
        load_env(base / ".env")
        database = Path(project.get("database", "data/pilot.sqlite3")).expanduser()
        if not database.is_absolute():
            database = base / database
        return Config(raw, base, timezone, start, database)
    except (OSError, ValueError, TypeError, ZoneInfoNotFoundError):
        raise ConfigError("No se pudo leer la configuración TOML; revisa ruta, fechas y zona horaria.") from None
