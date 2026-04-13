#Include "Protheus.ch"
#Include "restful.ch"
#Include "APWEBSRV.ch"
#Include "FWCOMMAND.ch"
#Include "FWLIBVERSION.ch"

#Define REC_NAO_CONCILIADO 1
#Define REC_CONCILIADO     2
#Define PAG_NAO_CONCILIADO 3
#Define PAG_CONCILIADO     4

Static cSM0Leiaute := AllTrim(FWSM0Layout())
Static lGestao     := ("E" $ cSM0Leiaute .Or. "U" $ cSM0Leiaute)

/*/{Protheus.doc} ZFIN470API
API REST equivalente ao relatorio FINR470 (Extrato Bancario).
Replica a finalidade do fonte oficial FINR470, mantendo as regras principais
 de saldo inicial, filtro por conciliacao, conversao monetaria e totalizadores.

Endpoint: GET /rest/zfin470api/api/v1/finr470

@type Function
@author Equipe Desenvolvimento
@since 25/03/2026
@version 1.0
/*/

wsrestful ZFIN470API description "FINR470 - Extrato Bancario"

	wsdata page               as string
	wsdata pageSize           as string
	wsdata banco              as string
	wsdata agencia            as string
	wsdata conta              as string
	wsdata data_ini           as string
	wsdata data_fim           as string
	wsdata moeda              as string
	wsdata situacao           as string
	wsdata linhas_pagina      as string
	wsdata taxa_moeda         as string
	wsdata saldo_compart      as string
	wsdata todas_filiais      as string
	wsdata data_conv_saldo    as string

	wsmethod GET getExtrato description "Extrato bancario por periodo" wssyntax "/api/v1/finr470" PATH "/api/v1/finr470"

EndwsRestFul

wsmethod GET getExtrato WSRESTFUL ZFIN470API
Local aArea          := GetArea()
Local oResp          := JsonObject():New()
Local oParams        := JsonObject():New()
Local oBanco         := JsonObject():New()
Local oTotais        := JsonObject():New()
Local aMovimentos    := {}
Local aAllMovs       := {}
Local oItem          := Nil
Local oError         := Nil
Local cAlias         := GetNextAlias()
Local cSql           := ""
Local cSqlWhere      := ""
Local cCampos        := ""
Local cExpMda        := ""
Local cTabela14      := ""
Local aRecon         := { { 0, 0, 0, 0 } }

Local cBanco         := AllTrim(Self:banco)
Local cAgencia       := AllTrim(Self:agencia)
Local cConta         := AllTrim(Self:conta)
Local cDataIni       := AllTrim(Self:data_ini)
Local cDataFim       := AllTrim(Self:data_fim)
Local cMoeda         := AllTrim(Self:moeda)
Local cSituacao      := AllTrim(Self:situacao)
Local cLinhasPagina  := AllTrim(Self:linhas_pagina)
Local cTaxaMoeda     := AllTrim(Self:taxa_moeda)
Local cSaldoCompart  := AllTrim(Self:saldo_compart)
Local cTodasFiliais  := AllTrim(Self:todas_filiais)
Local cDataConvSaldo := AllTrim(Self:data_conv_saldo)
Local nPage          := Max(1, Val(AllTrim(Self:page)))
Local nPageSize      := Val(AllTrim(Self:pageSize))

Local dDataIni       := CtoD("")
Local dDataFim       := CtoD("")
Local nMoedaRel      := 1
Local nSituacao      := 1
Local nLinhasPag     := 89
Local nTpTaxa        := 1
Local nSaldoCompart  := 1
Local nTodasFiliais  := 2
Local nDataConvSaldo := 1
Local nDecMoeda      := 2
Local nMoedaBco      := 1
Local nSaldoIni      := 0
Local nSaldoRod      := 0
Local nSaldoFinal    := 0
Local nLimCred       := 0
Local nValorMov      := 0
Local nValorRec      := 0
Local nValorPag      := 0
Local nTxMoeda       := 0
Local nTaxaMovi      := 0
Local nTaxaDest      := 0
Local nMoedaTit      := 0
Local nTxContr       := 0
Local nTotalReg      := 0
Local nTotalPages    := 1
Local nOffset        := 0
Local nRecAtual      := 0
Local nI             := 0

Local lSpbInUse      := SpbInUse()
Local lAllFil        := .F.
Local lVldUnNeg      := lGestao
Local lTudoComp      := .F.
Local lTitulo        := .T.

Local dDataMovi      := CtoD("")
Local dDtConvSld     := CtoD("")

