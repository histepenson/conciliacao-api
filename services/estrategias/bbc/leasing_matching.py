# services/estrategias/bbc/leasing_matching.py
"""
Motor de conferencia da BBC: compara a base unificada (LeasingMovimentacao)
contra o razao contabil (LeasingRazaoContabil), em cascata, exatamente
como definido pelo usuario:

  1) Nivel macro: soma total de debito da base vs soma total de debito do
     razao (idem credito). Se bater (tolerancia R$ 0,01), ja da' pra
     considerar conciliado no nivel geral -- mas o processo continua pros
     niveis seguintes de qualquer forma, pra dar o detalhe por natureza.
  2) Nivel por natureza: agrupa a base por natureza (codigo cadastrado em
     Operacao Financeira, que tambem diz se e' D ou C) e agrupa o razao
     por (historico, lado D/C). Uma natureza pode ser a soma de 1 ou mais
     grupos do razao -- tenta achar essa combinacao (ate
     MAX_ITENS_COMBINACAO grupos do razao por natureza).
  3) Nivel combinado: pras naturezas que ainda ficaram divergentes no
     passo 2, tenta combinar 2 ou mais delas (mesmo lado D/C) pra ver se
     a soma bate com 1 linha do razao que sobrou -- caso real confirmado
     pelo usuario ("pode existir 1 linha no razao que e' a soma de 2
     natureza").
  4) Detalhe por item: nao e' mais um nivel de casamento por valor, e'
     uma grade de composicao (igual a diferenca por item da conciliacao
     de fornecedor, so' que a unidade aqui e' natureza): pra cada
     natureza (e cada grupo combinado), lista os lancamentos que compoem
     o valor base, pro usuario conferir manualmente quando nao houver
     casamento automatico.

Isolado aqui porque a chave de agrupamento do razao (historico) e a
logica de "quais colunas valem" sao exclusivas do formato de razao da
BBC -- outro cliente/segmento poderia ter um layout de razao diferente.
"""
from collections import defaultdict
from itertools import combinations
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models.leasing_movimentacao import LeasingMovimentacao
from models.leasing_razao_contabil import LeasingRazaoContabil
from models.operacao_financeira import OperacaoFinanceira

TOLERANCIA = 0.01
MAX_ITENS_COMBINACAO = 3       # nivel 2: 1 natureza vs ate N grupos do razao
MAX_NATUREZAS_COMBINACAO = 4   # nivel 3: ate N naturezas vs 1 linha do razao


def _tentar_casar(valor_alvo: float, candidatos: List[Tuple[str, float]]) -> Optional[List[str]]:
    """
    candidatos: lista de (historico, valor). Tenta achar de 1 a
    MAX_ITENS_COMBINACAO candidatos cuja soma bate com valor_alvo
    (tolerancia de 1 centavo). Retorna a lista de historicos usados, ou
    None se nao achar nenhuma combinacao dentro do limite.
    """
    alvo_centavos = round(valor_alvo * 100)
    if alvo_centavos == 0:
        return []
    for tamanho in range(1, min(MAX_ITENS_COMBINACAO, len(candidatos)) + 1):
        for combo in combinations(candidatos, tamanho):
            soma_centavos = round(sum(v for _, v in combo) * 100)
            if abs(soma_centavos - alvo_centavos) <= 1:
                return [chave for chave, _ in combo]
    return None


def _serializar_item(m: LeasingMovimentacao) -> dict:
    return {
        "id": m.id,
        "relatorio": m.relatorio,
        "arquivo_origem": m.arquivo_origem,
        "lcto": m.lcto,
        "dt_lanc": m.dt_lanc,
        "nr_operacao": m.nr_operacao,
        "cliente": m.cliente,
        "nr_parc": m.nr_parc,
        "dt_mov": m.dt_mov,
        "conta_debito": m.conta_debito,
        "conta_credito": m.conta_credito,
        "valor": float(m.valor),
    }


