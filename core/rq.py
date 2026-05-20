from rq import Queue

from core.redis import get_redis_connection

PROTHEUS_CARGA_QUEUE = "protheus-cargas"


def get_protheus_carga_queue() -> Queue:
    return Queue(PROTHEUS_CARGA_QUEUE, connection=get_redis_connection())


def enqueue_protheus_carga(carga_id: int) -> str:
    from workers.protheus_carga_worker import executar_carga_protheus

    queue = get_protheus_carga_queue()
    job = queue.enqueue(
        executar_carga_protheus,
        carga_id,
        job_timeout="4h",
        result_ttl=86400,
        failure_ttl=604800,
    )
    return job.id
