-- SOLO LECTURA. Completar el ID_PERSONA de 01; no colocar el DNI.
-- Esta consulta resuelve claves de fecha por DIM_TIEMPO, no por aritmética ni formato YYYYMMDD.
DECLARE @persona_id numeric(18,0) = NULL;
DECLARE @fecha_operacion date = '2026-10-07';
IF @persona_id IS NULL
BEGIN
    SELECT N'Completa @persona_id y ejecuta todo el archivo.' AS instruction;
    RETURN;
END;

-- 05_fechas_CASO.csv. Una misma clave repetida en varias filas se muestra una sola vez por uso.
;WITH date_keys AS (
    SELECT N'UC' AS academic_source, x.date_use, x.date_key
    FROM dbo.DIM_ESTUDIANTE AS e
    JOIN dbo.FCT_MATRICULA AS m ON m.ID_ESTUDIANTE=e.ID_ESTUDIANTE
    CROSS APPLY (VALUES (N'enrollment',m.ID_FECHA_MATRICULA),(N'activity',m.ID_FECHA)) AS x(date_use,date_key)
    WHERE e.ID_PERSONA=@persona_id
    UNION ALL
    SELECT N'PSG',x.date_use,x.date_key FROM PSG.FCT_MATRICULA AS m
    CROSS APPLY (VALUES (N'enrollment',m.ID_FECHA_MATRICULA),(N'start',m.ID_FECHA_INICIO),
                        (N'end',m.ID_FECHA_FIN),(N'cutoff',m.ID_FECHA_CORTE)) AS x(date_use,date_key)
    WHERE m.ID_PERSONA=@persona_id
    UNION ALL
    SELECT N'EDC',N'enrollment',m.ID_FECHA_MATRICULA FROM EDC.FCT_MATRICULA AS m
    WHERE m.ID_PERSONA=@persona_id
)
SELECT DISTINCT k.academic_source,k.date_use,k.date_key,t.DES_TIEMPO AS resolved_date,
       CASE WHEN t.ID_TIEMPO IS NULL THEN N'not_found' ELSE N'mapped' END AS mapping_status,
       @fecha_operacion AS requested_activity_date
FROM date_keys AS k
LEFT JOIN dbo.DIM_TIEMPO AS t ON t.ID_TIEMPO=k.date_key
WHERE k.date_key IS NOT NULL
ORDER BY k.academic_source,k.date_use,k.date_key;

-- 05_periodos_CASO.csv. El período no contiene inicio/fin en DIM_PERIODO.
;WITH person_periods AS (
    SELECT N'UC' AS academic_source,m.ID_PERIODO AS period_id
    FROM dbo.DIM_ESTUDIANTE AS e JOIN dbo.FCT_MATRICULA AS m ON m.ID_ESTUDIANTE=e.ID_ESTUDIANTE
    WHERE e.ID_PERSONA=@persona_id
    UNION ALL
    SELECT N'PSG',m.ID_PERIODO FROM PSG.FCT_MATRICULA AS m WHERE m.ID_PERSONA=@persona_id
    UNION ALL
    SELECT N'EDC',m.ID_PERIODO FROM EDC.FCT_MATRICULA AS m WHERE m.ID_PERSONA=@persona_id
    UNION ALL
    SELECT N'teaching',p.ID_PERIODO_ACADEMICO FROM dbo.FCT_PROGRAMACION_DOCENTE AS p
    WHERE EXISTS (SELECT 1 FROM dbo.DIM_DOCENTE AS d WHERE d.ID_DOCENTE=p.ID_DOCENTE AND d.ID_PERSONA=@persona_id)
)
SELECT DISTINCT pp.academic_source,pp.period_id,per.DES_PERIODO_ACADEMICO AS period_name,
       per.TIP_PERIODO AS period_type,@fecha_operacion AS requested_activity_date
FROM person_periods AS pp LEFT JOIN dbo.DIM_PERIODO AS per ON per.ID_PERIODO_ACADEMICO=pp.period_id
ORDER BY pp.academic_source,pp.period_id;

-- 05_fuentes_calendario.csv: solo metadatos; localizar calendario real, no usar fechas ETL.
SELECT s.name AS schema_name,o.name AS object_name,c.name AS column_name,ty.name AS data_type
FROM sys.objects AS o JOIN sys.schemas AS s ON s.schema_id=o.schema_id
JOIN sys.columns AS c ON c.object_id=o.object_id
JOIN sys.types AS ty ON ty.user_type_id=c.user_type_id
WHERE o.type IN ('U','V') AND o.is_ms_shipped=0
  AND EXISTS (SELECT 1 FROM sys.columns AS p WHERE p.object_id=o.object_id AND p.name LIKE '%PERIODO%')
  AND EXISTS (SELECT 1 FROM sys.columns AS d JOIN sys.types AS dt ON dt.user_type_id=d.user_type_id
      WHERE d.object_id=o.object_id AND dt.name IN ('date','datetime','datetime2','smalldatetime','varchar','nvarchar','char','nchar')
      AND (d.name LIKE '%INIC%' OR d.name LIKE '%FIN' OR d.name LIKE '%TERMINO%'))
  AND (c.name LIKE '%PERIODO%' OR c.name LIKE '%INIC%' OR c.name LIKE '%FIN' OR c.name LIKE '%TERMINO%')
ORDER BY s.name,o.name,c.column_id;

-- 05_horarios_docentes_CASO.csv. Muestra acotada de los períodos de programación encontrados.
-- Las fechas son varchar en la arquitectura: conservar texto, no interpretar automáticamente su formato.
SELECT DISTINCT TOP (100) h.ID_PERIODO_ACADEMICO AS period_id,
       h.ID_CAMPUS_NRC AS teaching_campus_id, h.DES_TIPO_DOCENTE AS source_teacher_type,
       h.FECHA_INICIO AS source_start_text, h.FECHA_FIN AS source_end_text,
       h.FECHA_CLASE AS source_class_date_text, @fecha_operacion AS requested_activity_date
FROM dbo.FCT_HORAS_DOCENTE_MATRICULA AS h
WHERE h.ID_PERSONA=@persona_id
  AND h.ID_PERIODO_ACADEMICO IN (
      SELECT p.ID_PERIODO_ACADEMICO FROM dbo.FCT_PROGRAMACION_DOCENTE AS p
      WHERE EXISTS (SELECT 1 FROM dbo.DIM_DOCENTE AS d
                    WHERE d.ID_DOCENTE=p.ID_DOCENTE AND d.ID_PERSONA=@persona_id))
ORDER BY h.ID_PERIODO_ACADEMICO,h.ID_CAMPUS_NRC,h.FECHA_CLASE;
