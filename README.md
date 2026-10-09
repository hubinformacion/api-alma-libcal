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

## Salida compacta de Sheets

`[reporting].sheet_layout = "compact"` publica solo la información de reportería: ahora 21 columnas para préstamos, 23 para renovaciones y 28 para reservas. Se conserva `record_id`; en renovaciones se conserva también `loan_id`. Se omiten columnas técnicas duplicadas, como loan_channel, códigos de material, versiones y marcas de auditoría. Meses y horas derivadas no forman parte del esquema compacto; fechas y timestamps base permiten calcularlos.

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
- **Usuarios:** claves originales y nombres manuales se conservan como `source_user_*`. El correo puede aportar una clave candidata anterior a @. Los atributos verificados quedan pendientes del cruce universitario a la fecha de operación; los usos internos sin usuario no requieren ese cruce.
- **Meses y horas:** se calculan al exportar, sin duplicarlos en SQLite. Para omitir esas columnas en Sheets y utilizar un calendario de Power BI, cambia `[reporting].include_date_parts = false`.

Los archivos de `data/` son locales, contienen información personal y no se publican en GitHub. Los CSV de esta prueba están en **`data/reportes/`**, uno por conjunto y fecha. Son copias de ese momento: `sync` no los actualiza automáticamente. Las referencias aportadas para diseño se conservan localmente en `data/referencias/`; la especificación de API y la arquitectura institucional están en `data/referencias/technical/`, fuera del repositorio publicado.

## Piloto institucional mediante SQL Management Studio

Los archivos de **`sql/institutional/`** contienen consultas de lectura preparadas con la arquitectura recibida. Todavía deben ejecutarse en tu base; aquí no hay conexión a ese servidor. No requieren instalar Python ni WSL en el equipo institucional.

1. Selecciona la base institucional en SSMS y ejecuta **00_metadatos.sql** para confirmar objetos, columnas y claves. Guarda cada cuadrícula con encabezados según el nombre indicado en sus comentarios.
2. En **01_identificar_persona.sql**, sustituye los NULL del encabezado por `N'valor'` para correo, documento o identificador de UN caso. El identificador es source_user_id, no record_id ni loan_id. Ejecuta el archivo completo, no un SELECT aislado. Todos los candidatos se conservan: más de un resultado requiere revisión.
3. Copia ID_PERSONA del resultado a **02_roles_persona.sql** y **03_matriculas_persona.sql**, y conserva como fecha de operación el 6 o 7 de octubre para este piloto. El ID_PERSONA no es el DNI. Exporta sus cuadrículas con los nombres indicados y un sufijo de caso.
4. Ejecuta **04_catalogos.sql** una vez para obtener códigos de período, campus, modalidad y estados.
5. Guarda los CSV originales en **`data/referencias/usuarios/`**. Incluye encabezados y conserva documentos/códigos como texto; no pases por una conversión numérica de Excel. Una cuadrícula vacía puede indicarse como “sin filas”, sin generar otro archivo.

Primera entrega sugerida: tu caso con correo estudiantil antiguo, correo basado en DNI y cuenta laboral. Después agrega casos de intercambio TM, instituto i, docente, dos carreras y cambio de campus. Para cada caso necesitamos una nota de qué resultado esperas y en qué fecha; no se requieren contraseñas, direcciones, fechas de nacimiento ni datos ajenos al perfil de reportería.

También necesitaremos el calendario académico: ID/código de período, fecha de inicio y fin, y el significado de estados de matrícula, ESTADO_ACTIVO, ES_DOCENTE y fechas de ingreso/retiro/término. Las claves ID_FECHA no se tratarán como fechas hasta confirmar su formato. FEC_ACTUALIZACION es actualización/carga, no vigencia académica.

El correo exacto será el primer criterio, contrastado con los registros institucionales. El documento y los códigos estudiantiles respaldarán la identificación y los cambios de correo; no se reconstruyen cuentas docentes desde sus iniciales. Para una cuenta laboral con roles vigentes, la prioridad acordada es docente sobre administrativo. Una cuenta académica se resolverá con sus registros académicos, no solo por el formato de su correo.

