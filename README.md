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

## Transformaciones implementadas

### Alma

El mapa de Renewals ya incluye el campus del préstamo original y el nuevo orden de columnas. Se conservan `renewal_campus_code/name` y se añaden `loan_campus_code` y `loan_campus`.

Para agrupar usa `report_campus_code` y `report_campus`: priorizan el campus de renovación y, si ambos campos están vacíos, usan el préstamo original. `report_campus_source` identifica `renewal`, `loan` o `unassigned`. Si existe un campus parcial, no se mezclan códigos y nombres de orígenes distintos. La clave interna de la renovación sigue usando el campus original de renovación para evitar duplicados al completar la referencia.

Préstamos incorporan `loan_month`, `loan_month_number` y `loan_hour`; renovaciones, `renewal_month` y `renewal_month_number`. La hora se deriva de Loan Time, que se conserva tal como viene. Los meses están en español y las fechas en formato ISO.

### LibCal

La salida de reservas contiene los atributos operativos del reporte: correo, recurso, categoría, campus, fecha, inicio/fin, mes, número de mes, hora, estado, confirmación y correos de integrantes. Incluye IDs y puestos para seguimiento.

- `booking_duration_hours`: horas decimales entre inicio y fin, incluso si cruza medianoche. `booking_duration_minutes` conserva también la medida en minutos. Es duración reservada, no uso efectivo medido por check-in/check-out.
- `booking_confirmation`: Confirmado para Confirmed; Cancelado para los estados Cancelled/Canceled. Otros estados quedan sin clasificar en esta columna y se conservan en `booking_status`.
- `source_user_id`: parte anterior a `@` del correo cuando no hay ID explícito. Conserva ceros iniciales; es una clave candidata, no un DNI validado con la institución.
- `booking_account_email`: se llena solo si `account` contiene un correo. El valor original se conserva en `booking_account`; no se inventa un dominio para un login.
- `user_name`, `user_lastname`, `user_type`, `user_modality`, `user_campus`, `user_program`, `user_department` y `user_business_unit` quedan vacíos hasta cruzar con la base universitaria. Los nombres manuales de LibCal se conservan aparte en `source_user_name/lastname`; `user_email` conserva por ahora el correo original para el cruce.

Inicio/fin se normalizan a America/Lima; la fecha, mes y hora se calculan desde el inicio local. Los formularios 8253 aportan los correos de integrantes 2 y 3; las demás categorías dejan esas columnas vacías.

## Cómo publica y qué falta para escalar

SQLite actualiza por ID los registros del intervalo solicitado y conserva el histórico anterior. Sheets todavía recibe una copia completa del histórico de las pestañas seleccionadas; no compara qué filas faltan o cambiaron. El cambio de encabezados queda reflejado en esa recarga.

Se reemplazan valores y se escriben los nuevos en una sola petición atómica. El publicador limita esa petición a **1,8 MB** y la rechaza antes de enviarla si supera el umbral; el histórico local queda disponible. Google recomienda peticiones de hasta 2 MB y aplica cuotas y tiempos máximos de procesamiento. [Límites de Sheets](https://developers.google.com/workspace/sheets/api/limits).

Para miles de registros, el próximo cambio será publicar por lotes y comparar claves y contenido: agregar nuevos, actualizar modificados y omitir iguales. Al cambiar el esquema se necesitará reconstruir la salida de manera controlada. Esta publicación incremental todavía no está implementada.

## Dónde están los datos

- `data/pilot.sqlite3`: histórico local de los tres conjuntos. `records` distingue sistemas mediante `dataset` y guarda atributos en `payload`; `runs` registra ejecuciones y `snapshots` su estado.
- `data/verificacion/`: CSV de la muestra inicial. Son copias de ese momento; `sync` no los actualiza automáticamente.
- Google Sheets: hoja indicada por `[google].spreadsheet_id` en `config.toml`. La suma de renovaciones se obtiene de `renewal_quantity`, no del número de filas.

`.env` contiene claves de Alma y LibCal; `secrets/` contiene los JSON de autorización de Google; `config.toml` indica rutas, IDs y mapas. Los archivos privados y `data/` están excluidos de Git.

## Referencias y desarrollo pendiente

En `docs/` solo se conservan `1_1.yml` (API LibCal) y `database/` (arquitectura institucional). Las guías de configuración y verificación completadas fueron retiradas.

El orden de trabajo siguiente es:

1. Comparar las transformaciones con tus reportes terminados. Coloca `alma-prestamos.csv`, `alma-renovaciones.csv` y `libcal.csv` en **`data/referencias/`**. Esta carpeta es local y está excluida de Git; no se carga a Sheets automáticamente.
2. Implementar publicación incremental y por lotes antes de ampliar la carga histórica.
3. Definir el cruce con la base universitaria y la vigencia de los atributos académicos.
4. Resolver la fuente histórica de LibCal y programar las ejecuciones. Su endpoint actual no permite recuperar fechas pasadas.

Código en `src/alma_libcal/`; pruebas en `tests/`. Para comprobar el programa con datos ficticios:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```
