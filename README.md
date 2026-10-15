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

**Cuándo considerar cerrado un día:** comprueba en Alma Analytics «Datos actualizados a partir del» (corte de extracción de Alma), no solo «Datos disponibles a partir del» (fin de la carga a Analytics). Con corte del 13/10/2026 a las 19:05 y atención hasta las 21:00, el día 13 todavía no está completo; para la prueba del 14 se extrae el **12 de octubre**. Usar D−2 es un margen operativo inicial, no una garantía ante retrasos del origen. Las horas deben compararse en la misma zona horaria. Los reportes actuales no incorporan esos indicadores de actualización: la comprobación sigue siendo manual. [Referencia oficial de Ex Libris](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_%28English%29/080Analytics/010Introduction/Analytics_Database_Refresh).

### LibCal: reservas del día actual

```bash
.venv/bin/python -m alma_libcal sync --only reservas --from 2026-10-08 --to 2026-10-08 --extract-only
```

**Sustituye ambas fechas por hoy** cuando ejecutes el comando otro día. El endpoint de listado usado no permite fechas pasadas. Se consultan las categorías configuradas de los seis campus, incluidas canceladas.

Horario de atención confirmado: **07:00–21:00, America/Lima**. La captura de cierre se propone a las **21:30 del mismo día, antes de medianoche**. Esto deja margen tras la atención, pero no impide correcciones posteriores de asistencia o cancelación. La recuperación de cambios recientes aún no está implementada; no se considera un cierre definitivo e inmutable ni se filtran registros por esas horas.

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
- **Clave de LibCal:** `booking_id` conserva el `bookId` original, que puede agrupar varias posiciones. Con el mapeo `source_booking_row_id = "id"`, `record_id` combina `bookId:id` y distingue cada registro. Cuenta códigos distintos para reservas agrupadas; filas para posiciones/tramos; la suma de duración corresponde a horas de recurso reservado. Los tres registros previos del piloto se migran conservando sus versiones originales y sin duplicar operaciones. Si el ID configurado falta o una misma clave trae versiones contradictorias, la extracción se detiene.
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
- **Selección académica:** entre las matrículas de UC, PSG y EDC del ámbito universitario se elige la fecha de matrícula más reciente, anterior o igual a la operación. No se exige matrícula vigente, período actual, estado ACTIVO ni créditos positivos. Una actualización de estado, titulación, fin de estudios o emisión de documentos no constituye una nueva matrícula. No se mezclan atributos ni identificadores de programa entre escuelas.
- **Tipo académico:** el perfil seleccionado se reporta como Egresado si tiene evidencia formal de egreso/aprobación fechada hasta la operación y correspondiente a ese programa, posterior o igual a su última matrícula. En ausencia de esa evidencia se reporta **Estudiante por la regla de reportería acordada**, aunque el programa sea antiguo o haya terminado su plazo previsto. Esta categoría no demuestra matrícula vigente, actividad actual ni asistencia. La ausencia de egreso queda explícita en la auditoría, sin generar por sí sola un pendiente.
- **Atributos:** campus, modalidad, carrera y facultad proceden del programa seleccionado. Los campos faltantes siguen mostrando Pendiente de revisión; no se completan con otra carrera. Las referencias de Continua solo complementan una matrícula real del mismo programa, período y campus cuando sus claves están disponibles. Una referencia comercial sin matrícula no sustituye el estudio seleccionado.
- **Instituto:** el ámbito IC permanece separado. Como la fuente recibida no expone una fecha de matrícula equivalente, se utiliza el inicio de sección más reciente como referencia explícita (`section_start_reference`), no su fin ni la emisión del certificado. Certificado de egresado con estado **1 (emitido/aprobado)**, del mismo programa y fecha aplicable, permite Egresado; sin esa evidencia se aplica Estudiante. Una sección de un programa posterior no hereda el egreso de otro.
- **Empates y fechas faltantes:** si hay programas con la misma última fecha, se conservan atributos comunes y se señalan los ambiguos; tipos incompatibles quedan pendientes. Una matrícula sin fecha no desplaza por suposición a otra fechada. Sin matrícula fechada, un egreso formal puede conservarse como perfil parcial con la fecha de matrícula pendiente; la identidad o un estado comercial por sí solos no bastan para asignar Estudiante.
- **Períodos:** según la equivalencia proporcionada, enero–febrero = `00`, marzo–julio = `10`, agosto–diciembre = `20`, con el año correspondiente (octubre de 2026 → `202620`). Este calendario no bloquea la extracción ni la selección por última matrícula. La configuración `institutional.university_period_by_date` se conserva para la evidencia de programación docente; no se necesita ampliarla día por día para clasificar estudiantes.
- **Evidencia de egreso:** para UC se conservan fechas formales y estados fechados EGRESADO/BACHILLER/TITULADO; para IC, el certificado aprobado. Posgrado y Continua todavía no tienen reglas de egreso validadas con las fuentes recibidas: una fecha de fin prevista, emisión, indicador activo o estado comercial no equivale a aprobación y no se interpreta con el catálogo de UC. Se aplica el valor Estudiante acordado cuando existe matrícula seleccionable sin egreso comprobado.
- Docente precede a Administrativo con evidencia docente vigente; incluye JEFE DE PRACTICA. ES_DOCENTE por sí solo no demuestra vigencia. FECHA_TERMINO no se usa como retiro; se contrasta ingreso y FECHA_RETIRO.
- Los códigos laborales no se convierten en campus sin equivalencias confirmadas en `[institutional.labor_campuses]`. En `[institutional.labor_business_units]` están confirmados UCCI → Universidad Continental e IESC → Instituto Continental.
- Las cuentas de servicios se agregan por correo exacto en `[reporting].service_accounts`. Se reportan como Administrativo y campus Virtual, sin atributos de persona. No cambia el campus de la operación.

