from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException

from models.estoque import EstoqueSaldo, EstoqueMovimentacao, TipoMovimentacao
from models.nfe import NfeEntradaItem, NfeSaidaItem, NfeEntrada, NfeSaida
from models.produto import Produto
from schemas.estoque_schema import AjusteRequest


def _primeiro_dia_mes(d: date) -> date:
    return d.replace(day=1)


def _saldo_anterior(db: Session, empresa_id: int, produto_id: int, periodo: date) -> Decimal:
    """Retorna saldo_final do mês anterior, ou 0 se não existir."""
    mes = periodo.month
    ano = periodo.year
    if mes == 1:
        periodo_ant = date(ano - 1, 12, 1)
    else:
        periodo_ant = date(ano, mes - 1, 1)

    saldo = db.query(EstoqueSaldo).filter(
        EstoqueSaldo.empresa_id == empresa_id,
        EstoqueSaldo.produto_id == produto_id,
        EstoqueSaldo.periodo == periodo_ant,
    ).first()
    return saldo.saldo_final if saldo else Decimal("0")


def _calcular_entradas(db: Session, empresa_id: int, produto_id: int, periodo: date) -> Decimal:
    """Soma quantidade_convertida das NF-e entrada autorizadas, com vínculo, no período."""
    inicio = periodo
    if periodo.month == 12:
        fim = date(periodo.year + 1, 1, 1)
    else:
        fim = date(periodo.year, periodo.month + 1, 1)

    result = db.query(func.coalesce(func.sum(NfeEntradaItem.quantidade_convertida), 0)).join(
        NfeEntrada, NfeEntradaItem.nfe_entrada_id == NfeEntrada.id
    ).filter(
        NfeEntrada.empresa_id == empresa_id,
        NfeEntradaItem.produto_id == produto_id,
        NfeEntradaItem.vinculo_pendente == False,
        NfeEntrada.status == "autorizada",
        NfeEntrada.data_emissao >= inicio,
        NfeEntrada.data_emissao < fim,
    ).scalar()
    return Decimal(str(result))


def _calcular_saidas(db: Session, empresa_id: int, produto_id: int, periodo: date) -> Decimal:
    """Soma quantidade_convertida das NF-e saída autorizadas, com vínculo, no período."""
    inicio = periodo
    if periodo.month == 12:
        fim = date(periodo.year + 1, 1, 1)
    else:
        fim = date(periodo.year, periodo.month + 1, 1)

    result = db.query(func.coalesce(func.sum(NfeSaidaItem.quantidade_convertida), 0)).join(
        NfeSaida, NfeSaidaItem.nfe_saida_id == NfeSaida.id
    ).filter(
        NfeSaida.empresa_id == empresa_id,
        NfeSaidaItem.produto_id == produto_id,
        NfeSaidaItem.vinculo_pendente == False,
        NfeSaida.status == "autorizada",
        NfeSaida.data_emissao >= inicio,
        NfeSaida.data_emissao < fim,
    ).scalar()
    return Decimal(str(result))


def _calcular_ajustes(db: Session, empresa_id: int, produto_id: int, periodo: date) -> Decimal:
    """Soma movimentações de ajuste/estorno no período."""
    inicio = periodo
    if periodo.month == 12:
        fim = date(periodo.year + 1, 1, 1)
    else:
        fim = date(periodo.year, periodo.month + 1, 1)

    result = db.query(func.coalesce(func.sum(EstoqueMovimentacao.quantidade), 0)).filter(
        EstoqueMovimentacao.empresa_id == empresa_id,
        EstoqueMovimentacao.produto_id == produto_id,
        EstoqueMovimentacao.tipo.in_([TipoMovimentacao.ajuste, TipoMovimentacao.estorno]),
        EstoqueMovimentacao.data_movimentacao >= inicio,
        EstoqueMovimentacao.data_movimentacao < fim,
    ).scalar()
    return Decimal(str(result))


