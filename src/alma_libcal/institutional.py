"""Import reviewed, scoped institutional evidence without changing source operations."""

import csv
import hashlib
import io
import json
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from .errors import PilotError
from .models import ADMIN_NOT_APPLICABLE_FIELDS

PENDING = 'Pendiente de revisión'
USER_FIELDS = ('verified_user_id', 'verified_user_email', 'user_full_name', 'user_name',
               'user_lastname', 'user_type', 'user_modality', 'user_campus', 'user_program',
               'user_department', 'user_business_unit', 'user_match_status')
SOURCES = {
    'university': {'identity', 'uc_student', 'uc_enrollment', 'psg_student', 'psg_enrollment',
                   'psg_program', 'edc_enrollment', 'edc_profile'},
    'institute': {'identity', 'ic_enrollment', 'ic_graduation'},
    'labor': {'identity', 'employment', 'teacher', 'ic_employment', 'teaching_program',
              'teaching_affiliation', 'teaching_weeks', 'teaching_schedule'},
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_csv(path, required):
    """Choose separator from headers: JSON evidence makes whole-file sniffing unsafe."""
    try:
        content = Path(path).read_text(encoding='utf-8-sig')
        for delimiter in (';', ',', '\t'):
            reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
            if required.issubset(reader.fieldnames or []):
                rows = list(reader)
                if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
                    break
                return rows, content
    except (OSError, UnicodeError, csv.Error):
        pass
    raise PilotError('CSV institucional inválido: conserva encabezados, columnas y codificación UTF-8.')


def text(value):
    return '' if value is None else str(value).strip()


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFD', text(value).upper())
                   if not unicodedata.combining(c))


def day(value):
    value = text(value)
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        try:
            return datetime.strptime(value[:10], '%d/%m/%Y').date()
        except ValueError:
            return None


def consensus(rows, field):
    values = {text(row.get(field)) for row in rows}
    return next(iter(values)) if len(values) == 1 else ''


def attributes(rows):
    return {target: consensus(rows, source) for target, source in (
        ('user_campus', 'campus_name'), ('user_modality', 'modality_name'),
        ('user_program', 'program_name'), ('user_department', 'faculty_name'))}


def active_interval(row, start, end, operation):
    beginning = day(row.get(start))
    ending = day(row.get(end))
    # An invalid populated end must never turn into an open-ended interval.
    return (beginning is not None and beginning <= operation
            and (ending is not None and operation <= ending or not text(row.get(end))))


