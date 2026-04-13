#Include "Protheus.ch"
#INCLUDE "restful.CH"
#Include "APWEBSRV.ch"
#Include "FWCOMMAND.CH"

/*/{Protheus.doc} ZCTBR480API
API REST baseada no relatorio CTBR480 (Razao Contabil por Item).
A base de dados passa a ser gerada pelo mesmo fluxo do relatorio padrao
(CTBGerRaz + SaldTotCT4), reduzindo divergencias funcionais em relacao ao
fonte ctbr480.prw.

Endpoint: GET /rest/api/v1/ctbr480

Retorno:
  parametros        = parametros efetivos usados na consulta
  total_registros   = total de linhas retornadas pela API
  total_pages       = total de paginas da API
  page              = pagina atual
  linhas            = movimentos do razao em formato JSON

Campos principais por linha:
  data
  lote_sub_doc_linha
  historico
  complemento_historico
  xpartida
  c_custo
  item_conta
  cod_cl_val
  debito
  credito
  saldo_anterior
  saldo_atual
  conta
  desc_item
  desc_conta
  normal_item
  normal_cta

@author Equipe Desenvolvimento
@since 23/03/2026
@version 2.0
/*/

Static __lBlind := IsBlind()
Static lIsRedStor := FindFunction("IsRedStor") .And. IsRedStor()

wsrestful ZCTBR480API description "CTBR480 - Razao Contabil por Item"

	wsdata page             as string
	wsdata pageSize         as string

	wsdata item_de          as string
	wsdata item_ate         as string
	wsdata data_ini         as string
	wsdata data_fim         as string
	wsdata moeda            as string
	wsdata saldo            as string
	wsdata set_of_books     as string
	wsdata conta_de         as string
	wsdata conta_ate        as string
	wsdata custo_de         as string
	wsdata custo_ate        as string
	wsdata clvl_de          as string
	wsdata clvl_ate         as string
	wsdata vlr_zerado       as string
	wsdata consid_filiais   as string
	wsdata filial_de        as string
	wsdata filial_ate       as string

	// Aderencia funcional ao CTBR480 padrao
	wsdata analitico        as string   // 1=analitico / 2=sintetico por dia
	wsdata contas_sem_mov   as string   // 1=imprime / 2=nao imprime
	wsdata imprime_custo    as string   // 1=sim / 2=nao
	wsdata imprime_clvl     as string   // 1=sim / 2=nao
	wsdata totaliza_conta   as string   // 1=sim / 2=nao

	wsmethod GET getRazao description "Razao Contabil por Item" wssyntax "/api/v1/ctbr480" PATH "/api/v1/ctbr480"

EndwsRestFul

wsmethod GET getRazao WSRESTFUL ZCTBR480API

Local aArea         := GetArea()
Local oResp         := JsonObject():New()
Local oParams       := JsonObject():New()
Local aAllLinhas    := {}
Local aLinhas       := {}
Local oLinha        := Nil
Local oError        := Nil
Local cArqTmp       := ""
Local aSetOfBook    := {}
Local aCtbMoeda     := {}
Local aSelFil       := {}
Local aSaldoAnt     := {}
Local aSaldo        := {}

Local cDataIni      := AllTrim(Self:data_ini)
Local cDataFim      := AllTrim(Self:data_fim)
Local cItemDe       := AllTrim(Self:item_de)
Local cItemAte      := AllTrim(Self:item_ate)
Local cSaldo        := ""
Local cSetBook      := AllTrim(Self:set_of_books)
Local cContaDe      := AllTrim(Self:conta_de)
Local cContaAte     := AllTrim(Self:conta_ate)
Local cCustoDe      := AllTrim(Self:custo_de)
Local cCustoAte     := AllTrim(Self:custo_ate)
Local cClvlDe       := AllTrim(Self:clvl_de)
Local cClvlAte      := AllTrim(Self:clvl_ate)
Local cVlrZerado    := AllTrim(Self:vlr_zerado)
Local cConsidFil    := AllTrim(Self:consid_filiais)
Local cFilialDe     := AllTrim(Self:filial_de)
Local cFilialAte    := AllTrim(Self:filial_ate)
Local cSemMov       := AllTrim(Self:contas_sem_mov)
Local cImpCusto     := AllTrim(Self:imprime_custo)
Local cImpClvl      := AllTrim(Self:imprime_clvl)
Local cTotConta     := AllTrim(Self:totaliza_conta)
Local nPage         := Max(1, Val(AllTrim(Self:page)))
Local nPageSize     := Val(AllTrim(Self:pageSize))

