import json
import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .errors import PilotError
from .models import Record, report_headers


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def exclusive_lock(database: Path):
    """WSL/Linux process lock held across extraction, snapshot and publication."""
    import fcntl

    database.parent.mkdir(parents=True, exist_ok=True)
    handle = database.with_suffix(database.suffix + ".lock").open("a")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise PilotError("Otra ejecución está usando este histórico; espera a que termine.") from None
        yield
    finally:
        handle.close()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS records (
                dataset TEXT NOT NULL, record_id TEXT NOT NULL,
                activity_date TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY (dataset, record_id)
            );
            CREATE INDEX IF NOT EXISTS records_date ON records(dataset, activity_date);
            CREATE TABLE IF NOT EXISTS snapshots (
                dataset TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                published_revision INTEGER NOT NULL DEFAULT 0,
                extracted_at TEXT NOT NULL, published_at TEXT NOT NULL DEFAULT '',
                source_updated_at TEXT NOT NULL, source_available_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset TEXT NOT NULL, operation TEXT NOT NULL, status TEXT NOT NULL,
                started_at TEXT NOT NULL, finished_at TEXT NOT NULL DEFAULT '',
                date_from TEXT NOT NULL, date_to TEXT NOT NULL, row_count INTEGER NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS record_versions (
                dataset TEXT NOT NULL, record_id TEXT NOT NULL, version INTEGER NOT NULL,
                payload_hash TEXT NOT NULL, payload TEXT NOT NULL, observed_at TEXT NOT NULL,
                observation_type TEXT NOT NULL,
                PRIMARY KEY(dataset,record_id,version)
            );
        """)
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(records)')}
        for name, definition in {'record_version': 'INTEGER NOT NULL DEFAULT 0',
                                 'record_changed_at': "TEXT NOT NULL DEFAULT ''",
                                 'first_observed_at': "TEXT NOT NULL DEFAULT ''",
                                 'last_observed_at': "TEXT NOT NULL DEFAULT ''"}.items():
            if name not in columns:
                self.db.execute(f'ALTER TABLE records ADD COLUMN {name} {definition}')
        with self.db:
            self.db.execute("UPDATE runs SET status='interrupted',finished_at=?,error='Ejecución anterior interrumpida.' WHERE status='running'", (now(),))

    def close(self):
        self.db.close()

    def start_run(self, dataset, operation, interval):
        with self.db:
            cursor = self.db.execute(
                "INSERT INTO runs(dataset,operation,status,started_at,date_from,date_to) VALUES (?,?,?,?,?,?)",
                (dataset, operation, "running", now(), interval.start.isoformat(), interval.end.isoformat()),
            )
        return cursor.lastrowid

    def finish_run(self, run_id, status, count=0, error=""):
        with self.db:
            self.db.execute("UPDATE runs SET status=?,finished_at=?,row_count=?,error=? WHERE id=?",
                            (status, now(), count, error, run_id))

    def save(self, dataset, interval, batch, run_id):
        batch.validate(dataset, interval)
        observed_at = now()
        with self.db:
            for record in batch.records:
                payload = json.dumps(asdict(record), ensure_ascii=False, sort_keys=True)
                previous = self.db.execute('SELECT * FROM records WHERE dataset=? AND record_id=?',
                                           (dataset,record.record_id)).fetchone()
                version = previous['record_version'] if previous else 0
                changed_at = previous['record_changed_at'] if previous else ''
                old_payload = None
                if previous:
                    old_payload = json.dumps(asdict(Record(**json.loads(previous['payload']))),
                                             ensure_ascii=False, sort_keys=True)
                    if not version:
                        version = 1
                        changed_at = observed_at
                        self.save_version(dataset,record.record_id,version,old_payload,observed_at,'baseline')
                if payload != old_payload:
                    version += 1
                    changed_at = observed_at
                    self.save_version(dataset,record.record_id,version,payload,observed_at,'update' if previous else 'new')
                first_observed_at = (previous['first_observed_at'] if previous else '') or observed_at
                self.db.execute("""
                    INSERT INTO records(dataset,record_id,activity_date,payload,record_version,
                                        record_changed_at,first_observed_at,last_observed_at) VALUES(?,?,?,?,?,?,?,?)
                    ON CONFLICT(dataset,record_id) DO UPDATE SET
                        activity_date=excluded.activity_date,payload=excluded.payload,
                        record_version=excluded.record_version,record_changed_at=excluded.record_changed_at,
                        first_observed_at=excluded.first_observed_at,last_observed_at=excluded.last_observed_at
                """, (dataset, record.record_id, record.activity_date,
                      payload, version, changed_at, first_observed_at, observed_at))
            self.db.execute("""
                INSERT INTO snapshots(dataset,revision,extracted_at,source_updated_at,source_available_at)
                VALUES(?,1,?,?,?) ON CONFLICT(dataset) DO UPDATE SET
                    revision=revision+1,extracted_at=excluded.extracted_at,
                    source_updated_at=excluded.source_updated_at,
                    source_available_at=excluded.source_available_at
            """, (dataset, now(), batch.source_updated_at, batch.source_available_at))
            self.db.execute("UPDATE runs SET status='extracted',finished_at=?,row_count=? WHERE id=?",
                            (now(), len(batch.records), run_id))

    def save_version(self, dataset, record_id, version, payload, observed_at, observation_type):
        self.db.execute('INSERT INTO record_versions VALUES(?,?,?,?,?,?,?)',
                        (dataset,record_id,version,hashlib.sha256(payload.encode()).hexdigest(),
                         payload,observed_at,observation_type))

    def available(self):
        return [row[0] for row in self.db.execute("SELECT dataset FROM snapshots ORDER BY dataset")]

    def records(self, dataset):
        return [Record(**json.loads(row[0])) for row in self.db.execute(
            "SELECT payload FROM records WHERE dataset=? ORDER BY activity_date,record_id", (dataset,))]

    def table(self, dataset, reporting=None):
        table = [report_headers(dataset, reporting)]
        for row in self.db.execute('SELECT payload,record_version,record_changed_at FROM records WHERE dataset=? ORDER BY activity_date,record_id', (dataset,)):
            record = Record(**json.loads(row['payload']))
            table.append(record.report_values(reporting, {'record_version':row['record_version'],
                                                          'record_changed_at':row['record_changed_at']}))
        return table

    def count(self, dataset):
        return self.db.execute("SELECT COUNT(*) FROM records WHERE dataset=?", (dataset,)).fetchone()[0]

    def revisions(self, datasets):
        return {dataset: self.db.execute("SELECT revision FROM snapshots WHERE dataset=?", (dataset,)).fetchone()[0]
                for dataset in datasets}

    def mark_published(self, revisions, run_ids):
        with self.db:
            for dataset, revision in revisions.items():
                self.db.execute("UPDATE snapshots SET published_revision=?,published_at=? WHERE dataset=? AND revision=?",
                                (revision, now(), dataset, revision))
                self.db.execute("UPDATE runs SET status='published',finished_at=?,row_count=? WHERE id=?",
                                (now(), self.count(dataset), run_ids[dataset]))

    def control(self, proposed=None):
        proposed = proposed or {}
        header = ["dataset", "revision", "published_revision", "pending", "total_rows", "extracted_at",
                  "published_at", "source_updated_at", "source_available_at", "last_operation",
                  "last_status", "last_from", "last_to", "last_error", "last_extraction_status", "last_extraction_error"]
        rows = [header]
        for dataset in ("prestamos", "renovaciones", "reservas"):
            snapshot = self.db.execute("SELECT * FROM snapshots WHERE dataset=?", (dataset,)).fetchone()
            run = self.db.execute("SELECT * FROM runs WHERE dataset=? ORDER BY id DESC LIMIT 1", (dataset,)).fetchone()
            extraction = self.db.execute("SELECT * FROM runs WHERE dataset=? AND operation='extract' ORDER BY id DESC LIMIT 1", (dataset,)).fetchone()
            revision = snapshot["revision"] if snapshot else 0
            published = proposed.get(dataset, snapshot["published_revision"] if snapshot else 0)
            rows.append([
                dataset, revision, published, "sí" if revision != published else "no", self.count(dataset),
                snapshot["extracted_at"] if snapshot else "",
                now() if dataset in proposed else (snapshot["published_at"] if snapshot else ""),
                snapshot["source_updated_at"] if snapshot else "", snapshot["source_available_at"] if snapshot else "",
                run["operation"] if run else "", "published" if dataset in proposed else (run["status"] if run else "not_run"),
                run["date_from"] if run else "", run["date_to"] if run else "", run["error"] if run else "",
                extraction["status"] if extraction else "not_run", extraction["error"] if extraction else "",
            ])
        return rows
