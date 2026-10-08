# 02 — LibCal: contar, guardar y comparar

Las credenciales, ubicaciones, formularios y 14 categorías ya están configurados. No necesitas buscar IDs ni crear otra aplicación.

## 1. Consultar cantidades sin guardar reservas

Para Espacios grupales de Cusco, hoy:

```bash
.venv/bin/python -m alma_libcal check-libcal --location 20114 --category 42372
```

La salida muestra `rows` (reservas), `statuses` (cantidades por estado) y la fecha consultada. `pages` cuenta consultas paginadas, no reservas. Este comando no guarda filas en SQLite ni las envía a Sheets.

Para computadoras de Los Olivos:

```bash
.venv/bin/python -m alma_libcal check-libcal --location 20115 --category 42375
```

Omitir `--category` consulta todas las categorías de ese campus.

## 2. Guardar registros reales

Para el 8 de octubre de 2026:

```bash
.venv/bin/python -m alma_libcal sync --only reservas --from 2026-10-08 --to 2026-10-08 --extract-only
```

**Cambia ambas fechas por el día actual si ejecutas esto otro día.** El endpoint usado no permite consultar fechas pasadas. El comando guarda en `data/pilot.sqlite3` las reservas de las categorías configuradas de los seis campus. Para abrirlas, sigue [03 — Ver los datos](03-ver-datos.md).

## 3. Comparar con el reporte administrativo

En el reporte/exportación de LibCal usa la misma fecha de **inicio de la reserva**, campus y categoría. Incluye todos los estados, especialmente cancelaciones. Usa hora local de Perú.

Compara el total de reservas y los subtotales por estado. Una reserva grupal cuenta una vez; los correos de integrantes 2 y 3 no representan otras reservas. Si exportas varias franjas por reserva, revisa el ID de reserva antes de contar filas.

Para revisar registros individuales compara ID (`record_id`, procedente de `bookId`), inicio/fin, recurso, campus, estado y correo del solicitante. Los correos de integrantes están en `booking_form_answer_1` y `booking_form_answer_2`; los puestos de computadoras, cuando existen, en `seat_id` y `seat_name`. El formulario 0 de Los Olivos no requiere modificaciones.

| Campus | Ubicación | Computadoras/laptops | Espacios grupales | Kindle |
| --- | --- | --- | --- | --- |
| Instituto | 20116 | 42378 | 42377 | — |
| Huancayo | 20109 | 42358 | 42357 | 53609 |
| Arequipa | 20110 | 42369 | 42368 | — |
| Cusco | 20114 | 42373 | 42372 | 53604 |
| Los Olivos | 20115 | 42375 | 42374 | — |
| Ica | 23350 | 49252 | 49251 | — |

Los conteos anteriores del 7 de octubre (Cusco: 66; Los Olivos: 125) correspondían a pruebas de ese día, no a la extracción de hoy. Las reservas pueden cambiar de estado durante el día; compara consultas próximas en el tiempo.

## Pendientes posteriores

Faltan cálculos de mes/hora/duración y aclarar cuenta/confirmación. Los datos académicos vendrán de la universidad. Para históricos necesitamos una exportación u otra fuente: `/space/bookings` ignora fechas pasadas y `/space/bookings/updates` solo cubre las últimas 24 horas. Estas restricciones también condicionan la futura programación diaria o semanal.
