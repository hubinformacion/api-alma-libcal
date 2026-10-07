# Alma + LibCal → reportes de biblioteca

Extraemos operaciones de Alma y LibCal por separado. La base universitaria completará después los datos de usuarios.

## Pendientes

Empieza por [00 — Estado y próximos pasos](docs/00-inicio.md). Ya están preparados Python, las credenciales locales y Google Sheets; las guías contienen únicamente lo que falta validar o completar.

| Orden | Guía |
| --- | --- |
| 00 | [Estado y próximos pasos](docs/00-inicio.md) |
| 01 | [Alma: ajustes y validación](docs/01-alma.md) |
| 02 | [LibCal: categorías y prueba de reservas](docs/02-libcal.md) |
| 03 | [Completar extracción y validar publicación](docs/03-programa-y-sheets.md) |

## Comandos directos

Desde la carpeta del proyecto, sin activar entornos ni usar scripts:

```bash
.venv/bin/python -m alma_libcal inspect-alma --dataset prestamos --without-filter
.venv/bin/python -m alma_libcal discover-libcal --locations 20114
.venv/bin/python -m alma_libcal check-libcal --location 20114
```

`.venv/bin/python` selecciona el Python que ya tiene las dependencias de Google instaladas. `.env` contiene las credenciales y se lee automáticamente; `config.toml` contiene rutas, IDs y mapas de campos. Se usan juntos. Las opciones terminadas en `_env` solo indican nombres de variables, no contienen claves.

El piloto todavía debe ampliarse para guardar todos los campos del reporte. La consulta documentada de LibCal ignora fechas pasadas; el histórico requiere otra fuente.

## Desarrollo

Código en `src/alma_libcal/`, conectores en `src/alma_libcal/connectors/`, pruebas en `tests/`. `docs/1_1.yml` contiene la especificación LibCal y `docs/database/` los metadatos institucionales. `config.example.toml` y `.env.example` son plantillas; los archivos locales y `secrets/` están excluidos de Git.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Las pruebas usan `unittest`, respuestas ficticias y bases temporales. Para una demostración sin red ni publicación: `.venv/bin/python -m alma_libcal demo`. Estilo del código: cuatro espacios y nombres `snake_case`.
