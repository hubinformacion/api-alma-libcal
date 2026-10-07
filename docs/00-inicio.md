# 00 — Estado y próximos pasos

## Lo que ya está preparado

- Python 3.12.3 y dependencias locales.
- Credenciales en `.env`, rutas y opciones en `config.toml`.
- Reporte `Loans`: IDs sin duplicados en el día revisado; inspección API con fechas y mapeo básico confirmados.
- Reporte `Renewals`: columnas y mapeo básico confirmados, incluidos cantidad y campus de renovación.
- LibCal: ubicaciones y 14 categorías de los seis campus configuradas, con IDs y formularios de referencia.
- Formularios LibCal: asignación de correos de integrantes 2 y 3 confirmada e implementada; reservas de Los Olivos verificadas aunque categoría y recurso informen formulario 0.
- Prueba de salas de Cusco del 7 de octubre: 66 reservas, 65 confirmadas y una cancelada por administrador.
- Los Olivos: prueba directa del 7 de octubre con 125 reservas, 101 confirmadas y 24 canceladas por administrador.
- Almacenamiento de correo original, participantes de salas y puesto reservado (seat_id/seat_name) implementado.
- Google Sheets: configuración completada según tu confirmación.
- Código y guías guardados en Git.

Falta validar Renewals con fechas, comprobar las demás categorías de LibCal y comparar la extracción completa.

## Sigue este orden

| Paso | Qué falta | Dónde hacerlo |
| --- | --- | --- |
| 01 | Validar el filtro de fecha de Renewals y completar el esquema de ambos reportes | [Alma](01-alma.md): Analytics, terminal y `config.toml` |
| 02 | Comparar conteos por campus/categoría/estado y verificar las demás categorías | [LibCal](02-libcal.md): terminal y `config.toml` |
| 03 | Ampliar el extractor, comprobar conteos y publicar una muestra en Google | [Validación y publicación](03-programa-y-sheets.md) |

**El siguiente paso es comparar los conteos de Cusco y Los Olivos con los reportes administrativos y validar las demás categorías, siguiendo 02.** También queda validar el filtro de fecha de Renewals en 01. No recrees claves, reportes ni la autorización de Google.

## Después del piloto

Los reportes de Alma y LibCal permanecen separados. Extraeremos operaciones, recursos, sedes y claves originales para identificar usuarios. Nombre, tipo de usuario, modalidad, campus del usuario, programa, departamento y unidad de negocio vendrán de la universidad.

Los usos internos sin usuario no se cruzan con la base institucional. Un identificador no se asumirá como DNI sin verificarlo. Los CSV de [database/](database/) servirán para elegir uniones y validar vigencia académica en una fase posterior; no necesitamos todavía VPN ni credenciales Windows.

También quedan pendientes la fuente histórica de LibCal y la programación periódica. Su endpoint documentado ignora fechas pasadas y el endpoint de cambios limita la consulta a 24 horas.