Local dDataIni      := CtoD("")
Local dDataFim      := CtoD("")
Local nMoeda        := 1
Local nConsidFil    := 2
Local lPrintZero    := .F.
Local lAnalitico    := .T.
Local lNoMov        := .F.
Local lCusto        := .F.
Local lCLVL         := .F.
Local lTotConta     := .F.
Local lExterno      := .T.
Local cMoedaFmt     := "01"
Local nTotalReg     := 0
Local nTotalPages   := 1
Local nOffset       := 0
Local nRecAtual     := 0
Local nDecVlr       := 2
Local nDebito       := 0
Local nCredito      := 0
Local nSaldoAtu     := 0
Local nSaldoAntVal  := 0
Local cItemAnt      := ""
Local cItemAtual    := ""
Local dDataAnt      := CtoD("")
Local cContaAtual   := ""
Local cDescItem     := ""
Local cDescConta    := ""
Local cNormalItem   := ""
Local cNormalConta  := ""
Local cComplHist    := ""
Local nTamCusto     := 0
Local cFilCCIni     := ""
Local cFilCCFim     := ""
Local cFiltro       := ""

Self:SetContentType("application/json")

If Empty(cDataFim) .Or. Len(cDataFim) <> 8
	Self:SetResponse(CTB480MontaErro("VALIDATION_ERROR", ;
		"Parametro data_fim e obrigatorio no formato YYYYMMDD", ""))
	FreeObj(oResp)
	FreeObj(oParams)
	RestArea(aArea)
Return .T.
EndIf

Pergunte("CTR480", .F.)

dDataFim := StoD(cDataFim)
dDataIni := IIf(Len(cDataIni) == 8, StoD(cDataIni), StoD(Left(cDataFim, 4) + "0101"))

If Empty(dDataFim) .Or. Empty(dDataIni)
	Self:SetResponse(CTB480MontaErro("VALIDATION_ERROR", ;
		"Periodo invalido. Informe data_ini/data_fim no formato YYYYMMDD", ""))
	FreeObj(oResp)
	FreeObj(oParams)
	RestArea(aArea)
Return .T.
EndIf

If dDataIni > dDataFim
	Self:SetResponse(CTB480MontaErro("VALIDATION_ERROR", ;
		"Parametro data_ini nao pode ser maior que data_fim", ""))
	FreeObj(oResp)
	FreeObj(oParams)
	RestArea(aArea)
Return .T.
EndIf

nMoeda      := 1
cMoedaFmt   := "01"
cSaldo      := "1"
cSetBook    := IIf(Empty(cSetBook), mv_par07, cSetBook)
nConsidFil  := IIf(Empty(cConsidFil), 2, Val(cConsidFil))
lPrintZero  := (cVlrZerado == "1")
lAnalitico  := .T.
lNoMov      := (cSemMov == "1")
lCusto      := IIf(Empty(cImpCusto), !Empty(cCustoDe) .Or. !Empty(cCustoAte), cImpCusto == "1")
lCLVL       := IIf(Empty(cImpClvl), !Empty(cClvlDe) .Or. !Empty(cClvlAte), cImpClvl == "1")
lTotConta   := (cTotConta == "1")
nPageSize   := IIf(nPageSize <= 0 .Or. nPageSize > 2000, 500, nPageSize)