Local cFilSA6        := ""  // SA6 e compartilhado: A6_FILIAL e sempre vazio
Local cFilSE5        := IIf(lGestao, FWFilial("SE5"), xFilial("SE5"))
Local cFilSE8        := IIf(lGestao, FWFilial("SE8"), xFilial("SE8"))
Local cMoedaDesc     := ""
Local cDocument      := ""
Local cPrefTit       := ""
Local cHistSE5       := ""
Local cDataDisp      := ""
Local cTbl           := ""
Local cMvPagAnt      := SuperGetMv("MV_PAGANT", .F., "")
Local cMvRecAnt      := SuperGetMv("MV_RECANT", .F., "")
Local cMvCrNeg       := SuperGetMv("MV_CRNEG", .F., "")
Local aSaldoIni      := {}
Local aFiliais       := {}
Local aSelFil        := {}
Local nFiliais       := 0
Local nTamEmp        := 0
Local nTamUni        := 0
Local cMAEmpSA6      := ""
Local cMAUniSA6      := ""
Local cMAFilSA6      := ""
Local aTamBanco      := TamSX3("A6_COD")
Local aTamAgencia    := TamSX3("A6_AGENCIA")
Local aTamConta      := TamSX3("A6_NUMCON")
Local nTamBanco      := IIf(Len(aTamBanco)   >= 1, aTamBanco[1],   3)
Local nTamAgencia    := IIf(Len(aTamAgencia) >= 1, aTamAgencia[1],  5)
Local nTamConta      := IIf(Len(aTamConta)   >= 1, aTamConta[1],   10)
Local aTamE1Tx       := TamSX3("E1_TXMOEDA")
Local aTamE2Tx       := TamSX3("E2_TXMOEDA")
Local aTamE5Tx       := TamSX3("E5_TXMOEDA")
Local nCasDecE1      := IIf(Len(aTamE1Tx) >= 2, aTamE1Tx[2], 8)
Local nCasDecE2      := IIf(Len(aTamE2Tx) >= 2, aTamE2Tx[2], 8)
Local nCasDec        := IIf(Len(aTamE5Tx) >= 2, aTamE5Tx[2], 8)

Self:SetContentType("application/json")
ConOut("ZFIN470API - [1] inicio banco=" + cBanco + " ag=" + cAgencia + " cta=" + cConta)

If Empty(cBanco) .Or. Empty(cAgencia) .Or. Empty(cConta)
	oError := JsonObject():New()
	oError["erro"]      := .T.
	oError["status"]    := 422
	oError["mensagem"]  := "Parametros banco, agencia e conta sao obrigatorios"
	Self:SetResponse(oError:ToJson())
	FreeObj(oError)
	RestArea(aArea)
Return .T.
EndIf

If Empty(cDataIni) .Or. Len(cDataIni) <> 8 .Or. Empty(cDataFim) .Or. Len(cDataFim) <> 8
	oError := JsonObject():New()
	oError["erro"]      := .T.
	oError["status"]    := 422
	oError["mensagem"]  := "Parametros data_ini e data_fim sao obrigatorios no formato YYYYMMDD"
	Self:SetResponse(oError:ToJson())
	FreeObj(oError)
	RestArea(aArea)
Return .T.
EndIf

ConOut("ZFIN470API - [2] validacoes ok, convertendo parametros")
dDataIni       := StoD(cDataIni)
dDataFim       := StoD(cDataFim)
nMoedaRel      := IIf(Empty(cMoeda),         1, Val(cMoeda))
nSituacao      := IIf(Empty(cSituacao),      1, Val(cSituacao))
nLinhasPag     := IIf(Empty(cLinhasPagina), 89, Val(cLinhasPagina))
nTpTaxa        := IIf(Empty(cTaxaMoeda),     1, Val(cTaxaMoeda))
nSaldoCompart  := IIf(Empty(cSaldoCompart),  1, Val(cSaldoCompart))
nTodasFiliais  := IIf(Empty(cTodasFiliais),  2, Val(cTodasFiliais))
nDataConvSaldo := IIf(Empty(cDataConvSaldo), 1, Val(cDataConvSaldo))
nPageSize      := IIf(nPageSize <= 0 .Or. nPageSize > 2000, 200, nPageSize)
lAllFil        := (nTodasFiliais == 1)
nDecMoeda      := GetMv("MV_CENT" + IIf(nMoedaRel > 1, AllTrim(Str(nMoedaRel)), ""))
ConOut("ZFIN470API - [3] params: moeda=" + cValToChar(nMoedaRel) + " lAllFil=" + cValToChar(lAllFil) + " pageSize=" + cValToChar(nPageSize))

