#Include "CTBR400.ch"
#Include "Protheus.ch"
#Include "restful.ch"
#Include "APWEBSRV.ch"

/*/{Protheus.doc} ZCTBR400API
API REST baseada no relatorio CTBR400 (Razao Contabil).

Endpoint: GET /rest/zctbr400api/api/v1/ctbr400

Retorno:
  parametros      = parametros efetivos usados na consulta
  total_registros = total de linhas retornadas pela API
  total_pages     = total de paginas da API
  page            = pagina atual
  linhas          = lancamentos do razao em formato JSON

Campos principais por linha:
  data
  lote_sub_doc_linha
  historico
  xpartida
  c_custo
  item_conta
  cod_cl_val
  debito
  credito
  saldo_atual
  conta
  desc_conta
  normal_cta
  ct2_key (CT2_KEY do lancamento de origem na CT2, via MsSeek -- mesmo
           padrao usado em ZCTBR480API::CTB480HistCompl. Linha "TOTAL DO
           DIA" nao tem CT2 unica correspondente, fica em branco)

@author Equipe Desenvolvimento
@since 26/03/2026
@version 1.0
/*/

wsrestful ZCTBR400API description "CTBR400 - Razao Contabil"

	wsdata page             as string
	wsdata pageSize         as string
	wsdata data_ini         as string
	wsdata data_fim         as string
	wsdata conta_de         as string
	wsdata conta_ate        as string
	wsdata custo_de         as string
	wsdata custo_ate        as string
	wsdata item_de          as string
	wsdata item_ate         as string
	wsdata clvl_de          as string
	wsdata clvl_ate         as string
	wsdata moeda            as string
	wsdata saldo            as string
	wsdata set_of_books     as string
	wsdata imprime_custo    as string
	wsdata imprime_item     as string
	wsdata imprime_clvl     as string
	wsdata tipo_rel         as string
	wsdata salta_linha      as string
	wsdata moeda_desc       as string
	wsdata consid_filiais   as string
	wsdata filial_de        as string
	wsdata filial_ate       as string

	wsmethod GET getRazao description "Razao Contabil" wssyntax "/api/v1/ctbr400" PATH "/api/v1/ctbr400"

EndwsRestFul

wsmethod GET getRazao WSRESTFUL ZCTBR400API
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
Local aSaldoAnt     := {}
Local aSelFil       := {}
Local cFiltro       := ""

Local cDataIni      := AllTrim(Self:data_ini)
Local cDataFim      := AllTrim(Self:data_fim)
Local cContaDe      := AllTrim(Self:conta_de)
Local cContaAte     := AllTrim(Self:conta_ate)
Local cCustoDe      := AllTrim(Self:custo_de)
Local cCustoAte     := AllTrim(Self:custo_ate)
Local cItemDe       := AllTrim(Self:item_de)
Local cItemAte      := AllTrim(Self:item_ate)
Local cClvlDe       := AllTrim(Self:clvl_de)
Local cClvlAte      := AllTrim(Self:clvl_ate)
Local cMoeda        := AllTrim(Self:moeda)
Local cSaldo        := AllTrim(Self:saldo)
Local cSetBook      := AllTrim(Self:set_of_books)
Local cImpCusto     := AllTrim(Self:imprime_custo)
Local cImpItem      := AllTrim(Self:imprime_item)
Local cImpClvl      := AllTrim(Self:imprime_clvl)
Local cTipoRel      := AllTrim(Self:tipo_rel)
Local cSaltaLinha   := AllTrim(Self:salta_linha)
Local cMoedaDesc    := AllTrim(Self:moeda_desc)
Local nPage         := Max(1, Val(AllTrim(Self:page)))
Local nPageSize     := Val(AllTrim(Self:pageSize))

