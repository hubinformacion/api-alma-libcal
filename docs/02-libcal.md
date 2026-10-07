# 02 — LibCal: validar acceso y obtener IDs por campus

La documentación de tu API está en [1_1.yml](1_1.yml). Esta guía usa sus endpoints de **Spaces / Seats**. Alma y LibCal conservarán reportes separados.

## 1. Credenciales: dónde van

**Dónde:** LibCal → **Admin → API → API Authentication / Applications**. Registra una aplicación con lectura de Spaces; conserva su **Client ID** y **Client Secret**.

En la carpeta del proyecto, completa `.env`:

```dotenv
LIBCAL_CLIENT_ID=tu_client_id
LIBCAL_CLIENT_SECRET=tu_client_secret
```

En `config.toml`, conserva la URL y los nombres de variables:

```toml
[libcal]
base_url = "https://continental.libcal.com"
token_path = "/1.1/oauth/token"
bookings_path = "/1.1/space/bookings"
client_id_env = "LIBCAL_CLIENT_ID"
client_secret_env = "LIBCAL_CLIENT_SECRET"
```

Edita las secciones que ya existen; no las dupliques. El programa lee `.env` automáticamente y solicita el token; no necesitas copiar tokens ni ejecutar solicitudes manuales.

## 2. Campus: los IDs que ya obtuviste

**Dónde:** terminal de Ubuntu, dentro del proyecto.

```bash
./run.sh discover-libcal
```

Tu respuesta con ubicaciones demuestra que la autenticación y la lectura de ese endpoint funcionaron. `lid` significa **ID de ubicación/campus**; no es el ID de una categoría.

| Campus | lid |
| --- | --- |
| Instituto | 20116 |
| Huancayo | 20109 |
| Arequipa | 20110 |
| Cusco | 20114 |
| Los Olivos | 20115 |
| Ica | 23350 |

## 3. Obtener categorías, sin buscar IDs a mano

Para Cusco:

```bash
./run.sh discover-libcal --locations 20114
```

Para todos tus campus:

```bash
./run.sh discover-libcal --locations 20116 20109 20110 20114 20115 23350
```

Consulta `GET /1.1/space/categories/{lid}`. En cada campus busca el bloque `categories`: cada entrada tiene `cid` (ID de categoría), `name` y, cuando existe, `formid`. Identifica las categorías correspondientes a **Computadoras y laptops**, **Espacios grupales** y **Kindle**; puede haber más de una por grupo/campus.

**Dónde colocar los IDs:** en los bloques `[[libcal.categories]]` de `config.toml`. Reemplaza los bloques con `REPLACE_...` por una entrada para cada categoría real que quieras incluir. Ejemplo ficticio:

```toml
[[libcal.categories]]
id = "12345"                 # Sustituir por el cid REAL de la respuesta
name = "Espacios grupales"   # Grupo del reporte
location_id = "20114"        # lid de Cusco

[[libcal.categories]]
id = "67890"                 # Otro cid REAL, por ejemplo de Huancayo
name = "Espacios grupales"
location_id = "20109"
```

Los dos `cid` anteriores son ejemplos, no datos de tu cuenta. Puedes repetir un grupo en distintos campus. `name` usa uno de los tres grupos del piloto; el nombre original de la categoría puede ser distinto. No uses un `lid` como `id` de categoría.

## 4. Recursos y formularios

Con un `cid` real, consulta sus recursos:

```bash
./run.sh discover-libcal --category 12345
```

Sustituye `12345` por tu `cid`. Consulta `/1.1/space/category/{cid}` con detalles y muestra `items`: cada recurso tiene `id` y `name`. No necesitas copiar todos los recursos al TOML para extraer una categoría completa.

Si necesitas las preguntas de un formulario, usa su `formid`. Por ejemplo, el ID que recibiste para Los Olivos/Ica:

```bash
./run.sh discover-libcal --form 8254
```

Consulta `/1.1/space/form/{formid}`. En `fields`, las preguntas personalizadas se identifican como `q43`, `q44`, etc.; estos números son ejemplos. Verifica sus etiquetas antes de decidir qué corresponde a `booking_form_answer_1` y `booking_form_answer_2`. Los formularios pueden variar entre categorías o recursos.

## 5. Probar reservas sin mostrar usuarios

Para validar lectura de reservas en Cusco **hoy**:

```bash
./run.sh check-libcal --location 20114
```

Para una categoría concreta:

```bash
./run.sh check-libcal --location 20114 --category 12345
```

Sustituye `12345` por el `cid` real. No necesitas completar todos los grupos del TOML para esta prueba. Puedes elegir hoy o una fecha futura con `--date YYYY-MM-DD`.

El comando consulta todas las páginas y muestra `authentication`, número de filas, conteos por estado/campus y nombres de campos. **No imprime nombres, correos, respuestas de usuarios ni tokens; no publica ni guarda reservas.** Una respuesta vacía con autenticación correcta solo demuestra que no llegaron reservas para ese filtro.

## 6. Parámetros que ya confirmamos en el YAML

En `config.toml`, utiliza:

```toml
[libcal]
# Conservar aquí las otras opciones de libcal; no duplicar la sección.
pagination = "page"
page_start = 1
page_size = 100
response_path = ""

[libcal.query]
date = "{date}"
days = "{days}"
cid = "{category_id}"
limit = "{limit}"
page = "{page}"
form_answers = 1
include_cancel = 1
include_tentative = 1
include_denied = 1
```

Elimina `offset`: esta operación documenta `page`. `days=0` solicita el día inicial; el programa calcula este valor para cada ventana. No pedimos notas internas.

Los campos documentados son `bookId`, `eid`, `cid`, `lid`, `fromDate`, `toDate`, `email`, `account`, `status`, `location_name`, `category_name`, `item_name` y respuestas `qNN`. En `[libcal.fields]`, usa `resource_name = "item_name"`, `site = "location_name"`, `site_id = "lid"` y `category_id = "cid"`. `check_in_status` es un estado, no una fecha de check-in.

Mantén `user_id = ""` hasta verificar un identificador institucional real. `account` no está documentado como correo; tampoco trataremos `check_in_code` como equivalente de tu `booking_confirmation` sin confirmar su significado.

El programa aún debe ampliarse para almacenar el correo y respuestas del formulario en el reporte final. El comando de prueba permite confirmar que esos campos llegan antes de hacer esa ampliación. El campus de la reserva se obtiene de `lid`/`location_name`; los atributos del usuario vendrán de la universidad.

## 7. Límite importante para el histórico

Según [la especificación recibida](1_1.yml), `/space/bookings` **ignora fechas pasadas**. Por eso el programa rechaza una extracción retrospectiva con esa operación, en lugar de confundir reservas actuales con las de otro día.

`/space/bookings/updates` solo consulta cambios de las últimas 24 horas. Esto tampoco resuelve una carga retrospectiva de varios meses ni permite esperar una semana para recuperar todos los cambios.

Para el histórico evaluaremos una exportación administrativa o una operación que Springshare confirme que lo permite. Para la futura automatización debemos recoger datos con suficiente frecuencia y conservarlos localmente. La estrategia diaria/semanal se decidirá después de validar esta limitación; todavía no está implementada.

Cuando las categorías y los conteos estén comprobados, continúa con [03 — Programa y Google Sheets](03-programa-y-sheets.md).
