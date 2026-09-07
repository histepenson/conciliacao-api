#Include "Protheus.ch"
#Include "restful.ch"
#Include "APWEBSRV.ch"

/*/{Protheus.doc} ZSN3API
API REST de Baixas de Ativo Fixo via consulta SQL direta na tabela SN3.

Endpoint: GET /rest/zsn3api/api/v1/sn3

Parametros:
  data_ini      = data inicial YYYYMMDD  (obrigatorio) - filtra por N3_DTBAIXA
  data_fim      = data final   YYYYMMDD  (obrigatorio) - filtra por N3_DTBAIXA
  filial_de     = filial inicial (default "")
  filial_ate    = filial final   (default "zzzzzzzzz")
  page          = pagina (default 1)
  pageSize      = registros por pagina (default 5000, max 5000)

Retorno JSON:
  parametros      = parametros efetivos usados
  total_registros = total de linhas no resultado completo
  total_pages     = total de paginas
  page            = pagina atual
  hasMore         = ha mais paginas
  linhas          = registros da pagina

Campos por linha:
  filial, cbase, item, tipo, baixa, dtbaixa, seq, vorig1

@author Equipe Desenvolvimento
@since 21/06/2026
@version 1.0
/*/

wsrestful ZSN3API description "SN3 - Baixas de Ativo Fixo SQL Direto"

    wsdata page           as string
    wsdata pageSize       as string
    wsdata data_ini       as string
    wsdata data_fim       as string
    wsdata filial_de      as string
    wsdata filial_ate     as string

    wsmethod GET getSn3 description "Baixas de Ativo Fixo SN3 SQL direto" wssyntax "/api/v1/sn3" PATH "/api/v1/sn3"

EndwsRestFul

wsmethod GET getSn3 WSRESTFUL ZSN3API
Local aArea      := GetArea()
Local oResp      := JsonObject():New()
Local oParams    := JsonObject():New()
Local aLinhas    := {}
Local oLinha     := Nil
Local oError     := Nil
Local cAlias     := GetNextAlias()
Local cSql       := ""
Local cWhere     := ""
Local cTabela    := RetSqlName("SN3")
Local cErrMsg    := ""

Local cDataIni   := AllTrim(Self:data_ini)
Local cDataFim   := AllTrim(Self:data_fim)
Local cFilialDe  := AllTrim(Self:filial_de)
Local cFilialAte := AllTrim(Self:filial_ate)
Local nPage      := Max(1, Val(AllTrim(Self:page)))
Local nPageSize  := Val(AllTrim(Self:pageSize))

Local nTotalReg   := 0
Local nTotalPages := 1
Local nOffset     := 0
Local lHasMore    := .F.

Self:SetContentType("application/json")

// --- Validacoes obrigatorias ---
If Empty(cDataIni) .Or. Len(cDataIni) <> 8 .Or. Empty(cDataFim) .Or. Len(cDataFim) <> 8
    Self:SetResponse(Sn3_MontaErro("VALIDATION_ERROR", "Parametros data_ini e data_fim sao obrigatorios no formato YYYYMMDD", ""))
    FreeObj(oResp)
    FreeObj(oParams)
    RestArea(aArea)
Return .T.
EndIf

// --- Defaults ---
cFilialDe  := IIf(Empty(cFilialDe),  "",          cFilialDe)
cFilialAte := IIf(Empty(cFilialAte), "zzzzzzzzz", cFilialAte)
nPageSize  := IIf(nPageSize <= 0 .Or. nPageSize > 5000, 5000, nPageSize)
nOffset    := (nPage - 1) * nPageSize

ConOut("[ZSN3API] data=" + cDataIni + "/" + cDataFim + ;
    " filial_de=" + cFilialDe + " filial_ate=" + cFilialAte + ;
    " page=" + cValToChar(nPage) + " pageSize=" + cValToChar(nPageSize))

