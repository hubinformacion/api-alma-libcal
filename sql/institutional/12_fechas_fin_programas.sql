-- SOLO LECTURA. Usar 12_fechas_fin_preparado.sql, con los casos ya completos.
-- Ejecutar TODO una vez en la misma base de SSMS, sin completar parámetros.
-- Guardar dos resultados con encabezados en data/referencias/usuarios/actual/:
-- 1: 12_fechas_programas.csv (conservar profile_data completo).
-- 2: 12_fuentes_fechas_fin.csv.
-- Son casos de validación; no importar como operaciones ni perfiles del lote real.
DECLARE @casos TABLE (
    case_id int PRIMARY KEY, case_label nvarchar(100), person_id numeric(18,0),
    account_scope nvarchar(30), activity_date date
);
-- INSERT_DATE_CASES_HERE
IF NOT EXISTS (SELECT 1 FROM @casos)
BEGIN
    SELECT N'Abre 12_fechas_fin_preparado.sql, que contiene los casos de referencia.' AS instruction;
    RETURN;
END;

-- Resultado 1. Fechas originales, claves y disponibilidad; no deducir egreso de una emisión.
SELECT q.case_id,q.case_label,q.account_scope,q.activity_date,
       evidence.profile_source,evidence.profile_data
FROM @casos AS q
CROSS APPLY (
    SELECT N'uc_program_dates' AS profile_source,
           (SELECT e.ID_ESTUDIANTE AS student_id,e.ID_EAP AS program_id,
                   e.FEC_INICIO_ESTUDIO AS study_start,e.FEC_FIN_ESTUDIO AS study_end,
                   e.FEC_EGRESO AS graduation_date,e.FEC_BACHILLER AS bachelor_date,
                   e.FEC_TITULACION AS title_date,e.ESTADO AS source_status
            FOR JSON PATH,INCLUDE_NULL_VALUES,WITHOUT_ARRAY_WRAPPER) AS profile_data
    FROM dbo.DIM_ESTUDIANTE AS e
    WHERE q.account_scope=N'university' AND e.ID_PERSONA=q.person_id
    UNION ALL
    SELECT N'psg_program_dates',
           (SELECT m.ID_ESTUDIANTE AS student_id,m.ID_PROGRAMA AS program_id,
                   m.ID_PERIODO AS period_id,m.ID_SECCION AS section_id,
                   m.ID_FECHA_MATRICULA AS enrollment_date_key,
                   m.ID_FECHA_INICIO AS start_date_key,m.ID_FECHA_FIN AS end_date_key,
                   m.ID_FECHA_CORTE AS cutoff_date_key,
                   te.DES_TIEMPO AS enrollment_date,ts.DES_TIEMPO AS study_start,
                   tf.DES_TIEMPO AS study_end,tc.DES_TIEMPO AS cutoff_date,
                   CASE WHEN ISNULL(m.ID_FECHA_INICIO,0)=0 THEN N'not_provided'
                        WHEN ts.ID_TIEMPO IS NULL THEN N'unmapped_key' ELSE N'mapped' END AS start_lookup,
                   CASE WHEN ISNULL(m.ID_FECHA_FIN,0)=0 THEN N'not_provided'
                        WHEN tf.ID_TIEMPO IS NULL THEN N'unmapped_key' ELSE N'mapped' END AS end_lookup,
                   m.ID_ESTADO AS source_status_id,m.ESTADO_ACTIVO AS source_active_status,
                   m.INDICADOR_MATRICULA AS source_enrollment_flag
            FOR JSON PATH,INCLUDE_NULL_VALUES,WITHOUT_ARRAY_WRAPPER)
    FROM PSG.FCT_MATRICULA AS m
    LEFT JOIN dbo.DIM_TIEMPO AS te ON te.ID_TIEMPO=m.ID_FECHA_MATRICULA AND m.ID_FECHA_MATRICULA<>0
    LEFT JOIN dbo.DIM_TIEMPO AS ts ON ts.ID_TIEMPO=m.ID_FECHA_INICIO AND m.ID_FECHA_INICIO<>0
    LEFT JOIN dbo.DIM_TIEMPO AS tf ON tf.ID_TIEMPO=m.ID_FECHA_FIN AND m.ID_FECHA_FIN<>0
    LEFT JOIN dbo.DIM_TIEMPO AS tc ON tc.ID_TIEMPO=m.ID_FECHA_CORTE AND m.ID_FECHA_CORTE<>0
    WHERE q.account_scope=N'university' AND m.ID_PERSONA=q.person_id
    UNION ALL
    SELECT N'edc_profile_dates',
           (SELECT e.ID_PROGRAMA AS program_id,e.ID_PERIODO AS period_id,
                   e.COD_SECCIONC AS course_section_code,e.ID_FECHAINICIO AS start_date_key,
                   ts.DES_TIEMPO AS study_start,e.ID_FECHAEMISION AS emission_date_key,
                   td.DES_TIEMPO AS document_emission_date,e.ID_SUBESTADO AS source_substatus_id,
                   N'not_exposed_by_this_source' AS program_end_availability
            FOR JSON PATH,INCLUDE_NULL_VALUES,WITHOUT_ARRAY_WRAPPER)
    FROM EDC.FCT_PERFIL_ESTUDIANTE AS e
    LEFT JOIN dbo.DIM_TIEMPO AS ts ON ts.ID_TIEMPO=e.ID_FECHAINICIO AND e.ID_FECHAINICIO<>0
    LEFT JOIN dbo.DIM_TIEMPO AS td ON td.ID_TIEMPO=e.ID_FECHAEMISION AND e.ID_FECHAEMISION<>0
    WHERE q.account_scope=N'university' AND e.ID_PERSONA=q.person_id
    UNION ALL
    SELECT N'edc_enrollment_references',
           (SELECT m.ID_ESTUDIANTE AS student_id,m.ID_PROGRAMA AS program_id,
                   m.ID_PERIODO AS period_id,m.ID_SECCIONC AS course_section_id,m.NRC AS source_course_section,
                   m.ID_FECHA_MATRICULA AS enrollment_date_key,t.DES_TIEMPO AS enrollment_date,
                   m.ID_ESTADO AS source_status_id,m.ESTADO_ACTIVO AS source_active_status
            FOR JSON PATH,INCLUDE_NULL_VALUES,WITHOUT_ARRAY_WRAPPER)
    FROM EDC.FCT_MATRICULA AS m
    LEFT JOIN dbo.DIM_TIEMPO AS t ON t.ID_TIEMPO=m.ID_FECHA_MATRICULA AND m.ID_FECHA_MATRICULA<>0
    WHERE q.account_scope=N'university' AND m.ID_PERSONA=q.person_id
    UNION ALL
    SELECT N'ic_section_dates',
           (SELECT m.ID_ALUMNO AS student_id,m.ID_PROGRAMAESTUDIOS AS program_id,
                   m.ID_PERIODOACAD AS period_id,m.ID_SECCION AS section_id,s.COD_SECCION AS section_code,
                   s.FECHAINI AS section_start,s.FECHAFIN AS section_end,
                   N'section_not_entire_program' AS date_scope,m.ID_ESTADOGENERAL AS source_status_id
            FOR JSON PATH,INCLUDE_NULL_VALUES,WITHOUT_ARRAY_WRAPPER)
    FROM IC.FCT_MATRICULA AS m
    LEFT JOIN IC.DIM_SECCION AS s ON s.ID_SECCION=m.ID_SECCION
    WHERE q.account_scope=N'institute' AND m.ID_PERSONA=q.person_id
) AS evidence
ORDER BY q.case_id,evidence.profile_source;

