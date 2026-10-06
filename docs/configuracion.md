# Configuración paso a paso

Esta guía prepara tres accesos: **Alma**, **LibCal** y **Google Sheets**. No necesitas desarrollar otra API ni contratar un servidor para probar. Haz primero la demostración del README y luego configura una fuente a la vez.

## 1. Preparar la computadora

Abre Ubuntu desde Windows y entra en la carpeta del proyecto. Instala el entorno siguiendo el README, copia `config.example.toml` como `config.toml` y abre ese archivo con tu editor. Por ejemplo:

```bash
nano config.toml
```

Si usas `nano`, guarda con **Ctrl+O**, confirma con **Enter** y sal con **Ctrl+X**. Las entradas `REPLACE_...` son espacios para tus datos. No pongas claves en ese archivo: contiene rutas, nombres de campos e identificadores de recursos.

Puedes completar las fuentes por separado. `--only prestamos`, `--only renovaciones` o `--only reservas` permite probar una sin configurar las demás.

## 2. Dar acceso a Alma

### Crear la clave de lectura

1. Abre [Ex Libris Developer Network](https://developers.exlibrisgroup.com/) e inicia sesión con una cuenta vinculada a tu institución.
2. Busca la administración de claves, **Manage API Keys / API Keys**. Crea una aplicación para este piloto, por ejemplo `Reportes Alma LibCal`.
3. Añade acceso a **Alma → Analytics**, con permiso **Read** y el entorno de producción que contiene tus reportes. No necesitas escritura.
4. Guarda la clave solo en tu computadora. Si no aparece tu institución o Analytics, un administrador deberá vincular la cuenta o habilitar ese permiso.
5. En `config.toml`, verifica `alma.base_url`: debe ser el host API de la región de tu institución, no la dirección de inicio de sesión de Alma.

Consulta las [instrucciones oficiales de acceso a las APIs](https://developers.exlibrisgroup.com/alma/apis/) si las etiquetas difieren.

### Preparar los dos reportes

En Alma, abre **Analytics → Design Analytics**. Crea dos análisis del área **Fulfillment** y guárdalos en una carpeta compartida institucional, por ejemplo `Pilot`:

| Reporte | Datos necesarios |
| --- | --- |
| `Loans` | Item Loan ID, Loan Date, User Primary Identifier, Item ID, Title, biblioteca y Loan Status |
| `Renewals` | Item Loan ID, Renewal Date, User Primary Identifier, Item ID, Title, biblioteca y medida Renewals |

Incluye también los campos institucionales **Data updated as of** y **Data available as of** si están disponibles. Mantén los identificadores como texto para no perder ceros iniciales ni precisión. El reporte de renovaciones debe producir una fila por préstamo y día: no añadas dimensiones que dividan esa misma clave en varias filas.

En cada reporte prepara el filtro de su fecha como **is prompted**, para que la API pueda aplicar el intervalo solicitado. No dejes filtros fijos que excluyan parte del período del piloto. Obtén la ruta del análisis desde su URL en Analytics, como describe Ex Libris, y colócala en `report_path` **sin codificarla manualmente**. [Rutas y filtros](https://developers.exlibrisgroup.com/blog/Working-with-Analytics-REST-APIs/).

`date_column` debe contener la expresión exacta del campo en el análisis: confirma la carpeta y el nombre en **Advanced → Analysis XML**. Las expresiones incluidas en el ejemplo son puntos de partida.

### Introducir la clave e identificar columnas

En la terminal de Ubuntu, este comando pide la clave sin mostrarla ni escribir su valor en el historial:

```bash
read -rs -p "Clave API de Alma: " ALMA_API_KEY
export ALMA_API_KEY
```

Estas variables duran en esa terminal; repite la introducción al abrir otra. El programa no carga archivos `.env` automáticamente.

Después de configurar la ruta del reporte:

```bash
python -m alma_libcal inspect-alma --dataset prestamos
python -m alma_libcal inspect-alma --dataset renovaciones
```

Los comandos muestran nombres de columnas y encabezados disponibles, **sin imprimir los registros de usuarios**. Ajusta los mapas `[alma.prestamos.fields]` y `[alma.renovaciones.fields]` con el `ColumnN` correspondiente a cada campo. El orden API puede diferir del orden visual del reporte. Si los encabezados llegan vacíos, utiliza la sección de columnas/SQL de **Advanced** para determinar el orden; no adivines las posiciones.

No hace falta compartir la clave. Para ayudarte con el mapeo puedes compartir la salida de `inspect-alma`, que no incluye valores de usuarios.

## 3. Dar acceso a LibCal

### Registrar una aplicación

1. Entra al panel administrativo de tu LibCal institucional.
2. Abre **Admin → API** y busca la sección de aplicaciones o autenticación. Sus etiquetas pueden variar según la interfaz.
3. Crea una aplicación para el piloto, por ejemplo `Reportes Alma LibCal`. Habilita lectura de **Spaces / Seats**, incluyendo información administrativa de reservas si existe un permiso separado.
4. Guarda localmente **Client ID** y **Client Secret**. Son las credenciales del programa; no son tu usuario y contraseña de LibCal.
5. En `config.toml`, sustituye `libcal.base_url` por la dirección de tu instancia, por ejemplo `https://biblioteca.libcal.com`, sin agregar `/admin`.

Introduce las credenciales en Ubuntu:

```bash
read -rs -p "Client ID de LibCal: " LIBCAL_CLIENT_ID
export LIBCAL_CLIENT_ID
read -rs -p "Client Secret de LibCal: " LIBCAL_CLIENT_SECRET
export LIBCAL_CLIENT_SECRET
```

### Identificar tus tres categorías

Ejecuta:

```bash
python -m alma_libcal discover-libcal
```

El comando consulta las ubicaciones con detalles de Spaces; no consulta reservas ni usuarios. Si la respuesta incluye categorías, encuentra las tres y copia sus identificadores en las entradas `[[libcal.categories]]`. Conserva los nombres de agrupación del ejemplo. Si no incluye categorías, busca sus IDs al editar cada categoría en **Spaces** o en la documentación de **Admin → API**.

### Entender los datos técnicos sin programar

Dentro de **Admin → API**, busca en la documentación la consulta de **Space bookings / reservas de espacios**:

| Lo que aparece | Qué significa | Dónde se configura |
| --- | --- | --- |
| Endpoint o ruta | La dirección de una consulta, por ejemplo `/1.1/space/bookings` | `bookings_path` |
| Parameters | Opciones de la consulta: fecha, días, categoría y página | `[libcal.query]` |
| Response / Example | Estructura de los datos devueltos | `response_path` y `[libcal.fields]` |
| Limit / Offset / Page | Cómo pedir todos los registros cuando hay varias páginas | `pagination` y las plantillas de consulta |

**No tienes que crear esos elementos.** Ya aparecen en la documentación de LibCal. Los nombres del TOML son un ejemplo editable y deben coincidir con los que muestre tu instancia. Verifica también cómo solicitar **cancelaciones**: omitir un filtro no garantiza que el proveedor las devuelva.

El código institucional puede ser un campo de autenticación o una respuesta del formulario. Hay que mapear ese campo exacto, evitando usar un correo como sustituto. Las rutas con puntos permiten acceder a campos dentro de objetos, por ejemplo `patron.code`. Check-in/check-out solo deben mapearse si la respuesta contiene fechas ISO, no indicadores de sí/no.

Para que pueda ayudarte, puedes compartir **el texto de documentación de esa consulta**: nombres de parámetros y descripción de campos. No necesitas fabricar un ejemplo ni ejecutar solicitudes a mano. Si prefieres una captura, oculta Client ID, Client Secret, tokens y cualquier dato personal. Nunca compartas la pantalla de credenciales sin ocultarlos.

Si la respuesta devuelve un ID de categoría, añade `category_id = "nombre_del_campo"` a `[libcal.fields]` para verificar automáticamente que cada consulta retorna la categoría correcta.

## 4. Preparar Google Sheets

### Crear la hoja y el acceso de escritorio

1. Crea una **hoja nueva de prueba** desde tu cuenta de Google. Mantén acceso restringido al equipo correspondiente.
2. Copia su identificador: en `https://docs.google.com/spreadsheets/d/IDENTIFICADOR/edit`, es el segmento `IDENTIFICADOR`. Ponlo en `google.spreadsheet_id`.
3. En [Google Cloud Console](https://console.cloud.google.com/), crea o selecciona un proyecto para el piloto.
4. En **APIs & Services → Library**, habilita **Google Sheets API**.
5. En **Google Auth platform → Branding**, configura el nombre y contacto de la aplicación.
6. En **Audience**, elige **Internal** si tu organización Workspace lo permite. Si usas una aplicación **External** en pruebas, añade tu cuenta como usuario de prueba.
7. En **Data Access**, configura el alcance de Sheets `https://www.googleapis.com/auth/spreadsheets` cuando la consola lo requiera.
8. En **Clients → Create Client**, selecciona **Desktop app**. Descarga el JSON y guárdalo como `secrets/google-client.json` dentro del proyecto en Ubuntu.

Este es el flujo de escritorio descrito en las guías oficiales de [Google Sheets](https://developers.google.com/workspace/sheets/api/quickstart/python) y [credenciales OAuth](https://developers.google.com/workspace/guides/create-credentials). No necesitas una clave API de Google ni una cuenta de servicio para este piloto.

Si la descarga quedó en Windows, copia el archivo desde el Explorador a la carpeta `secrets` del proyecto en WSL y cámbiale el nombre. Evita subirlo al repositorio.

### Autorizar desde Windows

En Ubuntu:

```bash
python -m alma_libcal auth-google
```

La terminal mostrará un enlace. Ábrelo en el navegador de Windows, elige la cuenta con permiso de edición sobre la hoja y autoriza la aplicación. Mantén la terminal abierta mientras el navegador regresa a `localhost:8765`. El programa esperará hasta cinco minutos y guardará `secrets/google-token.json`.

Si el puerto está ocupado, usa `auth-google --port 8766`. Si el navegador no puede volver a localhost, revisa el acceso local de Windows a WSL antes de reintentar. Si el acceso vence o quieres cambiar de cuenta, ejecuta `auth-google` nuevamente.

## 5. Primera prueba con tus sistemas

Empieza con un solo día y una fuente a la vez:

```bash
python -m alma_libcal sync --only prestamos --extract-only --from 2026-10-06 --to 2026-10-06
python -m alma_libcal sync --only renovaciones --extract-only --from 2026-10-06 --to 2026-10-06
python -m alma_libcal sync --only reservas --extract-only --from 2026-10-06 --to 2026-10-06
python -m alma_libcal status
```

Compara préstamos, **suma de `quantity` en renovaciones** y reservas por categoría/estado con los reportes originales usando los mismos filtros. Alma puede tardar hasta su siguiente actualización de Analytics en mostrar el día de prueba. Una extracción vacía no demuestra por sí sola que no hubo actividad.

Con los datos comprobados:

```bash
python -m alma_libcal publish
```

El programa crea o actualiza `prestamos`, `renovaciones`, `reservas` y `control`. Repite la extracción y verifica que no haya duplicados. En una reserva de prueba autorizada por ti, cambia el estado desde LibCal y reconsulta su fecha para comprobar la actualización. El programa nunca modifica reservas o préstamos.

## 6. Diagnósticos comunes

| Mensaje | Acción |
| --- | --- |
| Falta una variable de entorno | Introduce y exporta esa credencial en la terminal actual |
| HTTP 401/403 | Revisa credenciales, permisos y región de origen |
| Falta un campo / formato inesperado | Verifica el mapa de columnas o la estructura de respuesta |
| Claves duplicadas en Alma | Corrige la granularidad del reporte; no agregues dimensiones que separen préstamo/día |
| LibCal repitió una página | Confirma cómo funciona la paginación en Admin → API |
| Publicación fallida | Corrige el acceso a Google y ejecuta `publish`; no se perdió SQLite |
| Otra ejecución usa el histórico | Espera a que termine; el bloqueo se libera al cerrar el proceso |

`status` muestra errores sin imprimir credenciales ni registros personales. Comparte esos mensajes y los nombres de campos si necesitas ayuda.
