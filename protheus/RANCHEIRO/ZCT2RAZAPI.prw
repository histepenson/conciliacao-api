#Include "Protheus.ch"
#Include "restful.ch"
#Include "APWEBSRV.ch"

/*/{Protheus.doc} ZCT2RAZAPI
API REST de razao contabil via consulta SQL direta na tabela CT2.

Substitui o uso de CTBGerRaz() dos relatorios CTBR400 e CTBR480 para fins
de conciliacao contabil, bancaria e de estoque, eliminando o principal
gargalo de performance dessas cargas.

Endpoint: GET /rest/zct2razapi/api/v1/ct2raz

Parametros:
  conta_de      = conta contabil inicial        (obrigatorio)
  conta_ate     = conta contabil final          (obrigatorio)
  data_ini      = data inicial YYYYMMDD         (obrigatorio)
  data_fim      = data final   YYYYMMDD         (obrigatorio)
  moeda         = codigo da moeda (default "01")
  saldo         = 1=Ambos | 2=Somente Debito | 3=Somente Credito (default "1")
  item_de       = item contabil inicial
  item_ate      = item contabil final
  clvl_de       = classe de valor inicial
  clvl_ate      = classe de valor final
  vlr_zerado    = 1=Incluir zeros | 2=Excluir zeros (default "2")
  consid_filiais= 1=Range filiais | 2=Filial corrente (default "2")
  filial_de     = filial inicial (quando consid_filiais=1)
  filial_ate    = filial final   (quando consid_filiais=1)
  custo_de      = centro de custo inicial (aceito, nao filtra em CT2)
  custo_ate     = centro de custo final   (aceito, nao filtra em CT2)
  page          = pagina (default 1)
  pageSize      = registros por pagina (default 5000, max 5000)

Retorno JSON:
  parametros      = parametros efetivos usados
  total_registros = total de linhas no resultado completo
  total_pages     = total de paginas
  page            = pagina atual
  hasMore         = ha mais paginas
  linhas          = lancamentos da pagina

Campos por linha (compativel com CTBR400 / CTBR480):
  data, lote_sub_doc_linha, historico, xpartida,
  c_custo, item_conta, cod_cl_val,
  debito, credito, saldo_atual, conta, ct2_key

@author Equipe Desenvolvimento
@since 21/05/2026
@version 1.3
/*/

wsrestful ZCT2RAZAPI description "CT2 - Razao Contabil SQL Direto"

    wsdata page          as string
    wsdata pageSize      as string
    wsdata conta_de      as string
    wsdata conta_ate     as string
    wsdata data_ini      as string
    wsdata data_fim      as string
    wsdata moeda         as string
    wsdata saldo         as string
    wsdata item_de       as string
    wsdata item_ate      as string
    wsdata clvl_de       as string
    wsdata clvl_ate      as string
    wsdata vlr_zerado    as string
    wsdata consid_filiais as string
    wsdata filial_de     as string
    wsdata filial_ate    as string
    wsdata custo_de      as string
    wsdata custo_ate     as string

    wsmethod GET getRazao description "Razao contabil CT2 SQL direto" wssyntax "/api/v1/ct2raz" PATH "/api/v1/ct2raz"

EndwsRestFul

wsmethod GET getRazao WSRESTFUL ZCT2RAZAPI
Local aArea      := GetArea()
Local oResp      := JsonObject():New()
Local oParams    := JsonObject():New()
Local aLinhas    := {}
Local oLinha     := Nil
Local oError     := Nil
Local cAlias     := GetNextAlias()
Local cSql       := ""
Local cWhere     := ""
Local cTabela    := RetSqlName("CT2")

Local cErrMsg       := ""

Local cContaDe      := AllTrim(Self:conta_de)
Local cContaAte     := AllTrim(Self:conta_ate)
Local cDataIni      := AllTrim(Self:data_ini)
Local cDataFim      := AllTrim(Self:data_fim)
Local cMoeda        := AllTrim(Self:moeda)
Local cSaldo        := AllTrim(Self:saldo)
Local cItemDe       := AllTrim(Self:item_de)
Local cItemAte      := AllTrim(Self:item_ate)
Local cClvlDe       := AllTrim(Self:clvl_de)
Local cClvlAte      := AllTrim(Self:clvl_ate)
Local cVlrZerado    := AllTrim(Self:vlr_zerado)
Local cConsidFil    := AllTrim(Self:consid_filiais)
Local cFilialDe     := AllTrim(Self:filial_de)
Local cFilialAte    := AllTrim(Self:filial_ate)
Local nPage         := Max(1, Val(AllTrim(Self:page)))
Local nPageSize     := Val(AllTrim(Self:pageSize))

