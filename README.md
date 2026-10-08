# Alma + LibCal → reportes de biblioteca

La configuración básica está preparada. Estamos verificando datos reales de ambos sistemas; los reportes se mantienen separados y la base universitaria completará después los atributos de usuarios.

Empieza por [00 — Empieza aquí](docs/00-inicio.md). No necesitas conocer Python para ejecutar los comandos de las guías.

| Orden | Guía |
| --- | --- |
| 00 | [Etapa actual y estructura de carpetas](docs/00-inicio.md) |
| 01 | [Extraer y comparar Alma](docs/01-alma.md) |
| 02 | [Contar, guardar y comparar LibCal](docs/02-libcal.md) |
| 03 | [Abrir SQLite en Antigravity o visualizar en Sheets](docs/03-ver-datos.md) |

Los registros guardados están en `data/pilot.sqlite3`. Los comandos de inspección y comprobación solo muestran resultados en la terminal; las extracciones con `--extract-only` sí guardan filas. La publicación a Google es un paso adicional.

Las cantidades de la muestra inicial están validadas y Alma tiene esquemas de salida propios para préstamos y renovaciones. Todavía faltan algunos campos finales de LibCal, la fuente histórica de LibCal y la automatización. La API LibCal utilizada no admite fechas pasadas.

## Para desarrollo

Código en `src/alma_libcal/`, conectores en `src/alma_libcal/connectors/`, pruebas en `tests/`. Las referencias técnicas están en `docs/1_1.yml` y `docs/database/`. Configuración local y datos están excluidos de Git.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Las pruebas usan respuestas ficticias y bases temporales, sin credenciales ni consultas a sistemas reales.
