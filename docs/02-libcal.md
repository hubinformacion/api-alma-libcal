# 02 — LibCal: categorías y reservas pendientes

La autenticación y lectura de ubicaciones ya funcionaron. Las rutas, paginación y opciones de consulta están configuradas a partir de [1_1.yml](1_1.yml). No necesitas registrar otra aplicación ni volver a introducir credenciales.

Las 14 categorías de los seis campus ya están configuradas en `config.toml`, junto con su ubicación, nombre original y formulario reportado. La consulta filtra por campus (`lid`) y categoría (`cid`).

## 1. Categorías confirmadas

| Campus | lid | Computadoras / laptops | Espacios grupales | Kindle |
| --- | --- | --- | --- | --- |
| Instituto | 20116 | 42378 | 42377 | — |
| Huancayo | 20109 | 42358 | 42357 | 53609 |
| Arequipa | 20110 | 42369 | 42368 | — |
| Cusco | 20114 | 42373 | 42372 | 53604 |
| Los Olivos | 20115 | 42375 | 42374 | — |
| Ica | 23350 | 49252 | 49251 | — |

Los nombres Computadoras y Computadoras y Laptops se agrupan como **Computadoras y laptops** en el reporte. `source_name` conserva la denominación original en la configuración; `location_id` es el campus y `id` es la categoría. Kindle solo aparece en Huancayo y Cusco en la respuesta recibida.

No necesitas volver a buscar ni introducir estos IDs. Los campos `location_name`, `source_name` y `form_id` del TOML conservan metadatos para la ampliación; el extractor básico todavía no exporta todos ellos.

## 2. Recursos y formularios

Consulta los recursos de Espacios grupales de Cusco:

```bash
.venv/bin/python -m alma_libcal discover-libcal --category 42372
```

Consulta `/1.1/space/category/{cid}` con detalles y muestra `items`: cada recurso tiene `id` y `name`. No necesitas copiar todos los recursos al TOML para extraer una categoría completa.

Los espacios grupales usan el formulario **8253**; computadoras y Kindle informan **8254**, salvo computadoras de Los Olivos, que devuelve **formid = 0**. Consulta ambos formularios:

```bash
.venv/bin/python -m alma_libcal discover-libcal --form 8253
.venv/bin/python -m alma_libcal discover-libcal --form 8254
```

Para Los Olivos, revisa los recursos con `discover-libcal --category 42375` y su posible `formid`. El valor 0 en la categoría no demuestra que las reservas carezcan de preguntas; no lo consultes como un formulario válido.

Consulta `/1.1/space/form/{formid}`. En `fields`, las preguntas personalizadas se identifican como `q43`, `q44`, etc.; estos números son ejemplos. Verifica sus etiquetas antes de decidir qué corresponde a `booking_form_answer_1` y `booking_form_answer_2`. Los formularios pueden variar entre categorías o recursos.

## 3. Probar reservas sin mostrar usuarios

Para validar lectura de reservas en Cusco **hoy**:

```bash
.venv/bin/python -m alma_libcal check-libcal --location 20114
```

Para una categoría concreta:

```bash
.venv/bin/python -m alma_libcal check-libcal --location 20114 --category 42372
```

La categoría 42372 corresponde a Espacios grupales de Cusco. Para los demás campus usa los IDs de la tabla. Puedes elegir hoy o una fecha futura con `--date YYYY-MM-DD`.

El comando consulta todas las páginas y muestra `authentication`, número de filas, conteos por estado/campus y nombres de campos. **No imprime nombres, correos, respuestas de usuarios ni tokens; no publica ni guarda reservas.** Una respuesta vacía con autenticación correcta solo demuestra que no llegaron reservas para ese filtro.

## 4. Resolver campos e histórico

Con los nombres de campos de la prueba y las preguntas del formulario, debemos confirmar:

- Qué preguntas corresponden a `booking_form_answer_1` y `booking_form_answer_2`, por categoría/recurso.
- Si hay un identificador institucional real; hasta entonces `user_id` permanece vacío.
- Qué significa `booking_confirmation` en tu reporte.
- Si `account` contiene un correo: el YAML no lo define como tal.

Después ampliaremos el programa para guardar correo y respuestas; actualmente no conserva todos los campos finales. Los datos académicos y de identidad vendrán de la universidad.

Según la especificación, `/space/bookings` ignora fechas pasadas. Prueba hoy o una fecha futura, no ayer. `/space/bookings/updates` solo cubre cambios de las últimas 24 horas. Para el histórico debemos elegir una exportación administrativa u otra fuente que Springshare confirme; la futura programación debe considerar ese límite.

Termina este paso cuando estén identificadas las preguntas y los conteos de reservas coincidan con el reporte administrativo por campus/categoría/estado. Continúa con [03 — Completar extracción y validar publicación](03-programa-y-sheets.md).
