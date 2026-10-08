# Alma + LibCal → reportes de biblioteca

La extracción de la muestra está validada. El siguiente paso es publicar los datos guardados y comprobarlos en Google Sheets. Los reportes permanecen separados; la integración con usuarios de la universidad vendrá después.

Solo hay dos guías de trabajo:

- [00 — Estado y pendientes, incluida la renovación sin campus](docs/00-inicio.md).
- [01 — Publicar y validar Google Sheets](docs/01-google-sheets.md).

Los registros están en `data/pilot.sqlite3`; las copias CSV de la muestra, en `data/verificacion/`. SQLite tiene una tabla `records` que distingue conjuntos mediante `dataset` y guarda los atributos en `payload` (JSON). `runs` registra ejecuciones y `snapshots` su estado. Los CSV y Sheets tienen encabezados propios para cada reporte de Alma.

`.env` contiene claves de Alma y LibCal; `secrets/` guarda los JSON de autorización de Google; `config.toml` indica rutas, IDs y mapas. Estos archivos privados y `data/` están excluidos de Git. No necesitas modificarlos para publicar la muestra.

`docs/1_1.yml` es la especificación de LibCal y `docs/database/` contiene la arquitectura institucional. Se conservan como referencias técnicas para las fases pendientes, no como guías de configuración.

## Desarrollo

Código en `src/alma_libcal/`, conectores en `src/alma_libcal/connectors/`, pruebas en `tests/`. Para ejecutarlas:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Las pruebas usan respuestas ficticias y bases temporales, sin consultar sistemas reales.
