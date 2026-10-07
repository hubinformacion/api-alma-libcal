# 00 — Inicio y orden de trabajo

**Empieza por crear el reporte de préstamos en Alma Analytics.** No hace falta configurar claves, Google ni la base universitaria para realizar esa primera tarea.

## Qué hará el proyecto

Alma aporta préstamos y renovaciones; LibCal aporta reservas. El programa consultará esos sistemas y guardará sus registros. Después completaremos los datos de usuarios desde la base universitaria y publicaremos los reportes por separado. La programación llegará después de validar una extracción manual y definir cómo conservar los cambios. El endpoint de LibCal documentado ignora fechas pasadas; su carga histórica necesita otra fuente.

En Alma, **sí: la API leerá un análisis guardado en Analytics**, identificado por su ruta. No necesitas desarrollar una API ni publicar un dashboard.

## Sigue este orden

| Orden | Documento | Dónde trabajar | Resultado |
| --- | --- | --- | --- |
| 01 | [Alma: reportes y acceso](01-alma.md) | Alma Analytics; después Developer Network | `Loans` y `Renewals` comprobados, rutas y clave de lectura |
| 02 | [LibCal: reservas y acceso](02-libcal.md) | Administración de LibCal | Credenciales y campos de reservas identificados |
| 03 | [Programa y Google Sheets](03-programa-y-sheets.md) | Ubuntu/WSL2; después Google Cloud | Inspección, adaptación del extractor y prueba de publicación |

**Tu tarea ahora:** abre el documento 01 y completa únicamente su sección «Crear Loans desde cero». Termina cuando puedas ver registros de un día conocido con un identificador de préstamo por fila. Después prepara renovaciones.

## De dónde saldrá cada dato

| Datos | Fuente |
| --- | --- |
| Operación, fecha, ejemplar/recurso, sede de la operación, estado | Alma o LibCal |
| Identificador y correo originales para buscar al usuario | Alma o LibCal; conservados sin asumir que son correctos |
| Nombre, tipo de usuario, modalidad, campus del usuario, programa, departamento, unidad de negocio | Base universitaria, en la etapa posterior |
| Mes, número de mes, hora entera y duración reservada | Cálculos del programa a partir de fechas/horas de origen |

Los usos internos de Alma se identifican por `In House Loan Indicator = Y`; si no tienen usuario, no intentaremos cruzarlos con la base universitaria. Las renovaciones se reportarán por el campus de renovación.

Un DNI solo se usará cuando confirmemos qué campo lo contiene. No lo deduciremos del correo ni asumiremos que todo identificador es DNI. Los casos sin coincidencia quedarán pendientes de revisión.

Los CSV de [database/](database/) documentan la arquitectura institucional. Incluyen dimensiones como `dbo.DIM_PERSONA`, `dbo.DIM_ESTUDIANTE` y `dbo.DIM_DOCENTE`, y candidatos como `COD_DOCUMENTO`, `PIDM` y `CORREO_CORPORATIVO`. Aún debemos verificar uniones, unicidad y vigencia académica. La VPN y las credenciales Windows corresponden a esa etapa posterior.

## Qué está listo y qué falta

Existe un piloto en Python con SQLite y publicación en Google Sheets. **Todavía no guarda todos los campos definidos en estas guías**, entre ellos el correo y varios atributos del ejemplar/formulario. Primero verificaremos los reportes; luego adaptaremos el código antes de una extracción completa.

Estas cuatro guías sustituyen las instrucciones anteriores. La configuración de ejemplo es una plantilla técnica y no confirma los campos de tu institución.
