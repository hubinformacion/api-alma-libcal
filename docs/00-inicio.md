# 00 — Estado y pendientes

Las cantidades de la muestra ya coinciden con los reportes de ambos sistemas. Préstamos y renovaciones de Alma tienen esquemas propios de 19 y 14 columnas. La siguiente prueba es publicar el histórico local y comprobarlo en Google Sheets: sigue [01 — Validar Sheets](01-google-sheets.md).

## Muestra guardada

| Conjunto | Fecha | Registros | Cantidad validada |
| --- | --- | ---: | ---: |
| Préstamos | 2026-10-07 | 198 | 198 |
| Renovaciones | 2026-10-07 | 10 | Suma de renewal_quantity: 10 |
| Reservas | 2026-10-08 | 3 | 3 al momento de consultar |

La base local es `data/pilot.sqlite3`; las copias CSV están en `data/verificacion/`. Los CSV son fotografías de la muestra y no se actualizan automáticamente con `sync`.

## Investigar la renovación sin campus

El préstamo **3142701100007836**, renovación del **7 de octubre de 2026**, llega desde la API de Analytics sin Renewal Campus Code ni Renewal Campus Name. Lo comprobamos en la respuesta original: el programa no elimina esos valores.

Estos campos describen el campus del módulo de renovación. [Referencia de Ex Libris](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_(English)/080Analytics/Alma_Analytics_Subject_Areas/Fulfillment).

1. En Analytics abre Renewals y utiliza **Guardar como** para hacer una copia de diagnóstico. Mantén intacto el análisis conectado a la API: agregar columnas podría cambiar sus ColumnN.
2. Filtra por Item Loan Id = `3142701100007836` y Renewal Date = `2026-10-07`.
3. En la copia agrega, desde **Renewal Circulation Desk**, Renewal Circ Desk Code, Renewal Circ Desk Name, Renewal Library Code y Renewal Library Name. Conserva Renewal Campus Code/Name y Renewals.
4. Si biblioteca y módulo también están vacíos, revisa la operación en Alma: localiza el préstamo mediante el usuario o barcode de tu CSV y abre **Actions (…) → Loan History** en su lista de préstamos. Investiga cómo se hizo esa renovación; todavía no sabemos la causa de este caso. [Historial en Alma](https://knowledge.exlibrisgroup.com/Alma/Product_Materials/050Alma_FAQs/Fulfillment/Circulation).
5. Si hay biblioteca, verifica su asociación a campus en **Configuration → General → Libraries → Add a Library or Edit Library Information**. [Configuración de bibliotecas](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_(English)/050Administration/050Configuring_General_Alma_Functions/020Managing_Institutions_and_Libraries).

No sustituyas automáticamente ese vacío por el campus del usuario o del préstamo original: describen otra relación. La renovación sigue contando en el total; incluye el grupo sin campus al sumar por sede.

## Después de validar Sheets

Quedan completar campos finales de LibCal, definir una fuente para su histórico, cruzar usuarios con la universidad y programar las ejecuciones. La API de reservas usada no consulta fechas pasadas; esto debe resolverse antes de elegir una frecuencia semanal.
