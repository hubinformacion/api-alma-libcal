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

## 3. Renewals: mapeo confirmado por campus

La inspección recibida confirma estas columnas; ya se configuró `[alma.renovaciones.fields]`:

| Campo del programa | Columna API |
| --- | --- |
| `loan_id` | Column4 — Item Loan Id |
| `activity_date` | Column13 — Renewal Date |
| `user_id` | Column1 — User Primary Identifier |
| `resource_id` | Column3 — Item Id |
| `resource_name` | Column8 — Title |
| `site_id` | Column11 — Renewal Campus Code |
| `site` | Column12 — Renewal Campus Name |
| `status` | Column5 — Loan Status |
| `quantity` | Column14 — Renewals |

Column0 se ignora. No hay fechas de actualización en esta respuesta, así que sus mapas quedan vacíos. Barcode (Column2), Material Type (Column6), MMS Id (Column7), Item Policy (Column9) y Preferred Email (Column10) quedan identificados para la ampliación del extractor.

La cantidad llega como `xsd:double`: el lector acepta valores enteros como `2.0` y los convierte a 2. El total de renovaciones es la **suma de quantity**, no el número de filas. La clave distingue préstamo + día + campus de renovación. Un campus ausente queda sin asignar.

## 4. Validación pendiente

Ambos reportes ya tienen su mapeo básico confirmado. Todavía debemos:

1. Confirmar que Renewals admite el intervalo de fecha enviado por la API. Su filtro debe usar Renewal Date como `is prompted`, sin un filtro fijo de Loan Date, y conservar `Renewals > 0`.
2. Ampliar el almacenamiento para correo y atributos del ejemplar que ya identificamos en ambos análisis.
3. Extraer un día conocido y comparar préstamos distintos y suma de renovaciones por campus con Analytics. Verificar que no se repiten claves préstamo/día/campus.

Para inspeccionar Renewals con fechas, sustituye ambos valores por un día con renovaciones conocidas:

```bash
.venv/bin/python -m alma_libcal inspect-alma --dataset renovaciones --from 2026-10-06 --to 2026-10-06
```

El comando solo muestra encabezados: confirma la consulta, pero no valida los conteos. La comparación se hará al extraer la muestra después de ampliar el esquema.

Las renovaciones automáticas siguen fuera del conteo fechado; Last Renewal Date tampoco permite reconstruir todos los movimientos. [Referencia oficial](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_(English)/080Analytics/Alma_Analytics_Subject_Areas/Fulfillment).

**No cambies columnas ni fórmulas sin volver a inspeccionar:** los números ColumnN pueden cambiar. La identidad validada y los atributos académicos se completarán desde la universidad en la etapa posterior.
