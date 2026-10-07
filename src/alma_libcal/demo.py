import json
from datetime import date
from importlib.resources import files

from .config import Config
from .connectors.alma import AlmaConnector
from .connectors.libcal import LibCalConnector
from .connectors.sheets import FilePublisher
from .models import Interval
from .service import extract, publish
from .storage import Store, exclusive_lock


def fixture(name):
    return files("alma_libcal").joinpath("fixtures", name).read_text(encoding="utf-8")


class DemoHTTP:
    """Fictional API responses; never opens a network connection."""

    def request(self, method, url, *, params=None, **kwargs):
        if method != "GET" or "/analytics/reports" not in url:
            raise AssertionError("Unexpected demo request")
        if params.get("token"):
            return fixture("alma_loans_page2.xml").encode()
        name = "alma_renewals.xml" if params["path"].endswith("Renewals") else "alma_loans_page1.xml"
        return fixture(name).encode()

    def json(self, method, url, *, params=None, **kwargs):
        if method == "POST":
            return {"access_token": "fictional-offline-token"}
        if int(params["offset"]) > 0:
            return []
        return [row for row in json.loads(fixture("libcal_bookings.json")) if row["cid"] == params["cid"]]


def demo_config(directory):
    raw = {
        "alma": {"base_url": "https://alma.invalid", "api_key_env": "DEMO_ALMA_KEY", "page_size": 25},
        "libcal": {
            "base_url": "https://libcal.invalid", "bookings_path": "/1.1/space/bookings", "token_path": "/1.1/oauth/token",
            "client_id_env": "DEMO_LIBCAL_ID", "client_secret_env": "DEMO_LIBCAL_SECRET", "pagination": "offset",
            "query": {"date": "{date}", "days": "{days}", "cid": "{category_id}", "limit": "{limit}", "offset": "{offset}"},
            "categories": [{"id": "101", "name": "Computadoras y laptops"}, {"id": "102", "name": "Espacios grupales"}, {"id": "103", "name": "Kindle"}],
            "fields": {"booking_id": "bookId", "user_id": "institutionalId", "resource_id": "eid", "resource_name": "itemName",
                       "starts_at": "fromDate", "ends_at": "toDate", "status": "status", "site": "locationName",
                       "check_in": "checkIn", "check_out": "checkOut"},
        },
    }
    fields = {"loan_id": "Column1", "activity_date": "Column2", "user_id": "Column3", "resource_id": "Column4",
              "resource_name": "Column5", "site": "Column6", "status": "Column7",
              "source_updated_at": "Column8", "source_available_at": "Column9"}
    raw["alma"]["prestamos"] = {"report_path": "/shared/Pilot/Loans", "date_column": '"Loan Date"."Loan Date"', "fields": fields}
    raw["alma"]["renovaciones"] = {"report_path": "/shared/Pilot/Renewals", "date_column": '"Renewal Date"."Renewal Date"', "fields": {**fields, "quantity": "Column10"}}
    return Config(raw, directory.resolve(), "America/Lima", date(2026, 10, 6), directory / "pilot.sqlite3")


def run_demo(directory):
    import os
    from unittest.mock import patch

    config = demo_config(directory)
    http = DemoHTTP()
    interval = Interval(date(2026, 10, 6), date(2026, 10, 6))
    connectors = {"prestamos": AlmaConnector(config, http, "prestamos"),
                  "renovaciones": AlmaConnector(config, http, "renovaciones"), "reservas": LibCalConnector(config, http)}
    with exclusive_lock(config.database), patch.dict(os.environ, {"DEMO_ALMA_KEY": "fictional", "DEMO_LIBCAL_ID": "fictional", "DEMO_LIBCAL_SECRET": "fictional"}), patch("alma_libcal.connectors.libcal.current_date", return_value=interval.start):
        store = Store(config.database)
        try:
            successful, failures = extract(store, connectors, interval)
            complete = publish(store, FilePublisher(directory), successful, interval)
            print(f"Demostración ficticia: {directory / 'sheets.json'} (no se publicó en Google).")
            return 0 if complete and not failures else 1
        finally:
            store.close()
