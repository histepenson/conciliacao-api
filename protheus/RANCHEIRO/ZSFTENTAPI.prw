#Include "Protheus.ch"
#Include "restful.ch"
#Include "APWEBSRV.ch"

/*/{Protheus.doc} ZSFTENTAPI
API REST do Livro Fiscal via consulta SQL direta na tabela SFT.

FONTE ESPECIFICO DA EMPRESA RANCHEIRO -- nao usar em outras empresas.
Diferenca em relacao ao fonte generico (protheus/ZSFTENTAPI.prw): sempre
inclui via UNION ALL as notas de saida da SF2 com FT_SERIE IN ('LOC','ND'),
que nao geram livro fiscal (nao entram na SFT) nessa empresa. Sem parametro
-- e' sempre ativo aqui.

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
  tipo_mov      = E (entrada) ou S (saida) -- filtra por FT_TIPOMOV (default "" = ambos)
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
  filial, nf, serie, tes, emissao, entrada, cliefor, estado, cfop, especie, quant,
  valcont, aliqicm, baseicm, valicm, isenicm, outricm,
  icmscom, icmsdif, difal, vfcpdif, icmsret,
  produto, cstpis, codbcc, valpis, valcof, valipi, tipomov

@author Equipe Desenvolvimento
@since 27/05/2026
@version 1.9
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
    wsdata tipo_mov       as string

    wsmethod GET getSftEnt description "Livro Fiscal SFT SQL direto" wssyntax "/api/v1/sftent" PATH "/api/v1/sftent"

EndwsRestFul

wsmethod GET getSftEnt WSRESTFUL ZSFTENTAPI
Local aArea      := GetArea()
Local oResp      := JsonObject():New()
Local oParams    := JsonObject():New()
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
Local cTipoMov   := Upper(AllTrim(Self:tipo_mov))
Local aCfopInc   := {}
Local aCfopExc   := {}
Local aTesInc    := {}
Local aTesExc    := {}
Local aEspecieInc := {}
Local aEspecieExc := {}
Local cFiltroCfopInc       := ""
Local cFiltroCfopExc       := ""
Local cFiltroTesInc        := ""
Local cFiltroTesExc        := ""
Local cFiltroEspecieInc    := ""
Local cFiltroEspecieExc    := ""
Local cFiltroCfopIncSF2    := ""
Local cFiltroTesIncSF2     := ""
Local cFiltroEspecieIncSF2 := ""
Local cFiltroEspecieExcSF2 := ""
Local nPage      := Max(1, Val(AllTrim(Self:page)))
Local nPageSize  := Val(AllTrim(Self:pageSize))

Local nTotalReg   := 0
Local nTotalPages := 1
Local nOffset     := 0
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

If !Empty(cTipoMov) .And. cTipoMov <> "E" .And. cTipoMov <> "S"
    Self:SetResponse(SftEnt_MontaErro("VALIDATION_ERROR", "Parametro tipo_mov deve ser E (entrada), S (saida) ou vazio (ambos)", ""))
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

// --- Filtros de lista (contem/nao contem) traduzidos para SQL (CHARINDEX) --
// para que a paginacao (ROW_NUMBER/COUNT(*) OVER) mais abaixo ja considere
// so' as linhas que passam no filtro. Antes esse filtro era feito em ADVPL
// apos ler cada linha do cursor, o que exigia reexecutar e percorrer o
// resultado inteiro (sem LIMIT) a cada pagina pedida -- essa retencao/varredura
// completa a cada pagina era o que estourava a memoria do AppServer em cargas
// grandes.
// No bloco SF2 (notas LOC/ND) os campos FT_CFOP/FT_TES nao existem de fato
// (vem como '' fixo na projecao) -- por isso o filtro de inclusao usa a
// string literal '' como "campo": nunca casa com nenhum codigo informado,
// excluindo essas linhas quando cfop_inc/tes_inc estao ativos, igual ao
// comportamento original em ADVPL (SftEnt_Contem("", lista) sempre .F.).
cFiltroCfopInc    := SftEnt_FiltroCharIdx("FT_CFOP",    aCfopInc,    .F.)
cFiltroCfopExc    := SftEnt_FiltroCharIdx("FT_CFOP",    aCfopExc,    .T.)
cFiltroTesInc     := SftEnt_FiltroCharIdx("FT_TES",     aTesInc,     .F.)
cFiltroTesExc     := SftEnt_FiltroCharIdx("FT_TES",     aTesExc,     .T.)
cFiltroEspecieInc := SftEnt_FiltroCharIdx("FT_ESPECIE", aEspecieInc, .F.)
cFiltroEspecieExc := SftEnt_FiltroCharIdx("FT_ESPECIE", aEspecieExc, .T.)

cFiltroCfopIncSF2    := SftEnt_FiltroCharIdx("''",         aCfopInc,    .F.)
cFiltroTesIncSF2     := SftEnt_FiltroCharIdx("''",         aTesInc,     .F.)
cFiltroEspecieIncSF2 := SftEnt_FiltroCharIdx("F2_ESPECIE", aEspecieInc, .F.)
cFiltroEspecieExcSF2 := SftEnt_FiltroCharIdx("F2_ESPECIE", aEspecieExc, .T.)

ConOut("[ZSFTENTAPI] data=" + cDataIni + "/" + cDataFim + ;
    " filial_de=" + cFilialDe + " filial_ate=" + cFilialAte + ;
    " cfop_inc=" + cCfopInc + " cfop_exc=" + cCfopExc + ;
    " tes_inc=" + cTesInc + " tes_exc=" + cTesExc + ;
    " especie_inc=" + cEspecieInc + " especie_exc=" + cEspecieExc + ;
    " tipo_mov=" + cTipoMov + ;
    " page=" + cValToChar(nPage) + " pageSize=" + cValToChar(nPageSize))

// --- WHERE ---
cWhere := " D_E_L_E_T_ = ' '"
cWhere += " AND FT_DTCANC = ' ' "
cWhere += " AND FT_ENTRADA BETWEEN '" + cDataIni + "' AND '" + cDataFim + "'"
cWhere += " AND FT_FILIAL BETWEEN '" + cFilialDe + "' AND '" + cFilialAte + "'"
If !Empty(cTipoMov)
    cWhere += " AND FT_TIPOMOV = '" + cTipoMov + "'"
EndIf
If !Empty(cFiltroCfopInc)
    cWhere += " AND " + cFiltroCfopInc
EndIf
If !Empty(cFiltroCfopExc)
    cWhere += " AND " + cFiltroCfopExc
EndIf
If !Empty(cFiltroTesInc)
    cWhere += " AND " + cFiltroTesInc
EndIf
If !Empty(cFiltroTesExc)
    cWhere += " AND " + cFiltroTesExc
EndIf
If !Empty(cFiltroEspecieInc)
    cWhere += " AND " + cFiltroEspecieInc
EndIf
If !Empty(cFiltroEspecieExc)
    cWhere += " AND " + cFiltroEspecieExc
EndIf

// --- Paginacao no proprio SQL via ROW_NUMBER() OVER() -- mesma tecnica do
// ZCT2RAZCT5/ZCT2RAZAPI: evita reexecutar e percorrer o resultado inteiro
// (pode passar de 200 mil linhas) a cada pagina pedida. COUNT(*) OVER() traz
// o total de linhas (ja filtrado) em cada linha devolvida, entao uma unica
// execucao ja da a pagina E o total.
cSql := " SELECT * FROM ("
cSql += "   SELECT *,"
cSql += "     ROW_NUMBER() OVER (ORDER BY FT_ENTRADA, FT_FILIAL, FT_NFISCAL) AS RN,"
cSql += "     COUNT(*) OVER() AS TOTAL_REG"
cSql += "   FROM ("
cSql += "     SELECT"
cSql += "         FT_FILIAL,"
cSql += "         FT_NFISCAL,"
cSql += "         FT_SERIE,"
cSql += "         FT_TES,"
cSql += "         FT_EMISSAO,"
cSql += "         FT_ENTRADA,"
cSql += "         FT_CLIEFOR,"
cSql += "         FT_ESTADO,"
cSql += "         FT_CFOP,"
cSql += "         FT_ESPECIE,"
cSql += "         FT_QUANT,"
cSql += "         FT_VALCONT,"
cSql += "         FT_ALIQICM,"
cSql += "         FT_BASEICM,"
cSql += "         FT_VALICM,"
cSql += "         FT_ISENICM,"
cSql += "         FT_OUTRICM,"
cSql += "         FT_ICMSCOM,"
cSql += "         FT_ICMSDIF,"
cSql += "         FT_DIFAL,"
cSql += "         FT_VFCPDIF,"
cSql += "         FT_ICMSRET,"
cSql += "         FT_PRODUTO,"
cSql += "         FT_CSTPIS,"
cSql += "         FT_CODBCC,"
cSql += "         FT_VALPIS,"
cSql += "         FT_VALCOF,"
cSql += "         FT_VALIPI,"
cSql += "         FT_TIPOMOV"
cSql += "     FROM " + cTabela
cSql += "     WHERE " + cWhere

// --- UNION ALL: notas de saida da SF2 com serie LOC/ND, que nao geram livro
// fiscal (nao entram na SFT) -- particularidade desta empresa (Rancheiro).
// Sempre ativo aqui. So' entram quando o filtro de tipo_mov nao exclui saida
// (essas linhas sao sempre TIPOMOV = 'S').
If (Empty(cTipoMov) .Or. cTipoMov == "S")
    cSql += "     UNION ALL"
    cSql += "     SELECT"
    cSql += "         F2_FILIAL       AS FT_FILIAL,"
    cSql += "         F2_DOC          AS FT_NFISCAL,"
    cSql += "         F2_SERIE        AS FT_SERIE,"
    cSql += "         ''              AS FT_TES,"
    cSql += "         F2_EMISSAO      AS FT_EMISSAO,"
    cSql += "         F2_EMISSAO      AS FT_ENTRADA,"
    cSql += "         F2_CLIENTE      AS FT_CLIEFOR,"
    cSql += "         F2_EST          AS FT_ESTADO,"
    cSql += "         ''              AS FT_CFOP,"
    cSql += "         F2_ESPECIE      AS FT_ESPECIE,"
    cSql += "         0               AS FT_QUANT,"
    cSql += "         SUM(F2_VALBRUT) AS FT_VALCONT,"
    cSql += "         0               AS FT_ALIQICM,"
    cSql += "         0               AS FT_BASEICM,"
    cSql += "         0               AS FT_VALICM,"
    cSql += "         0               AS FT_ISENICM,"
    cSql += "         0               AS FT_OUTRICM,"
    cSql += "         0               AS FT_ICMSCOM,"
    cSql += "         0               AS FT_ICMSDIF,"
    cSql += "         0               AS FT_DIFAL,"
    cSql += "         0               AS FT_VFCPDIF,"
    cSql += "         0               AS FT_ICMSRET,"
    cSql += "         ''              AS FT_PRODUTO,"
    cSql += "         ''              AS FT_CSTPIS,"
    cSql += "         ''              AS FT_CODBCC,"
    cSql += "         SUM(F2_VALIMP6) AS FT_VALPIS,"
    cSql += "         SUM(F2_VALIMP5) AS FT_VALCOF,"
    cSql += "         0               AS FT_VALIPI,"
    cSql += "         'S'             AS FT_TIPOMOV"
    cSql += "     FROM " + RetSqlName("SF2")
    cSql += "     WHERE D_E_L_E_T_ = ' '"
    cSql += "       AND F2_FILIAL BETWEEN '" + cFilialDe + "' AND '" + cFilialAte + "'"
    cSql += "       AND F2_EMISSAO BETWEEN '" + cDataIni + "' AND '" + cDataFim + "'"
    cSql += "       AND F2_SERIE IN ('LOC','ND')"
    If !Empty(cFiltroCfopIncSF2)
        cSql += "       AND " + cFiltroCfopIncSF2
    EndIf
    If !Empty(cFiltroTesIncSF2)
        cSql += "       AND " + cFiltroTesIncSF2
    EndIf
    If !Empty(cFiltroEspecieIncSF2)
        cSql += "       AND " + cFiltroEspecieIncSF2
    EndIf
    If !Empty(cFiltroEspecieExcSF2)
        cSql += "       AND " + cFiltroEspecieExcSF2
    EndIf
    cSql += "     GROUP BY F2_FILIAL, F2_DOC, F2_SERIE, F2_EMISSAO, F2_CLIENTE, F2_EST, F2_ESPECIE"
EndIf

cSql += "   ) AS SFTUNION"
cSql += " ) AS PAGINADO"
cSql += " WHERE RN > " + cValToChar(nOffset) + " AND RN <= " + cValToChar(nOffset + nPageSize)
cSql += " ORDER BY RN"

ConOut("[ZSFTENTAPI] SQL montado | tabela=" + cTabela + ;
    " offset=" + cValToChar(nOffset) + " pageSize=" + cValToChar(nPageSize))

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
    TCSetField(cAlias, "TOTAL_REG",  "N", 10, 0)
    TCSetField(cAlias, "RN",         "N", 10, 0)

    (cAlias)->(DbGoTop())
    // O SQL ja devolve so' a pagina pedida (filtro por RN) -- toda linha lida
    // aqui pertence a pagina, sem precisar filtrar/pular nada em ADVPL.
    // TOTAL_REG vem do COUNT(*) OVER() (mesmo valor em toda linha) e reflete
    // o total ja filtrado, ANTES do corte por RN.
    If !(cAlias)->(Eof())
        nTotalReg := (cAlias)->TOTAL_REG
    EndIf
    While !(cAlias)->(Eof())
        oLinha := JsonObject():New()
        oLinha["filial"]   := AllTrim((cAlias)->FT_FILIAL)
        oLinha["nf"]       := AllTrim((cAlias)->FT_NFISCAL)
        oLinha["serie"]    := AllTrim((cAlias)->FT_SERIE)
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
    cErrMsg := "Erro ao consultar SFT"
    If ValType(oError) == "O"
        cErrMsg += ": " + AllTrim(oError:Description)
    EndIf
    ConOut("[ZSFTENTAPI] ERRO: " + cErrMsg)
    Self:SetResponse(SftEnt_MontaErro("INTERNAL_ERROR", cErrMsg, ""))
    FreeObj(oResp)
    FreeObj(oParams)
    AEval(aLinhas, {|o| FreeObj(o)})
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
oParams["tipo_mov"]    := cTipoMov
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

/*/{Protheus.doc} SftEnt_FiltroCharIdx
Monta condicao SQL equivalente ao filtro "contem" (substring) que antes era
avaliado em ADVPL com o operador $. Usa CHARINDEX em vez de LIKE para nao
precisar escapar coringas (%, _) vindos do usuario. cCampo pode ser um nome
de coluna ou uma expressao SQL literal (ex.: "''"). Retorna "" (sem filtro)
se aLista estiver vazia.
/*/
Static Function SftEnt_FiltroCharIdx(cCampo, aLista, lExcluir)
Local cRet    := ""
Local nI      := 0
Local cItem   := ""
Local cOper   := IIf(lExcluir, " = 0", " > 0")
Local cConcat := IIf(lExcluir, " AND ", " OR ")

If Len(aLista) == 0
Return ""
EndIf

cRet := "("
For nI := 1 To Len(aLista)
    If nI > 1
        cRet += cConcat
    EndIf
    cItem := StrTran(aLista[nI], "'", "''")
    cRet += "CHARINDEX('" + cItem + "', " + cCampo + ")" + cOper
Next nI
cRet += ")"

Return cRet
