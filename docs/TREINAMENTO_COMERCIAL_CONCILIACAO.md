# Smart Conciliações — Guia Comercial



## O problema que resolvemos

Toda empresa precisa garantir que o **financeiro** (o que foi lançado, cobrado, pago) bate com a **contabilidade** (o que está registrado no razão contábil). Hoje isso é feito manualmente em planilhas, comparando linha por linha — processo lento, sujeito a erro e que não deixa rastro de auditoria.

O **Smart Conciliações** automatiza essa comparação. O usuário sobe os arquivos (exportados do Protheus ou de qualquer ERP) e o sistema faz o cruzamento, aponta as diferenças e gera o relatório em segundos.

Três frentes de conciliação: **Fornecedores**, **Clientes** e **Impostos**.

---

## 1. Conciliação de Fornecedores (Contas a Pagar)

**O que compara:** os títulos a pagar (o que a empresa deve a fornecedores) contra o saldo lançado na contabilidade.

**Pergunta que responde:** "O que está em aberto no financeiro para pagar bate com o que a contabilidade registrou?"

**Como funciona na prática:**
1. Usuário sobe a posição de títulos a pagar do período.
2. Usuário sobe o saldo contábil da conta de fornecedores.
3. O sistema cruza pelo código do fornecedor e aponta:
   - Fornecedores **conciliados** (financeiro = contábil)
   - Fornecedores **divergentes** (valores diferentes)
   - Fornecedores que existem só em um dos lados
4. Para cada divergência, o sistema já rastreia **os lançamentos individuais no razão** que explicam a diferença — inclusive tentando localizar o número da nota fiscal e o código do fornecedor dentro do histórico do lançamento contábil.

**Valor para o cliente:** elimina o trabalho manual de vasculhar o razão fornecedor por fornecedor. O time de contabilidade já recebe pronta a lista de "o que precisa investigar" — em vez de conferir tudo do zero.

---

## 2. Conciliação de Clientes (Contas a Receber)

**O que compara:** os títulos a receber (o que os clientes devem à empresa) contra o saldo lançado na contabilidade.

**Pergunta que responde:** "O que está em aberto para receber bate com o que a contabilidade registrou?"

**Como funciona:** mesma lógica da conciliação de fornecedores, espelhada para o lado de clientes — mesmo motor, mesmo relatório, mesma rastreabilidade de lançamentos.

**Valor para o cliente:** mesmo ganho de produtividade e confiabilidade do módulo de fornecedores, aplicado ao contas a receber. Empresas com carteira grande de clientes sentem o ganho de tempo de forma ainda mais evidente.

---

## 3. Conciliação de Impostos

**O que compara:** o valor de um imposto apurado nas notas fiscais de entrada (ICMS, PIS, COFINS, IPI, ICMS Substituição, ICMS Complementar, DIFAL, entre outros) contra o valor lançado na conta contábil correspondente.

**Pergunta que responde:** "O imposto que consta nas notas fiscais de entrada bate com o que foi contabilizado?"

**Como funciona na prática:**
1. Usuário sobe as notas fiscais de entrada do período (fonte fiscal).
2. Usuário sobe o razão contábil da conta do imposto.
3. Usuário escolhe **qual imposto** quer conferir (o sistema lista as colunas disponíveis: ICMS, PIS, COFINS, IPI, ICMS Retido, ICMS Complementar, DIFAL, etc.) e se quer olhar entradas, saídas, ou incluir/excluir notas de exportação.
4. O sistema soma o imposto apurado nas notas e compara com o lançamento contábil, mostrando:
   - Notas fiscais **sem** lançamento contábil correspondente
   - Lançamentos contábeis **sem** nota fiscal correspondente
   - O total conciliado vs. divergente

**Valor para o cliente:** hoje esse cruzamento fiscal x contábil normalmente é feito "de vez em quando" ou nem é feito, por ser trabalhoso. Com o sistema, vira rotina — reduz risco de autuação e retrabalho no fechamento fiscal.

---

## 4. Análise de Divergências com Inteligência Artificial

**O que faz:** depois que a conciliação roda (em Fornecedores, Clientes, Bancária, Estoque ou Impostos), o usuário pode pedir para a **IA analisar** as divergências que sobraram. Em vez de o time abrir o razão e investigar manualmente cada uma, o sistema já devolve um **diagnóstico da causa provável** em linguagem simples.

**Como funciona na prática:**
1. Usuário roda a conciliação normalmente e chega na lista de divergências.
2. Clica em "Analisar com IA" (por item ou para o lote de pendências).
3. No caso de Fornecedores/Clientes, antes de acionar a IA o sistema já vai sozinho até a contabilidade e verifica se aquele título "sumiu" apenas porque foi lançado em **outra conta contábil** — um dos motivos mais comuns de divergência.
4. A IA recebe todo esse contexto (os dois lados da conciliação, o que já foi investigado) e devolve a explicação mais provável para a diferença.

**Valor para o cliente:** essa é a etapa que mais consome tempo do time de contabilidade — descobrir *por que* algo não bateu, não só *que* não bateu. A IA entrega esse primeiro diagnóstico pronto, e o analista só precisa confirmar em vez de investigar do zero.

---

## O que os três módulos têm em comum

- **Upload simples**: arquivo Excel/CSV, sem necessidade de digitar nada manualmente.
- **Resultado em segundos**: mesmo com milhares de linhas.
- **Regra de arredondamento inteligente**: diferenças de até R$ 0,01 são tratadas como "sem diferença" (evita alertas falsos por arredondamento contábil).
- **Efetivação com histórico**: depois de conferido, o usuário "efetiva" a conciliação — ela fica salva, auditável, com os arquivos originais anexados, e não precisa ser refeita.
- **Acompanhamento**: todas as conciliações já efetivadas ficam disponíveis para consulta futura (auditoria, comprovação para o fiscal, etc.).

---

## Argumentos de venda (resumo rápido)

| Hoje (planilha manual) | Com o Smart Conciliações |
|---|---|
| Horas comparando linha por linha | Resultado em segundos |
| Erro humano no cruzamento | Cruzamento automático e consistente |
| Sem rastro de quem conferiu o quê e quando | Histórico de conciliações efetivadas, auditável |
| Fornecedor/cliente/imposto conferidos "quando dá tempo" | Vira rotina mensal, sem esforço extra |
| Divergência encontrada, mas sem saber a causa | Sistema já aponta o lançamento (ou nota) que explica a diferença |
| Investigar a causa da divergência do zero | IA sugere o diagnóstico provável em segundos |
