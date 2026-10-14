# Alma + LibCal — Guía de uso

Proyecto en desarrollo para extraer operaciones de biblioteca, guardarlas en SQLite y publicar reportes separados en Google Sheets. Actualmente las pruebas y extracciones se ejecutan manualmente. El cruce institucional se realiza mediante archivos exportados desde SSMS; la conexión directa y los jobs diarios siguen pendientes.

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
| `import-users 09.csv --review 08_revisada.csv` | Validar e importar perfiles institucionales y generar CSV completos en `data/reportes/`; no publica |
| `inspect-alma --dataset renovaciones --from 2026-10-06 --to 2026-10-07` | Mostrar columnas; necesario tras modificar Analytics |
| `inspect-alma --dataset prestamos --without-filter` | Diagnosticar el acceso sin filtro de fecha |
| `check-libcal --location 20114 --category 42372` | Contar reservas de salas de Cusco de hoy, sin guardarlas; admite `--date` para hoy/futuro |
| `discover-libcal` | Listar ubicaciones |
| `discover-libcal --locations 20114` | Listar categorías de un campus |
| `discover-libcal --category 42372` | Listar recursos |
| `discover-libcal --form 8253` | Consultar preguntas del formulario |
| `auth-google --open-browser` | Renovar autorización si Google la requiere |
| `demo` | Demostración ficticia, sin servicios reales; salida en `demo-output/` |

## Salida compacta de Sheets

`[reporting].sheet_layout = "compact"` publica solo la información de reportería: ahora 21 columnas para préstamos, 23 para renovaciones y 29 para reservas. Se conserva `record_id`; en renovaciones se conserva también `loan_id`. Se omiten columnas técnicas duplicadas, como loan_channel, códigos de material, versiones y marcas de auditoría. Meses y horas derivadas no forman parte del esquema compacto; fechas y timestamps base permiten calcularlos.

SQLite y los reportes completos mantienen todos los atributos. `sheet_layout = "full"` permite recuperarlos en Sheets sin volver a consultar las APIs. Si necesitas personalizar una pestaña, puedes añadir en el mismo config.toml:

```toml
[reporting.sheet_columns]
prestamos = ["record_id", "user_email", "loan_type", "loan_date", "loan_campus_name"]
```

La lista reemplaza la selección de ese conjunto. Los nombres deben existir, ser únicos e incluir record_id. El formato de una pestaña cambia en la siguiente publicación. `control` permanece completo. Esta selección reduce columnas; la publicación aún incluye todo el histórico local y no es incremental.

## Datos y reglas de reporte

- **SQLite:** `data/pilot.sqlite3`. `records` guarda el estado actual, `record_versions` conserva cambios de contenido, `runs` registra ejecuciones y `snapshots` su estado. Repetir datos idénticos no crea copias ni versiones nuevas. `record_changed_at` es observación local, no fecha de operación.
- **Sheets:** hoja indicada por `[google].spreadsheet_id`; pestañas `prestamos`, `renovaciones`, `reservas` y `control`. Los encabezados usan inglés en snake_case; códigos y nombres se conservan separados.
- **Materiales:** edita pares en `[reporting.material_types]`. Se conservan código, nombre y estado de equivalencia; un código nuevo no se inventa ni se descarta.
- **Tipos de préstamo:** Uso interno por indicador Y; autopréstamo por nombre/descripción del módulo; otros módulos por bibliotecario. Una renovación no se clasifica por el módulo del préstamo original.
- **Renovaciones:** suma `renewal_quantity`. Su `record_id` identifica préstamo/día/campus, no un evento individual. `report_campus_source` distingue campus de renovación y referencia del préstamo original.
- **Asistencia:** independiente del estado de reserva. Sí → 1; No explícito → 0; sin registro → vacío en el indicador. Un estado desconocido tampoco se interpreta como ausencia. Equivalencias editables en `[reporting.attendance_statuses]`.
- **Duración:** horas decimales exactas entre inicio y fin, incluso al cruzar medianoche; corresponde a tiempo reservado, no necesariamente a uso efectivo.
- **Formularios:** se extraen respuestas por ID: celular, correos de integrantes y términos. No se exportan los textos de preguntas.
- **Usuarios:** claves originales y nombres manuales se conservan como `source_user_*`. El correo puede aportar una clave candidata anterior a @. Los atributos verificados provienen del cruce institucional a la fecha de operación; los usos internos sin usuario no requieren ese cruce.
- **Meses y horas:** se calculan al exportar, sin duplicarlos en SQLite. Para omitir esas columnas en Sheets y utilizar un calendario de Power BI, cambia `[reporting].include_date_parts = false`.