// --- WHERE ---
cWhere := " N3_TIPO = '01'"
cWhere += " AND D_E_L_E_T_ = ' ' "
cWhere += " AND N3_VORIG1 > 0 "
cWhere += " AND N3_DTBAIXA BETWEEN '" + cDataIni + "' AND '" + cDataFim + "'"
cWhere += " AND N3_FILIAL BETWEEN '" + cFilialDe + "' AND '" + cFilialAte + "'"

// --- SQL ---
cSql := " SELECT"
cSql += "     N3_FILIAL,"
cSql += "     N3_CBASE,"
cSql += "     N3_ITEM,"
cSql += "     N3_TIPO,"
cSql += "     N3_BAIXA,"
cSql += "     N3_DTBAIXA,"
cSql += "     N3_SEQ,"
cSql += "     N3_VORIG1"
cSql += " FROM " + cTabela
cSql += " WHERE " + cWhere
cSql += " ORDER BY N3_DTBAIXA, N3_FILIAL, N3_CBASE, N3_ITEM, N3_SEQ"

ConOut("[ZSN3API] SQL montado | tabela=" + cTabela)

Begin Sequence
    dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .T., .F.)
    TCSetField(cAlias, "N3_DTBAIXA", "D",  8, 0)
    TCSetField(cAlias, "N3_VORIG1",  "N", 16, 2)

    (cAlias)->(DbGoTop())
    While !(cAlias)->(Eof())
        // So' monta o JsonObject quando a linha estiver dentro da janela da
        // pagina pedida -- evita reter em memoria o resultado inteiro so'
        // para devolver no maximo pageSize (5000) por requisicao.
        nTotalReg++
        If nTotalReg > nOffset .And. Len(aLinhas) < nPageSize
            oLinha := JsonObject():New()
            oLinha["filial"]  := AllTrim((cAlias)->N3_FILIAL)
            oLinha["cbase"]   := AllTrim((cAlias)->N3_CBASE)
            oLinha["item"]    := AllTrim((cAlias)->N3_ITEM)
            oLinha["tipo"]    := AllTrim((cAlias)->N3_TIPO)
            oLinha["baixa"]   := AllTrim((cAlias)->N3_BAIXA)
            oLinha["dtbaixa"] := DtoC((cAlias)->N3_DTBAIXA)
            oLinha["seq"]     := AllTrim((cAlias)->N3_SEQ)
            oLinha["vorig1"]  := Round((cAlias)->N3_VORIG1, 2)
            AAdd(aLinhas, oLinha)
        EndIf
        (cAlias)->(DbSkip())
    EndDo

    (cAlias)->(DbCloseArea())

    nTotalPages := Max(1, Int((nTotalReg + nPageSize - 1) / nPageSize))
    lHasMore    := (nPage < nTotalPages)

Recover Using oError
    If Select(cAlias) > 0
        (cAlias)->(DbCloseArea())
    EndIf
    cErrMsg := "Erro ao consultar SN3"
    If ValType(oError) == "O"
        cErrMsg += ": " + AllTrim(oError:Description)
    EndIf
    ConOut("[ZSN3API] ERRO: " + cErrMsg)
    Self:SetResponse(Sn3_MontaErro("INTERNAL_ERROR", cErrMsg, ""))
    FreeObj(oResp)
    FreeObj(oParams)
    AEval(aLinhas, {|o| FreeObj(o)})
    RestArea(aArea)
Return .T.
End Sequence

ConOut("[ZSN3API] total=" + cValToChar(nTotalReg) + ;
    " pages=" + cValToChar(nTotalPages) + ;
    " page=" + cValToChar(nPage) + ;
    " linhas_pagina=" + cValToChar(Len(aLinhas)) + ;
    " hasMore=" + IIf(lHasMore, "S", "N"))

oParams["data_ini"]   := cDataIni
oParams["data_fim"]   := cDataFim
oParams["filial_de"]  := cFilialDe
oParams["filial_ate"] := cFilialAte
oParams["page"]       := nPage
oParams["pageSize"]   := nPageSize

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

Static Function Sn3_MontaErro(cCode, cMessage, cDetails)
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
