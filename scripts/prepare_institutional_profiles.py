"""Prepare scoped institutional profile evidence for the reviewed identity batch."""

import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path

if __package__:
    from .prepare_institutional_check import ROOT, gather_requests, sql_text
else:
    from prepare_institutional_check import ROOT, gather_requests, sql_text

from alma_libcal.config import load_config


# Reuse the tested read-only discovery queries and keep their original source fields.
PROBES = (
    ('02_roles_persona.sql', '02_estudiante_uc_CASO.csv', 'uc_student', 'university'),
    ('02_roles_persona.sql', '02_estudiante_psg_CASO.csv', 'psg_student', 'university'),
    ('03_matriculas_persona.sql', '03_matriculas_uc_CASO.csv', 'uc_enrollment', 'university'),
    ('03_matriculas_persona.sql', '03_matriculas_psg_CASO.csv', 'psg_enrollment', 'university'),
    ('03_matriculas_persona.sql', '03_matriculas_edc_CASO.csv', 'edc_enrollment', 'university'),
    ('06_completar_perfiles.sql', '06_perfil_continua_CASO.csv', 'edc_profile', 'university'),
    ('06_completar_perfiles.sql', '06_programa_posgrado_CASO.csv', 'psg_program', 'university'),
    ('03_matriculas_persona.sql', '03_matriculas_ic_CASO.csv', 'ic_enrollment', 'institute'),
    ('07_validar_cuentas.sql', '07_egreso_instituto_CASO.csv', 'ic_graduation', 'institute'),
    ('02_roles_persona.sql', '02_empleo_CASO.csv', 'employment', 'labor'),
    ('02_roles_persona.sql', '02_docente_CASO.csv', 'teacher', 'labor'),
    ('02_roles_persona.sql', '02_trabajador_ic_CASO.csv', 'ic_employment', 'labor'),
    ('02_roles_persona.sql', '02_programacion_docente_CASO.csv', 'teaching_program', 'labor'),
    ('02_roles_persona.sql', '02_pertenencia_docente_CASO.csv', 'teaching_affiliation', 'labor'),
    ('06_completar_perfiles.sql', '06_vigencia_docente_CASO.csv', 'teaching_weeks', 'labor'),
    ('05_fechas_y_periodos.sql', '05_horarios_docentes_CASO.csv', 'teaching_schedule', 'labor'),
)


