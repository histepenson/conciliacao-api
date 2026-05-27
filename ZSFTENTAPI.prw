#Include "Protheus.ch"
#Include "restful.ch"
#Include "APWEBSRV.ch"

/*/{Protheus.doc} ZSFTENTAPI
API REST de entradas/saidas do Livro Fiscal via consulta SQL direta na tabela SFT.

Endpoint: GET /rest/zsftentapi/api/v1/sftent

Parametros:
  data_ini      = data inicial YYYYMMDD         (obrigatorio)
  data_fim      = data final   YYYYMMDD         (obrigatorio)
  filial_de     = filial inicial (default "")
  filial_ate    = filial final   (default "zzzzzzzzz")
  entrsa        = E=Entradas | S=Saidas | vazio=Todas (default vazio)
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
  filial, nf, serie, tipo, data, emissao,
  fornece, loja, cfop, tpnf, entrsa,
  valmerc, valipi, valfre, valliq,
  basicm, valicm, valdesc, valout, valcont

@author Equipe Desenvolvimento
@since 27/05/2026
@version 1.2
/*/

wsrestful ZSFTENTAPI description "SFT - Livro Fiscal Entradas/Saidas SQL Direto"

    wsdata page           as string
    wsdata pageSize       as string
    wsdata data_ini       as string
    wsdata data_fim       as string
    wsdata filial_de      as string
    wsdata filial_ate     as string
    wsdata entrsa         as string

    wsmethod GET getSftEnt description "Livro Fiscal SFT SQL direto" wssyntax "/api/v1/sftent" PATH "/api/v1/sftent"

EndwsRestFul

wsmethod GET getSftEnt WSRESTFUL ZSFTENTAPI
Local aArea      := GetArea()
Local oResp      := JsonObject():New()
Local oParams    := JsonObject():New()
Local aAllLinhas := {}
Local aLinhas    := {}
Local oLinha     := Nil
Local oError     := Nil
Local cAlias     := GetNextAlias()
Local cSql       := ""
Local cWhere     := ""
Local cTabela    := RetSqlName("SFT")
Local cErrMsg    := ""

Local cDataIni   := AllTrim(Self:data_ini)
Local cDataFim   := AllTrim(Self:data_fim)
Local cFilialDe  := AllTrim(Self:filial_de)
Local cFilialAte := AllTrim(Self:filial_ate)
Local cEntrSa    := Upper(AllTrim(Self:entrsa))
Local nPage      := Max(1, Val(AllTrim(Self:page)))
Local nPageSize  := Val(AllTrim(Self:pageSize))

Local nTotalReg   := 0
Local nTotalPages := 1
Local nOffset     := 0
Local nRecAtual   := 0
Local lHasMore    := .F.

Self:SetContentType("application/json")

// --- Validacoes obrigatorias ---
If Empty(cDataIni) .Or. Len(cDataIni) <> 8 .Or. Empty(cDataFim) .Or. Len(cDataFim) <> 8
    Self:SetResponse(SftEnt_MontaErro("VALIDATION_ERROR", "Parametros data_ini e data_fim sao obrigatorios no formato YYYYMMDD", ""))
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

ConOut("[ZSFTENTAPI] data=" + cDataIni + "/" + cDataFim + ;
    " filial_de=" + cFilialDe + " filial_ate=" + cFilialAte + ;
    " entrsa=" + cEntrSa + ;
    " page=" + cValToChar(nPage) + " pageSize=" + cValToChar(nPageSize))

// --- WHERE ---
cWhere := " D_E_L_E_T_ = ' '"
cWhere += " AND FT_DATA BETWEEN '" + cDataIni + "' AND '" + cDataFim + "'"
cWhere += " AND FT_FILIAL BETWEEN '" + cFilialDe + "' AND '" + cFilialAte + "'"

If !Empty(cEntrSa) .And. (cEntrSa == "E" .Or. cEntrSa == "S")
    cWhere += " AND FT_ENTRSA = '" + cEntrSa + "'"
EndIf

// --- SQL ---
cSql := " SELECT"
cSql += "     FT_FILIAL,"
cSql += "     FT_NFISCAL,"
cSql += "     FT_SERIE,"
cSql += "     FT_TIPO,"
cSql += "     FT_DATA,"
cSql += "     FT_EMISSAO,"
cSql += "     FT_FORNECE,"
cSql += "     FT_LOJA,"
cSql += "     FT_CFOP,"
cSql += "     FT_TPNF,"
cSql += "     FT_ENTRSA,"
cSql += "     FT_VALMERC,"
cSql += "     FT_VALIPI,"
cSql += "     FT_VALFRE,"
cSql += "     FT_VALLIQ,"
cSql += "     FT_BASICM,"
cSql += "     FT_VALICM,"
cSql += "     FT_VALDESC,"
cSql += "     FT_VALOUT,"
cSql += "     FT_VALCONT"
cSql += " FROM " + cTabela
cSql += " WHERE " + cWhere
cSql += " ORDER BY FT_DATA, FT_FILIAL, FT_NFISCAL, FT_SERIE"