mv_par01 := cItemDe
mv_par02 := cItemAte
mv_par03 := dDataIni
mv_par04 := dDataFim
mv_par05 := cMoedaFmt
mv_par06 := cSaldo
mv_par07 := cSetBook
mv_par08 := 1
mv_par09 := IIf(lNoMov, 1, 2)
mv_par10 := 1
mv_par11 := IIf(lTotConta, 1, 2)
mv_par12 := cContaDe
mv_par13 := cContaAte
mv_par14 := IIf(lCusto, 1, 2)
mv_par15 := cCustoDe
mv_par16 := cCustoAte
mv_par17 := IIf(lCLVL, 1, 2)
mv_par18 := cClvlDe
mv_par19 := cClvlAte
mv_par20 := 2
mv_par21 := 1
mv_par22 := 999999
mv_par23 := 1
mv_par24 := 1
mv_par25 := 1
mv_par26 := 1
mv_par27 := IIf(lPrintZero, 1, 2)
mv_par28 := 1
mv_par29 := nConsidFil

If !Ct040Valid(mv_par07)
	Self:SetResponse(CTB480MontaErro("VALIDATION_ERROR", ;
		"Set of books invalido para o CTBR480", mv_par07))
	FreeObj(oResp)
	FreeObj(oParams)
	RestArea(aArea)
Return .T.
EndIf

aCtbMoeda := CtbMoeda(mv_par05)
If Empty(aCtbMoeda[1])
	Self:SetResponse(CTB480MontaErro("VALIDATION_ERROR", ;
		"Moeda invalida para o CTBR480", mv_par05))
	FreeObj(oResp)
	FreeObj(oParams)
	RestArea(aArea)
Return .T.
EndIf

aSetOfBook := CTBSetOf(mv_par07)
nDecVlr    := DecimalCTB(aSetOfBook, mv_par05)
nTamConta  := TamSX3("CT1_CONTA")[1]
nTamItem   := TamSX3("CTD_ITEM")[1]
nTamCusto  := TamSX3("CTT_CUSTO")[1]
nTamClvl   := TamSX3("CTH_CLVL")[1]

mv_par01 := IIf(Empty(AllTrim(mv_par01)), Space(nTamItem),  PadR(AllTrim(mv_par01), nTamItem))
mv_par02 := IIf(Empty(AllTrim(mv_par02)), Repl("Z", nTamItem), PadR(AllTrim(mv_par02), nTamItem))
mv_par12 := IIf(Empty(AllTrim(mv_par12)), Space(nTamConta),  PadR(AllTrim(mv_par12), nTamConta))
mv_par13 := IIf(Empty(AllTrim(mv_par13)), Repl("Z", nTamConta), PadR(AllTrim(mv_par13), nTamConta))
mv_par15 := IIf(Empty(AllTrim(mv_par15)), Space(nTamCusto),  PadR(AllTrim(mv_par15), nTamCusto))
mv_par16 := IIf(Empty(AllTrim(mv_par16)), Repl("Z", nTamCusto), PadR(AllTrim(mv_par16), nTamCusto))
mv_par18 := IIf(Empty(AllTrim(mv_par18)), Space(nTamClvl),   PadR(AllTrim(mv_par18), nTamClvl))
mv_par19 := IIf(Empty(AllTrim(mv_par19)), Repl("Z", nTamClvl),  PadR(AllTrim(mv_par19), nTamClvl))
nTamCusto  := TamSX3("CTT_CUSTO")[1]
cFilCCIni  := Space(nTamCusto)
cFilCCFim  := Repl("Z", nTamCusto)
aSelFil    := Z480SelFil(nConsidFil, cFilialDe, cFilialAte, "CT2")

ConOut("ZCTBR480API - periodo=" + DtoS(dDataIni) + " a " + DtoS(dDataFim) + ;
	" moeda=" + mv_par05 + " saldo=" + mv_par06 + ;
	" analitico=" + IIf(lAnalitico, "1", "2") + ;
	" filiais=" + cValToChar(Len(aSelFil)))

