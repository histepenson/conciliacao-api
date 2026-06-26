-- Descoberta da sequencia para LP 610 - lancamento_padrao.sequencia esta
-- vazia, entao deriva direto da carga CT2RAZCT5 em cache (ct2_sequen ou,
-- na falta, os 7 primeiros caracteres de ct2_origem "LP-SEQUENCIA").
WITH ultima_carga AS (
    SELECT DISTINCT ON (empresa_id) id AS carga_id, empresa_id
    FROM concilia.protheus_carga
    WHERE tipo_relatorio = 'CT2RAZCT5' AND status = 'concluido'
    ORDER BY empresa_id, finalizado_em DESC
)
SELECT DISTINCT
    uc.empresa_id,
    e.nome AS empresa,
    TRIM(pcr.dados_json->>'ct2_lp') AS lp_codigo,
    COALESCE(
        NULLIF(TRIM(pcr.dados_json->>'ct2_sequen'), ''),
        NULLIF(split_part(LEFT(TRIM(pcr.dados_json->>'ct2_origem'), 7), '-', 2), '')
    ) AS sequencia_descoberta,
    TRIM(COALESCE(pcr.dados_json->>'ct5_desc', '')) AS descricao
FROM ultima_carga uc
JOIN concilia.protheus_carga_registro pcr ON pcr.carga_id = uc.carga_id
JOIN concilia.empresa e ON e.id = uc.empresa_id
WHERE TRIM(pcr.dados_json->>'ct2_lp') = '610'
ORDER BY uc.empresa_id, sequencia_descoberta;

-- Descricoes cadastradas para LP 610, sequencias 008 e 030 (cruzando com o cadastro)
SELECT
    lp.empresa_id,
    e.nome AS empresa,
    lp.lp_codigo,
    lp.sequencia,
    lp.descricao,
    lp.ativo
FROM concilia.lancamento_padrao lp
JOIN concilia.empresa e ON e.id = lp.empresa_id
WHERE lp.lp_codigo = '610'
  AND lp.sequencia IN ('008', '030')
ORDER BY lp.empresa_id, lp.sequencia;

-- Consulta anterior (inspecao de registros de uma carga) - mantida como referencia:
-- SELECT
--     r.id,
--     r.carga_id,
--     r.sequencia,
--     r.dados_json
-- FROM concilia.protheus_carga_registro r
-- WHERE r.carga_id = 5
-- ORDER BY r.sequencia

-- Backfill de lancamento_padrao.sequencia para LP 610 (Saida) - mesma logica
-- ja aplicada para LP 650 (Entrada). Deriva a sequencia da ULTIMA carga
-- CT2RAZCT5 concluida de cada empresa (ja em cache, nao busca nada no
-- Protheus): usa ct2_sequen quando vier preenchido, senao extrai dos
-- primeiros 7 caracteres de ct2_origem ("LP-SEQUENCIA"), igual ao JOIN do
-- ZCT2RAZCT5.prw. So atualiza onde sequencia esta vazia/nula.

-- 1) PREVIEW - rode primeiro para confirmar o que seria alterado
WITH ultima_carga AS (
    SELECT DISTINCT ON (empresa_id) id AS carga_id, empresa_id
    FROM concilia.protheus_carga
    WHERE tipo_relatorio = 'CT2RAZCT5' AND status = 'concluido'
    ORDER BY empresa_id, finalizado_em DESC
),
pares AS (
    SELECT DISTINCT ON (uc.empresa_id, lp_codigo, descricao)
        uc.empresa_id,
        TRIM(pcr.dados_json->>'ct2_lp') AS lp_codigo,
        TRIM(COALESCE(pcr.dados_json->>'ct5_desc', '')) AS descricao,
        COALESCE(
            NULLIF(TRIM(pcr.dados_json->>'ct2_sequen'), ''),
            NULLIF(split_part(LEFT(TRIM(pcr.dados_json->>'ct2_origem'), 7), '-', 2), '')
        ) AS sequencia_nova
    FROM ultima_carga uc
    JOIN concilia.protheus_carga_registro pcr ON pcr.carga_id = uc.carga_id
    WHERE TRIM(pcr.dados_json->>'ct2_lp') = '610'
    ORDER BY uc.empresa_id, lp_codigo, descricao
)
SELECT
    lp.id,
    lp.empresa_id,
    lp.lp_codigo,
    lp.descricao,
    lp.sequencia AS sequencia_atual,
    p.sequencia_nova
FROM concilia.lancamento_padrao lp
JOIN pares p
  ON lp.empresa_id = p.empresa_id
 AND lp.lp_codigo = p.lp_codigo
 AND COALESCE(lp.descricao, '') = p.descricao
WHERE (lp.sequencia IS NULL OR lp.sequencia = '')
  AND p.sequencia_nova IS NOT NULL;

-- 2) UPDATE - so rodar depois de revisar o preview acima
-- WITH ultima_carga AS (
--     SELECT DISTINCT ON (empresa_id) id AS carga_id, empresa_id
--     FROM concilia.protheus_carga
--     WHERE tipo_relatorio = 'CT2RAZCT5' AND status = 'concluido'
--     ORDER BY empresa_id, finalizado_em DESC
-- ),
-- pares AS (
--     SELECT DISTINCT ON (uc.empresa_id, lp_codigo, descricao)
--         uc.empresa_id,
--         TRIM(pcr.dados_json->>'ct2_lp') AS lp_codigo,
--         TRIM(COALESCE(pcr.dados_json->>'ct5_desc', '')) AS descricao,
--         COALESCE(
--             NULLIF(TRIM(pcr.dados_json->>'ct2_sequen'), ''),
--             NULLIF(split_part(LEFT(TRIM(pcr.dados_json->>'ct2_origem'), 7), '-', 2), '')
--         ) AS sequencia_nova
--     FROM ultima_carga uc
--     JOIN concilia.protheus_carga_registro pcr ON pcr.carga_id = uc.carga_id
--     WHERE TRIM(pcr.dados_json->>'ct2_lp') = '610'
--     ORDER BY uc.empresa_id, lp_codigo, descricao
-- )
-- UPDATE concilia.lancamento_padrao lp
-- SET sequencia = p.sequencia_nova, updated_at = now()
-- FROM pares p
-- WHERE lp.empresa_id = p.empresa_id
--   AND lp.lp_codigo = p.lp_codigo
--   AND COALESCE(lp.descricao, '') = p.descricao
--   AND (lp.sequencia IS NULL OR lp.sequencia = '')
--   AND p.sequencia_nova IS NOT NULL;
