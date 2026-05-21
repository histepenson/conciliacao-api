import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from rq import Queue
from rq.command import send_stop_job_command
from rq.job import Job
from rq.registry import DeferredJobRegistry, FailedJobRegistry, ScheduledJobRegistry, StartedJobRegistry
from sqlalchemy.orm import Session

from core.rq import PROTHEUS_CARGA_QUEUE, enqueue_protheus_carga
from core.redis import get_redis_connection
from models.protheus_carga import ProtheusCarga, ProtheusCargaConfig, ProtheusCargaRegistro
from schemas.protheus_carga_schema import ProtheusCargaConfigCreate, ProtheusCargaConfigUpdate, ProtheusCargaCreate

RELATORIOS_SUPORTADOS = {
    "FINR130",
    "FINR150",
    "CTBR140",
    "CTBR400",
    "CTBR480",
    "FINR470",
    "MATR900",
}

STATUS_REUTILIZAVEIS = {"concluido"}


def normalizar_tipo_relatorio(tipo_relatorio: str) -> str:
    tipo = (tipo_relatorio or "").strip().upper()
    if tipo not in RELATORIOS_SUPORTADOS:
        raise HTTPException(status_code=422, detail=f"Relatorio {tipo_relatorio} nao suportado para carga Protheus")
    return tipo


