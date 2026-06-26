#Include "Protheus.ch"
#Include "restful.ch"
#Include "APWEBSRV.ch"

/*/{Protheus.doc} ZSFTENTAPI
API REST do Livro Fiscal via consulta SQL direta na tabela SFT.

Endpoint: GET /rest/zsftentapi/api/v1/sftent

Parametros:
  data_ini      = data inicial YYYYMMDD  (obrigatorio) - filtra por FT_ENTRADA
  data_fim      = data final   YYYYMMDD  (obrigatorio) - filtra por FT_ENTRADA
  filial_de     = filial inicial (default "")
  filial_ate    = filial final   (default "zzzzzzzzz")
  cfop_inc      = CFOPs a incluir, separados por virgula (default "" = sem filtro)
                  Mantem apenas linhas cujo FT_CFOP CONTENHA (substring) algum dos codigos informados.
  cfop_exc      = CFOPs a excluir, separados por virgula (default "" = sem filtro)
                  Remove linhas cujo FT_CFOP CONTENHA (substring) algum dos codigos informados.
  tes_inc       = TES a incluir, separados por virgula (default "" = sem filtro)
                  Mantem apenas linhas cujo FT_TES CONTENHA (substring) algum dos codigos informados.
  tes_exc       = TES a excluir, separados por virgula (default "" = sem filtro)
                  Remove linhas cujo FT_TES CONTENHA (substring) algum dos codigos informados.
  especie_inc   = Especies a incluir, separadas por virgula (default "" = sem filtro)
                  Mantem apenas linhas cujo FT_ESPECIE CONTENHA (substring) algum dos codigos informados.
  especie_exc   = Especies a excluir, separadas por virgula (default "" = sem filtro)
                  Remove linhas cujo FT_ESPECIE CONTENHA (substring) algum dos codigos informados.
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
  filial, nf, tes, emissao, entrada, cliefor, estado, cfop, especie, quant,
  valcont, aliqicm, baseicm, valicm, isenicm, outricm,
  icmscom, icmsdif, difal, vfcpdif, icmsret,
  produto, cstpis, codbcc, valpis, valcof, valipi, tipomov

@author Equipe Desenvolvimento
@since 27/05/2026
@version 1.7
/*/

wsrestful ZSFTENTAPI description "SFT - Livro Fiscal SQL Direto"

    wsdata page           as string
    wsdata pageSize       as string
    wsdata data_ini       as string
    wsdata data_fim       as string
    wsdata filial_de      as string
    wsdata filial_ate     as string
    wsdata cfop_inc       as string
    wsdata cfop_exc       as string
    wsdata tes_inc        as string
    wsdata tes_exc        as string
    wsdata especie_inc    as string
    wsdata especie_exc    as string

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
Local cCfopInc   := AllTrim(Self:cfop_inc)
Local cCfopExc   := AllTrim(Self:cfop_exc)
Local cTesInc    := AllTrim(Self:tes_inc)
Local cTesExc    := AllTrim(Self:tes_exc)
Local cEspecieInc := AllTrim(Self:especie_inc)
Local cEspecieExc := AllTrim(Self:especie_exc)
Local aCfopInc   := {}
Local aCfopExc   := {}
Local aTesInc    := {}
Local aTesExc    := {}
Local aEspecieInc := {}
Local aEspecieExc := {}
Local lFiltraLista := .F.
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

// --- Parse de listas CFOP/TES/Especie (contem/nao contem) ---
aCfopInc := SftEnt_ParseLista(cCfopInc)
aCfopExc := SftEnt_ParseLista(cCfopExc)
aTesInc  := SftEnt_ParseLista(cTesInc)
aTesExc  := SftEnt_ParseLista(cTesExc)
aEspecieInc := SftEnt_ParseLista(cEspecieInc)
aEspecieExc := SftEnt_ParseLista(cEspecieExc)
lFiltraLista := (Len(aCfopInc) > 0 .Or. Len(aCfopExc) > 0 .Or. Len(aTesInc) > 0 .Or. Len(aTesExc) > 0 .Or. ;
    Len(aEspecieInc) > 0 .Or. Len(aEspecieExc) > 0)

ConOut("[ZSFTENTAPI] data=" + cDataIni + "/" + cDataFim + ;
    " filial_de=" + cFilialDe + " filial_ate=" + cFilialAte + ;
    " cfop_inc=" + cCfopInc + " cfop_exc=" + cCfopExc + ;
    " tes_inc=" + cTesInc + " tes_exc=" + cTesExc + ;
    " especie_inc=" + cEspecieInc + " especie_exc=" + cEspecieExc + ;
    " page=" + cValToChar(nPage) + " pageSize=" + cValToChar(nPageSize))

