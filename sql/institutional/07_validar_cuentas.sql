-- SOLO LECTURA. Caso de una persona con cuentas de instituto, universidad y trabajo.
-- El documento es referencia de validación: NO se usa para encontrar los candidatos del primer resultado.
-- Completar valores en SSMS; no guardar datos personales en la copia publicada en Git.
DECLARE @documento_referencia nvarchar(64) = NULL;
DECLARE @correo_instituto nvarchar(255) = NULL;
DECLARE @correo_universidad nvarchar(255) = NULL;
DECLARE @correo_laboral nvarchar(255) = NULL;
SET @documento_referencia=NULLIF(LTRIM(RTRIM(@documento_referencia)),N'');

DECLARE @cuentas TABLE (account_context nvarchar(30), source_email nvarchar(255),
                       local_part nvarchar(255), email_domain nvarchar(255));
INSERT INTO @cuentas(account_context,source_email)
VALUES (N'institute',NULLIF(LOWER(LTRIM(RTRIM(@correo_instituto))),N'')),
       (N'university',NULLIF(LOWER(LTRIM(RTRIM(@correo_universidad))),N'')),
       (N'work',NULLIF(LOWER(LTRIM(RTRIM(@correo_laboral))),N''));
DELETE FROM @cuentas WHERE source_email IS NULL;
UPDATE @cuentas SET local_part=LEFT(source_email,CHARINDEX(N'@',source_email)-1),
                    email_domain=SUBSTRING(source_email,CHARINDEX(N'@',source_email)+1,255)
WHERE CHARINDEX(N'@',source_email)>1
  AND LEN(source_email)-LEN(REPLACE(source_email,N'@',N''))=1;
IF @documento_referencia IS NULL OR NOT EXISTS (SELECT 1 FROM @cuentas)
BEGIN
    SELECT N'Completa documento de referencia y los correos conocidos. Ejecuta todo el archivo.' AS instruction;
    RETURN;
END;

