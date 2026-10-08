-- Ejecutar en SSMS seleccionando la base institucional correcta.
-- Solo lectura. Guardar cada cuadrícula por separado, con encabezados.
-- 00_contexto.csv (sin contraseña ni configuración de conexión)
SELECT DB_NAME() AS database_name,
       CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) AS sql_server_version;

-- 00_columnas.csv: incluye vistas de identidad/RRHH/calendarios que no aparezcan en el esquema anterior.
SELECT s.name AS schema_name, o.name AS object_name, o.type_desc AS object_type,
       c.column_id, c.name AS column_name, ty.name AS data_type,
       c.max_length, c.precision, c.scale, c.is_nullable
FROM sys.objects AS o
JOIN sys.schemas AS s ON s.schema_id = o.schema_id
JOIN sys.columns AS c ON c.object_id = o.object_id
JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
WHERE o.type IN ('U', 'V') AND o.is_ms_shipped = 0
  AND (o.name IN ('DIM_PERSONA','DIM_ESTUDIANTE','DIM_DOCENTE','FCT_TRABAJADOR_INFORMACION',
                 'DIM_TRABAJADOR','FCT_MATRICULA','DIM_PERIODO','DIM_PERIODOACAD',
                 'DIM_SECCION','FCT_PROGRAMACION_DOCENTE')
       OR o.name LIKE '%USUARIO%' OR o.name LIKE '%CORREO%' OR o.name LIKE '%ALIAS%'
       OR o.name LIKE '%CALENDARIO%' OR o.name LIKE '%PERSONAL%' OR o.name LIKE '%EMPLEADO%')
ORDER BY s.name, o.name, c.column_id;

-- 00_relaciones.csv: las relaciones no declaradas como FK necesitan validación con muestras.
SELECT OBJECT_SCHEMA_NAME(fk.parent_object_id) AS source_schema,
       OBJECT_NAME(fk.parent_object_id) AS source_table, pc.name AS source_column,
       OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS target_schema,
       OBJECT_NAME(fk.referenced_object_id) AS target_table, rc.name AS target_column,
       fk.name AS relation_name, fk.is_disabled, fk.is_not_trusted
FROM sys.foreign_keys AS fk
JOIN sys.foreign_key_columns AS k ON k.constraint_object_id = fk.object_id
JOIN sys.columns AS pc ON pc.object_id=k.parent_object_id AND pc.column_id=k.parent_column_id
JOIN sys.columns AS rc ON rc.object_id=k.referenced_object_id AND rc.column_id=k.referenced_column_id
WHERE OBJECT_NAME(fk.parent_object_id) IN ('DIM_ESTUDIANTE','DIM_DOCENTE','FCT_MATRICULA','FCT_PROGRAMACION_DOCENTE')
ORDER BY source_schema, source_table, relation_name;

-- 00_claves.csv: verificar si los IDs de dimensiones son realmente únicos.
SELECT s.name AS schema_name, t.name AS table_name, i.name AS key_name,
       i.is_primary_key, i.is_unique, ic.key_ordinal, c.name AS column_name
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id=t.schema_id
JOIN sys.indexes AS i ON i.object_id=t.object_id
JOIN sys.index_columns AS ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id AND ic.key_ordinal>0
JOIN sys.columns AS c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
WHERE i.is_unique=1 AND t.name IN ('DIM_PERSONA','DIM_ESTUDIANTE','DIM_DOCENTE',
       'FCT_TRABAJADOR_INFORMACION','DIM_TRABAJADOR','FCT_MATRICULA','DIM_PERIODO','DIM_PERIODOACAD','DIM_SECCION')
ORDER BY s.name,t.name,i.name,ic.key_ordinal;
