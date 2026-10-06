# Diseño del piloto Alma y LibCal

## Decisiones acordadas

- Ejecución manual en Ubuntu sobre WSL2; sin tareas programadas.
- Alma: préstamos y renovaciones manuales/autoservicio por su fecha de actividad.
- LibCal Spaces: todas las reservas, incluidas canceladas, de computadoras/laptops, espacios grupales y Kindle, por inicio del uso reservado.
- Código institucional de usuario compartido por ambos sistemas; códigos ausentes quedan explícitos. No se incorporan nombres ni correos al piloto.
- Inicio el 6 de octubre de 2026, zona America/Lima. Integración retrospectiva de 2026 posterior, por intervalos y sin duplicaciones.
- Python, SQLite y Google Sheets. La hoja es una salida; el histórico local permite republicar y cambiar de consumidor.

## Flujo

El comando `sync` consulta dos reportes de Alma Analytics y reservas de LibCal. Completa paginación y valida claves, fechas y granularidad antes de confirmar cada conjunto en SQLite. Un fallo de extracción conserva sus datos anteriores y permite continuar con los otros conjuntos.

Las claves son identificador de préstamo, préstamo/fecha para renovaciones e identificador de reserva para LibCal. Las renovaciones conservan cantidades si el reporte ofrece agregados diarios. Reconsultar el intervalo actualiza datos tardíos y estados; la ausencia de registros no elimina el histórico.

Google publica pestañas seleccionadas y control en un único batch atómico. Un fallo queda pendiente para el comando `publish`, que usa SQLite sin nuevas consultas a las fuentes. Un bloqueo impide ejecuciones simultáneas sobre la misma base.

## Verificación

Pruebas locales con respuestas ficticias: paginación, tres categorías, duplicados, intervalos, códigos como texto, reservas canceladas, errores de publicación y recuperación. La aceptación real exige comparar conteos y cantidades contra los reportes institucionales y validar el contrato LibCal en Admin → API.

## Etapas posteriores

Carga retrospectiva del año, evaluación del volumen de publicación, respaldo del histórico y traslado a VPS con credenciales apropiadas y ejecución periódica. Power BI y aplicación web quedan fuera del piloto.

## Estado de integración

El acceso de Alma y Google se basa en documentación oficial. Las rutas, parámetros y campos de LibCal se configuran mediante una plantilla que requiere contraste con la documentación de la instancia. Ninguna conexión institucional ha sido validada sin sus accesos. El entorno actual no proporciona un repositorio Git operativo, por lo que este documento se guarda sin commit.
