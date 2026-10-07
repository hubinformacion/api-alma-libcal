# 00 — Estado y próximos pasos

## Lo que ya está preparado

- Python 3.12.3 y dependencias locales.
- Credenciales en `.env`, rutas y opciones en `config.toml`.
- Reporte `Loans`: IDs sin duplicados en el día revisado; inspección API con fechas y mapeo básico confirmados.
- Reporte `Renewals`: columnas y mapeo básico confirmados, incluidos cantidad y campus de renovación.
- Acceso a ubicaciones de LibCal: recibimos los seis campus.
- Google Sheets: configuración completada según tu confirmación.
- Código y guías guardados en Git.

Falta validar Renewals con fechas y comparar la extracción completa; los IDs de categorías LibCal todavía son ejemplos.

## Sigue este orden

| Paso | Qué falta | Dónde hacerlo |
| --- | --- | --- |
| 01 | Validar el filtro de fecha de Renewals y completar el esquema de ambos reportes | [Alma](01-alma.md): Analytics, terminal y `config.toml` |
| 02 | Obtener los cid por campus, identificar preguntas y comparar reservas de hoy | [LibCal](02-libcal.md): terminal y `config.toml` |
| 03 | Ampliar el extractor, comprobar conteos y publicar una muestra en Google | [Validación y publicación](03-programa-y-sheets.md) |

**El siguiente paso es obtener los cid de LibCal, siguiendo 02, y validar el filtro de fecha de Renewals en 01.** No recrees claves, reportes ni la autorización de Google.

## Después del piloto

Los reportes de Alma y LibCal permanecen separados. Extraeremos operaciones, recursos, sedes y claves originales para identificar usuarios. Nombre, tipo de usuario, modalidad, campus del usuario, programa, departamento y unidad de negocio vendrán de la universidad.

Los usos internos sin usuario no se cruzan con la base institucional. Un identificador no se asumirá como DNI sin verificarlo. Los CSV de [database/](database/) servirán para elegir uniones y validar vigencia académica en una fase posterior; no necesitamos todavía VPN ni credenciales Windows.

También quedan pendientes la fuente histórica de LibCal y la programación periódica. Su endpoint documentado ignora fechas pasadas y el endpoint de cambios limita la consulta a 24 horas.
