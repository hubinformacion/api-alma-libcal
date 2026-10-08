-- SOLO LECTURA. Completar ID_PERSONA obtenido en 01_identificar_persona.sql.
-- Se conservan todos los períodos/carreras. No se decide vigencia por el máximo ID_PERIODO.
-- Los campos ID_FECHA son claves: su formato debe comprobarse antes de interpretarlos como fechas.
DECLARE @persona_id numeric(18,0) = NULL;
DECLARE @fecha_operacion date = '2026-10-07';
IF @persona_id IS NULL
BEGIN
    SELECT N'Completa @persona_id con ID_PERSONA y ejecuta todo el archivo.' AS instruction;
    RETURN;
END;

-- 03_matriculas_uc_CASO.csv
SELECT e.ID_PERSONA AS person_id, e.ID_ESTUDIANTE AS student_id, e.COD_ESTUDIANTE AS student_code,
       m.ID_PERIODO AS period_id, p.DES_PERIODO_ACADEMICO AS period_name,
       m.ID_FECHA_MATRICULA AS enrollment_date_key, m.ID_FECHA AS activity_date_key,
       m.ID_CAMPUS AS campus_id, c.DES_CAMPUS AS campus_name,
       m.ID_MODALIDAD AS modality_id, mo.DES_MODALIDAD AS modality_name,
       m.ID_FACULTAD_EAP AS faculty_program_id, fe.ID_EAP AS program_id, a.DES_EAP AS program_name,
       fe.ID_FACULTAD AS faculty_id, f.DES_FACULTAD AS faculty_name,
       m.ID_NIVEL AS academic_level_id, m.ID_ESTADO AS source_status_id,
       m.ID_ESTADO_MATRICULA AS enrollment_status_id, m.ID_ESTADO_BANNER AS banner_status_id,
       m.ID_ESTADO_INICIAL AS initial_status_id, m.ID_ESTADO_FINAL AS final_status_id,
       m.CREDITOS_MATRICULADOS AS enrolled_credits, m.FEC_ACTUALIZACION AS source_loaded_at,
       @fecha_operacion AS requested_activity_date
FROM dbo.DIM_ESTUDIANTE AS e
JOIN dbo.FCT_MATRICULA AS m ON m.ID_ESTUDIANTE=e.ID_ESTUDIANTE
LEFT JOIN dbo.DIM_PERIODO AS p ON p.ID_PERIODO_ACADEMICO=m.ID_PERIODO
LEFT JOIN dbo.DIM_CAMPUS AS c ON c.ID_CAMPUS=m.ID_CAMPUS
LEFT JOIN dbo.DIM_MODALIDAD AS mo ON mo.ID_MODALIDAD=m.ID_MODALIDAD
LEFT JOIN dbo.DIM_FACULTAD_EAP AS fe ON fe.ID_FACULTAD_EAP=m.ID_FACULTAD_EAP
LEFT JOIN dbo.DIM_EAP AS a ON a.ID_EAP=fe.ID_EAP
LEFT JOIN dbo.DIM_FACULTAD AS f ON f.ID_FACULTAD=fe.ID_FACULTAD
WHERE e.ID_PERSONA=@persona_id
ORDER BY m.ID_PERIODO,m.ID_FECHA_MATRICULA,m.ID_ESTUDIANTE,m.ID_FACULTAD_EAP;

-- 03_matriculas_psg_CASO.csv
SELECT m.ID_PERSONA AS person_id, m.ID_ESTUDIANTE AS student_id, m.PIDM_ESTUDIANTE AS source_pidm,
       m.ID_PERIODO AS period_id, m.ID_PROGRAMA AS program_id, p.DES_PROGRAMA AS program_name,
       m.ID_TIPO_PROGRAMA AS program_type_id, m.ID_CAMPUS AS campus_id,
       m.ID_MODALIDAD AS modality_id, mo.DES_MODALIDAD AS modality_name, m.ID_NIVEL AS academic_level_id,
       m.ID_FECHA_MATRICULA AS enrollment_date_key, m.ID_FECHA_INICIO AS start_date_key,
       m.ID_FECHA_FIN AS end_date_key, m.ID_FECHA_CORTE AS cutoff_date_key,
       m.ID_ESTADO AS source_status_id, m.ESTADO_ACTIVO AS source_active_status,
       m.INDICADOR_MATRICULA AS source_enrollment_flag, m.FEC_ACTUALIZACION AS source_loaded_at,
       @fecha_operacion AS requested_activity_date
