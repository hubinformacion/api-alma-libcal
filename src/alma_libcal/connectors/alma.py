import hashlib
from dataclasses import replace
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from ..config import https_url, positive, required, secret
from ..errors import ConfigError, SourceError
from ..models import Batch, Record, local_date, mapped, quantity


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def parse_xml(raw):
    upper = raw.upper() if isinstance(raw, bytes) else raw.upper().encode()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise SourceError("El XML contiene declaraciones no permitidas.")
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        raise SourceError("Alma no devolvió XML válido.") from None


def parse_page(raw):
    root = parse_xml(raw)
    if any(local_name(node.tag) in ("errorList", "errorCode", "error") for node in root.iter()):
        raise SourceError("Alma devolvió un error de reporte; revisa permisos, ruta y filtros.")
    nodes = list(root.iter())
    finished = next((node.text or "" for node in nodes if local_name(node.tag) == "IsFinished"), "").strip().lower()
    if finished not in ("true", "false"):
        raise SourceError("Falta IsFinished en la respuesta; no se puede verificar su integridad.")
    token = next((node.text or "" for node in nodes if local_name(node.tag) == "ResumptionToken"), "").strip()
    for node in nodes:
        if local_name(node.tag) == "ResultXml" and not len(node) and (node.text or "").strip():
            nodes.extend(parse_xml(node.text).iter())
    if not any(local_name(node.tag).lower() == "rowset" for node in nodes):
        raise SourceError("Falta el rowset del reporte; no se puede confirmar una respuesta vacía.")
    rows = []
    for node in nodes:
        if local_name(node.tag).lower() == "row":
            rows.append({local_name(child.tag): "".join(child.itertext()).strip() for child in node})
    # IsFinished=true with zero rows is a valid empty report.
    return rows, finished == "true", token


def date_filter(column, interval):
    return (
        '<sawx:expr xsi:type="sawx:comparison" op="between" '
        'xmlns:saw="com.siebel.analytics.web/report/v1.1" '
        'xmlns:sawx="com.siebel.analytics.web/expression/v1.1" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
        f'<sawx:expr xsi:type="sawx:sqlExpression">{escape(column)}</sawx:expr>'
        f'<sawx:expr xsi:type="xsd:date">{interval.start.isoformat()}</sawx:expr>'
        f'<sawx:expr xsi:type="xsd:date">{interval.end.isoformat()}</sawx:expr>'
        '</sawx:expr>'
    )


