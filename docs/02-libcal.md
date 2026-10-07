# 02 — LibCal: categorías y reservas pendientes

La autenticación y lectura de ubicaciones ya funcionaron. Las rutas, paginación y opciones de consulta están configuradas a partir de [1_1.yml](1_1.yml). No necesitas registrar otra aplicación ni volver a introducir credenciales.

Los `cid` de categorías siguen siendo ejemplos en `config.toml`. Primero necesitamos los valores reales. Ejecuta los comandos desde la carpeta del proyecto.

| Campus | ID de ubicación (lid) |
| --- | --- |
| Instituto | 20116 |
| Huancayo | 20109 |
| Arequipa | 20110 |
| Cusco | 20114 |
| Los Olivos | 20115 |
| Ica | 23350 |

## 1. Obtener categorías, sin buscar IDs a mano

Para Cusco:

```bash
.venv/bin/python -m alma_libcal discover-libcal --locations 20114
```

Para todos tus campus:

```bash
.venv/bin/python -m alma_libcal discover-libcal --locations 20116 20109 20110 20114 20115 23350
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

## 2. Recursos y formularios

Con un `cid` real, consulta sus recursos:

```bash
.venv/bin/python -m alma_libcal discover-libcal --category 12345
```

Sustituye `12345` por tu `cid`. Consulta `/1.1/space/category/{cid}` con detalles y muestra `items`: cada recurso tiene `id` y `name`. No necesitas copiar todos los recursos al TOML para extraer una categoría completa.

Si necesitas las preguntas de un formulario, usa su `formid`. Por ejemplo, el ID que recibiste para Los Olivos/Ica:

```bash
.venv/bin/python -m alma_libcal discover-libcal --form 8254
```

Consulta `/1.1/space/form/{formid}`. En `fields`, las preguntas personalizadas se identifican como `q43`, `q44`, etc.; estos números son ejemplos. Verifica sus etiquetas antes de decidir qué corresponde a `booking_form_answer_1` y `booking_form_answer_2`. Los formularios pueden variar entre categorías o recursos.

## 3. Probar reservas sin mostrar usuarios

Para validar lectura de reservas en Cusco **hoy**:

```bash
.venv/bin/python -m alma_libcal check-libcal --location 20114
```

Para una categoría concreta:

```bash
.venv/bin/python -m alma_libcal check-libcal --location 20114 --category 12345
```

Sustituye `12345` por el `cid` real. No necesitas completar todos los grupos del TOML para esta prueba. Puedes elegir hoy o una fecha futura con `--date YYYY-MM-DD`.

El comando consulta todas las páginas y muestra `authentication`, número de filas, conteos por estado/campus y nombres de campos. **No imprime nombres, correos, respuestas de usuarios ni tokens; no publica ni guarda reservas.** Una respuesta vacía con autenticación correcta solo demuestra que no llegaron reservas para ese filtro.

## 4. Resolver campos e histórico

Con los nombres de campos de la prueba y las preguntas del formulario, debemos confirmar:

- Qué preguntas corresponden a `booking_form_answer_1` y `booking_form_answer_2`, por categoría/recurso.
- Si hay un identificador institucional real; hasta entonces `user_id` permanece vacío.
- Qué significa `booking_confirmation` en tu reporte.
- Si `account` contiene un correo: el YAML no lo define como tal.

Después ampliaremos el programa para guardar correo y respuestas; actualmente no conserva todos los campos finales. Los datos académicos y de identidad vendrán de la universidad.

Según la especificación, `/space/bookings` ignora fechas pasadas. Prueba hoy o una fecha futura, no ayer. `/space/bookings/updates` solo cubre cambios de las últimas 24 horas. Para el histórico debemos elegir una exportación administrativa u otra fuente que Springshare confirme; la futura programación debe considerar ese límite.

Termina este paso cuando estén configurados los cid reales y los conteos de reservas coincidan con el reporte administrativo por campus/categoría/estado. Continúa con [03 — Completar extracción y validar publicación](03-programa-y-sheets.md).
