-- SOLO LECTURA. Usar 09_extraer_perfiles_preparado.sql generado desde el lote revisado.
-- Ejecutar una vez y guardar la única cuadrícula, con encabezados, como 09_perfiles_lote.csv.
-- Cada fila contiene evidencia de una fuente; varias filas no son nuevas operaciones.
-- profile_data es JSON para procesamiento local: conservarlo completo al guardar el CSV.
DECLARE @perfiles TABLE (
    request_id int PRIMARY KEY, source_email nvarchar(255), activity_date date,
    record_count int, source_datasets nvarchar(100), person_id numeric(18,0),
    account_scope nvarchar(30)
);
-- INSERT_PROFILE_REQUESTS_HERE
IF NOT EXISTS (SELECT 1 FROM @perfiles)
BEGIN
    SELECT N'Abre el archivo preparado con los correos y personas del lote revisado.' AS instruction;
    RETURN;
END;

SELECT q.request_id,q.source_email,q.activity_date,q.record_count,q.source_datasets,
       q.person_id,q.account_scope,identity_person.NOM_COMPLETOS AS identity_full_name,
       COALESCE(evidence.profile_source,N'missing_profile') AS profile_source,
       COALESCE(evidence.profile_data,N'{}') AS profile_data
FROM @perfiles AS q
LEFT JOIN dbo.DIM_PERSONA AS identity_person ON identity_person.ID_PERSONA=q.person_id
OUTER APPLY (
    SELECT N'identity' AS profile_source,
           (SELECT identity_person.ID_PERSONA AS person_id,identity_person.COD_DOCUMENTO AS source_identifier,
                   identity_person.NOM_COMPLETOS AS full_name
            FOR JSON PATH, INCLUDE_NULL_VALUES, WITHOUT_ARRAY_WRAPPER) AS profile_data
    WHERE identity_person.ID_PERSONA IS NOT NULL
-- PROFILE_EVIDENCE_HERE
) AS evidence
ORDER BY q.request_id,evidence.profile_source;