Local dDataIni      := CtoD("")
Local dDataFim      := CtoD("")
Local lCusto        := .F.
Local lItem         := .F.
Local lCLVL         := .F.
Local lSaltLin      := .T.
Local lAnalitico    := .T.
Local nTipoRel      := 1
Local nDecimais     := 2
Local nTotalReg     := 0
Local nTotalPages   := 1
Local nOffset       := 0
Local nRecAtual     := 0
Local lHasMore      := .F.
Local nSaldoAtu     := 0
Local nVlrDeb       := 0
Local nVlrCrd       := 0
Local cContaAnt     := ""
Local cDescConta    := ""
Local cNormalCta    := ""
Local dDataAnt      := CtoD("")

Self:SetContentType("application/json")

If Empty(cDataFim) .Or. Len(cDataFim) <> 8
	Self:SetResponse(CTB400ApiMontaErro("VALIDATION_ERROR", "Parametro data_fim e obrigatorio no formato YYYYMMDD", ""))
	FreeObj(oResp)
	FreeObj(oParams)
	RestArea(aArea)
Return .T.
EndIf

CTB4LogReq(Self, nPage, nPageSize)
Pergunte("CTBR400", .F.)
CTB4LogPerg("apos Pergunte()")
dDataFim := StoD(cDataFim)
dDataIni := IIf(Len(cDataIni) == 8, StoD(cDataIni), StoD(Left(cDataFim, 4) + "0101"))

If Empty(dDataFim) .Or. Empty(dDataIni)
	Self:SetResponse(CTB400ApiMontaErro("VALIDATION_ERROR", "Periodo invalido. Informe data_ini/data_fim no formato YYYYMMDD", ""))
	FreeObj(oResp)
	FreeObj(oParams)
	RestArea(aArea)
Return .T.
EndIf

If dDataIni > dDataFim
	Self:SetResponse(CTB400ApiMontaErro("VALIDATION_ERROR", "Parametro data_ini nao pode ser maior que data_fim", ""))
	FreeObj(oResp)
	FreeObj(oParams)
	RestArea(aArea)
Return .T.
EndIf

cMoeda      := IIf(Empty(cMoeda), "01", cMoeda)
cSaldo      := IIf(Empty(cSaldo), "1", cSaldo)
// set_of_books: vazio = sem configuracao de livro especifica (igual ao campo em branco no CTBR400 interativo)
cTipoRel    := IIf(Empty(cTipoRel), "1", cTipoRel)
lCusto      := (cImpCusto == "1")
lItem       := (cImpItem == "1")
lCLVL       := (cImpClvl == "1")
lSaltLin    := IIf(Empty(cSaltaLinha), .T., cSaltaLinha == "1")
nTipoRel    := Max(1, Min(3, Val(cTipoRel)))
lAnalitico  := (nTipoRel < 3)
nPageSize   := IIf(nPageSize <= 0 .Or. nPageSize > 5000, 5000, nPageSize)
nOffset     := (nPage - 1) * nPageSize

mv_par01 := cContaDe
mv_par02 := cContaAte
mv_par03 := dDataIni
mv_par04 := dDataFim
mv_par05 := cMoeda
mv_par06 := cSaldo
mv_par07 := cSetBook
mv_par08 := nTipoRel  // Tipo relatorio: 1=Analitico 2=Resumido 3=Sintetico
mv_par12 := IIf(lCusto, 1, 2)
mv_par13 := cCustoDe
mv_par14 := cCustoAte
mv_par15 := IIf(lItem, 1, 2)
mv_par16 := cItemDe
mv_par17 := cItemAte
mv_par18 := IIf(lCLVL, 1, 2)
mv_par19 := cClvlDe
mv_par20 := cClvlAte
mv_par31 := IIf(lSaltLin, 1, 2)
mv_par32 := 56
mv_par34 := IIf(Empty(cMoedaDesc), cMoeda, cMoedaDesc)
// mv_par36 = 2 fixo no REST, conforme regra definida para o CTBR400.
// Monta aSelFil com todas as filiais da empresa via SM0, igual ao que AdmGetFil faria.
mv_par36 := 2
dbSelectArea("SM0")
dbGoTop()
While !SM0->(Eof())
    If AllTrim(SM0->M0_CODIGO) == AllTrim(cEmpAnt) .Or. Empty(cEmpAnt)
        AAdd(aSelFil, AllTrim(SM0->M0_CODFIL))
    EndIf
    SM0->(dbSkip())
