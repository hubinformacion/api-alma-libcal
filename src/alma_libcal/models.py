from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
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
    "source_user_email", "booking_form_id", "booking_form_answer_1", "booking_form_answer_2",
    "seat_id", "seat_name",
)

# Each report exposes its own vocabulary; storage keys remain internal.
ALMA_ITEM_FIELDS = {
    "loan_id": "loan_id", "source_user_id": "user_id", "source_user_email": "source_user_email",
    "item_id": "resource_id", "item_mms_id": "item_mms_id", "item_barcode": "item_barcode",
    "item_material_type": "item_material_type", "item_policy": "item_policy", "item_title": "resource_name",
}
LOAN_FIELDS = {
    **ALMA_ITEM_FIELDS,
    "loan_date": "activity_date", "loan_time": "loan_time", "in_house_loan_indicator": "in_house_loan_indicator",
    "loan_campus_code": "site_id", "loan_campus": "site", "loan_library_code": "loan_library_code",
    "loan_desk_code": "loan_desk_code", "loan_desk_name": "loan_desk_name",
    "loan_desk_description": "loan_desk_description", "loan_status": "status",
    "loan_month": "report_month", "loan_month_number": "report_month_number", "loan_hour": "report_hour",
}
RENEWAL_FIELDS = {
    **ALMA_ITEM_FIELDS,
    "renewal_date": "activity_date", "renewal_campus_code": "site_id", "renewal_campus_name": "site",
    "renewal_quantity": "quantity", "loan_status": "status",
    "loan_campus_code": "loan_origin_campus_code", "loan_campus": "loan_origin_campus",
    "report_campus_code": "report_campus_code", "report_campus": "report_campus",
    "report_campus_source": "report_campus_source",
    "renewal_month": "report_month", "renewal_month_number": "report_month_number",
}
RESERVATION_FIELDS = {
    "booking_id": "record_id", "source_user_id": "user_id", "user_email": "source_user_email",
    **{name: name for name in ('user_name', 'user_lastname', 'user_type', 'user_modality', 'user_campus',
                             'user_program', 'user_department', 'user_business_unit')},
    "booking_month": "report_month", "booking_month_number": "report_month_number",
    "booking_account_email": "booking_account_email", "booking_resource": "resource_name",
    "booking_category": "category", "booking_campus": "site", "booking_date": "activity_date",
    "booking_start": "starts_at", "booking_end": "ends_at", "booking_duration_hours": "duration_hours",
    "booking_hour": "report_hour", "booking_status": "status", "booking_confirmation": "booking_confirmation",
    "booking_form_answer_1": "booking_form_answer_1", "booking_form_answer_2": "booking_form_answer_2",
    "booking_campus_code": "site_id", "booking_resource_id": "resource_id",
    "seat_id": "seat_id", "seat_name": "seat_name", "booking_account": "booking_account",
    "source_user_name": "source_user_name", "source_user_lastname": "source_user_lastname",
    "booking_duration_minutes": "duration_minutes",
}
REPORT_FIELDS = {"prestamos": LOAN_FIELDS, "renovaciones": RENEWAL_FIELDS, "reservas": RESERVATION_FIELDS}
MONTHS = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto',
          'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')


def report_headers(dataset):
    return list(REPORT_FIELDS[dataset])


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


def hour(value: str):
    if not value:
        return ""
    try:
        if value.isdigit() and 0 <= int(value) < 24:
            return int(value)
        return time.fromisoformat(value).hour
    except ValueError:
        raise SourceError('Hora inválida; se requiere una hora entre 0 y 23 o HH:MM:SS.') from None


def email_identifier(email: str) -> str:
    parts = email.strip().split('@')
    return parts[0] if len(parts) == 2 and all(parts) and not any(c.isspace() for c in email) else ''


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
    source_user_email: str = ""
    booking_form_id: str = ""
    booking_form_answer_1: str = ""
    booking_form_answer_2: str = ""
    seat_id: str = ""
    seat_name: str = ""
    loan_id: str = ""
    item_mms_id: str = ""
    item_barcode: str = ""
    item_material_type: str = ""
    item_policy: str = ""
    loan_time: str = ""
    loan_library_code: str = ""
    loan_desk_code: str = ""
    loan_desk_name: str = ""
    loan_desk_description: str = ""
    loan_origin_campus_code: str = ""
    loan_origin_campus: str = ""
    booking_account: str = ""
    source_user_name: str = ""
    source_user_lastname: str = ""
    user_name: str = ""
    user_lastname: str = ""
    user_type: str = ""
    user_modality: str = ""
    user_campus: str = ""
    user_program: str = ""
    user_department: str = ""
    user_business_unit: str = ""

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

    def report_values(self) -> list:
        values = asdict(self)
        # Old snapshots did not store the original loan ID separately.
        if self.dataset in ("prestamos", "renovaciones") and not self.loan_id:
            values["loan_id"] = self.record_id.split(":", 1)[0]
        values["user_id_missing"] = "sí" if not self.user_id else "no"
        day = date.fromisoformat(self.activity_date)
        values.update(report_month=MONTHS[day.month - 1], report_month_number=day.month, report_hour='')
        if self.dataset == 'prestamos':
            values['report_hour'] = hour(self.loan_time)
        elif self.dataset == 'renovaciones':
            # Choose one campus pair, never mix renewal code with loan name.
            if self.site_id or self.site:
                code, name, origin = self.site_id, self.site, 'renewal'
            elif self.loan_origin_campus_code or self.loan_origin_campus:
                code, name, origin = self.loan_origin_campus_code, self.loan_origin_campus, 'loan'
            else:
                code, name, origin = '', '', 'unassigned'
            values.update(report_campus_code=code, report_campus=name, report_campus_source=origin)
        else:
            values['booking_account_email'] = self.booking_account if email_identifier(self.booking_account) else ''
            values['duration_minutes'] = ''
            values['duration_hours'] = ''
            status = self.status.strip().casefold()
            values['booking_confirmation'] = ('Confirmado' if status == 'confirmed' else
                                              'Cancelado' if status.startswith(('cancelled', 'canceled')) else '')
            if self.starts_at:
                start = datetime.fromisoformat(self.starts_at)
                values['report_hour'] = start.hour
                if self.ends_at:
                    duration = (datetime.fromisoformat(self.ends_at) - start).total_seconds() / 60
                    if duration < 0:
                        raise SourceError('Una reserva tiene duración negativa.')
                    values['duration_minutes'] = duration
                    values['duration_hours'] = duration / 60
        return [values[name] for name in REPORT_FIELDS[self.dataset].values()]


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
