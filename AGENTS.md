# Repository Guidelines

## Project Context

Python 3.12 pilot: Alma loans/renewals and LibCal bookings go into SQLite and separate Sheets tabs. Validation is manual; institutional enrichment uses reviewed SSMS CSV imports. Direct database access and scheduled jobs are pending.

The institutional database will supply verified user attributes effective on the operation date. Match exact registered email first; use authoritative identifiers as fallback. For valid labor roles, docente precedes administrativo; JEFE DE PRACTICA counts as docente. Payroll ES_DOCENTE and FECHA_TERMINO are not sufficient alone to decide role or employment termination. Keep source identifiers distinct from verified identity. Never invent historical academic profiles or discard unmatched operations.

Administrative profiles, including configured service accounts, report No aplica for user_program, user_department and user_modality; these are not missing attributes. Their campus and business unit still require evidence. Teaching profiles retain their teaching program/faculty/modality, never student attributes from another scope.

The account used determines profile scope: institute accounts use IC only; university academic accounts use UC/PSG/EDC; labor accounts use employment/teaching. Select the applicable recent profile within that scope, never across scopes because the person/document matches. Report user_type is Estudiante (enrolled and studying in the applicable current period), Egresado (includes Bachiller/Titulado), Docente or Administrativo. Missing evidence remains unresolved, not a guessed category.

The reporting.service_accounts email list classifies area accounts as Administrativo with user campus Virtual at export time. They are not natural persons: keep source fields, clear person/academic attributes and mark configured_service_account; never replace the operation/resource campus. Exchange TM identifiers must remain alphanumeric; match the complete local part against COD_DOCUMENTO, not just its digits. Unknown labor-looking emails remain pending until an authoritative source resolves them.

Prioritize current institutional accounts in the pilot; legacy student email aliases are a later exception and must not block development. Preserve original graduation statuses independently of user_type; commercial funnel statuses do not prove academic graduation.

Validate identity discovery with email-only inputs: a known document is a test reference, not proof that the email resolved. Test multiple accounts of one person without assuming one account per document. Missing institutional email/code links require an authoritative account mapping; never fabricate employee usernames or institute aliases.

Two institute pilot cases (historical and current enrollment) match i + ID_ALUMNO to the expected person. This is pilot evidence, not general coverage. Identity matching alone does not prove current enrollment or graduation; validate operation dates and academic evidence separately.

## Structure and Configuration

Code is in `src/alma_libcal/`; adapters are in `connectors/`. `models.py` defines report headers and transformations; `storage.py` manages current records, versions and execution status. Tests use synthetic fixtures. Read-only institutional discovery queries are in `sql/institutional/` for manual SSMS execution. `scripts/prepare_institutional_check.py` reads SQLite in read-only mode and fills the batch template using identity methods from query 07. Generated SQL with real emails belongs under ignored `data/` only; unique identity and account scope do not prove a valid dated profile.

`scripts/prepare_institutional_profiles.py` prepares query 09 from the reviewed batch, verifies correspondence to current SQLite requests and restricts each evidence source by account scope. It exports source evidence as JSON per row. `import-users` validates the reviewed batch against current SQLite requests and imports through `institutional.py`. Profiles overlay exports by normalized exact email and operation date; raw operations and their versions never change. Separate institutional tables retain evidence, review, settings and semantic profile versions; identical imports are idempotent. Partial profiles retain known attributes and label missing ones for manual review. Pending descriptive report attributes display Pendiente de revisión with pending_review status, without inventing verified IDs or blocking operations.

`README.md` is the sole usage guide. Local `.env` supplies Alma/LibCal secrets, `config.toml` supplies routes, maps and reporting catalogs, and `secrets/` contains Google OAuth JSON. Templates are committed; populated configuration is ignored. Private references under `data/referencias/` are not repository dependencies.

## Commands and Verification

Run from the repository root with `.venv/bin/python -m alma_libcal`. Use `sync --only prestamos renovaciones --from YYYY-MM-DD --to YYYY-MM-DD --extract-only` to save without publishing; `publish --only prestamos renovaciones reservas` publishes saved history; `status` reports local state.

Run offline tests after behavior changes:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

The confirmed university period code is 202620 only for 2026-10-06 through 08, configured by date; period_id is a warehouse surrogate, so compare period_name. Do not extend this calendar without evidence. UC needs current ACTIVO states, dated enrollment and positive credits. IC requires validated enrollment status and a covering section interval. Unvalidated PSG/EDC/IC graduation rules remain pending. Never split unstructured institutional full names heuristically. Labor campus names require confirmed catalogs. Confirmed labor divisions: UCCI = Universidad Continental, IESC = Instituto Continental.

Use four-space indentation and descriptive `snake_case`. Mock external systems; retain tests and fixtures during cleanup.

## Reporting Invariants

Loans use the source loan ID. Renewal keys identify loan/date/renewal-campus aggregates: sum `renewal_quantity`, never interpret row count as event count. Keep original campuses and fallback provenance. LibCal retains bookId plus additional source IDs; attendance is independent of cancellation. Unrecorded attendance is excluded from its numeric indicator.

Preserve raw material codes and question IDs. Catalogs live in TOML; derive date parts when exporting. Preserve changed payloads in `record_versions`; identical extractions must not create extra versions.

Sheets projects compact columns; full data remains in SQLite. Publication replaces selected tabs atomically and rejects oversized requests; it is not incremental. LibCal's listing endpoint ignores past dates; recent updates cover only 24 hours. Do not claim complete historical coverage from either.

## Documentation, Git and Security

Use Context7 for current external library/API/CLI documentation: resolve the library first, then query each concept. If unavailable, use official documentation or the supplied specification and state uncertainty.

Never commit or print credentials, tokens, populated configuration or personal exports. Inspect Git staging before committing. Use concise English `feat:`, `fix:` or `docs:` subjects; report checks and limits. Do not push or reset data unless authorized by the task. Avoid adding development journals or duplicating the README.
