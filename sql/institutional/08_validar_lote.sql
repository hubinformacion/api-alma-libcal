-- SOLO LECTURA institucional. La preparación local incorpora correos desde SQLite.
-- Ejecutar el archivo PREPARADO, no esta plantilla vacía.
-- Guardar la única cuadrícula como 08_validacion_lote.csv, con encabezados.
-- matched_identity confirma un candidato único, no valida matrícula/rol ni titularidad por sí solo.
DECLARE @cuentas TABLE (
    request_id int PRIMARY KEY, source_email nvarchar(255), activity_date date,
    record_count int, source_datasets nvarchar(100),
    local_part nvarchar(255), email_domain nvarchar(255)
);
-- INSERT_REQUESTS_HERE
IF NOT EXISTS (SELECT 1 FROM @cuentas)
BEGIN
    SELECT N'Ejecuta el archivo preparado por scripts/prepare_institutional_check.py.' AS instruction;
    RETURN;
END;
UPDATE @cuentas SET local_part=LEFT(source_email,CHARINDEX(N'@',source_email)-1),
                    email_domain=SUBSTRING(source_email,CHARINDEX(N'@',source_email)+1,255)
WHERE CHARINDEX(N'@',source_email)>1
  AND LEN(source_email)-LEN(REPLACE(source_email,N'@',N''))=1
  AND SUBSTRING(source_email,CHARINDEX(N'@',source_email)+1,255) LIKE N'%.%';

-- La preparación reutiliza los métodos de 07, sin un DNI de referencia.
;WITH hits AS (
-- BEGIN_SHARED_MATCHES
    SELECT CAST(NULL AS int) AS request_id,CAST(NULL AS nvarchar(255)) AS source_email,
           CAST(NULL AS nvarchar(100)) AS match_method,CAST(NULL AS nvarchar(128)) AS source_object,
           CAST(NULL AS numeric(18,0)) AS person_id,CAST(NULL AS nvarchar(64)) AS document_number
    WHERE 1=0
-- END_SHARED_MATCHES
), scoped_hits AS (
    SELECT DISTINCT request_id,person_id,match_method,
        CASE WHEN match_method IN (N'stored_work_email',N'stored_teacher_email',N'stored_institute_work_email') THEN N'labor'
             WHEN match_method=N'email_institute_code_candidate' THEN N'institute'
             WHEN match_method IN (N'email_document_candidate',N'email_student_code_candidate') THEN N'university'
             ELSE NULL END AS profile_scope
    FROM hits
), summary AS (
    SELECT q.request_id,COUNT(DISTINCT h.person_id) AS candidate_person_count,
           COUNT(h.match_method) AS source_hit_count,MAX(h.person_id) AS only_person_candidate,
           COUNT(DISTINCT CASE WHEN h.person_id IS NOT NULL THEN h.profile_scope END) AS scope_count,
           MAX(CASE WHEN h.person_id IS NOT NULL THEN h.profile_scope END) AS only_scope_candidate,
           MAX(CASE WHEN h.match_method LIKE N'stored_%' THEN 1 ELSE 0 END) AS registered_email_match,
           MAX(CASE WHEN h.match_method=N'email_document_candidate' THEN 1 ELSE 0 END) AS document_prefix_match,
           MAX(CASE WHEN h.match_method=N'email_student_code_candidate' THEN 1 ELSE 0 END) AS student_code_match,
           MAX(CASE WHEN h.match_method=N'email_institute_code_candidate' THEN 1 ELSE 0 END) AS institute_code_match
    FROM @cuentas AS q LEFT JOIN scoped_hits AS h ON h.request_id=q.request_id
    GROUP BY q.request_id
)
SELECT q.request_id,q.source_email,q.activity_date,q.record_count,q.source_datasets,
       CASE WHEN q.local_part IS NULL THEN N'invalid_email'
            WHEN s.candidate_person_count>1 THEN N'ambiguous'
            WHEN s.candidate_person_count=1 THEN N'matched_identity'
            WHEN s.source_hit_count>0 THEN N'source_without_person'
            ELSE N'unmatched' END AS identity_status,
       CASE WHEN q.local_part IS NOT NULL AND s.candidate_person_count=1
            THEN s.only_person_candidate ELSE NULL END AS person_id,
       s.candidate_person_count,s.source_hit_count,
       CASE WHEN q.local_part IS NULL OR s.candidate_person_count<>1 THEN N'unresolved'
            WHEN s.scope_count>1 THEN N'ambiguous'
            WHEN s.scope_count=1 THEN s.only_scope_candidate ELSE N'unresolved' END AS account_scope,
       s.registered_email_match,s.document_prefix_match,s.student_code_match,s.institute_code_match
FROM @cuentas AS q JOIN summary AS s ON s.request_id=q.request_id
ORDER BY q.request_id;
