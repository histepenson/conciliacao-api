# models/__init__.py
"""
Importacoes dos modelos em ordem correta para evitar problemas de relacionamento.

ORDEM IMPORTANTE:
1. Base (do db.py)
2. Modelos independentes (Usuario, Perfil)
3. Modelos de empresa
4. Modelos de associacao (UsuarioEmpresa)
5. Modelos que dependem de multiplos anteriores
"""

# Importa Base do db.py
from db import Base

# 1. Modelos independentes (sem FK ou com FK circular)
from .usuario import Usuario
from .perfil import Perfil

# 2. Modelos de empresa
from .empresa import Empresa

# 3. Modelos de associacao
from .usuario_empresa import UsuarioEmpresa

# 4. Modelos com 1 FK
from .planodecontas import PlanoDeContas

# 5. Modelos com multiplas FK
from .conciliacao import Conciliacao

# 6. Modelos que dependem dos anteriores
from .arquivoconciliacao import ArquivoConciliacao

# 7. Modelos de autenticacao
from .password_reset import PasswordReset
from .user_session import UserSession
from .audit_log import AuditLog, AuditAction

# 8. Modelos de estoque
from .produto import Produto
from .produto_fornecedor import ProdutoFornecedor
from .certificado_digital import CertificadoDigital
from .nfe import NfeEntrada, NfeEntradaItem, NfeSaida, NfeSaidaItem
from .estoque_alerta import EstoqueAlerta
from .estoque import EstoqueSaldo, EstoqueMovimentacao

# Lista todos os modelos exportados
__all__ = [
    "Base",
    # Auth
    "Usuario",
    "Perfil",
    "UsuarioEmpresa",
    "PasswordReset",
    "UserSession",
    "AuditLog",
    "AuditAction",
    # Business
    "Empresa",
    "PlanoDeContas",
    "Conciliacao",
    "ArquivoConciliacao",
    # Estoque
    "Produto",
    "ProdutoFornecedor",
    "CertificadoDigital",
    "NfeEntrada",
    "NfeEntradaItem",
    "NfeSaida",
    "NfeSaidaItem",
    "EstoqueAlerta",
    "EstoqueSaldo",
    "EstoqueMovimentacao",
]
