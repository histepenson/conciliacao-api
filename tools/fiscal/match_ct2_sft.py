"""
Matching entre lancamentos contabeis CT2 (razao com CT2_KEY) e notas fiscais SFT.

Extraido de services/pre_conferencia_service.py para ser reutilizado tambem pela
conciliacao de impostos (mesma logica, mas comparando contra uma coluna de valor
do SFT diferente de valcont, ex: valicm, valpis, valcof).
"""
from typing import Optional


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
       principal que bate perfeitamente; o que nao for coberto cai pra fase
       3.
    3. Fallback greedy global por valor, so para CT2 sem CT2_KEY (ou cujo
       grupo de NF nao reconciliou nem parcialmente na fase 2).

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
    ct2_sem_chave: list = []  # nao tem ct2_key valida

    for i, rec in enumerate(ct2_recs):
        valor_ct2 = round(float(rec.get(campo_valor_ct2) or 0), 2)
        if valor_ct2 == 0:
            ct2_matched_set.add(i)
            continue
        chave = _extrair_chave_ct2(rec)
        if chave is None:
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

    sem_chave: list = list(ct2_sem_chave)
    for chave, ct2_idxs in ct2_por_chave.items():
        sft_idxs = sft_pendente_por_chave.get(chave, [])
        total_ct2 = round(sum(float(ct2_recs[i].get(campo_valor_ct2) or 0) for i in ct2_idxs), 2)
        total_sft = round(sum(float(sft_recs[i].get(campo_valor_sft) or 0) for i in sft_idxs), 2)
        if sft_idxs and abs(total_ct2 - total_sft) <= tolerancia:
            ct2_matched_set.update(ct2_idxs)
            sft_matched.update(sft_idxs)
            continue

        # Soma do grupo nao bate exatamente -- comum quando a NF tem um
        # lancamento "extra" sem correspondencia no SFT (ex.: complemento de
        # importacao) ao lado do lancamento principal que bate perfeitamente.
        # Em vez de descartar o grupo inteiro pro fallback global (onde ele
        # compete por valor com NFs de todo o dataset), tenta uma cobertura
        # greedy so' dentro da MESMA nota primeiro -- mantem a precisao de
        # nao misturar NFs diferentes.
        if sft_idxs:
            ct2_cob_grupo = _cobrir_greedy(ct2_idxs, ct2_recs, campo_valor_ct2, total_sft)
            sft_cob_grupo = _cobrir_greedy(sft_idxs, sft_recs, campo_valor_sft, total_ct2)
            ct2_matched_set.update(ct2_cob_grupo)
            sft_matched.update(sft_cob_grupo)
            sem_chave.extend(i for i in ct2_idxs if i not in ct2_cob_grupo)
        else:
            sem_chave.extend(ct2_idxs)

    # ==========================================================
    # Fase 3: fallback greedy global por valor (ultimo recurso)
    # ==========================================================
    sft_nao_cobertos = [i for i in range(len(sft_recs)) if i not in sft_matched]
    if sem_chave and sft_nao_cobertos:
        total_restante_ct2 = round(
            sum(float(ct2_recs[i].get(campo_valor_ct2) or 0) for i in sem_chave), 2
        )
        total_restante_sft = round(
            sum(float(sft_recs[i].get(campo_valor_sft) or 0) for i in sft_nao_cobertos), 2
        )

        ct2_cob = _cobrir_greedy(sem_chave, ct2_recs, campo_valor_ct2, total_restante_sft)
        sft_cob = _cobrir_greedy(sft_nao_cobertos, sft_recs, campo_valor_sft, total_restante_ct2)
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
