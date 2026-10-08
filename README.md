# Alma + LibCal — Guía de uso

Proyecto en desarrollo para extraer operaciones de biblioteca, guardarlas en SQLite y publicar reportes separados en Google Sheets. Actualmente las pruebas y extracciones se ejecutan manualmente. Los jobs diarios y el cruce con la base universitaria serán fases posteriores.

## Ejecutar desde la terminal

Abre la carpeta del proyecto y utiliza su Python con dependencias instaladas:

```bash
cd /home/asus/projects/api-alma-libcal
.venv/bin/python -m alma_libcal --help
```

No necesitas activar `.venv`. `.env` contiene claves de Alma y LibCal; `config.toml` contiene rutas, IDs, mapas y catálogos; `secrets/` conserva la autorización de Google. Estos archivos locales se leen automáticamente y están excluidos de Git. Las plantillas públicas son `.env.example` y `config.example.toml`.

## Extraer y publicar

### Alma: préstamos y renovaciones de un período

```bash
.venv/bin/python -m alma_libcal sync --only prestamos renovaciones --from 2026-10-06 --to 2026-10-07 --extract-only
```

Cambia las fechas según el período. `--extract-only` guarda sin publicar. Préstamos se seleccionan por Loan Date y renovaciones por Renewal Date. Las renovaciones automáticas no forman parte del conteo fechado de este análisis.

### LibCal: reservas del día actual

```bash
.venv/bin/python -m alma_libcal sync --only reservas --from 2026-10-08 --to 2026-10-08 --extract-only
```

**Sustituye ambas fechas por hoy** cuando ejecutes el comando otro día. El endpoint de listado usado no permite fechas pasadas. Se consultan las categorías configuradas de los seis campus, incluidas canceladas.

### Publicar el histórico guardado

```bash
.venv/bin/python -m alma_libcal publish --only prestamos renovaciones reservas
.venv/bin/python -m alma_libcal status
```

`publish` crea las pestañas que faltan y reemplaza los valores de las seleccionadas con todo el histórico local; también actualiza `control`. No consulta las APIs. Usa otras pestañas para fórmulas o ediciones manuales. `pending = no` y `revision = published_revision` indican publicación registrada; `total_rows` cuenta todo el histórico.

Para consultar, guardar y publicar en una ejecución, omite `--extract-only` en `sync`. `--only` acepta uno o varios conjuntos. Usa `sync --help` para sus opciones. Una configuración alternativa se indica antes del subcomando: `--config otra-config.toml status`.

## Comandos disponibles

Todos se preceden de `.venv/bin/python -m alma_libcal`:

| Comando | Uso |
| --- | --- |
| `sync` | Extraer, guardar y publicar; admite `--only`, `--from`, `--to`, `--extract-only` |
| `publish --only prestamos` | Publicar solo el conjunto indicado, sin consultar el origen |
| `status` | Consultar estado, cantidades y errores locales |
| `inspect-alma --dataset renovaciones --from 2026-10-06 --to 2026-10-07` | Mostrar columnas; necesario tras modificar Analytics |
| `inspect-alma --dataset prestamos --without-filter` | Diagnosticar el acceso sin filtro de fecha |
| `check-libcal --location 20114 --category 42372` | Contar reservas de salas de Cusco de hoy, sin guardarlas; admite `--date` para hoy/futuro |
| `discover-libcal` | Listar ubicaciones |
| `discover-libcal --locations 20114` | Listar categorías de un campus |
| `discover-libcal --category 42372` | Listar recursos |
| `discover-libcal --form 8253` | Consultar preguntas del formulario |
| `auth-google --open-browser` | Renovar autorización si Google la requiere |
| `demo` | Demostración ficticia, sin servicios reales; salida en `demo-output/` |

## Datos y reglas de reporte

