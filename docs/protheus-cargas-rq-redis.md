# Cargas Protheus com RQ + Redis

## Objetivo

Este recurso permite carregar relatórios grandes do Protheus em background, gravar o resultado no banco e reutilizar a carga quando a mesma combinação de empresa, relatório, data base e parâmetros já estiver concluída.

O objetivo é evitar que o usuário processe novamente relatórios demorados, como FINR130, FINR150 e CTBR140, sempre que precisar usar a mesma base.

## Relatórios suportados

- FINR130
- FINR150
- CTBR140
- CTBR400
- CTBR480
- FINR470
- MATR900

O cálculo dos relatórios não foi reimplementado. O worker chama os serviços já existentes, que por sua vez chamam os fontes Protheus/AdvPL existentes.

## Fluxo

1. O usuário cria uma configuração de carga com relatório, empresa e parâmetros.
2. A API calcula um hash dos parâmetros normalizados.
3. Se já existir uma carga concluída para empresa, relatório, data base e hash, a API informa que ela pode ser reutilizada.
4. Se não existir, a API cria uma carga com status `pendente` e envia um job para a fila RQ.
5. O worker RQ busca os dados no Protheus, grava os registros em tabela e marca a carga como `concluido`.
6. A tela pode consultar o histórico, status, total de registros e registros gravados.

## Tabelas

### `concilia.protheus_carga_config`

Guarda os parâmetros configurados pelo usuário.

Campos principais:

- `empresa_id`
- `tipo_relatorio`
- `nome`
- `parametros_json`
- `ativo`
- `atualizar_automatico`
- `data_base_origem`
- `data_base_fixa`

### `concilia.protheus_carga`

Guarda cada execução.

Campos principais:

- `empresa_id`
- `tipo_relatorio`
- `data_base`
- `parametros_hash`
- `parametros_json`
- `status`
- `total_registros`
- `iniciado_em`
- `finalizado_em`
- `erro`
- `rq_job_id`

Status possíveis:

- `pendente`
- `processando`
- `concluido`
- `erro`

### `concilia.protheus_carga_registro`

Guarda os registros retornados pela carga.

Campos principais:

- `carga_id`
- `sequencia`
- `dados_json`

## Endpoints

Todos os endpoints ficam abaixo de:

```text
/api/v1/protheus-cargas
```

### Configurações

```http
GET /api/v1/protheus-cargas/configs
POST /api/v1/protheus-cargas/configs
PATCH /api/v1/protheus-cargas/configs/{config_id}
POST /api/v1/protheus-cargas/configs/{config_id}/executar?data_base=20260131
```

### Cargas

```http
GET /api/v1/protheus-cargas
POST /api/v1/protheus-cargas
GET /api/v1/protheus-cargas/{carga_id}
POST /api/v1/protheus-cargas/{carga_id}/reprocessar
GET /api/v1/protheus-cargas/{carga_id}/registros?skip=0&limit=2000
POST /api/v1/protheus-cargas/agendar-diario?data_base=20260131
```

## Redis e RQ

Adicionar no ambiente:

```env
REDIS_URL=redis://localhost:6379/0
```

Instalar dependências:

```bash
pip install -r requirements.txt
```

Rodar a API:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Rodar o worker:

```bash
rq worker protheus-cargas --url redis://localhost:6379/0
```

No Railway, o ideal é criar um serviço separado para o worker usando o mesmo código da API e o comando acima, apontando para o mesmo banco e Redis.

## Carga diária às 00:00

O backend expõe duas formas de enfileirar cargas automáticas:

1. Endpoint:

```http
POST /api/v1/protheus-cargas/agendar-diario?data_base=20260131
```

2. Script:

```bash
python -m workers.protheus_carga_scheduler --data-base 20260131
```

Esse script enfileira todas as configurações ativas e marcadas com `atualizar_automatico=True`.

Importante: a data base precisa vir de uma configuração real de período em aberto. Enquanto essa origem não estiver conectada a uma tabela de períodos, informe a data base no endpoint/script ou configure `data_base_fixa`.

## Tela

A tela criada no frontend fica em:

```text
/conciliacoes/cargas-protheus
```

Ela permite:

- cadastrar configurações de carga;
- executar uma configuração manualmente;
- ver histórico de cargas;
- reprocessar cargas;
- abrir os registros gravados.

## Migração

Migration criada:

```text
alembic/versions/f1a2b3c4d5e6_add_protheus_carga_rq_cache.py
```

Aplicar:

```bash
alembic upgrade head
```

## Observações importantes

- Reutilização só acontece quando a carga está `concluido`.
- O hash considera os parâmetros enviados no JSON. Mudou filtro, mudou hash, então gera nova carga.
- Os registros são salvos como JSONB para preservar o formato específico de cada relatório.
- O recurso não altera os fontes AdvPL nem a regra de cálculo dos saldos.
- Para relatórios contábeis, a integridade dos saldos continua dependendo dos serviços e fontes Protheus já existentes.
