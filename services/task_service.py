"""
Gerenciamento de tarefas assíncronas em memória.
Tasks são resetadas ao reiniciar o servidor — suficiente para o volume atual.
"""
import threading
from uuid import uuid4
from datetime import datetime

_lock = threading.Lock()
_tasks: dict[str, dict] = {}


def criar_task() -> str:
    task_id = str(uuid4())
    with _lock:
        _tasks[task_id] = {
            "status": "processando",
            "progresso": 0,
            "total": 0,
            "importadas": 0,
            "pendentes_vinculo": 0,
            "erro": None,
            "criado_em": datetime.utcnow().isoformat(),
        }
    return task_id


def atualizar_task(task_id: str, **kwargs) -> None:
    with _lock:
        if task_id in _tasks:
            _tasks[task_id].update(kwargs)


def concluir_task(task_id: str, importadas: int, pendentes_vinculo: int) -> None:
    with _lock:
        if task_id in _tasks:
            _tasks[task_id].update({
                "status": "concluido",
                "progresso": _tasks[task_id].get("total", 0),
                "importadas": importadas,
                "pendentes_vinculo": pendentes_vinculo,
            })


def falhar_task(task_id: str, erro: str) -> None:
    with _lock:
        if task_id in _tasks:
            _tasks[task_id].update({"status": "erro", "erro": erro})


def obter_task(task_id: str) -> dict:
    with _lock:
        return dict(_tasks.get(task_id, {}))