ConOut("ZCTBR480API - aSelFil=" + Z480FilTxt(aSelFil))
Begin Sequence

	ConOut("ZCTBR480API - antes CTBGerRaz filiais=" + Z480FilTxt(aSelFil))
    ConOut("ZCTBR480API - ranges item=[" + AllTrim(mv_par01) + " - " + AllTrim(mv_par02) + "] conta=[" + AllTrim(mv_par12) + " - " + AllTrim(mv_par13) + "]")
    ConOut("ZCTBR480API - ranges custo=[" + AllTrim(mv_par15) + " - " + AllTrim(mv_par16) + "] clvl=[" + AllTrim(mv_par18) + " - " + AllTrim(mv_par19) + "]")

	CTBGerRaz(Nil, Nil, Nil, .F., @cArqTmp, mv_par12, mv_par13, mv_par15, mv_par16, ;
		mv_par01, mv_par02, mv_par18, mv_par19, mv_par05, mv_par03, mv_par04, ;
		aSetOfBook, lNoMov, mv_par06, .T., "3", lAnalitico, Nil, Nil, cFiltro, Nil, aSelFil, lExterno)

    // No contexto REST, CTBGerRaz pode nao setar @cArqTmp por referencia
    // mas cria a area temporaria com alias literal "cArqTmp" (mesmo comportamento do ctbr480.prw original)
    If Empty(cArqTmp) .And. Select("cArqTmp") > 0
        cArqTmp := "cArqTmp"
    EndIf

    ConOut("ZCTBR480API - cArqTmp=[" + cArqTmp + "] select=" + cValToChar(Select(cArqTmp)) + " select_literal=" + cValToChar(Select("cArqTmp")))
    If !Empty(cArqTmp) .And. Select(cArqTmp) > 0
        ConOut("ZCTBR480API - cArqTmp reccount=" + cValToChar((cArqTmp)->(RecCount())))
    EndIf

	If !Empty(cArqTmp) .And. Select(cArqTmp) > 0

		(cArqTmp)->(DbGoTop())
		If Select("CTD") > 0
			CTD->(dbSetOrder(1))
		EndIf
		If Select("CT1") > 0
			CT1->(dbSetOrder(1))
		EndIf

		While !(cArqTmp)->(Eof())
		cItemAtual := AllTrim((cArqTmp)->ITEM)
		If cItemAtual != cItemAnt
			If lCusto
				aSaldoAnt := SaldTotCT4(cItemAtual, cItemAtual, mv_par15, mv_par16, mv_par12, mv_par13, dDataIni, mv_par05, mv_par06, aSelFil)
				aSaldo    := SaldTotCT4(cItemAtual, cItemAtual, mv_par15, mv_par16, mv_par12, mv_par13, (cArqTmp)->DATAL, mv_par05, mv_par06, aSelFil)
			Else
				aSaldoAnt := SaldTotCT4(cItemAtual, cItemAtual, cFilCCIni, cFilCCFim, mv_par12, mv_par13, dDataIni, mv_par05, mv_par06, aSelFil)
				aSaldo    := SaldTotCT4(cItemAtual, cItemAtual, cFilCCIni, cFilCCFim, mv_par12, mv_par13, (cArqTmp)->DATAL, mv_par05, mv_par06, aSelFil)
			EndIf

			If CTB480FilSemMov(lNoMov, aSaldo, dDataIni, cArqTmp)
				(cArqTmp)->(DbSkip())
				Loop
			EndIf

			cItemAnt     := cItemAtual
			nSaldoAntVal := CTB480SaldoArray(aSaldoAnt)
			nSaldoAtu    := nSaldoAntVal
			dDataAnt     := CtoD("")
		EndIf

		cContaAtual  := AllTrim((cArqTmp)->CONTA)
		cDescItem    := CTB480DescItem((cArqTmp)->ITEM, mv_par05)
		cDescConta   := DescConta((cArqTmp)->CONTA, mv_par05)
		cNormalItem  := CTB480NormalItem((cArqTmp)->ITEM)
		cNormalConta := NormalConta((cArqTmp)->CONTA)

		nDebito := (cArqTmp)->LANCDEB
		nCredito := (cArqTmp)->LANCCRD
		If lIsRedStor
			nSaldoAtu := nSaldoAtu - nDebito + nCredito
		Else
			nSaldoAtu := Round(NoRound(nSaldoAtu - nDebito + nCredito, nDecVlr + 1), nDecVlr)
		EndIf
		cComplHist := CTB480HistCompl(cArqTmp)

		oLinha := JsonObject():New()
		oLinha["data"]                 := DtoS((cArqTmp)->DATAL)
		oLinha["lote_sub_doc_linha"]   := AllTrim((cArqTmp)->LOTE) + AllTrim((cArqTmp)->SUBLOTE) + AllTrim((cArqTmp)->DOC) + AllTrim((cArqTmp)->LINHA)
		oLinha["historico"]            := AllTrim((cArqTmp)->HISTORICO)
		oLinha["complemento_historico"]:= cComplHist
		oLinha["xpartida"]             := AllTrim((cArqTmp)->XPARTIDA)
		oLinha["c_custo"]              := AllTrim((cArqTmp)->CCUSTO)
		oLinha["item_conta"]           := AllTrim((cArqTmp)->ITEM)
		oLinha["cod_cl_val"]           := AllTrim((cArqTmp)->CLVL)
		oLinha["debito"]               := Round(nDebito, 2)
		oLinha["credito"]              := Round(nCredito, 2)
		oLinha["saldo_anterior"]       := Round(nSaldoAntVal, 2)
		oLinha["saldo_atual"]          := Round(nSaldoAtu, 2)
		oLinha["conta"]                := cContaAtual
		oLinha["desc_item"]            := cDescItem
		oLinha["desc_conta"]           := cDescConta
		oLinha["normal_item"]          := cNormalItem
		oLinha["normal_cta"]           := cNormalConta
		oLinha["modo"]                 := "analitico"
		aAdd(aAllLinhas, oLinha)
		(cArqTmp)->(DbSkip())
	EndDo

		If Select(cArqTmp) > 0
			(cArqTmp)->(DbCloseArea())
		EndIf
	EndIf

	Recover Using oError
	If !Empty(cArqTmp) .And. Select(cArqTmp) > 0
		(cArqTmp)->(DbCloseArea())
	EndIf
	CtbRazClean()
	SetRestFail(500, "Erro interno")
	Self:SetResponse(CTB480MontaErro("INTERNAL_ERROR", ;
		"Erro interno ao consultar razao contabil", oError:Description))
	FreeObj(oResp)
	FreeObj(oParams)
	AEval(aAllLinhas, {|o| FreeObj(o)})
	RestArea(aArea)