Local nTotalReg   := 0
Local nTotalPages := 1
Local nOffset     := 0
Local lHasMore    := .F.
Local lIncCred    := .T.
Local lIncDeb     := .T.
Local cFilialAtual := xFilial("CT2")

Self:SetContentType("application/json")

// --- Validacoes obrigatorias ---
If Empty(cContaDe) .Or. Empty(cContaAte)
    Self:SetResponse(CT2Raz_MontaErro("VALIDATION_ERROR", "Parametros conta_de e conta_ate sao obrigatorios", ""))
    FreeObj(oResp)
    FreeObj(oParams)
    RestArea(aArea)
Return .T.
EndIf

If Empty(cDataIni) .Or. Len(cDataIni) <> 8 .Or. Empty(cDataFim) .Or. Len(cDataFim) <> 8
    Self:SetResponse(CT2Raz_MontaErro("VALIDATION_ERROR", "Parametros data_ini e data_fim sao obrigatorios no formato YYYYMMDD", ""))
    FreeObj(oResp)
    FreeObj(oParams)
    RestArea(aArea)
Return .T.
EndIf

// --- Defaults e normalizacao ---
cMoeda     := IIf(Empty(cMoeda), "01", PadL(AllTrim(cMoeda), 2, "0"))
cSaldo     := IIf(Empty(cSaldo),     "1",  cSaldo)
cVlrZerado := IIf(Empty(cVlrZerado),"2",  cVlrZerado)
cConsidFil := IIf(Empty(cConsidFil), "2",  cConsidFil)
nPageSize  := IIf(nPageSize <= 0 .Or. nPageSize > 5000, 5000, nPageSize)
nOffset    := (nPage - 1) * nPageSize

// saldo=2 => somente debito | saldo=3 => somente credito
lIncCred := (cSaldo != "2")
lIncDeb  := (cSaldo != "3")

ConOut("[ZCT2RAZ] conta_de=[" + cContaDe + "] conta_ate=[" + cContaAte + "]" + ;
    " data=" + cDataIni + "/" + cDataFim + ;
    " moeda=" + cMoeda + " saldo=" + cSaldo + ;
    " item=" + cItemDe + "/" + cItemAte + ;
    " clvl=" + cClvlDe + "/" + cClvlAte + ;
    " vlr_zerado=" + cVlrZerado + " consid_filiais=" + cConsidFil + ;
    " filial_de=" + cFilialDe + " filial_ate=" + cFilialAte + ;
    " filial_atual=" + cFilialAtual + ;
    " page=" + cValToChar(nPage) + " pageSize=" + cValToChar(nPageSize))

// --- WHERE comum (data, moeda, valor zerado, filial) ---
cWhere := " D_E_L_E_T_ = ' '"
cWhere += " AND CT2_MOEDLC = '" + cMoeda + "'"
cWhere += " AND CT2_DATA BETWEEN '" + cDataIni + "' AND '" + cDataFim + "'"

If cVlrZerado == "2"
    cWhere += " AND CT2_VALOR <> 0"
EndIf

If cConsidFil == "1"
    If !Empty(cFilialDe) .And. !Empty(cFilialAte)
        cWhere += " AND CT2_FILORI BETWEEN '" + cFilialDe + "' AND '" + cFilialAte + "'"
    // consid_filiais=1 sem range = todas as filiais, sem filtro
    EndIf
Else
    cWhere += " AND CT2_FILORI = '" + cFilialAtual + "'"
EndIf

// --- Paginacao no proprio SQL via ROW_NUMBER() OVER() -- evita reexecutar e
// rematerializar o resultado inteiro (UNION) a cada pagina pedida. Mesma
// tecnica usada no ZCT2RAZCT5. COUNT(*) OVER() traz o total de linhas (antes
// do corte por RN) em cada linha devolvida, entao uma unica execucao ja da a
// pagina E o total, sem segunda consulta.
cSql := " SELECT * FROM ("
cSql += "   SELECT *,"
cSql += "     ROW_NUMBER() OVER (ORDER BY CT2_DATA, CT2_LOTE, CT2_SBLOTE, CT2_DOC, CT2_LINHA, CT2_KEY) AS RN,"
cSql += "     COUNT(*) OVER() AS TOTAL_REG"
cSql += "   FROM ("