class AlmaConnector:
    def __init__(self, config, http, dataset):
        self.config = config
        self.http = http
        self.dataset = dataset

    def inspect(self, interval, *, without_filter=False):
        settings = self.config.raw.get("alma", {})
        report = settings.get(self.dataset, {})
        path = required(report, "report_path", f"alma.{self.dataset}")
        if not path.startswith("/shared/"):
            raise ConfigError("La ruta API de Alma debe comenzar por /shared/, no /Shared Folders/ ni My Folders.")
        params = {"path": path, "limit": 25, "apikey": secret(settings, "api_key_env", "alma"), "col_names": "true"}
        if not without_filter:
            params["filter"] = date_filter(required(report, "date_column", f"alma.{self.dataset}"), interval)
        try:
            raw = self.http.request("GET", https_url(required(settings, "base_url", "alma")) + "/almaws/v1/analytics/reports",
                params=params, headers={"Accept": "application/xml"})
        except SourceError as error:
            if "HTTP 500" in str(error):
                raise SourceError("Alma respondió HTTP 500. Verifica ruta /shared/, permisos Analytics/Production y región. "
                                  "Prueba inspect-alma --dataset " + self.dataset + " --without-filter para aislar el filtro de fecha.") from None
            raise
        rows, _, _ = parse_page(raw)
        root = parse_xml(raw)
        nodes = list(root.iter())
        for node in list(nodes):
            if local_name(node.tag) == "ResultXml" and not len(node) and (node.text or "").strip():
                nodes.extend(parse_xml(node.text).iter())
        columns = {}
        for node in nodes:
            name = node.attrib.get("name", "")
            if local_name(node.tag) == "element" and name.startswith("Column"):
                attributes = {local_name(key): value for key, value in node.attrib.items()}
                columns[name] = {"column": name, "heading": attributes.get("columnHeading", ""),
                                 "type": attributes.get("type", "")}
        for row in rows:
            for name in row:
                columns.setdefault(name, {"column": name, "heading": "", "type": ""})
        return list(columns.values())

    def fetch(self, interval):
        settings = self.config.raw.get("alma", {})
        report = settings.get(self.dataset, {})
        fields = report.get("fields", {})
        url = https_url(required(settings, "base_url", "alma")) + "/almaws/v1/analytics/reports"
        key = secret(settings, "api_key_env", "alma")
        path = required(report, "report_path", f"alma.{self.dataset}")
        if not path.startswith("/shared/"):
            raise ConfigError("La ruta API de Alma debe comenzar por /shared/.")
        column = required(report, "date_column", f"alma.{self.dataset}")
        for name in ("loan_id", "activity_date"):
            required(fields, name, f"alma.{self.dataset}.fields")
        if self.dataset == "renovaciones":
            required(fields, "quantity", "alma.renovaciones.fields")
        limit = positive(settings, "page_size", 1000)
        if limit > 1000 or limit < 25 or limit % 25:
            raise ConfigError("alma.page_size debe ser múltiplo de 25 entre 25 y 1000.")
        params = {"path": path, "filter": date_filter(column, interval), "limit": limit, "col_names": "true", "apikey": key}
        records = []
        token = ""
        fingerprints = set()
        updated, available = set(), set()
        for _ in range(positive(settings, "max_pages", 10000)):
            # Continuation tokens advance a server-side cursor. A lost response
            # must fail this extraction rather than retry and silently skip rows.
            raw = self.http.request("GET", url, params=params, headers={"Accept": "application/xml"}, retry=not bool(token))
            rows, finished, new_token = parse_page(raw)
            fingerprint = hashlib.sha256(repr(rows).encode()).digest()
            if rows and fingerprint in fingerprints:
                raise SourceError("Alma repitió una página; se cancela la extracción incompleta.")
            fingerprints.add(fingerprint)
            for row in rows:
                record = self.normalize(row, fields)
                if record.source_updated_at:
                    updated.add(record.source_updated_at)
                if record.source_available_at:
                    available.add(record.source_available_at)
                if interval.contains(record.activity_date):
                    records.append(record)
            if finished:
                batch = Batch(records, self.watermark(updated), self.watermark(available))
                batch.records = [replace(record, source_updated_at=batch.source_updated_at,
                                         source_available_at=batch.source_available_at) for record in records]
                batch.validate(self.dataset, interval)
                return batch
            if not rows:
                raise SourceError("Alma devolvió una página vacía sin finalizar el reporte.")
            token = new_token or token  # Alma may reuse one token throughout the session.
            if not token:
                raise SourceError("Alma indicó más páginas sin proporcionar un token.")
            params = {"token": token, "limit": limit, "col_names": "true", "apikey": key}
        raise SourceError("Alma alcanzó max_pages antes de completar el reporte.")

    @staticmethod
    def watermark(values):
        if len(values) > 1:
            raise SourceError("El reporte mezcla fechas de actualización; reintenta tras la carga de Analytics.")
        return next(iter(values), "")

    def normalize(self, row, fields):
        loan_id = mapped(row, fields, "loan_id", required=True)
        day = local_date(mapped(row, fields, "activity_date", required=True), self.config.timezone)
        renewal = self.dataset == "renovaciones"
        site_id = mapped(row, fields, "site_id")
        indicator = mapped(row, fields, "in_house_loan_indicator").upper()
        if indicator not in ("", "Y", "N"):
            raise SourceError("In House Loan Indicator debe ser Y, N o vacío; conserva el indicador original.")
        user_id = mapped(row, fields, "user_id")
        # Existing Analytics formulas use this activity label instead of a user ID.
        if not renewal and indicator == "Y" and user_id.casefold() == "uso interno":
            user_id = ""
        email = mapped(row, fields, "source_user_email")
        if not renewal and indicator == "Y" and email.casefold() == "uso interno":
            email = ""
        record_id = f"{loan_id}:{day}:{site_id}" if renewal and site_id else (f"{loan_id}:{day}" if renewal else loan_id)
        return Record(
            dataset=self.dataset,
            record_id=record_id,
            activity_date=day,
            user_id=user_id,
            source_user_email=email,
            resource_id=mapped(row, fields, "resource_id"),
            resource_name=mapped(row, fields, "resource_name"),
            site=mapped(row, fields, "site"),
            site_id=site_id,
            in_house_loan_indicator=indicator if not renewal else "",
            status=mapped(row, fields, "status"),
            quantity=quantity(mapped(row, fields, "quantity", required=True)) if renewal else 1,
            source_updated_at=mapped(row, fields, "source_updated_at"),
            source_available_at=mapped(row, fields, "source_available_at"),
        )