Los archivos de `data/` son locales, contienen información personal y no se publican en GitHub. Los CSV completos generados por `import-users` están en **`data/reportes/prestamos.csv`**, **`renovaciones.csv`** y **`reservas.csv`**, con todo el histórico local de cada conjunto. `usuarios_revision.csv` detalla el estado y motivo por cuenta/fecha. Son copias del momento de la importación: `sync` y `publish` no actualizan estos archivos. Las referencias aportadas para diseño se conservan localmente en `data/referencias/`; la especificación de API y la arquitectura institucional están en `data/referencias/technical/`, fuera del repositorio publicado.

## Incorporar los datos institucionales

En el piloto, el equipo institucional ejecuta SQL de lectura en SSMS y este equipo importa sus CSV. No compartas credenciales ni necesitas instalar Python en el equipo institucional.

### Importar el lote actual

El archivo 09 debe conservar encabezados y la columna JSON completa, sin editarla en Excel. Para los archivos recibidos en este piloto:

```bash
.venv/bin/python -m alma_libcal import-users data/referencias/usuarios/actual/09_perfiles_lote.csv --review data/referencias/usuarios/lote/08_validacion_lote_revisada.csv
```

Esto valida correspondencia con el histórico, persona, fecha y ámbito antes de importar. Guarda perfiles y evidencia en tablas separadas de SQLite y genera los cuatro CSV de `data/reportes/`. Repetir un lote idéntico no crea versiones de perfil ni revisiones de publicación adicionales. Los registros originales de Alma/LibCal permanecen intactos.

Abre los CSV para revisar `user_type`, `user_full_name`, campus y programa. `user_match_status` distingue:

| Estado | Significado |
| --- | --- |
| `matched_profile` | Perfil con los atributos de reportería completos |
| `partial_profile` | Tipo de usuario identificado; faltan atributos o existen ambigüedades |
| `pending_review` | Identidad, ámbito o rol pendiente de comprobar |
| `configured_service_account` | Cuenta de área del catálogo local |
| `not_applicable` | Uso interno de Alma |

Estos estados describen el **cruce de usuarios**, no el estado del préstamo, la reserva o la asistencia. `partial_profile` no invalida los atributos ya identificados; por ejemplo, un estudiante de instituto puede tener rol y programa confirmados, pero campus pendiente. En administrativos, **carrera, facultad y modalidad muestran «No aplica»**, incluidas las cuentas de servicios. Esos campos no se cuentan como faltantes. Campus y unidad institucional sí requieren datos confirmados; un administrativo con campus pendiente mantiene `partial_profile`.

Para un **Docente**, `user_program_name` representa el programa de su programación docente; `user_department_name`, la facultad de su pertenencia docente cuando está disponible y es consistente. No provienen de una matrícula del docente como estudiante. Si existen varias asignaciones, se conservan los atributos comunes y no se elige una carrera arbitrariamente.

Los atributos descriptivos sin evidencia muestran **Pendiente de revisión**. Un nombre completo institucional no se divide por suposición; LibCal conserva además nombres manuales en `source_user_*`. Ninguna excepción elimina ni duplica operaciones.

Después de revisar, publica el histórico enriquecido:

```bash
.venv/bin/python -m alma_libcal publish --only prestamos renovaciones reservas
```

