# core/particularidades.py
"""
Catalogo fechado de chaves de particularidade por empresa.

Cada empresa pode ter particularidades habilitadas via `empresa_configuracao`
(tabela chave-valor auditavel, ver models/empresa_configuracao.py e
services/empresa_configuracao_service.py). A chave usada precisa estar
listada aqui - isso evita erro de digitacao silencioso (chave inexistente
nao ativa nada e nao gera erro nenhum se nao for validada).

Nova particularidade = novo membro neste Enum, feito junto com a
implementacao da regra de negocio correspondente (nao antes).
"""
from enum import Enum


class ChaveParticularidade(str, Enum):
    TEM_PRE_CONFERENCIA = "tem_pre_conferencia"
    TEM_CROMS051 = "tem_croms051"
    TEM_CONFERENCIA_LEASING = "tem_conferencia_leasing"
