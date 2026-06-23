"""
Matching entre movimentos de Ativo Fixo (SN3/SN4) e o razao contabil
(CT2RAZCT5), usando o campo ct2_key como chave de casamento.

Diferente do matching fiscal (tools/fiscal/match_ct2_sft.py), aqui nao ha
fatiamento posicional de ct2_key -- a chave do lado SN3/SN4 e' construida
pela concatenacao dos proprios campos do movimento e comparada por igualdade
de string direta contra ct2_key (ver protheus/ZSN3API.prw / ZSN4API.prw e o
formato esperado em services/ativo_fixo_service.py).
"""
from typing import Optional


def match_sn_razao(
    sn_recs: list[dict],
    razao_recs: list[dict],
    montar_chave_sn,
    campo_valor_sn: str,
    campo_valor_razao: str,
    tolerancia: float = 0.10,
) -> tuple[list[dict], list[dict]]:
    """
    Casa lancamentos de Ativo Fixo (SN3 ou SN4) com linhas do razao por
    igualdade exata de chave (montar_chave_sn(rec) == razao_rec["ct2_key"])
    + valor (campo_valor_sn do SN x campo_valor_razao do razao) dentro da
    tolerancia.

    montar_chave_sn: funcao(rec_sn) -> str, monta a chave esperada em
    ct2_key a partir dos campos brutos do registro SN3/SN4.

    Fases:
    1. Matching exato 1:1 por chave + valor dentro da tolerancia.
    2. Reconciliacao por grupo: para o que sobrou da fase 1 mas tem chave
       valida, agrupa por chave. Se a soma do que restou do SN bater com a
       soma do que restou do razao para aquele MESMO grupo, marca tudo como
       casado. Senao, tenta cobertura greedy por valor dentro do proprio
       grupo (nunca mistura com outra chave).

    Propositalmente NAO ha fallback global (cruzando todo o dataset por
    valor, sem respeitar a chave) -- mesma decisao de seguranca tomada em
    match_ct2_sft (evitar falso positivo por coincidencia de soma entre
    movimentos sem relacao).

    Returns:
        Tupla (sn_resultado, razao_resultado), cada item original com a
        chave booleana "matched" adicionada.
    """

    def _cobrir_greedy(indices, recs, campo_valor, budget):
        ordered = sorted(indices, key=lambda i: -round(float(recs[i].get(campo_valor) or 0), 2))
        cobertos: set = set()
        restante = budget
        for i in ordered:
            v = round(float(recs[i].get(campo_valor) or 0), 2)
            if v == 0:
                cobertos.add(i)
                continue
            if restante <= 0:
                break
            if restante >= v - 0.01:
                cobertos.add(i)
                restante = round(restante - v, 2)
        return cobertos

    # Indice razao por ct2_key -> lista de indices
    razao_por_chave: dict = {}
    for i, r in enumerate(razao_recs):
        chave = str(r.get("ct2_key") or "").strip()
        if chave:
            razao_por_chave.setdefault(chave, []).append(i)

    # ==========================================================
    # Fase 1: matching exato 1:1 por chave + valor (tolerancia)
    # ==========================================================
    razao_matched: set = set()
    sn_matched_set: set = set()
    sn_pendente_com_chave: list = []  # tem chave valida mas nao casou 1:1

    for i, rec in enumerate(sn_recs):
        valor_sn = round(float(rec.get(campo_valor_sn) or 0), 2)
        if valor_sn == 0:
            sn_matched_set.add(i)
            continue
        chave = montar_chave_sn(rec)
        if not chave:
            continue

        matched = False
        for idx in razao_por_chave.get(chave, []):
            if idx not in razao_matched:
                valor_razao = round(float(razao_recs[idx].get(campo_valor_razao) or 0), 2)
                if abs(valor_razao - valor_sn) <= tolerancia:
                    razao_matched.add(idx)
                    sn_matched_set.add(i)
                    matched = True
                    break

        if not matched:
            sn_pendente_com_chave.append(i)

    # ==========================================================
    # Fase 2: reconciliacao por grupo (soma do que restou, por chave)
    # ==========================================================
    sn_por_chave: dict = {}
    for i in sn_pendente_com_chave:
        chave = montar_chave_sn(sn_recs[i])
        sn_por_chave.setdefault(chave, []).append(i)

    razao_pendente_por_chave: dict = {}
    for i in range(len(razao_recs)):
        if i in razao_matched:
            continue
        chave = str(razao_recs[i].get("ct2_key") or "").strip()
        if chave:
            razao_pendente_por_chave.setdefault(chave, []).append(i)

    for chave, sn_idxs in sn_por_chave.items():
        razao_idxs = razao_pendente_por_chave.get(chave, [])
        if not razao_idxs:
            continue  # nenhuma linha de razao correspondente sobrou -- fica como diferenca
        total_sn = round(sum(float(sn_recs[i].get(campo_valor_sn) or 0) for i in sn_idxs), 2)
        total_razao = round(sum(float(razao_recs[i].get(campo_valor_razao) or 0) for i in razao_idxs), 2)
        if abs(total_sn - total_razao) <= tolerancia:
            sn_matched_set.update(sn_idxs)
            razao_matched.update(razao_idxs)
            continue

        # Soma do grupo nao bate exatamente -- tenta cobertura greedy por
        # valor so' dentro do mesmo grupo (nunca mistura com outra chave).
        sn_cob_grupo = _cobrir_greedy(sn_idxs, sn_recs, campo_valor_sn, total_razao)
        razao_cob_grupo = _cobrir_greedy(razao_idxs, razao_recs, campo_valor_razao, total_sn)
        sn_matched_set.update(sn_cob_grupo)
        razao_matched.update(razao_cob_grupo)

    sn_resultado = [
        {**rec, "matched": i in sn_matched_set}
        for i, rec in enumerate(sn_recs)
    ]
    razao_resultado = [
        {**r, "matched": i in razao_matched}
        for i, r in enumerate(razao_recs)
    ]
    return sn_resultado, razao_resultado
