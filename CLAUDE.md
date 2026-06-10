# CLAUDE.md - Backend API

Este arquivo fornece orientações para o Claude Code ao trabalhar com código neste repositório.

## Visão Geral do Projeto

**conciliacao-api** é o backend de um sistema de conciliação contábil e financeira, desenvolvido com FastAPI e PostgreSQL. Processa arquivos Excel contendo dados financeiros e contábeis para identificar discrepâncias e gerar relatórios detalhados de conciliação.

**Frontend:** React em `C:\conciliacao-app`

### Fluxo Principal da Aplicação
1. Cadastro de empresa
2. Importação do plano de contas (Excel)
3. Upload de 3 arquivos de conciliação (Origem, Contábil Filtrado, Contábil Geral)
4. Processamento e geração de relatório de conciliação

## Comandos Principais

```bash
# Ativar ambiente virtual
.\venv\Scripts\activate     # Windows
source venv/bin/activate    # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Desenvolvimento (com reload automático)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Produção
uvicorn main:app --host 0.0.0.0 --port 8000

# Testar conexão com banco
python db.py
```

### Migrações (Alembic)
```bash
alembic revision --autogenerate -m "descrição"  # Criar migração
alembic upgrade head                             # Aplicar pendentes
alembic downgrade -1                             # Reverter última
alembic history                                  # Ver histórico
alembic current                                  # Status atual
```

## Arquitetura

### Estrutura de Camadas

```
Requisição HTTP
    ↓
Middleware (middleware/)    → Auth (JWT), tenant (empresa), permissões
    ↓
Router (routers/)           → Endpoints da API
    ↓
Schema Pydantic (schemas/)  → Validação de entrada/saída
    ↓
Service (services/)         → Lógica de negócio e orquestração
    ↓
Tools (tools/)              → Processamento de dados (normalização, cálculos)
    ↓
Model SQLAlchemy (models/)  → Acesso ao banco
    ↓
PostgreSQL (schema: concilia)
```

Jobs assíncronos (cargas Protheus) rodam fora do ciclo request/response via fila Redis (RQ) processada por `workers/`.

### Estrutura de Pastas (visão geral)