-- Resultado 2. Fuentes candidatas y relaciones declaradas, sin consultar personas.
-- CIC se inspecciona solo como candidato: un nombre de sección parecido no prueba relación con EDC.
SELECT s.name AS source_schema,o.name AS source_object,o.type_desc AS object_type,
       c.column_id,c.name AS source_column,ty.name AS data_type,
       OBJECT_SCHEMA_NAME(k.referenced_object_id) AS referenced_schema,
       OBJECT_NAME(k.referenced_object_id) AS referenced_object,
       rc.name AS referenced_column,fk.name AS relation_name
FROM sys.objects AS o
JOIN sys.schemas AS s ON s.schema_id=o.schema_id
JOIN sys.columns AS c ON c.object_id=o.object_id
JOIN sys.types AS ty ON ty.user_type_id=c.user_type_id
LEFT JOIN sys.foreign_key_columns AS k ON k.parent_object_id=o.object_id AND k.parent_column_id=c.column_id
LEFT JOIN sys.foreign_keys AS fk ON fk.object_id=k.constraint_object_id
LEFT JOIN sys.columns AS rc ON rc.object_id=k.referenced_object_id AND rc.column_id=k.referenced_column_id
WHERE o.type IN ('U','V') AND o.is_ms_shipped=0
  AND s.name IN ('EDC','PSG','CIC','IC')
  AND (o.name LIKE '%SECCION%' OR o.name LIKE '%PROGRAMA%' OR o.name LIKE '%CALENDARIO%'
       OR o.name LIKE '%EGRES%' OR o.name LIKE '%CERTIFIC%' OR o.name LIKE '%ESTADO%'
       OR EXISTS (SELECT 1 FROM sys.columns AS d WHERE d.object_id=o.object_id
                  AND (d.name LIKE '%FIN%' OR d.name LIKE '%TERMIN%' OR d.name LIKE '%DURACION%')))
ORDER BY s.name,o.name,c.column_id,fk.name;