- **SQLite:** `data/pilot.sqlite3`. `records` guarda el estado actual, `record_versions` conserva cambios de contenido, `runs` registra ejecuciones y `snapshots` su estado. Repetir datos idénticos no crea copias ni versiones nuevas. `record_changed_at` es observación local, no fecha de operación.
- **Sheets:** hoja indicada por `[google].spreadsheet_id`; pestañas `prestamos`, `renovaciones`, `reservas` y `control`. Los encabezados usan inglés en snake_case; códigos y nombres se conservan separados.
- **Materiales:** edita pares en `[reporting.material_types]`. Se conservan código, nombre y estado de equivalencia; un código nuevo no se inventa ni se descarta.
- **Tipos de préstamo:** Uso interno por indicador Y; autopréstamo por nombre/descripción del módulo; otros módulos por bibliotecario. Una renovación no se clasifica por el módulo del préstamo original.
- **Renovaciones:** suma `renewal_quantity`. Su `record_id` identifica préstamo/día/campus, no un evento individual. `report_campus_source` distingue campus de renovación y referencia del préstamo original.
- **Asistencia:** independiente del estado de reserva. Sí → 1; No explícito → 0; sin registro → vacío en el indicador. Un estado desconocido tampoco se interpreta como ausencia. Equivalencias editables en `[reporting.attendance_statuses]`.
- **Duración:** horas decimales exactas entre inicio y fin, incluso al cruzar medianoche; corresponde a tiempo reservado, no necesariamente a uso efectivo.
- **Formularios:** se extraen respuestas por ID: celular, correos de integrantes y términos. No se exportan los textos de preguntas.
- **Usuarios:** claves originales y nombres manuales se conservan como `source_user_*`. El correo puede aportar una clave candidata anterior a @. Los atributos verificados quedan pendientes del cruce universitario a la fecha de operación; los usos internos sin usuario no requieren ese cruce.
- **Meses y horas:** se calculan al exportar, sin duplicarlos en SQLite. Para omitir esas columnas en Sheets y utilizar un calendario de Power BI, cambia `[reporting].include_date_parts = false`.

Los archivos de `data/` son locales, contienen información personal y no se publican en GitHub. Los CSV de esta prueba están en **`data/reportes/`**, uno por conjunto y fecha. Son copias de ese momento: `sync` no los actualiza automáticamente. Las referencias aportadas para diseño se conservan localmente en `data/referencias/`; la especificación de API y la arquitectura institucional están en `data/referencias/technical/`, fuera del repositorio publicado.

## Histórico de LibCal y próximos pasos

`/space/bookings` ignora fechas pasadas. `/space/bookings/updates` recupera cambios recientes de las últimas 24 horas, incluidos cambios de reservas antiguas; no reconstruye meses de histórico. La consulta por ID conocido devolvió una reserva del 2 de octubre durante esta prueba. Puede complementar registros antiguos, pero requiere sus IDs; la especificación excluye canceladas y no proporciona un listado histórico completo.

Antes de producción debemos preparar una carga inicial desde una exportación administrativa con IDs, fechas/horas completas, recursos, estados, asistencia y respuestas. Su importador y la consulta histórica por ID todavía no están implementados. Luego necesitaremos capturar cambios con frecuencia suficiente para conservar cancelaciones y asistencias posteriores; una consulta semanal aislada no cubre la ventana de 24 horas.

El orden siguiente es: validar esta nueva muestra, conectar la base universitaria en modo lectura y resolver vigencias históricas, implementar publicación incremental por lotes antes de ampliar el volumen, completar el histórico de LibCal y finalmente programar jobs con control de fallos y recuperación.

La publicación actual sustituye las tablas seleccionadas en una petición atómica y tiene un límite local de 1,8 MB. No compara filas nuevas/modificadas en Sheets. Para cargas grandes primero debe ampliarse el publicador.

## Código y verificación

Código en `src/alma_libcal/`, pruebas automatizadas en `tests/` y fixtures ficticios en `src/alma_libcal/fixtures/`. Estas pruebas son parte del proyecto; los resultados temporales se eliminan al terminar.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```
