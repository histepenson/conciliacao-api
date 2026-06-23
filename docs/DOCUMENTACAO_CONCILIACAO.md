# Smart Conciliações — Documentação do Módulo de Conciliação

> Última atualização: Junho 2026
>
> Para as regras de cálculo, classificação e thresholds usados internamente, veja [REGRAS_NEGOCIO.md](REGRAS_NEGOCIO.md).

---

## Índice

1. [O que é Conciliação?](#1-o-que-é-conciliação)
2. [Tipos de Conciliação](#2-tipos-de-conciliação)
3. [Fluxo Geral](#3-fluxo-geral)
4. [Passo 1 — Selecionar Período](#4-passo-1--selecionar-período)
5. [Passo 2 — Configurar as Fontes de Dados](#5-passo-2--configurar-as-fontes-de-dados)
6. [Passo 3 — Processar a Conciliação](#6-passo-3--processar-a-conciliação)
7. [Passo 4 — Analisar o Resultado](#7-passo-4--analisar-o-resultado)
8. [Passo 5 — Efetivar a Conciliação](#8-passo-5--efetivar-a-conciliação)
9. [Acompanhamento de Conciliações Efetivadas](#9-acompanhamento-de-conciliações-efetivadas)
10. [Parâmetros da API Protheus](#10-parâmetros-da-api-protheus)
11. [Conciliação Bancária](#11-conciliação-bancária)
12. [Conciliação de Estoque](#12-conciliação-de-estoque)
13. [Exportação de Resultados](#13-exportação-de-resultados)
14. [Glossário](#14-glossário)

---

## 1. O que é Conciliação?

A conciliação contábil é o processo de **comparar dois conjuntos de dados** — normalmente o saldo registrado no sistema financeiro (origem) e o saldo registrado na contabilidade — para identificar se estão em conformidade ou se existem divergências a serem explicadas e corrigidas.

O sistema compara automaticamente os registros e classifica cada item como:

| Situação | Significado |
|----------|-------------|
| ✅ Conciliado | Valores iguais (diferença ≤ R$ 0,01) |
| 🔴 Financeiro > Contabilidade | Valor na origem é maior que no contábil |
| 🔴 Contabilidade > Financeiro | Valor no contábil é maior que na origem |
| ⚠️ Só no Financeiro | Código existe apenas na origem, não na contabilidade |
| ⚠️ Só na Contabilidade | Código existe apenas na contabilidade, não na origem |

---

## 2. Tipos de Conciliação

| Tipo | Menu | Bases de dados utilizadas |
|------|------|--------------------------|
| **A Receber** | Conciliações > A Receber | FINR130 (origem) + CTBR140 (contábil filtrado) + CTBR480 (razão geral) |
| **A Pagar** | Conciliações > A Pagar | FINR150 (origem) + CTBR140 (contábil filtrado) + CTBR480 (razão geral) |
| **Bancária** | Conciliações > Bancária | FINR470 (extrato bancário) + razão contábil |
| **Estoque** | Conciliações > Estoque | MATR900 (kardex) + saldos de NF-e |

---

## 3. Fluxo Geral

```
1. Selecionar Período
   └─ Empresa + Data-base (último dia do mês) + Conta Contábil + Tipo
         │
         ▼
2. Configurar Fontes de Dados
   └─ Para cada base: informar parâmetros da API Protheus
      OU carregar arquivo Excel localmente
         │
         ▼
3. Processar
   └─ Sistema busca os dados no Protheus (via API),
      normaliza, faz o merge e calcula as diferenças
         │
         ▼
4. Analisar Resultado
   └─ Resumo + tabela de diferenças + análise detalhada por código
         │
         ▼
5. Efetivar (opcional)
   └─ Registra o resultado no histórico para auditoria futura
```

---

## 4. Passo 1 — Selecionar Período

**Onde:** `Conciliações > Selecionar Período`

1. Selecione a **Empresa**.
2. Informe a **Data-base**: deve ser sempre o **último dia do mês** (ex.: 31/01/2026).
   > O sistema valida automaticamente e alerta se a data não for o último dia do mês.
3. Escolha a **Conta Contábil** que será conciliada. A lista exibe apenas contas marcadas como "Conciliável" no plano de contas da empresa.
4. Clique em **Avançar** e selecione o **tipo de conciliação** (A Receber, A Pagar, Bancária ou Estoque).
5. O sistema abrirá a tela de conciliação correspondente ao tipo escolhido.

---

## 5. Passo 2 — Configurar as Fontes de Dados

A conciliação financeira utiliza **três bases de dados**. Para cada uma, o sistema oferece duas formas de obter os dados:

| Base | Relatório Protheus | O que contém |
|------|-------------------|--------------|
| **Origem (Financeiro)** | FINR130 (A Receber) ou FINR150 (A Pagar) | Posição dos títulos financeiros por cliente/fornecedor |
| **Contábil Filtrado** | CTBR140 — Balancete | Saldo contábil filtrado pela conta que está sendo conciliada |
| **Contábil Geral (Razão)** | CTBR480 — Razão Geral | Todos os lançamentos contábeis da conta, para análise detalhada |

### Forma 1 — Busca automática via API Protheus (recomendada)

O sistema busca os dados diretamente do Protheus sem necessidade de exportar arquivos.

1. Clique em **"Parâmetros Protheus"** (ou ícone de engrenagem) ao lado da base desejada.
2. Preencha os parâmetros do relatório (período, conta, filial, etc.).
3. Confirme. Os dados serão buscados automaticamente no momento em que você processar a conciliação.

> Veja todos os parâmetros disponíveis na [seção 10](#10-parâmetros-da-api-protheus).

### Forma 2 — Carregar arquivo Excel localmente (alternativa)

Caso a integração com o Protheus não esteja disponível ou você precise usar uma extração específica:

1. Exporte o relatório correspondente do Protheus em formato Excel (`.xlsx`).
2. Clique na área de carregamento da base ou arraste o arquivo para ela.
3. O sistema lê o arquivo **localmente no seu computador** e prepara os dados para o processamento.

> Formatos aceitos: `.xlsx`, `.xls`, `.csv` — tamanho máximo: **50 MB**.

---

## 6. Passo 3 — Processar a Conciliação

Após configurar as três bases de dados, clique em **"Processar Conciliação"**.

O sistema irá:
1. Para cada base configurada via API: buscar os dados no Protheus em tempo real
2. Normalizar os dados de todas as bases
3. Padronizar os códigos de cliente/fornecedor para o cruzamento
4. Fazer o merge entre financeiro e contábil
5. Calcular as diferenças (valor absoluto, percentual e classificação)
6. Buscar os lançamentos individuais no razão geral para análise detalhada

> O processamento pode levar alguns segundos a mais quando os dados são buscados da API Protheus, dependendo do volume de registros e da latência de rede com o servidor Protheus.

---

## 7. Passo 4 — Analisar o Resultado

Após o processamento, a tela exibe o resultado em três seções:

### 7.1 Resumo Geral

Cards com os totais:

| Card | O que mostra |
|------|-------------|
| Total de registros | Quantidade total após o cruzamento |
| Conciliados | Registros com diferença ≤ R$ 0,01 |
| Com divergência | Registros fora do threshold |
| Taxa de sucesso | % conciliados sobre o total |

### 7.2 Tabela de Diferenças

Tabela paginada (10/20/50/100 itens) com todos os registros e os valores de cada base:

| Coluna | Descrição |
|--------|-----------|
| Código | Código do cliente/fornecedor |
| Cliente/Fornecedor | Nome |
| Valor Financeiro | Saldo no sistema financeiro |
| Valor Contábil | Saldo no razão contábil |
| Diferença | Contábil − Financeiro |
| Diferença % | Percentual sobre o financeiro |
| Tipo | Classificação da diferença |
| Origem | Ambos / Só Financeiro / Só Contabilidade |

**Filtros disponíveis:**
- Busca por código ou nome
- Status: OK (conciliado) / Com Diferença
- Origem: Ambos / Só Financeiro / Só Contabilidade
- Ordenação por qualquer coluna

### 7.3 Análise Detalhada

Para cada código com divergência, o sistema exibe os **lançamentos individuais** encontrados no razão geral (CTBR480), permitindo identificar exatamente quais lançamentos causam a diferença.

Cada item da análise mostra:
- Data do lançamento
- Histórico
- Débito / Crédito / Saldo Atual
- Status: **verde** (conciliado) ou **vermelho** (divergente)
- Tipo: `CONCILIADO`, `SÓ FINANCEIRO`, `SÓ CONTABILIDADE`, `DIVERGENTE_VALOR`

---

## 8. Passo 5 — Efetivar a Conciliação

Efetivar significa **registrar oficialmente** o resultado da conciliação no histórico do sistema para fins de auditoria.

1. Após analisar o resultado e verificar que está correto, clique em **"Efetivar Conciliação"**.
2. Confirme a operação no dialog de confirmação.
3. O sistema salva o resultado com data, hora, usuário e empresa.

> **Atenção:** Por padrão, o sistema só permite efetivar conciliações **sem divergências**. Se a empresa estiver configurada para permitir efetivação com divergências, um alerta será exibido antes da confirmação.

### Exclusão de efetivação

Uma efetivação pode ser excluída pelo administrador em `Conciliações > Acompanhamento`. A exclusão remove permanentemente o registro do histórico.

---

## 9. Acompanhamento de Conciliações Efetivadas

**Onde:** `Conciliações > Acompanhamento`

Lista todas as conciliações efetivadas da empresa, ordenadas por data. Para cada registro é possível:

- Ver o **detalhe** completo (todos os dados do resultado)
- Fazer o **download** dos arquivos gerados (Excel com as diferenças)
- **Excluir** o registro (somente administradores)

### Filtros disponíveis

- Por conta contábil
- Por período (data-base)
- Por tipo de conciliação

---

## 10. Parâmetros da API Protheus

O sistema se conecta diretamente ao Protheus para buscar os dados de cada base. A URL e as credenciais são configuradas pelo administrador. Abaixo estão os parâmetros disponíveis em cada dialog de configuração.

### CTBR140 — Balancete Contábil

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| Data Fim | ✅ Sim | Data de fechamento do período (formato YYYYMMDD) |
| Data Início | Não | Data de abertura (padrão: 01/01 do ano da Data Fim) |
| Conta De / Conta Até | Não | Intervalo de contas contábeis |
| Item De / Item Até | Não | Intervalo de itens/centros de custo |
| Incluir Valores Zerados | Não | Se marcado, inclui contas com saldo zero |
| Moeda | Não | Código da moeda (padrão: 1) |
| Considerar Filiais | Não | Incluir todas as filiais ou apenas a corrente |
| Filial De / Filial Até | Não | Intervalo de filiais (quando considera filiais) |

### CTBR480 — Razão Geral

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| Data Fim | ✅ Sim | Data de fechamento do período (formato YYYYMMDD) |
| Data Início | Não | Data de abertura |
| Conta De / Conta Até | Não | Intervalo de contas contábeis |
| Item De / Item Até | Não | Intervalo de itens contábeis |
| Centro de Custo De / Até | Não | Intervalo de centros de custo |
| Classe de Valor De / Até | Não | Intervalo de classes de valor |
| Moeda | Não | Código da moeda (padrão: 1) |
| Incluir Valores Zerados | Não | Se marcado, inclui registros com saldo zero |
| Considerar Filiais | Não | Incluir todas as filiais ou apenas a corrente |

### FINR130 — Títulos a Receber / FINR150 — Títulos a Pagar

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| Data Fim | ✅ Sim | Data de posição dos títulos |
| Data Início | Não | Data inicial do filtro |
| Cliente/Fornecedor De / Até | Não | Intervalo de clientes ou fornecedores |
| Loja De / Até | Não | Intervalo de lojas |

### FINR470 — Extrato Bancário (Conciliação Bancária)

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| Data Fim | ✅ Sim | Data final do extrato |
| Data Início | Não | Data inicial do extrato |
| Banco / Agência / Conta | Não | Filtros bancários |

> **Dica:** Se precisar sobrescrever a URL do Protheus configurada pelo administrador (ex.: para apontar para um ambiente de homologação), informe a URL diretamente no campo "URL Protheus" disponível em cada dialog.

---

## 11. Conciliação Bancária

**Onde:** `Conciliações > Bancária`

Compara o extrato bancário (FINR470) com o razão contábil da conta bancária.

O fluxo é o mesmo da conciliação financeira:
1. Selecione o período e a conta bancária
2. Configure os parâmetros do FINR470 (API Protheus) ou carregue o arquivo Excel localmente
3. Configure o razão contábil correspondente
4. Processe e analise as diferenças
5. Efetive se correto

O resultado identifica lançamentos que estão no extrato mas não na contabilidade (e vice-versa).

---

## 12. Conciliação de Estoque

**Onde:** `Conciliações > Estoque`

Compara o **Kardex físico-financeiro (MATR900)** com o **razão contábil de estoque (CTBR400)**, agrupando os movimentos por **código de movimento** (entradas DE0–DE7/PR0/DEV vs. saídas RE0–RE7) e fazendo matching individual por data, CF/CFOP e valor.

O sistema verifica:
- Se o total de cada grupo de movimento bate entre Kardex e Razão (entradas = débito, saídas = crédito)
- Quais lançamentos existem só no Kardex ou só no Razão dentro de cada grupo
- Se a soma das pendências dos dois lados se compensa (mesmo sem match individual exato)

> Esta conciliação **não** usa diretamente as NF-e da SEFAZ — ela compara o Kardex do Protheus com o razão contábil. As regras detalhadas estão em [REGRAS_NEGOCIO.md](REGRAS_NEGOCIO.md#7-conciliação-de-estoque-kardex--razão-ctbr400). Para o módulo de cadastro/saldos de estoque baseado em NF-e, veja [DOCUMENTACAO_ESTOQUE.md](DOCUMENTACAO_ESTOQUE.md).

---

## 13. Exportação de Resultados

Na tela de resultado, estão disponíveis as seguintes opções de exportação:

| Opção | Formato | O que exporta |
|-------|---------|---------------|
| Exportar CSV | `.csv` | Tabela de diferenças completa |
| Download Excel | `.xlsx` | Arquivo com 5 abas: Total, Com Diferenças, Só Financeiro, Só Contabilidade, Resumo |

O arquivo Excel contém formatação com cores para facilitar a análise:
- Verde: registros conciliados
- Vermelho: registros com divergência
- Amarelo: registros exclusivos (só em uma das bases)

---

## 14. Glossário

| Termo | Definição |
|-------|-----------|
| **Conciliação** | Processo de comparar dois conjuntos de dados para verificar conformidade |
| **Efetivar** | Registrar oficialmente o resultado no histórico do sistema |
| **Threshold** | Valor mínimo de diferença considerado relevante (padrão: R$ 0,01) |
| **Origem** | Base financeira (FINR130/FINR150) |
| **Contábil Filtrado** | Balancete contábil da conta específica (CTBR140) |
| **Razão Geral** | Todos os lançamentos contábeis da conta (CTBR480) |
| **FINR130** | Relatório Protheus de posição de títulos a receber |
| **FINR150** | Relatório Protheus de posição de títulos a pagar |
| **CTBR140** | Relatório Protheus de balancete contábil analítico por conta/item |
| **CTBR480** | Relatório Protheus de razão geral por item |
| **FINR470** | Relatório Protheus de extrato bancário |
| **MATR900** | Relatório Protheus de kardex físico-financeiro |
| **Data-base** | Último dia do mês de referência da conciliação |
| **Merge** | Cruzamento dos registros das duas bases pelo código do cliente/fornecedor |
| **SO_FINANCEIRO** | Código encontrado apenas na base financeira |
| **SO_CONTABILIDADE** | Código encontrado apenas na base contábil |
| **DIVERGENTE_VALOR** | Código encontrado nas duas bases mas com valores diferentes |
| **CONCILIADO** | Código com diferença ≤ R$ 0,01 entre as bases |
| **API Protheus** | Integração direta com o servidor Protheus para busca automática dos dados |