def calcular_parametros_hash(parametros: dict[str, Any]) -> str:
    payload = json.dumps(parametros or {}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validar_data_base(data_base: str) -> str:
    value = (data_base or "").strip()
    if len(value) != 8 or not value.isdigit():
        raise HTTPException(status_code=422, detail="data_base deve estar no formato YYYYMMDD")
    return value


def listar_configs(db: Session, empresa_id: int) -> list[ProtheusCargaConfig]:
    return (
        db.query(ProtheusCargaConfig)
        .filter(ProtheusCargaConfig.empresa_id == empresa_id)
        .order_by(ProtheusCargaConfig.tipo_relatorio, ProtheusCargaConfig.nome)
        .all()
    )


def parar_agendamentos(db: Session, empresa_id: int) -> int:
    configs = db.query(ProtheusCargaConfig).filter(ProtheusCargaConfig.empresa_id == empresa_id).all()
    for config in configs:
        config.ativo = False
        config.atualizar_automatico = False
    db.commit()
    return len(configs)


def excluir_todas_configs(db: Session, empresa_id: int) -> int:
    configs = db.query(ProtheusCargaConfig).filter(ProtheusCargaConfig.empresa_id == empresa_id).all()
    total = len(configs)
    for config in configs:
        db.delete(config)
    db.commit()
    return total


def criar_config(db: Session, empresa_id: int, payload: ProtheusCargaConfigCreate) -> ProtheusCargaConfig:
    config = ProtheusCargaConfig(
        empresa_id=empresa_id,
        tipo_relatorio=normalizar_tipo_relatorio(payload.tipo_relatorio),
        nome=payload.nome.strip(),
        parametros_json=payload.parametros_json or {},
        ativo=payload.ativo,
        atualizar_automatico=payload.atualizar_automatico,
        data_base_origem=payload.data_base_origem,
        data_base_fixa=payload.data_base_fixa,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def atualizar_config(
    db: Session,
    empresa_id: int,
    config_id: int,
    payload: ProtheusCargaConfigUpdate,
) -> ProtheusCargaConfig:
    config = obter_config(db, empresa_id, config_id)
    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(config, campo, valor)
    db.commit()
    db.refresh(config)
    return config


def excluir_config(db: Session, empresa_id: int, config_id: int) -> None:
    config = obter_config(db, empresa_id, config_id)
    db.delete(config)
    db.commit()


def obter_config(db: Session, empresa_id: int, config_id: int) -> ProtheusCargaConfig:
    config = (
        db.query(ProtheusCargaConfig)
        .filter(ProtheusCargaConfig.id == config_id, ProtheusCargaConfig.empresa_id == empresa_id)
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Configuracao de carga nao encontrada")
    return config


def listar_cargas(
    db: Session,
    empresa_id: int,
    tipo_relatorio: Optional[str] = None,
    data_base: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[ProtheusCarga]:
    query = db.query(ProtheusCarga).filter(ProtheusCarga.empresa_id == empresa_id)
    if tipo_relatorio:
        query = query.filter(ProtheusCarga.tipo_relatorio == normalizar_tipo_relatorio(tipo_relatorio))
    if data_base:
        query = query.filter(ProtheusCarga.data_base == validar_data_base(data_base))
    if status:
        query = query.filter(ProtheusCarga.status == status)
    return query.order_by(ProtheusCarga.created_at.desc()).limit(limit).all()


def excluir_todas_cargas(db: Session, empresa_id: int) -> int:
    cargas = db.query(ProtheusCarga).filter(ProtheusCarga.empresa_id == empresa_id).all()
    total = len(cargas)
    for carga in cargas:
        db.delete(carga)
    db.commit()
    return total


def abortar_fila(db: Session, empresa_id: int) -> dict[str, Any]:
    conn = get_redis_connection()
    queue = Queue(PROTHEUS_CARGA_QUEUE, connection=conn)

    queued_job_ids = list(queue.job_ids)
    queue.empty()

    stopped: list[str] = []
    stop_errors: list[dict[str, str]] = []
    started = StartedJobRegistry(PROTHEUS_CARGA_QUEUE, connection=conn)
    for job_id in started.get_job_ids():
        try:
            send_stop_job_command(conn, job_id)
            stopped.append(job_id)
        except Exception as exc:
            stop_errors.append({"job_id": job_id, "erro": str(exc)})

    cancelled: list[str] = []
    for registry_cls in (ScheduledJobRegistry, DeferredJobRegistry, FailedJobRegistry):
        registry = registry_cls(PROTHEUS_CARGA_QUEUE, connection=conn)
        for job_id in registry.get_job_ids():
            try:
                job = Job.fetch(job_id, connection=conn)
                job.cancel()
                job.delete()
                cancelled.append(job_id)
            except Exception:
                pass

    cargas = (
        db.query(ProtheusCarga)
        .filter(
            ProtheusCarga.empresa_id == empresa_id,
            ProtheusCarga.status.in_(["pendente", "processando"]),
        )
        .all()
    )
    for carga in cargas:
        carga.status = "cancelado"
        carga.erro = "Fila abortada pelo usuario."
        carga.finalizado_em = datetime.now(timezone.utc)
    db.commit()

    return {
        "fila": PROTHEUS_CARGA_QUEUE,
        "jobs_pendentes_removidos": len(queued_job_ids),
        "jobs_em_execucao_sinalizados": len(stopped),
        "jobs_cancelados_registries": len(cancelled),
        "cargas_canceladas": len(cargas),
        "pendentes": queued_job_ids,
        "stop_enviado": stopped,
        "cancelados": cancelled,
        "erros_stop": stop_errors,
    }


def obter_carga(db: Session, empresa_id: int, carga_id: int) -> ProtheusCarga:
    carga = (
        db.query(ProtheusCarga)
        .filter(ProtheusCarga.id == carga_id, ProtheusCarga.empresa_id == empresa_id)
        .first()
    )
    if not carga:
        raise HTTPException(status_code=404, detail="Carga Protheus nao encontrada")
    return carga


def obter_carga_existente(
    db: Session,
    empresa_id: int,
    tipo_relatorio: str,
    data_base: str,
    parametros_json: dict[str, Any],
) -> Optional[ProtheusCarga]:
    parametros_hash = calcular_parametros_hash(parametros_json)
    return (
        db.query(ProtheusCarga)
        .filter(
            ProtheusCarga.empresa_id == empresa_id,
            ProtheusCarga.tipo_relatorio == normalizar_tipo_relatorio(tipo_relatorio),
            ProtheusCarga.data_base == validar_data_base(data_base),
            ProtheusCarga.parametros_hash == parametros_hash,
        )
        .order_by(ProtheusCarga.created_at.desc())
        .first()
    )


def obter_registros_carga_concluida(
    db: Session,
    empresa_id: int,
    tipo_relatorio: str,
    data_base: str,
    parametros_json: dict[str, Any],
) -> tuple[Optional[ProtheusCarga], list[dict[str, Any]]]:
    tipo = normalizar_tipo_relatorio(tipo_relatorio)
    data_base = validar_data_base(data_base)
    parametros = dict(parametros_json or {})
    parametros["data_base"] = parametros.get("data_base") or data_base
    parametros_hash = calcular_parametros_hash(parametros)

    carga = (
        db.query(ProtheusCarga)
        .filter(
            ProtheusCarga.empresa_id == empresa_id,
            ProtheusCarga.tipo_relatorio == tipo,
            ProtheusCarga.data_base == data_base,
            ProtheusCarga.parametros_hash == parametros_hash,
            ProtheusCarga.status == "concluido",
        )
        .order_by(ProtheusCarga.finalizado_em.desc().nullslast(), ProtheusCarga.created_at.desc())
        .first()
    )

    if not carga:
        carga = (
            db.query(ProtheusCarga)
            .filter(
                ProtheusCarga.empresa_id == empresa_id,
                ProtheusCarga.tipo_relatorio == tipo,
                ProtheusCarga.data_base == data_base,
                ProtheusCarga.status == "concluido",
            )
            .order_by(ProtheusCarga.finalizado_em.desc().nullslast(), ProtheusCarga.created_at.desc())
            .first()
        )

    if not carga:
        return None, []

    registros = (
        db.query(ProtheusCargaRegistro)
        .filter(ProtheusCargaRegistro.carga_id == carga.id)
        .order_by(ProtheusCargaRegistro.sequencia)
        .all()
    )
    return carga, [registro.dados_json for registro in registros]


def criar_ou_enfileirar_carga(db: Session, empresa_id: int, payload: ProtheusCargaCreate) -> tuple[ProtheusCarga, bool]:
    tipo = normalizar_tipo_relatorio(payload.tipo_relatorio)
    data_base = validar_data_base(payload.data_base)
    parametros = dict(payload.parametros_json or {})
    parametros["data_base"] = parametros.get("data_base") or data_base
    parametros_hash = calcular_parametros_hash(parametros)

    existente = (
        db.query(ProtheusCarga)
        .filter(
            ProtheusCarga.empresa_id == empresa_id,
            ProtheusCarga.tipo_relatorio == tipo,
            ProtheusCarga.data_base == data_base,
            ProtheusCarga.parametros_hash == parametros_hash,
        )
        .first()
    )
    if existente and existente.status in STATUS_REUTILIZAVEIS:
        return existente, True

    if existente and existente.status == "processando":
        return existente, False

    if existente and existente.status in {"pendente", "erro"}:
        existente.status = "pendente"
        existente.erro = None
        existente.iniciado_em = None
        existente.finalizado_em = None
        _tentar_enfileirar(db, existente)
        return existente, False

    carga = ProtheusCarga(
        config_id=payload.config_id,
        empresa_id=empresa_id,
        tipo_relatorio=tipo,
        data_base=data_base,
        parametros_hash=parametros_hash,
        parametros_json=parametros,
        status="pendente",
    )
    db.add(carga)
    db.commit()
    db.refresh(carga)

    _tentar_enfileirar(db, carga)
    return carga, False


def enfileirar_config(db: Session, empresa_id: int, config_id: int, data_base: Optional[str] = None) -> tuple[ProtheusCarga, bool]:
    config = obter_config(db, empresa_id, config_id)
    if not config.ativo:
        raise HTTPException(status_code=422, detail="Configuracao de carga inativa")

    data_base_resolvida = resolver_data_base_config(config, data_base)
    return criar_ou_enfileirar_carga(
        db,
        empresa_id,
        ProtheusCargaCreate(
            empresa_id=empresa_id,
            config_id=config.id,
            tipo_relatorio=config.tipo_relatorio,
            data_base=data_base_resolvida,
            parametros_json=config.parametros_json or {},
        ),
    )


def resolver_data_base_config(config: ProtheusCargaConfig, data_base: Optional[str] = None) -> str:
    if data_base:
        return validar_data_base(data_base)
    if config.data_base_origem == "fixa" and config.data_base_fixa:
        return validar_data_base(config.data_base_fixa)
    raise HTTPException(
        status_code=422,
        detail=(
            "Data base nao resolvida. Informe data_base na execucao ou configure data_base_fixa. "
            "A origem 'periodo_aberto' precisa ser conectada a uma configuracao de periodo do sistema."
        ),
    )


def reprocessar_carga(db: Session, empresa_id: int, carga_id: int) -> ProtheusCarga:
    carga = obter_carga(db, empresa_id, carga_id)
    carga.status = "pendente"
    carga.erro = None
    carga.iniciado_em = None
    carga.finalizado_em = None
    carga.total_registros = 0
    db.query(ProtheusCargaRegistro).filter(ProtheusCargaRegistro.carga_id == carga.id).delete()
    db.commit()

    _tentar_enfileirar(db, carga)
    return carga


def cancelar_carga(db: Session, empresa_id: int, carga_id: int) -> ProtheusCarga:
    carga = obter_carga(db, empresa_id, carga_id)
    stop_error = None

    if carga.rq_job_id and carga.status in {"pendente", "processando"}:
        try:
            send_stop_job_command(get_redis_connection(), carga.rq_job_id)
        except Exception as exc:
            stop_error = str(exc)

    carga.status = "cancelado"
    carga.erro = f"Cancelada pelo usuario. Stop RQ: {stop_error}" if stop_error else "Cancelada pelo usuario."
    carga.finalizado_em = datetime.now(timezone.utc)
    db.commit()
    db.refresh(carga)
    return carga


def excluir_carga(db: Session, empresa_id: int, carga_id: int) -> None:
    carga = obter_carga(db, empresa_id, carga_id)
    db.delete(carga)
    db.commit()


def listar_registros(db: Session, carga: ProtheusCarga, skip: int, limit: int) -> tuple[int, list[ProtheusCargaRegistro]]:
    query = db.query(ProtheusCargaRegistro).filter(ProtheusCargaRegistro.carga_id == carga.id)
    total = query.count()
    registros = query.order_by(ProtheusCargaRegistro.sequencia).offset(skip).limit(limit).all()
    return total, registros


def _tentar_enfileirar(db: Session, carga: ProtheusCarga) -> None:
    try:
        carga.rq_job_id = enqueue_protheus_carga(carga.id)
        carga.status = "processando"
        carga.erro = None
    except Exception as exc:
        carga.status = "erro"
        carga.erro = f"Falha ao enfileirar no RQ/Redis: {exc}"
    db.commit()
    db.refresh(carga)


def marcar_processando(db: Session, carga: ProtheusCarga) -> None:
    carga.status = "processando"
    carga.iniciado_em = datetime.now(timezone.utc)
    carga.finalizado_em = None
    carga.erro = None
    db.commit()


def marcar_concluido(db: Session, carga: ProtheusCarga, total_registros: int) -> None:
    carga.status = "concluido"
    carga.total_registros = total_registros
    carga.finalizado_em = datetime.now(timezone.utc)
    db.commit()


def marcar_erro(db: Session, carga: ProtheusCarga, erro: str) -> None:
    carga.status = "erro"
    carga.erro = erro[:8000]
    carga.finalizado_em = datetime.now(timezone.utc)
    db.commit()
