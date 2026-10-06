# Alma + LibCal → Google Sheets

Piloto de extracción **manual** para Ubuntu en WSL2. Lee préstamos y renovaciones de Alma Analytics y reservas de las categorías **Computadoras y laptops**, **Espacios grupales** y **Kindle** de LibCal. Conserva el histórico en SQLite y publica una hoja para análisis posteriores.

No necesitas crear una API: debes registrar accesos a las APIs que ya ofrecen ambos sistemas. La configuración real se hace siguiendo [la guía paso a paso](docs/configuracion.md). No compartas contraseñas, claves ni archivos de autorización por el chat.

## Primero: probar sin cuentas ni credenciales

Desde la carpeta del proyecto, en Ubuntu:

```bash
python3 --version
PYTHONPATH=src python3 -m alma_libcal demo
```

Requiere Python **3.12 o posterior**. La demostración no usa red ni Google: produce `demo-output/pilot.sqlite3` y `demo-output/sheets.json` con datos ficticios. Incluye dos préstamos, una fila de renovaciones con cantidad dos y tres reservas, una cancelada. Puedes repetirla: los registros no se duplican.

## Instalar para usar Google Sheets

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[google]"
cp config.example.toml config.toml
mkdir -p secrets
chmod 700 secrets
```

Si Ubuntu informa que falta `venv`, instala el paquete `python3-venv` correspondiente a tu versión de Python. El núcleo y las pruebas no necesitan paquetes externos; la autorización de Google usa las dependencias opcionales.

## Comandos del piloto

Con el entorno activado y la configuración preparada:

```bash
# Autorizar Google desde el navegador de Windows.
python -m alma_libcal auth-google

# Extraer sin publicar: útil para la primera comparación.
python -m alma_libcal sync --extract-only --from 2026-10-06 --to 2026-10-06

# Extraer y publicar; por defecto, desde el arranque hasta hoy en Lima.
python -m alma_libcal sync

# Extraer solo un conjunto.
python -m alma_libcal sync --only reservas --extract-only

# Reintentar la publicación desde SQLite, sin consultar Alma ni LibCal.
python -m alma_libcal publish

# Consultar conteos, fechas, errores y publicaciones pendientes.
python -m alma_libcal status
```

Un archivo alternativo se selecciona **antes** del subcomando: `python -m alma_libcal --config otra-config.toml sync`. Las rutas dentro del TOML son relativas a ese archivo.

`publish` siempre publica todo el histórico local de los conjuntos elegidos. Usa `--only` para republicar conjuntos específicos. Las opciones de fechas de `sync` delimitan la extracción, no recortan el histórico que se publica.

## Datos y comportamiento

| Pestaña | Granularidad / clave |
| --- | --- |
| `prestamos` | Una fila por identificador del préstamo |
| `renovaciones` | Una fila por préstamo y fecha de renovación; `quantity` conserva la cantidad |
| `reservas` | Una fila por identificador de reserva, con categoría y estado |
| `control` | Estado por conjunto, revisión, conteos, actualización de origen y errores |

Los códigos institucionales permanecen como texto, incluidos sus ceros iniciales. Los códigos ausentes se dejan vacíos y se marcan mediante `user_id_missing`; no se sustituyen por correos ni se inventan asociaciones. El piloto identifica personas por código: no incorpora nombres o correos de usuarios.

Las fechas deben llegar en ISO 8601. Las fechas con hora y zona se convierten a Lima; las horas sin zona se interpretan en la zona configurada. En LibCal se filtra por el inicio del uso reservado, no por la creación de la reserva. Check-in/check-out ausentes permanecen vacíos.

Cada ejecución vuelve a consultar su intervalo. Los registros se actualizan por clave y se conserva el resto del histórico. **La ausencia de un registro en una respuesta no lo elimina**: tampoco permite deducir que fue cancelado. Para reflejar cancelaciones, la API debe devolverlas con su estado y debe reconsultarse la fecha de la reserva.

Una extracción solo se guarda después de terminar todas sus páginas; en LibCal, deben completarse las tres categorías. Si falla un conjunto, los demás pueden publicarse y su histórico previo queda intacto. La publicación reemplaza las pestañas seleccionadas y `control` en una única operación atómica; las otras pestañas se conservan. Las pestañas administradas son salidas del proceso: las ediciones manuales de sus valores se reemplazan en la siguiente publicación.

## Límites del piloto

- Alma Analytics tiene una carga diaria: puede faltar actividad de hoy hasta su siguiente actualización. Se conservan las fechas de actualización cuando el reporte las incluye. [Documentación](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_%28English%29/080Analytics/010Introduction/Analytics_Database_Refresh).
- Solo se incluyen renovaciones manuales y por autoservicio. No se cuentan renovaciones automáticas por día.
- La configuración de LibCal es una plantilla editable. Sus parámetros, campos y acceso a cancelaciones requieren verificación en **Admin → API** de tu instancia; no se han validado contra tu cuenta.
- Para evitar borrar datos antes de una escritura fallida, la publicación tiene un límite local de **1,8 MB por solicitud**. Si se supera, queda pendiente y el histórico sigue en SQLite. Antes de cargar todo 2026 habrá que evaluar el volumen y ampliar el publicador si es necesario.
- La autorización es de escritorio. La migración a VPS deberá revisar autorización, respaldo y ejecución periódica. Este proyecto no instala tareas programadas.

La carga retrospectiva queda soportada por intervalos, pero no se ejecuta automáticamente:

```bash
python -m alma_libcal sync --extract-only --from 2026-01-01 --to 2026-10-06
```

La recuperación histórica de códigos de usuario depende también de las políticas de anonimización y retención de los sistemas de origen.

## Desarrollo y pruebas

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m compileall -q src tests
```

Las pruebas usan `unittest`, respuestas ficticias y bases temporales. Verifican paginación, duplicados, cancelaciones, renovaciones, intervalos históricos, errores y publicación. La comparación con los reportes institucionales es una verificación adicional obligatoria antes de confiar en los resultados reales.

El código está en `src/alma_libcal/`, los conectores en `connectors/`, las pruebas en `tests/` y las instrucciones en `docs/`. Estilo: cuatro espacios, nombres `snake_case` y diagnósticos sin credenciales ni datos personales. No hay umbral de cobertura configurado.