dbSelectArea("SA6")
SA6->(DbSetOrder(1))
ConOut("ZFIN470API - [4] SA6 seek key=[" + PadR(cFilSA6, TamSX3("A6_FILIAL")[1]) + PadR(AllTrim(cBanco), nTamBanco) + PadR(AllTrim(cAgencia), nTamAgencia) + PadR(AllTrim(cConta), nTamConta) + "]")
If !SA6->(DbSeek(PadR(cFilSA6, TamSX3("A6_FILIAL")[1]) + PadR(AllTrim(cBanco), nTamBanco) + PadR(AllTrim(cAgencia), nTamAgencia) + PadR(AllTrim(cConta), nTamConta)))
	ConOut("ZFIN470API - [4] SA6 nao encontrado")
	oError := JsonObject():New()
	oError["erro"]      := .T.
	oError["status"]    := 404
	oError["mensagem"]  := "Banco/agencia/conta nao encontrados em SA6"
	Self:SetResponse(oError:ToJson())
	FreeObj(oError)
	RestArea(aArea)
Return .T.
EndIf

ConOut("ZFIN470API - [5] SA6 encontrado moeda=" + cValToChar(SA6->A6_MOEDA))
nMoedaBco := Max(SA6->A6_MOEDA, 1)
ConOut("ZFIN470API - [6] chamando FR470Tab14")
cTabela14 := FR470Tab14()
ConOut("ZFIN470API - [7] Tab14=" + cTabela14)

If cPaisLoc == "BRA"
	cExpMda := "E5_MOEDA NOT IN " + FormatIn(cTabela14, "/")
Else
	cExpMda := "E5_MOEDA NOT IN " + FormatIn(cTabela14 + "/DO", "/")
EndIf

ConOut("ZFIN470API - [8] chamando F470SaldoInicial")
aSaldoIni   := F470SaldoInicial(cBanco, cAgencia, cConta, dDataIni, nSituacao, nMoedaBco, nMoedaRel, nDataConvSaldo, nDecMoeda, nSaldoCompart, dDataFim)
ConOut("ZFIN470API - [9] SaldoIni=" + cValToChar(aSaldoIni[1]))
nSaldoIni   := aSaldoIni[1]
dDtConvSld  := aSaldoIni[2]
nSaldoRod   := nSaldoIni
nSaldoFinal := nSaldoIni

If cPaisLoc == "BRA"
	nLimCred := SA6->A6_LIMCRED
Else
	If SA6->A6_MOEDA <> 1 .And. SA6->A6_MOEDA == nMoedaRel
		nLimCred := SA6->A6_LIMCRED
	Else
		nLimCred := xMoeda(SA6->A6_LIMCRED, SA6->A6_MOEDA, 1, dDataBase)
	EndIf
EndIf

If lAllFil
	cMAEmpSA6 := AllTrim(FWModeAccess("SA6", 1))
	cMAUniSA6 := AllTrim(FWModeAccess("SA6", 2))
	cMAFilSA6 := AllTrim(FWModeAccess("SA6", 3))
	nTamEmp   := Len(FWSM0Layout(, 1))
	nTamUni   := Len(FWSM0Layout(, 2))

	If (nTamEmp + nTamUni) == 0
		cMAEmpSA6 := cMAUniSA6 := cMAFilSA6
	Else
		If nTamEmp == 0
			cMAEmpSA6 := cMAUniSA6
		ElseIf nTamUni == 0
			cMAUniSA6 := cMAFilSA6
		EndIf
	EndIf

	lTudoComp := ((cMAEmpSA6 + cMAUniSA6 + cMAFilSA6) == "CCC")

	If nTamUni > 0 .And. !lTudoComp
		lVldUnNeg := (cMAUniSA6 == "E")
	EndIf

	aFiliais := AdmGetFil(.F., lGestao, "SA6", lVldUnNeg, Nil, .F., lTudoComp)
	nFiliais := Len(aFiliais)
	For nI := 1 To nFiliais
		AAdd(aSelFil, aFiliais[nI, 1])
	Next nI
	cSqlWhere += FinSelFil(aSelFil, "SE5", .F., .F.) + " AND "
Else
	cSqlWhere += " SE5.E5_FILIAL = '" + cFilSE5 + "' AND "
	If Empty(cFilSE5) .And. !Empty(cFilSE8)
		cSqlWhere += " SE5.E5_FILORIG = '" + cFilSE8 + "' AND "
	EndIf
EndIf

If lSpbInUse
	cSqlWhere += " SE5.E5_DTDISPO >= '" + DtoS(dDataIni) + "' AND "
	cSqlWhere += " ((SE5.E5_DTDISPO <= '" + DtoS(dDataFim) + "') OR "
	cSqlWhere += "  (SE5.E5_DTDISPO >= '" + DtoS(dDataFim) + "' AND "
	cSqlWhere += "   (SE5.E5_DATA >= '" + DtoS(dDataIni) + "' AND "
	cSqlWhere += "    SE5.E5_DATA <= '" + DtoS(dDataFim) + "'))) AND "