Return .T.
End Sequence

CtbRazClean()

nTotalReg   := Len(aAllLinhas)
nTotalPages := Max(1, Int((nTotalReg + nPageSize - 1) / nPageSize))
nOffset     := (nPage - 1) * nPageSize

While nRecAtual < nPageSize .And. (nOffset + nRecAtual + 1) <= nTotalReg
	aAdd(aLinhas, aAllLinhas[nOffset + nRecAtual + 1])
	nRecAtual++
EndDo

oParams["data_ini"]         := DtoS(dDataIni)
oParams["data_fim"]         := DtoS(dDataFim)
oParams["item_de"]          := mv_par01
oParams["item_ate"]         := mv_par02
oParams["conta_de"]         := mv_par12
oParams["conta_ate"]        := mv_par13
oParams["custo_de"]         := mv_par15
oParams["custo_ate"]        := mv_par16
oParams["clvl_de"]          := mv_par18
oParams["clvl_ate"]         := mv_par19
oParams["moeda"]            := nMoeda
oParams["moeda_fmt"]        := mv_par05
oParams["tp_saldo"]         := mv_par06
oParams["set_of_books"]     := mv_par07
oParams["analitico"]        := 1
oParams["contas_sem_mov"]   := IIf(lNoMov, 1, 2)
oParams["imprime_custo"]    := IIf(lCusto, 1, 2)
oParams["imprime_clvl"]     := IIf(lCLVL, 1, 2)
oParams["totaliza_conta"]   := IIf(lTotConta, 1, 2)
oParams["considera_filiais"]:= nConsidFil
oParams["filiais_selecionadas"] := Len(aSelFil)
oParams["page"]             := nPage
oParams["pageSize"]         := nPageSize