ConOut("[ZSFTENTAPI] SQL montado | tabela=" + cTabela)

Begin Sequence
    dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .T., .F.)
    TCSetField(cAlias, "FT_DATA",    "D",  8, 0)
    TCSetField(cAlias, "FT_EMISSAO", "D",  8, 0)
    TCSetField(cAlias, "FT_VALMERC", "N", 16, 2)
    TCSetField(cAlias, "FT_VALIPI",  "N", 16, 2)
    TCSetField(cAlias, "FT_VALFRE",  "N", 16, 2)
    TCSetField(cAlias, "FT_VALLIQ",  "N", 16, 2)
    TCSetField(cAlias, "FT_BASICM",  "N", 16, 2)
    TCSetField(cAlias, "FT_VALICM",  "N", 16, 2)
    TCSetField(cAlias, "FT_VALDESC", "N", 16, 2)
    TCSetField(cAlias, "FT_VALOUT",  "N", 16, 2)
    TCSetField(cAlias, "FT_VALCONT", "N", 16, 2)

    (cAlias)->(DbGoTop())
    While !(cAlias)->(Eof())
        oLinha := JsonObject():New()
        oLinha["filial"]   := AllTrim((cAlias)->FT_FILIAL)
        oLinha["nf"]       := AllTrim((cAlias)->FT_NFISCAL)
        oLinha["serie"]    := AllTrim((cAlias)->FT_SERIE)
        oLinha["tipo"]     := AllTrim((cAlias)->FT_TIPO)
        oLinha["data"]     := DtoC((cAlias)->FT_DATA)
        oLinha["emissao"]  := DtoC((cAlias)->FT_EMISSAO)
        oLinha["fornece"]  := AllTrim((cAlias)->FT_FORNECE)
        oLinha["loja"]     := AllTrim((cAlias)->FT_LOJA)
        oLinha["cfop"]     := AllTrim((cAlias)->FT_CFOP)
        oLinha["tpnf"]     := AllTrim((cAlias)->FT_TPNF)
        oLinha["entrsa"]   := AllTrim((cAlias)->FT_ENTRSA)
        oLinha["valmerc"]  := Round((cAlias)->FT_VALMERC, 2)
        oLinha["valipi"]   := Round((cAlias)->FT_VALIPI,  2)
        oLinha["valfre"]   := Round((cAlias)->FT_VALFRE,  2)
        oLinha["valliq"]   := Round((cAlias)->FT_VALLIQ,  2)
        oLinha["basicm"]   := Round((cAlias)->FT_BASICM,  2)
        oLinha["valicm"]   := Round((cAlias)->FT_VALICM,  2)
        oLinha["valdesc"]  := Round((cAlias)->FT_VALDESC,  2)
        oLinha["valout"]   := Round((cAlias)->FT_VALOUT,   2)
        oLinha["valcont"]  := Round((cAlias)->FT_VALCONT,  2)
        AAdd(aAllLinhas, oLinha)
        (cAlias)->(DbSkip())
    EndDo

    (cAlias)->(DbCloseArea())

    nTotalReg   := Len(aAllLinhas)
    nTotalPages := Max(1, Int((nTotalReg + nPageSize - 1) / nPageSize))
    lHasMore    := (nPage < nTotalPages)

    nRecAtual := 0
    While nRecAtual < nPageSize .And. (nOffset + nRecAtual + 1) <= nTotalReg
        AAdd(aLinhas, aAllLinhas[nOffset + nRecAtual + 1])
        nRecAtual++
    EndDo

Recover Using oError
    If Select(cAlias) > 0
        (cAlias)->(DbCloseArea())
    EndIf
    cErrMsg := "Erro ao consultar SFT"
    If ValType(oError) == "O"
        cErrMsg += ": " + AllTrim(oError:Description)
    EndIf
    ConOut("[ZSFTENTAPI] ERRO: " + cErrMsg)
    Self:SetResponse(SftEnt_MontaErro("INTERNAL_ERROR", cErrMsg, ""))
    FreeObj(oResp)
    FreeObj(oParams)
    AEval(aAllLinhas, {|o| FreeObj(o)})
    RestArea(aArea)
Return .T.
End Sequence

ConOut("[ZSFTENTAPI] total=" + cValToChar(nTotalReg) + ;
    " pages=" + cValToChar(nTotalPages) + ;
    " page=" + cValToChar(nPage) + ;
    " linhas_pagina=" + cValToChar(Len(aLinhas)) + ;
    " hasMore=" + IIf(lHasMore, "S", "N"))

oParams["data_ini"]   := cDataIni
oParams["data_fim"]   := cDataFim
oParams["filial_de"]  := cFilialDe
oParams["filial_ate"] := cFilialAte
oParams["entrsa"]     := cEntrSa
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
AEval(aAllLinhas, {|o| FreeObj(o)})
RestArea(aArea)

Return .T.

Static Function SftEnt_MontaErro(cCode, cMessage, cDetails)
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
