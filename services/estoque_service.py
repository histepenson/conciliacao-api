from datetime import date, timedelta
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


def gerar_kardex(db: Session, empresa_id: int, produto_id: int, data_inicio: date, data_fim: date) -> dict:
    """
    Monta o kardex (ficha de estoque) do produto: entradas e saídas em ordem
    cronológica (entradas antes de saídas no mesmo dia), com saldo corrente
    de quantidade e valor, calculando o custo médio móvel.

    `data_inicio`/`data_fim` definem o intervalo exibido (inclusive); o saldo
    anterior é calculado a partir de todo o histórico anterior a `data_inicio`.
    """
    fim_exclusivo = data_fim + timedelta(days=1)

    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(404, "Produto nao encontrado")

    entradas = db.query(NfeEntradaItem, NfeEntrada).join(
        NfeEntrada, NfeEntradaItem.nfe_entrada_id == NfeEntrada.id
    ).filter(
        NfeEntrada.empresa_id == empresa_id,
        NfeEntradaItem.produto_id == produto_id,
        NfeEntradaItem.vinculo_pendente == False,  # noqa
        NfeEntrada.status == "autorizada",
        NfeEntrada.data_emissao < fim_exclusivo,
    ).all()

    saidas = db.query(NfeSaidaItem, NfeSaida).join(
        NfeSaida, NfeSaidaItem.nfe_saida_id == NfeSaida.id
    ).filter(
        NfeSaida.empresa_id == empresa_id,
        NfeSaidaItem.produto_id == produto_id,
        NfeSaidaItem.vinculo_pendente == False,  # noqa
        NfeSaida.status == "autorizada",
        NfeSaida.data_emissao < fim_exclusivo,
    ).all()

    ajustes = db.query(EstoqueMovimentacao).filter(
        EstoqueMovimentacao.empresa_id == empresa_id,
        EstoqueMovimentacao.produto_id == produto_id,
        EstoqueMovimentacao.tipo.in_([TipoMovimentacao.ajuste, TipoMovimentacao.estorno]),
        EstoqueMovimentacao.data_movimentacao < fim_exclusivo,
    ).all()

    eventos = []
    for item, nfe in entradas:
        data_evento = nfe.data_emissao or nfe.data_autorizacao
        if not data_evento:
            continue
        eventos.append({
            "data": data_evento,
            "ordem": 0,  # entradas primeiro
            "tipo": "entrada",
            "documento": nfe.numero_nf,
            "descricao": item.descricao_produto,
            "quantidade": Decimal(str(item.quantidade_convertida or 0)),
            "valor_total": Decimal(str(item.valor_total_item)) if item.valor_total_item is not None else None,
        })
    for item, nfe in saidas:
        data_evento = nfe.data_emissao or nfe.data_autorizacao
        if not data_evento:
            continue
        eventos.append({
            "data": data_evento,
            "ordem": 1,  # saídas depois das entradas
            "tipo": "saida",
            "documento": nfe.numero_nf,
            "descricao": item.descricao_produto,
            "quantidade": Decimal(str(item.quantidade_convertida or 0)),
            "valor_total": None,
        })
    for mov in ajustes:
        qtd = Decimal(str(mov.quantidade))
        eventos.append({
            "data": mov.data_movimentacao,
            "ordem": 0 if qtd >= 0 else 1,
            "tipo": mov.tipo.value,
            "documento": mov.documento_origem,
            "descricao": mov.justificativa,
            "quantidade_assinada": qtd,
            "valor_total": None,
        })

    eventos.sort(key=lambda e: (e["data"], e["ordem"]))

    saldo_qtd = Decimal("0")
    saldo_valor = Decimal("0")
    custo_medio = Decimal("0")
    saldo_inicial_qtd = Decimal("0")
    saldo_inicial_valor = Decimal("0")
    saldo_inicial_custo_medio = Decimal("0")
    saldo_inicial_definido = False
    linhas = []

    for ev in eventos:
        if not saldo_inicial_definido and ev["data"] >= data_inicio:
            saldo_inicial_qtd = saldo_qtd
            saldo_inicial_valor = saldo_valor
            saldo_inicial_custo_medio = custo_medio
            saldo_inicial_definido = True

        qtd_assinada = ev.get("quantidade_assinada")
        if qtd_assinada is None:
            qtd_assinada = ev["quantidade"] if ev["ordem"] == 0 else -ev["quantidade"]

        if ev["ordem"] == 0:
            # Entrada (NF ou ajuste positivo)
            valor_evento = ev["valor_total"]
            if valor_evento is None:
                valor_evento = qtd_assinada * custo_medio
        else:
            # Saída (NF, ajuste negativo ou estorno) — valorizada ao custo médio atual
            valor_evento = qtd_assinada * custo_medio

        saldo_qtd += qtd_assinada
        saldo_valor += valor_evento

        if saldo_qtd == 0:
            saldo_valor = Decimal("0")
            custo_medio = Decimal("0")
        else:
            custo_medio = saldo_valor / saldo_qtd

        if ev["data"] >= data_inicio:
            linhas.append({
                "data": ev["data"],
                "tipo": ev["tipo"],
                "documento": ev["documento"],
                "descricao": ev["descricao"],
                "quantidade": qtd_assinada,
                "valor_total": valor_evento,
                "valor_unitario": (valor_evento / qtd_assinada) if qtd_assinada else Decimal("0"),
                "saldo_quantidade": saldo_qtd,
                "custo_medio": custo_medio,
                "saldo_valor": saldo_valor,
            })

    if not saldo_inicial_definido:
        saldo_inicial_qtd = saldo_qtd
        saldo_inicial_valor = saldo_valor
        saldo_inicial_custo_medio = custo_medio

    return {
        "produto_id": produto_id,
        "produto_codigo": produto.codigo_interno,
        "produto_descricao": produto.descricao,
        "produto_unidade": produto.unidade_estoque,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "saldo_inicial_quantidade": saldo_inicial_qtd,
        "saldo_inicial_valor": saldo_inicial_valor,
        "saldo_inicial_custo_medio": saldo_inicial_custo_medio,
        "saldo_final_quantidade": saldo_qtd,
        "saldo_final_valor": saldo_valor,
        "saldo_final_custo_medio": custo_medio,
        "linhas": linhas,
    }