-- 07_busqueda_por_correo_CASO.csv. Conservar todos los métodos y candidatos; no elegir TOP 1.
-- account_context es la etiqueta de la prueba, no un rol deducido ni un atributo verificado.
-- Los métodos candidate prueban equivalencias; no demuestran por sí solos la titularidad del correo.
;WITH hits AS (
    SELECT q.account_context,q.source_email,N'stored_person_email' AS match_method,
           N'dbo.DIM_PERSONA' AS source_object,p.ID_PERSONA AS person_id,
           CONVERT(nvarchar(64),p.COD_DOCUMENTO) AS document_number
    FROM @cuentas AS q JOIN dbo.DIM_PERSONA AS p
      ON q.source_email=LOWER(LTRIM(RTRIM(p.CORREO_CORPORATIVO)))
      OR q.source_email=LOWER(LTRIM(RTRIM(p.CORREOPERSONAL1)))
      OR q.source_email=LOWER(LTRIM(RTRIM(p.CORREOPERSONAL2)))
    UNION ALL
    SELECT q.account_context,q.source_email,N'stored_work_email',N'dbo.FCT_TRABAJADOR_INFORMACION',
           p.ID_PERSONA,CONVERT(nvarchar(64),w.DNI)
    FROM @cuentas AS q JOIN dbo.FCT_TRABAJADOR_INFORMACION AS w ON q.source_email=LOWER(LTRIM(RTRIM(w.EMAIL)))
    LEFT JOIN dbo.DIM_PERSONA AS p ON LTRIM(RTRIM(p.COD_DOCUMENTO))=LTRIM(RTRIM(w.DNI))
    UNION ALL
    SELECT q.account_context,q.source_email,N'stored_teacher_email',N'dbo.DIM_DOCENTE',
           p.ID_PERSONA,CONVERT(nvarchar(64),d.NUMERO_DOCUMENTO)
    FROM @cuentas AS q JOIN dbo.DIM_DOCENTE AS d ON q.source_email=LOWER(LTRIM(RTRIM(d.EMAIL_CORPORATIVO)))
    LEFT JOIN dbo.DIM_PERSONA AS p ON CONVERT(nvarchar(80),p.ID_PERSONA)=LTRIM(RTRIM(CONVERT(nvarchar(80),d.ID_PERSONA)))
    UNION ALL
    SELECT q.account_context,q.source_email,N'stored_institute_work_email',N'IC.DIM_TRABAJADOR',
           p.ID_PERSONA,CONVERT(nvarchar(64),w.DNI)
    FROM @cuentas AS q JOIN IC.DIM_TRABAJADOR AS w ON q.source_email=LOWER(LTRIM(RTRIM(w.EMAIL)))
    LEFT JOIN dbo.DIM_PERSONA AS p ON LTRIM(RTRIM(p.COD_DOCUMENTO))=LTRIM(RTRIM(w.DNI))
    UNION ALL
    SELECT q.account_context,q.source_email,N'email_document_candidate',N'dbo.DIM_PERSONA',
           p.ID_PERSONA,CONVERT(nvarchar(64),p.COD_DOCUMENTO)
    FROM @cuentas AS q JOIN dbo.DIM_PERSONA AS p ON LTRIM(RTRIM(p.COD_DOCUMENTO))=q.local_part
    WHERE q.email_domain IN (N'continental.edu.pe',N'icontinental.edu.pe')
      AND LEN(q.local_part)=8 AND q.local_part NOT LIKE N'%[^0-9]%'
    UNION ALL
    SELECT q.account_context,q.source_email,N'email_student_code_candidate',N'dbo.DIM_ESTUDIANTE',
           p.ID_PERSONA,CONVERT(nvarchar(64),p.COD_DOCUMENTO)
    FROM @cuentas AS q JOIN dbo.DIM_ESTUDIANTE AS e
      ON q.local_part=LOWER(LTRIM(RTRIM(CONVERT(nvarchar(80),e.COD_ESTUDIANTE))))
    LEFT JOIN dbo.DIM_PERSONA AS p ON p.ID_PERSONA=e.ID_PERSONA
    WHERE q.email_domain IN (N'continental.edu.pe',N'icontinental.edu.pe')
    UNION ALL
    SELECT q.account_context,q.source_email,N'email_student_code_candidate',N'PSG.DIM_ESTUDIANTE',
           p.ID_PERSONA,CONVERT(nvarchar(64),p.COD_DOCUMENTO)
    FROM @cuentas AS q JOIN PSG.DIM_ESTUDIANTE AS e
      ON q.local_part=LOWER(LTRIM(RTRIM(CONVERT(nvarchar(80),e.COD_ESTUDIANTE))))
    LEFT JOIN dbo.DIM_PERSONA AS p ON p.ID_PERSONA=e.ID_PERSONA
    WHERE q.email_domain IN (N'continental.edu.pe',N'icontinental.edu.pe')
    UNION ALL
    -- Hipótesis contrastada en la primera muestra: i + ID_ALUMNO, sin dominio.
    -- Requiere otras muestras y validación de la convención; no inferir egreso ni vigencia.
    SELECT q.account_context,q.source_email,N'email_institute_code_candidate',N'IC.FCT_MATRICULA',
           p.ID_PERSONA,CONVERT(nvarchar(64),p.COD_DOCUMENTO)
    FROM @cuentas AS q JOIN IC.FCT_MATRICULA AS m
      ON SUBSTRING(q.local_part,2,255)=CONVERT(nvarchar(80),m.ID_ALUMNO)
    LEFT JOIN dbo.DIM_PERSONA AS p ON p.ID_PERSONA=m.ID_PERSONA
    WHERE q.email_domain IN (N'continental.edu.pe',N'icontinental.edu.pe')
      AND LEFT(q.local_part,1)=N'i' AND LEN(q.local_part)>1
      AND SUBSTRING(q.local_part,2,255) NOT LIKE N'%[^0-9]%'
)
SELECT DISTINCT q.account_context,q.source_email,COALESCE(h.match_method,N'unmatched') AS match_method,
       h.source_object,h.person_id,h.document_number,
       CASE WHEN h.document_number IS NULL THEN NULL
            WHEN LTRIM(RTRIM(h.document_number))=@documento_referencia THEN 1 ELSE 0 END AS reference_document_match
FROM @cuentas AS q LEFT JOIN hits AS h ON h.account_context=q.account_context AND h.source_email=q.source_email
ORDER BY q.account_context,q.source_email,match_method,h.source_object,h.person_id,h.document_number,reference_document_match;

-- 07_identificadores_instituto_CASO.csv. Aquí sí se usa el documento de control.
-- Permite contrastar ID_ALUMNO/ID_PERSONA con una matrícula conocida; no fabrica un correo con prefijo i.
SELECT DISTINCT p.ID_PERSONA AS person_id,m.ID_ALUMNO AS source_student_id,
       m.ID_PERIODOACAD AS period_id,pe.COD_PERIODO AS source_period_code,
       m.ID_PROGRAMAESTUDIOS AS program_id,pr.DESC_PROGRAMA AS program_name,
       m.ID_ESTADOGENERAL AS source_status_id
