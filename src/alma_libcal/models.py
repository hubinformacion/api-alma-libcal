from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any
import unicodedata
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

# Storage keeps original fields; the reporting contract has explicit meanings.
USER_FIELDS = {
    "source_user_id": "user_id", "source_user_email": "source_user_email",
    "user_id": "verified_user_id", "user_email": "report_user_email",
    "user_full_name": "user_full_name", "user_first_name": "user_name", "user_last_name": "user_lastname",
    "user_type": "user_type", "user_modality": "user_modality", "user_campus_name": "user_campus",
    "user_program_name": "user_program", "user_department_name": "user_department",
    "user_business_unit_name": "user_business_unit", "user_match_status": "user_match_status",
}
TRACE_FIELDS = {"record_id": "record_id", "source_system": "source_system",
                "record_version": "record_version", "record_changed_at": "record_changed_at"}
ALMA_ITEM_FIELDS = {
    **TRACE_FIELDS, "loan_id": "loan_id", **USER_FIELDS,
    "item_id": "resource_id", "item_mms_id": "item_mms_id", "item_barcode": "item_barcode",
    "item_material_type_code": "item_material_type", "item_material_type_name": "material_name",
    "item_material_type_mapping_status": "material_mapping_status",
    "item_policy_name": "item_policy", "item_title": "resource_name",
}
LOAN_FIELDS = {
    **ALMA_ITEM_FIELDS,
    "loan_type": "loan_type", "loan_channel": "loan_channel",
    "loan_date": "activity_date", "loan_time": "loan_time", "in_house_loan_indicator": "in_house_loan_indicator",
    "loan_campus_code": "site_id", "loan_campus_name": "site_name", "loan_library_code": "loan_library_code",
    "loan_desk_code": "loan_desk_code", "loan_desk_name": "loan_desk_name",
    "loan_desk_description": "loan_desk_description", "loan_status": "status",
    "loan_month_name": "report_month", "loan_month_number": "report_month_number", "loan_hour": "report_hour",
}
RENEWAL_FIELDS = {
    **ALMA_ITEM_FIELDS, "renewal_type": "renewal_type",
    "renewal_date": "activity_date", "renewal_campus_code": "site_id", "renewal_campus_name": "site_name",
    "renewal_quantity": "quantity", "loan_status": "status",
    "loan_campus_code": "loan_origin_campus_code", "loan_campus_name": "loan_origin_campus_name",
    "report_campus_code": "report_campus_code", "report_campus_name": "report_campus",
    "report_campus_source": "report_campus_source",
    "renewal_month_name": "report_month", "renewal_month_number": "report_month_number",
}
RESERVATION_FIELDS = {
    **TRACE_FIELDS, "booking_id": "record_id", "source_booking_row_id": "source_booking_row_id", **USER_FIELDS,
    "booking_month_name": "report_month", "booking_month_number": "report_month_number",
    "booking_account_email": "booking_account_email", "booking_resource_name": "resource_name",
    "booking_category_code": "booking_category_code", "booking_category_name": "category",
    "source_booking_category_name": "source_booking_category_name",
    "booking_campus_name": "site_name", "booking_date": "activity_date",
    "booking_start_at": "starts_at", "booking_end_at": "ends_at",
    "booking_start_time": "start_time", "booking_end_time": "end_time",
    "booking_duration_hours": "duration_hours", "booking_hour": "report_hour",
    "booking_status": "booking_status_name", "source_booking_status": "status",
    "booking_attendance_status": "attendance_status", "booking_attendance_indicator": "attendance_indicator",
    "source_booking_attendance_status": "booking_check_in_status",
    "booking_phone": "booking_phone", "booking_terms_accepted": "terms_indicator",
    "source_booking_terms_response": "booking_terms_accepted",
    "booking_participant_2_email": "booking_form_answer_1", "booking_participant_3_email": "booking_form_answer_2",
    "booking_form_id": "booking_form_id", "booking_campus_code": "site_id", "booking_resource_id": "resource_id",
    "seat_id": "seat_id", "seat_name": "seat_name", "booking_account": "booking_account",
    "source_user_first_name": "source_user_name", "source_user_last_name": "source_user_lastname",
}
REPORT_FIELDS = {"prestamos": LOAN_FIELDS, "renovaciones": RENEWAL_FIELDS, "reservas": RESERVATION_FIELDS}
COMPACT_USER_FIELDS = (
    'source_user_id', 'user_id', 'user_email', 'user_type', 'user_modality', 'user_campus_name',
    'user_program_name', 'user_department_name', 'user_business_unit_name', 'user_match_status',
)
COMPACT_SHEET_FIELDS = {
    'prestamos': ('record_id', 'user_full_name', *COMPACT_USER_FIELDS, 'item_barcode',
                 'item_material_type_name', 'item_policy_name', 'item_title', 'loan_type',
                 'loan_date', 'loan_time', 'loan_campus_name', 'loan_status'),
    'renovaciones': ('record_id', 'loan_id', 'user_full_name', *COMPACT_USER_FIELDS, 'item_barcode',
                    'item_material_type_name', 'item_policy_name', 'item_title', 'renewal_type',
                    'renewal_date', 'renewal_quantity', 'report_campus_name', 'report_campus_source', 'loan_status'),
    'reservas': ('record_id', 'user_first_name', 'user_last_name', *COMPACT_USER_FIELDS,
                'booking_account_email', 'booking_resource_name', 'booking_category_name',
                'booking_campus_name', 'booking_date', 'booking_start_at', 'booking_end_at',
                'booking_duration_hours', 'booking_status', 'booking_attendance_status',
                'booking_attendance_indicator', 'booking_phone', 'booking_participant_2_email',
                'booking_participant_3_email', 'seat_name'),
}