Else
	cSqlWhere += " SE5.E5_DTDISPO >= '" + DtoS(dDataIni) + "' AND "
	cSqlWhere += " SE5.E5_DTDISPO <= '" + DtoS(dDataFim) + "' AND "
EndIf

cSqlWhere += " NOT (SE5.E5_TIPODOC = 'PA ' AND SE5.E5_ORIGEM = 'FINA090' AND SE5.E5_NUMCHEQ <> ' ') AND "

If nSituacao == 2
	cSqlWhere += " SE5.E5_RECONC <> ' ' AND "
ElseIf nSituacao == 3
	cSqlWhere += " SE5.E5_RECONC = ' ' AND "
EndIf

cCampos := "SE5.E5_FILIAL,SE5.E5_DTDISPO,SE5.E5_HISTOR,SE5.E5_NUMCHEQ,SE5.E5_DOCUMEN,SE5.E5_PREFIXO,"
cCampos += "SE5.E5_NUMERO,SE5.E5_PARCELA,SE5.E5_TIPODOC,SE5.E5_FILORIG,SE5.E5_DATA,SE5.E5_RECPAG,"
cCampos += "SE5.E5_VALOR,SE5.E5_MOEDA,SE5.E5_VLMOED2,SE5.E5_CLIFOR,SE5.E5_LOJA,SE5.E5_RECONC,SE5.E5_TIPO,"
cCampos += "SE5.E5_SEQ,SE5.E5_BANCO,SE5.E5_AGENCIA,SE5.E5_CONTA,SE5.E5_TXMOEDA,SE5.E5_ORIGEM,SE5.E5_MOTBX,"
cCampos += "SA6.A6_COD,SA6.A6_NREDUZ,SA6.A6_AGENCIA,SA6.A6_NUMCON,SA6.A6_LIMCRED"

cSql := " SELECT " + cCampos
cSql += " FROM " + RetSqlName("SE5") + " SE5 "
cSql += " LEFT JOIN " + RetSqlName("SA6") + " SA6 "
cSql += "   ON SA6.A6_COD = SE5.E5_BANCO "
cSql += "  AND SA6.A6_AGENCIA = SE5.E5_AGENCIA "
cSql += "  AND SA6.A6_NUMCON = SE5.E5_CONTA "
cSql += "  AND SA6.A6_FILIAL = '" + cFilSA6 + "' "
cSql += "  AND SA6.D_E_L_E_T_ = ' ' "
cSql += " WHERE " + cSqlWhere
cSql += " SE5.E5_BANCO = '" + cBanco + "' AND "
cSql += " SE5.E5_AGENCIA = '" + cAgencia + "' AND "
cSql += " SE5.E5_CONTA = '" + cConta + "' AND "
cSql += " SE5.E5_TIPODOC NOT IN ('DC','JR','MT','CM','D2','J2','M2','V2','C2','CP','TL','BA','I2','EI','VA') AND "
cSql += " (SE5.E5_TIPODOC <> 'VL' OR SE5.E5_TIPO <> 'VP') AND "
cSql += " NOT (SE5.E5_TIPODOC = 'ES' AND SE5.E5_RECPAG = 'P' AND SE5.E5_MOTBX = 'CMP') AND "
cSql += " NOT (SE5.E5_MOEDA IN ('C1','C2','C3','C4','C5','CH') AND SE5.E5_NUMCHEQ = '               ' AND "
cSql += "      (SE5.E5_TIPODOC NOT IN ('TR','TE'))) AND "
cSql += " NOT (SE5.E5_TIPODOC IN ('TR','TE') AND "
cSql += "      ((SE5.E5_NUMCHEQ BETWEEN '*              ' AND '*ZZZZZZZZZZZZZZ') OR "
cSql += "       (SE5.E5_DOCUMEN BETWEEN '*                ' AND '*ZZZZZZZZZZZZZZZZ'))) AND "
cSql += " NOT (SE5.E5_TIPODOC IN ('TR','TE') AND SE5.E5_NUMERO = '      ' AND " + cExpMda + ") AND "
cSql += " SE5.E5_VALOR <> 0 AND SE5.E5_SITUACA <> 'C' AND "
cSql += " NOT (SE5.E5_NUMCHEQ BETWEEN '*              ' AND '*ZZZZZZZZZZZZZZ') AND "
cSql += " SE5.D_E_L_E_T_ = ' ' "
cSql += " ORDER BY SE5.E5_DTDISPO, SE5.E5_BANCO, SE5.E5_AGENCIA, SE5.E5_CONTA, "
cSql += "          SE5.E5_NUMCHEQ, SE5.E5_DOCUMEN, SE5.R_E_C_N_O_, SE5.E5_PREFIXO, SE5.E5_NUMERO "