### Reglas y configuración

- El correo utilizado delimita el perfil: instituto → IC; universidad → UC/PSG/EDC; trabajo → empleo/docencia. No se trasladan atributos de una cuenta a otra por compartir documento.
- Para UC, Estudiante requiere el período confirmado, estado académico y matrícula ACTIVO, créditos positivos y fechas aplicables. No se usan períodos futuros. En `[institutional.university_period_by_date]` está confirmado **202620 únicamente para 2026-10-06, 07 y 08**. Para otras fechas se requiere validar el calendario.
- Egresado requiere evidencia formal anterior a la operación; incluye bachiller/titulado. Para UC se consideran fechas formales y estados fechados EGRESADO/BACHILLER/TITULADO. Un trámite de grado en el período actual no constituye una nueva matrícula. Entre programas finalizados se prioriza la fecha conocida de fin académico más reciente; cuando falta, se usan fechas de egreso y luego de estudio como referencias explícitas. La titulación y emisión de certificados no ordenan carreras. Si otro estudio posterior sigue sin resolverse, se conserva el perfil respaldado con `partial_profile` y su motivo; el perfil sin respaldo suficiente continúa pendiente.
- En instituto, certificado de egresado con estado **1 (emitido/aprobado, confirmado)** y fecha válida anterior o igual a la operación permite Egresado. Una matrícula vigente posterior tiene prioridad. Para graduados, el fin de la última sección del mismo programa sirve de referencia con el certificado aprobado; no se presenta como una fecha oficial del programa completo. Si existe otro estudio sin finalización comprobada, el perfil respaldado se conserva como parcial. La fecha de emisión del certificado no se usa para ordenar estudios. Los estados originales y su evidencia se conservan en SQLite.
- Una fecha de fin por sí sola no demuestra aprobación: el rol Egresado sigue necesitando evidencia académica. No estar matriculado, una emisión de documento de Continua o un estado comercial tampoco demuestran egreso. Posgrado y Continua todavía requieren validar sus reglas; un código sin descripción de su propio catálogo no se interpreta con el catálogo de otra escuela.
- Docente precede a Administrativo con evidencia docente vigente; incluye JEFE DE PRACTICA. ES_DOCENTE por sí solo no demuestra vigencia. FECHA_TERMINO no se usa como retiro; se contrasta ingreso y FECHA_RETIRO.
- Las matrículas vigentes tienen prioridad sobre estudios finalizados. Si hay varios perfiles finalizados, se elige la finalización conocida más reciente; los empates conservan atributos comunes y dejan pendientes los ambiguos. Los códigos laborales no se convierten en campus sin equivalencias confirmadas en `[institutional.labor_campuses]`. En `[institutional.labor_business_units]` están confirmados UCCI → Universidad Continental e IESC → Instituto Continental.
- Las cuentas de servicios se agregan por correo exacto en `[reporting].service_accounts`. Se reportan como Administrativo y campus Virtual, sin atributos de persona. No cambia el campus de la operación.

### Completar campus y calendarios

El campus laboral se configura en `[institutional.labor_campuses]` mediante claves `division:sucursal`. La institución debe confirmar el nombre correspondiente; no se equiparan automáticamente esos códigos con `dbo.DIM_CAMPUS` ni con el campus de una reserva/préstamo.

`sql/institutional/10_ubicaciones_y_calendarios.sql` permite investigar sucursales y posibles fuentes de ubicaciones/calendarios. Se ejecuta una sola vez por revisión de fuentes, sin parámetros, y sus dos resultados se exportan con encabezados a `data/referencias/usuarios/actual/`. Los códigos de sucursal sin nombres no bastan para asignar un campus.

Para ampliar las fechas del piloto necesitamos confirmar qué período corresponde a cada fecha, considerando modalidad o programa cuando tengan calendarios distintos. Las fechas de clases, secciones o carga de datos no demuestran por sí solas el inicio y fin de un período institucional completo.