def conferir(
    db: Session,
    empresa_id: int,
    lote_razao_id: Optional[int] = None,
    lote_movimentacao_ids: Optional[List[int]] = None,
) -> dict:
    query_mov = db.query(LeasingMovimentacao).filter(LeasingMovimentacao.empresa_id == empresa_id)
    if lote_movimentacao_ids:
        query_mov = query_mov.filter(LeasingMovimentacao.lote_importacao_id.in_(lote_movimentacao_ids))
    movimentacoes = query_mov.all()

    query_razao = db.query(LeasingRazaoContabil).filter(LeasingRazaoContabil.empresa_id == empresa_id)
    if lote_razao_id:
        query_razao = query_razao.filter(LeasingRazaoContabil.lote_importacao_id == lote_razao_id)
    razao = query_razao.all()

    if not movimentacoes:
        raise ValueError("Nenhuma movimentacao encontrada para conferir. Importe os relatorios primeiro.")
    if not razao:
        raise ValueError("Nenhum lancamento de razao encontrado para conferir. Importe o razao contabil primeiro.")

    naturezas_cadastro = {
        op.codigo: op
        for op in db.query(OperacaoFinanceira).filter(
            OperacaoFinanceira.empresa_id == empresa_id,
            OperacaoFinanceira.modalidade == "LEASING",
        ).all()
    }

    # Toda a conferencia (macro, natureza, combinado) so' considera
    # movimentacao cuja natureza esta cadastrada como LEASING -- o
    # restante (natureza de outra modalidade, ou nunca cadastrada) e'
    # ignorado dos calculos, nao so' escondido na tela.
    total_linhas_antes = len(movimentacoes)
    movimentacoes = [m for m in movimentacoes if m.natureza_codigo in naturezas_cadastro]
    movimentacoes_ignoradas = total_linhas_antes - len(movimentacoes)

    # ---- Passo 1: nivel macro ----
    total_base_d = 0.0
    total_base_c = 0.0
    for m in movimentacoes:
        cadastro = naturezas_cadastro[m.natureza_codigo]
        if cadastro.tipo_lancamento == "D":
            total_base_d += float(m.valor)
        elif cadastro.tipo_lancamento == "C":
            total_base_c += float(m.valor)

    total_razao_d = sum(float(r.valor_debito or 0) for r in razao)
    total_razao_c = sum(float(r.valor_credito or 0) for r in razao)

    resumo_macro = {
        "total_base_debito": round(total_base_d, 2),
        "total_base_credito": round(total_base_c, 2),
        "total_razao_debito": round(total_razao_d, 2),
        "total_razao_credito": round(total_razao_c, 2),
        "bate_debito": abs(total_base_d - total_razao_d) <= TOLERANCIA,
        "bate_credito": abs(total_base_c - total_razao_c) <= TOLERANCIA,
    }

    # ---- Passo 2: por natureza ----
    # So' ha' movimentacao de natureza LEASING cadastrada aqui (filtrado
    # acima), entao todo codigo em base_por_natureza sempre resolve pra
    # um cadastro valido com tipo_lancamento definido.
    base_por_natureza: Dict[str, float] = defaultdict(float)
    for m in movimentacoes:
        base_por_natureza[m.natureza_codigo] += float(m.valor)

    pool_razao: Dict[Tuple[str, str], float] = defaultdict(float)
    for r in razao:
        historico = r.historico or "(SEM HISTORICO)"
        if r.valor_debito:
            pool_razao[(historico, "D")] += float(r.valor_debito)
        if r.valor_credito:
            pool_razao[(historico, "C")] += float(r.valor_credito)

    naturezas_resultado = []
    pendentes: List[Tuple[str, str, float]] = []  # (codigo, tipo_lancamento, valor_base) ainda sem match
    for codigo, valor_base in sorted(base_por_natureza.items(), key=lambda kv: -abs(kv[1])):
        cadastro = naturezas_cadastro[codigo]
        tipo_lancamento = cadastro.tipo_lancamento
        descricao = cadastro.descricao

        candidatos = [
            (chave[0], valor) for chave, valor in pool_razao.items() if chave[1] == tipo_lancamento
        ]
        match = _tentar_casar(valor_base, candidatos)

        if match is not None:
            valor_razao = 0.0
            historicos_usados: List[str] = []
            for historico in match:
                chave = (historico, tipo_lancamento)
                valor_razao += pool_razao.pop(chave, 0.0)
                historicos_usados.append(historico)
            status = "conciliado"
            diferenca = round(valor_base - valor_razao, 2)
        else:
            valor_razao = None
            historicos_usados = []
            status = "divergente"
            diferenca = None
            pendentes.append((codigo, tipo_lancamento, valor_base))

        naturezas_resultado.append({
            "natureza_codigo": codigo,
            "natureza_descricao": descricao,
            "tipo_lancamento": tipo_lancamento,
            "valor_base": round(valor_base, 2),
            "valor_razao": round(valor_razao, 2) if valor_razao is not None else None,
            "diferenca": diferenca,
            "status": status,
            "razao_historicos": historicos_usados,
            "grupo_combinado_id": None,
        })

    # ---- Passo 3: combinacao de 2+ naturezas vs 1 linha do razao ----
    # So' entra aqui quem ficou divergente no passo 2. Agrupa por lado
    # D/C (o razao tambem esta separado por lado), tenta combinacoes de
    # tamanho crescente (2..MAX_NATUREZAS_COMBINACAO), primeira que bater
    # fecha o grupo e consome a linha do razao (nao pode ser reaproveitada
    # por outro grupo).
    por_tipo: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
    for item in pendentes:
        por_tipo[item[1]].append(item)

    grupos_combinados: List[dict] = []
    resolvidos_combinado: Dict[str, str] = {}  # natureza_codigo -> grupo_id
    for tipo_lancamento, itens in por_tipo.items():
        itens = sorted(itens, key=lambda i: i[0])
        if len(itens) < 2:
            continue
        for tamanho in range(2, min(MAX_NATUREZAS_COMBINACAO, len(itens)) + 1):
            for combo in combinations(itens, tamanho):
                codigos_combo = [c[0] for c in combo]
                if any(cod in resolvidos_combinado for cod in codigos_combo):
                    continue
                soma_centavos = round(sum(c[2] for c in combo) * 100)
                chave_achada = None
                for chave, valor in pool_razao.items():
                    if chave[1] != tipo_lancamento:
                        continue
                    if abs(round(valor * 100) - soma_centavos) <= 1:
                        chave_achada = chave
                        break
                if chave_achada is None:
                    continue
                valor_razao_grupo = pool_razao.pop(chave_achada)
                grupo_id = f"G{len(grupos_combinados) + 1}"
                for cod in codigos_combo:
                    resolvidos_combinado[cod] = grupo_id
                grupos_combinados.append({
                    "id": grupo_id,
                    "naturezas": codigos_combo,
                    "tipo_lancamento": tipo_lancamento,
                    "valor_base": round(sum(c[2] for c in combo), 2),
                    "valor_razao": round(valor_razao_grupo, 2),
                    "razao_historico": chave_achada[0],
                })

    for nat in naturezas_resultado:
        grupo_id = resolvidos_combinado.get(nat["natureza_codigo"])
        if grupo_id:
            nat["status"] = "conciliado_combinado"
            nat["grupo_combinado_id"] = grupo_id

    # ---- Passo 4: detalhe -- lancamentos que compoem cada natureza ----
    # Nao e' mais casamento por valor, e' composicao pra grade de
    # detalhe (igual diferenca por item da conciliacao de fornecedor,
    # aqui a unidade e' natureza): mostra do lado esquerdo os
    # lancamentos que somam o valor base, do lado direito o valor/
    # historico do razao que foi (ou nao) encontrado.
    movimentacoes_por_natureza: Dict[str, List[LeasingMovimentacao]] = defaultdict(list)
    for m in movimentacoes:
        movimentacoes_por_natureza[m.natureza_codigo].append(m)

    for nat in naturezas_resultado:
        itens = movimentacoes_por_natureza.get(nat["natureza_codigo"], [])
        nat["itens"] = [_serializar_item(m) for m in itens]

    # Grupos do razao que sobraram (nenhuma natureza, nem combinacao,
    # reivindicou)
    razao_nao_utilizado = [
        {"historico": chave[0], "tipo_lancamento": chave[1], "valor": round(valor, 2)}
        for chave, valor in pool_razao.items()
        if abs(valor) > TOLERANCIA
    ]

    return {
        "resumo_macro": resumo_macro,
        "naturezas": naturezas_resultado,
        "grupos_combinados": grupos_combinados,
        "razao_nao_utilizado": razao_nao_utilizado,
        "movimentacoes_ignoradas_natureza_nao_leasing": movimentacoes_ignoradas,
    }