EndDo
ConOut("[ZCTBR400] aSelFil montado via SM0 | qtd_filiais=" + cValToChar(Len(aSelFil)) + " filiais=" + cValToChar(aSelFil))

CTB4LogPerg("apos normalizacao API")
ConOut("[ZCTBR400] params | conta_de=[" + cValToChar(mv_par01) + "] conta_ate=[" + cValToChar(mv_par02) + "]" + ;
    " data_ini=" + DToC(mv_par03) + " data_fim=" + DToC(mv_par04) + ;
    " moeda=[" + mv_par05 + "] saldo=[" + mv_par06 + "] set_of_books=[" + mv_par07 + "]" + ;
    " tipo_rel=" + cValToChar(mv_par08) + " mv_par36=" + cValToChar(mv_par36))
If !Empty(mv_par07) .And. !Ct040Valid(mv_par07)
    ConOut("[ZCTBR400] ERRO: Set of books invalido | valor=[" + cValToChar(mv_par07) + "]")
	Self:SetResponse(CTB400ApiMontaErro("VALIDATION_ERROR", "Set of books invalido para o CTBR400", cValToChar(mv_par07)))
	FreeObj(oResp)
	FreeObj(oParams)
	RestArea(aArea)
Return .T.
EndIf

aCtbMoeda := CtbMoeda(mv_par05)
If Empty(aCtbMoeda[1])
	Self:SetResponse(CTB400ApiMontaErro("VALIDATION_ERROR", "Moeda invalida para o CTBR400", mv_par05))
	FreeObj(oResp)
	FreeObj(oParams)
	RestArea(aArea)
Return .T.
EndIf

aSetOfBook := CTBSetOf(mv_par07)
nDecimais  := IIf(DecimalCTB(aSetOfBook, mv_par05) == 0, SuperGetMv("MV_CENT"), DecimalCTB(aSetOfBook, mv_par05))
ConOut("[ZCTBR400] antes CTBGerRaz | set_of_books=" + cValToChar(aSetOfBook) + ;
    " nDecimais=" + cValToChar(nDecimais) + ;
    " lAnalitico=" + IIf(lAnalitico, "S", "N") + ;
    " aSelFil=" + cValToChar(aSelFil))
ConOut("[ZCTBR400] contexto CTBGerRaz | empresa_atual=[" + cValToChar(cEmpAnt) + "]" + ;
    " xFilial(CT1)=[" + xFilial("CT1") + "]" + ;
    " xFilial(CT2)=[" + xFilial("CT2") + "]" + ;
    " xFilial(CT7)=[" + xFilial("CT7") + "]")
ConOut("[ZCTBR400] arrays CTBGerRaz | aSetOfBook_len=" + IIf(ValType(aSetOfBook) == "A", cValToChar(Len(aSetOfBook)), "Nil") + ;
    " aSetOfBook=" + CTB4ArrTxt(aSetOfBook) + ;
    " aSelFil_len=" + cValToChar(Len(aSelFil)) + ;
    " aSelFil=" + CTB4ArrTxt(aSelFil))

