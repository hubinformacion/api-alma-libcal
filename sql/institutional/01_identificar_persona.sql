-- SOLO LECTURA. Completar UNO O VARIOS valores en el equipo institucional.
-- Ejemplo de sintaxis: sustituir NULL por N'valor' (mantener comillas).
-- No guardar tus datos personales en la copia de este archivo que se sube a Git.
DECLARE @correo nvarchar(255) = NULL;       -- Correo completo tal como aparece en Alma/LibCal.
DECLARE @documento nvarchar(64) = NULL;     -- Documento conocido; no se convierte a número.
DECLARE @identificador nvarchar(80) = NULL; -- Código U..., TM..., i... o identificador fuente.

SET @correo = NULLIF(LOWER(LTRIM(RTRIM(@correo))), N'');
SET @documento = NULLIF(LTRIM(RTRIM(@documento)), N'');
SET @identificador = NULLIF(LOWER(LTRIM(RTRIM(@identificador))), N'');
IF @correo IS NULL AND @documento IS NULL AND @identificador IS NULL
BEGIN
    SELECT N'Completa correo, documento o identificador y ejecuta todo el archivo.' AS instruction;
    RETURN;
END;

-- 01_personas_CASO.csv. Todos los candidatos: no elegir arbitrariamente TOP 1.
-- Buscar correo exacto antes de usar documento/código como respaldo.
SELECT p.ID_PERSONA AS person_id, p.PIDM AS source_pidm,
       p.COD_DOCUMENTO AS document_number, p.NOM_COMPLETOS AS full_name,
       p.CORREO_CORPORATIVO AS corporate_email,
       CASE WHEN @correo IS NOT NULL AND LOWER(LTRIM(RTRIM(p.CORREO_CORPORATIVO)))=@correo THEN 1 ELSE 0 END AS corporate_email_match,
       CASE WHEN @correo IS NOT NULL AND
            (LOWER(LTRIM(RTRIM(p.CORREOPERSONAL1)))=@correo OR LOWER(LTRIM(RTRIM(p.CORREOPERSONAL2)))=@correo)
            THEN 1 ELSE 0 END AS contact_email_match,
       CASE WHEN (@documento IS NOT NULL AND LTRIM(RTRIM(p.COD_DOCUMENTO))=@documento)
            OR (@identificador IS NOT NULL AND LOWER(LTRIM(RTRIM(p.COD_DOCUMENTO)))=@identificador) THEN 1 ELSE 0 END AS document_match,
       COUNT(*) OVER() AS candidate_person_count
FROM dbo.DIM_PERSONA AS p
WHERE (@correo IS NOT NULL AND (@correo=LOWER(LTRIM(RTRIM(p.CORREO_CORPORATIVO)))
       OR @correo=LOWER(LTRIM(RTRIM(p.CORREOPERSONAL1))) OR @correo=LOWER(LTRIM(RTRIM(p.CORREOPERSONAL2)))))
   OR (@documento IS NOT NULL AND @documento=LTRIM(RTRIM(p.COD_DOCUMENTO)))
   OR (@identificador IS NOT NULL AND @identificador=LOWER(LTRIM(RTRIM(p.COD_DOCUMENTO))))
   OR (@identificador IS NOT NULL AND EXISTS (SELECT 1 FROM dbo.DIM_ESTUDIANTE AS e
       WHERE e.ID_PERSONA=p.ID_PERSONA AND LOWER(LTRIM(RTRIM(e.COD_ESTUDIANTE)))=@identificador))
   OR (@identificador IS NOT NULL AND EXISTS (SELECT 1 FROM PSG.DIM_ESTUDIANTE AS g
       WHERE g.ID_PERSONA=p.ID_PERSONA AND LOWER(LTRIM(RTRIM(g.COD_ESTUDIANTE)))=@identificador))
ORDER BY corporate_email_match DESC, contact_email_match DESC, document_match DESC, p.ID_PERSONA;

-- 01_cuentas_laborales_CASO.csv. No derivar el correo de las iniciales del nombre.
SELECT w.DNI AS document_number, w.USUARIO AS account_name, w.EMAIL AS work_email,
       w.ES_DOCENTE AS source_teacher_flag, w.DES_DIV AS source_division, w.SUCURSAL AS source_branch,
       w.FECHA_INGRESO AS employment_start, w.FECHA_RETIRO AS employment_withdrawal,
       w.FECHA_TERMINO AS employment_end, w.FEC_ACTUALIZACION AS source_loaded_at,
       CASE WHEN @correo IS NOT NULL AND LOWER(LTRIM(RTRIM(w.EMAIL)))=@correo THEN 1 ELSE 0 END AS email_match
FROM dbo.FCT_TRABAJADOR_INFORMACION AS w
WHERE (@correo IS NOT NULL AND LOWER(LTRIM(RTRIM(w.EMAIL)))=@correo)
   OR (@documento IS NOT NULL AND LTRIM(RTRIM(w.DNI))=@documento)
   OR (@identificador IS NOT NULL AND LOWER(LTRIM(RTRIM(w.USUARIO)))=@identificador)
ORDER BY email_match DESC, w.DNI, w.USUARIO;

-- 01_cuentas_docentes_CASO.csv. Permite comprobar correo laboral y documento contra persona.
SELECT d.ID_DOCENTE AS teacher_id, d.ID_PERSONA AS person_id, d.PIDM AS source_pidm,
       d.NUMERO_DOCUMENTO AS document_number, d.TIPO_DOCUMENTO AS document_type,
       d.EMAIL_CORPORATIVO AS work_email, d.FECHAINGRESO AS teacher_start, d.FECHASALIDA AS teacher_end
FROM dbo.DIM_DOCENTE AS d
WHERE (@correo IS NOT NULL AND LOWER(LTRIM(RTRIM(d.EMAIL_CORPORATIVO)))=@correo)
   OR (@documento IS NOT NULL AND LTRIM(RTRIM(d.NUMERO_DOCUMENTO))=@documento)
ORDER BY d.ID_PERSONA,d.ID_DOCENTE;
