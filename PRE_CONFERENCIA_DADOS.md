# Pré-Conferência — Teoria do Problema

## O que queremos resolver

A empresa lança notas fiscais de entrada no sistema (Protheus). Esses lançamentos geram dois registros em lugares diferentes:

1. **Lançamento contábil (CT2)** — o contador registra o débito na conta contábil correspondente.
2. **Livro fiscal (SFT)** — o sistema registra a nota fiscal de entrada no livro fiscal eletrônico.

Em teoria, cada nota fiscal deve aparecer nos dois lugares com o mesmo valor. Na prática, isso nem sempre acontece — e é exatamente essa diferença que queremos identificar.

---

## Os dois relatórios

### Relatório 1 — Razão Contábil (CT2)

Contém todos os lançamentos contábeis do período. Cada linha representa um débito ou crédito em uma conta contábil, com:

- Data do lançamento
- Conta contábil debitada
- Histórico (texto livre que identifica a NF, o fornecedor etc.)
- Valor debitado
- Código do fornecedor / cliente
- Número da NF (extraído da chave do lançamento)
- Lançamento Padrão (LP) — identifica o tipo de operação (ex: frete, serviço, mercadoria)

### Relatório 2 — Livro Fiscal (SFT)

Contém todas as notas fiscais de entrada registradas no livro fiscal do período. Cada linha representa uma NF, com:

- Filial que recebeu a NF
- Número da NF
- Fornecedor
- Data de entrada no sistema
- CFOP — código que classifica a operação fiscal (ex: 2352 = compra de serviço de frete)
- Valor contábil da NF

---

## Como funciona o cruzamento

Para cada tipo de operação (LP), existe uma configuração que diz quais CFOPs do livro fiscal correspondem àquele lançamento contábil.

Com isso, o sistema:

1. Soma todos os débitos do CT2 para aquele LP no período.
2. Soma todos os valores das NFs do SFT que têm os CFOPs configurados para aquele LP.
3. Compara os dois totais.

Se os totais forem iguais, está **OK**.
Se houver diferença, o sistema abre o detalhe e mostra **quais NFs estão em um relatório mas não no outro**.

---

## Por que aparecem diferenças

| Situação | Descrição |
|----------|-----------|
| NF só no SFT | A nota foi recebida e registrada no livro fiscal, mas o lançamento contábil ainda não foi feito (ou foi feito em outro período). |
| NF só no CT2 | O contador lançou o débito contábil, mas a nota não entrou no livro fiscal (recusa fiscal, cancelamento, digitação errada). |
| Valores diferentes | A NF existe nos dois, mas com valores distintos (desconto posterior, erro de digitação, diferença de impostos). |

---

## Ponto crítico: o campo de data

O CT2 usa a **data do lançamento contábil** (quando o contador processou).
O SFT deve usar a **data de entrada da NF no sistema** (`FT_ENTRADA`), não a data de emissão da nota pelo fornecedor (`FT_EMISSAO`).

Usar a data de emissão no SFT é o principal motivo de notas "desaparecerem" do cruzamento — o fornecedor emite a nota em dezembro, mas ela entra no sistema em janeiro. O CT2 a enxerga em janeiro, o SFT (com filtro por emissão) não.

---

## O que a configuração precisa ter

Para cada tipo de lançamento contábil que a empresa usa, precisamos saber:

- **Qual é o LP** (código e descrição) — identifica o lançamento no CT2.
- **Quais são os CFOPs** correspondentes no livro fiscal — identifica as NFs no SFT.
- **Se faz parte de um grupo** — algumas operações têm vários LPs que devem ser somados antes de comparar com o SFT.

Sem essa configuração, o sistema não consegue cruzar os dados e marca o LP como "sem mapeamento".
