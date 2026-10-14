-- SOLO LECTURA. Selecciona la base institucional de las pruebas en SSMS.
-- Ejecuta TODO este archivo UNA VEZ. No requiere completar correos ni documentos.
-- Guarda las DOS cuadrículas con encabezados en:
-- data/referencias/usuarios/actual/
-- No contiene datos personales. Un resultado vacío también es válido.

-- Resultado 1: 10_sucursales_laborales.csv
-- Son códigos originales: no asumir que SUCURSAL equivale a dbo.DIM_CAMPUS.ID_CAMPUS.
SELECT DISTINCT
       CONVERT(nvarchar(100),w.DES_DIV) AS labor_division_code,
       CONVERT(nvarchar(100),w.SUCURSAL) AS labor_branch_code
FROM dbo.FCT_TRABAJADOR_INFORMACION AS w
ORDER BY labor_division_code,labor_branch_code;

-- Resultado 2: 10_fuentes_ubicaciones_calendarios.csv
-- Busca catálogos/vistas y muestra todas sus columnas para revisar posibles relaciones.
-- La coincidencia de nombres NO demuestra una relación ni autoriza a unir códigos.
-- Las fechas FEC_CREACION/FEC_ACTUALIZACION no son un calendario académico.
SELECT s.name AS schema_name,o.name AS object_name,o.type_desc AS object_type,
       c.column_id,c.name AS column_name,ty.name AS data_type
FROM sys.objects AS o
JOIN sys.schemas AS s ON s.schema_id=o.schema_id
JOIN sys.columns AS c ON c.object_id=o.object_id
JOIN sys.types AS ty ON ty.user_type_id=c.user_type_id
WHERE o.type IN ('U','V') AND o.is_ms_shipped=0
  AND (
      o.name LIKE '%SUCURSAL%' OR o.name LIKE '%SEDE%'
      OR o.name LIKE '%CAMPUS%' OR o.name LIKE '%FACULTAD%'
      OR o.name LIKE '%CALENDARIO%'
      OR EXISTS (
          SELECT 1 FROM sys.columns AS location_column
          WHERE location_column.object_id=o.object_id
            AND (location_column.name LIKE '%SUCURSAL%'
                 OR location_column.name LIKE '%SEDE%')
      )
      OR (
          EXISTS (SELECT 1 FROM sys.columns AS period_column
                  WHERE period_column.object_id=o.object_id
                    AND period_column.name LIKE '%PERIODO%')
          AND EXISTS (SELECT 1 FROM sys.columns AS date_column
                      WHERE date_column.object_id=o.object_id
                        AND (date_column.name LIKE '%INIC%'
                             OR date_column.name LIKE '%FIN'
                             OR date_column.name LIKE '%TERMINO%'))
      )
  )
ORDER BY s.name,o.name,c.column_id;
