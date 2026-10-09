# Repository Guidelines

## Project Context

Python 3.12 pilot: Alma loans/renewals and LibCal bookings go into SQLite and separate Sheets tabs. Validation is manual; scheduled jobs and institutional enrichment are pending.

The institutional database will supply verified user attributes effective on the operation date. Match exact registered email first; use authoritative identifiers as fallback. For valid labor roles, docente precedes administrativo; JEFE DE PRACTICA counts as docente. Payroll ES_DOCENTE and FECHA_TERMINO are not sufficient alone to decide role or employment termination. Keep source identifiers distinct from verified identity. Never invent historical academic profiles or discard unmatched operations.

Prioritize current institutional accounts in the pilot; legacy student email aliases are a later exception and must not block development. Academic graduation statuses and commercial funnel statuses are distinct. Preserve original labels until reporting equivalences are agreed.

Validate identity discovery with email-only inputs: a known document is a test reference, not proof that the email resolved. Test multiple accounts of one person without assuming one account per document. Missing institutional email/code links require an authoritative account mapping; never fabricate employee usernames or institute aliases.

## Structure and Configuration

Code is in `src/alma_libcal/`; adapters are in `connectors/`. `models.py` defines report headers and transformations; `storage.py` manages current records, versions and execution status. Tests use synthetic fixtures. Read-only institutional discovery queries are in `sql/institutional/` for manual SSMS execution.

`README.md` is the sole usage guide. Local `.env` supplies Alma/LibCal secrets, `config.toml` supplies routes, maps and reporting catalogs, and `secrets/` contains Google OAuth JSON. Templates are committed; populated configuration is ignored. Private references under `data/referencias/` are not repository dependencies.

## Commands and Verification

Run from the repository root with `.venv/bin/python -m alma_libcal`. Use `sync --only prestamos renovaciones --from YYYY-MM-DD --to YYYY-MM-DD --extract-only` to save without publishing; `publish --only prestamos renovaciones reservas` publishes saved history; `status` reports local state.

Run offline tests after behavior changes:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Use four-space indentation and descriptive `snake_case`. Mock external systems; retain tests and fixtures during cleanup.

## Reporting Invariants

Loans use the source loan ID. Renewal keys identify loan/date/renewal-campus aggregates: sum `renewal_quantity`, never interpret row count as event count. Keep original campuses and fallback provenance. LibCal retains bookId plus additional source IDs; attendance is independent of cancellation. Unrecorded attendance is excluded from its numeric indicator.

Preserve raw material codes and question IDs. Catalogs live in TOML; derive date parts when exporting. Preserve changed payloads in `record_versions`; identical extractions must not create extra versions.

Sheets projects compact columns; full data remains in SQLite. Publication replaces selected tabs atomically and rejects oversized requests; it is not incremental. LibCal's listing endpoint ignores past dates; recent updates cover only 24 hours. Do not claim complete historical coverage from either.

## Documentation, Git and Security

Use Context7 for current external library/API/CLI documentation: resolve the library first, then query each concept. If unavailable, use official documentation or the supplied specification and state uncertainty.

Never commit or print credentials, tokens, populated configuration or personal exports. Inspect Git staging before committing. Use concise English `feat:`, `fix:` or `docs:` subjects; report checks and limits. Do not push or reset data unless authorized by the task. Avoid adding development journals or duplicating the README.