def sheet_table(dataset, table, reporting=None):
    """Project only the public columns; never modify stored/full report data."""
    settings = reporting or {}
    names = settings.get('sheet_columns', {}).get(dataset)
    if names is None:
        names = COMPACT_SHEET_FIELDS[dataset] if settings.get('sheet_layout', 'compact') == 'compact' else table[0]
    if 'record_id' not in names or len(set(names)) != len(names) or any(name not in table[0] for name in names):
        raise SourceError('Las columnas de Sheets deben existir, ser únicas y conservar record_id.')
    indices = [table[0].index(name) for name in names]
    return [[row[i] for i in indices] for row in table]
MONTHS = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto',
          'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')


def report_headers(dataset, reporting=None):
    names = list(REPORT_FIELDS[dataset])
    if (reporting or {}).get('include_date_parts', True):
        return names
    return [name for name in names if not name.endswith(('_month_name', '_month_number', '_hour'))]


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


def campus_name(value):
    return value[7:].strip() if value.casefold().startswith('campus ') else value


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
    user_full_name: str = ""
    verified_user_id: str = ""
    verified_user_email: str = ""
    user_match_status: str = "pending"
    booking_check_in_status: str = ""
    booking_phone: str = ""
    booking_terms_accepted: str = ""
    source_booking_row_id: str = ""
    booking_category_code: str = ""
    source_booking_category_name: str = ""

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

    def report_values(self, reporting=None, audit=None) -> list:
        values = asdict(self)
        reporting = reporting or {}
        values.update(source_system='libcal' if self.dataset == 'reservas' else 'alma',
                      record_version=0, record_changed_at='', report_user_email=self.verified_user_email or self.source_user_email)
        values.update(audit or {})
        values.update(site_name=campus_name(self.site), loan_origin_campus_name=campus_name(self.loan_origin_campus))
        if self.dataset == 'prestamos' and self.in_house_loan_indicator == 'Y' and not self.user_id:
            values['user_match_status'] = 'not_applicable'
        catalog = reporting.get('material_types', {})
        values['material_name'] = catalog.get(self.item_material_type, 'Sin clasificar') if self.item_material_type else ''
        values['material_mapping_status'] = ('mapped' if self.item_material_type in catalog else
                                             'unmapped' if self.item_material_type else 'missing')
        # Old snapshots did not store the original loan ID separately.
        if self.dataset in ("prestamos", "renovaciones") and not self.loan_id:
            values["loan_id"] = self.record_id.split(":", 1)[0]
        values["user_id_missing"] = "sí" if not self.user_id else "no"
        day = date.fromisoformat(self.activity_date)
        values.update(report_month=MONTHS[day.month - 1], report_month_number=day.month, report_hour='')
        if self.dataset == 'prestamos':
            values['report_hour'] = hour(self.loan_time)
            desk = self.loan_desk_description + ' ' + self.loan_desk_name
            normalized = ''.join(ch for ch in unicodedata.normalize('NFD', desk.casefold()) if not unicodedata.combining(ch))
            if self.in_house_loan_indicator == 'Y':
                label, channel = 'Uso interno', 'in_house'
            elif 'autoprestamo' in normalized:
                label, channel = 'Préstamo regular por autopréstamo', 'self_check'
            elif desk.strip():
                label, channel = 'Préstamo regular por bibliotecario', 'staff'
            else:
                label, channel = 'Préstamo regular (módulo sin asignar)', 'unassigned'
            values.update(loan_type=label, loan_channel=channel)
        elif self.dataset == 'renovaciones':
            values['renewal_type'] = 'Renovación'
            # Choose one campus pair, never mix renewal code with loan name.
            if self.site_id or self.site:
                code, name, origin = self.site_id, self.site, 'renewal'
            elif self.loan_origin_campus_code or self.loan_origin_campus:
                code, name, origin = self.loan_origin_campus_code, self.loan_origin_campus, 'loan'
            else:
                code, name, origin = '', '', 'unassigned'
            values.update(report_campus_code=code, report_campus=campus_name(name), report_campus_source=origin)
        else:
            values['booking_account_email'] = self.booking_account if email_identifier(self.booking_account) else ''
            values['duration_minutes'] = ''
            values['duration_hours'] = ''
            status = self.status.strip().casefold()
            values['booking_status_name'] = ('Confirmado' if status == 'confirmed' else
                                            'Cancelado' if status.startswith(('cancelled', 'canceled')) else self.status)
            labels = reporting.get('attendance_statuses', {'in': 'Sí', 'out': 'Sí', '-': '-', 'no': 'No'})
            raw_attendance = self.booking_check_in_status.strip().casefold()
            attendance = labels.get(raw_attendance, 'Desconocido') if raw_attendance else '-'
            values['attendance_status'] = attendance
            values['attendance_indicator'] = 1 if attendance == 'Sí' else 0 if attendance == 'No' else ''
            terms = self.booking_terms_accepted.strip().casefold()
            values['terms_indicator'] = (1 if terms in ('acepto','sí','si','yes','true','1') else
                                         0 if terms in ('no','false','0') else '')
            values.update(start_time='', end_time='')
            if self.starts_at:
                start = datetime.fromisoformat(self.starts_at)
                values['report_hour'] = start.hour
                values['start_time'] = start.strftime('%H:%M:%S')
                if self.ends_at:
                    end = datetime.fromisoformat(self.ends_at)
                    values['end_time'] = end.strftime('%H:%M:%S')
                    duration = (end - start).total_seconds() / 60
                    if duration < 0:
                        raise SourceError('Una reserva tiene duración negativa.')
                    values['duration_minutes'] = duration
                    values['duration_hours'] = duration / 60
        return [values[REPORT_FIELDS[self.dataset][name]] for name in report_headers(self.dataset, reporting)]


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
