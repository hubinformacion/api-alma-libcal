# 03 — Dónde están los datos y cómo abrirlos

## Ver la primera muestra en Excel

Ya generamos estas copias locales para la primera comparación:

- `data/verificacion/prestamos-2026-10-07.csv`: 198 filas.
- `data/verificacion/renovaciones-2026-10-07.csv`: 10 filas; suma de renewal_quantity igual a 10.
- `data/verificacion/reservas-2026-10-08.csv`: 3 filas al momento de consultar.
- `data/verificacion/resumen.csv`: conteos y suma de quantity por conjunto, fecha, campus, categoría y estado.

En Excel usa **Datos → Desde texto/CSV**, selecciona el archivo y el delimitador punto y coma. Importa IDs, códigos y correos como texto para conservar ceros iniciales y números largos. En `resumen.csv`, compara `filas` para préstamos/reservas y `suma_quantity` para renovaciones.

Estas copias son una fotografía de la primera muestra; `sync` no las actualiza automáticamente. Para ver nuevas extracciones utiliza SQLite o Sheets como se explica abajo.

## Archivo local

La ruta configurada es:

```text
/home/asus/projects/api-alma-libcal/data/pilot.sqlite3
```

SQLite guarda la base de datos en **ese único archivo**. No necesitas instalar un servidor. El programa lo crea al abrir el almacenamiento; puede existir vacío antes de la primera extracción. `check-libcal` e `inspect-alma` no agregan registros.

Para saber qué hay guardado:

```bash
.venv/bin/python -m alma_libcal status
```

Busca `dataset`, `total_rows`, `last_extraction_status`, `last_from` y `last_to`. `total_rows` cuenta todo el histórico del conjunto, no solo la última fecha. `last_extraction_status = extracted` confirma que terminó la extracción.

## Abrir SQLite en Antigravity

Usa **SQLite Viewer**, de **qwtel**, identificador `qwtel.sqlite-viewer`, disponible en [Open VSX](https://open-vsx.org/extension/qwtel/sqlite-viewer). Es un visor de tablas en modo lectura; no necesitas sus funciones de pago para revisar tablas. [Documentación de la extensión](https://github.com/qwtel/sqlite-viewer-vscode).

1. Abre Extensiones en Antigravity (`Ctrl+Shift+X`, si tu versión usa esos atajos), busca el identificador exacto e instálala si aparece en su catálogo.
2. Abre `data/pilot.sqlite3` desde el explorador del proyecto. Si no aparece, usa Archivo → Abrir archivo y pega la ruta completa anterior. Estar excluido de Git no elimina el archivo.
3. Si abre como contenido binario, usa **Reopen Editor With / Abrir con → SQLite Viewer**.
4. Selecciona `records` para ver operaciones; `runs` contiene ejecuciones y errores; `snapshots`, el estado de extracción/publicación.
5. Filtra `dataset` por `prestamos`, `renovaciones` o `reservas` y `activity_date` por el día que comparas.

La tabla `records` contiene ID y fecha como columnas; los demás atributos están juntos en `payload`, un texto JSON. Estos nombres internos permiten gestionar el histórico; no son los encabezados del CSV o de Sheets. Cada reporte de Alma tiene su propio esquema de salida, detallado en la guía 01. Tras otra extracción, cierra y vuelve a abrir el archivo para refrescar el visor. La compatibilidad depende de la versión de Antigravity y su catálogo; si no aparece la extensión, utiliza la opción siguiente.

## Ver cada atributo en una columna de Sheets

La autorización de Google ya está preparada. Después de guardar una muestra, puedes publicarla en la hoja configurada:

```bash
.venv/bin/python -m alma_libcal publish --only prestamos
.venv/bin/python -m alma_libcal publish --only renovaciones
.venv/bin/python -m alma_libcal publish --only reservas
```

Ejecuta solo el conjunto que quieras revisar. Abre tu hoja habitual de Google Sheets y la pestaña con ese nombre. Allí correo, fechas, recurso, campus, estado y cantidad aparecen en columnas separadas. Para renovaciones suma `renewal_quantity`; para préstamos/reservas cuenta registros filtrados por fecha y campus.

**La publicación reemplaza la pestaña seleccionada con su histórico local y actualiza `control`.** No la uses como lugar de edición manual de datos. `publish` no vuelve a consultar las APIs y las fechas de la última extracción no limitan lo publicado.

SQLite y los archivos locales con credenciales están excluidos de Git. Alma ya exporta las columnas indicadas en la guía 01 para cada conjunto. LibCal todavía tiene pendientes algunos cálculos y campos del reporte final.