FROM dbo.DIM_PERSONA AS p JOIN IC.FCT_MATRICULA AS m ON m.ID_PERSONA=p.ID_PERSONA
LEFT JOIN IC.DIM_PERIODOACAD AS pe ON pe.ID_PERIODO=m.ID_PERIODOACAD
LEFT JOIN IC.DIM_PROGRAMAESTUDIOS AS pr ON pr.ID_PROGRAMA=m.ID_PROGRAMAESTUDIOS
WHERE LTRIM(RTRIM(p.COD_DOCUMENTO))=@documento_referencia
ORDER BY p.ID_PERSONA,m.ID_ALUMNO,m.ID_PERIODOACAD,pe.COD_PERIODO,m.ID_PROGRAMAESTUDIOS,pr.DESC_PROGRAMA,m.ID_ESTADOGENERAL;

-- 07_egreso_instituto_CASO.csv. Evidencia académica separada de matrícula histórica.
-- Los estados de certificado necesitan interpretación institucional; aptitud no equivale a egreso certificado.
SELECT DISTINCT p.ID_PERSONA AS person_id,g.ID_ALUMNO AS source_student_id,
       g.ID_PERIODOACAD AS period_id,pe.COD_PERIODO AS source_period_code,
       g.ID_PROGRAMAESTUDIOS AS program_id,pr.DESC_PROGRAMA AS program_name,
       g.ESTADOCERTIFICADOEGRESADO AS source_graduation_certificate_status,
       g.FECHACERTIFICADOEGRESADO AS source_graduation_certificate_date,
       g.ESTADOCERTIFICADOBACHILLER AS source_bachelor_certificate_status,
       g.ESTADOCERTIFICADOTITULO AS source_title_certificate_status,
       g.PERIODOMIN AS source_minimum_period
FROM dbo.DIM_PERSONA AS p JOIN IC.FCT_EGRESADOSAPTOS AS g ON g.ID_PERSONA=p.ID_PERSONA
LEFT JOIN IC.DIM_PERIODOACAD AS pe ON pe.ID_PERIODO=g.ID_PERIODOACAD
LEFT JOIN IC.DIM_PROGRAMAESTUDIOS AS pr ON pr.ID_PROGRAMA=g.ID_PROGRAMAESTUDIOS
WHERE LTRIM(RTRIM(p.COD_DOCUMENTO))=@documento_referencia
ORDER BY p.ID_PERSONA,g.ID_ALUMNO,g.ID_PERIODOACAD,pe.COD_PERIODO,g.ID_PROGRAMAESTUDIOS,pr.DESC_PROGRAMA,
         g.ESTADOCERTIFICADOEGRESADO,g.FECHACERTIFICADOEGRESADO,g.ESTADOCERTIFICADOBACHILLER,
         g.ESTADOCERTIFICADOTITULO,g.PERIODOMIN;

-- 07_fuentes_cuentas.csv. Metadatos de tablas/vistas accesibles con correo o login y claves de persona.
SELECT s.name AS schema_name,o.name AS object_name,c.name AS column_name,ty.name AS data_type
FROM sys.objects AS o JOIN sys.schemas AS s ON s.schema_id=o.schema_id
JOIN sys.columns AS c ON c.object_id=o.object_id
JOIN sys.types AS ty ON ty.user_type_id=c.user_type_id
WHERE o.type IN ('U','V') AND o.is_ms_shipped=0
  AND o.name NOT LIKE '%CENSO%' AND o.name NOT LIKE '%ENCUESTA%'
  AND EXISTS (SELECT 1 FROM sys.columns AS mail WHERE mail.object_id=o.object_id
      AND (mail.name LIKE '%CORREO%' OR mail.name LIKE '%EMAIL%' OR mail.name LIKE '%MAIL%' OR mail.name LIKE '%LOGIN%'))
  AND EXISTS (SELECT 1 FROM sys.columns AS identity_key WHERE identity_key.object_id=o.object_id
      AND (identity_key.name LIKE '%PERSONA%' OR identity_key.name LIKE '%DOCUMENTO%' OR identity_key.name LIKE '%DNI%'
           OR identity_key.name LIKE '%ALUMNO%' OR identity_key.name LIKE '%USUARIO%' OR identity_key.name LIKE '%ESTUDIANTE%'))
  AND (c.name LIKE '%CORREO%' OR c.name LIKE '%MAIL%' OR c.name LIKE '%LOGIN%' OR c.name LIKE '%PERSONA%'
       OR c.name LIKE '%DOCUMENTO%' OR c.name LIKE '%DNI%' OR c.name LIKE '%ALUMNO%' OR c.name LIKE '%USUARIO%' OR c.name LIKE '%ESTUDIANTE%')
ORDER BY s.name,o.name,c.column_id;