// --- WHERE ---
cWhere := " D_E_L_E_T_ = ' '" 
cWhere += " AND FT_DTCANC = ' ' "
cWhere += " AND FT_ENTRADA BETWEEN '" + cDataIni + "' AND '" + cDataFim + "'"
cWhere += " AND FT_FILIAL BETWEEN '" + cFilialDe + "' AND '" + cFilialAte + "'"

// --- SQL ---
cSql := " SELECT"
cSql += "     FT_FILIAL,"
cSql += "     FT_NFISCAL,"
cSql += "     FT_TES,"
cSql += "     FT_EMISSAO,"
cSql += "     FT_ENTRADA,"
cSql += "     FT_CLIEFOR,"
cSql += "     FT_ESTADO,"
cSql += "     FT_CFOP,"
cSql += "     FT_ESPECIE,"
cSql += "     FT_QUANT,"
cSql += "     FT_VALCONT,"
cSql += "     FT_ALIQICM,"
cSql += "     FT_BASEICM,"
cSql += "     FT_VALICM,"
cSql += "     FT_ISENICM,"
cSql += "     FT_OUTRICM,"
cSql += "     FT_ICMSCOM,"
cSql += "     FT_ICMSDIF,"
cSql += "     FT_DIFAL,"
cSql += "     FT_VFCPDIF,"
cSql += "     FT_ICMSRET,"
cSql += "     FT_PRODUTO,"
cSql += "     FT_CSTPIS,"
cSql += "     FT_CODBCC,"
cSql += "     FT_VALPIS,"
cSql += "     FT_VALCOF,"
cSql += "     FT_VALIPI,"
cSql += "     FT_TIPOMOV"
cSql += " FROM " + cTabela
cSql += " WHERE " + cWhere
cSql += " ORDER BY FT_ENTRADA, FT_FILIAL, FT_NFISCAL"

ConOut("[ZSFTENTAPI] SQL montado | tabela=" + cTabela)

Begin Sequence
    dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .T., .F.)
    TCSetField(cAlias, "FT_EMISSAO", "D",  8, 0)
    TCSetField(cAlias, "FT_ENTRADA", "D",  8, 0)
    TCSetField(cAlias, "FT_QUANT",   "N", 16, 3)
    TCSetField(cAlias, "FT_VALCONT", "N", 16, 2)
    TCSetField(cAlias, "FT_ALIQICM", "N",  8, 4)
    TCSetField(cAlias, "FT_BASEICM", "N", 16, 2)
    TCSetField(cAlias, "FT_VALICM",  "N", 16, 2)
    TCSetField(cAlias, "FT_ISENICM", "N", 16, 2)
    TCSetField(cAlias, "FT_OUTRICM", "N", 16, 2)
    TCSetField(cAlias, "FT_ICMSCOM", "N", 16, 2)
    TCSetField(cAlias, "FT_ICMSDIF", "N", 16, 2)
    TCSetField(cAlias, "FT_DIFAL",   "N", 16, 2)
    TCSetField(cAlias, "FT_VFCPDIF", "N", 16, 2)
    TCSetField(cAlias, "FT_ICMSRET", "N", 16, 2)
    TCSetField(cAlias, "FT_VALPIS",  "N", 16, 2)
    TCSetField(cAlias, "FT_VALCOF",  "N", 16, 2)
    TCSetField(cAlias, "FT_VALIPI",  "N", 16, 2)

    (cAlias)->(DbGoTop())
    While !(cAlias)->(Eof())
        oLinha := JsonObject():New()
        oLinha["filial"]   := AllTrim((cAlias)->FT_FILIAL)
        oLinha["nf"]       := AllTrim((cAlias)->FT_NFISCAL)
        oLinha["tes"]      := AllTrim((cAlias)->FT_TES)
        oLinha["emissao"]  := DtoC((cAlias)->FT_EMISSAO)
        oLinha["entrada"]  := DtoC((cAlias)->FT_ENTRADA)
        oLinha["cliefor"]  := AllTrim((cAlias)->FT_CLIEFOR)
        oLinha["estado"]   := AllTrim((cAlias)->FT_ESTADO)
        oLinha["cfop"]     := AllTrim((cAlias)->FT_CFOP)
        oLinha["especie"]  := AllTrim((cAlias)->FT_ESPECIE)
        oLinha["quant"]    := Round((cAlias)->FT_QUANT,   3)
        oLinha["valcont"]  := Round((cAlias)->FT_VALCONT, 2)
        oLinha["aliqicm"]  := Round((cAlias)->FT_ALIQICM, 4)
        oLinha["baseicm"]  := Round((cAlias)->FT_BASEICM, 2)
        oLinha["valicm"]   := Round((cAlias)->FT_VALICM,  2)
        oLinha["isenicm"]  := Round((cAlias)->FT_ISENICM, 2)
        oLinha["outricm"]  := Round((cAlias)->FT_OUTRICM, 2)
        oLinha["icmscom"]  := Round((cAlias)->FT_ICMSCOM, 2)
        oLinha["icmsdif"]  := Round((cAlias)->FT_ICMSDIF, 2)
        oLinha["difal"]    := Round((cAlias)->FT_DIFAL,   2)
        oLinha["vfcpdif"]  := Round((cAlias)->FT_VFCPDIF, 2)
        oLinha["icmsret"]  := Round((cAlias)->FT_ICMSRET, 2)
        oLinha["produto"]  := AllTrim((cAlias)->FT_PRODUTO)
        oLinha["cstpis"]   := AllTrim((cAlias)->FT_CSTPIS)
        oLinha["codbcc"]   := AllTrim((cAlias)->FT_CODBCC)
        oLinha["valpis"]   := Round((cAlias)->FT_VALPIS,  2)
        oLinha["valcof"]   := Round((cAlias)->FT_VALCOF,  2)
        oLinha["valipi"]   := Round((cAlias)->FT_VALIPI,  2)
        oLinha["tipomov"]  := AllTrim((cAlias)->FT_TIPOMOV)

        If !lFiltraLista .Or. SftEnt_PassaFiltro(AllTrim((cAlias)->FT_CFOP), AllTrim((cAlias)->FT_TES), AllTrim((cAlias)->FT_ESPECIE), ;
                aCfopInc, aCfopExc, aTesInc, aTesExc, aEspecieInc, aEspecieExc)
            AAdd(aAllLinhas, oLinha)
        Else
            FreeObj(oLinha)
        EndIf
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
oParams["cfop_inc"]   := cCfopInc
oParams["cfop_exc"]   := cCfopExc
oParams["tes_inc"]    := cTesInc
oParams["tes_exc"]    := cTesExc
oParams["especie_inc"] := cEspecieInc
oParams["especie_exc"] := cEspecieExc
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

