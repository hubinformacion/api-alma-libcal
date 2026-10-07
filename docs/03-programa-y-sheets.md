# 03 — Configurar el programa, validar y publicar

Usa este documento cuando los reportes de [Alma](01-alma.md) estén preparados. Puedes inspeccionar Alma sin configurar LibCal ni Google.

## Ejecutar sin activar entornos manualmente

Tienes Python 3.12.3: cumple el requisito. Abre Ubuntu y entra al proyecto:

```bash
cd /home/asus/projects/api-alma-libcal
./run.sh --help
```

`./run.sh` utiliza automáticamente `.venv`, una carpeta con un entorno Python separado para este proyecto. Si no existe, la crea. No necesitas ejecutar `source`, activar el entorno ni repetir la instalación para inspeccionar Alma/LibCal.

## Qué va en .env y qué va en config.toml

**`.env`: solo las credenciales**, en la misma carpeta que `config.toml`:

```dotenv
ALMA_API_KEY=tu_clave_de_alma
LIBCAL_CLIENT_ID=tu_client_id
LIBCAL_CLIENT_SECRET=tu_client_secret
```

Usa una entrada por línea. Se admiten comillas y comentarios; no se ejecutan comandos ni se expanden variables. Si un valor contiene espacios o `#`, ponlo entre comillas. El archivo no se sube a Git. Las variables ya exportadas en la terminal tienen prioridad; si conservaste una clave antigua exportada, abre otra terminal o elimina esa variable antes de reintentar.

**`config.toml`: URLs, rutas de análisis, IDs y mapas de campos.** Ya existe: edita sus secciones, sin sobrescribirlo con el ejemplo ni duplicar nombres de sección. `ALMA_API_KEY` en `api_key_env` es el nombre de la variable, no la clave.

El programa carga `.env` automáticamente. No hace falta usar `read`, `export` ni instalar una dependencia adicional para hacerlo.

## Inspeccionar Alma

1. Completa `alma.base_url` con el host regional de tu institución.
2. En `[alma.prestamos]`, completa `report_path` y `date_column` con la ruta y expresión exactas de `Loans`. No codifiques manualmente la ruta.
3. Primero comprueba ruta y acceso sin filtro de fecha:

```bash
./run.sh inspect-alma --dataset prestamos --without-filter
```

Solo muestra nombres de columnas, aunque la consulta recupere una muestra del reporte. Si funciona, comprueba un día conocido:

```bash
./run.sh inspect-alma --dataset prestamos --from 2026-10-06 --to 2026-10-06
```

Sustituye las fechas por el día que comprobaste en Analytics. El comando muestra nombres de columnas, sin imprimir valores de usuarios.

Después completa `[alma.renovaciones]` y ejecuta:

```bash
./run.sh inspect-alma --dataset renovaciones --from 2026-10-06 --to 2026-10-06
```

La API puede devolver `Column1`, `Column2`, etc. Sus posiciones **no coinciden necesariamente con el orden visual**. El mapa `[alma.*.fields]` debe basarse en los encabezados/estructura real y, cuando haga falta, en **Advanced → SQL / Analysis XML**. Las posiciones del ejemplo son ficticias.

Si las fechas no llegan en ISO, debemos adaptar el lector: no basta con cambiar su presentación visual. Las credenciales permanecen en `.env` y se cargan en cada ejecución.

### Si Alma sigue respondiendo HTTP 500

La configuración recibida usaba `/Shared Folders/…`; se corrigió a `/shared/…`. Esto elimina un problema de ruta, pero no confirma que sea la única causa del error.

- Si también falla `--without-filter`, verifica la ruta completa y los permisos de la clave **Analytics / Production / Read-only**, además del host regional.
- Si funciona sin filtro y falla con fechas, abre **Criteria → columna de fecha → Edit Formula** y compara con `date_column`, siguiendo [01 — Alma](01-alma.md). Verifica también que el filtro esté como `is prompted`.
- No cambies el orden de `ColumnN` a ciegas: primero necesitamos la salida de inspección.

## Inspeccionar LibCal

Las instrucciones completas, incluidos tus seis campus, están en [02 — LibCal](02-libcal.md). Empieza por:

```bash
./run.sh discover-libcal --locations 20114
./run.sh check-libcal --location 20114
```

El primer comando obtiene categorías de Cusco; el segundo valida reservas de hoy y solo muestra conteos/campos. No hace falta configurar todas las categorías para estas pruebas.

El YAML recibido confirma que `/space/bookings` ignora fechas pasadas. **No pruebes ayer ni un histórico con esa operación.** Una futura carga histórica requiere exportación u otra fuente confirmada por Springshare.

## Antes de extraer el reporte completo

**El código actual guarda un esquema básico.** Inspeccionar más columnas no hace que se almacenen. Antes de ejecutar la extracción completa debemos:

1. Ampliar modelos, conectores, SQLite y salidas para los campos de 01 y 02, incluidos correo y respuestas de formulario.
2. Verificar formatos de fechas y claves. Las renovaciones se separan por campus mediante `site_id`; si se añaden mesas habrá que revisar su clave antes de importarlas.
3. Probar un día de Alma y hoy en LibCal y comparar préstamos distintos, suma de renovaciones y reservas por categoría/estado con los sistemas originales.
4. Repetir el mismo intervalo y confirmar que los registros no se duplican.

