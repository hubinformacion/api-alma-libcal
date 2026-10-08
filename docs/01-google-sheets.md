# 01 — Publicar la muestra y validar Google Sheets

El acceso a la hoja configurada fue comprobado el 8 de octubre de 2026. Las credenciales ya están preparadas; no repitas la autorización. Esta es una ejecución manual: todavía no hay programación automática.

## 1. Publicar lo que ya está guardado

En la terminal del proyecto:

```bash
cd /home/asus/projects/api-alma-libcal
.venv/bin/python -m alma_libcal publish --only prestamos renovaciones reservas
```

El programa lee `data/pilot.sqlite3` y publica en la hoja cuyo ID está en `[google].spreadsheet_id` de `config.toml`. No consulta Alma ni LibCal nuevamente. Creará las pestañas `prestamos`, `renovaciones`, `reservas` y `control` si faltan.

**La publicación reemplaza el contenido de las pestañas seleccionadas con todo su histórico local.** Usa otras pestañas para fórmulas y análisis manuales. La respuesta esperada es `Publicación confirmada: prestamos, renovaciones, reservas.` Si hay error, el histórico sigue local y puedes reintentar el mismo comando.

## 2. Abrir y comprobar la hoja

Abre la hoja configurada en Google Sheets. Si no tienes su enlace, copia el valor de `spreadsheet_id` y úsalo en `https://docs.google.com/spreadsheets/d/ID/edit`.

| Pestaña | Filas de datos esperadas | Comprobación |
| --- | ---: | --- |
| prestamos | 198, además del encabezado | 19 encabezados; columnas propias de préstamos |
| renovaciones | 10, además del encabezado | 14 encabezados; suma de renewal_quantity igual a 10 |
| reservas | 3, además del encabezado | IDs, inicio/fin, campus y estado de la muestra |

Compara con los CSV locales y revisa algunas operaciones por loan_id o record_id: correos originales, fechas, barcode, MMS ID y campus. Los IDs deben conservar sus dígitos y ceros iniciales. La renovación sin campus debe seguir vacía; es una característica de la respuesta de Alma, no un fallo de publicación.

Las fechas de las muestras son las de la guía 00. Si extraes otros días, la publicación incluye también esos registros: adapta los conteos y filtra por fecha.

## 3. Revisar el estado y repetir

```bash
.venv/bin/python -m alma_libcal status
```

Para cada conjunto publicado, verifica `pending = no`, `revision = published_revision` y `last_status = published`. Lo mismo aparece en `control`. Esto confirma el estado registrado tras la respuesta de Google; la comprobación visual anterior valida el contenido de la hoja.

Repite `publish --only prestamos renovaciones reservas`. Las filas deben permanecer en 198, 10 y 3, porque la publicación reemplaza las tablas y no agrega copias. La prueba queda cerrada cuando coinciden encabezados, valores, cantidades y estado local.

## 4. Nuevas extracciones

Para Alma cambia las fechas según el día que quieras recuperar:

```bash
.venv/bin/python -m alma_libcal sync --only prestamos renovaciones --from 2026-10-07 --to 2026-10-07 --extract-only
```

Para LibCal usa el día actual, no una fecha pasada. Este ejemplo solo corresponde al 8 de octubre:

```bash
.venv/bin/python -m alma_libcal sync --only reservas --from 2026-10-08 --to 2026-10-08 --extract-only
```

Después revisa lo extraído y ejecuta `publish`. `--extract-only` guarda en SQLite; omitirlo en `sync` consulta, guarda y publica en una misma ejecución. Al repetir una fecha, los mismos IDs se actualizan sin duplicarse. La suma de renovaciones se consulta en `renewal_quantity`, no en la cantidad de filas.
