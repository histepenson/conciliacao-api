---
name: importar-csv-protheus
description: Use ao importar dados de uma empresa SEM acesso a API do Protheus (ex.: GENIX), a partir de CSV/Excel manuais, normalizando-os e gravando em protheus_carga/protheus_carga_registro no mesmo padrao de quem tem integracao via API (FINR130/150/470, CTBR140/400/480, MATR900, SFTENT, CT2RAZCT5)
---

# Importar CSV manual como se fosse carga via API Protheus

## Quando usar

A empresa nao tem `protheus_url`/`protheus_user`/`protheus_password` configurados
(sem acesso REST ao Protheus). Os dados chegam apenas em CSV/Excel exportados
manualmente, mas o frontend (telas de Conciliacao Financeira/Bancaria/Estoque/
Pre-Conferencia) precisa funcionar **sem nenhuma mudanca de codigo** — exatamente
como funciona hoje para empresas com integracao via API.

**Cadastro da empresa:** crie normalmente em `empresa` (nome, cnpj). Deixe
`protheus_tenant`, `protheus_url`, `protheus_rest_prefix`, `protheus_user`,
`protheus_password` em branco/NULL. Considere marcar
`permite_efetivar_divergente = true` se os dados historicos da empresa
provavelmente terao pequenas divergencias (evita bloqueio na efetivacao —
ver `services/efetivacao_service.py:130-153`).

## O mecanismo e UM SO: gravar em `protheus_carga` + `protheus_carga_registro`

Verificado direto no frontend (`C:\conciliacao-app`): **todas** as telas de
conciliacao (`ConciliacoesPagar.jsx`, `ConciliacoesBanco.jsx`,
`ConciliacoesEstoque.jsx`, `PreConferencia.jsx`) usam o hook
`useCargaProtheus` + os dialogs `Finr130/150/470ParamsDialog`,
`Ctbr140/400/480ParamsDialog`, `Matr900ParamsDialog`. Nenhuma delas tem upload
manual de arquivo — todas dependem de uma carga em `protheus_carga` (criada
hoje pelo botao "Carregar do Protheus", que chama a API e grava via
`workers/protheus_carga_worker.py`).

Cada dialog, ao abrir, chama:
```js
listarCargasProtheus({ empresa_id, tipo_relatorio: '<TIPO>', status: 'concluido', limit: 1 })
```
Se existir QUALQUER carga concluida daquele tipo/empresa, aparece o banner
**"Dados em cache disponiveis"** com o botao **"Usar cache"**
(`Finr470ParamsDialog.jsx:199-207`, mesmo padrao nos outros dialogs) — que
carrega os registros via `obterRegistrosCarga` direto de
`protheus_carga_registro.dados_json`, sem nunca chamar o Protheus.

**Logo: o trabalho de "importar" e so gravar a carga certa.** Depois disso o
usuario abre a tela normal no navegador, clica "Usar cache" em cada bloco,
clica "Processar Conciliacao" e "Efetivar" — tudo pelo fluxo ja implementado,
sem precisar de nenhum script adicional de efetivacao.

Use `scripts/importar_carga_manual.py` para todos os 9 tipos de relatorio
(inclusive FINR130/150/470/CTBR140/400/480/MATR900 — nao so SFTENT/CT2RAZCT5).

```bash
# 1) descobrir o empresa_id da GENIX
python scripts/importar_carga_manual.py --listar-empresas

# 2) gerar um JSON com a lista de registros no schema exato do tipo (ver tabelas abaixo)
#    -> escreva um script python ad-hoc com pandas: ler o CSV da GENIX, mapear/
#       renomear colunas pro schema de destino, json.dump(lista_de_dicts, f)

# 3) gravar a carga (repita por tipo)
python scripts/importar_carga_manual.py \
    --empresa-id <ID> --tipo FINR470 --data-base 20260531 \
    --registros-json finr470_registros.json
```

`data_base` deve ser YYYYMMDD (so identifica a carga; os dialogs do frontend
nao filtram por isso ao mostrar o banner de cache — pegam a carga concluida
mais recente daquele tipo). Reimportar com o mesmo `--tipo`/`--data-base`
substitui a carga anterior (idempotente). Cada CSV vira UMA carga (um tipo).

---

## Schema de destino por tipo de relatorio

Cada `dados_json` em `protheus_carga_registro` precisa ter EXATAMENTE os
campos que o Protheus produziria — alguns servicos gravam o JSON **bruto**
(raw, fiel ao `.prw`), outros gravam **ja transformado** (porque o worker usa
`buscar_como_registros_pagina`, que aplica uma transformacao antes de salvar).
Confirme sempre em `workers/protheus_carga_worker.py:127-150` e no
`services/<tipo>_service.py::buscar_como_registros_pagina` correspondente.