oResp["parametros"]      := oParams
oResp["total_registros"] := nTotalReg
oResp["total_pages"]     := nTotalPages
oResp["page"]            := nPage
oResp["linhas"]          := aLinhas

ConOut("ZCTBR480API - retorno total_registros=" + cValToChar(nTotalReg) + ;
    " total_pages=" + cValToChar(nTotalPages) + ;
    " page=" + cValToChar(nPage) + ;
    " linhas_pagina=" + cValToChar(Len(aLinhas)))
If Len(aLinhas) > 0 .And. ValType(aLinhas[1]) == "O"
    ConOut("ZCTBR480API - primeira_linha=" + aLinhas[1]:ToJson())
EndIf
Self:SetResponse(oResp:ToJson())
FreeObj(oResp)
FreeObj(oParams)
RestArea(aArea)

Return .T.

Static Function CTB480MontaErro(cCode, cMessage, cDetails)
Local oErr  := JsonObject():New()
Local cJson := ""

oErr["error"]   := cCode
oErr["message"] := cMessage
If !Empty(cDetails)
	oErr["details"] := cDetails
EndIf

cJson := oErr:ToJson()
FreeObj(oErr)

Return cJson

Static Function CTB480SaldoArray(aSaldo)
Local nRet := 0

If ValType(aSaldo) == "A" .And. Len(aSaldo) >= 6 .And. ValType(aSaldo[6]) == "N"
	nRet := aSaldo[6]
EndIf

Return nRet

Static Function Z480SelFil(nConsidFil, cFilialDe, cFilialAte, cAlias)
Local aSelFil  := {}
Local cFilPad  := cFilAnt
Local nTamFil  := Len(cFilPad)
Local cFilDe   := PadR(AllTrim(cFilialDe), nTamFil)
Local cFilAte  := PadR(AllTrim(cFilialAte), nTamFil)
Local lTodas   := Empty(AllTrim(cFilialDe)) .And. ;
	Upper(AllTrim(cFilialAte)) == Replicate("Z", Len(AllTrim(cFilialAte)))

If nConsidFil == 2
	aAdd(aSelFil, cFilPad)
ElseIf lTodas
	aSelFil := Z480AllFil(cAlias)
ElseIf !Empty(AllTrim(cFilialDe)) .And. cFilDe == cFilAte
	aAdd(aSelFil, cFilDe)
ElseIf !Empty(AllTrim(cFilialDe)) .And. Empty(AllTrim(cFilialAte))
	aAdd(aSelFil, cFilDe)
EndIf

Return aSelFil

Static Function Z480AllFil(cAlias)
Local aArea    := GetArea()
Local aSelFil  := {}
Local aSM0     := AdmAbreSM0()
Local nX       := 0
Local cFilSM0  := ""
Local lUserOk  := .T.

For nX := 1 To Len(aSM0)
	If aSM0[nX][SM0_GRPEMP] == cEmpAnt
		lUserOk := IIf(ValType(aSM0[nX][SM0_USEROK]) == "L", aSM0[nX][SM0_USEROK], .T.)
		If lUserOk
			cFilSM0 := PadR(AllTrim(aSM0[nX][SM0_CODFIL]), Len(cFilAnt))
			If aScan(aSelFil, cFilSM0) == 0
				aAdd(aSelFil, cFilSM0)
			EndIf
		EndIf
	EndIf
Next

If Empty(aSelFil)
	aAdd(aSelFil, cFilAnt)
EndIf

RestArea(aArea)
Return aSelFil

Static Function CTB480FilSemMov(lNoMov, aSaldo, dDataIni, cAliasTmp)
Local lRet := .F.

If !lNoMov
	If CTB480SaldoArray(aSaldo) == 0 .And. (cAliasTmp)->LANCDEB == 0 .And. (cAliasTmp)->LANCCRD == 0
		lRet := .T.
	EndIf
EndIf

