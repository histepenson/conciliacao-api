"""
Inicia workers RQ para processar cargas do Protheus no Railway.
Substitui o comando `rq worker protheus-cargas`.
"""
import logging
import os
import uuid
from multiprocessing import Process

from rq import Queue, Worker

from core.redis import get_redis_connection
from core.rq import PROTHEUS_CARGA_QUEUE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

NUM_WORKERS = int(os.environ.get("RQ_NUM_WORKERS", "3"))

# Prefixo único por execução do processo pai — evita colisão de nomes no Redis
# quando o serviço reinicia antes dos registros antigos expirarem.
_RUN_ID = uuid.uuid4().hex[:8]


def _run_worker(worker_index: int) -> None:
    conn = get_redis_connection()
    queue = Queue(PROTHEUS_CARGA_QUEUE, connection=conn)
    name = f"protheus-cargas-{_RUN_ID}-{worker_index}"
    worker = Worker([queue], connection=conn, name=name)
    logging.info("Worker %s iniciado na fila '%s'", worker.name, PROTHEUS_CARGA_QUEUE)
    worker.work(logging_level="INFO")


if __name__ == "__main__":
    logging.info("Iniciando %s worker(s) RQ na fila '%s'", NUM_WORKERS, PROTHEUS_CARGA_QUEUE)

    if NUM_WORKERS <= 1:
        _run_worker(1)
    else:
        processes = [Process(target=_run_worker, args=(i + 1,)) for i in range(NUM_WORKERS)]
        for process in processes:
            process.start()

        try:
            for process in processes:
                process.join()
        except KeyboardInterrupt:
            logging.info("Encerrando workers RQ")
            for process in processes:
                process.terminate()
            for process in processes:
                process.join()