/*/{Protheus.doc} SftEnt_ParseLista
Converte string "1101, 2101,3102" em array de strings trim+upper:
{"1101","2101","3102"}. Retorna array vazio se a string for vazia.
/*/
Static Function SftEnt_ParseLista(cTexto)
Local aRet   := {}
Local aSplit := {}
Local nI     := 0
Local cItem  := ""

If Empty(cTexto)
Return aRet
EndIf

aSplit := StrTokArr(cTexto, ",")
For nI := 1 To Len(aSplit)
    cItem := Upper(AllTrim(aSplit[nI]))
    If !Empty(cItem)
        AAdd(aRet, cItem)
    EndIf
Next nI

Return aRet

/*/{Protheus.doc} SftEnt_Contem
Retorna .T. se cValor contiver (substring) algum dos itens de aLista.
/*/
Static Function SftEnt_Contem(cValor, aLista)
Local nI     := 0
Local cValUp := Upper(cValor)

For nI := 1 To Len(aLista)
    If aLista[nI] $ cValUp
        Return .T.
    EndIf
Next nI

Return .F.

/*/{Protheus.doc} SftEnt_PassaFiltro
Combina os 6 filtros (cfop_inc, cfop_exc, tes_inc, tes_exc, especie_inc, especie_exc):
  - Se aCfopInc nao vazio: cCfop deve conter ALGUM item de aCfopInc, senao reprova.
  - Se aCfopExc nao vazio: cCfop NAO PODE conter NENHUM item de aCfopExc, senao reprova.
  - Mesma logica para TES com cTes/aTesInc/aTesExc.
  - Mesma logica para Especie com cEspecie/aEspecieInc/aEspecieExc.
Retorna .T. somente se passar em todos os criterios ativos.
/*/
Static Function SftEnt_PassaFiltro(cCfop, cTes, cEspecie, aCfopInc, aCfopExc, aTesInc, aTesExc, aEspecieInc, aEspecieExc)

If Len(aCfopInc) > 0 .And. !SftEnt_Contem(cCfop, aCfopInc)
Return .F.
EndIf

If Len(aCfopExc) > 0 .And. SftEnt_Contem(cCfop, aCfopExc)
Return .F.
EndIf

If Len(aTesInc) > 0 .And. !SftEnt_Contem(cTes, aTesInc)
Return .F.
EndIf

If Len(aTesExc) > 0 .And. SftEnt_Contem(cTes, aTesExc)
Return .F.
EndIf

If Len(aEspecieInc) > 0 .And. !SftEnt_Contem(cEspecie, aEspecieInc)
Return .F.
EndIf

If Len(aEspecieExc) > 0 .And. SftEnt_Contem(cEspecie, aEspecieExc)
Return .F.
EndIf

Return .T.
