# 03 — Completar extracción y validar publicación

Python, credenciales locales y Google Sheets ya están preparados. Aquí quedan únicamente la explicación de archivos y los pasos pendientes después de validar [Alma](01-alma.md) y [LibCal](02-libcal.md).

## Cómo se usan los dos archivos

**Sí, se usan juntos.** El programa lee `config.toml` y carga automáticamente el `.env` situado en su misma carpeta.

| Archivo | Qué contiene | Ejemplo sin secretos |
| --- | --- | --- |
| `.env` | Valores de las credenciales | `ALMA_API_KEY=valor_privado` |
| `config.toml` | Rutas, URLs, IDs y mapas; referencias a las variables de credenciales | `api_key_env = "ALMA_API_KEY"` |

En el ejemplo, `api_key_env` significa «busca la variable ALMA_API_KEY». **No es otra clave ni una copia de su valor.** Lo mismo ocurre con `client_id_env = "LIBCAL_CLIENT_ID"` y `client_secret_env = "LIBCAL_CLIENT_SECRET"`.

Edita `.env` para cambiar una credencial; edita `config.toml` para cambiar una ruta, categoría o columna. Ninguno de los dos archivos locales se sube a Git. Las variables exportadas en la terminal tienen prioridad sobre `.env`; si conservas un valor antiguo exportado, abre otra terminal antes de probar.

## Ejecutar comandos directamente

Desde la carpeta del proyecto:

```bash
.venv/bin/python -m alma_libcal --help
```

`.venv/bin/python` es el Python del proyecto, con las dependencias de Google ya instaladas. No necesitas activar el entorno ni utilizar un script adicional. `.venv` se conserva para que esas dependencias sigan disponibles.

## Trabajo pendiente en el programa

Una vez verificadas las columnas/respuestas reales:

1. Completar los mapas de Alma y las categorías de LibCal con los valores reales.
2. Ampliar conectores, modelos, almacenamiento y salida para conservar correo, atributos del ejemplar y respuestas del formulario.
3. Verificar formatos de fechas y clasificación de préstamos; conservar usos internos sin usuario y renovaciones por campus.
4. Comparar un día de Alma y hoy en LibCal con los reportes originales.
5. Repetir la extracción y confirmar que no duplica registros.

Estas son tareas de desarrollo; no necesitas programarlas para preparar los análisis. Todavía no ejecutes una carga completa esperando obtener todas tus columnas.

## Validar la publicación ya configurada

Después de la adaptación, extraeremos primero con `--extract-only`. Compararemos los registros guardados y publicaremos una muestra en tu hoja existente usando `publish --only prestamos`, seguido de los demás conjuntos validados. Ambos subcomandos se ejecutan con `.venv/bin/python -m alma_libcal`.

La publicación reemplaza las pestañas seleccionadas con el histórico local; las fechas de extracción no limitan lo que se publica. Los reportes permanecen separados. Antes de una carga grande evaluaremos el límite actual de 1,8 MB por solicitud.

La automatización periódica, la fuente histórica de LibCal y el cruce con la universidad son posteriores a esta validación. No hace falta repetir la autorización de Google para avanzar.
