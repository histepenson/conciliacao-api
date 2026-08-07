# services/leasing_movimentacao_service.py
"""
Persistencia generica da Conferencia LEASING: grava um DataFrame ja
normalizado (independente de qual relatorio de origem veio) como um novo
LeasingLoteImportacao + N LeasingMovimentacao. Nao tem nenhuma regra de
negocio especifica da BBC aqui -- quem sabe como transformar cada
relatorio bruto em DataFrame e' o parser (services/estrategias/bbc/).
"""
from typing import List, Optional

import pandas as pd
from sqlalchemy.orm import Session

from models.leasing_lote_importacao import LeasingLoteImportacao
from models.leasing_movimentacao import LeasingMovimentacao
from models.operacao_financeira import OperacaoFinanceira

CAMPOS_MOVIMENTACAO = [
    "arquivo_origem", "relatorio", "lcto", "dt_lanc", "nr_operacao",
    "cliente", "nr_parc", "dt_mov", "natureza_codigo", "natureza_descricao",
    "conta_debito", "conta_credito", "valor",
]


def _sanitizar_nan(dados: dict) -> dict:
    """
    df.to_dict("records") pode devolver `float('nan')` (nao `None`) para
    celulas vazias em colunas de texto -- o pandas 3.x usa NaN como
    sentinela de nulo mesmo em colunas inferidas como "str". Isso quebra
    o bind de tipo do SQLAlchemy num INSERT em lote (tenta gravar a
    string NaN numa coluna de outra linha por causa da inferencia de
    tipo por coluna do insertmanyvalues). Mesma coisa pra `pd.NaT` nas
    colunas de data (dt_lanc/dt_mov, agora preenchidas por lancamento
    real). Troca ambos por None antes de montar o objeto ORM.
    """
    saneado = {}
    for k, v in dados.items():
        if v is None:
            saneado[k] = None
            continue
        try:
            eh_nulo = bool(pd.isna(v))
        except (TypeError, ValueError):
            eh_nulo = False
        saneado[k] = None if eh_nulo else v
    return saneado


def registrar_lote(
    db: Session,
    empresa_id: int,
    tipo_relatorio: str,
    nome_arquivo: str,
    usuario_id: Optional[int],
    df: pd.DataFrame,
    modalidade: Optional[str] = None,
) -> dict:
    """
    Grava o lote de importacao + as movimentacoes e retorna um resumo.

    Reimportar o mesmo tipo de relatorio SUBSTITUI a importacao anterior
    (apaga o(s) lote(s) anteriores desse `tipo_relatorio` pra essa
    empresa antes de gravar o novo) -- confirmado com o usuario: clicar
    em "Processar" varias vezes nao pode duplicar valores na conferencia.
    O cascade de LeasingLoteImportacao -> LeasingMovimentacao
    (ondelete=CASCADE) cuida de apagar as movimentacoes junto.

    Naturezas cadastradas em Operacao Financeira com `ativo=False` sao
    barradas aqui -- nao entram na base unificada mesmo vindo no arquivo
    (confirmado com o usuario: "Considera=Nao" bloqueia, nao e' so' um
    filtro de exibicao).

    `modalidade`: reservado pro chamador informar qual modalidade este
    import pertence (ex: "LEASING") -- hoje NAO filtra a consulta de
    cadastro (codigo ja e' unico por empresa, e natureza inativa fica com
    modalidade nula por regra, entao filtrar por modalidade aqui excluiria
    justamente as inativas que precisam ser reconhecidas pra bloquear).
    Mantido no assinatura pra uso futuro caso o cadastro deixe de ter
    codigo unico por empresa.
    """
    total_linhas_arquivo = len(df)

    naturezas_arquivo = sorted({
        str(n) for n in df.get("natureza_codigo", pd.Series(dtype=str)).dropna().unique() if str(n).strip()
    })
    cadastro_por_codigo = {}
    if naturezas_arquivo:
        cadastro_por_codigo = {
            op.codigo: op
            for op in db.query(OperacaoFinanceira).filter(
                OperacaoFinanceira.empresa_id == empresa_id,
                OperacaoFinanceira.codigo.in_(naturezas_arquivo),
            ).all()
        }
    naturezas_nao_cadastradas = [n for n in naturezas_arquivo if n not in cadastro_por_codigo]
    naturezas_inativas = sorted(
        codigo for codigo, op in cadastro_por_codigo.items() if not op.ativo
    )

    if naturezas_inativas and "natureza_codigo" in df.columns:
        df = df[~df["natureza_codigo"].isin(naturezas_inativas)]
    linhas_ignoradas_natureza_inativa = total_linhas_arquivo - len(df)

    db.query(LeasingLoteImportacao).filter(
        LeasingLoteImportacao.empresa_id == empresa_id,
        LeasingLoteImportacao.tipo_relatorio == tipo_relatorio,
    ).delete(synchronize_session=False)

    lote = LeasingLoteImportacao(
        empresa_id=empresa_id,
        tipo_relatorio=tipo_relatorio,
        nome_arquivo=nome_arquivo,
        usuario_id=usuario_id,
        qtd_linhas=len(df),
        status="concluido",
    )
    db.add(lote)
    db.flush()  # obtem lote.id sem commitar ainda

    registros = df.to_dict("records")
    movimentacoes: List[LeasingMovimentacao] = []
    for row in registros:
        dados = _sanitizar_nan({campo: row.get(campo) for campo in CAMPOS_MOVIMENTACAO})
        if not dados.get("arquivo_origem"):
            dados["arquivo_origem"] = nome_arquivo
        dados["valor"] = dados.get("valor") or 0
        movimentacoes.append(
            LeasingMovimentacao(empresa_id=empresa_id, lote_importacao_id=lote.id, **dados)
        )
    db.add_all(movimentacoes)
    db.commit()

    return {
        "lote_id": lote.id,
        "tipo_relatorio": tipo_relatorio,
        "nome_arquivo": nome_arquivo,
        "total_linhas": len(df),
        "linhas_ignoradas_natureza_inativa": linhas_ignoradas_natureza_inativa,
        "naturezas_inativas_ignoradas": naturezas_inativas,
        "valor_total": float(df["valor"].sum()) if "valor" in df.columns else 0.0,
        "naturezas_encontradas": naturezas_arquivo,
        "naturezas_nao_cadastradas": naturezas_nao_cadastradas,
    }
