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

## Columnas y transformaciones

Los tres reportes usan inglés en `snake_case`: `_code` para códigos, `_name` para nombres, `_date` para fechas ISO, `_time` para horas y `_at` para fecha/hora con zona. `record_id` es la clave del registro dentro de su conjunto; `source_system` indica Alma o LibCal. Las claves originales se conservan para comparar y actualizar.

### Materiales y préstamos

El código de Alma se conserva en `item_material_type_code`; su nombre se obtiene de **`[reporting.material_types]` en `config.toml`**. Ya contiene las 20 equivalencias aprobadas. Puedes añadir o eliminar pares allí; no necesitas otro CSV ni modificar Python. `item_material_type_mapping_status` identifica códigos mapeados, ausentes o desconocidos. Un código nuevo queda como Sin clasificar y conserva su valor original.

`loan_type` distingue Uso interno (indicador Y), Préstamo regular por autopréstamo (módulo cuyo nombre/descripción contiene autopréstamo, sin depender de mayúsculas o tildes) y Préstamo regular por bibliotecario (otros módulos). Si no hay módulo, se conserva sin asignar. `loan_channel` expone la clasificación para filtros.

Las renovaciones se extraen por Renewal Date y su cantidad se suma desde `renewal_quantity`. `renewal_type` es Renovación: no se deduce el canal de la renovación a partir del módulo del préstamo original. No existe un ID individual de renovación en este análisis: `record_id` identifica el agregado préstamo + fecha + campus de renovación; una fila puede contener varias renovaciones.

Para agrupar renovaciones usa `report_campus_code/name`. Prioriza el campus de renovación y, si ambos campos están vacíos, usa el préstamo original. `report_campus_source` distingue renewal, loan y unassigned. Las dos procedencias se conservan y los pares de campus no se mezclan.

### Reservas y asistencia

`booking_id` conserva bookId, `source_booking_row_id` conserva el id adicional de la respuesta y los IDs de campus/categoría/recurso/puesto permiten rastrear la operación. La reserva cuenta una vez; los integrantes adicionales no crean otras reservas.

- `booking_status`: estado traducido, independiente de asistencia; `source_booking_status` conserva el valor original.
- `booking_attendance_status`: Sí, No o -. `source_booking_attendance_status` conserva la marcación original. Las equivalencias están en **`[reporting.attendance_statuses]`**; los estados nuevos no reconocidos quedan como Desconocido, sin inferir ausencia.
- `booking_attendance_indicator`: 1 para Sí, 0 para No y vacío para - o Desconocido. Así los registros sin marcación no entran en el denominador de asistencia. Los códigos in/out indican uso registrado; el código `no` se traduce explícitamente a No cuando la API lo entrega. Hay que verificar cualquier otro código antes de incorporarlo al catálogo.
- `booking_duration_hours`: diferencia exacta entre timestamps, incluso al cruzar medianoche. Es tiempo reservado, no duración de uso medida por el gestor. No se añade 0,01 horas ni se redondea antes de sumar.
- `booking_start_at/end_at`: fecha/hora normalizada a America/Lima. `booking_start_time/end_time` presentan HH:MM:SS para comparar con el reporte manual.
- `booking_phone`, `booking_participant_2_email`, `booking_participant_3_email`: respuestas por ID de pregunta, sin textos de preguntas ni dependencia de su posición.
- `source_booking_terms_response`: respuesta original a términos; `booking_terms_accepted`: 1, 0 o vacío según la respuesta reconocida.
- `booking_category_code/name` distingue ID y grupo de reportería; `source_booking_category_name` conserva el nombre de origen. El prefijo Campus se retira en los nombres de campus de reporte; SQLite conserva el valor original.

### Usuarios

`source_user_id/email` conservan claves originales. En LibCal se obtiene una clave candidata desde la parte anterior a @ cuando no hay ID explícito; no se declara DNI verificado. Los nombres capturados manualmente quedan en `source_user_first_name/last_name`.

`user_id`, `user_full_name`, `user_first_name`, `user_last_name`, tipo, modalidad, campus, programa, departamento y unidad de negocio se completarán con la universidad. `user_match_status` es pending hasta implementar el cruce, o not_applicable para usos internos sin usuario. `user_email` conserva por ahora el correo de origen; se reemplazará por el institucional validado al cruzar. Los registros sin coincidencia no se eliminarán.

El perfil académico debe ser el vigente **en la fecha de la operación**, según tu decisión. La conexión a la base y la selección de vigencias aún no están implementadas; sin historial institucional no se inventará una situación pasada.

### Fechas, meses y espacio

SQLite guarda fechas/horas base; mes, número de mes y hora se calculan al exportar. Se mantienen por comodidad y compatibilidad con tu reporte manual. Si usarás una tabla calendario de Power BI y quieres omitirlos de Sheets, cambia **`[reporting].include_date_parts = false`**. Se conservan las fechas y horas completas. Los meses tienen nombres en español.

## Trazabilidad de actualizaciones

`record_version` y `record_changed_at` indican la versión del contenido guardado. Una extracción idéntica actualiza la observación sin crear otra versión; un cambio conserva el estado previo y crea la nueva versión en **`record_versions`** de SQLite. No se añaden copias a la tabla actual. Los cambios de etiquetas del catálogo se aplican al publicar sin modificar los códigos originales.

La auditoría empieza con esta actualización. Los registros que ya existían se conservan como baseline; no se reconstruyen versiones previas que nunca guardamos. `first_observed_at/last_observed_at` están disponibles en la tabla records. Estos tiempos son de observación local, no de realización de la operación.

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

1. Revisar las nuevas columnas y la asistencia. Los CSV manuales de enero en `data/referencias/` siguen como referencia privada; los catálogos ya están integrados en config.toml.
2. Implementar publicación incremental y por lotes antes de ampliar la carga histórica.
3. Implementar el cruce con la universidad para entregar perfiles vigentes a la fecha de cada operación, como ya acordamos.
4. Resolver la fuente histórica de LibCal y programar las ejecuciones. Su endpoint actual no permite recuperar fechas pasadas.

Código en `src/alma_libcal/`; pruebas en `tests/`. Para comprobar el programa con datos ficticios:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```