// --- Bloco CREDITO (DC=2 e DC=3) ---
If lIncCred
    cSql += " SELECT"
    cSql += "     CT2_DATA, CT2_LOTE, CT2_SBLOTE, CT2_DOC, CT2_LINHA,"
    cSql += "     CT2_CREDIT AS conta,"
    cSql += "     CT2_DEBITO AS xpartida,"
    cSql += "     CT2_HIST   AS historico,"
    cSql += "     CT2_ITEMC  AS item_conta,"
    cSql += "     CT2_CLVLCR AS cod_cl_val,"
    cSql += "     0          AS debito,"
    cSql += "     CT2_VALOR  AS credito,"
    cSql += "     CT2_KEY"
    cSql += " FROM " + cTabela
    cSql += " WHERE " + cWhere
    cSql += "   AND CT2_DC IN ('2','3')"
    cSql += "   AND CT2_CREDIT BETWEEN '" + cContaDe + "' AND '" + cContaAte + "'"
    If !Empty(cItemDe) .And. !Empty(cItemAte)
        cSql += "   AND CT2_ITEMC BETWEEN '" + cItemDe + "' AND '" + cItemAte + "'"
    EndIf
    If !Empty(cClvlDe) .And. !Empty(cClvlAte)
        cSql += "   AND CT2_CLVLCR BETWEEN '" + cClvlDe + "' AND '" + cClvlAte + "'"
    EndIf
EndIf

// --- UNION (elimina duplicatas de DC=3 que aparece nos dois lados) ---
If lIncCred .And. lIncDeb
    cSql += " UNION"
EndIf

// --- Bloco DEBITO (DC=1 e DC=3) ---
If lIncDeb
    cSql += " SELECT"
    cSql += "     CT2_DATA, CT2_LOTE, CT2_SBLOTE, CT2_DOC, CT2_LINHA,"
    cSql += "     CT2_DEBITO AS conta,"
    cSql += "     CT2_CREDIT AS xpartida,"
    cSql += "     CT2_HIST   AS historico,"
    cSql += "     CT2_ITEMD  AS item_conta,"
    cSql += "     CT2_CLVLDB AS cod_cl_val,"
    cSql += "     CT2_VALOR  AS debito,"
    cSql += "     0          AS credito,"
    cSql += "     CT2_KEY"
    cSql += " FROM " + cTabela
    cSql += " WHERE " + cWhere
    cSql += "   AND CT2_DC IN ('1','3')"
    cSql += "   AND CT2_DEBITO BETWEEN '" + cContaDe + "' AND '" + cContaAte + "'"
    If !Empty(cItemDe) .And. !Empty(cItemAte)
        cSql += "   AND CT2_ITEMD BETWEEN '" + cItemDe + "' AND '" + cItemAte + "'"
    EndIf
    If !Empty(cClvlDe) .And. !Empty(cClvlAte)
        cSql += "   AND CT2_CLVLDB BETWEEN '" + cClvlDe + "' AND '" + cClvlAte + "'"
    EndIf
EndIf

cSql += "   ) AS RAZAO"
cSql += " ) AS PAGINADO"
cSql += " WHERE RN > " + cValToChar(nOffset) + " AND RN <= " + cValToChar(nOffset + nPageSize)
cSql += " ORDER BY RN"

ConOut("[ZCT2RAZ] SQL montado | tabela=" + cTabela + " incCred=" + IIf(lIncCred,"S","N") + " incDeb=" + IIf(lIncDeb,"S","N") + ;
    " offset=" + cValToChar(nOffset) + " pageSize=" + cValToChar(nPageSize))

