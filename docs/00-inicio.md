# 00 — Empieza aquí: verificar datos

La configuración básica de Python, credenciales, reportes de Alma, categorías de LibCal y Google Sheets está preparada. Ahora comprobamos si los registros y cantidades coinciden con los reportes de los sistemas. Todavía faltan algunas columnas del reporte final; el cruce con usuarios de la universidad y la automatización vendrán después.

## Orden de trabajo

1. [01 — Alma](01-alma.md): extraer un día de préstamos y renovaciones y compararlo con Analytics.
2. [02 — LibCal](02-libcal.md): consultar cantidades o guardar reservas del día y compararlas con su reporte administrativo.
3. [03 — Ver los datos](03-ver-datos.md): abrir SQLite en Antigravity o llevar lo guardado a Sheets para verlo por columnas.

Ejecuta los comandos desde la terminal de Antigravity, en la carpeta del proyecto:

```bash
cd /home/asus/projects/api-alma-libcal
```

El comienzo `.venv/bin/python -m alma_libcal` llama al programa con el Python que ya tiene sus dependencias. Copia el comando completo; no necesitas activar un entorno.

## Qué hay en cada carpeta

| Ruta | Para qué sirve |
| --- | --- |
| `docs/00…03` | Estas cuatro guías de verificación |
| `data/pilot.sqlite3` | Un archivo local con los registros guardados de los tres conjuntos |
| `src/alma_libcal/` | Código del programa; no necesitas editarlo para verificar datos |
| `tests/` | Pruebas del programa |
| `.env` y `config.toml` | Credenciales y configuración ya preparadas |
| `secrets/` | Autorización de Google |
| `docs/1_1.yml` y `docs/database/` | Referencias técnicas para el desarrollo posterior |

`data/` está excluida de Git, pero existe en disco y puede abrirse desde el editor. No hay un archivo SQLite por sistema: `dataset` distingue `prestamos`, `renovaciones` y `reservas` dentro de la misma base.

## Por qué existe `secrets/`

`.env` contiene claves de Alma y LibCal. `secrets/google-client.json` contiene la configuración OAuth de Google y `secrets/google-token.json` conserva la autorización obtenida al iniciar sesión. La biblioteca de Google admite credenciales de usuario en JSON; el programa lee estos archivos y actualiza el token cuando lo renueva. [Referencia de Google](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.credentials.html#google.oauth2.credentials.Credentials.from_authorized_user_file).

No es obligatorio que todas las credenciales estén en `.env`. `secrets/` es el nombre elegido para agrupar estos archivos locales; cambiarlo no mejora su protección. `.gitignore` ya excluye `secrets/`, `.env`, `config.toml` y `data/`, y comprobamos que los archivos privados no están registrados en Git. Las plantillas `config.example.toml` y `.env.example` sí se publican, sin valores privados. Una futura instalación tendrá que aportar sus propias credenciales.

## Consultar, guardar y publicar

- `inspect-alma`: muestra columnas, sin guardar registros.
- `check-libcal`: muestra cantidades y estados, sin guardar reservas.
- `sync ... --extract-only`: consulta el sistema y guarda los registros en SQLite.
- `status`: muestra cantidades del histórico local y el estado de las ejecuciones.
- `publish --only ...`: envía el histórico guardado a Google Sheets.

Empieza con una fecha y un conjunto. Una consulta vacía no demuestra por sí sola un error: compárala con el reporte del sistema para la misma fecha.

## Primera muestra guardada el 8 de octubre de 2026

| Conjunto | Fecha de operaciones | Filas guardadas | Cantidad a comparar |
| --- | --- | ---: | ---: |
| Préstamos | 2026-10-07 | 198 | 198 préstamos/usos internos |
| Renovaciones | 2026-10-07 | 10 | Suma de quantity: 10 |
| Reservas | 2026-10-08 | 3 | 3 reservas al momento de consultar |

Estas muestras están en SQLite. También preparamos copias CSV en `data/verificacion/` y un `resumen.csv` por fecha/campus/categoría/estado. Empieza comparando esta muestra con los reportes originales. Las reservas del día pueden aumentar o cambiar de estado.