### Completar campus laborales

El campus laboral se configura en `[institutional.labor_campuses]` mediante claves `division:sucursal`. La institución debe confirmar el nombre correspondiente; no se equiparan automáticamente esos códigos con `dbo.DIM_CAMPUS` ni con el campus de una reserva/préstamo.

`sql/institutional/10_ubicaciones_y_calendarios.sql` permite investigar sucursales y posibles fuentes de ubicaciones/calendarios. Se ejecuta una sola vez por revisión de fuentes, sin parámetros, y sus dos resultados se exportan con encabezados a `data/referencias/usuarios/actual/`. Los códigos de sucursal sin nombres no bastan para asignar un campus.

La fecha del préstamo o reserva limita qué matrículas y pruebas de egreso son aplicables. El calendario ya no es un requisito para seleccionar el perfil académico. Las fechas de carga de datos no se usan como fechas de matrícula.

### Fechas académicas y trazabilidad

La comprobación de las fuentes disponibles mantiene separados fin de estudios, fin de sección y emisión de documentos. La fecha usada para ordenar perfiles es la última matrícula disponible; en IC se identifica expresamente la referencia de inicio de sección. En UC, `study_end` conserva el valor de `DIM_ESTUDIANTE.FEC_FIN_ESTUDIO`; haber comprobado ese valor no confirma que su definición institucional equivalga a egreso ni a última matrícula. `graduation_date` procede de `FEC_EGRESO`, mientras que `enrollment_date` procede de `FCT_MATRICULA.ID_FECHA_MATRICULA` resuelto con `DIM_TIEMPO`. Se conservan separados y el rol Egresado exige evidencia fechada de egreso/grado. En los casos revisados, Posgrado tiene claves de inicio/fin en 0 y las fuentes consultadas de Continua no exponen un fin académico. Sin egreso comprobado del programa seleccionado se utiliza Estudiante por la regla acordada; no se afirma que continúe cursándolo.

Una clave 0 significa no proporcionada; una clave real sin correspondencia significa una relación de fecha pendiente. Los catálogos candidatos no se unen por parecido de códigos. La consulta `sql/institutional/12_fechas_fin_programas.sql` queda disponible para revisar fuentes si cambian la base o los casos. Su versión preparada y sus resultados son privados y diagnósticos: no se importan mediante `import-users`.

