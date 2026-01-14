# models/__init__.py
"""
Importações dos modelos em ordem correta para evitar problemas de relacionamento.

ORDEM IMPORTANTE:
1. Base (do db.py)
2. Modelos independentes (Empresa)
3. Modelos que dependem dos anteriores (PlanoDeContas, Conciliacao)
4. Modelos que dependem de múltiplos anteriores (ArquivoConciliacao)
"""

# Importa Base do db.py
from db import Base

# 1. Modelos independentes (sem FK)
from .empresa import Empresa

# 2. Modelos com 1 FK
from .planodecontas import PlanoDeContas

# 3. Modelos com múltiplas FK
from .conciliacao import Conciliacao

# 4. Modelos que dependem dos anteriores
from .arquivoconciliacao import ArquivoConciliacao

# Lista todos os modelos exportados
__all__ = [
    "Base",
    "Empresa",           # ← SINGULAR (mudou de Empresas)
    "PlanoDeContas",
    "Conciliacao",
    "ArquivoConciliacao",
]