Begin Sequence
	dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .T., .F.)
	TCSetField(cAlias, "E5_DTDISPO", "D", 8, 0)
	TCSetField(cAlias, "E5_DATA",    "D", 8, 0)
	TCSetField(cAlias, "E5_VALOR",   "N", 16, 2)
	TCSetField(cAlias, "E5_VLMOED2", "N", 16, 2)
	TCSetField(cAlias, "E5_TXMOEDA", "N", 16, 8)
	TCSetField(cAlias, "A6_LIMCRED", "N", 16, 2)

	(cAlias)->(DbGoTop())
	While !(cAlias)->(Eof())
		nTaxaMovi := 0
		nTaxaDest := 0
		nMoedaTit := 0
		nValorMov := 0
		nValorRec := 0
		nValorPag := 0
		nTxContr  := 0
		lTitulo   := .T.
		cDocument := ""
		cHistSE5  := ""
		cPrefTit  := ""
		cDataDisp := ""
		dDataMovi := CtoD("")
		cTbl      := ""

		If (cAlias)->E5_MOEDA == "TC" .And. cPaisLoc == "MEX"
			(cAlias)->(DbSkip())
			Loop
		EndIf

		If (cAlias)->E5_TIPODOC == "ES"
			dbSelectArea("SE5")
			SE5->(DbSetOrder(7))
			If SE5->(DbSeek((cAlias)->(E5_FILIAL + E5_PREFIXO + E5_NUMERO + E5_PARCELA + E5_TIPO + E5_CLIFOR + E5_LOJA + E5_SEQ))) .And. SE5->E5_TIPODOC == "V2"
				(cAlias)->(DbSkip())
				Loop
			EndIf
		EndIf

		nValorMov := (cAlias)->E5_VALOR

		If nMoedaBco > 0 .And. nMoedaBco != nMoedaRel .And. !Empty((cAlias)->E5_RECPAG) .And. !Empty((cAlias)->E5_MOEDA)
			dDataMovi := IIf(nTpTaxa == 2, (cAlias)->E5_DATA, dDataBase)
			nCasDec   := nCasDecE1
			cTbl      := "SE1"
			nTxMoeda  := IIf((cAlias)->E5_TXMOEDA != 1, (cAlias)->E5_TXMOEDA, 0)

			If (cAlias)->E5_TIPO $ cMvPagAnt .Or. ;
			   (!( (cAlias)->E5_TIPO $ cMvRecAnt + "|" + cMvCrNeg ) .And. ;
			    (((cAlias)->E5_RECPAG == "P" .And. (cAlias)->E5_TIPODOC != "ES") .Or. ;
			     ((cAlias)->E5_RECPAG == "R" .And. (cAlias)->E5_TIPODOC == "ES")))
				cTbl    := "SE2"
				nCasDec := nCasDecE2
			EndIf

			(cTbl)->(DbSetOrder(1))
			lTitulo := (cTbl)->(MsSeek(xFilial(cTbl, (cAlias)->E5_FILORIG) + (cAlias)->(E5_PREFIXO + E5_NUMERO + E5_PARCELA + E5_TIPO + E5_CLIFOR + E5_LOJA)))
			If lTitulo
				nMoedaTit := IIf(cTbl == "SE1", SE1->E1_MOEDA, SE2->E2_MOEDA)
				nTxContr  := IIf(cTbl == "SE1", SE1->E1_TXMOEDA, SE2->E2_TXMOEDA)
			EndIf

			If nTpTaxa == 1
				If nMoedaRel > 1 .And. nMoedaBco > 1
					nTaxaMovi := nTxMoeda
					nTaxaDest := RecMoeda(dDataMovi, nMoedaRel)
				Else
					nTaxaMovi := RecMoeda(dDataMovi, IIf(nMoedaBco > 1, nMoedaBco, nMoedaRel))
				EndIf
			Else
				nTaxaMovi := nTxMoeda
				If nMoedaRel > 1
					If !lTitulo .And. nTxMoeda > 0
						nTaxaMovi := 0
						nTaxaDest := nTxMoeda
					Else
						nTaxaDest := IIf(nMoedaBco > 1, ;
							IIf(nMoedaRel == nMoedaTit .And. nTxContr > 0, nTxContr, RecMoeda(dDataMovi, nMoedaRel)), ;
							IIf(nMoedaRel == nMoedaTit, nTxMoeda, RecMoeda(dDataMovi, nMoedaRel)))
						nTaxaMovi := IIf(nMoedaBco > 1, nTxMoeda, 0)
					EndIf
				EndIf
			EndIf
		EndIf

		If lTitulo .And. nMoedaRel == nMoedaTit .And. nMoedaBco > 1 .And. nMoedaTit > 1 .And. nTpTaxa == 2
			nValorMov := (cAlias)->E5_VLMOED2
		Else
			nValorMov := Round(xMoeda(nValorMov, nMoedaBco, nMoedaRel, dDataMovi, nCasDec, nTaxaMovi, nTaxaDest), 2)
		EndIf

		If (cAlias)->E5_RECPAG == "R"
			nValorRec := nValorMov
			If Empty((cAlias)->E5_RECONC)
				aRecon[1][REC_NAO_CONCILIADO] += nValorRec
			Else
				aRecon[1][REC_CONCILIADO] += nValorRec
			EndIf
		Else
			nValorPag := nValorMov
			If Empty((cAlias)->E5_RECONC)
				aRecon[1][PAG_NAO_CONCILIADO] += nValorPag
			Else
				aRecon[1][PAG_CONCILIADO] += nValorPag
			EndIf
		EndIf

		nSaldoRod += (nValorMov * IIf((cAlias)->E5_RECPAG == "R", 1, -1))
		nSaldoFinal := nSaldoRod

		cDataDisp := DtoC((cAlias)->E5_DTDISPO)
		cHistSE5  := AllTrim((cAlias)->E5_HISTOR)

		If Len(AllTrim((cAlias)->E5_DOCUMEN)) + Len(AllTrim((cAlias)->E5_NUMCHEQ)) > 35
			cDocument := AllTrim(SubStr((cAlias)->E5_DOCUMEN, 1, 20)) + IIf(!Empty(AllTrim((cAlias)->E5_DOCUMEN)), "-", " ") + AllTrim((cAlias)->E5_NUMCHEQ)
		Else
			cDocument := IIf(Empty((cAlias)->E5_NUMCHEQ), (cAlias)->E5_DOCUMEN, (cAlias)->E5_NUMCHEQ)
		EndIf

		If (cAlias)->E5_TIPODOC == "CH"
			cPrefTit := ChecaTp((cAlias)->(E5_NUMCHEQ + E5_BANCO + E5_AGENCIA + E5_CONTA), (cAlias)->E5_FILORIG)
		Else
			cPrefTit := (cAlias)->E5_PREFIXO + IIf(Empty((cAlias)->E5_PREFIXO), " ", "-") + (cAlias)->E5_NUMERO + IIf(Empty((cAlias)->E5_PARCELA), " ", "-") + (cAlias)->E5_PARCELA
		EndIf

		oItem := JsonObject():New()
		// Campos no formato esperado pelo backend Python / frontend de conciliacao bancaria.
		oItem["data"]                    := cDataDisp
		oItem["documento"]               := AllTrim(cDocument)
		oItem["prefixo_titulo"]          := AllTrim(cPrefTit)
		oItem["entradas"]                := Round(nValorRec, 2)
		oItem["saidas"]                  := Round(nValorPag, 2)
		oItem["saldo_atual"]             := Round(nSaldoRod, 2)
		oItem["descricao"]               := cHistSE5
		// Campos adicionais uteis para rastreabilidade e debug.
		oItem["data_disponibilidade"]    := DtoS((cAlias)->E5_DTDISPO)
		oItem["data_movimento"]          := DtoS((cAlias)->E5_DATA)
		oItem["data_disponibilidade_br"] := cDataDisp
		oItem["historico"]               := cHistSE5
		oItem["tipo_documento"]          := AllTrim((cAlias)->E5_TIPODOC)
		oItem["tipo_movimento"]          := AllTrim((cAlias)->E5_TIPO)
		oItem["natureza"]                := AllTrim((cAlias)->E5_RECPAG)
		oItem["conciliado"]              := !Empty((cAlias)->E5_RECONC)
		oItem["codigo_conciliacao"]      := AllTrim((cAlias)->E5_RECONC)
		oItem["valor_entrada"]           := Round(nValorRec, 2)
		oItem["valor_saida"]             := Round(nValorPag, 2)
		oItem["valor_movimento"]         := Round(nValorMov, 2)
		oItem["moeda_relatorio"]         := nMoedaRel

		AAdd(aAllMovs, oItem)
		(cAlias)->(DbSkip())
	EndDo

	(cAlias)->(DbCloseArea())

	nTotalReg   := Len(aAllMovs)
	nTotalPages := Max(1, Int((nTotalReg + nPageSize - 1) / nPageSize))
	nOffset     := (nPage - 1) * nPageSize

	nRecAtual := 0
	While nRecAtual < nPageSize .And. (nOffset + nRecAtual + 1) <= nTotalReg
		AAdd(aMovimentos, aAllMovs[nOffset + nRecAtual + 1])
		nRecAtual++
	EndDo