Para el lote de operaciones, `usuarios_revision.csv` incluye `selected_academic_date`, `selected_academic_date_basis`, `academic_selection_policy`, `academic_sources` y `academic_classification_basis`. La política es `latest_enrollment`; `student_without_dated_graduation` identifica la clasificación acordada sin prueba de egreso y `dated_graduation` identifica el egreso respaldado. La selección se conserva en SQLite bajo `academic_selection`, junto con los estados originales en `academic_evidence`. Los diagnósticos privados anteriores no sustituyen estos reportes actualizados.

### Preparar otro lote

Este es el recorrido de la prueba del **14/10/2026**. Cambia las fechas y la carpeta para otro lote. Los dos comandos `sync` ya se ejecutaron; no necesitas repetirlos para continuar con SSMS.

**1. En el equipo de desarrollo: extraer y preparar los correos.** Ejecuta los comandos uno después de otro, no simultáneamente:

```bash
.venv/bin/python -m alma_libcal sync --only prestamos renovaciones --from 2026-10-12 --to 2026-10-12 --extract-only
.venv/bin/python -m alma_libcal sync --only reservas --from 2026-10-14 --to 2026-10-14 --extract-only
.venv/bin/python scripts/prepare_institutional_check.py --output data/referencias/usuarios/prueba_2026-10-14/08_validar_lote_preparado.sql
```

Las operaciones quedan en `data/pilot.sqlite3`. El SQL preparado contiene los correos y fechas: no tienes que introducir DNI ni repetir la consulta por usuario. Incluye todo el histórico guardado, porque el importador actual valida el lote completo.