Begin Sequence
	CTBGerRaz(Nil, Nil, Nil, .F., @cArqTmp, mv_par01, mv_par02, mv_par13, mv_par14, ;
		mv_par16, mv_par17, mv_par19, mv_par20, mv_par05, mv_par03, mv_par04, ;
		aSetOfBook, .F., mv_par06, .F., "1", lAnalitico, Nil, Nil, cFiltro, .F., aSelFil, .T.)

	// No contexto REST, CTBGerRaz pode nao setar @cArqTmp por referencia
	// mas cria a area temporaria com alias literal "cArqTmp"
	If Empty(cArqTmp) .And. Select("cArqTmp") > 0
		cArqTmp := "cArqTmp"
	EndIf
    ConOut("[ZCTBR400] apos CTBGerRaz | cArqTmp=[" + cValToChar(cArqTmp) + "] select=" + ;
        cValToChar(IIf(Empty(cArqTmp), 0, Select(cArqTmp))))

	If !Empty(cArqTmp) .And. Select(cArqTmp) > 0
		(cArqTmp)->(DbGoTop())
        ConOut("[ZCTBR400] alias temporario posicionado | recno=" + cValToChar((cArqTmp)->(RecNo())) + ;
            " eof=" + IIf((cArqTmp)->(Eof()), "S", "N"))
        ConOut("[ZCTBR400] alias temporario detalhe | lastrec=" + cValToChar((cArqTmp)->(LastRec())) + ;
            " bof=" + IIf((cArqTmp)->(Bof()), "S", "N") + ;
            " deleted=" + IIf((cArqTmp)->(Deleted()), "S", "N"))
	EndIf

	If Empty(cArqTmp) .Or. Select(cArqTmp) == 0 .Or. (cArqTmp)->(Eof())
        ConOut("[ZCTBR400] retorno sem linhas | cArqTmp=[" + cValToChar(cArqTmp) + "]" + ;
            " select=" + cValToChar(IIf(Empty(cArqTmp), 0, Select(cArqTmp))) + ;
            " eof=" + IIf(!Empty(cArqTmp) .And. Select(cArqTmp) > 0 .And. (cArqTmp)->(Eof()), "S", "N"))
        If !Empty(cArqTmp) .And. Select(cArqTmp) > 0
            ConOut("[ZCTBR400] retorno sem linhas detalhe | lastrec=" + cValToChar((cArqTmp)->(LastRec())) + ;
                " recno=" + cValToChar((cArqTmp)->(RecNo())) + ;
                " bof=" + IIf((cArqTmp)->(Bof()), "S", "N"))
        EndIf
		oParams["data_ini"]     := DtoS(dDataIni)
		oParams["data_fim"]     := DtoS(dDataFim)
		oParams["conta_de"]     := cContaDe
		oParams["conta_ate"]    := cContaAte
		oParams["custo_de"]     := cCustoDe
		oParams["custo_ate"]    := cCustoAte
		oParams["item_de"]      := cItemDe
		oParams["item_ate"]     := cItemAte
		oParams["clvl_de"]      := cClvlDe
		oParams["clvl_ate"]     := cClvlAte
		oParams["moeda"]        := cMoeda
		oParams["saldo"]        := cSaldo
		oParams["set_of_books"] := cSetBook
		oParams["tipo_rel"]     := nTipoRel
		oParams["page"]         := nPage
		oParams["pageSize"]     := nPageSize
		oResp["parametros"]      := oParams
		oResp["total_registros"] := 0
		oResp["total_pages"]     := 1
		oResp["page"]            := nPage
		oResp["hasMore"]         := .F.
		oResp["linhas"]          := {}
		Self:SetResponse(oResp:ToJson())
		If !Empty(cArqTmp) .And. Select(cArqTmp) > 0
			(cArqTmp)->(DbCloseArea())
		EndIf
		CtbRazClean()
		FreeObj(oResp)
		FreeObj(oParams)
		RestArea(aArea)
	Return .T.
	EndIf

	While !(cArqTmp)->(Eof())
		cContaAnt := (cArqTmp)->CONTA
        ConOut("[ZCTBR400] lendo conta temporaria | conta=[" + cValToChar(cContaAnt) + "] data=" + DToC((cArqTmp)->DATAL) + ;
            " deb=" + cValToChar((cArqTmp)->LANCDEB) + " cred=" + cValToChar((cArqTmp)->LANCCRD))
		cDescConta := CTB400ApiContaDesc(cContaAnt, mv_par34, @cNormalCta)
		aSaldoAnt := CTB400ApiSaldo(cContaAnt, dDataIni, (cArqTmp)->DATAL, mv_par05, mv_par06, ;
			lCusto, lItem, lCLVL, cCustoDe, cCustoAte, cItemDe, cItemAte, cClvlDe, cClvlAte, aSelFil)
		nSaldoAtu := aSaldoAnt[6]
		dDataAnt := CtoD("")

		Do While !(cArqTmp)->(Eof()) .And. (cArqTmp)->CONTA == cContaAnt
			If nTipoRel < 3
				nSaldoAtu := Round(nSaldoAtu - (cArqTmp)->LANCDEB + (cArqTmp)->LANCCRD, nDecimais)
				oLinha := JsonObject():New()
				CTB400ApiPreencheLinha(oLinha, cArqTmp, cContaAnt, cDescConta, cNormalCta, nSaldoAtu, nTipoRel)
				nTotalReg++
				If nTotalReg > (nOffset + nPageSize)
					lHasMore := .T.
					FreeObj(oLinha)
					Exit
				ElseIf nTotalReg > nOffset
					AAdd(aLinhas, oLinha)
				Else
					FreeObj(oLinha)
				EndIf
				(cArqTmp)->(DbSkip())
			Else
				nVlrDeb := 0
				nVlrCrd := 0
				dDataAnt := (cArqTmp)->DATAL
				Do While !(cArqTmp)->(Eof()) .And. (cArqTmp)->CONTA == cContaAnt .And. (cArqTmp)->DATAL == dDataAnt
					nVlrDeb += (cArqTmp)->LANCDEB
					nVlrCrd += (cArqTmp)->LANCCRD
					(cArqTmp)->(DbSkip())
				EndDo
				nSaldoAtu := Round(nSaldoAtu - nVlrDeb + nVlrCrd, nDecimais)
				oLinha := JsonObject():New()
				oLinha["data"]               := DtoC(dDataAnt)
				oLinha["lote_sub_doc_linha"] := ""
				oLinha["historico"]          := "TOTAL DO DIA"
				oLinha["xpartida"]           := ""
				oLinha["c_custo"]            := ""
				oLinha["item_conta"]         := ""
				oLinha["cod_cl_val"]         := ""
				oLinha["debito"]             := Round(nVlrDeb, nDecimais)
				oLinha["credito"]            := Round(nVlrCrd, nDecimais)
				oLinha["saldo_atual"]        := Round(nSaldoAtu, nDecimais)
				oLinha["conta"]              := cContaAnt
				oLinha["desc_conta"]         := cDescConta
				oLinha["normal_cta"]         := cNormalCta
				oLinha["ct2_key"]            := ""
				nTotalReg++
				If nTotalReg > (nOffset + nPageSize)
					lHasMore := .T.
					FreeObj(oLinha)
					Exit
				ElseIf nTotalReg > nOffset
					AAdd(aLinhas, oLinha)
				Else
					FreeObj(oLinha)
				EndIf
			EndIf
		EndDo
		If lHasMore
			Exit
		EndIf
	EndDo

	If !Empty(cArqTmp) .And. Select(cArqTmp) > 0
		(cArqTmp)->(DbCloseArea())
	EndIf
	CtbRazClean()

