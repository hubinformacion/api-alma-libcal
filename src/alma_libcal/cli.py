import argparse
import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import load_config
from .connectors.alma import AlmaConnector
from .connectors.libcal import LibCalConnector
from .connectors.sheets import SheetsPublisher, credentials
from .errors import PilotError
from .http import HTTPClient
from .models import DATASETS, Interval
from .service import extract, publish
from .storage import Store, exclusive_lock


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Usa una fecha YYYY-MM-DD válida.") from None


def parser():
    root = argparse.ArgumentParser(description="Extracción manual de Alma y LibCal a SQLite y Google Sheets.")
    root.add_argument("--config", type=Path, default=Path("config.toml"), help="Configuración TOML (antes del subcomando).")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("sync", "publish"):
        command = commands.add_parser(name, help="Extraer y publicar." if name == "sync" else "Republicar el histórico sin consultar los sistemas.")
        command.add_argument("--only", choices=DATASETS, nargs="+", help="Conjuntos a procesar.")
        if name == "sync":
            command.add_argument("--from", dest="date_from", type=parse_date)
            command.add_argument("--to", dest="date_to", type=parse_date)
            command.add_argument("--extract-only", action="store_true", help="Guardar en SQLite sin publicar en Google.")
    commands.add_parser("status", help="Ver estado y pendientes locales, sin consultar APIs.")
    commands.add_parser("discover-libcal", help="Consultar ubicaciones y categorías sin recuperar usuarios.")
    inspect = commands.add_parser("inspect-alma", help="Mostrar columnas del reporte sin imprimir registros.")
    inspect.add_argument("--dataset", choices=("prestamos", "renovaciones"), required=True)
    inspect.add_argument("--from", dest="date_from", type=parse_date)
    inspect.add_argument("--to", dest="date_to", type=parse_date)
    auth = commands.add_parser("auth-google", help="Autorizar Google mediante navegador y callback local.")
    auth.add_argument("--port", type=int, default=8765)
    auth.add_argument("--open-browser", action="store_true")
    demo = commands.add_parser("demo", help="Probar el flujo con datos ficticios, sin red ni credenciales.")
    demo.add_argument("--directory", type=Path, default=Path("demo-output"))
    return root


def main(argv=None):
    os.umask(0o077)
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "demo":
            from .demo import run_demo
            return run_demo(arguments.directory)
        config = load_config(arguments.config)
        if arguments.command == "auth-google":
            if not 1 <= arguments.port <= 65535:
                raise PilotError("El puerto debe estar entre 1 y 65535.")
            credentials(config, interactive=True, port=arguments.port, open_browser=arguments.open_browser)
            print("Autorización de Google guardada localmente.")
            return 0
        interval = Interval(
            getattr(arguments, "date_from", None) or config.start_date,
            getattr(arguments, "date_to", None) or datetime.now(ZoneInfo(config.timezone)).date(),
        )
        if arguments.command == "discover-libcal":
            metadata = LibCalConnector(config, HTTPClient()).discover()
            print(json.dumps(metadata, ensure_ascii=False, indent=2))
            return 0
        if arguments.command == "inspect-alma":
            columns = AlmaConnector(config, HTTPClient(), arguments.dataset).inspect(interval)
            print(json.dumps(columns, ensure_ascii=False, indent=2))
            return 0
        with exclusive_lock(config.database):
            store = Store(config.database)
            try:
                if arguments.command == "status":
                    table = store.control()
                    print(json.dumps([dict(zip(table[0], row)) for row in table[1:]], ensure_ascii=False, indent=2))
                    return 0
                selected = list(dict.fromkeys(arguments.only or DATASETS))
                if arguments.command == "publish":
                    available = store.available()
                    missing = [dataset for dataset in selected if dataset not in available]
                    if missing:
                        print("Sin extracción completa previa: " + ", ".join(missing) + ".")
                    selected = [dataset for dataset in selected if dataset in available]
                    success = publish(store, SheetsPublisher(config), selected, interval)
                    return 0 if success and not missing else 1
                http = HTTPClient()
                connectors = {dataset: (LibCalConnector(config, http) if dataset == "reservas"
                                       else AlmaConnector(config, http, dataset)) for dataset in selected}
                successful, failures = extract(store, connectors, interval)
                if arguments.extract_only:
                    return 1 if failures else 0
                published = publish(store, SheetsPublisher(config), successful, interval)
                return 0 if published and not failures else 1
            finally:
                store.close()
    except (PilotError, ValueError) as error:
        print(f"Error: {error}")
        return 1
    except (OSError, sqlite3.Error):
        print("Error de almacenamiento local; revisa la ruta, permisos y espacio disponible.")
        return 1
    except KeyboardInterrupt:
        print("Ejecución interrumpida. Revisa el estado local antes de reintentar.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