**2. En el equipo institucional con VPN: comprobar identidades.** Copia únicamente `08_validar_lote_preparado.sql` a una carpeta local, por ejemplo `Documentos\alma-libcal\`. Abre SSMS, conéctate como habitualmente mediante Windows y selecciona la misma base de datos usada en las pruebas anteriores. Abre el archivo preparado y ejecútalo completo una vez. Guarda la única cuadrícula como `08_validacion_lote.csv`, con encabezados. En SSMS, habilita «Incluir encabezados de columna al copiar o guardar resultados» en Herramientas → Opciones → Resultados de consultas → SQL Server → Resultados a cuadrícula; abre otra consulta si la opción no se aplica a la actual. Comprueba que la primera línea incluye `request_id` y `source_email`.

**3. De vuelta en desarrollo: revisar el resultado 08.** Guarda ese CSV en `data/referencias/usuarios/prueba_2026-10-14/`. Este es el siguiente archivo que debes entregar durante el piloto. Tras revisar identidad y ámbito, se genera `08_validacion_lote_revisada.csv`: conserva las columnas originales y añade `review_status`. `ready_for_profile` se reserva para identidad única y ámbito respaldado; las cuentas de servicios y excepciones quedan identificadas para revisión, sin inventar personas. No copies el archivo revisado del lote antiguo: las solicitudes y sus IDs pueden haber cambiado.

**4. En desarrollo: preparar los perfiles, después de revisar 08.**

```bash
.venv/bin/python scripts/prepare_institutional_profiles.py --review data/referencias/usuarios/prueba_2026-10-14/08_validacion_lote_revisada.csv --output data/referencias/usuarios/prueba_2026-10-14/09_extraer_perfiles_preparado.sql
```

**5. En el equipo institucional:** copia el SQL 09 preparado, ejecútalo completo una vez en SSMS y guarda la única cuadrícula con encabezados como `09_perfiles_lote.csv`. Copia el CSV de vuelta a `data/referencias/usuarios/prueba_2026-10-14/`. No abras y vuelvas a guardar este archivo en Excel: contiene JSON que debe conservarse completo. Si aparece JSON cortado o no válido, hay que corregir la exportación antes de importar.

**6. En desarrollo: importar, revisar y publicar.**

```bash
.venv/bin/python -m alma_libcal import-users data/referencias/usuarios/prueba_2026-10-14/09_perfiles_lote.csv --review data/referencias/usuarios/prueba_2026-10-14/08_validacion_lote_revisada.csv
.venv/bin/python -m alma_libcal publish --only prestamos
.venv/bin/python -m alma_libcal publish --only renovaciones
.venv/bin/python -m alma_libcal publish --only reservas
.venv/bin/python -m alma_libcal status
```

Entre importar y publicar, revisa los CSV actualizados de `data/reportes/`, especialmente `usuarios_revision.csv`. Puedes publicar antes del cruce para inspeccionar las operaciones: los nuevos usuarios mostrarán `pending_review`, salvo las cuentas de servicios configuradas. Después de importar, vuelve a publicar para incorporar los perfiles. No ejecutes nuevas extracciones entre preparar 08 e importar 09: si cambian las solicitudes, debes preparar el lote nuevamente. Los CSV preliminares de esta prueba están en `data/reportes/prueba_2026-10-14/`; son una copia anterior al nuevo cruce, no se actualizan automáticamente.

En esta prueba, los tres reportes juntos superan el límite local de 1,8 MB: por eso se publican uno por uno. Cada pestaña conserva su reemplazo atómico; las tres publicaciones separadas no forman una única transacción. Si una pestaña falla, consulta `status` y reintenta solo esa. Si un reporte individual supera el límite, habrá que ampliar el publicador antes de continuar; no borres el histórico para hacerlo caber.

Las consultas `00`–`07` de `sql/institutional/` sirven para investigar excepciones; no se repiten para cada extracción. Los SQL preparados y CSV personales se guardan exclusivamente bajo `data/`, excluido de Git.

### Opciones para reducir el paso manual

Por ahora, **SSMS y dos intercambios de archivos** permiten validar el flujo sin instalar Python ni WSL en el equipo institucional. La siguiente opción es un script de **PowerShell** en ese equipo: ejecutaría el SQL y exportaría CSV usando la sesión de Windows autorizada. Requerirá confirmar servidor, base de datos, herramientas disponibles y exportación sin truncar el JSON; no necesitas compartir contraseñas. El módulo oficial [SqlServer e Invoke-Sqlcmd](https://learn.microsoft.com/en-us/powershell/module/sqlserver/invoke-sqlcmd) es una alternativa para implementarlo. El script aún no existe.

Después podría ejecutarse con el Programador de tareas de Windows, bajo una cuenta con acceso autorizado y con VPN disponible. Automatizar la exportación no resuelve por sí solo la revisión de identidades ni el traslado de archivos: ambos deben definirse antes de programar el flujo completo. La conexión directa desde un proceso con acceso a la red institucional sería una tercera opción, cuando ese acceso esté disponible.

## Histórico de LibCal y próximos pasos

`/space/bookings` ignora fechas pasadas. `/space/bookings/updates` recupera cambios recientes de las últimas 24 horas, incluidos cambios de reservas antiguas; no reconstruye meses de histórico. La consulta por ID conocido devolvió una reserva del 2 de octubre durante esta prueba. Puede complementar registros antiguos, pero requiere sus IDs; la especificación excluye canceladas y no proporciona un listado histórico completo.

Antes de producción debemos preparar una carga inicial desde una exportación administrativa con IDs, fechas/horas completas, recursos, estados, asistencia y respuestas. Su importador y la consulta histórica por ID todavía no están implementados. Luego necesitaremos capturar cambios con frecuencia suficiente para conservar cancelaciones y asistencias posteriores; una consulta semanal aislada no cubre la ventana de 24 horas.

El orden siguiente es: revisar el cruce del piloto, completar equivalencias y revisar casos pendientes, preparar el acceso institucional en modo lectura, implementar publicación por lotes antes de ampliar el volumen, completar el histórico de LibCal y programar jobs con recuperación de fallos.

La publicación actual sustituye las tablas seleccionadas en una petición atómica y tiene un límite local de 1,8 MB. No compara filas nuevas/modificadas en Sheets. Para cargas grandes primero debe ampliarse el publicador.

## Código y verificación

Código en `src/alma_libcal/`, pruebas automatizadas en `tests/` y fixtures ficticios en `src/alma_libcal/fixtures/`. Estas pruebas son parte del proyecto; los resultados temporales se eliminan al terminar.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```