```
conciliacao-api/
├── main.py            # Entry point FastAPI: lifespan (APScheduler), CORS, exception handler, registro dos routers
├── db.py              # Configuração SQLAlchemy, pool de conexões
├── requirements.txt
├── alembic/           # Migrações (schema concilia)
│
├── core/              # Infraestrutura compartilhada
│   ├── config.py        # Settings (pydantic-settings): DB, JWT, SMTP, CORS, Protheus, Redis
│   ├── security.py       # Hash de senha, geração/validação de JWT
│   ├── protheus.py        # Criptografia de credenciais Protheus, helpers de integração
│   ├── protheus_http.py   # Cliente HTTP para REST do Protheus
│   ├── redis.py          # Conexão Redis (get_redis_connection)
│   └── rq.py             # Fila RQ "protheus-cargas", enqueue/job status, callback de falha
│
├── middleware/        # Multitenant e autorização (ver docs/ARCHITECTURE_AUTH_MULTITENANT.md)
│   ├── auth.py           # get_current_user: valida JWT, retorna CurrentUser
│   ├── tenant.py          # get_empresa_context: resolve EmpresaContext (empresa, perfil, permissões)
│   └── permission.py      # require_permission/require_admin/require_empresa_admin + Permissions
│
├── routers/           # ~28 routers, registrados em main.py com prefix="/api"
│   ├── auth_router.py                 # Login, refresh token, reset de senha
│   ├── admin_usuarios_router.py       # CRUD usuários (admin master)
│   ├── admin_empresas_router.py       # CRUD empresas (admin master)
│   ├── admin_perfis_router.py         # CRUD perfis/permissões (admin master)
│   ├── empresa_router.py              # CRUD de empresas (escopo do tenant)
│   ├── planodecontas_router.py        # CRUD + importação de plano de contas
│   ├── arquivo_router.py              # Upload e gestão de arquivos
│   ├── dashboard_router.py            # Indicadores consolidados
│   ├── conciliacao_router.py          # Conciliação financeira (FINR130/150 × CTBR140/480)
│   ├── conciliacao_bancaria_router.py # Conciliação bancária (FINR470 × CTBR400)
│   ├── conciliacao_estoque_router.py  # Conciliação de estoque (MATR900 × CTBR400)
│   ├── finr130_router.py / finr150_router.py / finr470_router.py  # Importação relatórios financeiros Protheus
│   ├── ctbr140_router.py / ctbr400_router.py / ctbr480_router.py  # Importação relatórios contábeis Protheus
│   ├── matr900_router.py              # Importação Kardex de estoque (Protheus)
│   ├── efetivacao_router.py           # Efetivação/baixa de itens conciliados
│   ├── protheus_carga_router.py       # Dispara/consulta cargas assíncronas do Protheus (RQ)
│   ├── produto_router.py              # CRUD de produtos
│   ├── produto_fornecedor_router.py   # De-Para produto x fornecedor
│   ├── certificado_router.py          # Certificado digital A1 (NF-e/SEFAZ)
│   ├── nfe_router.py                  # Importação de NF-e via SEFAZ
│   ├── estoque_router.py              # Saldos, movimentações, ajustes de estoque
│   ├── pre_conferencia_router.py      # Pré-conferência (CT2 × SFT)
│   └── lancamento_padrao_router.py    # Lançamentos padrão / templates contábeis
│
├── schemas/           # Validação Pydantic (1 arquivo por domínio, espelha routers/)
│
├── services/          # Lógica de negócio (1+ arquivo por domínio, espelha routers/)
│   ├── conciliacao_service.py / analise_diferencas_service.py     # Orquestração + análise detalhada (financeira)
│   ├── conciliacao_bancaria_service.py / *_efetivacao_service.py  # Conciliação bancária + efetivação
│   ├── conciliacao_estoque_service.py / *_efetivacao_service.py   # Conciliação de estoque + efetivação
│   ├── pre_conferencia_service.py / ct2raz_service.py / ct2raz_ct5_service.py / sft_ent_service.py
│   ├── estoque_service.py / fechamento_service.py                  # Saldos e fechamento de período
│   ├── nfe_service.py / sefaz_service.py / certificado_service.py  # NF-e e SEFAZ
│   ├── produto_service.py / produto_fornecedor_service.py
│   ├── protheus_carga_service.py / task_service.py                 # Cargas assíncronas Protheus
│   ├── auth_service.py / admin_*_service.py                        # Auth e administração
│   ├── dashboard_service.py / relatorio_service.py / file_storage_service.py
│   └── finr130/finr150/finr470/ctbr140/ctbr400/ctbr480/matr900_service.py  # Importação de relatórios Protheus
│
├── tools/             # Processamento de dados (normalização, cálculos)
│   ├── financeiro/    # base.py (parsing, normalização de código), contas_pagar.py, contas_receber.py, factory.py
│   ├── contabilidade.py / calc_diferencas.py / mappers.py          # Conciliação financeira
│   ├── banco/         # extrato_bancario.py, razao_banco.py, calc_diferencas_banco.py
│   └── estoque/       # kardex.py, razao_estoque.py, calc_diferencas_estoque.py
│
├── models/            # Modelos SQLAlchemy (schema concilia)
│   ├── empresa.py / planodecontas.py / conciliacao.py / arquivoconciliacao.py
│   ├── usuario.py / usuario_empresa.py / perfil.py / user_session.py / password_reset.py / audit_log.py
│   ├── produto.py / produto_fornecedor.py / nfe.py / certificado_digital.py
│   ├── estoque.py / estoque_alerta.py / protheus_carga.py
│   └── request_models.py / response_models.py  # Schemas legados
│
├── workers/           # Processamento assíncrono via RQ
│   ├── protheus_carga_worker.py     # Executa carga de dados do Protheus (job RQ)
│   └── protheus_carga_scheduler.py  # Agenda/dispara cargas
│
├── protheus/          # Fontes ADVPL/TLPP (.prw) expostos via REST custom no Protheus
│   ├── ZFINR130API.prw / ZFINR150API.prw / ZFIN470API.prw      # APIs financeiras (FINR130/150/470)
│   ├── ZCTBR140API.prw / ZCTBR400API.prw / ZCTBR480API.prw     # APIs contábeis (CTBR140/400/480)
│   ├── ZMATR900API.prw                                          # API Kardex de estoque (MATR900)
│   ├── ZCT2RAZAPI.prw / ZCT2RAZAPI_BKP.prw / ZCT2RAZCT5.prw     # APIs de razão (CT2RAZ)
│   └── ZSFTENTAPI.prw                                           # API de entradas (SFT)
│
└── uploads/           # Arquivos enviados pelo usuário
```

