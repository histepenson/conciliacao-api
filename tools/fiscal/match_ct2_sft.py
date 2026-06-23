"""
Matching entre lancamentos contabeis CT2 (razao com CT2_KEY) e notas fiscais SFT.

Extraido de services/pre_conferencia_service.py para ser reutilizado tambem pela
conciliacao de impostos (mesma logica, mas comparando contra uma coluna de valor
do SFT diferente de valcont, ex: valicm, valpis, valcof).
"""
import re
from typing import Optional

# Extrai o numero do documento (NF ou CT-e) de historicos como "PIS CREDITADO
# NFE 61" ou "COFINS AQUISICAO FRETE CTE 124" -- usado so' como fallback
# (fase 3) quando o lancamento nao tem CT2_KEY. O SFT guarda o numero do CT-e
# no mesmo campo "nf" (especie="CTE"), por isso o numero extraido casa direto.
_NF_HISTORICO_RE = re.compile(r"(?:NFE?|CTE)\.?\s*(\d+)", re.IGNORECASE)


def match_ct2_sft(
    ct2_recs: list[dict],
    sft_recs: list[dict],
    campo_valor_sft: str = "valcont",
    campo_valor_ct2: str = "debito",
    tolerancia: float = 0.10,
) -> tuple[list[dict], list[dict]]:
    """
    Casa lancamentos do CT2 (via CT2_KEY) com notas do SFT por
    (filial, nf, fornece) + valor (campo_valor_sft) dentro da tolerancia.

    campo_valor_ct2 indica qual coluna do CT2 usar como valor do lancamento
    ("debito" para notas de Entrada, "credito" para notas de Saida).

    Fases:
    1. Matching exato 1:1 por chave (filial+nf+fornece) + valor dentro da
       tolerancia.
    2. Reconciliacao por nota: para o que sobrou da fase 1 mas ainda tem
       chave valida, agrupa por (filial, nf, fornece). Se a soma do que
       restou do CT2 bater com a soma do que restou do SFT para aquela
       MESMA nota, marca tudo daquele grupo como casado (cobre o caso comum
       de o razao lancar a nota inteira em uma linha so enquanto o SFT lista
       por item, ou vice-versa). Se a soma nao bater exatamente, tenta uma
       cobertura greedy por valor so' dentro do proprio grupo (mesma nota) --
       cobre o caso de a nota ter um lancamento extra sem correspondencia no
       SFT (ex.: complemento de importacao) ao lado de um lancamento
       principal que bate perfeitamente.
    3. Fallback por historico (so' para CT2 SEM CT2_KEY): extrai o numero da
       NF do texto do historico (ex.: "PIS CREDITADO NFE 61" -> NF 61) e
       agrupa pelas notas do SFT que ainda sobraram com essa MESMA NF -- por
       (filial, NF) quando o CT2 tiver o campo "filial" (chave mais forte),
       ou so' por NF quando nao tiver (cargas antigas, antes do campo
       existir no CT2RAZCT5). Sem fornecedor no CT2 pra validar a chave
       inteira, so' segue se todas as notas do SFT daquele grupo forem do
       MESMO fornecedor (senao e' ambiguo -- NF repetida entre fornecedores
       diferentes -- e fica como diferenca). Com fornecedor unico, soma o
       grupo igual a fase 2 (cobre NF dividida em varios itens no SFT) e,
       se a soma nao bater, tenta cobertura greedy dentro do mesmo grupo.

    Propositalmente NAO ha fallback global (cruzando todo o dataset por
    valor, sem respeitar NF): isso ja causou falsos positivos reais --
    lancamentos sem nenhuma relacao com nota fiscal (ex.: credito de PIS
    sobre aluguel) "casando" so' porque a soma batia por coincidencia com
    sobras de outras notas. CT2 sem CT2_KEY cujo numero de NF (via
    historico) nao for unico entre as sobras do SFT, ou cujo grupo de NF
    nao reconciliou nem parcialmente na fase 2, fica como diferenca -- mais
    seguro deixar para revisao manual do que arriscar um match errado.

    Returns:
        Tupla (ct2_resultado, sft_resultado), cada item original com a chave
        booleana "matched" adicionada.
    """

    def _norm_filial(v: str) -> str:
        return v.strip().zfill(4)

    def _norm_nf(v: str) -> str:
        return v.strip().zfill(9)

    def _norm_cliefor(v: str) -> str:
        s = str(v or "").strip()
        return s[:6].zfill(6) if len(s) >= 6 else s.zfill(6)

    def _extrair_chave_ct2(rec: dict):
        key = str(rec.get("ct2_key") or "").strip()
        if len(key) < 22:
            return None
        # O segmento da NF (posicoes 4:13) nao tem largura fixa de digitos
        # significativos no CT2_KEY real do Protheus -- varia por tipo de
        # documento (NF-e, CT-e, etc), vindo com espacos de preenchimento a
        # direita em vez de zeros a esquerda (ex.: "00005439 ", "001447   ").
        # _norm_nf (strip + zfill(9)) recanonicaliza para o mesmo formato do
        # SFT independente da largura original.
        return (_norm_filial(key[0:4]), _norm_nf(key[4:13]), _norm_cliefor(key[16:22]))

    def _chave_sft(rec: dict):
        filial = str(rec.get("filial") or "").strip()
        nf = str(rec.get("nf") or "").strip()
        cliefor = str(rec.get("cliefor") or "").strip()
        if not filial or not nf:
            return None
        return (_norm_filial(filial), _norm_nf(nf), _norm_cliefor(cliefor))

    def _extrair_nf_historico(historico: str) -> Optional[str]:
        m = _NF_HISTORICO_RE.search(historico or "")
        if not m:
            return None
        return _norm_nf(m.group(1))

    def _cobrir_greedy(indices, recs, chave_v, budget):
        ordered = sorted(indices, key=lambda i: -round(float(recs[i].get(chave_v) or 0), 2))
        cobertos: set = set()
        restante = budget
        for i in ordered:
            v = round(float(recs[i].get(chave_v) or 0), 2)
            if v == 0:
                cobertos.add(i)
                continue
            if restante <= 0:
                break
            if restante >= v - 0.01:
                cobertos.add(i)
                restante = round(restante - v, 2)
        return cobertos

    # Indice SFT por (filial, nf, fornece) -> lista de indices
    sft_por_doc: dict = {}
    for i, s in enumerate(sft_recs):
        chave = _chave_sft(s)
        if chave:
            sft_por_doc.setdefault(chave, []).append(i)

    # ==========================================================
    # Fase 1: matching exato 1:1 por CT2_KEY + valor (tolerancia)
    # ==========================================================
    sft_matched: set = set()
    ct2_matched_set: set = set()
    ct2_pendente_com_chave: list = []  # tem ct2_key valida mas nao casou 1:1
    ct2_sem_chave: list = []  # sem ct2_key -- candidato ao fallback por historico (fase 3)

    for i, rec in enumerate(ct2_recs):
        valor_ct2 = round(float(rec.get(campo_valor_ct2) or 0), 2)
        if valor_ct2 == 0:
            ct2_matched_set.add(i)
            continue
        chave = _extrair_chave_ct2(rec)
        if chave is None:
            # Sem CT2_KEY valida -- tentativa de recuperacao via historico na fase 3.
            ct2_sem_chave.append(i)
            continue

        matched = False
        for idx in sft_por_doc.get(chave, []):
            if idx not in sft_matched:
                valor_sft = round(float(sft_recs[idx].get(campo_valor_sft) or 0), 2)
                if abs(valor_sft - valor_ct2) <= tolerancia:
                    sft_matched.add(idx)
                    ct2_matched_set.add(i)
                    matched = True
                    break

        if not matched:
            ct2_pendente_com_chave.append(i)

    # ==========================================================
    # Fase 2: reconciliacao por nota (soma do que restou, por chave)
    # ==========================================================
    ct2_por_chave: dict = {}
    for i in ct2_pendente_com_chave:
        chave = _extrair_chave_ct2(ct2_recs[i])
        ct2_por_chave.setdefault(chave, []).append(i)

    sft_pendente_por_chave: dict = {}
    for i in range(len(sft_recs)):
        if i in sft_matched:
            continue
        chave = _chave_sft(sft_recs[i])
        if chave:
            sft_pendente_por_chave.setdefault(chave, []).append(i)

    for chave, ct2_idxs in ct2_por_chave.items():
        sft_idxs = sft_pendente_por_chave.get(chave, [])
        if not sft_idxs:
            continue  # nenhuma nota correspondente sobrou -- fica como diferenca
        total_ct2 = round(sum(float(ct2_recs[i].get(campo_valor_ct2) or 0) for i in ct2_idxs), 2)
        total_sft = round(sum(float(sft_recs[i].get(campo_valor_sft) or 0) for i in sft_idxs), 2)
        if abs(total_ct2 - total_sft) <= tolerancia:
            ct2_matched_set.update(ct2_idxs)
            sft_matched.update(sft_idxs)
            continue

        # Soma do grupo nao bate exatamente -- comum quando a NF tem um
        # lancamento "extra" sem correspondencia no SFT (ex.: complemento de
        # importacao) ao lado do lancamento principal que bate perfeitamente.
        # Tenta cobertura greedy por valor so' dentro da MESMA nota -- nunca
        # mistura com outras NFs do dataset. O que nao for coberto fica como
        # diferenca (sem fallback global, ver docstring).
        ct2_cob_grupo = _cobrir_greedy(ct2_idxs, ct2_recs, campo_valor_ct2, total_sft)
        sft_cob_grupo = _cobrir_greedy(sft_idxs, sft_recs, campo_valor_sft, total_ct2)
        ct2_matched_set.update(ct2_cob_grupo)
        sft_matched.update(sft_cob_grupo)

    # ==========================================================
    # Fase 3: fallback por (filial)+NF do historico (so' para CT2 sem CT2_KEY)
    # ==========================================================
    # Indice por NF sozinha (fallback quando o CT2 nao tem filial) e por
    # (filial, NF) quando o CT2 tiver o campo "filial" -- chave mais forte,
    # reduz a chance de colisao de NF entre fornecedores/filiais diferentes.
    sft_pendente_por_nf: dict = {}
    sft_pendente_por_filial_nf: dict = {}
    for i in range(len(sft_recs)):
        if i in sft_matched:
            continue
        nf = str(sft_recs[i].get("nf") or "").strip()
        if not nf:
            continue
        nf_norm = _norm_nf(nf)
        sft_pendente_por_nf.setdefault(nf_norm, []).append(i)
        filial = str(sft_recs[i].get("filial") or "").strip()
        if filial:
            sft_pendente_por_filial_nf.setdefault((_norm_filial(filial), nf_norm), []).append(i)

    ct2_sem_chave_por_grupo: dict = {}
    for i in ct2_sem_chave:
        nf = _extrair_nf_historico(ct2_recs[i].get("historico"))
        if nf is None:
            continue
        filial_ct2 = str(ct2_recs[i].get("filial") or "").strip()
        grupo = (_norm_filial(filial_ct2), nf) if filial_ct2 else nf
        ct2_sem_chave_por_grupo.setdefault(grupo, []).append(i)

    for grupo, ct2_idxs in ct2_sem_chave_por_grupo.items():
        if isinstance(grupo, tuple):
            candidatos = sft_pendente_por_filial_nf.get(grupo, [])
        else:
            candidatos = sft_pendente_por_nf.get(grupo, [])
        if not candidatos:
            continue  # nenhuma nota com essa (filial+)NF sobrou no SFT -- fica como diferenca

        fornecedores = {str(sft_recs[idx].get("cliefor") or "").strip() for idx in candidatos}
        if len(fornecedores) > 1:
            # NF repetida entre fornecedores diferentes -- sem CT2_KEY nao ha
            # como confirmar de qual fornecedor e', ambiguo. Fica como diferenca.
            continue

        total_ct2 = round(sum(float(ct2_recs[i].get(campo_valor_ct2) or 0) for i in ct2_idxs), 2)
        total_sft = round(sum(float(sft_recs[idx].get(campo_valor_sft) or 0) for idx in candidatos), 2)
        if abs(total_ct2 - total_sft) <= tolerancia:
            # Cobre tanto o 1:1 quanto a NF dividida em varios itens no SFT
            # (ou varios lancamentos do CT2 sem chave para a mesma NF).
            ct2_matched_set.update(ct2_idxs)
            sft_matched.update(candidatos)
            continue

        # Soma nao bate exatamente -- tenta cobertura greedy so' dentro da
        # mesma NF, mesma logica da fase 2.
        ct2_cob = _cobrir_greedy(ct2_idxs, ct2_recs, campo_valor_ct2, total_sft)
        sft_cob = _cobrir_greedy(candidatos, sft_recs, campo_valor_sft, total_ct2)
        ct2_matched_set.update(ct2_cob)
        sft_matched.update(sft_cob)

    ct2_resultado = [
        {**rec, "matched": i in ct2_matched_set}
        for i, rec in enumerate(ct2_recs)
    ]
    sft_resultado = [
        {**s, "matched": i in sft_matched}
        for i, s in enumerate(sft_recs)
    ]
    return ct2_resultado, sft_resultado