### Investigar fechas de finalización

Para continuar con las fuentes disponibles, copia **`data/referencias/usuarios/lote/12_fechas_fin_preparado.sql`** al equipo institucional y ejecútalo completo una vez en SSMS, sin completar parámetros. Exporta sus dos resultados con encabezados a `data/referencias/usuarios/actual/`:

1. `12_fechas_programas.csv`: fechas y claves originales; conserva `profile_data` completo.
2. `12_fuentes_fechas_fin.csv`: otras fuentes candidatas y sus relaciones declaradas.

Una clave 0 se marca como no proporcionada, distinta de una clave real sin correspondencia. La consulta mantiene separados fin de programa, fin de sección y emisión de documentos; no une fuentes solo porque sus códigos se parezcan. El SQL público está en `sql/institutional/12_fechas_fin_programas.sql`; el preparado contiene casos privados y permanece fuera de Git. Estos resultados son diagnósticos y no se importan mediante `import-users`.

`data/reportes/validacion_academica.csv` resume la selección de los cuatro casos de prueba. Para el lote de operaciones, `usuarios_revision.csv` incluye `selected_academic_date`, `selected_academic_date_basis` y `academic_selection_policy`, que permiten verificar la fecha utilizada. La selección también se conserva en SQLite bajo `academic_selection`, junto con la evidencia original de egreso.

### Preparar otro lote

1. Extrae las operaciones necesarias con `sync --extract-only`.
2. Ejecuta `.venv/bin/python scripts/prepare_institutional_check.py`. Lleva el SQL preparado bajo `data/referencias/usuarios/lote/` a SSMS, ejecútalo completo y exporta con encabezados. Revisa identidades y ámbitos antes de preparar perfiles.
3. Con `08_validacion_lote_revisada.csv` actualizado, ejecuta `.venv/bin/python scripts/prepare_institutional_profiles.py`. En SSMS ejecuta `09_extraer_perfiles_preparado.sql` y guarda `09_perfiles_lote.csv` con encabezados.
4. Importa indicando las rutas reales y revisa los CSV antes de publicar. Si cambian las operaciones del lote, la validación exige prepararlo nuevamente.

Las consultas `00`–`07` de `sql/institutional/` sirven para investigar excepciones; no se repiten para cada extracción. Los SQL preparados y CSV personales se guardan exclusivamente bajo `data/`, excluido de Git.

## Histórico de LibCal y próximos pasos

`/space/bookings` ignora fechas pasadas. `/space/bookings/updates` recupera cambios recientes de las últimas 24 horas, incluidos cambios de reservas antiguas; no reconstruye meses de histórico. La consulta por ID conocido devolvió una reserva del 2 de octubre durante esta prueba. Puede complementar registros antiguos, pero requiere sus IDs; la especificación excluye canceladas y no proporciona un listado histórico completo.

Antes de producción debemos preparar una carga inicial desde una exportación administrativa con IDs, fechas/horas completas, recursos, estados, asistencia y respuestas. Su importador y la consulta histórica por ID todavía no están implementados. Luego necesitaremos capturar cambios con frecuencia suficiente para conservar cancelaciones y asistencias posteriores; una consulta semanal aislada no cubre la ventana de 24 horas.

El orden siguiente es: revisar el cruce del piloto, completar calendarios y equivalencias pendientes, preparar el acceso institucional en modo lectura, implementar publicación por lotes antes de ampliar el volumen, completar el histórico de LibCal y programar jobs con recuperación de fallos.

La publicación actual sustituye las tablas seleccionadas en una petición atómica y tiene un límite local de 1,8 MB. No compara filas nuevas/modificadas en Sheets. Para cargas grandes primero debe ampliarse el publicador.

## Código y verificación

Código en `src/alma_libcal/`, pruebas automatizadas en `tests/` y fixtures ficticios en `src/alma_libcal/fixtures/`. Estas pruebas son parte del proyecto; los resultados temporales se eliminan al terminar.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```
