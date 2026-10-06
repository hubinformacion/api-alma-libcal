import hashlib
from datetime import timedelta

from ..config import https_url, positive, required, secret
from ..errors import ConfigError, SourceError
from ..models import Batch, Record, local_date, lookup, mapped, timestamp

CATEGORY_NAMES = {"Computadoras y laptops", "Espacios grupales", "Kindle"}


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

    def discover(self):
        settings = self.config.raw.get("libcal", {})
        base = https_url(required(settings, "base_url", "libcal"))
        headers = self.authenticate(settings, base)
        result = self.http.json("GET", base + "/1.1/space/locations", params={"details": "1"}, headers=headers)
        if not isinstance(result, (list, dict)) or (isinstance(result, dict) and ("error" in result or "errors" in result)):
            raise SourceError("LibCal no devolvió metadatos de ubicaciones válidos.")
        return result

    def fetch(self, interval):
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
        if {item.get("name") for item in categories} != CATEGORY_NAMES or len(categories) != 3:
            raise ConfigError("Configura exactamente las tres categorías del piloto de LibCal.")
        ids = [required(item, "id", "libcal.categories") for item in categories]
        if len(set(ids)) != 3:
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
                    variables = {"date": day.isoformat(), "end_date": end.isoformat(), "days": days,
                                 "category_id": category["id"], "limit": limit, "offset": offset,
                                 "page": index + page_start}
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
        starts_at = timestamp(mapped(row, fields, "starts_at", required=True), timezone)
        ends_at = timestamp(mapped(row, fields, "ends_at", required=True), timezone)
        if ends_at < starts_at:
            raise SourceError("Una reserva tiene fin anterior a su inicio.")
        return Record(
            dataset="reservas", record_id=mapped(row, fields, "booking_id", required=True),
            activity_date=local_date(starts_at, timezone), user_id=mapped(row, fields, "user_id"),
            resource_id=mapped(row, fields, "resource_id", required=True),
            resource_name=mapped(row, fields, "resource_name"), site=mapped(row, fields, "site"),
            status=mapped(row, fields, "status", required=True), category=category["name"],
            starts_at=starts_at, ends_at=ends_at,
            check_in=timestamp(mapped(row, fields, "check_in"), timezone),
            check_out=timestamp(mapped(row, fields, "check_out"), timezone),
        )