Recover Using oError
	If !Empty(cArqTmp) .And. Select(cArqTmp) > 0
		(cArqTmp)->(DbCloseArea())
	EndIf
	CtbRazClean()
	Self:SetResponse(CTB400ApiMontaErro("INTERNAL_ERROR", "Erro interno ao consultar razao contabil", oError:Description))
	FreeObj(oResp)
	FreeObj(oParams)
	AEval(aAllLinhas, {|oObj| FreeObj(oObj)})
	RestArea(aArea)
Return .T.
End Sequence
ConOut("[ZCTBR400] fim montagem linhas | linhas_pagina=" + cValToChar(Len(aLinhas)) + ;
	" total_processado=" + cValToChar(nTotalReg) + ;
	" hasMore=" + IIf(lHasMore, "S", "N"))

nTotalPages := IIf(lHasMore, nPage + 1, Max(1, nPage))

oParams["data_ini"]     := DtoS(dDataIni)
oParams["data_fim"]     := DtoS(dDataFim)
oParams["conta_de"]     := cContaDe
oParams["conta_ate"]    := cContaAte
oParams["custo_de"]     := cCustoDe
oParams["custo_ate"]    := cCustoAte
oParams["item_de"]      := cItemDe
oParams["item_ate"]     := cItemAte
oParams["clvl_de"]      := cClvlDe
oParams["clvl_ate"]     := cClvlAte
oParams["moeda"]        := cMoeda
oParams["saldo"]        := cSaldo
oParams["set_of_books"] := cSetBook
oParams["tipo_rel"]     := nTipoRel
oParams["page"]         := nPage
oParams["pageSize"]     := nPageSize

