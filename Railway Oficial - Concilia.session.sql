SELECT
    r.id,
    r.carga_id,
    r.sequencia,
    r.dados_json
FROM concilia.protheus_carga_registro r
WHERE r.carga_id = 5
ORDER BY r.sequencia
