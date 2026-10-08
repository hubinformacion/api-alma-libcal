# Alma + LibCal → reportes de biblioteca

La extracción, las cantidades y la publicación en Google Sheets de la muestra inicial están validadas. Los reportes de préstamos, renovaciones y reservas permanecen separados. La ejecución es manual; todavía no hay tareas programadas.

## Comandos de uso diario

Ejecuta desde la terminal del proyecto:

```bash
cd /home/asus/projects/api-alma-libcal
```

`.venv/bin/python -m alma_libcal` llama al programa con sus dependencias ya instaladas. No necesitas activar el entorno. `--only` acepta `prestamos`, `renovaciones` y `reservas`, solos o juntos.

### Extraer Alma y guardar localmente

```bash
.venv/bin/python -m alma_libcal sync --only prestamos renovaciones --from 2026-10-07 --to 2026-10-07 --extract-only
```

Cambia las fechas por el período que necesitas. Para un día, usa la misma fecha en ambos parámetros. `--extract-only` guarda en SQLite y muestra cuántas filas extrajo, sin publicar.

### Extraer LibCal y guardar localmente

```bash
.venv/bin/python -m alma_libcal sync --only reservas --from 2026-10-08 --to 2026-10-08 --extract-only
```

**Sustituye ambas fechas por el día actual.** El endpoint usado no admite fechas pasadas. LibCal consulta las categorías configuradas de los seis campus. No omitas las fechas: el inicio predeterminado del proyecto podría ser anterior a hoy.

### Publicar el histórico guardado

```bash
.venv/bin/python -m alma_libcal publish --only prestamos renovaciones reservas
```

Para publicar un solo conjunto, deja únicamente su nombre tras `--only`. La publicación reemplaza las pestañas seleccionadas con todo su histórico local y actualiza `control`. No vuelve a consultar los sistemas. Usa otras pestañas para fórmulas o ediciones manuales.

### Extraer y publicar en una misma ejecución

```bash
.venv/bin/python -m alma_libcal sync --only prestamos renovaciones --from 2026-10-07 --to 2026-10-07
```

Omitir `--extract-only` permite consultar, guardar y publicar. Para incluir LibCal, el intervalo debe ser de hoy o futuro. Los registros se actualizan por ID; repetir una fecha o publicación no agrega copias del mismo registro.

### Consultar estado y ayuda

```bash
.venv/bin/python -m alma_libcal status
.venv/bin/python -m alma_libcal --help
.venv/bin/python -m alma_libcal sync --help
```

`total_rows` cuenta todo el histórico. Después de publicar, `pending` debe ser `no` y `revision` debe coincidir con `published_revision`. Una configuración alternativa se indica antes del subcomando: `--config otra-config.toml status`.

## Comandos de diagnóstico

| Comando y ejemplo después de `.venv/bin/python -m alma_libcal` | Utilidad |
| --- | --- |
| `inspect-alma --dataset renovaciones --from 2026-10-07 --to 2026-10-07` | Ver encabezados de Analytics; necesario después de cambiar sus columnas |
| `inspect-alma --dataset prestamos --without-filter` | Diagnosticar acceso al reporte sin filtro de fecha |
| `check-libcal --location 20114 --category 42372` | Contar las reservas de salas de Cusco de hoy y sus estados, sin guardarlas |
| `discover-libcal` | Listar ubicaciones de LibCal |
| `discover-libcal --locations 20114` | Listar categorías del campus indicado |
| `discover-libcal --category 42372` | Listar recursos de esa categoría |
| `discover-libcal --form 8253` | Consultar las preguntas del formulario |
| `auth-google --open-browser` | Renovar la autorización únicamente si Google la requiere |
| `demo` | Ejecutar una muestra ficticia sin conexiones reales; resultados en `demo-output/` |

`check-libcal` admite `--date YYYY-MM-DD` para hoy o fechas futuras. Los IDs de campus, categorías y formularios ya están en `config.toml`.

## Campus de las renovaciones: siguiente ajuste

Confirmaste que el caso sin campus corresponde a una renovación realizada por un operador sin módulo/locación asignado. Los campos originales `renewal_campus_code` y `renewal_campus_name` deben conservar ese vacío.

Podemos incorporar el campus del préstamo original como referencia mediante `loan_campus_code` y `loan_campus`. El criterio para agrupar sería usar el campus de renovación cuando exista y, si falta, el del préstamo original, conservando la distinción de origen. No representa una confirmación del lugar donde se renovó.

Para obtenerlo, abre el análisis **Renewals** conectado a la API y añade al final, desde **Loan Circulation Desk**, **Campus Code** y **Campus Name**, sin fórmulas. Puedes ponerles encabezados `Loan Campus Code` y `Loan Campus Name`. Esa dimensión describe el módulo del préstamo original. [Referencia de Ex Libris](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_(English)/080Analytics/Alma_Analytics_Subject_Areas/Fulfillment).

Guarda el análisis y ejecuta `inspect-alma --dataset renovaciones --from 2026-10-07 --to 2026-10-07`. Comparte su salida de encabezados para actualizar el mapa y ampliar la salida del programa. **No extraigas renovaciones después de modificar el análisis hasta actualizar el mapa:** Analytics puede cambiar los números ColumnN. Estas dos columnas adicionales todavía no están incorporadas al extractor.

## Dónde están los datos

- `data/pilot.sqlite3`: histórico local de los tres conjuntos. `records` distingue sistemas mediante `dataset` y guarda atributos en `payload`; `runs` registra ejecuciones y `snapshots` su estado.
- `data/verificacion/`: CSV de la muestra inicial. Son copias de ese momento; `sync` no los actualiza automáticamente.
- Google Sheets: hoja indicada por `[google].spreadsheet_id` en `config.toml`. La suma de renovaciones se obtiene de `renewal_quantity`, no del número de filas.

`.env` contiene claves de Alma y LibCal; `secrets/` contiene los JSON de autorización de Google; `config.toml` indica rutas, IDs y mapas. Los archivos privados y `data/` están excluidos de Git.

## Referencias y desarrollo pendiente

En `docs/` solo se conservan `1_1.yml` (API LibCal) y `database/` (arquitectura institucional). Las guías de configuración y verificación completadas fueron retiradas.

Quedan incorporar el campus de referencia, completar campos finales de LibCal, resolver su fuente histórica, cruzar usuarios con la universidad y programar las extracciones.

Código en `src/alma_libcal/`; pruebas en `tests/`. Para comprobar el programa con datos ficticios:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```