### Multitenant e Autenticação

- JWT (`core/security.py`) carrega `sub` (user id), `empresa_id` e `is_admin`.
- `middleware/auth.py::get_current_user` valida o token e retorna `CurrentUser`.
- `middleware/tenant.py::get_empresa_context` resolve `EmpresaContext` (empresa ativa, perfil e lista de permissões); admins master sem empresa selecionada recebem permissão `"*"`.
- `middleware/permission.py` expõe `require_permission(...)`, `require_admin`, `require_empresa_admin()` e a classe `Permissions` com as constantes de permissão (ex.: `conciliacao:write`, `estoque:read`).
- Praticamente todo router de domínio depende de `get_empresa_context` (ou `require_permission`) para isolar dados por `empresa_id`.
- Detalhes completos: [docs/ARCHITECTURE_AUTH_MULTITENANT.md](docs/ARCHITECTURE_AUTH_MULTITENANT.md)

### Integração com Protheus (cargas assíncronas)

- `core/protheus_http.py` faz as chamadas REST ao Protheus; `core/protheus.py` cuida de criptografia de credenciais (Fernet, `CERT_ENCRYPTION_KEY`).
- `routers/protheus_carga_router.py` dispara uma carga, que é enfileirada via `core/rq.py::enqueue_protheus_carga` na fila Redis `"protheus-cargas"`.
- `workers/protheus_carga_worker.py` consome a fila e executa `executar_carga_protheus`; falhas/abandonos atualizam o status da carga (`models/protheus_carga.py`) via callback `on_failure`.
- `workers/protheus_carga_scheduler.py` agenda cargas recorrentes.
- Resultado das cargas alimenta os relatórios FINR130/150/470, CTBR140/400/480 e MATR900.

### Jobs Agendados (APScheduler)

- Configurado no `lifespan` de `main.py`.
- `job_fechar_mes_anterior`: roda no dia 1 de cada mês às 02:00, fechando automaticamente o período de estoque do mês anterior (`services/fechamento_service.py`).

### Módulos de Negócio