def apurar_saldo(db: Session, empresa_id: int, produto_id: int, periodo: date) -> EstoqueSaldo:
    """Calcula e persiste (upsert) o saldo do produto no período."""
    periodo = _primeiro_dia_mes(periodo)

    saldo_inicial = _saldo_anterior(db, empresa_id, produto_id, periodo)
    entradas = _calcular_entradas(db, empresa_id, produto_id, periodo)
    saidas = _calcular_saidas(db, empresa_id, produto_id, periodo)
    ajustes = _calcular_ajustes(db, empresa_id, produto_id, periodo)
    saldo_final = saldo_inicial + entradas - saidas + ajustes

    saldo = db.query(EstoqueSaldo).filter(
        EstoqueSaldo.empresa_id == empresa_id,
        EstoqueSaldo.produto_id == produto_id,
        EstoqueSaldo.periodo == periodo,
    ).first()

    if saldo:
        if saldo.fechado:
            return saldo
        saldo.saldo_inicial = saldo_inicial
        saldo.entradas = entradas
        saldo.saidas = saidas
        saldo.ajustes = ajustes
        saldo.saldo_final = saldo_final
    else:
        saldo = EstoqueSaldo(
            empresa_id=empresa_id,
            produto_id=produto_id,
            periodo=periodo,
            saldo_inicial=saldo_inicial,
            entradas=entradas,
            saidas=saidas,
            ajustes=ajustes,
            saldo_final=saldo_final,
            fechado=False,
        )
        db.add(saldo)

    db.commit()
    db.refresh(saldo)
    return saldo


def registrar_ajuste(db: Session, req: AjusteRequest) -> EstoqueMovimentacao:
    data_mov = req.data_movimentacao or date.today()

    mov = EstoqueMovimentacao(
        empresa_id=req.empresa_id,
        produto_id=req.produto_id,
        data_movimentacao=data_mov,
        tipo=TipoMovimentacao.ajuste,
        quantidade=req.quantidade,
        justificativa=req.justificativa,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)

    # Reapura saldo do período afetado
    apurar_saldo(db, req.empresa_id, req.produto_id, _primeiro_dia_mes(data_mov))
    return mov


def reprocessar_periodo(db: Session, empresa_id: int, periodo: date) -> int:
    """Reapura todos os produtos da empresa no período. Retorna qtd processada."""
    periodo = _primeiro_dia_mes(periodo)

    produtos = db.query(Produto.id).filter(
        Produto.empresa_id == empresa_id,
        Produto.ativo == True,
    ).all()

    count = 0
    for (produto_id,) in produtos:
        apurar_saldo(db, empresa_id, produto_id, periodo)
        count += 1
    return count


def listar_saldos(db: Session, empresa_id: int, periodo: date) -> list[EstoqueSaldo]:
    periodo = _primeiro_dia_mes(periodo)
    saldos = db.query(EstoqueSaldo).filter(
        EstoqueSaldo.empresa_id == empresa_id,
        EstoqueSaldo.periodo == periodo,
    ).all()

    for s in saldos:
        produto = db.query(Produto).filter(Produto.id == s.produto_id).first()
        if produto:
            s.produto_codigo = produto.codigo_interno
            s.produto_descricao = produto.descricao
            s.produto_unidade = produto.unidade_estoque
        s.alerta_negativo = s.saldo_final < 0

    return saldos


def listar_movimentacoes(
    db: Session,
    empresa_id: int,
    produto_id: int | None = None,
    periodo: date | None = None,
) -> list[EstoqueMovimentacao]:
    q = db.query(EstoqueMovimentacao).filter(
        EstoqueMovimentacao.empresa_id == empresa_id
    )
    if produto_id:
        q = q.filter(EstoqueMovimentacao.produto_id == produto_id)
    if periodo:
        inicio = _primeiro_dia_mes(periodo)
        if inicio.month == 12:
            fim = date(inicio.year + 1, 1, 1)
        else:
            fim = date(inicio.year, inicio.month + 1, 1)
        q = q.filter(
            EstoqueMovimentacao.data_movimentacao >= inicio,
            EstoqueMovimentacao.data_movimentacao < fim,
        )

    movs = q.order_by(EstoqueMovimentacao.data_movimentacao.desc()).all()

    for m in movs:
        produto = db.query(Produto).filter(Produto.id == m.produto_id).first()
        if produto:
            m.produto_codigo = produto.codigo_interno
            m.produto_descricao = produto.descricao

    return movs
