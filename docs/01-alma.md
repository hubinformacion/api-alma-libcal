# 01 — Alma: ajustes y validación pendientes

Ya tienes Loans y comprobaste que `loan_id` no se repite en el día revisado. Las rutas están introducidas en `config.toml`; no recrees el análisis ni la clave.

## 1. Loans: consulta y mapeo confirmados

La inspección con fechas devolvió las columnas del reporte. No hace falta repetir el diagnóstico HTTP 500. Se actualizó `[alma.prestamos.fields]` de `config.toml` con este mapa:

| Campo | Columna API |
| --- | --- |
| ID del préstamo | Column12 |
| Fecha | Column8 |
| Identificador original del usuario | Column1 |
| ID del ejemplar | Column11 |
| Título | Column17 |
| Campus / código de campus | Column3 / Column2 |
| Estado | Column13 |
| Indicador de uso interno | Column10 |

`Column0` es auxiliar y no se importa. El reporte no entrega fechas de actualización; esos mapas permanecen vacíos.

## 2. Identidad original y campos pendientes de almacenamiento

El reporte ya entrega User Primary Identifier (Column1) y Preferred Email (Column19) sin CASE ni LOWER. El programa obtiene la clasificación de uso interno del indicador Y/N; no se sustituye la identidad por una etiqueta.

También quedaron identificados Barcode (Column9), Loan Time (Column14), Material Type (Column15), MMS Id (Column16), Item Policy (Column18), correo (Column19), Library Code (Column7) y el módulo (Column4–Column6). El extractor todavía debe ampliarse para almacenar todos esos campos; el mapeo actual corresponde al esquema básico implementado.

**Si cambias columnas o fórmulas, vuelve a inspeccionar antes de importar:** el orden de ColumnN puede cambiar. Los atributos académicos y la identidad validada se completarán desde la universidad después.

## 3. Revisar renovaciones por campus

**Dónde:** Renewals → Edit → Criteria.

Comprueba estas columnas:

| Columna | Campo de Analytics |
| --- | --- |
| Préstamo | Loan Details → Item Loan ID |
| Fecha de renovación | Renewal Date → Renewal Date |
| Cantidad | Loan → Renewals |
| Código de campus | Renewal Circulation Desk → Campus Code |
| Campus | Renewal Circulation Desk → Campus Name |

Conserva los identificadores originales de usuario, correo y ejemplar. Filtra por fecha de renovación y `Renewals > 0`; no por fecha del préstamo. Compara la suma de cantidades por campus, no el número de filas.

La clave será préstamo + día + campus. Un campus ausente queda sin asignar; no lo sustituyas por el del préstamo ni por el del usuario. No añadas todavía mesas que dividan esa misma clave.

Las renovaciones automáticas no pueden incluirse en el conteo fechado de la misma forma; tampoco reconstruiremos todas las renovaciones usando Last Renewal Date. [Referencia oficial](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_(English)/080Analytics/Alma_Analytics_Subject_Areas/Fulfillment).

## 4. Confirmar fechas y mapear columnas

En **Criteria → menú de columna de fecha → Edit Formula**, consulta **Column Formula**. Debe coincidir con `date_column` en la sección existente de `config.toml`:

| Sección | Expresión esperada si usaste esas columnas |
| --- | --- |
| `[alma.prestamos]` | `"Loan Date"."Loan Date"` |
| `[alma.renovaciones]` | `"Renewal Date"."Renewal Date"` |

No necesitas copiar todo el XML. En el análisis de la API, la fecha debe quedar como `is prompted`, sin un filtro fijo adicional que limite el período. [Rutas y filtros](https://developers.exlibrisgroup.com/blog/Working-with-Analytics-REST-APIs/).

Ejecuta también la inspección de Renewals:

```bash
.venv/bin/python -m alma_libcal inspect-alma --dataset renovaciones --without-filter
```

Loans ya tiene su mapeo verificado para el esquema básico. Falta la salida de Renewals para actualizar `[alma.renovaciones.fields]`, que todavía contiene ejemplos. No reutilices el orden de Loans: cada análisis puede devolver columnas diferentes.

| Mapeo del programa | Loans | Renewals |
| --- | --- | --- |
| `loan_id` | Item Loan ID | Item Loan ID |
| `activity_date` | Loan Date | Renewal Date |
| `user_id` | Identificador original | Identificador original |
| `site` / `site_id` | Nombre/código del campus del préstamo | Nombre/código del campus de renovación |
| `in_house_loan_indicator` | Indicador Y/N original | No aplica |
| `quantity` | Una operación | Medida Renewals |

También comprobaremos correo, Item ID, MMS ID, Barcode, Material Type, Item Policy, Title, hora original y módulo del préstamo. **Loan Time está en Loan Details.** El código aún debe ampliarse para guardar todos esos campos; no necesitas añadir atributos académicos del usuario.

Termina este paso cuando funcionen ambas inspecciones, tengamos el mapeo verificado y los conteos por fecha/campus coincidan con Analytics. Comparte solo encabezados y fórmulas, sin usuarios ni claves.