| Módulo | Routers/Services principais | Documentação |
|--------|------------------------------|---------------|
| Conciliação Financeira (Contas a Receber/Pagar) | `conciliacao_router`, `conciliacao_service`, `analise_diferencas_service` | [docs/DOCUMENTACAO_CONCILIACAO.md](docs/DOCUMENTACAO_CONCILIACAO.md), [docs/REGRAS_NEGOCIO.md](docs/REGRAS_NEGOCIO.md) |
| Conciliação Bancária | `conciliacao_bancaria_router`, `conciliacao_bancaria_service`, `tools/banco/` | docs/REGRAS_NEGOCIO.md §6 |
| Conciliação de Estoque (Kardex × Razão) | `conciliacao_estoque_router`, `conciliacao_estoque_service`, `tools/estoque/` | docs/REGRAS_NEGOCIO.md §7 |
| Pré-Conferência (CT2 × SFT) | `pre_conferencia_router`, `pre_conferencia_service`, `ct2raz_*`, `sft_ent_service` | docs/REGRAS_NEGOCIO.md §9 |
| Estoque (saldos, fechamento, NF-e, SEFAZ) | `estoque_router`, `nfe_router`, `produto_router`, `produto_fornecedor_router`, `certificado_router` | [docs/DOCUMENTACAO_ESTOQUE.md](docs/DOCUMENTACAO_ESTOQUE.md), docs/REGRAS_NEGOCIO.md §8 |
| Importação de Relatórios Protheus | `finr130/150/470_router`, `ctbr140/400/480_router`, `matr900_router`, `protheus_carga_router` | - |
| Lançamento Padrão | `lancamento_padrao_router` | - |
| Administração (usuários/empresas/perfis) | `admin_usuarios_router`, `admin_empresas_router`, `admin_perfis_router`, `auth_router` | docs/ARCHITECTURE_AUTH_MULTITENANT.md |
| Dashboard | `dashboard_router`, `dashboard_service` | - |

## Banco de Dados

**PostgreSQL** com schema `concilia`

### Tabelas e Relacionamentos

```
┌─────────────────┐
│     empresa     │  (raiz)
├─────────────────┤
│ id (PK)         │
│ nome            │
│ cnpj (unique)   │
│ status          │
│ created_at      │
│ updated_at      │
└────────┬────────┘
         │
         ├──────────────────────────────┐
         │                              │
         ▼                              ▼
┌─────────────────┐            ┌─────────────────┐
│  plano_contas   │            │  conciliacoes   │
├─────────────────┤            ├─────────────────┤
│ id (PK)         │            │ id (PK)         │
│ empresa_id (FK) │◄───────────│ empresa_id (FK) │
│ conta_contabil  │            │ conta_contabil_id (FK)
│ descricao       │            │ periodo         │
│ tipo_conta      │            │ saldo           │
│ conciliavel     │            │ created_at      │
│ conta_superior  │            │ updated_at      │
│ created_at      │            └────────┬────────┘
│ updated_at      │                     │
└─────────────────┘                     ▼
                               ┌─────────────────────┐
                               │ arquivos_conciliacao│
                               ├─────────────────────┤
                               │ id (PK)             │
                               │ conciliacao_id (FK) │
                               │ caminho_arquivo     │
                               │ data_conciliacao    │
                               │ created_at          │
                               │ updated_at          │
                               └─────────────────────┘
```

### Convenções de Nomenclatura
| Elemento | Padrão | Exemplo |
|----------|--------|---------|
| Classes (models) | Singular, PascalCase | `Empresa`, `PlanoDeContas` |
| Tabelas | Singular, snake_case | `empresa`, `plano_contas` |
| Schema | Sempre `concilia` | `__table_args__ = {"schema": "concilia"}` |
| Colunas | snake_case | `created_at`, `conta_contabil` |
| FKs | Full path | `"concilia.empresa.id"` |

## Endpoints da API

Base URL: `http://localhost:8000/api`

### Empresas (`/empresas`)
| Método | Endpoint | Função |
|--------|----------|--------|
| POST | `/empresas/` | Criar empresa (valida CNPJ duplicado) |
| GET | `/empresas/` | Listar todas |
| GET | `/empresas/{id}` | Obter por ID |
| PUT | `/empresas/{id}` | Atualizar (parcial) |
| DELETE | `/empresas/{id}` | Excluir (cascade) |

### Plano de Contas (`/plano-contas`)
| Método | Endpoint | Função |
|--------|----------|--------|
| GET | `/plano-contas/?empresa_id=X` | Listar contas (paginação) |
| GET | `/plano-contas/{id}` | Obter por ID |
| POST | `/plano-contas/` | Criar conta |
| PUT | `/plano-contas/{id}` | Atualizar |
| DELETE | `/plano-contas/{id}` | Excluir |
| POST | `/plano-contas/importar` | **Importar Excel** |

