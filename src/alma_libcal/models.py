from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from .errors import SourceError

DATASETS = ("prestamos", "renovaciones", "reservas")
HEADERS = (
    "record_id", "activity_date", "user_id", "resource_id", "resource_name", "site",
    "status", "category", "starts_at", "ends_at", "check_in", "check_out", "quantity",
    "source_updated_at", "source_available_at", "user_id_missing",
    "site_id", "in_house_loan_indicator", "usage_type",
)


@dataclass(frozen=True)
class Interval:
    start: date
    end: date

    def __post_init__(self):
        if self.start > self.end:
            raise ValueError("La fecha inicial debe ser anterior o igual a la final.")

    def contains(self, value: str) -> bool:
        return self.start <= date.fromisoformat(value) <= self.end


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, bool)):
        raise SourceError("Un campo escalar tiene un formato inesperado; revisa el mapeo.")
    return str(value).strip()


def lookup(row: dict, path: str) -> Any:
    """Resolve explicit dotted paths, including array indices; never guess identity."""
    value: Any = row
    if not path:
        return None
    for key in path.split("."):
        if isinstance(value, dict):
            if key not in value:
                return None
            value = value[key]
        elif isinstance(value, list) and key.isdigit() and int(key) < len(value):
            value = value[int(key)]
        else:
            return None
    return value


def mapped(row: dict, fields: dict, name: str, *, required: bool = False) -> str:
    path = fields.get(name, "")
    value = text(lookup(row, path))
    if required and not value:
        raise SourceError(f"Falta el campo obligatorio {name}; revisa su mapeo.")
    return value


def local_datetime(value: str, timezone: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        zone = ZoneInfo(timezone)
        return parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed.astimezone(zone)
    except ValueError:
        raise SourceError("Fecha inválida; se requiere formato ISO 8601.") from None


def local_date(value: str, timezone: str) -> str:
    return local_datetime(value, timezone).date().isoformat()


def timestamp(value: str, timezone: str) -> str:
    return local_datetime(value, timezone).isoformat() if value else ""


def quantity(value: str) -> int:
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0 or number != number.to_integral_value():
            raise InvalidOperation
        return int(number)
    except (InvalidOperation, ValueError):
        raise SourceError("La cantidad debe ser un entero no negativo.") from None


@dataclass(frozen=True)
class Record:
    dataset: str
    record_id: str
    activity_date: str
    user_id: str = ""
    resource_id: str = ""
    resource_name: str = ""
    site: str = ""
    status: str = ""
    category: str = ""
    starts_at: str = ""
    ends_at: str = ""
    check_in: str = ""
    check_out: str = ""
    quantity: int = 1
    source_updated_at: str = ""
    source_available_at: str = ""
    site_id: str = ""
    in_house_loan_indicator: str = ""

    def __post_init__(self):
        if self.dataset not in DATASETS or not self.record_id:
            raise SourceError("Identificador de registro o conjunto inválido.")
        try:
            date.fromisoformat(self.activity_date)
        except ValueError:
            raise SourceError("Fecha normalizada inválida.") from None

    def values(self) -> list:
        values = asdict(self)
        internal = self.dataset == "prestamos" and self.in_house_loan_indicator == "Y"
        values["user_id_missing"] = "no aplica" if internal and not self.user_id else ("sí" if not self.user_id else "no")
        values["usage_type"] = ("Uso interno" if internal else "Préstamo") if self.dataset == "prestamos" else ""
        return [values[name] for name in HEADERS]


@dataclass
class Batch:
    records: list[Record] = field(default_factory=list)
    source_updated_at: str = ""
    source_available_at: str = ""

    def validate(self, dataset: str, interval: Interval) -> None:
        seen = set()
        for record in self.records:
            if record.dataset != dataset or not interval.contains(record.activity_date):
                raise SourceError("La extracción contiene registros fuera del conjunto o intervalo.")
            if record.record_id in seen:
                raise SourceError("La fuente devolvió claves duplicadas; revisa la granularidad del reporte.")
            seen.add(record.record_id)
