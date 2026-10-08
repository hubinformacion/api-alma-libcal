-- SOLO LECTURA. Obtener person_id de 01_identificar_persona.sql; no es el DNI.
DECLARE @persona_id numeric(18,0) = NULL;
DECLARE @fecha_operacion date = '2026-10-07';
IF @persona_id IS NULL
BEGIN
    SELECT N'Completa @persona_id con ID_PERSONA y ejecuta todo el archivo.' AS instruction;
    RETURN;
END;
DECLARE @documento nvarchar(64);
SELECT @documento=LTRIM(RTRIM(p.COD_DOCUMENTO)) FROM dbo.DIM_PERSONA AS p WHERE p.ID_PERSONA=@persona_id;

-- 02_estudiante_uc_CASO.csv: conservar cada carrera, campus y código, no seleccionar la última por FEC_ACTUALIZACION.
SELECT e.ID_PERSONA AS person_id, e.ID_ESTUDIANTE AS student_id, e.COD_ESTUDIANTE AS student_code,
       e.ID_EAP AS program_id, e.ID_FACULTAD AS faculty_id, e.ID_CAMPUS AS campus_id,
       e.ID_MODALIDAD_INGRESO AS entry_modality_id, e.ID_MODALIDAD_ADMISION AS admission_modality_id,
       e.ID_PERIODO_INGRESO AS entry_period_id, e.ID_PERIODO_EGRESO AS graduation_period_id,
       e.FEC_INGRESO AS admission_date, e.FEC_INICIO_ESTUDIO AS study_start,
       e.FEC_FIN_ESTUDIO AS study_end, e.FEC_EGRESO AS graduation_date,
       e.ESTADO AS source_status, e.FEC_ACTUALIZACION AS source_loaded_at,
       @fecha_operacion AS requested_activity_date
FROM dbo.DIM_ESTUDIANTE AS e WHERE e.ID_PERSONA=@persona_id ORDER BY e.ID_ESTUDIANTE;

-- 02_estudiante_psg_CASO.csv
SELECT e.ID_PERSONA AS person_id, e.ID_ESTUDIANTE AS student_id, e.COD_ESTUDIANTE AS student_code,
       e.PIDM_ESTUDIANTE AS source_pidm, e.ID_CAMPUS AS campus_id, e.ID_MODALIDAD AS modality_id,
       e.ID_NIVEL AS academic_level_id, e.ID_PROGRAMA AS program_id, e.ID_TIPO_PROGRAMA AS program_type_id,
       e.CATALOGO AS source_catalog, e.FEC_ACTUALIZACION AS source_loaded_at,
       @fecha_operacion AS requested_activity_date
FROM PSG.DIM_ESTUDIANTE AS e WHERE e.ID_PERSONA=@persona_id ORDER BY e.ID_ESTUDIANTE;

-- 02_empleo_CASO.csv: ES_DOCENTE y fechas necesitan semántica confirmada.
-- La existencia de la cuenta hoy no prueba el rol de años anteriores.
SELECT w.DNI AS document_number, w.USUARIO AS account_name, w.EMAIL AS work_email,
       w.ES_DOCENTE AS source_teacher_flag, w.DES_DIV AS source_division, w.SUCURSAL AS source_branch,
       w.FECHA_INGRESO AS employment_start, w.FECHA_RETIRO AS employment_withdrawal,
       w.FECHA_TERMINO AS employment_end, w.FEC_ACTUALIZACION AS source_loaded_at,
       @fecha_operacion AS requested_activity_date
FROM dbo.FCT_TRABAJADOR_INFORMACION AS w
WHERE @documento IS NOT NULL AND LTRIM(RTRIM(w.DNI))=@documento
ORDER BY w.USUARIO,w.FECHA_INGRESO;

-- 02_docente_CASO.csv: validar continuidad por persona/documento.
SELECT d.ID_DOCENTE AS teacher_id, d.ID_PERSONA AS person_id, d.NUMERO_DOCUMENTO AS document_number,
       d.TIPO_DOCUMENTO AS document_type, d.EMAIL_CORPORATIVO AS work_email,
       d.FECHAINGRESO AS teacher_start, d.FECHASALIDA AS teacher_end,
       @fecha_operacion AS requested_activity_date
FROM dbo.DIM_DOCENTE AS d
WHERE d.ID_PERSONA=@persona_id OR (@documento IS NOT NULL AND LTRIM(RTRIM(d.NUMERO_DOCUMENTO))=@documento)
ORDER BY d.ID_DOCENTE;

-- 02_trabajador_ic_CASO.csv: dimensión sin fechas laborales; no prueba vigencia histórica.
SELECT t.ID_TRABAJADOR AS worker_id, t.DNI AS document_number, t.EMAIL AS work_email,
       t.NOMBRES AS first_name, t.APELLIDO_PATERNO AS paternal_last_name, t.APELLIDO_MATERNO AS maternal_last_name,
       t.DESC_TIPO_CONTRATO AS source_contract_type, t.FEC_ACTUALIZACION AS source_loaded_at
FROM IC.DIM_TRABAJADOR AS t
WHERE @documento IS NOT NULL AND LTRIM(RTRIM(t.DNI))=@documento
ORDER BY t.ID_TRABAJADOR;

-- 02_programacion_docente_CASO.csv: conservar períodos y posibles múltiples campus.
SELECT p.ID_DOCENTE AS teacher_id, p.ID_PERIODO_ACADEMICO AS period_id, p.ID_CAMPUS AS campus_id,
       p.ID_MODALIDAD AS modality_id, p.ID_EAP AS program_id, p.TIPO_DOCENTE AS source_teacher_type,
       p.CARGA_LABORAL AS source_workload, p.TIPO_CONTRATO AS source_contract_type,
       p.FEC_ACTUALIZACION AS source_loaded_at
FROM dbo.FCT_PROGRAMACION_DOCENTE AS p
WHERE EXISTS (SELECT 1 FROM dbo.DIM_DOCENTE AS d WHERE d.ID_DOCENTE=p.ID_DOCENTE
       AND (d.ID_PERSONA=@persona_id OR (@documento IS NOT NULL AND LTRIM(RTRIM(d.NUMERO_DOCUMENTO))=@documento)))
ORDER BY p.ID_PERIODO_ACADEMICO,p.ID_DOCENTE,p.ID_CAMPUS;
