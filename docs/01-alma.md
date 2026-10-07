# 01 — Alma: ajustes y validación pendientes

Ya tienes Loans y comprobaste que `loan_id` no se repite en el día revisado. Las rutas están introducidas en `config.toml`; no recrees el análisis ni la clave.

## 1. Validar la consulta que devolvía HTTP 500

**Dónde:** terminal de Ubuntu, dentro del proyecto.

```bash
.venv/bin/python -m alma_libcal inspect-alma --dataset prestamos --without-filter
```

Muestra columnas, sin imprimir usuarios. Se corrigió el prefijo de las rutas de `/Shared Folders/` a `/shared/`, pero aún falta confirmar que la consulta funciona.

- Si falla también sin filtro, revisa el resto de la ruta, la región y los permisos de la clave Analytics/Production/Read-only.
- Si funciona, prueba el día que revisaste en Analytics; sustituye ambas fechas del ejemplo:

```bash
.venv/bin/python -m alma_libcal inspect-alma --dataset prestamos --from 2026-10-06 --to 2026-10-06
```

Si solo falla con fechas, verifica `date_column` y el filtro `is prompted` del análisis.

## 2. Separar usos internos e identidad

**Dónde:** Loans → Edit → Criteria.

Conserva dos columnas independientes:

| Columna | Campo de Analytics |
| --- | --- |
| Identificador original | Borrower Details → User Primary Identifier |
| Indicador de uso interno | Loan Details → In House Loan Indicator |

No sustituyas el identificador por «Uso interno» en la columna que extraeremos. Puedes conservar tu fórmula anterior para el reporte visual. Si quieres una etiqueta separada:

```sql
CASE WHEN "Loan Details"."In House Loan Indicator" = 'Y'
THEN 'Uso interno' ELSE 'Préstamo' END
```

El programa conserva el indicador y calcula `usage_type`. Un uso interno sin usuario no es un error de identificación ni genera un usuario ficticio. No lo excluyas mediante filtros de correo/identificador no nulos.

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

Con la salida de ambas inspecciones, actualizaremos los `ColumnN` de `[alma.prestamos.fields]` y `[alma.renovaciones.fields]`. No se deducen del orden visual y los actuales siguen siendo ejemplos.

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