### FINR130 — Contas a Receber (RAW — `services/finr130_service.py` nao transforma)

| Campo | Origem/observacao |
|---|---|
| `filial`, `prefixo`, `numero`, `parcela`, `tipo` | identificacao do titulo |
| `cliente`, `loja`, `nome_cliente` | codigo cliente (sem prefixo C/F), loja, nome |
| `codigo_cli` | codigo Protheus completo `C` + digitos (ex: `C0000011`) — **se presente, o normalizador usa direto** (`tools/financeiro/base.py:540-554`) |
| `natureza`, `emissao` (YYYYMMDD), `vencto`, `vencto_real` (YYYYMMDD) | |
| `banco`, `situacao`, `numero_banco` | |
| `valor_original`, `saldo_na_data`, `saldo_atual`, `juros` | numericos |
| `moeda` | numero (1) |
| `historico`, `dias_vencidos`, `prazo` (`"CURTO"`/`"LONGO"`) | |

`codigo_cli` + `loja` + `filial` presentes e `codigo_cli` no padrao `^[CFcf]\d+$`
e o gatilho para o normalizador usar o codigo Protheus direto em vez de
parsear `cliente-loja-nome` manualmente — **sempre preencha os 3** (`codigo_cli`,
`loja`, `filial`) para os titulos a receber da GENIX.

### FINR150 — Contas a Pagar (TRANSFORMADO — `_titulos_para_registros` em `services/finr150_service.py:133-165`)

| Campo destino | Como montar |
|---|---|
| `codigo_nome_do_fornecedor` | `f"{fornecedor}-{loja}-{nome}"` |
| `tit_vencidos_valor_corrigido` | `saldo_na_data` se `dias_vencidos > 0`, senao `0` |
| `titulos_a_vencer_valor_nominal` | `saldo_na_data` se `dias_vencidos <= 0`, senao `0` |
| `vencto_real` | string YYYYMMDD ou DD/MM/YYYY |
| `data_de_emissao` | idem |
| `prf_numero_parcela` | `f"{prefixo}{numero}{parcela}"` |
| `dias_atraso` | mesmo valor de `dias_vencidos` (negativo = a vencer) |
| `tp`, `natureza`, `historico` | texto livre |

### FINR470 — Extrato Bancario (RAW — `protheus/ZFIN470API.prw:478-501`)

| Campo | Observacao |
|---|---|
| `data` | `DD/MM/YYYY` (data de disponibilidade) |
| `documento` | numero do documento/cheque |
| `prefixo_titulo` | ex: `"RA-01120253"`, `"NF9-000034395"` |
| `entradas`, `saidas`, `saldo_atual` | numericos, 2 decimais |
| `descricao`, `historico` | mesmo texto nos dois campos |
| `data_disponibilidade`, `data_movimento` | `YYYYMMDD` |
| `data_disponibilidade_br` | igual a `data` |
| `tipo_documento`, `tipo_movimento` | |
| `natureza` | `"R"` (recebimento) ou `"P"` (pagamento) |
| `conciliado` | boolean |
| `codigo_conciliacao` | string (pode ser vazia) |
| `valor_entrada`, `valor_saida` | iguais a `entradas`/`saidas` |
| `valor_movimento` | `entradas - saidas` |
| `moeda_relatorio` | `1` |

### CTBR140 — Balancete Filtrado (TRANSFORMADO — `Ctbr140Service._linha_para_registro`, `services/ctbr140_service.py:134-151`)

| Campo destino | Como montar |
|---|---|
| `Codigo` | codigo do item/centro de custo |
| `Descricao` | descricao do item |
| `Saldo atual` | saldo na direcao normal da conta: se `normal_cta=="2"` (credito-normal) inverte o sinal do saldo bruto, senao mantem |
| `Saldo anterior` | mesma regra de sinal, mas do saldo anterior ao periodo |

### CTBR400 e CTBR480 — Razao Contabil (RAW — `protheus/ZCT2RAZAPI.prw:242-255`, mesmo endpoint/shape pros dois tipos)

| Campo | Observacao |
|---|---|
| `data` | `DD/MM/YYYY` |
| `lote_sub_doc_linha` | concatenacao lote+sublote+doc+linha |
| `historico` | texto do lancamento |
| `xpartida` | conta de contrapartida |
| `c_custo` | `""` sempre (nao vem do CT2 nesta API) |
| `item_conta` | item da conta |
| `cod_cl_val` | classe de valor |
| `debito`, `credito` | numericos, 2 decimais, um dos dois e 0 por linha |
| `saldo_atual` | `0` sempre (a API zera aqui) |
| `conta` | codigo da conta contabil |

