# 01 — Alma: crear los reportes y habilitar su lectura

## Qué vamos a crear

Dos análisis del área **Fulfillment**, guardados como `Loans` y `Renewals`. El programa leerá cada uno mediante la API de Analytics. Tu reporte habitual puede seguir disponible; crearemos análisis nuevos para extraer los datos de origen.

| Análisis | Qué representa | Fecha que filtra | Cómo contar |
| --- | --- | --- | --- |
| `Loans` | Un préstamo por `Item Loan ID` | `Loan Date` | Préstamos distintos, después de verificar que no hay filas duplicadas |
| `Renewals` | Cantidad de renovaciones por préstamo, día y campus de renovación | `Renewal Date` | Suma de `Renewals`, no número de filas |

Por ejemplo, un préstamo del 10 de enero renovado el 17 cuenta como préstamo el día 10 y renovación el día 17. No cambia de categoría ni se convierte en un préstamo nuevo.

Ex Libris recomienda separar estos reportes por sus fechas; admite combinarlos mediante filtros más complejos, pero aquí usaremos dos análisis para comprobar los conteos por separado. [Referencia oficial de Fulfillment](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_(English)/080Analytics/Alma_Analytics_Subject_Areas/Fulfillment).

## Crear Loans desde cero

**Dónde:** Alma → **Analytics → Design Analytics**. Las etiquetas pueden aparecer traducidas. Si no ves esta opción, solicita acceso para diseñar análisis.

1. En Analytics, selecciona **New → Analysis → Fulfillment**.
2. En **Criteria**, expande las carpetas del panel izquierdo y añade las columnas de la tabla siguiente, normalmente con doble clic.
3. Conserva inicialmente los nombres originales. Los nombres en la primera columna son los que usaremos al preparar la extracción; no tienes que escribir fórmulas para renombrarlos ahora.
4. En **Filters**, añade **Loan Date → Loan Date → is between** y selecciona un día conocido con actividad y ya cargado en Analytics.
5. Abre **Results** y comprueba que `Item Loan ID` aparece una sola vez por préstamo.
6. Guarda con **Save As** en **Shared Folders → carpeta institucional → Integraciones Biblioteca → Loans**. Si falta la carpeta, créala donde tengas permiso o solicita que la creen.

### Columnas de Loans

Estas columnas cubren la operación y los datos del ejemplar de tu reporte, además de las claves necesarias para actualizar registros y cruzar usuarios después.

| Nombre que usaremos | Carpeta → columna en Fulfillment | Uso |
| --- | --- | --- |
| `loan_id` | Loan Details → Item Loan ID | Identificador único del préstamo |
| `source_user_id` | Borrower Details → User Primary Identifier | Identificador original para el cruce futuro |
| `source_user_email` | Preferred Contact Information → Preferred Email | Correo original para el cruce futuro |
| `item_id` | Loan Details → Item ID | Identificador del ejemplar |
| `item_mms_id` | Loan Details → MMS ID | Identificador bibliográfico |
| `item_barcode` | Loan Details → Barcode | Código de barras |
| `item_material_type` | Loan Details → Material Type | Tipo de material |
| `item_policy` | Physical Item Details → Item Policy | Política registrada en el ejemplar |
| `item_title` | Loan Details → Title | Título |
| `loan_date` | Loan Date → Loan Date | Fecha original del préstamo; elegir la columna simple de fecha |
| `loan_time` | Loan Details → Loan Time | Hora original completa |
| `in_house_loan_indicator` | Loan Details → In House Loan Indicator | Base para distinguir uso en sala y préstamo regular |
| `loan_campus_code` | Loan Circulation Desk → Campus Code | Código de sede de la operación |
| `loan_campus` | Loan Circulation Desk → Campus Name | Nombre de sede de la operación |
| `loan_library_code` | Loan Circulation Desk → Library Code | Biblioteca de la operación |
| `loan_desk_code` | Loan Circulation Desk → Circ Desk Code | Código del módulo de circulación |
| `loan_desk_name` | Loan Circulation Desk → Circ Desk Name | Nombre del módulo |
| `loan_desk_description` | Loan Circulation Desk → Circ Desk Desc | Descripción del módulo |
| `loan_status` | Loan Details → Loan Status | Estado original para control |

