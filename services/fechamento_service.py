from datetime import date
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models.estoque import EstoqueSaldo, EstoqueMovimentacao
from models.estoque_alerta import EstoqueAlerta, TipoAlerta
from models.produto import Produto
from services.estoque_service import apurar_saldo, reprocessar_periodo, _primeiro_dia_mes
from schemas.estoque_schema import FechamentoOut


def fechar_periodo(db: Session, empresa_id: int, periodo: date) -> FechamentoOut:
    """Fecha o período para a empresa. Idempotente."""
    periodo = _primeiro_dia_mes(periodo)

    # Garante que todos os saldos do período estão apurados
    reprocessar_periodo(db, empresa_id, periodo)

    saldos = db.query(EstoqueSaldo).filter(
        EstoqueSaldo.empresa_id == empresa_id,
        EstoqueSaldo.periodo == periodo,
        EstoqueSaldo.fechado == False,
    ).all()

    for s in saldos:
        s.fechado = True
        # Alerta se saldo negativo
        if s.saldo_final < 0:
            alerta_existe = db.query(EstoqueAlerta).filter(
                EstoqueAlerta.empresa_id == empresa_id,
                EstoqueAlerta.tipo == TipoAlerta.estoque_negativo,
                EstoqueAlerta.referencia_id == s.produto_id,
                EstoqueAlerta.resolvido == False,
            ).first()
            if not alerta_existe:
                db.add(EstoqueAlerta(
                    empresa_id=empresa_id,
                    tipo=TipoAlerta.estoque_negativo,
                    referencia_id=s.produto_id,
                    mensagem=f"Saldo negativo no fechamento {periodo.strftime('%m/%Y')}: {s.saldo_final}",
                ))

    db.commit()
    return FechamentoOut(
        periodo=periodo,
        produtos_fechados=len(saldos),
        message=f"Período {periodo.strftime('%m/%Y')} fechado com {len(saldos)} produto(s).",
    )


def reabrir_periodo(db: Session, empresa_id: int, periodo: date) -> FechamentoOut:
    """Reabre um período fechado."""
    periodo = _primeiro_dia_mes(periodo)

    saldos = db.query(EstoqueSaldo).filter(
        EstoqueSaldo.empresa_id == empresa_id,
        EstoqueSaldo.periodo == periodo,
        EstoqueSaldo.fechado == True,
    ).all()

    if not saldos:
        raise HTTPException(404, "Nenhum saldo fechado encontrado para este período")

    for s in saldos:
        s.fechado = False

    # Cria alerta de reabertura
    db.add(EstoqueAlerta(
        empresa_id=empresa_id,
        tipo=TipoAlerta.periodo_reaberto,
        referencia_id=None,
        mensagem=f"Período {periodo.strftime('%m/%Y')} reaberto manualmente.",
    ))

    db.commit()
    return FechamentoOut(
        periodo=periodo,
        produtos_fechados=len(saldos),
        message=f"Período {periodo.strftime('%m/%Y')} reaberto com {len(saldos)} produto(s).",
    )


def verificar_e_reabrir_se_necessario(db: Session, empresa_id: int, periodo: date) -> bool:
    """
    Reabre o período se estiver fechado (chamado ao registrar NF em período fechado).
    Retorna True se reabriu.
    """
    periodo = _primeiro_dia_mes(periodo)
    saldo = db.query(EstoqueSaldo).filter(
        EstoqueSaldo.empresa_id == empresa_id,
        EstoqueSaldo.periodo == periodo,
        EstoqueSaldo.fechado == True,
    ).first()

    if not saldo:
        return False

    db.query(EstoqueSaldo).filter(
        EstoqueSaldo.empresa_id == empresa_id,
        EstoqueSaldo.periodo == periodo,
    ).update({"fechado": False})

    db.add(EstoqueAlerta(
        empresa_id=empresa_id,
        tipo=TipoAlerta.periodo_reaberto,
        referencia_id=None,
        mensagem=f"Período {periodo.strftime('%m/%Y')} reaberto automaticamente por nova NF-e importada.",
    ))
    db.commit()
    return True


def listar_status_fechamentos(db: Session, empresa_id: int, ano: int) -> list[dict]:
    """Retorna status de fechamento para cada mês do ano."""
    result = []
    for mes in range(1, 13):
        periodo = date(ano, mes, 1)
        saldos = db.query(EstoqueSaldo).filter(
            EstoqueSaldo.empresa_id == empresa_id,
            EstoqueSaldo.periodo == periodo,
        ).all()

        fechados = sum(1 for s in saldos if s.fechado)
        total = len(saldos)
        result.append({
            "periodo": periodo,
            "total_produtos": total,
            "fechados": fechados,
            "abertos": total - fechados,
            "status": "fechado" if total > 0 and fechados == total else ("parcial" if fechados > 0 else "aberto"),
        })
    return result


def job_fechar_mes_anterior(db_factory) -> None:
    """APScheduler job: fecha o mês anterior no dia 1 de cada mês."""
    db: Session = db_factory()
    try:
        hoje = date.today()
        if hoje.month == 1:
            periodo = date(hoje.year - 1, 12, 1)
        else:
            periodo = date(hoje.year, hoje.month - 1, 1)

        from models.empresa import Empresa
        empresas = db.query(Empresa.id).filter(Empresa.status == True).all()
        for (empresa_id,) in empresas:
            try:
                fechar_periodo(db, empresa_id, periodo)
            except Exception:
                pass
    finally:
        db.close()
