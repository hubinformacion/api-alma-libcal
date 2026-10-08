from .errors import PilotError
from .models import sheet_table


def extract(store, connectors, interval, report=print):
    successful = []
    failures = []
    for dataset, connector in connectors.items():
        run_id = store.start_run(dataset, "extract", interval)
        try:
            batch = connector.fetch(interval)
            store.save(dataset, interval, batch, run_id)
        except PilotError as error:
            store.finish_run(run_id, "extraction_failed", error=str(error))
            report(f"{dataset}: extracción fallida — {error}")
            failures.append(dataset)
            continue
        except Exception:
            store.finish_run(run_id, "extraction_failed", error="Error interno durante la extracción.")
            report(f"{dataset}: error interno; revisa configuración y ejecuta las pruebas.")
            failures.append(dataset)
            continue
        successful.append(dataset)
        missing = sum(not record.user_id and not (dataset == "prestamos" and record.in_house_loan_indicator == "Y") for record in batch.records)
        report(f"{dataset}: {len(batch.records)} filas extraídas; {store.count(dataset)} en histórico; {missing} sin código de usuario.")
    return successful, failures


def publish(store, publisher, datasets, interval, report=print, reporting=None):
    if not datasets:
        report("No hay conjuntos completos disponibles para publicar.")
        return False
    revisions = store.revisions(datasets)
    run_ids = {dataset: store.start_run(dataset, "publish", interval) for dataset in datasets}
    try:
        tables = {dataset: sheet_table(dataset, store.table(dataset, reporting), reporting) for dataset in datasets}
        tables["control"] = store.control(proposed=revisions)
        publisher.publish(tables)
    except PilotError as error:
        for run_id in run_ids.values():
            store.finish_run(run_id, "publication_failed", error=str(error))
        report(f"Publicación fallida: {error}")
        return False
    except Exception:
        for run_id in run_ids.values():
            store.finish_run(run_id, "publication_failed", error="Error interno durante la publicación.")
        report("Publicación no confirmada; el histórico local sigue disponible para reintentar.")
        return False
    store.mark_published(revisions, run_ids)
    report("Publicación confirmada: " + ", ".join(datasets) + ".")
    return True