oResp["parametros"]      := oParams
oResp["total_registros"] := nTotalReg
oResp["total_pages"]     := nTotalPages
oResp["page"]            := nPage
oResp["hasMore"]         := lHasMore
oResp["linhas"]          := aLinhas
ConOut("[ZCTBR400] resposta final | total_registros=" + cValToChar(nTotalReg) + ;
    " total_pages=" + cValToChar(nTotalPages) + ;
    " page=" + cValToChar(nPage) + ;
    " linhas_pagina=" + cValToChar(Len(aLinhas)))

Self:SetResponse(oResp:ToJson())

FreeObj(oResp)
FreeObj(oParams)
RestArea(aArea)

Return .T.

Static Function CTB4LogReq(oWs, nPage, nPageSize)
ConOut("[ZCTBR400] requisicao recebida" + ;
	" | page=" + cValToChar(nPage) + ;
	" pageSize=" + cValToChar(nPageSize) + ;
	" data_ini=[" + AllTrim(oWs:data_ini) + "]" + ;
	" data_fim=[" + AllTrim(oWs:data_fim) + "]" + ;
	" conta_de=[" + AllTrim(oWs:conta_de) + "]" + ;
	" conta_ate=[" + AllTrim(oWs:conta_ate) + "]" + ;
	" custo_de=[" + AllTrim(oWs:custo_de) + "]" + ;
	" custo_ate=[" + AllTrim(oWs:custo_ate) + "]" + ;
	" item_de=[" + AllTrim(oWs:item_de) + "]" + ;
	" item_ate=[" + AllTrim(oWs:item_ate) + "]" + ;
	" clvl_de=[" + AllTrim(oWs:clvl_de) + "]" + ;
	" clvl_ate=[" + AllTrim(oWs:clvl_ate) + "]" + ;
	" moeda=[" + AllTrim(oWs:moeda) + "]" + ;
	" saldo=[" + AllTrim(oWs:saldo) + "]" + ;
	" set_of_books=[" + AllTrim(oWs:set_of_books) + "]" + ;
	" imprime_custo=[" + AllTrim(oWs:imprime_custo) + "]" + ;
	" imprime_item=[" + AllTrim(oWs:imprime_item) + "]" + ;
	" imprime_clvl=[" + AllTrim(oWs:imprime_clvl) + "]" + ;
	" tipo_rel=[" + AllTrim(oWs:tipo_rel) + "]" + ;
	" salta_linha=[" + AllTrim(oWs:salta_linha) + "]" + ;
	" moeda_desc=[" + AllTrim(oWs:moeda_desc) + "]" + ;
	" consid_filiais=[" + AllTrim(oWs:consid_filiais) + "]" + ;
	" filial_de=[" + AllTrim(oWs:filial_de) + "]" + ;
	" filial_ate=[" + AllTrim(oWs:filial_ate) + "]")