Elegiremos la matrícula más reciente aplicable a la fecha de operación, con estados y vigencias confirmados; no simplemente el mayor ID de período o la última carga. Si dos carreras siguen vigentes y no existe un criterio confirmado, se conservará la ambigüedad sin duplicar la operación ni elegir arbitrariamente un perfil. La integración automática todavía no está implementada: este piloto define esas reglas con datos reales.

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

### Segunda comprobación del piloto institucional

Los primeros CSV llegaron sin encabezados: se reconstruyeron copias locales en `data/referencias/usuarios/normalizados/`, conservando los originales. Los TXT vacíos indican que la consulta no devolvió filas; no demuestran por sí solos que la persona no tenga el rol.

Repite `01_identificar_persona.sql` por cada cuenta con correo completo. El campo identificador es un código sin dominio; si se introduce un correo allí, la consulta extrae su parte anterior a @ y avisa en Mensajes. Un dominio incompleto genera advertencia, nunca se completa por suposición.

Ejecuta `05_fechas_y_periodos.sql` con el ID_PERSONA del caso para resolver ID_FECHA usando `dbo.DIM_TIEMPO.DES_TIEMPO`, comprobar períodos y buscar un calendario real. La consulta incluye una muestra de horarios docentes, con sus fechas de texto originales, para validar el formato. Exporta las cuadrículas con los nombres indicados en sus comentarios.

Si los horarios docentes no devuelven filas o hay referencias tanto en EDC como en PSG, ejecuta `06_completar_perfiles.sql` con el mismo ID_PERSONA. Sus tres resultados muestran el perfil de Continua, los nombres del programa de Posgrado y semanas de docencia de otra fuente. Una fecha de emisión no se interpreta como egreso; una referencia de programa no demuestra matrícula vigente. Guarda las cuadrículas con encabezados en la carpeta local de referencias, siguiendo los nombres de sus comentarios.

Para reportería, JEFE DE PRACTICA se considera Docente y tiene prioridad sobre Administrativo cuando la asignación corresponde a la fecha de operación. ES_DOCENTE de nómina no es prueba única de docencia. FECHA_TERMINO tampoco se trata como baja laboral sin validar su significado y las renovaciones/contratos indefinidos; debe contrastarse con FECHA_RETIRO y la fuente laboral.

El piloto prioriza las cuentas institucionales actuales; las equivalencias de correos antiguos se resolverán después. `04_catalogos.sql` incluye tipos de estudiante y estados del funnel de Continua. Estos últimos no se interpretan automáticamente como estados de egreso. `03_matriculas_persona.sql` conserva también el tipo de estudiante de la fuente junto al estado académico; ninguna categoría se deduce solo del correo.

Para comprobar que el cruce funciona cuando Alma/LibCal aportan solo correo, usa `07_validar_cuentas.sql` con un documento de referencia y los correos conocidos de instituto, universidad y trabajo de una misma persona. Ejecútalo una vez. El primer resultado busca candidatos sin usar ese documento como filtro y después compara lo encontrado con la referencia; `unmatched` indica un vínculo pendiente. Los demás resultados muestran identificadores de instituto y fuentes accesibles de cuentas. Exporta las tres cuadrículas con los nombres de sus comentarios. Los métodos `candidate` deben validarse antes de automatizarse. Si falta la relación correo/código/persona de instituto o intercambio, necesitaremos una exportación o vista institucional de cuentas; no se deduce desde nombres ni se elimina la operación sin coincidencia.

Las últimas filas de FCT_MATRICULA pueden reflejar egreso o titulación sin una nueva matrícula. No basta con seleccionar el máximo período. Una referencia en DIM_ESTUDIANTE de PSG sin filas de matrícula no prueba matrícula vigente. Estas comprobaciones siguen pendientes de validación antes de automatizar el cruce; no se han enriquecido los reportes con una regla provisional.
