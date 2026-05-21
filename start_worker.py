"""
Inicia um pool de workers RQ para processar cargas do Protheus em paralelo.
Substitui o comando `rq worker protheus-cargas` no Railway.
"""
import os
import logging

from rq import WorkerPool

from core.redis import get_redis_connection
from core.rq import PROTHEUS_CARGA_QUEUE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

NUM_WORKERS = int(os.environ.get("RQ_NUM_WORKERS", "3"))

if __name__ == "__main__":
    conn = get_redis_connection()
    logging.info("Iniciando WorkerPool com %s workers na fila '%s'", NUM_WORKERS, PROTHEUS_CARGA_QUEUE)
    pool = WorkerPool(
        queues=[PROTHEUS_CARGA_QUEUE],
        connection=conn,
        num_workers=NUM_WORKERS,
    )
    pool.start(logging_level="INFO")