def resolve_profile(context, evidence, settings):
    operation = date.fromisoformat(context['activity_date'])
    scope = context['account_scope']
    identities = evidence['identity']
    identifier = consensus(identities, 'source_identifier')
    full_name = consensus(identities, 'full_name')
    profile = {field: '' for field in USER_FIELDS}
    profile.update(verified_user_id=identifier, verified_user_email=context['source_email'],
                   user_full_name=full_name)
    reasons = []
    period = str(settings.get('university_period_by_date', {}).get(operation.isoformat(), ''))
    selected = []
    if scope == 'university':
        profile['user_business_unit'] = 'Universidad Continental'
        # Keep the latest effective state of each career within the confirmed period.
        candidates = defaultdict(list)
        for row in evidence['uc_enrollment']:
            effective = day(row.get('source_activity_date'))
            enrolled = day(row.get('enrollment_date'))
            if (period and text(row.get('period_name')) == period and effective and effective <= operation
                    and (not enrolled or enrolled <= operation)):
                candidates[(text(row.get('student_id')), text(row.get('program_id')))].append(row)
        for rows in candidates.values():
            latest = max(day(r['source_activity_date']) for r in rows)
            current = [r for r in rows if day(r['source_activity_date']) == latest]
            def enrolled(row):
                try:
                    credits = float(row.get('enrolled_credits') or 0)
                except (TypeError, ValueError):
                    return False
                return (normalized(row.get('source_status_name')) == 'ACTIVO'
                        and normalized(row.get('enrollment_status_name')) == 'ACTIVO'
                        and day(row.get('enrollment_date')) is not None and credits > 0)
            if all(enrolled(r) for r in current):
                selected.extend(current)
        if selected:
            profile.update(attributes(selected), user_type='Estudiante')
            # A newer study in the same account family may supersede this career.
            latest_uc = max(day(r['enrollment_date']) for r in selected)
            newer = [r for source in ('edc_enrollment', 'edc_profile', 'psg_enrollment')
                     for r in evidence[source]
                     if any(latest_uc < d <= operation for d in
                            [day(r.get('enrollment_date')), day(r.get('source_start_date'))] if d)]
            if newer:
                profile.update({k: '' for k in attributes([])}, user_type='')
                reasons.append('newer_academic_study_requires_validation')
        else:
            # Formal graduation evidence is independent of commercial funnel labels.
            graduates = [r for r in evidence['uc_student'] if any(
                d and d <= operation for d in [day(r.get(k)) for k in
                                               ('graduation_date', 'bachelor_date', 'title_date')])]
            if graduates and not candidates and not any(evidence[s] for s in
                    ('psg_enrollment', 'edc_enrollment', 'edc_profile')):
                latest = max(day(r.get('graduation_date')) or day(r.get('study_end')) or date.min
                             for r in graduates)
                profile.update(attributes([r for r in graduates if
                    (day(r.get('graduation_date')) or day(r.get('study_end')) or date.min) == latest]),
                    user_type='Egresado')
            else:
                reasons.append('academic_status_not_proven' if period else 'academic_period_not_confirmed')
    elif scope == 'institute':
        profile['user_business_unit'] = 'Instituto Continental'
        selected = [r for r in evidence['ic_enrollment'] if text(r.get('source_status_id')) == '4'
                    and active_interval(r, 'section_start', 'section_end', operation)]
        if selected:
            profile.update(attributes(selected), user_type='Estudiante')
        else:
            reasons.append('institute_status_not_proven')
    elif scope == 'labor':
        jobs = [r for r in evidence['employment']
                if text(r.get('work_email')).lower() == context['source_email']
                and active_interval(r, 'employment_start', 'employment_withdrawal', operation)
                and day(r.get('employment_withdrawal')) != operation]
        teachers = [r for r in evidence['teacher']
                    if text(r.get('work_email')).lower() == context['source_email']
                    and active_interval(r, 'teacher_start', 'teacher_end', operation)]
        teacher_ids = {text(r.get('teacher_id')) for r in teachers}
        def teaching_role(row):
            return normalized(row.get('source_teacher_type')) in (
                'DOCENTE', 'JEFE DE PRACTICA', 'JEFE DE PRACTICA HYFLEX')
        programs = [r for r in evidence['teaching_program'] if period and
                    text(r.get('period_name')) == period and text(r.get('teacher_id')) in teacher_ids
                    and teaching_role(r)]
        weeks = [r for r in evidence['teaching_weeks'] if teaching_role(r)
                 and active_interval(r, 'source_week_start_text', 'source_week_end_text', operation)]
        if teachers and (programs or weeks):
            selected = programs or weeks
            affiliations = [r for r in evidence['teaching_affiliation'] if
                            text(r.get('teacher_id')) in teacher_ids
                            and text(r.get('period_id')) in {text(p.get('period_id')) for p in selected}
                            and text(r.get('campus_id')) in {text(p.get('campus_id')) for p in selected}]
            profile.update(attributes(selected), user_type='Docente')
            programs_selected = {text(r.get('program_id')) for r in selected}
            affiliations = [r for r in affiliations if text(r.get('program_id')) in programs_selected]
            if programs_selected == {text(r.get('program_id')) for r in affiliations}:
                profile['user_department'] = consensus(affiliations, 'faculty_name')
                # Never select one teaching career just because affiliation has a name.
                if len(programs_selected) == 1 and not profile['user_program']:
                    profile['user_program'] = consensus(affiliations, 'program_name')
        elif jobs:
            if any(text(r.get('source_teacher_flag')) == '1' for r in jobs):
                reasons.append('teaching_status_requires_validation')
            else:
                profile['user_type'] = 'Administrativo'
        else:
            reasons.append('employment_not_proven_on_operation_date')
        division = consensus(jobs, 'source_division')
        profile['user_business_unit'] = settings.get('labor_business_units', {}).get(division, '')
        if jobs and not profile['user_campus']:
            keys = {text(r.get('source_division')) + ':' + text(r.get('source_branch')) for r in jobs}
            mapped = {settings.get('labor_campuses', {}).get(k, '') for k in keys}
            if len(mapped) == 1:
                profile['user_campus'] = mapped.pop()
    if profile['user_type'] == 'Administrativo':
        profile.update({field: 'No aplica' for field in ADMIN_NOT_APPLICABLE_FIELDS})
    if not identifier or not full_name:
        raise PilotError('La evidencia de identidad está incompleta o es ambigua; no se importó el lote.')
    if not profile['user_type']:
        profile['user_match_status'] = 'pending_review'
    else:
        missing = [f for f in ('user_campus', 'user_modality', 'user_program', 'user_department',
                               'user_business_unit') if not profile[f]]
        reasons.extend('missing_or_ambiguous_' + f for f in missing)
        profile['user_match_status'] = 'partial_profile' if missing else 'matched_profile'
    return {'fields': profile, 'reasons': sorted(set(reasons)), 'account_scope': scope,
            'person_id': context['person_id']}


