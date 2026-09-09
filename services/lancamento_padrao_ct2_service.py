"""
Servico de resolucao da familia de formula de CT2_KEY por Lancamento Padrao,
usado no matching exato da Conciliacao de Estoque (Kardex x Razao).

Ver models/lancamento_padrao.py::LancamentoPadraoCt2Layout e
tools/estoque/calc_diferencas_estoque.py::_matching_por_ct2_key.
"""

from sqlalchemy.orm import Session

from models.lancamento_padrao import LancamentoPadraoCt2Layout


def obter_mapa_tipo_chave(db: Session, empresa_id: int) -> dict[str, str]:
    """Retorna {lp_codigo: tipo_chave} pra empresa, usado no matching por
    ct2_key da conciliacao de estoque. LPs sem cadastro simplesmente nao
    aparecem no dict -- o chamador trata como "nao configurado" e cai no
    fallback de matching por (data, cf)."""
    linhas = (
        db.query(LancamentoPadraoCt2Layout)
        .filter(LancamentoPadraoCt2Layout.empresa_id == empresa_id)
        .filter(LancamentoPadraoCt2Layout.tipo_chave.isnot(None))
        .all()
    )
    return {linha.lp_codigo: linha.tipo_chave for linha in linhas}


def obter_mapa_movimento_ct2_vazio(db: Session, empresa_id: int) -> dict[str, str]:
    """Retorna {lp_codigo: codigo_movimento} pra empresa -- usado quando o
    lancamento do Razao vem com CT2_KEY vazio (LP nao gera chave nativa,
    entao nao ha' como decodificar produto/armazem/data). Nesses casos o
    codigo_movimento do Kardex correspondente e' conhecido de antemao por
    configuracao (ex.: LP 666 -> "RE1"), e o matching individual passa a
    ser por valor+data em vez de chave (ver calc_diferencas_estoque.py)."""
    linhas = (
        db.query(LancamentoPadraoCt2Layout)
        .filter(LancamentoPadraoCt2Layout.empresa_id == empresa_id)
        .filter(LancamentoPadraoCt2Layout.codigo_movimento_ct2_vazio.isnot(None))
        .all()
    )
    return {linha.lp_codigo: linha.codigo_movimento_ct2_vazio for linha in linhas}


def obter_mapa_layout_campos(db: Session, empresa_id: int) -> dict[str, list]:
    """Retorna {lp_codigo: layout_campos} pra empresa -- layout generico de
    posicoes do CT2_KEY cadastrado por LP (campo/inicio/tamanho), usado no
    matching generico da conciliacao de estoque quando o CT2_KEY vem
    preenchido (ver tools/estoque/calc_diferencas_estoque.py::
    _decodificar_ct2_key_por_layout). LPs sem layout cadastrado nao
    aparecem no dict."""
    linhas = (
        db.query(LancamentoPadraoCt2Layout)
        .filter(LancamentoPadraoCt2Layout.empresa_id == empresa_id)
        .filter(LancamentoPadraoCt2Layout.layout_campos.isnot(None))
        .all()
    )
    return {linha.lp_codigo: linha.layout_campos for linha in linhas}