Recover Using oError
	If Select(cAlias) > 0
		(cAlias)->(DbCloseArea())
	EndIf
	oResp["erro"]     := .T.
	oResp["status"]   := 500
	oResp["mensagem"] := "Erro interno ao consultar extrato bancario: " + oError:Description
	Self:SetResponse(oResp:ToJson())
	FreeObj(oResp)
	FreeObj(oParams)
	FreeObj(oBanco)
	FreeObj(oTotais)
	AEval(aAllMovs, {|oObj| FreeObj(oObj)})
	RestArea(aArea)
Return .T.
End Sequence

cMoedaDesc := Upper(GetMv("MV_MOEDA" + LTrim(Str(nMoedaRel))))

oParams["banco"]           := cBanco
oParams["agencia"]         := cAgencia
oParams["conta"]           := cConta
oParams["data_ini"]        := DtoS(dDataIni)
oParams["data_fim"]        := DtoS(dDataFim)
oParams["moeda"]           := nMoedaRel
oParams["situacao"]        := nSituacao
oParams["linhas_pagina"]   := nLinhasPag
oParams["taxa_moeda"]      := nTpTaxa
oParams["saldo_compart"]   := nSaldoCompart
oParams["todas_filiais"]   := nTodasFiliais
oParams["data_conv_saldo"] := nDataConvSaldo
oParams["page"]            := nPage
oParams["pageSize"]        := nPageSize