def prepare_import(store, evidence_path, review_path, settings, services):
    """Validate the entire batch before allowing any SQLite mutation."""
    metadata = {'request_id', 'source_email', 'activity_date', 'record_count', 'source_datasets',
                'person_id', 'account_scope'}
    reviews, review_content = read_csv(review_path, metadata | {'identity_status', 'review_status'})
    evidence_rows, content = read_csv(evidence_path, metadata | {'profile_source', 'profile_data'})
    grouped = defaultdict(lambda: {'record_count': 0, 'datasets': set()})
    for dataset in store.available():
        for record in store.records(dataset):
            if dataset == 'prestamos' and record.in_house_loan_indicator == 'Y':
                continue
            email = record.source_user_email.strip().lower()
            if email:
                item = grouped[(email, record.activity_date)]
                item['record_count'] += 1
                item['datasets'].add(dataset)
    expected = {str(i): dict(source_email=email, activity_date=operation,
                            record_count=str(item['record_count']),
                            source_datasets=','.join(sorted(item['datasets'])))
                for i, ((email, operation), item) in enumerate(sorted(grouped.items()), 1)}
    if len(reviews) != len(expected) or len({r['request_id'] for r in reviews}) != len(reviews):
        raise PilotError('El lote revisado no corresponde al histórico actual.')
    ready = {}
    for row in reviews:
        original = expected.get(row['request_id'])
        if original is None or any(original[k] != row[k] for k in original):
            raise PilotError('El histórico cambió; prepara un nuevo lote institucional.')
        if row['review_status'] == 'ready_for_profile' and row['source_email'] not in services:
            if (row['identity_status'] != 'matched_identity' or row['account_scope'] not in SOURCES
                    or not row['person_id'].isdigit() or int(row['person_id']) <= 0):
                raise PilotError('Una cuenta lista no tiene identidad y ámbito válidos.')
            ready[row['request_id']] = row
    evidence = defaultdict(lambda: defaultdict(list))
    for row in evidence_rows:
        context = ready.get(row['request_id'])
        if not context or any(context[k] != row[k] for k in metadata):
            raise PilotError('La evidencia no corresponde a las cuentas revisadas.')
        source = row['profile_source']
        if source not in SOURCES[context['account_scope']]:
            raise PilotError('La evidencia mezcla ámbitos institucionales.')
        try:
            payload = json.loads(row['profile_data'])
        except (ValueError, TypeError):
            raise PilotError('Hay evidencia JSON inválida; exporta nuevamente sin editarla.') from None
        if (not isinstance(payload, dict) or any(isinstance(v, (dict, list)) for v in payload.values())
                or ('person_id' in payload and text(payload['person_id']) != context['person_id'])
                or ('requested_activity_date' in payload and
                    text(payload['requested_activity_date'])[:10] != context['activity_date'])):
            raise PilotError('La evidencia contiene una persona, fecha o estructura incompatible.')
        evidence[row['request_id']][source].append(payload)
    if set(evidence) != set(ready) or any(len(e['identity']) != 1 for e in evidence.values()):
        raise PilotError('El archivo de perfiles está incompleto o repite identidades.')
    profiles = []
    for key, context in ready.items():
        profiles.append((context['source_email'], context['activity_date'],
                         resolve_profile(context, evidence[key], settings)))
    for context in reviews:
        if context['request_id'] in ready:
            continue
        fields = {field: '' for field in USER_FIELDS}
        service = context['source_email'] in services
        fields['user_match_status'] = 'configured_service_account' if service else 'pending_review'
        profiles.append((context['source_email'], context['activity_date'], {
            'fields': fields, 'person_id': '', 'account_scope': context['account_scope'],
            'reasons': ['configured_service_account' if service else 'identity_or_scope_pending']}))
    return profiles, content, review_content


def import_users(store, evidence_path, review_path, settings=None, reporting=None, output=None):
    settings, reporting = settings or {}, reporting or {}
    profiles, content, review_content = prepare_import(store, evidence_path, review_path, settings,
                                       reporting.get('service_accounts', {}))
    changed = store.save_profiles(profiles, content, review_content,
                                  {**settings, 'service_accounts': reporting.get('service_accounts', {})})
    counts = Counter(p['fields']['user_match_status'] for _, _, p in profiles)
    if output is not None:
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        for dataset in store.available():
            with (output / (dataset + '.csv')).open('w', encoding='utf-8-sig', newline='') as handle:
                csv.writer(handle).writerows(store.table(dataset, reporting))
        with (output / 'usuarios_revision.csv').open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['source_email', 'activity_date', 'account_scope', 'status', 'reasons'])
            for email, operation, profile in profiles:
                writer.writerow([email, operation, profile['account_scope'],
                                 profile['fields']['user_match_status'], ';'.join(profile['reasons'])])
    return {'profiles': len(profiles), 'changed_profiles': changed, 'statuses': dict(counts),
            'report_directory': str(output) if output else ''}