CTBR400 e CTBR480 sao o MESMO schema — a diferenca e so o uso (CTBR400 =
razao da conta banco/estoque; CTBR480 = razao geral usado na conciliacao
financeira). Gere uma carga `CTBR400` e, se precisar, outra `CTBR480` com os
mesmos registros (ou um subconjunto).

### MATR900 — Kardex de Estoque (RAW — `protheus/ZMATR900API.prw:415-437`, chaves em Title Case)

| Campo | Observacao |
|---|---|
| `Codigo`, `Descricao`, `UM`, `Tipo`, `Grupo` | identificacao do produto |
| `Custo Medio`, `Qtd Saldo`, `Vlr Total Saldo` | saldo atual |
| `Posicao IPI`, `Endereco` | |
| `Operacao Data` | `DD/MM/YYYY` |
| `ARM` | armazem |
| `TES`, `CF` | `CF` e o campo chave: `DE0`-`DE7` (entrada), `RE0`-`RE7` (saida), `PR0`, CFOPs numericos |
| `Documento Numero` | |
| `Entradas Quantidade`, `Entradas Custo Total` | |
| `Custo Medio do Movimento` | |
| `Saidas Quantidade`, `Saidas Custo Total` | |
| `Saldo Quantidade`, `Saldo Valor Total` | |
| `CLI/FOR/CC/PJ/OP/OS` | parceiro do movimento |

Atencao as chaves: sao literalmente como no relatorio Excel (com espacos e
Title Case), nao snake_case — `tools/estoque/kardex.py` normaliza isso
internamente, mas o `dados_json` salvo pelo worker (`buscar_como_registros_pagina`
so repassa `linhas` sem transformar) fica nesse formato bruto.

### SFTENT — Entradas Fiscais / Pre-Conferencia (RAW — `protheus/ZSFTENTAPI.prw`)

| Campo | Obrigatorio p/ matching |
|---|---|
| `filial`, `nf`, `cliefor`, `cfop`, `valcont`, `entrada` (`DD/MM/YYYY`) | sim |
| `tes` | so se o Lancamento Padrao usar `tes_codes` |
| `emissao`, `estado`, `especie`, `quant`, `aliqicm`, `baseicm`, `valicm`, `isenicm`, `outricm`, `icmscom`, `icmsdif`, `difal`, `icmsret`, `produto`, `cstpis`, `codbcc`, `valpis`, `valcof`, `valipi` | nao |

### CT2RAZCT5 — Razao com Lancamento Padrao / Pre-Conferencia (RAW — `protheus/ZCT2RAZCT5.prw:250-269`)

Mesmo schema de CTBR400/480, mais os campos do JOIN com CT5:

| Campo extra | Observacao |
|---|---|
| `ct2_key` | 22 chars: filial(4)+nf(9)+serie(3)+cliefor(6) — usado no matching de NF |
| `ct2_lp` | codigo do lancamento padrao (6 chars) — alimenta `lancamento_padrao.lp_codigo` |
| `ct2_origem` | >=7 chars, primeiros 7 = `"LP-SEQUEN"` |
| `ct2_itemc` | sempre o item de credito, mesmo em linha de debito |
| `ct5_desc` | descricao do LP — pode deixar `""` se nao tiver a referencia; o usuario completa depois pelo CRUD de Lancamento Padrao no frontend (gravar `CT2RAZCT5` ja faz upsert automatico em `lancamento_padrao` — `workers/protheus_carga_worker.py:94-104`) |

Depois de gravar `CT2RAZCT5` e `SFTENT`, `GET /v1/pre-conferencia/conferir?empresa_id=<ID>`
ja funciona sem nenhum parametro adicional (resolve a ultima carga concluida de cada tipo).

---

## Alternativa headless (sem abrir o navegador)

Se quiser pular a etapa de abrir a tela e clicar "Usar cache" / "Processar" /
"Efetivar", existe `scripts/efetivar_conciliacao_manual.py`: ele loga na API
(`/auth/login`), chama o endpoint de calculo (`/conciliacoes/contabil|bancaria|estoque`)
e depois o de efetivar (grava em `concilia.conciliacoes`). Os `registros` que
ele envia devem ser os MESMOS objetos gravados em `protheus_carga_registro`
(schemas acima) — os normalizadores backend (`tools/financeiro`, `tools/banco`,
`tools/estoque`) reconhecem esses nomes de campo nativamente porque foram
desenhados para consumir exatamente o formato que vem do Protheus.

Prefira o caminho normal (gravar a carga + usar a tela) quando possivel — fica
identico ao uso real e nao corre risco de o payload manual divergir do que o
backend espera em algum detalhe (ex: `tipo_conciliacao`, `conta_contabil_id`).