Las carpetas y campos proceden de la referencia oficial enlazada arriba. **Loan Time está en Loan Details**; la guía anterior lo situaba incorrectamente en Loan Date. Si alguna etiqueta difiere en tu interfaz, anota la que aparece antes de sustituirla por otro campo.

Como controles adicionales, añade **Loan → Num of Loans (In house + Not In House)** y **Institution → Data updated as of / Data available as of**, si están disponibles. Los identificadores y códigos se tratarán como texto para preservar ceros iniciales y números largos. `Item Policy` no demuestra por sí sola cuál era la política histórica del préstamo.

### Reglas de Loans

- Usa la fecha del préstamo para seleccionar el período. No añadas `Renewal Date`, `Last Renewal Date` ni un filtro de renovaciones a este análisis.
- Conserva estados de origen; no filtres únicamente préstamos activos, porque perderías los ya devueltos. Los eliminados deben identificarse por estado y revisarse antes del conteo final.
- No añadas múltiples correos, direcciones ni categorías del usuario que multipliquen una operación. Si se repite `Item Loan ID`, revisa las columnas antes de importar.
- No necesitas `user_name`, `user_type`, `user_modality`, `user_campus`, `user_program`, `user_department` ni `user_business_unit`: vendrán de la base universitaria. El correo y el identificador de Alma son claves candidatas, no identidad verificada.
- No calcules mes ni hora entera en Analytics. Conserva fecha/hora originales y después derivaremos `loan_month`, `loan_month#` y `loan_hour` en el programa.

### Qué hacer con tus reglas actuales

#### Uso interno sin usuario

**Sí, usa el mismo indicador `In House Loan Indicator = 'Y'`.** No uses la ausencia de usuario para decidir: un préstamo regular también puede tener datos ausentes o anonimizados.

Tu fórmula mezcla una etiqueta de actividad con un identificador de persona. Puedes conservarla en el reporte visual habitual, pero en la extracción separaremos las columnas:

- `source_user_id`: **Borrower Details → User Primary Identifier**, sin sustituirlo por «Uso interno» ni aplicarle `LOWER`.
- `in_house_loan_indicator`: **Loan Details → In House Loan Indicator**, conservando `Y`, `N` o vacío.
- `usage_type`: etiqueta derivada por el programa. Si la quieres ver también en Analytics, añade una columna calculada con esta fórmula:

```sql
CASE
  WHEN "Loan Details"."In House Loan Indicator" = 'Y' THEN 'Uso interno'
  ELSE 'Préstamo'
END
```

Un uso interno sin usuario conserva su operación y queda fuera del cruce institucional; no creamos un usuario llamado «Uso interno». El programa distingue ese caso de un préstamo regular sin identificador. Mantén los usos internos al filtrar: no exijas identificador o correo no nulos.

La comprobación de que `loan_id` no se repite en tu día de prueba es correcta. Repite la revisión cuando añadas columnas o amplíes el período.

Conserva tu análisis habitual como referencia. En **Criteria → menú de columna → Edit Formula**, copia únicamente las fórmulas de `loan_type` y `loan_description`, sin registros personales, para revisarlas.

Una regla como «si tiene renovaciones, clasificar como renovación; si no, préstamo» no sirve para obtener ambos movimientos: un mismo préstamo puede generar varias renovaciones y debe conservar su operación original.

Para este análisis nuevo no necesitas esa regla. `Loans` identifica el tipo de operación. Más adelante construiremos tu etiqueta `loan_type` a partir de campos comprobados:

- `In House Loan Indicator`: `Y` indica uso en sala; `N` o nulo, préstamo regular, según la documentación de Alma.
- Para distinguir bibliotecario y autoservicio, la documentación utiliza el nombre del operador del préstamo (`Loaned By / Loan Operator Details → User Name`). Añádelo solo si necesitas esa distinción; verificaremos sus valores y la fórmula existente antes de asignar etiquetas. `Has Self Check` indica que una mesa dispone de máquina, no quién realizó cada operación.
- Para `loan_description`, compararemos `Circ Desk Name` y `Circ Desk Desc` con tus módulos. No lo sustituiremos por `Loan Details → Description` solo porque se llama parecido.

Así evitamos inventar una fórmula que cambie el significado de «Préstamo regular por bibliotecario».

## Crear Renewals después de comprobar Loans

**Dónde:** el mismo editor de Alma Analytics.

1. Crea otro análisis: **New → Analysis → Fulfillment**.
2. Añade las columnas de esta tabla. Los campos de usuario/ejemplar tienen el mismo origen que en `Loans`.
3. En **Filters**, usa **Renewal Date → Renewal Date → is between** para el día de prueba. Añade también **Loan → Renewals > 0**.
4. No filtres por `Loan Date`: el préstamo que se renovó ese día puede ser mucho más antiguo.
5. Abre **Results**, verifica las fechas y compara la **suma de Renewals** con renovaciones conocidas.
6. Guarda en la misma carpeta compartida con el nombre `Renewals`.

### Columnas de Renewals

| Columnas | Origen / tratamiento |
| --- | --- |
| `loan_id`, `source_user_id`, `source_user_email` | Mismos campos de Loans |
| `item_id`, `item_mms_id`, `item_barcode`, `item_material_type`, `item_policy`, `item_title` | Mismos campos de Loans |
| `renewal_date` | Renewal Date → Renewal Date; columna simple de fecha |
| `renewal_quantity` | Loan → Renewals; conservar la agregación definida por Alma |
| `loan_status` | Loan Details → Loan Status; estado del préstamo, no estado de cada renovación |
| `renewal_campus_code` | Renewal Circulation Desk → Campus Code; necesario para separar campus |
| `renewal_campus` | Renewal Circulation Desk → Campus Name; necesario para el reporte por campus |
| Fechas de actualización, si están disponibles | Institution → Data updated as of / Data available as of |

El objetivo es una fila por **préstamo + día + campus de renovación**, con su cantidad. Si se renovó dos veces ese día en el mismo campus, la cantidad puede ser dos: no inventaremos dos filas con horas desconocidas.

**Incluye ambos campos de campus.** Se refieren a dónde se renovó, no al campus del usuario ni al lugar del préstamo original. Para canales sin mesa/campus informado, deja el campus vacío y repórtalo como «Sin campus informado»; no lo asignes automáticamente a la sede del préstamo.

En `[alma.renovaciones.fields]` de `config.toml`, mapea `site` al nombre del campus de renovación y `site_id` a su código. El programa ya distingue las claves préstamo/día/campus cuando `site_id` está configurado. Si tienes un histórico anterior con claves préstamo/día, habrá que migrarlo antes de reextraer con la nueva clave para no mantener ambas versiones.

No añadas aún el módulo de renovación: podría multiplicar filas del mismo préstamo/día/campus. No copies la hora del préstamo como hora de renovación.

### La limitación de renovaciones automáticas

**Renewals** cuenta renovaciones manuales y mediante máquinas de autoservicio. **Auto Renewals** es otra medida: Analytics no la asocia con una fecha y no admite combinarla con la carpeta **Renewal Date**. Por eso no podemos incluirla en un conteo diario o semanal fechado de la misma manera. Tampoco podemos reconstruir todas las renovaciones usando solo **Last Renewal Date**. [Reglas oficiales](https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/010Alma_Online_Help_(English)/080Analytics/Alma_Analytics_Subject_Areas/Fulfillment).

Esta es una limitación de los datos analíticos, no una regla que debas activar para permitir renovaciones en Alma. Empezaremos con las renovaciones que sí se pueden fechar. Si luego necesitas las automáticas, evaluaremos una fuente adicional o un reporte acumulado separado, identificado como tal.

## Dejar los análisis listos para la API

Cuando hayas comprobado ambos análisis:

1. En `Loans`, reemplaza el filtro fijo de prueba por **Loan Date → Loan Date → is prompted**.
2. En `Renewals`, haz lo mismo con **Renewal Date → Renewal Date → is prompted**. Conserva `Renewals > 0`.
3. Guarda los cambios. No dejes también un filtro fijo de un día o «mes actual»: limitaría las consultas futuras.
4. Anota la expresión de fecha con los pasos de abajo y la ruta de catálogo de cada análisis.

### Qué significa «expresión exacta de la fecha»

Es el nombre técnico que Analytics utiliza para la columna. **No necesitas copiar todo el XML.**

1. Abre el análisis en modo **Edit → Criteria**.
2. En la columna de fecha, abre su menú y selecciona **Edit Formula**.
3. Copia el contenido de **Column Formula** y cierra sin modificarlo.
4. En `config.toml`, pega esa expresión en `date_column` del análisis correspondiente. Por ejemplo, si esas son las expresiones que muestra tu análisis:

```toml
[alma.prestamos]
report_path = "/shared/Universidad Continental 51UCCI_INST/Reports/TSI/API/Loans"
date_column = '"Loan Date"."Loan Date"'

[alma.renovaciones]
report_path = "/shared/Universidad Continental 51UCCI_INST/Reports/TSI/API/Renewals"
date_column = '"Renewal Date"."Renewal Date"'
```

Edita las secciones existentes, no añadas otras con el mismo nombre. En **Advanced → Analysis XML** también aparece la expresión dentro de `sawx:sqlExpression`, pero el menú de fórmula es más sencillo.

**La ruta API empieza con `/shared/`.** «Shared Folders» es la etiqueta de pantalla; `/Shared Folders/…` no es la ruta que enviamos a la API. Verifica el resto del recorrido en el catálogo o el parámetro `path` de la URL del análisis.

El programa enviará el intervalo de fechas. La API requiere reportes en carpetas compartidas y puede devolver nombres/orden de columnas distintos de los visuales: verificaremos el mapeo, no lo deduciremos del orden de esta tabla. [Rutas, columnas y filtros de la API](https://developers.exlibrisgroup.com/blog/Working-with-Analytics-REST-APIs/).

## Crear la clave de lectura

**Dónde:** [Ex Libris Developer Network](https://developers.exlibrisgroup.com/), con una cuenta vinculada a tu institución.

1. Abre [Manage API Keys](https://developers.exlibrisgroup.com/manage/keys/) y selecciona **Add API Key**.
2. Nombre sugerido: `Reportes Biblioteca - Analytics`.
3. Añade acceso **Analytics / Production / Read-only** y guarda la clave en un lugar privado.
4. Anota el host API regional indicado para tu institución. La región depende de dónde está alojado Alma.

Si solo aparece un sandbox o no puedes seleccionar tu institución, solicita al administrador la vinculación y el permiso. [Acceso oficial a las APIs de Alma](https://developers.exlibrisgroup.com/alma/apis/).

Usaremos **GET /almaws/v1/analytics/reports** con la ruta del análisis. El programa se encargará del filtro y las páginas; no necesitas construir la URL manualmente. [Referencia de consulta](https://developers.exlibrisgroup.com/alma/apis/docs/analytics/R0VUIC9hbG1hd3MvdjEvYW5hbHl0aWNzL3JlcG9ydHM%3D/).

## Cuándo está completo este paso

- `Loans` muestra operaciones del día elegido, sin duplicar `Item Loan ID`.
- `Renewals` muestra cantidades por fecha y campus de renovación, sin usar la fecha original para seleccionar el período.
- Ambos están guardados en carpeta compartida y tienen su fecha configurada como `is prompted`.
- Tienes las rutas, expresiones de fecha y región. La clave permanece privada.

Con eso podremos inspeccionar la respuesta siguiendo [03 — Programa y Google Sheets](03-programa-y-sheets.md). Para avanzar basta compartir rutas, nombres de columnas y fórmulas; no hace falta enviar usuarios ni la clave.