Begin Sequence
    dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .T., .F.)
    TCSetField(cAlias, "CT2_DATA",  "D",  8, 0)
    TCSetField(cAlias, "debito",    "N", 18, 2)
    TCSetField(cAlias, "credito",   "N", 18, 2)
    TCSetField(cAlias, "TOTAL_REG", "N", 10, 0)
    TCSetField(cAlias, "RN",        "N", 10, 0)

    (cAlias)->(DbGoTop())
    // O SQL ja devolve so' a pagina pedida (filtro por RN) -- toda linha lida
    // aqui pertence a pagina, sem precisar pular nenhuma em ADVPL. TOTAL_REG
    // vem do COUNT(*) OVER() (mesmo valor em toda linha) e reflete o total
    // ANTES do corte por RN.
    If !(cAlias)->(Eof())
        nTotalReg := (cAlias)->TOTAL_REG
    EndIf
    While !(cAlias)->(Eof())
        oLinha := JsonObject():New()
        oLinha["data"]               := DtoC((cAlias)->CT2_DATA)
        oLinha["lote_sub_doc_linha"] := AllTrim((cAlias)->CT2_LOTE)  + ;
                                        AllTrim((cAlias)->CT2_SBLOTE) + ;
                                        AllTrim((cAlias)->CT2_DOC)    + ;
                                        AllTrim((cAlias)->CT2_LINHA)
        oLinha["historico"]          := AllTrim((cAlias)->historico)
        oLinha["xpartida"]           := AllTrim((cAlias)->xpartida)
        oLinha["c_custo"]            := ""
        oLinha["item_conta"]         := AllTrim((cAlias)->item_conta)
        oLinha["cod_cl_val"]         := AllTrim((cAlias)->cod_cl_val)
        oLinha["debito"]             := Round((cAlias)->debito,  2)
        oLinha["credito"]            := Round((cAlias)->credito, 2)
        oLinha["saldo_atual"]        := 0
        oLinha["conta"]              := AllTrim((cAlias)->conta)
        oLinha["ct2_key"]            := AllTrim((cAlias)->CT2_KEY)
        AAdd(aLinhas, oLinha)
        (cAlias)->(DbSkip())
    EndDo

    (cAlias)->(DbCloseArea())

    nTotalPages := Max(1, Int((nTotalReg + nPageSize - 1) / nPageSize))
    lHasMore    := (nPage < nTotalPages)

Recover Using oError
    If Select(cAlias) > 0
        (cAlias)->(DbCloseArea())
    EndIf
    cErrMsg := "Erro ao consultar CT2"
    If ValType(oError) == "O"
        cErrMsg += ": " + AllTrim(oError:Description)
    EndIf
    ConOut("[ZCT2RAZ] ERRO: " + cErrMsg)
    Self:SetResponse(CT2Raz_MontaErro("INTERNAL_ERROR", cErrMsg, ""))
    FreeObj(oResp)
    FreeObj(oParams)
    AEval(aLinhas, {|o| FreeObj(o)})
    RestArea(aArea)
Return .T.
End Sequence

ConOut("[ZCT2RAZ] total=" + cValToChar(nTotalReg) + ;
    " pages=" + cValToChar(nTotalPages) + ;
    " page=" + cValToChar(nPage) + ;
    " linhas_pagina=" + cValToChar(Len(aLinhas)) + ;
    " hasMore=" + IIf(lHasMore, "S", "N"))

oParams["conta_de"]       := cContaDe
oParams["conta_ate"]      := cContaAte
oParams["data_ini"]       := cDataIni
oParams["data_fim"]       := cDataFim
oParams["moeda"]          := cMoeda
oParams["saldo"]          := cSaldo
oParams["item_de"]        := cItemDe
oParams["item_ate"]       := cItemAte
oParams["clvl_de"]        := cClvlDe
oParams["clvl_ate"]       := cClvlAte
oParams["vlr_zerado"]     := cVlrZerado
oParams["consid_filiais"] := cConsidFil
oParams["filial_de"]      := cFilialDe
oParams["filial_ate"]     := cFilialAte
oParams["page"]           := nPage
oParams["pageSize"]       := nPageSize

oResp["parametros"]      := oParams
oResp["total_registros"] := nTotalReg
oResp["total_pages"]     := nTotalPages
oResp["page"]            := nPage
oResp["hasMore"]         := lHasMore
oResp["linhas"]          := aLinhas

Self:SetResponse(oResp:ToJson())

FreeObj(oResp)
FreeObj(oParams)
AEval(aLinhas, {|o| FreeObj(o)})
RestArea(aArea)

Return .T.

Static Function CT2Raz_MontaErro(cCode, cMessage, cDetails)
Local oErr  := JsonObject():New()
Local cJson := ""

oErr["erro"]     := .T.
oErr["status"]   := IIf(cCode == "INTERNAL_ERROR", 500, 422)
oErr["mensagem"] := cMessage
If !Empty(cDetails)
    oErr["details"] := cDetails
EndIf

cJson := oErr:ToJson()
FreeObj(oErr)

Return cJson
