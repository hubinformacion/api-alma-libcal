import hashlib
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..config import https_url, positive, required, secret
from ..errors import ConfigError, SourceError
from ..models import Batch, Record, email_identifier, local_date, lookup, mapped, timestamp

CATEGORY_NAMES = {"Computadoras y laptops", "Espacios grupales", "Kindle"}


def current_date(timezone):
    return datetime.now(ZoneInfo(timezone)).date()


def numeric_ids(values):
    ids = [str(value) for value in values]
    if not ids or any(not value.isdigit() or int(value) < 1 for value in ids):
        raise ConfigError("Los IDs de LibCal deben ser números positivos.")
    return ",".join(ids)


class LibCalConnector:
    def __init__(self, config, http):
        self.config = config
        self.http = http

    def authenticate(self, settings, base):
        token_path = required(settings, "token_path", "libcal")
        if not token_path.startswith("/") or token_path.startswith("//") or "?" in token_path or "#" in token_path:
            raise ConfigError("libcal.token_path debe ser una ruta relativa que comience con /.")
        access = self.http.json("POST", base + token_path, form={
            "grant_type": "client_credentials",
            "client_id": secret(settings, "client_id_env", "libcal"),
            "client_secret": secret(settings, "client_secret_env", "libcal"),
        })
        if not isinstance(access, dict) or not isinstance(access.get("access_token"), str) or not access["access_token"]:
            raise SourceError("LibCal no devolvió un token de acceso válido.")
        return {"Authorization": "Bearer " + access["access_token"], "Accept": "application/json"}

    def discover(self, locations=None, category=None, form=None):
        settings = self.config.raw.get("libcal", {})
        base = https_url(required(settings, "base_url", "libcal"))
        headers = self.authenticate(settings, base)
        params = {"details": "1", "admin_only": "1"}
        if locations:
            path = "/1.1/space/categories/" + numeric_ids(locations)
        elif category:
            path = "/1.1/space/category/" + numeric_ids([category])
        elif form:
            path = "/1.1/space/form/" + numeric_ids([form])
            params = {}
        else:
            path = "/1.1/space/locations"
        result = self.http.json("GET", base + path, params=params, headers=headers)
        if not isinstance(result, (list, dict)) or (isinstance(result, dict) and ("error" in result or "errors" in result)):
            raise SourceError("LibCal no devolvió metadatos de ubicaciones válidos.")
        return result

    def check_bookings(self, day, location, category=None):
        """Read all pages for one day; return only counts and field names."""
        if day < current_date(self.config.timezone):
            raise ConfigError("LibCal ignora fechas pasadas en /space/bookings. Prueba con hoy o una fecha futura; "
                              "este endpoint no permite validar una carga histórica.")
        settings = self.config.raw.get("libcal", {})
        base = https_url(required(settings, "base_url", "libcal"))
        params = {"lid": numeric_ids([location]), "date": day.isoformat(), "days": 0, "limit": 100,
                  "form_answers": 1, "include_cancel": 1, "include_tentative": 1, "include_denied": 1,
                  "check_in_status": 1}
        if category:
            params["cid"] = numeric_ids([category])
        headers = self.authenticate(settings, base)
        fields, statuses, campuses, count = set(), Counter(), Counter(), 0
        fingerprints = set()
        for page in range(1, positive(settings, "max_pages", 10000) + 1):
            rows = self.http.json("GET", base + "/1.1/space/bookings", params={**params, "page": page}, headers=headers)
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise SourceError("LibCal no devolvió una lista de reservas válida.")
            if not rows:
                return {"authentication": "ok", "date": day.isoformat(), "location_id": str(location),
                        "category_id": str(category or ""), "rows": count, "pages": page,
                        "statuses": dict(statuses), "campus_counts": dict(campuses), "fields": sorted(fields)}
            fingerprint = hashlib.sha256(repr(rows).encode()).digest()
            if fingerprint in fingerprints:
                raise SourceError("LibCal repitió una página; no se puede confirmar la consulta completa.")
            fingerprints.add(fingerprint)
            for row in rows:
                if str(row.get("lid", "")) != str(location) or (category and str(row.get("cid", "")) != str(category)):
                    raise SourceError("LibCal devolvió reservas de otro campus/categoría; revisa los filtros.")
                fields.update(row.keys())
                if local_date(str(row.get("fromDate", "")), self.config.timezone) == day.isoformat():
                    count += 1
                    statuses[str(row.get("status", ""))] += 1
                    campuses[str(row.get("lid", ""))] += 1
        raise SourceError("LibCal alcanzó max_pages antes de completar la prueba.")

    def fetch(self, interval):
        if interval.start < current_date(self.config.timezone):
            raise ConfigError("LibCal ignora fechas pasadas en /space/bookings. No se puede extraer ese histórico con este endpoint; "
                              "usa una exportación histórica o una fuente documentada que lo permita.")
        settings = self.config.raw.get("libcal", {})
        base = https_url(required(settings, "base_url", "libcal"))
        endpoint = required(settings, "bookings_path", "libcal")
        token_path = required(settings, "token_path", "libcal")
        for value in (endpoint, token_path):
            if not value.startswith("/") or value.startswith("//") or "?" in value or "#" in value:
                raise ConfigError("Los endpoints de LibCal deben ser rutas relativas que comiencen con /.")
        fields = settings.get("fields", {})
        for name in ("booking_id", "starts_at", "ends_at", "resource_id", "status"):
            required(fields, name, "libcal.fields")
        if any(not isinstance(value, str) or "REPLACE" in value for value in fields.values()):
            raise ConfigError("Reemplaza los campos de ejemplo de libcal.fields por los de tu instancia.")
        categories = settings.get("categories", [])
        if not categories or any(item.get("name") not in CATEGORY_NAMES for item in categories):
            raise ConfigError("Configura categorías de Computadoras y laptops, Espacios grupales o Kindle; puedes repetir grupos por campus.")
        ids = [required(item, "id", "libcal.categories") for item in categories]
        if len(set(ids)) != len(ids):
            raise ConfigError("Los identificadores de categorías deben ser distintos.")
        templates = settings.get("query", {})
        if not templates or not any("{date}" in str(value) for value in templates.values()):
            raise ConfigError("Configura libcal.query con el parámetro de fecha documentado en Admin → API.")
        if not any("{category_id}" in str(value) for value in templates.values()):
            raise ConfigError("Configura libcal.query con el filtro de categoría.")
        mode = settings.get("pagination", "offset")
        if mode not in ("offset", "page", "none"):
            raise ConfigError("libcal.pagination debe ser offset, page o none.")
        if mode != "none" and not any("{" + mode + "}" in str(value) for value in templates.values()):
            raise ConfigError("Configura el parámetro de paginación de LibCal.")
        headers = self.authenticate(settings, base)
        records = {}
        day = interval.start
        limit = positive(settings, "page_size", 100)
        window_days = positive(settings, "window_days", 1)
        while day <= interval.end:
            days = min(window_days, (interval.end - day).days + 1)
            end = day + timedelta(days=days - 1)
            for category in categories:
                fingerprints = set()
                offset = 0
                page_start = settings.get("page_start", 1)
                if type(page_start) is not int or page_start < 0:
                    raise ConfigError("libcal.page_start debe ser un entero no negativo.")
                for index in range(positive(settings, "max_pages", 10000)):
                    variables = {"date": day.isoformat(), "end_date": end.isoformat(), "days": days - 1,
                                 "category_id": category["id"], "limit": limit, "offset": offset,
                                 "page": index + page_start, "location_id": category.get("location_id", "")}
                    try:
                        params = {key: str(value).format(**variables) for key, value in templates.items()}
                    except (KeyError, ValueError):
                        raise ConfigError("libcal.query contiene una plantilla desconocida o inválida.") from None
                    payload = self.http.json("GET", base + endpoint, params=params, headers=headers)
                    if isinstance(payload, dict) and ("error" in payload or "errors" in payload):
                        raise SourceError("LibCal devolvió un error de consulta.")
                    response_path = settings.get("response_path", "")
                    rows = lookup(payload, response_path) if response_path else payload
                    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                        raise SourceError("La respuesta de LibCal no contiene la lista configurada.")
                    if not rows:
                        break
                    fingerprint = hashlib.sha256(repr(rows).encode()).digest()
                    if fingerprint in fingerprints:
                        raise SourceError("LibCal repitió una página; verifica sus parámetros de paginación.")
                    fingerprints.add(fingerprint)
                    for row in rows:
                        record = self.normalize(row, fields, category)
                        if not interval.contains(record.activity_date):
                            continue
                        previous = records.get(record.record_id)
                        if previous is not None and previous != record:
                            raise SourceError("LibCal devolvió versiones contradictorias de una reserva.")
                        records[record.record_id] = record
                    if mode == "none":
                        break
                    # Continue until an EMPTY page, even when the server caps page sizes.
                    offset += len(rows)
                else:
                    raise SourceError("LibCal alcanzó max_pages antes de completar la consulta.")
            day = end + timedelta(days=1)
        batch = Batch(list(records.values()))
        batch.validate("reservas", interval)
        return batch

    def normalize(self, row, fields, category):
        timezone = self.config.timezone
        if fields.get("category_id") and mapped(row, fields, "category_id", required=True) != category["id"]:
            raise SourceError("LibCal devolvió una reserva de otra categoría; revisa el filtro configurado.")
        site_id = mapped(row, fields, "site_id")
        if category.get("location_id") and site_id and site_id != str(category["location_id"]):
            raise SourceError("LibCal devolvió una reserva de otro campus; revisa la categoría y location_id.")
        starts_at = timestamp(mapped(row, fields, "starts_at", required=True), timezone)
        ends_at = timestamp(mapped(row, fields, "ends_at", required=True), timezone)
        if ends_at < starts_at:
            raise SourceError("Una reserva tiene fin anterior a su inicio.")
        form_id = str(category.get("form_id", ""))
        form = self.config.raw.get("libcal", {}).get("forms", {}).get(form_id, {})
        answers = form.get("report_fields", {})
        if not isinstance(answers, dict) or any(not isinstance(value, str) for value in answers.values()):
            raise ConfigError("Configura libcal.forms.report_fields con los IDs de pregunta como texto.")
        email = mapped(row, fields, 'source_user_email')
        user_id = mapped(row, fields, 'user_id')
        if not user_id and self.config.raw.get('libcal', {}).get('user_id_from_email', False):
            user_id = email_identifier(email)
        return Record(
            dataset="reservas", record_id=mapped(row, fields, "booking_id", required=True),
            activity_date=local_date(starts_at, timezone), user_id=user_id,
            resource_id=mapped(row, fields, "resource_id", required=True),
            resource_name=mapped(row, fields, "resource_name"), site=mapped(row, fields, "site"),
            site_id=site_id,
            status=mapped(row, fields, "status", required=True), category=category["name"],
            starts_at=starts_at, ends_at=ends_at,
            check_in=timestamp(mapped(row, fields, "check_in"), timezone),
            check_out=timestamp(mapped(row, fields, "check_out"), timezone),
            source_user_email=email,
            booking_account=mapped(row, fields, 'booking_account'),
            booking_check_in_status=mapped(row, fields, 'booking_check_in_status'),
            booking_phone=mapped(row, fields, 'booking_phone'),
            booking_terms_accepted=mapped(row, fields, 'booking_terms_accepted'),
            source_booking_row_id=mapped(row, fields, 'source_booking_row_id'),
            booking_category_code=category['id'],
            source_booking_category_name=mapped(row, fields, 'source_booking_category_name'),
            source_user_name=mapped(row, fields, 'source_user_name'),
            source_user_lastname=mapped(row, fields, 'source_user_lastname'),
            booking_form_id=form_id if form_id != "0" else "",
            booking_form_answer_1=mapped(row, answers, "booking_form_answer_1"),
            booking_form_answer_2=mapped(row, answers, "booking_form_answer_2"),
            seat_id=mapped(row, fields, "seat_id"),
            seat_name=mapped(row, fields, "seat_name"),
        )