Return Nil

Static Function CTB4LogPerg(cEtapa)
ConOut("[ZCTBR400] " + cEtapa + ;
	" | mv_par01=[" + cValToChar(mv_par01) + "]" + ;
	" mv_par02=[" + cValToChar(mv_par02) + "]" + ;
	" mv_par03=[" + CTB400ApiFmtMv(mv_par03) + "]" + ;
	" mv_par04=[" + CTB400ApiFmtMv(mv_par04) + "]" + ;
	" mv_par05=[" + cValToChar(mv_par05) + "]" + ;
	" mv_par06=[" + cValToChar(mv_par06) + "]" + ;
	" mv_par07=[" + cValToChar(mv_par07) + "]" + ;
	" mv_par08=[" + cValToChar(mv_par08) + "]" + ;
	" mv_par12=[" + cValToChar(mv_par12) + "]" + ;
	" mv_par13=[" + cValToChar(mv_par13) + "]" + ;
	" mv_par14=[" + cValToChar(mv_par14) + "]" + ;
	" mv_par15=[" + cValToChar(mv_par15) + "]" + ;
	" mv_par16=[" + cValToChar(mv_par16) + "]" + ;
	" mv_par17=[" + cValToChar(mv_par17) + "]" + ;
	" mv_par18=[" + cValToChar(mv_par18) + "]" + ;
	" mv_par19=[" + cValToChar(mv_par19) + "]" + ;
	" mv_par20=[" + cValToChar(mv_par20) + "]" + ;
	" mv_par31=[" + cValToChar(mv_par31) + "]" + ;
	" mv_par32=[" + cValToChar(mv_par32) + "]" + ;
	" mv_par34=[" + cValToChar(mv_par34) + "]" + ;
	" mv_par36=[" + cValToChar(mv_par36) + "]")

Return Nil

Static Function CTB400ApiFmtMv(uValor)
Local cTipo := ValType(uValor)

If cTipo == "D"
	Return DtoS(uValor)
EndIf

If cTipo == "L"
	Return IIf(uValor, ".T.", ".F.")
EndIf

Return cValToChar(uValor)

Static Function CTB4ArrTxt(aDados)
Local cRet := ""
Local nI   := 0

If ValType(aDados) <> "A"
    Return cValToChar(aDados)
EndIf

For nI := 1 To Len(aDados)
    cRet += IIf(nI > 1, ";", "") + cValToChar(aDados[nI])
Next

Return "[" + cRet + "]"

Static Function CTB400ApiSaldo(cConta, dDataIni, dDataMov, cMoeda, cSaldo, lCusto, lItem, lCLVL, cCustoDe, cCustoAte, cItemDe, cItemAte, cClvlDe, cClvlAte, aSelFil)
Local aSaldoRet := {}

If lCusto
	aSaldoRet := SaldTotCT3(cCustoDe, cCustoAte, cConta, cConta, dDataIni, cMoeda, cSaldo, aSelFil)
ElseIf lItem
	aSaldoRet := SaldTotCT4(cItemDe, cItemAte, cCustoDe, cCustoAte, cConta, cConta, dDataIni, cMoeda, cSaldo, aSelFil)
ElseIf lCLVL
	aSaldoRet := SaldTotCTI(cClvlDe, cClvlAte, cItemDe, cItemAte, cCustoDe, cCustoAte, cConta, cConta, dDataIni, cMoeda, cSaldo, aSelFil)
Else
	aSaldoRet := SaldoCT7Fil(cConta, dDataIni, cMoeda, cSaldo, "CTBR400",,, aSelFil)
EndIf

Return aSaldoRet