### Conciliação (`/conciliacoes`)
| Método | Endpoint | Função |
|--------|----------|--------|
| POST | `/conciliacoes/contabil` | **Processar conciliação** (endpoint principal) |

### Arquivos (`/arquivos`)
| Método | Endpoint | Função |
|--------|----------|--------|
| GET | `/arquivos/` | Listar (filtro por empresa_id) |
| GET | `/arquivos/{id}` | Obter por ID |
| POST | `/arquivos/` | Criar registro |
| POST | `/arquivos/upload` | **Upload de arquivo** |
| PUT | `/arquivos/{id}` | Atualizar |
| DELETE | `/arquivos/{id}` | Excluir (arquivo + registro) |

### Documentação
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Fluxo de Processamento da Conciliação

```
POST /conciliacoes/contabil
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│ RequestConciliacao                                      │
│ ├── base_origem: {registros: [...]}       → Financeiro  │
│ ├── base_contabil_filtrada: {registros, conta_contabil} │
│ ├── base_contabil_geral: {registros: [...]}             │
│ └── parametros: {data_base, ...}                        │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ ConciliacaoService.executar()           │
│                                         │
│ 1. Valida dados de entrada              │
│ 2. normalizar_planilha_financeira()     │
│    └── Output: codigo | cliente | valor │
│ 3. normalizar_planilha_contabilidade()  │
│    └── Output: codigo | cliente | valor │
│ 4. calcular_diferencas()                │
│    └── Merge + cálculo de diferenças    │
│ 5. Filtra por tipo_diferenca            │
│ 6. AnaliseDiferencasService             │
│    └── Análise detalhada por código     │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ RelatorioConsolidacao (Response)        │
│ ├── resumo                              │
│ ├── diferencas_origem_maior             │
│ ├── diferencas_contabilidade_maior      │
│ ├── analise_detalhada                   │
│ ├── resumo_analise                      │
│ ├── observacoes                         │
│ └── alertas                             │
└─────────────────────────────────────────┘
```

## Tools - Processamento de Dados

### financeiro.py
**Função:** `normalizar_planilha_financeira(entrada) → DataFrame`

Processa planilha financeira com:
- Normalização de nomes de colunas
- Extração de código cliente: `"CODIGO-LOJA-NOME"` → `C{base}{loja}`
- Cálculo de valor: vencidos + a vencer
- Parse de números BR: `1.234.567,89`, `(100,00)`, sufixos D/C
- Cálculo de dias vencidos
- Classificação: "CURTO PRAZO" (≤365 dias) ou "LONGO PRAZO"
- Agregação por código

**Output:** `codigo | cliente | valor | dias_vencidos | TIPO`

### contabilidade.py
**Função:** `normalizar_planilha_contabilidade(entrada) → DataFrame`

Processa planilha contábil com:
- Normalização de nomes de colunas
- Extração de código: 6+2 dígitos → `C{base}{loja}`
- Parse de números BR
- Agregação por código

**Output:** `codigo | cliente | valor`

### calc_diferencas.py
**Função:** `calcular_diferencas(df_fin, df_cont, salvar_arquivo=True) → dict`

Calcula diferenças entre financeiro e contabilidade:
- Outer merge por código
- `diferenca = valor_cont - valor_fin`
- `diferenca_abs = |diferenca|`
- `diferenca_perc = (diferenca / valor_fin) * 100`

Classificação:
- `tipo_diferenca`: "Sem diferença" (≤0.01), "Contabilidade > Financeiro", "Financeiro > Contabilidade", "Exclusivo"
- `origem`: "Ambos", "Só Contabilidade", "Só Financeiro"

**Export Excel** (se salvar_arquivo=True):
- Sheet 1: Total das Diferenças
- Sheet 2: Com Diferenças
- Sheet 3: Só Financeiro
- Sheet 4: Só Contabilidade
- Sheet 5: Resumo

