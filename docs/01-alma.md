# 01 — Alma: extraer y comparar

Loans y Renewals ya tienen rutas y mapas de columnas en `config.toml`. Para esta verificación conserva los análisis actuales, con identificadores y correos originales, sin fórmulas que sustituyan usuarios por etiquetas.

## 1. Guardar préstamos de un día

Desde la carpeta del proyecto:

```bash
.venv/bin/python -m alma_libcal sync --only prestamos --from 2026-10-07 --to 2026-10-07 --extract-only
```

Sustituye ambas fechas por el mismo día con registros conocidos en Analytics. El programa consulta todas las páginas y muestra cuántas filas extrajo y cuántas hay en el histórico. Guarda los registros en `data/pilot.sqlite3`, sin enviarlos a Google.

En Analytics abre el análisis **Loans** conectado a la API, aplica la misma fecha de préstamo y exporta a Excel. Compara:

- Cantidad de préstamos: IDs `Item Loan Id` distintos frente a las filas extraídas.
- Conteos por campus de la operación, no por campus del usuario.
- Usos internos: `In House Loan Indicator = Y`. La ausencia de usuario por sí sola no los identifica.
- Algunas filas por ID: fecha, ejemplar, título, campus, estado y correo original.

El programa conserva préstamos y usos internos en `prestamos`; `in_house_loan_indicator = Y` permite distinguirlos.

## 2. Guardar renovaciones del mismo día

```bash
.venv/bin/python -m alma_libcal sync --only renovaciones --from 2026-10-07 --to 2026-10-07 --extract-only
```

En Analytics abre **Renewals**, usa la misma `Renewal Date` y compara la **suma de Renewals** con la **suma de renewal_quantity** en los registros guardados. El número de filas no es el total de renovaciones: una fila puede representar varias.

Compara esa suma por campus de renovación. La clave del programa distingue préstamo, día y campus. Para ver `renewal_quantity` por columnas, sigue [03 — Ver los datos](03-ver-datos.md).

Si falla el filtro de fechas, prueba:

```bash
.venv/bin/python -m alma_libcal inspect-alma --dataset renovaciones --from 2026-10-07 --to 2026-10-07
```

Ese diagnóstico muestra encabezados, no cantidades. Verifica en Analytics que Renewal Date sea un filtro `is prompted`, que no quede un filtro fijo de Loan Date y que se conserve `Renewals > 0`. Las renovaciones automáticas no se incorporan al conteo fechado: la medida no tiene asociación con Renewal Date. [Referencia de Ex Libris](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_(English)/080Analytics/Alma_Analytics_Subject_Areas/Fulfillment).

## 3. Registrar el resultado

Anota fecha, conjunto, campus, cantidad de Analytics y cantidad del programa. Repite la extracción del mismo día: los IDs existentes se actualizan y no deben duplicarse.

Los CSV y las pestañas de Sheets tienen estructuras distintas para préstamos y renovaciones. Ya se guardan barcode, MMS ID, tipo de material, política y los detalles de hora/biblioteca/módulo disponibles en Loans. Si cambias el orden de columnas de Analytics, debemos actualizar el mapa antes de extraer.

## Columnas de salida

Préstamos (19 columnas):

```text
loan_id, source_user_id, source_user_email, item_id, item_mms_id, item_barcode, item_material_type, item_policy, item_title, loan_date, loan_time, in_house_loan_indicator, loan_campus_code, loan_campus, loan_library_code, loan_desk_code, loan_desk_name, loan_desk_description, loan_status
```

Renovaciones (14 columnas):

```text
loan_id, source_user_id, source_user_email, item_id, item_mms_id, item_barcode, item_material_type, item_policy, item_title, renewal_date, renewal_campus_code, renewal_campus_name, renewal_quantity, loan_status
```

`loan_id` es el ID original de Alma. La clave interna compuesta de renovación no se exporta como loan_id. Los campos vacíos de la fuente siguen vacíos. No se incluyen columnas de reservas de LibCal en estos reportes.
