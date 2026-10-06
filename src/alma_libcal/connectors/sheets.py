import json
import os
import tempfile
from pathlib import Path

from ..config import required
from ..errors import ConfigError, PublicationError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def atomic_write(path: Path, value: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def credentials(config, *, interactive=False, port=8765, open_browser=False):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise ConfigError('Instala las dependencias de Google: python -m pip install -e ".[google]".') from None
    settings = config.raw.get("google", {})
    token_path = config.path(required(settings, "token_file", "google"))
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES) if token_path.exists() and not interactive else None
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            if not interactive:
                raise ConfigError("Autoriza Google primero con python -m alma_libcal auth-google.")
            client_path = config.path(required(settings, "client_file", "google"))
            flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
            creds = flow.run_local_server(host="localhost", bind_addr="127.0.0.1", port=port,
                                          open_browser=open_browser, timeout_seconds=300)
        atomic_write(token_path, creds.to_json())
        return creds
    except ConfigError:
        raise
    except Exception:
        raise PublicationError("No se pudo autorizar Google; revisa el cliente OAuth y ejecuta auth-google para renovar el acceso.") from None


class SheetsPublisher:
    """Replace managed tabs in a single atomic batch, never clear before writing."""

    def __init__(self, config, session=None):
        self.config = config
        self.session = session

    def request(self, method, url, **kwargs):
        try:
            response = self.session.request(method, url, timeout=60, **kwargs)
            if response.status_code != 200:
                raise PublicationError(f"Google Sheets respondió HTTP {response.status_code}; los datos locales siguen pendientes.")
            return response.json()
        except PublicationError:
            raise
        except Exception:
            raise PublicationError("No se confirmó la publicación en Google Sheets; reintenta desde SQLite.") from None

    def publish(self, tables):
        settings = self.config.raw.get("google", {})
        spreadsheet = required(settings, "spreadsheet_id", "google")
        if not all(char.isalnum() or char in "-_" for char in spreadsheet):
            raise ConfigError("google.spreadsheet_id debe ser un identificador, no una URL.")
        if self.session is None:
            creds = credentials(self.config)
            from google.auth.transport.requests import AuthorizedSession
            self.session = AuthorizedSession(creds)
        base = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet}"
        metadata = self.request("GET", base, params={"fields": "sheets(properties)"})
        try:
            sheets = {sheet["properties"]["title"]: sheet["properties"] for sheet in metadata["sheets"]}
        except (KeyError, TypeError):
            raise PublicationError("Google Sheets devolvió metadatos inesperados.") from None
        used_ids = {properties["sheetId"] for properties in sheets.values()}
        requests = []
        for name, rows in tables.items():
            if name not in ("prestamos", "renovaciones", "reservas", "control"):
                raise PublicationError("Se intentó publicar una pestaña fuera del piloto.")
            width = max((len(row) for row in rows), default=1)
            height = max(len(rows), 2)
            if name in sheets:
                properties = sheets[name]
                sheet_id = properties["sheetId"]
                if properties.get("sheetType", "GRID") != "GRID":
                    raise PublicationError("Una pestaña administrada no es una cuadrícula editable.")
                grid = properties.get("gridProperties", {})
                requests.append({"updateSheetProperties": {"properties": {
                    "sheetId": sheet_id, "gridProperties": {
                        "rowCount": max(height, grid.get("rowCount", 1)),
                        "columnCount": max(width, grid.get("columnCount", 1)), "frozenRowCount": 1,
                    }}, "fields": "gridProperties(rowCount,columnCount,frozenRowCount)"}})
            else:
                sheet_id = 1
                while sheet_id in used_ids:
                    sheet_id += 1
                used_ids.add(sheet_id)
                requests.append({"addSheet": {"properties": {"sheetId": sheet_id, "title": name,
                    "gridProperties": {"rowCount": height, "columnCount": width, "frozenRowCount": 1}}}})
            # Clearing and setting cells are applied atomically in this same batch.
            requests.append({"updateCells": {"range": {"sheetId": sheet_id}, "fields": "userEnteredValue"}})
            cells = [{"values": [{"userEnteredValue": self.cell(value)} for value in row]} for row in rows]
            requests.append({"updateCells": {"start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
                                               "rows": cells, "fields": "userEnteredValue"}})
        body = {"requests": requests}
        if len(json.dumps(body, ensure_ascii=False).encode()) > 1_800_000:
            raise PublicationError("La publicación supera el tamaño del piloto (1,8 MB); el histórico queda local. Divide o amplía el publicador antes de cargar todo el año.")
        self.request("POST", base + ":batchUpdate", json=body)

    @staticmethod
    def cell(value):
        if type(value) in (int, float):
            return {"numberValue": value}
        # String values preserve leading zeros and do not execute as formulas.
        return {"stringValue": str(value)}


class FilePublisher:
    """Offline demo publication; its output is deliberately isolated from Google."""

    def __init__(self, directory):
        self.directory = directory

    def publish(self, tables):
        self.directory.mkdir(parents=True, exist_ok=True)
        atomic_write(self.directory / "sheets.json", json.dumps(tables, ensure_ascii=False, indent=2))