oBanco["codigo"]               := AllTrim(SA6->A6_COD)
oBanco["descricao"]            := AllTrim(SA6->A6_NREDUZ)
oBanco["agencia"]              := AllTrim(SA6->A6_AGENCIA)
oBanco["conta"]                := AllTrim(SA6->A6_NUMCON)
oBanco["moeda_banco"]          := nMoedaBco
oBanco["moeda_relatorio"]      := nMoedaRel
oBanco["descricao_moeda"]      := cMoedaDesc
oBanco["saldo_inicial"]        := Round(nSaldoIni, 2)
oBanco["data_conversao_saldo"] := DtoS(dDtConvSld)

oTotais["saldo_inicial"]                 := Round(nSaldoIni, 2)
oTotais["recebimentos_nao_conciliados"] := Round(aRecon[1][REC_NAO_CONCILIADO], 2)
oTotais["recebimentos_conciliados"]     := Round(aRecon[1][REC_CONCILIADO], 2)
oTotais["recebimentos_total"]           := Round(aRecon[1][REC_NAO_CONCILIADO] + aRecon[1][REC_CONCILIADO], 2)
oTotais["pagamentos_nao_conciliados"]   := Round(aRecon[1][PAG_NAO_CONCILIADO], 2)
oTotais["pagamentos_conciliados"]       := Round(aRecon[1][PAG_CONCILIADO], 2)
oTotais["pagamentos_total"]             := Round(aRecon[1][PAG_NAO_CONCILIADO] + aRecon[1][PAG_CONCILIADO], 2)
oTotais["limite_credito"]               := Round(nLimCred, 2)
oTotais["saldo_final"]                  := Round(nSaldoFinal, 2)
oTotais["saldo_disponivel"]             := Round(nSaldoFinal + nLimCred, 2)

oResp["parametros"]      := oParams
oResp["banco"]           := oBanco
oResp["totais"]          := oTotais
oResp["total_registros"] := nTotalReg
oResp["total_pages"]     := nTotalPages
oResp["page"]            := nPage
oResp["registros"]       := aMovimentos
oResp["movimentos"]      := aMovimentos

Self:SetResponse(oResp:ToJson())

FreeObj(oResp)
RestArea(aArea)
Return .T.

Static Function F470SaldoInicial(cBanco, cAgencia, cConta, dDataIni, nSituacao, nMoedaBco, nMoedaRel, nDataConvSaldo, nDecMoeda, nSaldoCompart, dDataFim)
Local cAlias    := GetNextAlias()
Local cSql      := ""
Local cFilial   := IIf(lGestao, FWFilial("SE8"), xFilial("SE8"))
Local cFilAnt   := ""
Local nSalAtu   := 0
Local nSalRec   := 0
Local nSaldo    := 0
Local dDtConv   := dDataBase
Local aTamE5Tx2 := TamSX3("E5_TXMOEDA")
Local nDecTaxa  := IIf(Len(aTamE5Tx2) >= 2, aTamE5Tx2[2], 8)

