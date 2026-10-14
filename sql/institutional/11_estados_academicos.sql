-- SOLO LECTURA. Catálogos de estados para contrastar la evidencia académica.
-- En el piloto este bloque acompaña a 11_validar_academicos_preparado.sql.
-- Guardar esta cuadrícula con encabezados como 11_estados_academicos.csv.
-- Un estado comercial de EDC no prueba matrícula vigente ni egreso académico.
-- No asumir que los códigos de dbo/PSG son el catálogo de EDC.FCT_MATRICULA.ID_ESTADO.
-- Los estados numéricos de certificados IC requieren confirmación institucional.
SELECT N'dbo' AS source_schema,N'DIM_ESTADO' AS catalog,
       CONVERT(nvarchar(100),e.ID_ESTADO) AS source_code,
       CONVERT(nvarchar(300),e.DES_ESTADO) AS source_label,
       CONVERT(nvarchar(300),NULL) AS additional_value
FROM dbo.DIM_ESTADO AS e
UNION ALL
SELECT N'dbo',N'DIM_ESTADO_TIPO_ESTUDIANTE',
       CONVERT(nvarchar(100),e.ID_ESTADO_TIPO_ESTUDIANTE),
       CONVERT(nvarchar(300),e.DES_TIPO_ESTUDIANTE),NULL
FROM dbo.DIM_ESTADO_TIPO_ESTUDIANTE AS e
UNION ALL
SELECT N'PSG',N'DIM_ESTADO',CONVERT(nvarchar(100),e.ID_ESTADO),
       CONVERT(nvarchar(300),e.DES_ESTADO),NULL
FROM PSG.DIM_ESTADO AS e
UNION ALL
SELECT N'IC',N'DIM_ESTADO',CONVERT(nvarchar(100),e.ID_ESTADO),
       CONVERT(nvarchar(300),e.DESC_ESTADO),CONVERT(nvarchar(300),e.COD_ESTADO)
FROM IC.DIM_ESTADO AS e
UNION ALL
SELECT N'EDC',N'DIM_ESTADO_FUNNEL',CONVERT(nvarchar(100),e.ID_SUBESTADO),
       CONVERT(nvarchar(300),e.DES_SUBESTADO),CONVERT(nvarchar(300),e.DES_ESTADO)
FROM EDC.DIM_ESTADO_FUNNEL AS e
ORDER BY source_schema,catalog,source_code;
