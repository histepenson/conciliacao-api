# Smart Conciliações — Documentação do Módulo de Estoque

> Última atualização: Maio 2026

---

## Índice

1. [Visão Geral do Módulo](#1-visão-geral-do-módulo)
2. [Cadastro de Produtos](#2-cadastro-de-produtos)
3. [De-Para (Vínculo Produto x Fornecedor)](#3-de-para-vínculo-produto-x-fornecedor)
4. [Certificado Digital](#4-certificado-digital)
5. [Importação de NF-e (SEFAZ)](#5-importação-de-nf-e-sefaz)
6. [Vínculo de Itens com Produtos](#6-vínculo-de-itens-com-produtos)
7. [Saldos de Estoque](#7-saldos-de-estoque)
8. [Movimentações](#8-movimentações)
9. [Ajuste Manual](#9-ajuste-manual)
10. [Fechamento de Períodos](#10-fechamento-de-períodos)
11. [Relatórios e Exportação](#11-relatórios-e-exportação)
12. [Alertas Automáticos](#12-alertas-automáticos)
13. [Fluxo Recomendado](#13-fluxo-recomendado)
14. [Glossário](#14-glossário)

---

## 1. Visão Geral do Módulo

O módulo de estoque controla o **saldo de produtos** com base nas notas fiscais eletrônicas (NF-e) obtidas diretamente da **SEFAZ**. O sistema:

- Importa NF-e de entrada e saída automaticamente via certificado digital A1 (PFX)
- Calcula automaticamente as entradas, saídas e saldo por produto e período
- Permite ajustes manuais justificados
- Fecha períodos para impedir alterações retroativas
- Gera relatórios em Excel e PDF
- Dispara alertas para situações como saldo negativo ou itens sem vínculo

**Fórmula do saldo:**
```
Saldo Final = Saldo Inicial (mês anterior) + Entradas − Saídas + Ajustes
```

---

## 2. Cadastro de Produtos

**Onde:** `Estoque > Produtos`

Antes de importar NF-e, os produtos devem estar cadastrados no sistema.

### Criar produto

1. Clique em **"Novo Produto"**.
2. Preencha os campos:

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| Código Interno | Sim | Código único do produto na empresa |
| Descrição | Sim | Nome do produto |
| NCM | Não | Nomenclatura Comum do Mercosul |
| Unidade de Estoque | Sim | Unidade de medida (ex.: UN, KG, CX) |
| Ativo | Sim | Define se o produto está em uso |

3. Clique em **"Salvar"**.

> O código interno deve ser único por empresa.

### Editar / Inativar produto

Use os ícones na linha do produto. Inativar um produto não exclui seu histórico de movimentações — ele apenas deixa de aparecer nos filtros de novos lançamentos.

---

## 3. De-Para (Vínculo Produto x Fornecedor)

**Onde:** `Estoque > De-Para`

Os itens das NF-e vêm com o código do produto **do fornecedor**, que pode ser diferente do código interno da empresa. O De-Para faz essa tradução automaticamente.

### Criar vínculo

1. Clique em **"Novo Vínculo"**.
2. Preencha:

| Campo | Descrição |
|-------|-----------|
| Produto | Produto cadastrado no sistema (código interno) |
| CNPJ do Fornecedor | CNPJ do emitente da NF-e |
| Código do Produto no Fornecedor | Como o fornecedor chama este produto |
| Fator de Conversão | Número para converter a quantidade (ex.: 12 — se o fornecedor vende em caixas de 12 unidades) |
| Operação de Conversão | Multiplicar ou dividir o fator |

3. Clique em **"Salvar"**.

### Como funciona na prática

Quando uma NF-e é importada, o sistema procura o CNPJ do fornecedor e o código do produto nos vínculos cadastrados:

- **Se encontrar:** vincula automaticamente ao produto interno e converte a quantidade.
- **Se não encontrar:** marca o item como "vínculo pendente" e exige vinculação manual.

**Exemplo de conversão:**
- Fornecedor vende produto "ABC" em caixas de 12 unidades
- Fator: 12, operação: multiplicar
- NF-e vem com quantidade 5 (caixas) → sistema converte para 60 (unidades)

---

## 4. Certificado Digital

**Onde:** `Cadastros > Empresas` (ícone de certificado na linha da empresa)

O certificado digital A1 (arquivo `.pfx`) é necessário para acessar a SEFAZ e baixar as NF-e automaticamente.

### Cadastrar certificado

1. Na listagem de empresas, clique no ícone de certificado da empresa desejada.
2. Clique em **"Upload de Certificado"**.
3. Selecione o arquivo `.pfx`.
4. Informe a **senha do certificado**.
5. Clique em **"Salvar"**.

> O certificado é armazenado de forma segura e criptografada. A senha não fica visível após o cadastro.

### Validade do certificado

Certificados A1 têm validade de 1 a 3 anos. O sistema exibirá um alerta quando a validade estiver próxima do vencimento. Renove o certificado junto à Autoridade Certificadora (AC) antes do vencimento.

---

## 5. Importação de NF-e (SEFAZ)

**Onde:** `Estoque > Importar NF-e`

### Iniciar importação

1. Selecione a **empresa** (deve ter certificado cadastrado).
2. Informe o **CNPJ do certificado** (preenchido automaticamente se houver apenas um).
3. Defina o **período**: data de início e data de fim.
4. Clique em **"Iniciar Importação"**.

> A importação é **assíncrona** — o sistema envia a solicitação à SEFAZ e processa em segundo plano. Um indicador de progresso é exibido enquanto aguarda.

### O que é importado

| Tipo | Descrição |
|------|-----------|
| NF-e de Entrada | Notas em que a empresa é destinatária |
| NF-e de Saída | Notas em que a empresa é emitente |

Para cada nota, o sistema importa:
- Dados da nota (chave de acesso, número, série, data, fornecedor/cliente, valor total)
- Todos os itens (código, descrição, NCM, CFOP, quantidade, valor unitário)

### Vínculo automático

Após a importação, o sistema tenta vincular cada item ao produto interno via De-Para:
- **Vínculo automático bem-sucedido:** o item já é processado no saldo.
- **Vínculo pendente:** o item aguarda vinculação manual (ver [seção 6](#6-vínculo-de-itens-com-produtos)).

### Notas já importadas

O sistema não importa a mesma NF-e duas vezes (controle por chave de acesso). Se uma nota já existir, ela será ignorada na reimportação.

---

## 6. Vínculo de Itens com Produtos

**Onde:** `Estoque > Importar NF-e` (abas "Entrada" e "Saída")

Itens com **"Vínculo Pendente"** precisam ser vinculados manualmente ao produto interno.

### Vincular um item

1. Na aba correspondente (Entrada ou Saída), localize o item com status "Pendente".
2. Clique no ícone de vínculo na linha do item.
3. Na janela que abrir, selecione o produto interno correspondente.
4. Confirme.

> Após vincular, o sistema recalcula automaticamente a quantidade convertida com base no De-Para e atualiza o saldo do período.

### Criar De-Para durante o vínculo

Se o item não tiver De-Para cadastrado, o sistema oferece a opção de criá-lo no momento do vínculo, evitando que itens do mesmo fornecedor precisem ser vinculados manualmente novamente no futuro.

### Reprocessar nota

Se os vínculos do De-Para foram atualizados após a importação, é possível **reprocessar** uma nota para refazer os vínculos automáticos:

1. Clique no ícone de reprocessamento na linha da nota.
2. O sistema tentará vincular automaticamente os itens pendentes com base nos De-Para atuais.

---

## 7. Saldos de Estoque

**Onde:** `Estoque > Saldos`

Exibe o **saldo atual por produto** para o período selecionado.

### Visualizar saldos

1. Selecione a **empresa** e o **período** (mês/ano).
2. A tabela exibe todos os produtos com suas quantidades.

| Coluna | Descrição |
|--------|-----------|
| Produto | Código interno e descrição |
| Saldo Inicial | Saldo do final do mês anterior |
| Entradas | Total de entradas do período (NF-e de entrada) |
| Saídas | Total de saídas do período (NF-e de saída) |
| Ajustes | Somatório de ajustes manuais |
| Saldo Final | Saldo Inicial + Entradas − Saídas + Ajustes |
| Status | Aberto / Fechado |

### Reprocessar período

Se houver novos vínculos ou importações após o cálculo, use **"Reprocessar"** para recalcular todos os saldos do período do zero.

> Reprocessar um período **fechado** não é permitido. Reabra o período antes.

---

## 8. Movimentações

**Onde:** `Estoque > Movimentações`

Lista o **histórico detalhado de movimentações** de um produto.

### Filtros disponíveis

| Filtro | Opções |
|--------|--------|
| Empresa | Seletor |
| Produto | Busca por código ou descrição |
| Período | Mês/ano |
| Tipo | Entrada / Saída / Ajuste / Estorno |

### Tipos de movimentação

| Tipo | Origem | Efeito no saldo |
|------|--------|-----------------|
| Entrada | NF-e de entrada importada | Aumenta o saldo |
| Saída | NF-e de saída importada | Diminui o saldo |
| Ajuste | Registrado manualmente | Pode aumentar ou diminuir |
| Estorno | Cancelamento de NF-e | Reverte a movimentação original |

---

## 9. Ajuste Manual

**Onde:** `Estoque > Saldos` → botão "Ajuste Manual"

Permite corrigir o saldo de um produto sem emitir NF-e. Exemplos de uso: perda, avaria, diferença de inventário físico.

### Registrar ajuste

1. Na tela de Saldos, clique em **"Ajuste Manual"**.
2. Na janela que abrir, preencha:

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| Produto | Sim | Produto a ser ajustado |
| Quantidade | Sim | Positivo para aumentar, negativo para diminuir |
| Data | Sim | Data do ajuste |
| Justificativa | Sim | Motivo do ajuste (campo obrigatório para auditoria) |

3. Clique em **"Confirmar"**.

> O ajuste é registrado como uma movimentação do tipo "Ajuste" e o saldo é atualizado imediatamente.

---

## 10. Fechamento de Períodos

**Onde:** `Estoque > Fechamento`

O fechamento de período **bloqueia alterações** nas movimentações do mês, garantindo a integridade dos dados.

### Fechar período

1. Selecione a **empresa** e o **período** a ser fechado.
2. Clique em **"Fechar Período"**.
3. Confirme a operação.

Após o fechamento:
- Novas importações de NF-e desse período continuam sendo aceitas mas **não alteram o saldo fechado**.
- Ajustes manuais **não são permitidos**.
- O saldo final torna-se o **saldo inicial** do próximo mês.

### Reabrir período

Se necessário corrigir dados após o fechamento:

1. Localize o período na lista.
2. Clique em **"Reabrir"**.
3. Confirme a operação.

> Reabrir um período anula o bloqueio. Use com cautela — pode impactar o encadeamento de saldos dos meses seguintes.

### Fechamento automático

O sistema fecha automaticamente o período do mês anterior no **dia 01 de cada mês às 02:00**. Esse comportamento pode ser desativado pelo administrador.

### Status de fechamentos

A tela exibe o status de todos os meses do ano:

| Status | Significado |
|--------|-------------|
| Aberto | Período em edição, aceita alterações |
| Fechado | Período bloqueado, dados imutáveis |

---

## 11. Relatórios e Exportação

**Onde:** Botão de exportação nas telas de Saldos e Movimentações.

| Relatório | Formato | O que contém |
|-----------|---------|--------------|
| Saldos por Período | Excel (.xlsx) | Todos os produtos com entradas, saídas, ajustes e saldo final |
| Saldos por Período | PDF | Versão formatada para impressão |
| Movimentações | Excel (.xlsx) | Histórico detalhado de movimentações com filtros aplicados |
| Movimentações | PDF | Versão formatada para impressão |

---

## 12. Alertas Automáticos

**Onde:** Dashboard e `Estoque > Importar NF-e` (aba Alertas)

O sistema gera alertas automáticos nas seguintes situações:

| Tipo de Alerta | Quando ocorre |
|----------------|---------------|
| Saldo Negativo | Saldo final calculado é menor que zero |
| Diferença NF-e | Quantidade calculada difere da quantidade da NF-e |
| Vínculo Pendente | Itens de NF-e sem produto vinculado |

### Resolver alerta

1. Acesse a aba **"Alertas"** na tela de Importar NF-e.
2. Verifique o motivo do alerta.
3. Corrija o problema (vincule o item, faça ajuste, etc.).
4. Clique em **"Resolver"** para marcar o alerta como tratado.

---

## 13. Fluxo Recomendado

Para cada novo período (mês), siga esta sequência:

```
1. Verificar produtos
   └─ Estoque > Produtos: checar se novos produtos precisam ser cadastrados

         ↓

2. Verificar De-Para
   └─ Estoque > De-Para: checar se há novos fornecedores ou códigos

         ↓

3. Importar NF-e
   └─ Estoque > Importar NF-e: importar o período desejado

         ↓

4. Vincular itens pendentes
   └─ Aba Entrada e Saída: resolver itens com "Vínculo Pendente"

         ↓

5. Verificar alertas
   └─ Aba Alertas: resolver saldo negativo ou diferenças

         ↓

6. Revisar saldos
   └─ Estoque > Saldos: conferir os totais de cada produto

         ↓

7. Fazer ajustes (se necessário)
   └─ Estoque > Saldos > Ajuste Manual

         ↓

8. Fechar período
   └─ Estoque > Fechamento: fechar o mês após conferência
```

---

## 14. Glossário

| Termo | Definição |
|-------|-----------|
| **NF-e** | Nota Fiscal Eletrônica |
| **SEFAZ** | Secretaria da Fazenda — autoriza e armazena as NF-e |
| **Certificado Digital A1** | Arquivo `.pfx` com chave criptográfica para autenticação na SEFAZ |
| **De-Para** | Tabela de equivalência entre o código do produto no fornecedor e o código interno da empresa |
| **Chave de Acesso** | Código de 44 dígitos que identifica unicamente uma NF-e |
| **Vínculo Pendente** | Item de NF-e sem produto interno associado |
| **Saldo Inicial** | Saldo final do período imediatamente anterior |
| **Entradas** | Total de quantidade recebida no período (NF-e de entrada) |
| **Saídas** | Total de quantidade enviada no período (NF-e de saída) |
| **Ajuste** | Movimentação manual para corrigir saldo sem NF-e |
| **Estorno** | Reversão automática gerada pelo cancelamento de uma NF-e |
| **Fechamento** | Bloqueio do período para impedir alterações retroativas |
| **Período** | Mês e ano de referência (ex.: Janeiro/2026) |
| **NCM** | Nomenclatura Comum do Mercosul — classificação fiscal do produto |
| **CFOP** | Código Fiscal de Operações e Prestações — define a natureza da operação na NF-e |
| **Fator de Conversão** | Número usado para converter a unidade do fornecedor para a unidade interna |
| **Reprocessar** | Recalcular os saldos do período do zero com base nas movimentações atuais |
