"""Prepare a private SSMS identity-check batch from the saved pilot history."""

import argparse
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def gather_requests(database):
    grouped = {}
    counts = Counter(total_records=0, eligible_records=0, in_house_records=0, missing_email_records=0)
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        for dataset, day, payload in db.execute(
            'SELECT dataset,activity_date,payload FROM records ORDER BY dataset,record_id'
        ):
            record = json.loads(payload)
            counts['total_records'] += 1
            if dataset == 'prestamos' and record.get('in_house_loan_indicator') == 'Y':
                counts['in_house_records'] += 1
                continue
            email = str(record.get('source_user_email') or '').strip().lower()
            if not email:
                counts['missing_email_records'] += 1
                continue
            if len(email) > 255:
                raise ValueError('Un correo supera el tamaño permitido para la prueba.')
            date.fromisoformat(day)
            counts['eligible_records'] += 1
            item = grouped.setdefault((email, day), {'record_count': 0, 'datasets': set()})
            item['record_count'] += 1
            item['datasets'].add(dataset)
    requests = [
        {'request_id': index, 'source_email': email, 'activity_date': day,
         'record_count': values['record_count'], 'source_datasets': ','.join(sorted(values['datasets']))}
        for index, ((email, day), values) in enumerate(sorted(grouped.items()), start=1)
    ]
    counts['requests'] = len(requests)
    counts['distinct_emails'] = len({r['source_email'] for r in requests})
    return requests, dict(counts)


def sql_text(value):
    return "N'" + value.replace("'", "''") + "'"


def render_sql(requests, template, identity_query):
    start = ';WITH hits AS (\n'
    end = '\n)\nSELECT DISTINCT q.account_context'
    if identity_query.count(start) != 1 or end not in identity_query:
        raise ValueError('La consulta 07 cambió de estructura; revisa la preparación del lote.')
    matches = identity_query.split(start, 1)[1].split(end, 1)[0]
    matches = matches.replace('q.account_context', 'q.request_id')
    inserts = []
    for offset in range(0, len(requests), 500):
        values = [
            f"({r['request_id']},{sql_text(r['source_email'])},{sql_text(r['activity_date'])},"
            f"{r['record_count']},{sql_text(r['source_datasets'])})"
            for r in requests[offset:offset + 500]
        ]
        inserts.append(
            'INSERT INTO @cuentas(request_id,source_email,activity_date,record_count,source_datasets)\n'
            'VALUES\n' + ',\n'.join(values) + ';'
        )
    begin_marker = '-- BEGIN_SHARED_MATCHES'
    end_marker = '-- END_SHARED_MATCHES'
    insert_marker = '-- INSERT_REQUESTS_HERE'
    if any(template.count(marker) != 1 for marker in [begin_marker, end_marker, insert_marker]):
        raise ValueError('La plantilla del lote tiene marcadores inesperados.')
    prefix, remainder = template.split(begin_marker, 1)
    _, suffix = remainder.split(end_marker, 1)
    template = prefix + matches + suffix
    return template.replace(insert_marker, '\n'.join(inserts))


def main():
    parser = argparse.ArgumentParser(description='Preparar el lote institucional para ejecutar en SSMS.')
    parser.add_argument('--database', type=Path, default=ROOT / 'data/pilot.sqlite3')
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'data/referencias/usuarios/lote/08_validar_lote_preparado.sql')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / 'data').resolve()):
        parser.error('El archivo preparado debe guardarse dentro de data/, fuera de Git.')
    requests, counts = gather_requests(args.database)
    if not requests:
        parser.error('No hay registros con correo para preparar esta prueba.')
    sql = render_sql(requests, (ROOT / 'sql/institutional/08_validar_lote.sql').read_text(),
                     (ROOT / 'sql/institutional/07_validar_cuentas.sql').read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(sql, encoding='utf-8-sig')
    print(json.dumps({**counts, 'prepared_sql': str(output)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