Static Function CTB400ApiContaDesc(cConta, cMoedaDesc, cNormalCta)
Local cDescConta := ""
Local cAliasCT1  := xFilial("CT1") + cConta

DbSelectArea("CT1")
CT1->(DbSetOrder(1))
If CT1->(MsSeek(cAliasCT1, .F.))
	cDescConta := &("CT1->CT1_DESC" + cMoedaDesc)
	cNormalCta := CT1->CT1_NORMAL
Else
	cDescConta := ""
	cNormalCta := ""
EndIf

Return cDescConta

Static Function CTB400ApiPreencheLinha(oLinha, cAlias, cConta, cDescConta, cNormalCta, nSaldoAtu, nTipoConta)
Local cLoteDoc := ""
Local cContaFmt := cConta
Local cPartFmt  := (cAlias)->XPARTIDA
Local cCustoFmt := (cAlias)->CCUSTO
Local cItemFmt  := (cAlias)->ITEM
Local cClvlFmt  := (cAlias)->CLVL

cLoteDoc := AllTrim((cAlias)->LOTE) + AllTrim((cAlias)->SUBLOTE) + AllTrim((cAlias)->DOC) + AllTrim((cAlias)->LINHA)

If nTipoConta == 1
	cContaFmt := EntidadeCTB((cAlias)->CONTA, 0, 0, TamSX3("CT1_CONTA")[1], .F.)
	cPartFmt  := EntidadeCTB((cAlias)->XPARTIDA, 0, 0, TamSX3("CT1_CONTA")[1], .F.)
EndIf

oLinha["data"]               := DtoC((cAlias)->DATAL)
oLinha["lote_sub_doc_linha"] := cLoteDoc
oLinha["historico"]          := (cAlias)->HISTORICO
oLinha["xpartida"]           := cPartFmt
oLinha["c_custo"]            := cCustoFmt
oLinha["item_conta"]         := cItemFmt
oLinha["cod_cl_val"]         := cClvlFmt
oLinha["debito"]             := Round((cAlias)->LANCDEB, 2)
oLinha["credito"]            := Round((cAlias)->LANCCRD, 2)
oLinha["saldo_atual"]        := Round(nSaldoAtu, 2)
oLinha["conta"]              := cContaFmt
oLinha["desc_conta"]         := cDescConta
oLinha["normal_cta"]         := cNormalCta
oLinha["filial"]             := (cAlias)->FILIAL
oLinha["filial_origem"]      := (cAlias)->FILORI
oLinha["emp_origem"]         := (cAlias)->EMPORI
oLinha["ct2_key"]            := CTB400Ct2Key(cAlias)

Return Nil

/*/{Protheus.doc} CTB400Ct2Key
Busca o CT2_KEY do lancamento de origem na CT2 a partir da linha do
relatorio (gerada por CTBGerRaz, sem CT2_KEY nativo). Mesmo padrao de
MsSeek (ordem 10, por filial+data+lote+sublote+doc+linha+empresa/filial
origem) usado em ZCTBR480API::CTB480HistCompl - so troca o campo lido
(CT2_KEY no lugar de CT2_HIST). Nome encurtado (sem "Api") para nao
colidir com CTB400ApiContaDesc nos 10 primeiros caracteres do identificador.
/*/
Static Function CTB400Ct2Key(cAlias)
Local aArea  := GetArea()
Local cRet   := ""

If Select("CT2") <= 0
	RestArea(aArea)
	Return cRet
EndIf

DbSelectArea("CT2")
dbSetOrder(10)
If MsSeek(xFilial("CT2") + (cAlias)->(DTOS(DATAL) + LOTE + SUBLOTE + DOC + LINHA + EMPORI + FILORI), .F.)
	cRet := AllTrim(CT2->CT2_KEY)
EndIf

RestArea(aArea)
Return cRet

Static Function CTB400ApiMontaErro(cCode, cMessage, cDetails)
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