def read_review(path, expected_requests, excluded_emails=()):
    text = Path(path).read_text(encoding='utf-8-sig')
    delimiter = csv.Sniffer().sniff(text[:8192], delimiters=',;\t').delimiter
    rows = list(csv.DictReader(text.splitlines(), delimiter=delimiter))
    required = {'request_id', 'source_email', 'activity_date', 'record_count', 'source_datasets',
                'person_id', 'identity_status', 'account_scope', 'review_status'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('El lote revisado está vacío o no tiene los encabezados esperados.')
    expected = {str(r['request_id']): r for r in expected_requests}
    if len(rows) != len(expected) or len({r['request_id'] for r in rows}) != len(rows):
        raise ValueError('El lote revisado no coincide con las solicitudes del histórico actual.')
    ready = []
    for row in rows:
        original = expected.get(row['request_id'])
        if original is None or any(str(original[key]) != row[key] for key in
                                   ['source_email', 'activity_date', 'record_count', 'source_datasets']):
            raise ValueError('El histórico cambió o el lote revisado contiene solicitudes diferentes.')
        if row['review_status'] != 'ready_for_profile' or row['source_email'] in excluded_emails:
            continue
        if (row['identity_status'] != 'matched_identity' or row['account_scope'] not in
                {'university', 'institute', 'labor'} or not re.fullmatch(r'[0-9]{1,18}', row['person_id'])
                or int(row['person_id']) <= 0):
            raise ValueError('Una solicitud marcada como lista no tiene identidad y ámbito válidos.')
        date.fromisoformat(row['activity_date'])
        ready.append({**original, 'person_id': row['person_id'], 'account_scope': row['account_scope']})
    return ready


def evidence_query(text, label, source, scope):
    marker = '-- ' + label
    if text.count(marker) != 1:
        raise ValueError('No se encuentra una fuente de evidencia en las consultas institucionales.')
    section = text.split(marker, 1)[1]
    match = re.search(r'^SELECT\s+(.*?)\nFROM\s+(.*?);', section, flags=re.M | re.S)
    if not match:
        raise ValueError('La consulta de evidencia cambió de estructura.')
    fields, body = match.groups()
    # Sample-only TOP clauses must not truncate the real profile batch.
    fields = re.sub(r'^DISTINCT\s+', '', fields)
    fields = re.sub(r'^TOP\s*\(\d+\)\s+', '', fields)
    body = re.sub(r'\bORDER\s+BY\s+.*$', '', body, flags=re.S | re.I)
    parts = re.split(r'\bWHERE\b', body, maxsplit=1, flags=re.I)
    if len(parts) != 2:
        raise ValueError('La fuente de evidencia no tiene el filtro de persona esperado.')
    tables, predicate = parts
    if re.search(r'\b(?:SELECT|APPLY)\b', tables, flags=re.I):
        raise ValueError('Revisa el filtro de ámbito antes de usar una fuente con subconsultas en FROM.')
    query = (f"SELECT DISTINCT {sql_text(source)} AS profile_source,\n"
             f"       (SELECT {fields}\n FOR JSON PATH, INCLUDE_NULL_VALUES, WITHOUT_ARRAY_WRAPPER) AS profile_data\n"
             f"FROM {tables.rstrip()}\nWHERE q.account_scope={sql_text(scope)} AND ({predicate.strip()})")
    # DIM_DOCENTE stores person IDs as text; do not convert unrelated IDs to numbers.
    query = query.replace('d.ID_PERSONA=@persona_id',
                          'LTRIM(RTRIM(d.ID_PERSONA))=CONVERT(nvarchar(80),q.person_id)')
    query = query.replace('@documento_referencia', 'identity_person.COD_DOCUMENTO')
    query = query.replace('@documento', 'identity_person.COD_DOCUMENTO')
    query = query.replace('@persona_id', 'q.person_id').replace('@fecha_operacion', 'q.activity_date')
    if source == 'ic_graduation':
        query += '\n AND p.ID_PERSONA=q.person_id'
    return query


def render_profiles(requests, template, query_directory):
    inserts = []
    for offset in range(0, len(requests), 500):
        values = [f"({r['request_id']},{sql_text(r['source_email'])},{sql_text(r['activity_date'])},"
                  f"{r['record_count']},{sql_text(r['source_datasets'])},{r['person_id']},{sql_text(r['account_scope'])})"
                  for r in requests[offset:offset + 500]]
        inserts.append('INSERT INTO @perfiles(request_id,source_email,activity_date,record_count,source_datasets,person_id,account_scope)\n'
                       'VALUES\n' + ',\n'.join(values) + ';')
    probes = [evidence_query((query_directory / filename).read_text(), label, source, scope)
              for filename, label, source, scope in PROBES]
    replacements = {'-- INSERT_PROFILE_REQUESTS_HERE': '\n'.join(inserts),
                    '-- PROFILE_EVIDENCE_HERE': '\nUNION ALL\n' + '\nUNION ALL\n'.join(probes)}
    for marker, content in replacements.items():
        if template.count(marker) != 1:
            raise ValueError('La plantilla de perfiles tiene marcadores inesperados.')
        template = template.replace(marker, content)
    return template


def main():
    parser = argparse.ArgumentParser(description='Preparar la segunda etapa de perfiles en SSMS.')
    parser.add_argument('--database', type=Path, default=ROOT / 'data/pilot.sqlite3')
    parser.add_argument('--review', type=Path, default=ROOT / 'data/referencias/usuarios/lote/08_validacion_lote_revisada.csv')
    parser.add_argument('--config', type=Path, default=ROOT / 'config.toml')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/referencias/usuarios/lote/09_extraer_perfiles_preparado.sql')
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to((ROOT / 'data').resolve()):
        parser.error('El SQL preparado contiene datos privados y debe guardarse dentro de data/.')
    expected, counts = gather_requests(args.database)
    services = load_config(args.config).raw.get('reporting', {}).get('service_accounts', {})
    requests = read_review(args.review, expected, services)
    if not requests:
        parser.error('No hay solicitudes con persona y ámbito listos para esta etapa.')
    sql = render_profiles(requests, (ROOT / 'sql/institutional/09_extraer_perfiles.sql').read_text(),
                          ROOT / 'sql/institutional')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sql, encoding='utf-8-sig')
    print(json.dumps({'profile_requests': len(requests),
                      'represented_records': sum(r['record_count'] for r in requests),
                      'excluded_requests': counts['requests'] - len(requests),
                      'prepared_sql': str(args.output)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
