-- SOLO LECTURA. Completar con person_id de 01; ejecutar todo el archivo.
-- Complementa los resultados recibidos; no selecciona todavía un perfil de reporte.
DECLARE @persona_id numeric(18,0) = NULL;
DECLARE @fecha_operacion date = '2026-10-07';
IF @persona_id IS NULL
BEGIN
    SELECT N'Completa @persona_id con ID_PERSONA y ejecuta todo el archivo.' AS instruction;
    RETURN;
END;

-- 06_perfil_continua_CASO.csv. Inicio y modalidad de perfiles registrados en EDC.
-- La fecha de emisión no se interpreta como egreso ni término del programa.
SELECT DISTINCT e.ID_PERIODO AS period_id, pe.DES_PERIODO_ACADEMICO AS period_name,
       e.ID_PROGRAMA AS program_id, p.DES_PROGRAMA AS program_name,
       p.DES_TIPO_PROGRAMA AS source_program_type,
       e.ID_FECHAINICIO AS start_date_key, ti.DES_TIEMPO AS source_start_date,
       e.ID_FECHAEMISION AS emission_date_key, te.DES_TIEMPO AS source_emission_date,
       e.ID_MODALIDAD AS modality_id, mo.DES_MODALIDAD AS modality_name,
       e.ID_CAMPUS AS campus_id, c.DES_CAMPUS AS campus_name,
       e.ID_SUBESTADO AS source_substatus_id,
       @fecha_operacion AS requested_activity_date
FROM EDC.FCT_PERFIL_ESTUDIANTE AS e
LEFT JOIN EDC.DIM_PROGRAMA AS p ON p.ID_PROGRAMA=e.ID_PROGRAMA
LEFT JOIN dbo.DIM_PERIODO AS pe ON pe.ID_PERIODO_ACADEMICO=e.ID_PERIODO
LEFT JOIN dbo.DIM_TIEMPO AS ti ON ti.ID_TIEMPO=e.ID_FECHAINICIO
LEFT JOIN dbo.DIM_TIEMPO AS te ON te.ID_TIEMPO=e.ID_FECHAEMISION
LEFT JOIN dbo.DIM_MODALIDAD AS mo ON mo.ID_MODALIDAD=e.ID_MODALIDAD
LEFT JOIN dbo.DIM_CAMPUS AS c ON c.ID_CAMPUS=e.ID_CAMPUS
WHERE e.ID_PERSONA=@persona_id
ORDER BY e.ID_PERIODO,e.ID_PROGRAMA,e.ID_FECHAINICIO,e.ID_MODALIDAD,e.ID_CAMPUS,e.ID_SUBESTADO,e.ID_FECHAEMISION;

-- 06_programa_posgrado_CASO.csv. Identifica la referencia PSG; no prueba matrícula vigente.
SELECT e.ID_PROGRAMA AS program_id, p.DES_PROGRAMA AS program_name,
       e.ID_TIPO_PROGRAMA AS program_type_id, tp.DES_TIPO_PROGRAMA AS program_type_name,
       e.ID_MODALIDAD AS modality_id, mo.DES_MODALIDAD AS modality_name,
       e.ID_CAMPUS AS campus_id, e.CATALOGO AS source_catalog,
       @fecha_operacion AS requested_activity_date
FROM PSG.DIM_ESTUDIANTE AS e
LEFT JOIN PSG.DIM_PROGRAMA AS p ON p.ID_PROGRAMA=e.ID_PROGRAMA
LEFT JOIN PSG.DIM_TIPO_PROGRAMA AS tp ON tp.ID_TIPO_PROGRAMA=e.ID_TIPO_PROGRAMA
LEFT JOIN PSG.DIM_MODALIDAD AS mo ON mo.ID_MODALIDAD=e.ID_MODALIDAD
WHERE e.ID_PERSONA=@persona_id
ORDER BY e.ID_ESTUDIANTE,e.ID_PROGRAMA;

-- 06_vigencia_docente_CASO.csv. Otra fuente con semanas de docencia del caso.
-- Conservar fechas varchar originales: no interpretar automáticamente el formato.
SELECT DISTINCT TOP (100) g.ID_PERIODO AS period_id,
       pe.DES_PERIODO_ACADEMICO AS period_name, g.ID_CAMPUS AS campus_id,
       g.ID_MODALIDAD AS modality_id, g.ID_PROGRAMA AS program_id,
       g.TIPO_DOCENTE AS source_teacher_type,
       g.FECHA_INICIO_SEMANA AS source_week_start_text,
       g.FECHA_FIN_SEMANA AS source_week_end_text,
       g.NRO_SEMANA AS source_week_number,
       @fecha_operacion AS requested_activity_date
FROM dbo.FCT_REPORTE_GESTION_DOCENTE AS g
LEFT JOIN dbo.DIM_PERIODO AS pe ON pe.ID_PERIODO_ACADEMICO=g.ID_PERIODO
WHERE EXISTS (SELECT 1 FROM dbo.DIM_DOCENTE AS d
              WHERE d.ID_PERSONA=@persona_id AND d.ID_DOCENTE=g.ID_DOCENTE)
  AND EXISTS (SELECT 1 FROM dbo.FCT_PROGRAMACION_DOCENTE AS pr
              WHERE pr.ID_DOCENTE=g.ID_DOCENTE AND pr.ID_PERIODO_ACADEMICO=g.ID_PERIODO)
ORDER BY g.ID_PERIODO,g.ID_CAMPUS,g.ID_MODALIDAD,g.ID_PROGRAMA,
         g.TIPO_DOCENTE,g.FECHA_INICIO_SEMANA,g.FECHA_FIN_SEMANA,g.NRO_SEMANA;
