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
        .all()
    )
    return {linha.lp_codigo: linha.tipo_chave for linha in linhas}