If lNoMov .And. CTB480SaldoArray(aSaldo) == 0 .And. (cAliasTmp)->LANCDEB == 0 .And. (cAliasTmp)->LANCCRD == 0
	If CtbExDtFim("CTD")
		If Select("CTD") > 0
			CTD->(dbSetOrder(1))
			If CTD->(MsSeek(xFilial("CTD") + (cAliasTmp)->ITEM))
				lRet := !CtbVlDtFim("CTD", dDataIni)
			EndIf
		EndIf
	EndIf
EndIf

Return lRet

Static Function CTB480DescItem(cItem, cMoeda)
Local cRet := ""
Local cCampo := ""

If Select("CTD") > 0
	If CTD->(MsSeek(xFilial("CTD") + cItem))
		cCampo := "CTD->CTD_DESC" + cMoeda
		If Type(cCampo) != "U"
			cRet := AllTrim(&(cCampo))
		EndIf
		If Empty(cRet) .And. Type("CTD->CTD_DESC01") != "U"
			cRet := AllTrim(CTD->CTD_DESC01)
		EndIf
	EndIf
EndIf

Return cRet

Static Function DescConta(cConta, cMoeda)
Local cRet := ""
Local cCampo := ""

If Select("CT1") > 0
	If CT1->(MsSeek(xFilial("CT1") + cConta))
		cCampo := "CT1->CT1_DESC" + cMoeda
		If Type(cCampo) != "U"
			cRet := AllTrim(&(cCampo))
		EndIf
		If Empty(cRet) .And. Type("CT1->CT1_DESC01") != "U"
			cRet := AllTrim(CT1->CT1_DESC01)
		EndIf
	EndIf
EndIf

Return cRet

Static Function CTB480NormalItem(cItem)
Local cRet := ""

If Select("CTD") > 0
	If CTD->(MsSeek(xFilial("CTD") + cItem))
		cRet := AllTrim(CTD->CTD_NORMAL)
	EndIf
EndIf

Return cRet

Static Function NormalConta(cConta)
Local cRet := ""

If Select("CT1") > 0
	If CT1->(MsSeek(xFilial("CT1") + cConta))
		cRet := AllTrim(CT1->CT1_NORMAL)
	EndIf
EndIf

Return cRet

Static Function CTB480HistCompl(cAliasTmp)
Local aArea := GetArea()
Local cRet  := ""

If Select("CT2") <= 0
	RestArea(aArea)
	Return cRet
EndIf

DbSelectArea("CT2")
dbSetOrder(10)
If MsSeek(xFilial("CT2") + (cAliasTmp)->(DTOS(DATAL) + LOTE + SUBLOTE + DOC + SEQLAN + EMPORI + FILORI), .F.)
	dbSkip()
	If CT2->CT2_DC == "4"
		Do While !CT2->(Eof()) .And. ;
			CT2->CT2_FILIAL == xFilial("CT2") .And. ;
			CT2->CT2_LOTE   == (cAliasTmp)->LOTE .And. ;
			CT2->CT2_SBLOTE == (cAliasTmp)->SUBLOTE .And. ;
			CT2->CT2_DOC    == (cAliasTmp)->DOC .And. ;
			CT2->CT2_SEQLAN == (cAliasTmp)->SEQLAN .And. ;
			CT2->CT2_EMPORI == (cAliasTmp)->EMPORI .And. ;
			CT2->CT2_FILORI == (cAliasTmp)->FILORI .And. ;
			CT2->CT2_DC     == "4" .And. ;
			DTOS(CT2->CT2_DATA) == DTOS((cAliasTmp)->DATAL)
			cRet += IIf(Empty(cRet), "", CRLF) + AllTrim(CT2->CT2_HIST)
			CT2->(dbSkip())
		EndDo
	EndIf
EndIf

RestArea(aArea)
Return cRet





Static Function Z480FilTxt(aSelFil)
Local cRet := ""
Local nX   := 0

If ValType(aSelFil) != "A" .Or. Len(aSelFil) == 0
	Return "[]"
EndIf

For nX := 1 To Len(aSelFil)
	cRet += IIf(Empty(cRet), "", ",") + AllTrim(aSelFil[nX])
Next

Return "[" + cRet + "]"








