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

## 2. Formularios confirmados; excepción de Los Olivos pendiente

Ambos formularios ya fueron consultados y sus campos quedaron registrados en `[libcal.forms]` del TOML como metadatos de referencia:

| Campo | Pregunta | Formulario 8253 (salas) | Formulario 8254 (computadoras/Kindle) |
| --- | --- | --- | --- |
| `fname`, `lname`, `email` | Nombre, apellido y correo del solicitante | Sí | Sí |
| `q25458` | Número de celular | Sí | Sí |
| `q25459` | Correo del integrante 2 | Sí | No |
| `q25460` | Correo del integrante 3 | Sí | No |
| `q25536` | Términos y Condiciones, opción Acepto | Sí | Sí |

No hay una pregunta de DNI en estos formularios. La persona que reserva se identifica por el correo de la reserva; los correos de integrantes adicionales son campos distintos. Una reserva grupal sigue siendo una operación, aunque participen varias personas.

Falta confirmar qué dos preguntas corresponden a tus columnas `booking_form_answer_1` y `booking_form_answer_2`. Para salas, la propuesta es usar los correos de integrantes 2 y 3; aún no se ha aplicado esa asignación. En computadoras/Kindle esas preguntas no existen: no rellenaremos las mismas columnas con otros significados sin definirlo antes.

Computadoras de Los Olivos devuelve `formid = 0`. Consulta sus recursos para verificar si informan un formulario específico:

```bash
.venv/bin/python -m alma_libcal discover-libcal --category 42375
```

El 0 de la categoría no demuestra que las reservas carezcan de preguntas; no lo consultes como un formulario válido. No hace falta volver a consultar 8253 y 8254.

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

Con las preguntas ya identificadas, queda confirmar en la respuesta de reservas:

- Que llegan `q25459` y `q25460` en salas con `form_answers=1`; definir su asignación a las dos columnas del reporte.
- Si hay un identificador institucional real; hasta entonces `user_id` permanece vacío.
- Qué significa `booking_confirmation` en tu reporte.
- Si `account` contiene un correo: el YAML no lo define como tal.

Después ampliaremos el programa para guardar correo y respuestas; actualmente no conserva todos los campos finales. Los datos académicos y de identidad vendrán de la universidad.

Según la especificación, `/space/bookings` ignora fechas pasadas. Prueba hoy o una fecha futura, no ayer. `/space/bookings/updates` solo cubre cambios de las últimas 24 horas. Para el histórico debemos elegir una exportación administrativa u otra fuente que Springshare confirme; la futura programación debe considerar ese límite.

Termina este paso cuando estén identificadas las preguntas y los conteos de reservas coincidan con el reporte administrativo por campus/categoría/estado. Continúa con [03 — Completar extracción y validar publicación](03-programa-y-sheets.md).