FROM PSG.FCT_MATRICULA AS m
LEFT JOIN PSG.DIM_PROGRAMA AS p ON p.ID_PROGRAMA=m.ID_PROGRAMA
LEFT JOIN PSG.DIM_MODALIDAD AS mo ON mo.ID_MODALIDAD=m.ID_MODALIDAD
WHERE m.ID_PERSONA=@persona_id
ORDER BY m.ID_PERIODO,m.ID_FECHA_MATRICULA,m.ID_PROGRAMA;

-- 03_matriculas_edc_CASO.csv
SELECT m.ID_PERSONA AS person_id, m.ID_ESTUDIANTE AS student_id, m.PIDM AS source_pidm,
       m.ID_PERIODO AS period_id, m.ID_PROGRAMA AS program_id, p.DES_PROGRAMA AS program_name,
       p.DES_TIPO_PROGRAMA AS source_program_type, m.ID_CAMPUS AS campus_id,
       m.ID_FECHA_MATRICULA AS enrollment_date_key, m.ID_NIVEL AS academic_level_id,
       m.ID_ESTADO AS source_status_id, m.ESTADO_ACTIVO AS source_active_status,
       m.NRC AS source_course_section, m.FEC_ACTUALIZACION AS source_loaded_at,
       @fecha_operacion AS requested_activity_date
FROM EDC.FCT_MATRICULA AS m
LEFT JOIN EDC.DIM_PROGRAMA AS p ON p.ID_PROGRAMA=m.ID_PROGRAMA
WHERE m.ID_PERSONA=@persona_id
ORDER BY m.ID_PERIODO,m.ID_FECHA_MATRICULA,m.ID_PROGRAMA;

-- 03_matriculas_ic_CASO.csv: vínculo ID_PERSONA aún debe validarse con muestras.
-- No hay ID_CAMPUS en esta tabla: no se inventa un campus a partir del código de sección.
SELECT m.ID_PERSONA AS person_id, m.ID_ALUMNO AS student_id, m.ID_PERIODOACAD AS period_id,
       p.COD_PERIODO AS source_period_code, p.DESC_PERIODO AS period_name,
       m.ID_PROGRAMAESTUDIOS AS program_id, a.COD_PROGRAMA AS program_code, a.DESC_PROGRAMA AS program_name,
       m.ID_MODALIDAD AS modality_id, mo.DESC_MODALIDAD AS modality_name,
       m.ID_PLANESTUDIO AS curriculum_id, m.ID_SECCION AS section_id, s.COD_SECCION AS section_code,
       s.FECHAINI AS section_start, s.FECHAFIN AS section_end,
       m.ID_ESTADOGENERAL AS source_status_id, m.ID_ESTADOCAJA AS source_payment_status_id,
       m.CICLO AS source_cycle, m.FEC_ACTUALIZACION AS source_loaded_at,
       @fecha_operacion AS requested_activity_date
FROM IC.FCT_MATRICULA AS m
LEFT JOIN IC.DIM_PERIODOACAD AS p ON p.ID_PERIODO=m.ID_PERIODOACAD
LEFT JOIN IC.DIM_PROGRAMAESTUDIOS AS a ON a.ID_PROGRAMA=m.ID_PROGRAMAESTUDIOS
LEFT JOIN IC.DIM_MODALIDAD AS mo ON mo.ID_MODALIDAD=m.ID_MODALIDAD
LEFT JOIN IC.DIM_SECCION AS s ON s.ID_SECCION=m.ID_SECCION
WHERE m.ID_PERSONA=@persona_id
ORDER BY m.ID_PERIODOACAD,m.ID_PROGRAMAESTUDIOS,m.ID_SECCION;