Begin Sequence
	cSql := " SELECT E8_FILIAL, E8_DTSALAT, E8_SALATUA, E8_SALRECO "
	cSql += " FROM " + RetSqlName("SE8") + " SE8 "
	cSql += " WHERE E8_BANCO   = '" + cBanco + "' "
	cSql += "   AND E8_AGENCIA = '" + cAgencia + "' "
	cSql += "   AND E8_CONTA   = '" + cConta + "' "
	cSql += "   AND E8_DTSALAT < '" + DtoS(dDataIni) + "' "
	cSql += "   AND D_E_L_E_T_ = ' ' "
	If nSaldoCompart != 2
		cSql += "   AND E8_FILIAL = '" + cFilial + "' "
	EndIf
	cSql += " ORDER BY E8_FILIAL, E8_DTSALAT DESC "

	dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .T., .F.)
	TCSetField(cAlias, "E8_DTSALAT", "D", 8, 0)
	TCSetField(cAlias, "E8_SALATUA", "N", 16, 2)
	TCSetField(cAlias, "E8_SALRECO", "N", 16, 2)

	(cAlias)->(DbGoTop())
	If !(cAlias)->(Eof())
		cFilAnt := (cAlias)->E8_FILIAL
		nSalAtu := (cAlias)->E8_SALATUA
		nSalRec := (cAlias)->E8_SALRECO
		dDtConv := F470DtConvSaldo((cAlias)->E8_DTSALAT, nDataConvSaldo, dDataIni, dDataFim)

		While !(cAlias)->(Eof())
			If (cAlias)->E8_FILIAL != cFilAnt
				nSalAtu += (cAlias)->E8_SALATUA
				nSalRec += (cAlias)->E8_SALRECO
				cFilAnt  := (cAlias)->E8_FILIAL
			EndIf
			(cAlias)->(DbSkip())
		EndDo
	EndIf

	(cAlias)->(DbCloseArea())

	If nSituacao == 2
		nSaldo := nSalRec
	ElseIf nSituacao == 3
		nSaldo := (nSalAtu - nSalRec)
	Else
		nSaldo := nSalAtu
	EndIf

	nSaldo := Round(xMoeda(nSaldo, nMoedaBco, nMoedaRel, dDtConv, nDecTaxa), nDecMoeda)

Recover
	If Select(cAlias) > 0
		(cAlias)->(DbCloseArea())
	EndIf
	nSaldo  := 0
	dDtConv := dDataBase
End Sequence

Return { nSaldo, dDtConv }

Static Function F470DtConvSaldo(dSaldoSE8, nDataConvSaldo, dDataIni, dDataFim)
Local dRet := dSaldoSE8

Do Case
	Case nDataConvSaldo == 2
		dRet := dDataBase
	Case nDataConvSaldo == 3
		dRet := dDataIni
	Case nDataConvSaldo == 4
		dRet := dDataFim
	Otherwise
		dRet := dSaldoSE8
EndCase

Return dRet

Static Function FR470Tab14()
Local cTabela14 := ""
Local aRetSX5   := FWGetSX5("14", , "pt-br")
Local nX        := 0

For nX := 1 To Len(aRetSX5)
	If cPaisLoc != "BRA"
		cTabela14 += AllTrim(aRetSX5[nX, 3]) + "/"
	Else
		cTabela14 += SubStr(AllTrim(aRetSX5[nX, 3]), 1, 2) + "/"
	EndIf
Next nX

If cPaisLoc == "BRA"
	If !Empty(cTabela14)
		cTabela14 := SubStr(cTabela14, 1, Len(cTabela14) - 1)
	EndIf
Else
	cTabela14 += "/$ "
EndIf

Return cTabela14

Static Function ChecaTp(cChaveTp, cFilOrig)
Local cRetorno := ""
Local cChavSef := ""

dbSelectArea("SEF")
SEF->(DbSetOrder(4))
cChavSef := xFilial("SE5") + cChaveTp

If !SEF->(DbSeek(cChavSef))
	cChavSef := cFilOrig + cChaveTp
	SEF->(DbSeek(cChavSef))
EndIf

While !SEF->(Eof()) .And. SEF->(EF_FILIAL + EF_NUM + EF_BANCO + EF_AGENCIA + EF_CONTA) == cChavSef
	If !Empty(SEF->EF_TIPO)
		cRetorno := SEF->EF_PREFIXO + IIf(Empty(SEF->EF_PREFIXO), " ", "-") + SEF->EF_TITULO + IIf(Empty(SEF->EF_PARCELA), " ", "-") + SEF->EF_PARCELA
		Exit
	EndIf
	SEF->(DbSkip())
EndDo

Return cRetorno

Static Function F470MontaErro(cCode, cMessage, cDetails)
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