Estas tareas corresponden al desarrollo del programa, después de verificar la estructura real. No necesitas aprender a programarlas para preparar los reportes.

## Google Sheets: omitir si ya quedó configurado

Si ya tienes la hoja y los archivos de autorización, conserva esa configuración y pasa a la validación. Estos pasos quedan como referencia para reinstalar.

**Dónde:** navegador → Google Sheets y [Google Cloud Console](https://console.cloud.google.com/).

1. Crea una hoja de prueba. Su ID está entre `/d/` y `/edit` en la URL; colócalo en `google.spreadsheet_id`.
2. Crea o selecciona un proyecto de Google Cloud y habilita **Google Sheets API** en **APIs & Services → Library**.
3. En **Google Auth platform**, configura **Branding** y **Audience**. Usa audiencia interna si tu organización lo permite; si es externa en pruebas, añade tu cuenta como usuario de prueba.
4. Configura el alcance `https://www.googleapis.com/auth/spreadsheets` en **Data Access**, cuando se solicite.
5. En **Clients → Create Client**, selecciona **Desktop app** y descarga su JSON.
6. Guarda el archivo en `secrets/google-client.json`, dentro del proyecto. Los secretos y tokens están excluidos de Git.

Referencias de configuración: [inicio rápido de Sheets](https://developers.google.com/workspace/sheets/api/quickstart/python) y [credenciales OAuth](https://developers.google.com/workspace/guides/create-credentials).

En Ubuntu:

```bash
mkdir -p secrets
chmod 700 secrets
./run.sh auth-google
```

Abre el enlace mostrado en el navegador de Windows y autoriza la cuenta con acceso de edición. Conserva la terminal abierta mientras el navegador regresa a `localhost:8765`. El token se guarda en `secrets/google-token.json`. Si el puerto está ocupado, usa `auth-google --port 8766`.

## Extraer y publicar, después de adaptar el código

Cada conjunto se puede ejecutar por separado; Google no hace falta para `--extract-only`:

```bash
./run.sh sync --only prestamos --extract-only --from 2026-10-06 --to 2026-10-06
./run.sh sync --only renovaciones --extract-only --from 2026-10-06 --to 2026-10-06
# LibCal: sustituye AMBAS fechas por hoy, después de configurar los cid reales.
./run.sh sync --only reservas --extract-only --from YYYY-MM-DD --to YYYY-MM-DD
./run.sh status
./run.sh publish --only prestamos
```

Sustituye las fechas por el día validado. Con una configuración completa, `sync` extrae y publica todos los conjuntos; `publish` reintenta desde SQLite sin consultar los proveedores. Un archivo alternativo se indica antes del subcomando: `./run.sh --config otra-config.toml status`.

## Comportamiento y límites del piloto

- Python consulta fuentes; SQLite conserva el histórico; Google es la salida. Hay pestañas separadas `prestamos`, `renovaciones`, `reservas` y `control`. No unimos Alma y LibCal.
- Las claves actuales son préstamo, préstamo/día/campus para renovaciones cuando se mapea `site_id` y reserva. Una extracción se guarda al completar sus páginas; un fallo conserva el histórico anterior. La ausencia de registros no prueba cancelaciones ni borra operaciones.
- `publish` reemplaza las pestañas seleccionadas con todo su histórico local; las fechas de `sync` solo delimitan la extracción. Se sobrescriben ediciones manuales en esas pestañas.
- El publicador actual limita cada solicitud a 1,8 MB y publica atómicamente las pestañas seleccionadas y el control. Si excede el límite, la publicación queda pendiente. Revisaremos volumen antes de una carga anual.
- Analytics se actualiza por cargas: no debe asumirse que incluye la actividad de hoy. Revisaremos sus fechas de actualización. La anonimización puede impedir el cruce de usuarios antiguos. [Actualización de Analytics](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_(English)/080Analytics/010Introduction/Analytics_Database_Refresh).
- La zona del piloto es `America/Lima`; el inicio configurable está en `project.start_date`. Hoy la ejecución es manual, con autorización de escritorio. Después añadiremos programación diaria/semanal, respaldo y alojamiento.

## Diagnóstico

| Problema | Qué revisar |
| --- | --- |
| Falta una variable de entorno | Completar la credencial en `.env`, junto a `config.toml` |
| HTTP 401/403 | Credenciales, permisos y región |
| Columna o fecha inesperada | Encabezados reales, mapa de campos y formato |
| Claves duplicadas en Alma | Granularidad del análisis; columnas que multiplican préstamo/día |
| Página repetida de LibCal | Contrato real de paginación |
| Publicación pendiente | Acceso a Google y volumen; reintentar `publish` |

Los comandos de desarrollo y la demostración sin credenciales están en el [README](../README.md).

## Si hay que reinstalar las dependencias de Google

Para inspeccionar Alma y LibCal basta la biblioteca estándar de Python. Solo si falta la autorización de Google, instala una vez sus dependencias:

```bash
./run.sh --help
.venv/bin/python -m pip install -e ".[google]"
```

La segunda instrucción necesita acceso a internet. No elimina los JSON ni la hoja que ya configuraste.
