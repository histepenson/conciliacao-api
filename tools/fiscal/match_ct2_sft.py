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

    Fallback: para CT2 sem CT2_KEY ou sem correspondencia exata, aplica
    cobertura greedy por valor entre os registros restantes de cada lado.

    Returns:
        Tupla (ct2_resultado, sft_resultado), cada item original com a chave
        booleana "matched" adicionada.
    """

    def _extrair_chave_ct2(rec: dict):
        key = str(rec.get("ct2_key") or "").strip()
        if len(key) < 22:
            return None
        return (key[0:4], key[4:13], key[16:22].strip())

    # Indice SFT por (filial, nf, fornece) -> lista de indices
    sft_por_doc: dict = {}
    for i, s in enumerate(sft_recs):
        filial = str(s.get("filial") or "").strip()
        nf = str(s.get("nf") or "").strip()
        cliefor = str(s.get("cliefor") or "").strip()
        if filial and nf:
            sft_por_doc.setdefault((filial, nf, cliefor), []).append(i)

    # Tenta matching por CT2_KEY + valor (tolerancia)
    sft_matched: set = set()
    ct2_matched_set: set = set()
    sem_chave: list = []

    for i, rec in enumerate(ct2_recs):
        valor_ct2 = round(float(rec.get(campo_valor_ct2) or 0), 2)
        if valor_ct2 == 0:
            ct2_matched_set.add(i)
            continue
        chave = _extrair_chave_ct2(rec)
        if chave is None:
            sem_chave.append(i)
            continue

        filial, nf, fornece = chave
        matched = False

        for idx in sft_por_doc.get((filial, nf, fornece), []):
            if idx not in sft_matched:
                valor_sft = round(float(sft_recs[idx].get(campo_valor_sft) or 0), 2)
                if abs(valor_sft - valor_ct2) <= tolerancia:
                    sft_matched.add(idx)
                    ct2_matched_set.add(i)
                    matched = True
                    break

        if not matched:
            sem_chave.append(i)

    # Fallback greedy para CT2 sem chave / sem correspondencia
    sft_nao_cobertos = [i for i in range(len(sft_recs)) if i not in sft_matched]
    if sem_chave and sft_nao_cobertos:
        total_restante_ct2 = round(
            sum(float(ct2_recs[i].get(campo_valor_ct2) or 0) for i in sem_chave), 2
        )
        total_restante_sft = round(
            sum(float(sft_recs[i].get(campo_valor_sft) or 0) for i in sft_nao_cobertos), 2
        )

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
