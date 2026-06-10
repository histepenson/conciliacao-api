# Smart Conciliações — Regras de Negócio

> Última atualização: Junho 2026
>
> Este documento consolida as regras de negócio implementadas no backend, extraídas e atualizadas a partir de
> `AJUSTE_FILTRO_CONTA_CONTABIL.md`, `AJUSTE_THRESHOLD_CONCILIACAO.md`, `ESTRUTURA_DADOS_FINANCEIRO_CONTABILIDADE.md`,
> `IMPLEMENTACAO_ANALISE_DETALHADA*.md`, `PRE_CONFERENCIA_DADOS.md` e do `CLAUDE.md`. Os arquivos originais
> permanecem na raiz do projeto como histórico de implementação, mas a referência viva das regras é este documento.

---

## Índice

1. [Threshold Geral de Conciliação](#1-threshold-geral-de-conciliação)
2. [Parsing de Valores (formato BR)](#2-parsing-de-valores-formato-br)
3. [Normalização de Códigos Cliente/Fornecedor](#3-normalização-de-códigos-clientefornecedor)
4. [Conciliação Financeira (A Receber / A Pagar)](#4-conciliação-financeira-a-receber--a-pagar)
5. [Análise Detalhada por Código](#5-análise-detalhada-por-código)
6. [Conciliação Bancária](#6-conciliação-bancária)
7. [Conciliação de Estoque (Kardex × Razão CTBR400)](#7-conciliação-de-estoque-kardex--razão-ctbr400)
8. [Módulo de Estoque (Saldos e Fechamento)](#8-módulo-de-estoque-saldos-e-fechamento)
9. [Pré-Conferência (CT2 × SFT)](#9-pré-conferência-ct2--sft)
10. [Normalização de Datas](#10-normalização-de-datas)
11. [Correção de Header de Relatórios](#11-correção-de-header-de-relatórios)

---

## 1. Threshold Geral de Conciliação

**Valor:** `R$ 0,01` (constante `THRESHOLD_CONCILIACAO = 0.01` / literal `0.01` espalhado pelo código).

Diferenças **menores ou iguais a R$ 0,01 (`<= 0.01`)** são consideradas **conciliadas**. Diferenças **maiores que R$ 0,01 (`> 0.01`)** são **divergentes**.

| Diferença Absoluta | Status |
|---------------------|--------|
| R$ 0,00 | 🟢 CONCILIADO |
| R$ 0,01 | 🟢 CONCILIADO |
| R$ 0,02+ | 🔴 DIVERGENTE |

**Por quê `<=` e não `<`:** diferenças de 1 centavo são geralmente arredondamento e não devem gerar alertas. Considerar `< 0.01` deixaria diferenças de exatamente R$ 0,01 marcadas erroneamente como divergentes.

Esse threshold é usado de forma consistente em:
- `services/analise_diferencas_service.py` (`_classificar_tipo`, `_status`)
- `tools/calc_diferencas.py` (contagem de registros com/sem diferença)
- `tools/banco/calc_diferencas_banco.py` (matching e classificação por dia)
- `tools/estoque/calc_diferencas_estoque.py` (matching e classificação por grupo/registro)
- `services/pre_conferencia_service.py` (matching CT2 × SFT)

---

## 2. Parsing de Valores (formato BR)

Função principal: `tools/financeiro/base.py::parse_numero_brasileiro` (usada por contas a receber/pagar). Existe uma variação equivalente em `tools/contabilidade.py::converter_valor` para o balancete.

Formatos suportados:
- `1.234.567,89` → milhar com ponto, decimal com vírgula
- `1234,89` → sem milhar
- `(1.234,89)` → negativo por parênteses
- `1234,89-` → negativo por sufixo `-`
- `1000D` / `1000C` → sufixo Débito/Crédito (no balancete, **C inverte o sinal** — crédito é tratado como negativo)

Regra de conversão:
1. Remove espaços e caracteres não numéricos (exceto `, . - ()`).
2. Se houver vírgula → remove pontos (milhar) e troca vírgula por ponto (decimal).
3. Se não houver vírgula e houver mais de um ponto → trata pontos como separador de milhar e remove todos.
4. Aplica sinal negativo conforme parênteses/sufixo `-`/sufixo `C`.

---

## 3. Normalização de Códigos Cliente/Fornecedor

### 3.1 Regra de ouro (extração base/loja)

Função: `tools/financeiro/base.py::extrair_base_loja` / `normalizar_codigo_cliente`

- Usar o separador **`-`** para dividir base e loja — **nunca** posições fixas de dígitos (bases podem ter mais de 6 dígitos).
- **Base**: preserva letras + dígitos → `re.sub(r"[^a-zA-Z0-9]", "", parte0)`. **Não** usar `\D+`, pois remove prefixos alfabéticos (ex.: "EX").
- **Loja**: extrai apenas dígitos → `re.sub(r"\D+", "", parte1)`.
- **Sem separador `-`**: todo o texto é o código completo. **Não** completar loja com `"00"` — isso geraria um código diferente do usado na contabilidade.

Exemplos:
```
"01704361-81-NOME CLIENTE" -> base="01704361", loja="81" -> código "C0170436181"
"123456-789"                -> base="123456", loja="789" -> código "C123456789"
"12345678" (sem separador)  -> código "C12345678" (sem acrescentar loja)
```

Prefixo: `C` para clientes (Contas a Receber), `F` para fornecedores (Contas a Pagar).

### 3.2 Código vindo pronto do Protheus

Quando o registro já vem com `codigo_cli` no formato `C\d+`/`F\d+` **e** existem colunas `loja`/`filial` (indicativo de carga vinda da API Protheus), o sistema usa `codigo_cli` diretamente — ele já contém base+loja no formato correto, sem reaplicar a extração.

### 3.3 Código da Contabilidade (CTBR140 / CTBR480)

A contabilidade já entrega o código formatado (`tools/contabilidade.py`). A única transformação aplicada é **remover espaços internos**:

```
"F01133510 0002" -> "F011335100002"
```

Isso é necessário porque o CTBR140/CTBR480 pode trazer o código com espaço como separador em vez de traço, o que quebrava o merge com o financeiro (`F01133510 0002` ≠ `F011335100002`).

### 3.4 Matching agnóstico de prefixo C/F (análise detalhada)

Em `services/analise_diferencas_service.py`, as funções `_normalizar_codigo_numerico`, `_normalizar_item_conta_razao` e `_normalizar_codigo_razao` **removem o prefixo C/F** antes de comparar:

```
"F011335100002" -> "011335100002"
"C011335100002" -> "011335100002"
```

Isso permite que o matching no razão geral funcione independentemente de a conta conciliada ser de Contas a Receber (prefixo C) ou Contas a Pagar (prefixo F). A coluna **COD CL VAL** do CTBR480, quando disponível, tem prioridade sobre **ITEM CONTA** na lista de candidatos de matching.

---

## 4. Conciliação Financeira (A Receber / A Pagar)

### 4.1 Bases utilizadas

| Base | Relatório Protheus | Papel |
|------|--------------------|----|
| Origem (Financeiro) | FINR130 (Receber) / FINR150 (Pagar) | Posição dos títulos |
| Contábil Filtrado | CTBR140 (Balancete) | Saldo contábil da conta conciliada |
| Contábil Geral (Razão) | CTBR480 (Razão Geral) | Lançamentos individuais para análise detalhada |

### 4.2 Cálculo do valor (financeiro)

Implementado em `ProcessadorFinanceiroBase._calcular_valor` (`tools/financeiro/base.py`):

- Se existirem colunas de **valor vencido** e **valor a vencer**, o valor final é a **soma** das duas.
- Caso contrário, usa uma **coluna única de valor** (busca exata e depois flexível por substring).
- A busca de colunas é flexível: tenta nomes exatos da configuração e, se não achar, varre por combinações de substrings (`buscar_coluna_flexivel`).

### 4.3 Classificação de prazo (curto/longo)

Função: `classificar_prazo` (`tools/financeiro/base.py`)

- `dias_vencidos <= 365` → `"CURTO PRAZO"`
- `dias_vencidos > 365` → `"LONGO PRAZO"`
- Valores nulos (`NaN`) são tratados como `"CURTO PRAZO"`.

`dias_vencidos` é calculado como `hoje - data_vencimento` (em dias).

### 4.4 Agregação

Tanto o financeiro quanto a contabilidade são **agrupados por `codigo`** antes do merge (somando os valores). Isso evita duplicação de linhas no merge final (`tools/calc_diferencas.py` / `tools/contabilidade.py`).

### 4.5 Cálculo de diferenças (`tools/calc_diferencas.py`)

```
diferenca       = valor_contabil - valor_financeiro
diferenca_abs   = |diferenca|
diferenca_perc  = (diferenca / valor_financeiro) * 100
```

Classificação `tipo_diferenca`:

| Condição | tipo_diferenca |
|----------|-----------------|
| `diferenca == 0` | "Sem diferenca" |
| `diferenca > 0` | "Contabilidade > Financeiro" |
| `diferenca < 0` | "Financeiro > Contabilidade" |
| `origem != "Ambos"` (existe em apenas uma base) | "Exclusivo" (sobrescreve a classificação acima) |

Classificação `origem` (resultado do `outer merge` por `codigo`):
- `"Ambos"` — código presente nas duas bases
- `"Só Contabilidade"` — código só na contabilidade
- `"Só Financeiro"` — código só no financeiro

Contagens do resumo:
- `registros_com_diferenca` = `diferenca_abs > 0.01`
- `registros_sem_diferenca` = `diferenca_abs <= 0.01`

### 4.6 Filtro do Razão Geral pela conta contábil

Antes da análise detalhada, o razão geral (CTBR480 — pode conter lançamentos de **todas** as contas contábeis) é **filtrado pela conta contábil que está sendo conciliada** (`ConciliacaoService._filtrar_razao_por_conta`, `services/conciliacao_service.py`).

Sem esse filtro, o rastreamento de um fornecedor poderia encontrar lançamentos do mesmo código em outras contas (ex.: Caixa, Bancos), produzindo análises sem sentido contábil. Com o filtro, a análise detalhada de "Conta 2.01.01.001 — Fornecedores" só considera lançamentos dessa conta.

---

## 5. Análise Detalhada por Código

Implementada em `services/analise_diferencas_service.py` (`AnaliseDiferencasService`).

### 5.1 Classificação (`_classificar_tipo`)

```python
if abs(diferenca) <= 0.01:
    return "CONCILIADO"
if valor_financeiro > 0 and valor_contabilidade == 0:
    return "SO_FINANCEIRO"
if valor_contabilidade > 0 and valor_financeiro == 0:
    return "SO_CONTABILIDADE"
return "DIVERGENTE_VALOR"
```

Status visual: `"verde"` se `|diferenca| <= 0.01`, senão `"vermelho"`.

| Tipo | Significado |
|------|-------------|
| **CONCILIADO** | Financeiro = Contabilidade (dentro do threshold) |
| **SO_FINANCEIRO** | Existe valor no financeiro, mas nada (ou zero) na contabilidade |
| **SO_CONTABILIDADE** | Existe valor na contabilidade, mas nada (ou zero) no financeiro |
| **DIVERGENTE_VALOR** | Existe valor nas duas bases, mas com diferença > R$ 0,01 |

### 5.2 Regra contábil de lançamento (Contas a Pagar/Receber)

- **Geração de título** (compra/venda) → lançamento a **CRÉDITO** na contabilidade.
- **Baixa de título** (pagamento/recebimento) → lançamento a **DÉBITO** na contabilidade (zera o crédito gerado).
- **Saldo contábil do código** = `total_credito - total_debito`.

### 5.3 Rastreamento de lançamentos no razão

Para cada código (já filtrado pela conta contábil — ver 4.6), o sistema:

1. Busca **todos os lançamentos do código** no razão filtrado.
2. Separa por **DÉBITO** e **CRÉDITO**, calcula `total_credito`, `total_debito` e `total_rastreado` (saldo = crédito − débito).
3. Identifica:
   - **`lancamentos_nao_contabilizados`**: valores que deveriam existir na contabilidade (ex.: financeiro maior que contabilidade) mas não foram encontrados.
   - **`lancamentos_orfaos_contabilidade`**: lançamentos na contabilidade sem correspondência no financeiro (ex.: contabilidade maior que financeiro).
4. Extrai do **histórico** do lançamento contábil (campo livre):
   - **Número da NF** (`extrair_nf_do_historico`) — formatos como `"NF. 020252443"`, `"NF354753007"`, `"NOTA FISCAL 123456"`.
   - **Código do fornecedor** (`extrair_codigo_fornecedor_do_historico`) — formatos como `"FORN 004111"`, `"FORNECEDOR 067201"`.

### 5.4 Critérios de match (confiança)

| Critério | Confiança |
|----------|-----------|
| Código do fornecedor encontrado no histórico/Item Contábil | ALTA |
| NF do financeiro = NF extraída do histórico | ALTA |
| Valor aproximado, tolerância < 1% | ALTA |
| Valor aproximado, tolerância 1–3% | MÉDIA |
| Valor aproximado, tolerância > 3% (até 5–10%) | BAIXA |

### 5.5 Análise profunda SO_CONTABILIDADE

Para registros classificados como `SO_CONTABILIDADE`, o serviço tenta selecionar um **subconjunto de lançamentos do razão** cuja soma "fecha" exatamente a diferença, com tolerância de `0.01` (`_selecionar_registros_que_somam` / lógica de seleção por subconjunto). Isso ajuda a apontar exatamente quais lançamentos compõem o valor não localizado no financeiro.

### 5.6 Filtro por período

Quando `data_base` é informada, `_periodo_data_base`/`_data_no_periodo` permitem restringir a análise a lançamentos do **mesmo mês/ano** da data-base da conciliação (formatos aceitos: `%d/%m/%Y`, `%Y-%m-%d`, `%m/%d/%Y`, `%d/%m/%y`).

---

## 6. Conciliação Bancária

Bases: **FINR470** (extrato bancário) × **CTBR400** (razão contábil da conta banco).

Implementado em `tools/banco/calc_diferencas_banco.py`.

### 6.1 Regra de equivalência

```
Entrada no extrato  = Débito no razão
Saída no extrato    = Crédito no razão
```

### 6.2 Agrupamento por dia

Extrato e razão são **agrupados por dia** (`data` no formato `DD/MM/YYYY`, normalizada via `pd.to_datetime(..., dayfirst=True)`):

```
dif_entradas = debitos_razao - entradas_extrato
dif_saidas   = creditos_razao - saidas_extrato
```

Um dia é **conciliado** quando `|dif_entradas| <= 0.01` **e** `|dif_saidas| <= 0.01`.

### 6.3 Matching individual

Além do agrupamento por dia, o módulo tenta matching **registro a registro** por número de documento e por valor:
- Match exato (documento + valor, tolerância `0.01`)
- Match por soma de valores do mesmo documento
- Match por soma de documentos relacionados

---

## 7. Conciliação de Estoque (Kardex × Razão CTBR400)

> Esta é a "Conciliação de Estoque" do menu **Conciliações**. **Não** deve ser confundida com o módulo de **Estoque** (cadastro de produtos, NF-e, saldos — ver seção 8). A conciliação de estoque compara o **Kardex (MATR900)** com o **razão contábil de estoque (CTBR400)**, e **não** usa diretamente as NF-e da SEFAZ.

Implementado em `tools/estoque/calc_diferencas_estoque.py` (`calcular_diferencas_estoque`), bases normalizadas por `tools/estoque/kardex.py` e `tools/estoque/razao_estoque.py`.

### 7.1 Códigos de movimento

```
CODIGOS_ENTRADA = {"ENTRADAS", "DEV", "PR0", "DE0".."DE7"}
```

- Códigos de **entrada** (DE0–DE7, PR0, DEV, CFOPs < 5000) → comparados com **Débito** no razão.
- Códigos de **saída** (RE0–RE7, CFOPs >= 5000) → comparados com **Crédito** no razão.

### 7.2 Agrupamento e classificação por grupo (`codigo_movimento`)

```
diferenca     = valor_razao - valor_kardex
diferenca_abs = |diferenca|
status        = "CONCILIADO" se diferenca_abs <= 0.01, senão "DIVERGENTE"

origem:
- "SO_RAZAO"  se valor_kardex == 0
- "SO_KARDEX" se valor_razao == 0
- "AMBOS"     caso contrário
```

### 7.3 Matching individual (data + CF + valor)

Dentro de cada grupo (`codigo_movimento`), os registros são normalizados para um formato comum (`data`, `cf`, `valor`) e:

1. **Aglutinados** por `(data, cf)` somando valores.
2. Comparados Kardex × Razão. Diferenças `> 0.01` viram pendências `so_kardex` / `so_razao`.
3. **2ª passada**: tenta reconciliar pendências remanescentes por **valor aproximado** (mesmo `codigo_movimento`), ignorando data/CF — mitiga inconsistências de data no histórico.
4. **3ª passada (compensação por saldo)**: se ainda houver pendências dos dois lados mas o **total pendente bate** (`|total_so_kardex - total_so_razao| <= 0.01`), o grupo é considerado conciliado mesmo sem match individual exato.

### 7.4 Normalização de CF

- Para grupos `ENTRADAS`/`SAIDAS` (totais agregados), usa-se uma chave única de grupo (`"ENTRADAS"`/`"SAIDAS"`) — evita falso mismatch entre CFOP numérico do Kardex e código interno (DE/RE/PR) do razão.
- Para `CPV` e `DEV`, o matching **ignora o CF** (`_skip_cf_match`) e compara apenas por `(data, valor)`.
- Códigos internos (`DE[0-7]`, `RE[0-7]`, `PR0`, `CPV`, `DEV`) são preservados como estão; demais valores são reduzidos a apenas dígitos (CFOP).

### 7.5 Composição de diferenças (`_selecionar_registros_para_total`)

Quando uma pendência precisa ser "explicada" por múltiplos lançamentos, o sistema usa um algoritmo de **soma de subconjunto em centavos** (DP/programação dinâmica, com poda por proximidade ao alvo) para encontrar quais registros somam exatamente o valor da diferença (tolerância de 1 centavo).

---

## 8. Módulo de Estoque (Saldos e Fechamento)

> Cadastro de produtos, De-Para, importação de NF-e da SEFAZ e cálculo de saldo mensal. Detalhes funcionais em [DOCUMENTACAO_ESTOQUE.md](DOCUMENTACAO_ESTOQUE.md).

### 8.1 Fórmula do saldo (`services/estoque_service.py::apurar_saldo`)

```
saldo_final = saldo_inicial + entradas - saidas + ajustes
```

- `saldo_inicial` = `saldo_final` do **mês anterior** (0 se não existir registro).
- `entradas` = soma de `quantidade_convertida` dos itens de **NF-e de entrada** com `status == "autorizada"`, `vinculo_pendente == False`, filtrando por `data_emissao` dentro do mês.
- `saidas` = idem para **NF-e de saída**.
- `ajustes` = soma de `quantidade` das movimentações do tipo **ajuste** ou **estorno** no período (pode ser positiva ou negativa).
- Itens com **vínculo pendente** (sem De-Para resolvido) **não entram** no cálculo até serem vinculados.

### 8.2 Fechamento de período (`services/fechamento_service.py`)

- `fechar_periodo`: reapura todos os saldos do período (`reprocessar_periodo`) e marca `fechado = True` para cada produto. Se `saldo_final < 0`, gera um alerta `estoque_negativo` (se ainda não existir um aberto para o produto).
- `reabrir_periodo`: marca `fechado = False` e gera um alerta `periodo_reaberto`.
- `verificar_e_reabrir_se_necessario`: se uma nova NF-e for registrada num período **já fechado**, o período é **reaberto automaticamente** (alerta `periodo_reaberto` informando reabertura automática).
- **Job automático** (`job_fechar_mes_anterior`): roda no **dia 1 de cada mês**, fecha o **mês anterior** para todas as empresas com `status == True`. Falhas por empresa são silenciadas individualmente (não interrompem o job para as demais).

---

## 9. Pré-Conferência (CT2 × SFT)

> Cruzamento entre lançamentos contábeis (CT2/Razão) e o Livro Fiscal Eletrônico (SFT) de notas de entrada. Teoria completa em [PRE_CONFERENCIA_DADOS.md](../PRE_CONFERENCIA_DADOS.md).

Implementado em `services/pre_conferencia_service.py`.

### 9.1 Conceito

Cada NF de entrada deve gerar:
- Um lançamento contábil no **CT2** (débito na conta correspondente, identificado por **Lançamento Padrão — LP**).
- Um registro no **livro fiscal SFT** (identificado por **CFOP**).

Para cada **LP**, existe uma configuração (`lancamento_padrao_service`) que mapeia quais **CFOPs** do SFT correspondem àquele LP — opcionalmente agrupando vários LPs que devem ser somados antes da comparação.

### 9.2 Regra de data crítica

- **CT2**: usa a data do **lançamento contábil**.
- **SFT**: usa a data de **entrada da NF no sistema** (`FT_ENTRADA`), **não** a data de emissão (`FT_EMISSAO`). Usar `FT_EMISSAO` é a principal causa de notas "desaparecerem" do cruzamento (nota emitida em dezembro, mas que entra no sistema em janeiro).

### 9.3 Matching CT2 × SFT

- Match primário: **(filial, NF, fornecedor, valor ±0.01)** exato.
- Quando não há match exato, `_resolver_hist`/`_match_ct2_sft` tentam normalizar filial/NF/CNPJ-fornecedor e buscar candidatos por chave composta, incluindo cobertura "greedy" de múltiplos registros que somem o valor procurado.
- Status do LP: `"ok"` se `|diferenca| <= 0.01`, senão `"diferente"`.

### 9.4 Tipos de diferença

| Situação | Causa típica |
|----------|--------------|
| NF só no SFT | Nota recebida/registrada no fiscal, mas lançamento contábil não feito (ou feito em outro período) |
| NF só no CT2 | Débito contábil lançado, mas a nota não entrou no livro fiscal (recusa, cancelamento, erro de digitação) |
| Valores diferentes | NF existe nos dois lados com valores distintos (desconto posterior, erro de digitação, diferença de impostos) |

---

## 10. Normalização de Datas

### 10.1 CTBR480 (razão geral) — formato americano

O CTBR480 traz datas em **MM/DD/YYYY** (padrão americano). `pd.to_datetime(..., dayfirst=True)` retorna `NaT` para esse formato no pandas 2.x.

`_formatar_data` (`services/analise_diferencas_service.py`) tenta uma **lista explícita de formatos**, nesta ordem:
1. ISO (`YYYY-MM-DD`)
2. `%m/%d/%Y` (MM/DD — padrão do CTBR480)
3. `%d/%m/%Y` (DD/MM)
4. Outros formatos de fallback

Para datas ambíguas (ex.: `05/03/2024`), o sistema **prioriza MM/DD** por ser o padrão observado no CTBR480.

### 10.2 Conciliação de Estoque — chave de matching

`_normalizar_data_chave` (`tools/estoque/calc_diferencas_estoque.py`) converte qualquer formato reconhecido (já em `DD/MM/YYYY`, ISO `YYYY-MM-DD`, ou demais com `dayfirst=True`) para **`DD/MM/YYYY`**, usado como chave de agrupamento/matching. Se nada for reconhecido, tenta extrair a primeira ocorrência de `DD/MM/YYYY` no texto via regex.

### 10.3 Conciliação Bancária

`_normalizar_data_coluna` (`tools/banco/calc_diferencas_banco.py`) converte a coluna `data` com `pd.to_datetime(dayfirst=True)` e formata como `DD/MM/YYYY` antes do agrupamento por dia.

---

## 11. Correção de Header de Relatórios

Função: `corrigir_header_titulo` (`tools/financeiro/base.py`)

### Problema

Arquivos Excel exportados com **título na linha 1** (ex.: "Títulos a Pagar", "Razão Geral") fazem com que o XLSX.js (frontend) leia a linha de título como cabeçalho, gerando colunas genéricas:
- Coluna 0: o próprio título (ex.: `titulos_a_pagar`)
- Demais colunas: `__EMPTY`, `__EMPTY_1`, `__EMPTY_2`, ... (padrão XLSX.js para células de header vazias)

### Regra de detecção e correção

Pattern de coluna genérica: `r'^(_+empty(_\d+)?|empty(_\d+)?|nan(\d+)?|unnamed.*|_\d+)$'` (case-insensitive) — cobre `__EMPTY`/`__EMPTY_1` (XLSX.js), `empty`/`empty_1` (pandas), `nan`/`nanN`, `unnamed...`, `_N`.

A correção só é aplicada quando:
1. **Mais de 50%** das colunas batem no padrão genérico, **e**
2. A **primeira linha de dados** contém nomes reais de coluna (≥ 30% das células não vazias).

Quando ambas condições são satisfeitas, a primeira linha vira o cabeçalho real e é removida dos dados.

### Onde é aplicado

| Base | Aplicação |
|------|-----------|
| FINR130 / FINR150 (financeiro) | Dentro de `carregar_dados()` e novamente antes de `validar_layout_planilha` em `conciliacao_service.py` |
| CTBR480 (razão geral) | Aplicado explicitamente em `conciliacao_service.py` |
| CTBR140 (contábil filtrado) | **Não aplicado** — esse relatório não tem linha de título no padrão observado |

### Colunas do CTBR480 após correção e normalização

```
Brutas:  DATA, LOTE/SUB/DOC/LINHA, HISTORICO, XPARTIDA, C CUSTO, ITEM CONTA, COD CL VAL, DEBITO, CREDITO, SALDO ATUAL
Normalizadas: data, lote_sub_doc_linha, historico, xpartida, c_custo, item_conta, cod_cl_val, debito, credito, saldo_atual
```
