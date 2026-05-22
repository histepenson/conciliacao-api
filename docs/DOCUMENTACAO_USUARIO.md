# Smart Conciliações — Documentação do Usuário

> Versão do sistema: 1.0 | Última atualização: Maio 2026

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Acesso ao Sistema](#2-acesso-ao-sistema)
3. [Layout e Navegação](#3-layout-e-navegação)
4. [Dashboard](#4-dashboard)
5. [Cadastros](#5-cadastros)
   - [Empresas](#51-empresas)
   - [Plano de Contas](#52-plano-de-contas)
6. [Módulo de Conciliação](#6-módulo-de-conciliação)
7. [Módulo de Estoque](#7-módulo-de-estoque)
8. [Área Administrativa](#8-área-administrativa)
9. [Atalhos de Teclado](#9-atalhos-de-teclado)
10. [Dúvidas Frequentes](#10-dúvidas-frequentes)

---

## 1. Visão Geral

O **Smart Conciliações** é um sistema para conciliação contábil, financeira e de estoque. Ele permite comparar os saldos registrados nos sistemas financeiro e contábil (incluindo dados exportados do Protheus), identificar divergências e registrar o resultado da conciliação de forma organizada e auditável.

**Principais funcionalidades:**

| Módulo | O que faz |
|--------|-----------|
| Conciliação Financeira | Compara títulos a receber/pagar com o razão contábil |
| Conciliação Bancária | Compara extrato bancário com o razão contábil |
| Conciliação de Estoque | Compara saldos do Kardex com as NF-e |
| Estoque | Controla entradas, saídas, ajustes e fechamento de períodos |
| Cadastros | Gerencia empresas e plano de contas |
| Admin | Cria e gerencia usuários e perfis de acesso |

---

## 2. Acesso ao Sistema

### 2.1 Login

Acesse a URL do sistema no navegador e informe seu **e-mail** e **senha**.

- Usuários administradores entram diretamente no **Dashboard**.
- Usuários comuns vinculados a mais de uma empresa verão a tela de **Seleção de Empresa** antes do Dashboard.

### 2.2 Selecionar Empresa

Caso você tenha acesso a mais de uma empresa, escolha a empresa desejada na tela de seleção. Somente dados da empresa selecionada serão exibidos. Para trocar de empresa, faça logout e entre novamente.

### 2.3 Esqueci minha senha

Na tela de login, clique em **"Esqueci minha senha"**. Informe o e-mail cadastrado e você receberá um link para redefinição. O link é válido por **30 minutos**.

### 2.4 Logout

Clique no seu nome no canto inferior da barra lateral e selecione **Sair**, ou acesse `/sair` diretamente.

---

## 3. Layout e Navegação

O sistema possui uma **barra lateral (sidebar)** à esquerda com todos os menus. Ela pode ser recolhida clicando no ícone de menu ou pressionando `Ctrl+B`.

### Menus Disponíveis

| Menu | Submenu | Descrição |
|------|---------|-----------|
| Dashboard | — | Resumo e métricas |
| Conciliações | Selecionar Período | Escolher empresa, período e conta |
| | A Receber | Conciliação de contas a receber |
| | A Pagar | Conciliação de contas a pagar |
| | Bancária | Conciliação bancária |
| | Estoque | Conciliação de estoque |
| | Acompanhamento | Histórico de conciliações efetivadas |
| Estoque | Produtos | Cadastro de produtos |
| | De-Para | Vínculo produto x fornecedor |
| | Importar NF-e | Importação de notas fiscais |
| | Saldos | Saldos por período |
| | Movimentações | Histórico de movimentações |
| | Fechamento | Fechar/reabrir períodos |
| Cadastros | Empresas | CRUD de empresas |
| | Plano de Contas | CRUD e importação do plano |
| Admin | Usuários | Gerenciar usuários (somente admin) |
| | Empresas | Gerenciar empresas (somente admin) |
| | Perfis | Gerenciar perfis de acesso (somente admin) |

---

## 4. Dashboard

O Dashboard exibe um **resumo geral** da empresa selecionada:

- **Total de contas** no plano de contas
- **Contas conciliadas** no período atual
- **Contas pendentes** de conciliação
- **Taxa de sucesso** (% conciliadas)
- **Gráfico de conciliações por mês** (últimos 6 meses)
- **Últimas conciliações** com links para detalhes
- **Alertas e pendências** (ex.: itens de estoque sem vínculo)
- **Ações rápidas:** Nova Conciliação, Ver Fechamentos, Plano de Contas

> Administradores visualizam dados de todas as empresas e podem usar o seletor de empresa no topo da página.

---

## 5. Cadastros

### 5.1 Empresas

**Onde:** Menu `Cadastros > Empresas`

Permite cadastrar e gerenciar as empresas do sistema.

#### Criar nova empresa

1. Clique em **"Nova Empresa"** (ou `Ctrl+N`).
2. Preencha:
   - **Nome:** Razão social da empresa
   - **CNPJ:** Formatado automaticamente (XX.XXX.XXX/XXXX-XX)
   - **Status:** Ativo/Inativo
3. Clique em **"Salvar"**.

> O sistema valida automaticamente os dígitos verificadores do CNPJ e impede duplicatas.

#### Editar empresa

Clique no ícone de lápis na linha da empresa desejada, altere os campos e salve.

#### Excluir empresa

Clique no ícone de lixeira. Uma confirmação será solicitada. A exclusão remove **todos os dados vinculados** (plano de contas, conciliações, etc.).

#### Certificado Digital

Na tela de listagem, cada empresa pode ter um certificado digital (PFX) associado, usado para importação de NF-e via SEFAZ. Para adicionar:

1. Clique no ícone de certificado na linha da empresa.
2. Faça o upload do arquivo `.pfx`.
3. Informe a senha do certificado.

### 5.2 Plano de Contas

**Onde:** Menu `Cadastros > Plano de Contas`

Gerencia as contas contábeis da empresa, com suporte a hierarquia (contas sintéticas e analíticas).

#### Importar via Excel

A forma mais rápida de cadastrar o plano de contas é pela importação de um arquivo Excel:

1. Clique em **"Importar Excel"**.
2. Selecione o arquivo (`.xlsx` ou `.xls`).
3. O sistema mapeará automaticamente as colunas.
4. Revise o resumo e confirme a importação.

> Colunas esperadas: `Conta Contábil`, `Descrição`, `Tipo`, `Conciliável`, `Conta Superior`.

#### Criar conta manualmente

1. Clique em **"Nova Conta"** (ou `Ctrl+N`).
2. Preencha:
   - **Conta Contábil:** Código da conta
   - **Descrição:** Nome da conta
   - **Tipo:** Ativo, Passivo, Receita, Despesa ou Patrimônio
   - **Conciliável:** Marque se a conta será usada em conciliações
   - **Conta Superior:** Para contas filhas (hierarquia)
3. Clique em **"Salvar"**.

#### Editar / Excluir

Use os ícones na linha da conta desejada.

---

## 6. Módulo de Conciliação

O módulo de conciliação é o coração do sistema. Veja a documentação completa em [DOCUMENTACAO_CONCILIACAO.md](DOCUMENTACAO_CONCILIACAO.md).

**Resumo do fluxo:**

1. Acesse `Conciliações > Selecionar Período`
2. Escolha empresa, data-base (último dia do mês) e conta contábil
3. Selecione o tipo de conciliação (A Receber, A Pagar, Bancária, Estoque)
4. Faça o upload dos arquivos e processe
5. Analise o resultado e, se correto, efetive a conciliação

---

## 7. Módulo de Estoque

Controla o estoque de produtos com base nas NF-e importadas da SEFAZ. Veja a documentação completa em [DOCUMENTACAO_ESTOQUE.md](DOCUMENTACAO_ESTOQUE.md).

**Resumo do fluxo:**

1. Cadastre os produtos em `Estoque > Produtos`
2. Configure o De-Para (vínculo com fornecedores) em `Estoque > De-Para`
3. Importe as NF-e em `Estoque > Importar NF-e`
4. Consulte saldos em `Estoque > Saldos`
5. Feche o período em `Estoque > Fechamento`

---

## 8. Área Administrativa

**Acesso:** Apenas usuários com perfil **Administrador**.

### 8.1 Usuários

**Onde:** Menu `Admin > Usuários`

| Ação | Descrição |
|------|-----------|
| Criar usuário | Nome, e-mail, senha e tipo (admin/comum) |
| Editar usuário | Alterar dados ou redefinir senha |
| Ativar/Inativar | Bloqueia ou libera o acesso sem excluir |
| Vincular empresa | Associa o usuário a uma ou mais empresas |
| Definir perfil | Escolhe o perfil de acesso por empresa |

### 8.2 Perfis de Acesso

**Onde:** Menu `Admin > Perfis`

Perfis definem quais funcionalidades cada usuário pode acessar. Cada perfil tem um conjunto de **permissões** que pode ser personalizado pelo administrador.

Para criar um perfil:
1. Clique em **"Novo Perfil"**.
2. Informe nome e descrição.
3. Selecione as permissões desejadas.
4. Salve.

### 8.3 Empresas (Admin)

**Onde:** Menu `Admin > Empresas`

Visão administrativa de todas as empresas cadastradas no sistema, com acesso aos dados de cada uma.

---

## 9. Atalhos de Teclado

| Atalho | Ação | Onde |
|--------|------|------|
| `Ctrl+B` | Recolher/expandir barra lateral | Qualquer página |
| `Ctrl+N` | Novo registro | Listas (Empresas, Plano de Contas) |
| `Ctrl+R` | Atualizar lista | Listas (Empresas, Plano de Contas) |
| `Esc` | Fechar modal/janela | Modais e dialogs |

---

## 10. Dúvidas Frequentes

**O sistema aceita quais formatos de arquivo?**
Excel (`.xlsx`, `.xls`) e CSV. Tamanho máximo: 50 MB por arquivo.

**Posso desfazer uma conciliação efetivada?**
Sim. Acesse `Conciliações > Acompanhamento`, localize o registro e use a opção de exclusão. Essa ação é irreversível e remove todos os dados do período efetivado.

**Como trocar de empresa sem fazer logout?**
Atualmente é necessário fazer logout e escolher outra empresa na tela de seleção. Usuários administradores podem alternar via seletor no Dashboard.

**Por que meu acesso está bloqueado?**
Seu usuário pode estar inativo ou desvinculado da empresa. Entre em contato com o administrador do sistema.

**O sistema funciona em celular?**
Sim, o sistema é responsivo e funciona em navegadores mobile, mas é otimizado para uso em desktop.

**O que significa "Threshold de R$ 0,01"?**
Diferenças iguais ou menores que R$ 0,01 entre o financeiro e o contábil são consideradas conciliadas automaticamente (arredondamento contábil).
