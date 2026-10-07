# Alma + LibCal → reportes de biblioteca

Proyecto para extraer préstamos/renovaciones de Alma Analytics y reservas de LibCal. Los reportes permanecen separados; los datos académicos y de identidad se completarán después desde la base universitaria.

## Empieza aquí

Lee [00 — Inicio y orden de trabajo](docs/00-inicio.md). Tu primera tarea es **crear el análisis Loans en Alma Analytics**, siguiendo el documento 01. No hace falta configurar claves ni Google para empezar.

| Orden | Guía |
| --- | --- |
| 00 | [Inicio: alcance y primer paso](docs/00-inicio.md) |
| 01 | [Alma: columnas, reglas de préstamos/renovaciones y acceso API](docs/01-alma.md) |
| 02 | [LibCal: reservas, formularios y acceso API](docs/02-libcal.md) |
| 03 | [Programa: configuración, validación y Google Sheets](docs/03-programa-y-sheets.md) |

**Estado:** existe un piloto manual en Python, SQLite y Google Sheets. Todavía debe ampliarse para guardar todos los campos definidos en las guías. Primero validaremos las estructuras reales de los proveedores. La automatización diaria/semanal y el cruce institucional serán etapas posteriores.

## Ejecución sencilla

Desde Ubuntu, en la carpeta del proyecto:

```bash
./run.sh --help
./run.sh discover-libcal --locations 20114
./run.sh check-libcal --location 20114
```

El programa lee `.env` junto a `config.toml`; `run.sh` gestiona el entorno Python sin activarlo manualmente. Los pasos e IDs por campus están en 02. La consulta LibCal documentada ignora fechas pasadas: aún debemos definir otra fuente para el histórico.

## Demostración sin credenciales

En Ubuntu/WSL2, con Python 3.12 o posterior, desde la carpeta del proyecto:

```bash
PYTHONPATH=src python3 -m alma_libcal demo
```

Genera `demo-output/pilot.sqlite3` y `demo-output/sheets.json` con datos ficticios, sin consultar APIs ni publicar en Google. Se puede repetir sin duplicar registros. La instalación para usar fuentes reales se explica en 03.

## Desarrollo

- `src/alma_libcal/`: programa, configuración, modelos y almacenamiento.
- `src/alma_libcal/connectors/`: Alma, LibCal y Google Sheets.
- `tests/`: pruebas con `unittest`, respuestas ficticias y bases temporales.
- `docs/`: las cuatro guías; `docs/database/` conserva los metadatos institucionales recibidos.
- `config.example.toml`: plantilla; `config.toml` y `secrets/` son privados y están excluidos de Git.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m compileall -q src tests
```

Estilo del código: cuatro espacios y nombres `snake_case`. Las pruebas verifican paginación, duplicados, cantidades, cancelaciones y recuperación ante errores. La comparación con los sistemas institucionales sigue siendo necesaria antes de usar los datos reales.