### mappers.py
Funções de mapeamento para schemas de resposta:
- `map_origem_maior(row)` → DiferencaOrigemMaior
- `map_contabilidade_maior(df, conta)` → List[DiferencaContabilidadeMaior]
- `classificar_prazo(codigo)` → "Curto" | "Longo"

## Services - Lógica de Negócio

### conciliacao_service.py
Classe `ConciliacaoService` - orquestra o fluxo de conciliação:
- `validar_dados()` - Valida estrutura do request
- `executar()` - Método principal de processamento
- `_filtrar_razao_por_conta()` - Filtra razão contábil
- `_formatar_resumo_analise()` - Formata resumo de análise

### analise_diferencas_service.py
Classe `AnaliseDiferencasService` - análise detalhada:
- `processar_analise_detalhada()` - Análise por código
- `gerar_resumo_analise()` - Totais e percentuais
- `_classificar_tipo()` - CONCILIADO | SO_FINANCEIRO | SO_CONTABILIDADE | DIVERGENTE_VALOR
- `_status()` - "verde" (≤0.01) | "vermelho"

**Threshold de conciliação:** `0.01` (R$ 0,01)

## Padrões de Código

### Routers
```python
@router.post("/", response_model=EmpresaOut)
def criar_empresa(empresa: EmpresaCreate, db: Session = Depends(get_db)):
    # Validação de duplicidade no service
    # HTTPException(400) para erros de negócio
    # HTTPException(404) para não encontrado
```

### Services
```python
def criar_empresa(db: Session, empresa: EmpresaCreate) -> Empresa:
    # Verifica duplicidade
    if db.query(Empresa).filter(Empresa.cnpj == empresa.cnpj).first():
        raise HTTPException(400, "CNPJ já cadastrado")
    # Cria e retorna
```

### Models
```python
class Empresa(Base):
    __tablename__ = "empresa"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships com cascade
    planos = relationship("PlanoDeContas", back_populates="empresa", cascade="all, delete-orphan")
```

### Schemas
```python
class EmpresaCreate(BaseModel):
    nome: str
    cnpj: str
    status: bool = True

class EmpresaUpdate(BaseModel):
    nome: Optional[str] = None
    cnpj: Optional[str] = None
    status: Optional[bool] = None

class EmpresaOut(BaseModel):
    id: int
    nome: str
    cnpj: str
    status: bool
    created_at: datetime

    class Config:
        from_attributes = True
```

## Configuração

### Arquivo .env
```env
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require
```

### db.py - Pool de Conexões
```python
Pool size: 10
Max overflow: 20
SSL: via DATABASE_URL
```

### Dependências Principais
- **FastAPI** 0.109.0 - Framework web
- **SQLAlchemy** ≥2.0.25 - ORM
- **Alembic** - Migrações
- **Uvicorn** 0.27.0 - Servidor ASGI
- **Pandas** ≥2.2.0 - Processamento de dados
- **openpyxl** 3.1.2 - Leitura/escrita Excel
- **psycopg2-binary** ≥2.9 - Driver PostgreSQL
- **python-dotenv** ≥1.0.0 - Variáveis de ambiente
- **python-multipart** 0.0.6 - Upload de arquivos

## Notas Importantes

1. **Schema do banco:** Sempre usar `concilia` em todas as operações
2. **Tabelas:** Nomes no SINGULAR (diferente do padrão Django)
3. **Uploads:** Salvos em `uploads/`
4. **Threshold:** Diferenças ≤ R$ 0,01 são consideradas conciliadas
5. **Alembic:** URL do banco hardcoded em `alembic.ini` - ajustar se necessário
6. **Testes:** Não implementados
7. **CORS:** Configurado para aceitar qualquer origem (desenvolvimento)

## Integração com Frontend

O frontend React está em `C:\conciliacao-app` e consome esta API via:
- Base URL: `http://localhost:8000/api`
- Formato: JSON
- Upload: multipart/form-data
