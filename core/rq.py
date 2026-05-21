import logging

from rq import Queue
from rq.job import Job

from core.redis import get_redis_connection

PROTHEUS_CARGA_QUEUE = "protheus-cargas"

logger = logging.getLogger(__name__)


def get_protheus_carga_queue() -> Queue:
    return Queue(PROTHEUS_CARGA_QUEUE, connection=get_redis_connection())


def _on_failure_carga_protheus(job: Job, connection, type, value, traceback) -> None:
    """Chamado pelo RQ quando o job falha ou é abandonado (AbandonedJobError inclusive)."""
    from db import SessionLocal
    from models.protheus_carga import ProtheusCarga
    from services.protheus_carga_service import marcar_erro

    carga_id = job.args[0] if job.args else None
    if not carga_id:
        return

    db = SessionLocal()
    try:
        carga = db.query(ProtheusCarga).filter(ProtheusCarga.id == carga_id).first()
        if carga and carga.status == "processando":
            erro = f"{type.__name__}: {value}" if type else "Job falhou ou foi abandonado pelo worker"
            marcar_erro(db, carga, erro)
            logger.warning("Carga %s marcada como erro via on_failure: %s", carga_id, erro)
    except Exception as exc:
        logger.exception("Erro no on_failure da carga %s: %s", carga_id, exc)
    finally:
        db.close()


def job_esta_ativo(job_id: str) -> bool:
    """Retorna True se o job ainda está na fila ou em execução no Redis."""
    try:
        conn = get_redis_connection()
        job = Job.fetch(job_id, connection=conn)
        return job.get_status() in {"queued", "started", "deferred", "scheduled"}
    except Exception:
        return False


def enqueue_protheus_carga(carga_id: int) -> str:
    from workers.protheus_carga_worker import executar_carga_protheus

    queue = get_protheus_carga_queue()
    job = queue.enqueue(
        executar_carga_protheus,
        carga_id,
        job_timeout="4h",
        result_ttl=86400,
        failure_ttl=604800,
        on_failure=_on_failure_carga_protheus,
    )
    return job.id
