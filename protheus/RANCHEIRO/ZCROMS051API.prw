#Include "Protheus.ch"
#Include "restful.ch"
#Include "APWEBSRV.ch"

/*/{Protheus.doc} ZCROMS051API
API REST equivalente ao relatorio customizado CROMS051 (Conta Corrente Desconto).
Substitui a tela de perguntas (SX1) por parametros de query string e troca a
saida em Excel (u_Excel2) por um array JSON, mantendo as mesmas regras de
negocio do fonte original: montagem da base via UNION ALL (SE1/SE5, Z0V/Z0W,
Z12/SE2), quebra de subtotal por cliente e extracao do numero de
acordo/contrato a partir do historico quando NUM CLI nao esta preenchido.

Endpoint: GET /rest/zcroms051api/api/v1/croms051

Parametros:
  cliente          = codigo do cliente unico (default "" = todos os clientes)
                     Quando informado, filtra tambem os clientes da mesma rede
                     (Z0S/Z0W), igual ao relatorio original.
  considera_data    = "1"=Sim "2"=Nao (default "2")
                     Quando "1", data_de e data_ate sao obrigatorios e os
                     registros sao filtrados pela DATA do movimento.
  data_de           = data inicial YYYYMMDD (obrigatorio se considera_data=1)
  data_ate          = data final   YYYYMMDD (obrigatorio se considera_data=1)
  modalidade_nova   = "1"=Sim "2"=Nao (default "2")
                     Quando "1", restringe titulos SE1/SE5 a E1_EMISSAO
                     posterior ao parametro MV_XULDESC.
  vendedor          = codigo do vendedor unico (default "" = todos)
  filiais           = lista de filiais separadas por virgula (default = filial
                     corrente da conexao REST)
  page              = pagina (default 1)
  pageSize          = registros por pagina (default 5000, max 5000)

Retorno JSON:
  parametros      = parametros efetivos usados
  total_registros = total de linhas processadas ate o fim da pagina solicitada
  total_pages     = total de paginas
  page            = pagina atual
  hasMore         = ha mais paginas
  linhas          = registros da pagina

Campos por linha:
  modalidade, vendedor, codigo_cliente, loja, cliente, unidade, data, origem,
  tipo, tipo_nota, filial, serie, numero, saldo_inicial, valor,
  valor_associacao, subtotal, numero_cliente, historico, ordenacao,
  lancamento, desconto_boleto, desconto_pago, acordo, contrato

@type Function
@author Equipe Desenvolvimento
@since 27/07/2026
@version 1.0
/*/

wsrestful ZCROMS051API description "CROMS051 - Conta Corrente Desconto"

	wsdata page             as string
	wsdata pageSize         as string
	wsdata cliente          as string
	wsdata considera_data   as string
	wsdata data_de          as string
	wsdata data_ate         as string
	wsdata modalidade_nova  as string
	wsdata vendedor         as string
	wsdata filiais          as string

	wsmethod GET getContaCorrenteDesconto description "Conta Corrente Desconto por cliente" wssyntax "/api/v1/croms051" PATH "/api/v1/croms051"

EndwsRestFul


// =============================================================================
// wsmethod GET ZCROMS051API
// =============================================================================
wsmethod GET getContaCorrenteDesconto WSRESTFUL ZCROMS051API
Local aArea         := GetArea()
Local oResp         := JsonObject():New()
Local oParams       := JsonObject():New()
Local aLinhas       := {}
Local oItem         := Nil
Local oError        := Nil
Local cAlias        := GetNextAlias()
Local cSql          := ""
Local cLogPrefix    := "[ZCROMS051API] "

Local cCliente         := AllTrim(Self:cliente)
Local cConsideraData   := IIf(Empty(AllTrim(Self:considera_data)),  "2", AllTrim(Self:considera_data))
Local cDataDe          := AllTrim(Self:data_de)
Local cDataAte         := AllTrim(Self:data_ate)
Local cModalidadeNova  := IIf(Empty(AllTrim(Self:modalidade_nova)), "2", AllTrim(Self:modalidade_nova))
Local cVendedor        := AllTrim(Self:vendedor)
Local cFiliaisParam    := AllTrim(Self:filiais)
Local nPage            := Max(1, Val(AllTrim(Self:page)))
Local nPageSize        := Val(AllTrim(Self:pageSize))

Local lConsideraData   := (cConsideraData == "1")
Local lModalidadeNova  := (cModalidadeNova == "1")
Local dDataDe          := CtoD("")
Local dDataAte         := CtoD("")
Local aFiliais         := {}
Local cFiliaisIn       := ""
Local nI               := 0

Local nTotalReg     := 0
Local nTotalPages   := 1
Local nOffset        := 0
Local lHasMore       := .F.

// Estado de quebra por cliente (identico ao loop "imprime" do CROMS051 original)
Local nSubTot        := 0
Local cUltCli        := ""
Local cAcoAtu        := ""
Local cHisAtu         := ""
Local nPosNum         := 999
Local nSeqOri         := 0
Local nSaldoIni        := 0
Local nX                := 0
Local lPrim              := .T.

Self:SetContentType("application/json")

// -------------------------------------------------------------------------
// Validacoes
// -------------------------------------------------------------------------
If lConsideraData .And. (Len(cDataDe) <> 8 .Or. Len(cDataAte) <> 8)
	Self:nStatusCode := 422
	Self:cResponse   := CROMS051MontaErro("VALIDATION_ERROR", ;
		"Quando considera_data=1, data_de e data_ate sao obrigatorios no formato YYYYMMDD", "")
	FreeObj(oResp)
	FreeObj(oParams)
	RestArea(aArea)
Return .T.
EndIf

If Len(cDataDe) == 8
	dDataDe := StoD(cDataDe)
EndIf
If Len(cDataAte) == 8
	dDataAte := StoD(cDataAte)
EndIf

nPageSize := IIf(nPageSize <= 0 .Or. nPageSize > 5000, 5000, nPageSize)
nOffset   := (nPage - 1) * nPageSize

// -------------------------------------------------------------------------
// Filiais: lista explicita via parametro ou filial corrente como fallback
// (equivalente ao AdmGetFil(.F.,.F.,"SE1") / {cFilAnt} do relatorio original)
// -------------------------------------------------------------------------
If !Empty(cFiliaisParam)
	aFiliais := StrTokArr(cFiliaisParam, ",")
	For nI := 1 To Len(aFiliais)
		aFiliais[nI] := AllTrim(aFiliais[nI])
	Next
Else
	aFiliais := { xFilial("SE1") }
EndIf

For nI := 1 To Len(aFiliais)
	If nI > 1
		cFiliaisIn += ","
	EndIf
	cFiliaisIn += "'" + aFiliais[nI] + "'"
Next

ConOut(cLogPrefix + "Requisicao recebida | cliente=[" + cCliente + "] considera_data=" + cConsideraData + ;
	" data_de=" + cDataDe + " data_ate=" + cDataAte + " modalidade_nova=" + cModalidadeNova + ;
	" vendedor=[" + cVendedor + "] filiais=[" + cFiliaisIn + "] page=" + cValToChar(nPage) + ;
	" pageSize=" + cValToChar(nPageSize))

// -------------------------------------------------------------------------
// Monta SQL (identico ao geratmp() do CROMS051 original)
// -------------------------------------------------------------------------
cSql := "WITH ClientesRede AS ("
cSql += "	SELECT DISTINCT " + CRLF
cSql += " 		A1_COD " + CRLF
cSql += " 	FROM " + CRLF
cSql += " 		" + RetSqlName("SA1") + " SA1 " + CRLF
cSql += " 	WHERE " + CRLF
cSql += " 		D_E_L_E_T_ = ' ' " + CRLF
cSql += " 		AND A1_CLIREDE IN ( " + CRLF
cSql += " 			SELECT " + CRLF
cSql += " 				A1_CLIREDE " + CRLF
cSql += " 			FROM " + CRLF
cSql += " 				" + RetSqlName("SA1") + CRLF
cSql += " 			WHERE " + CRLF
cSql += " 				D_E_L_E_T_ = ' ' " + CRLF
cSql += " 				AND A1_COD = '" + cCliente + "' " + CRLF
cSql += " 		) " + CRLF
cSql += "	 	AND EXISTS ( " + CRLF
cSql += " 			SELECT " + CRLF
cSql += " 				Z0S_FILIAL " + CRLF
cSql += "	 		FROM " + CRLF
cSql += " 				" + RetSqlName("Z0S") + CRLF
cSql += " 			WHERE " + CRLF
cSql += "	 			D_E_L_E_T_ = ' ' " + CRLF
cSql += " 				AND Z0S_CLIENT = SA1.A1_COD " + CRLF
cSql += " 				AND Z0S_LOJA = SA1.A1_LOJA " + CRLF
cSql += " 		) " + CRLF
cSql += ")"

cSql += " SELECT "
cSql += " 	(CASE WHEN A1_COD IN ('020443','027778') THEN 0 ELSE 9 END) PRIORIDADE, "
cSql += " 	(CASE WHEN E1_EMISSAO > '" + DtoS(GetNewPar("MV_XULDESC", StoD("20190531"))) + "' THEN 'NOVA' ELSE 'ANTIGA' END) MODALIDADE, "
cSql += " 	E5_CLIENTE CODCLI, "
cSql += " 	E5_LOJA LOJA, "
cSql += " 	A1_NOME CLIENTE,	 "
cSql += " 	A1_NREDUZ UNIDADE, "
cSql += " 	E5_DTDISPO DATA, "
cSql += " 	'BAIXA' ORIGEM, "
cSql += " 	CASE  "
cSql += " 		WHEN E5_TIPODOC = 'ES' THEN 'CREDITO' "
cSql += " 		ELSE 'DESCONTO' "
cSql += " 	END AS TIPO, "
cSql += " 	'SAIDA' TPNOTA, "
cSql += " 	E5_FILIAL FILIAL, "
cSql += " 	E5_PREFIXO SERIE, "
cSql += " 	E5_NUMERO NUMERO, "
cSql += " 	E1_VEND1 VENDEDOR, "
cSql += " 	CASE  "
cSql += " 		WHEN E5_TIPODOC = 'ES' THEN E5_VLDESCO "
cSql += " 		ELSE E5_VLDESCO*-1 "
cSql += " 	END AS VALOR, "
cSql += " 	0 AS VALORASS, "
cSql += " 	' ' AS NUMCLI, "
cSql += " 	CASE "
cSql += " 		WHEN E5_ARQCNAB <> ' ' THEN "
cSql += "			CASE WHEN E1_XOBSDN <> ' ' "
cSql += "				THEN CAST(ROUND(E5_VLDESCO/(E5_VALOR+E5_VLDESCO)*100,2) AS VARCHAR) + '% BX AUTO BOL - ' + LTRIM(RTRIM(E1_XOBSDN)) "
cSql += "				ELSE CAST(ROUND(E5_VLDESCO/(E5_VALOR+E5_VLDESCO)*100,2) AS VARCHAR) + '% BAIXA AUTOMATICA BOLETO' "
cSql += "			END "
cSql += " 		ELSE E5_HISTOR  "
cSql += " 	END AS HISTORICO, "
cSql += " 	'N' EHMOV, "
cSql += " 	'N' DESBOL, "
cSql += "  'N' as EHASSOC, "
cSql += "  'N' as EDESCPG, "
cSql += "  E5_XNUMACO AS NUMEROACORDO, "
cSql += "  '' AS NUMEROCONTRATO "
cSql += " FROM "
cSql += " 	" + RetSqlName("SE5") + " SE5 "
cSql += " 	JOIN " + RetSqlName("SE1") + " SE1 ON "
cSql += " 	( "
cSql += " 		E1_FILIAL = E5_FILIAL "
cSql += " 		AND E1_PREFIXO = E5_PREFIXO "
cSql += " 		AND E1_NUM = E5_NUMERO "
cSql += " 		AND E1_PARCELA = E5_PARCELA "
cSql += " 		AND SE1.D_E_L_E_T_ = ' ' "
If lModalidadeNova
	cSql += " 		AND E1_EMISSAO > '" + DtoS(GetNewPar("MV_XULDESC", StoD("20190531"))) + "' "
EndIf
If !Empty(cVendedor)
	cSql += " 		AND E1_VEND1 = '" + cVendedor + "' "
EndIf
cSql += " 	) "
cSql += " 	JOIN " + RetSqlName("SA1") + " SA1 ON "
cSql += " 	( "
cSql += " 		E1_CLIENTE = A1_COD "
cSql += " 		AND E1_LOJA = A1_LOJA "
cSql += " 		AND SA1.D_E_L_E_T_ = ' ' "
If !Empty(cCliente)
	cSql += " 		AND E1_CLIENTE IN ( SELECT * FROM ClientesRede) "
EndIf
cSql += " 	) "
cSql += " WHERE "
cSql += " 	SE5.D_E_L_E_T_ = ' ' "
cSql += "  AND E5_FILIAL IN (" + cFiliaisIn + ") "
cSql += " 	AND E5_VLDESCO > 0 "
cSql += " 	AND ( E5_TIPO NOT IN ('NCC','RA') )"
cSql += " 	AND E5_MOTBX <> 'CMP'"
cSql += " 	AND E1_XNUMCAR <> '' "
cSql += " 	AND EXISTS "
cSql += " ( "
cSql += " 		SELECT "
cSql += " 			Z0S_CLIENT "
cSql += " 		FROM "
cSql += " 			" + RetSqlName("Z0S") + " "
cSql += " 		WHERE "
cSql += " 			D_E_L_E_T_ = ' ' "
cSql += " 			AND Z0S_CLIENT = SE1.E1_CLIENTE "
cSql += " 		UNION ALL "
cSql += " 		SELECT "
cSql += " 			Z0W_CLIENT "
cSql += " 		FROM "
cSql += " 			" + RetSqlName("Z0W") + " "
cSql += " 		WHERE "
cSql += " 			D_E_L_E_T_ = ' ' "
cSql += " 			AND Z0W_FILIAL IN (" + cFiliaisIn + ") "
cSql += " 			AND Z0W_CLIENT = SE1.E1_CLIENTE "
cSql += " ) "

cSql += " UNION ALL "

cSql += " SELECT "
cSql += " 	(CASE WHEN A1_COD IN ('020443','027778') THEN 0 ELSE 9 END) PRIORIDADE, "
cSql += " 	'NOVA' MODALIDADE, "
cSql += " 	Z0V_CLIENT CODCLI, "
cSql += " 	Z0V_LOJA LOJA, "
cSql += " 	A1_NOME CLIENTE,	 "
cSql += " 	A1_NREDUZ UNIDADE, "
cSql += " 	Z0V_DTDOC DATA, "
cSql += " 	CASE "
cSql += " 		WHEN Z0V_ORIGEM = 'C' THEN 'CONTRATO' "
cSql += " 		ELSE 'ACORDO' "
cSql += " 	END AS ORIGEM, "
cSql += " 	CASE "
cSql += " 		WHEN Z0V_TIPO = 'D' THEN 'PROVISAO' "
cSql += " 		ELSE 'ESTORNO' "
cSql += " 	END AS TIPO, "
cSql += " 	CASE "
cSql += " 		WHEN Z0V_TPNF = 'S' THEN 'SAIDA' "
cSql += " 		ELSE 'DEVOLUCAO' "
cSql += " 	END TPNOTA,	 "
cSql += " 	Z0V_FILIAL FILIAL, "
cSql += " 	Z0V_SERIE SERIE, "
cSql += " 	Z0V_DOC NUMERO, "
cSql += " 	Z0V_VEND VEND, "
cSql += " 	CASE "
cSql += " 		WHEN Z0V_TIPO = 'D' THEN Z0V_VALTOT "
cSql += " 		ELSE Z0V_VALTOT * -1 "
cSql += " 	END AS VALOR, "
cSql += " 	CASE "
cSql += " 		WHEN Z0V_TIPO = 'D' THEN Z0V_VALASS "
cSql += " 		ELSE Z0V_VALASS * -1 "
cSql += " 	END AS VALORASS, "
cSql += " 	Z0V_NUMCLI NUMCLI, "
cSql += " 	Z0V_OBS HISTORICO, "
cSql += " 	ISNULL(Z0W_MOV,'N') EHMOV, "
cSql += " 	Z0V_DESBOL DESBOL, "
cSql += " 'N' as EHASSOC, "
cSql += "  Z0V_DESCPG as EDESCPG, "
cSql += "  Z0V_NUMACO AS NUMEROACORDO, "
cSql += "  Z0V_NUMCTR AS NUMEROCONTRATO "
cSql += " FROM "
cSql += " 	" + RetSqlName("Z0V") + " Z0V "
cSql += " 	JOIN " + RetSqlName("SA1") + " SA1 ON "
cSql += " 	( "
cSql += " 		Z0V_CLIENT = A1_COD "
cSql += " 		AND Z0V_LOJA = A1_LOJA "
cSql += " 		AND SA1.D_E_L_E_T_ = ' ' "
cSql += " 	) "
cSql += " 	LEFT JOIN " + RetSqlName("Z0W") + " Z0W ON "
cSql += " 	( "
cSql += " 		Z0V_FILIAL = Z0W_FILIAL "
cSql += " 		AND Z0V_NUMACO = Z0W_CODIGO "
cSql += " 		AND Z0W.D_E_L_E_T_ = ' ' "
cSql += " 	) "
cSql += " WHERE "
cSql += " 	Z0V.D_E_L_E_T_ = ' ' "
cSql += "  AND Z0V_FILIAL IN (" + cFiliaisIn + ") "
If !Empty(cCliente)
	cSql += " 		AND Z0V_CLIENT IN ( SELECT * FROM ClientesRede) "
EndIf
If !Empty(cVendedor)
	cSql += " 	AND Z0V_VEND = '" + cVendedor + "' "
EndIf

cSql += " UNION ALL "

cSql += " select "
cSql += " 	(CASE WHEN A1_COD IN ('020443','027778') THEN 0 ELSE 9 END) PRIORIDADE, "
cSql += " 'NOVA' AS MODALIDADE, "
cSql += " A1_COD AS CODCLI, "
cSql += " A1_LOJA AS LOJA, "
cSql += " A1_NOME AS CLIENTE, "
cSql += " A1_NREDUZ AS UNIDADE, "
cSql += " E2_EMISSAO AS DATA, "
cSql += " 'SOPAG' AS ORIGEM, "
cSql += " 'DESCONTO' AS TIPO, "
cSql += " 'TITULO' AS TPNOTA, "
cSql += " E2_FILIAL AS FILIAL, "
cSql += " E2_PREFIXO AS SERIE, "
cSql += " E2_NUM AS NUMERO, "
cSql += " A1_VEND AS VENDEDOR, "
cSql += " CASE WHEN SUBSTRING(A1_CGC,1,8) = SUBSTRING(A2_CGC,1,8) THEN E2_VALOR*-1 ELSE 0 END AS VALOR, "
cSql += " CASE WHEN SUBSTRING(A1_CGC,1,8) = SUBSTRING(A2_CGC,1,8) THEN 0 ELSE E2_VALOR*-1 END as VALORASS, "
cSql += " ' ' as NUMCLI, "
cSql += " E2_HIST HISTORICO, "
cSql += " 'N' as EHMOV, "
cSql += " 'N' as DESBOL, "
cSql += " CASE WHEN SUBSTRING(A1_CGC,1,8) = SUBSTRING(A2_CGC,1,8) THEN 'N' ELSE 'S' END as EHASSOC, "
cSql += "  'N' as EDESCPG, "
cSql += "  '' AS NUMEROACORDO, "
cSql += "  '' AS NUMEROCONTRATO "
cSql += " FROM " + RetSqlName("Z12") + " Z12 "
cSql += " JOIN " + RetSqlName("SA1") + " SA1 ON "
cSql += " SA1.D_E_L_E_T_ = ' ' "
cSql += " AND A1_COD = Z12_CLIASS "
cSql += " AND A1_LOJA = Z12_LOJASS "
If !Empty(cVendedor)
	cSql += " 	AND A1_VEND = '" + cVendedor + "' "
EndIf
If !Empty(cCliente)
	cSql += " 		AND A1_COD IN ( SELECT * FROM ClientesRede) "
EndIf
cSql += " JOIN " + RetSqlName("SA2") + " SA2 ON "
cSql += " SA2.D_E_L_E_T_ = ' ' "
cSql += " AND A2_COD = Z12_CODFOR "
cSql += " AND A2_LOJA = Z12_LOJA "
cSql += " JOIN " + RetSqlName("SE2") + " SE2 ON "
cSql += " SE2.D_E_L_E_T_ = ' ' "
cSql += " AND E2_PREFIXO = 'SOP' "
cSql += " AND E2_NUM = Z12_NUM "
cSql += " AND E2_FORNECE = Z12_CODFOR "
cSql += " AND E2_LOJA = Z12_LOJA "
cSql += " AND E2_FILIAL = Z12_FILIAL "
cSql += " WHERE "
cSql += " Z12.D_E_L_E_T_ = ' ' "
cSql += " AND Z12_FILIAL IN (" + cFiliaisIn + ") "

cSql += " ORDER BY PRIORIDADE, CODCLI, DATA, TIPO DESC "

// -------------------------------------------------------------------------
// Executa query e processa registros
// -------------------------------------------------------------------------
Begin Sequence

	dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .F., .T.)
	ConOut(cLogPrefix + "SQL executado - LastRec=" + Str((cAlias)->(LastRec()), 6))

	TCSetField(cAlias, "DATA",     "D", 8, 0)
	TCSetField(cAlias, "VALOR",    "N", 16, 2)
	TCSetField(cAlias, "VALORASS", "N", 16, 2)

	(cAlias)->(DbGoTop())

	While !(cAlias)->(Eof())

		If !Empty(cCliente)
			cUltCli := cCliente
		Else
			cUltCli := (cAlias)->CODCLI
		EndIf

		If lPrim .And. (cAlias)->DATA >= dDataDe .And. AllTrim((cAlias)->MODALIDADE) == "NOVA"
			nSaldoIni := nSubTot
			lPrim := .F.
		EndIf

		nSeqOri++
		If AllTrim((cAlias)->MODALIDADE) == "NOVA"
			nSubTot += (cAlias)->VALOR - IIf(AllTrim((cAlias)->EHASSOC) != "S", (cAlias)->VALORASS, 0)
		EndIf

		// Resolve numero de acordo/contrato: usa NUMCLI quando preenchido, senao
		// tenta extrair do HISTORICO (mesma heuristica do CROMS051 original)
		If !Empty(AllTrim((cAlias)->NUMCLI))
			cAcoAtu := AllTrim((cAlias)->NUMCLI)
		Else
			cAcoAtu := ""
			nPosNum := 999
			cHisAtu := AllTrim((cAlias)->HISTORICO)
			If !"% BAIXA AUTOMATICA BOLETO" $ cHisAtu
				For nX := 0 To 9
					If At(cValToChar(nX), cHisAtu) > 0 .And. At(cValToChar(nX), cHisAtu) < Len(cHisAtu) .And. At(cValToChar(nX), cHisAtu) < nPosNum
						nPosNum := At(cValToChar(nX), cHisAtu)
					EndIf
				Next
				If nPosNum < 999
					If Substr(cHisAtu, nPosNum + 1, 1) != "%"
						While nPosNum <= Len(cHisAtu) .And. Substr(cHisAtu, nPosNum, 1) $ "0123456789/-"
							cAcoAtu += Substr(cHisAtu, nPosNum, 1)
							nPosNum++
						EndDo
					EndIf
				EndIf
			EndIf
		EndIf

		If (lConsideraData .And. (cAlias)->DATA >= dDataDe .And. (cAlias)->DATA <= dDataAte) .Or. !lConsideraData

			nTotalReg++

			If nTotalReg > nOffset .And. Len(aLinhas) < nPageSize

				oItem := JsonObject():New()
				oItem["modalidade"]         := AllTrim((cAlias)->MODALIDADE)
				oItem["vendedor"]           := AllTrim((cAlias)->VENDEDOR)
				oItem["codigo_cliente"]     := AllTrim((cAlias)->CODCLI)
				oItem["loja"]               := AllTrim((cAlias)->LOJA)
				oItem["cliente"]            := AllTrim((cAlias)->CLIENTE)
				oItem["unidade"]            := AllTrim((cAlias)->UNIDADE)
				oItem["data"]               := DtoS((cAlias)->DATA)
				oItem["origem"]             := AllTrim((cAlias)->ORIGEM)
				oItem["tipo"]               := AllTrim((cAlias)->TIPO)
				oItem["tipo_nota"]          := AllTrim((cAlias)->TPNOTA)
				oItem["filial"]             := AllTrim((cAlias)->FILIAL)
				oItem["serie"]              := AllTrim((cAlias)->SERIE)
				oItem["numero"]             := AllTrim((cAlias)->NUMERO)
				oItem["saldo_inicial"]      := Round(nSaldoIni, 2)
				oItem["valor"]              := Round((cAlias)->VALOR, 2)
				oItem["valor_associacao"]   := Round((cAlias)->VALORASS, 2)
				oItem["subtotal"]           := Round(nSubTot, 2)
				oItem["numero_cliente"]     := cAcoAtu
				oItem["historico"]          := AllTrim((cAlias)->HISTORICO)
				oItem["ordenacao"]          := nSeqOri
				oItem["lancamento"]         := IIf(AllTrim((cAlias)->EHMOV) == "S", "MOV", "PROTHEUS")
				oItem["desconto_boleto"]    := (AllTrim((cAlias)->DESBOL) == "S")
				oItem["desconto_pago"]      := (AllTrim((cAlias)->EDESCPG) == "S")
				oItem["acordo"]             := AllTrim((cAlias)->NUMEROACORDO)
				oItem["contrato"]           := AllTrim((cAlias)->NUMEROCONTRATO)

				AAdd(aLinhas, oItem)
			EndIf
		EndIf

		(cAlias)->(DbSkip())

		If !(cAlias)->(Eof()) .And. !((cAlias)->CODCLI $ cUltCli)
			nSubTot := 0
			nSeqOri := 0
			lPrim   := .T.
		EndIf
	EndDo

	(cAlias)->(DbCloseArea())

	// Paginacao real: o loop acima percorre o cursor inteiro (sem sair
	// antecipadamente), entao nTotalReg reflete o total de linhas filtradas
	// e nTotalPages/lHasMore podem ser calculados com precisao.
	nTotalPages := Max(1, Int((nTotalReg + nPageSize - 1) / nPageSize))
	lHasMore    := (nPage < nTotalPages)

	ConOut(cLogPrefix + "Pagina montada | registros_retornados=" + cValToChar(Len(aLinhas)) + ;
		" total_processado=" + cValToChar(nTotalReg) + " hasMore=" + IIf(lHasMore, "S", "N"))

Recover Using oError
	If Select(cAlias) > 0
		(cAlias)->(DbCloseArea())
	EndIf
	ConOut(cLogPrefix + "ERRO INTERNO: " + oError:Description)
	Self:nStatusCode := 500
	Self:cResponse   := CROMS051MontaErro("INTERNAL_ERROR", "Erro interno ao consultar conta corrente desconto", oError:Description)
	FreeObj(oResp)
	FreeObj(oParams)
	AEval(aLinhas, {|o| FreeObj(o)})
	RestArea(aArea)
Return .T.
End Sequence

// Monta resposta
oParams["cliente"]         := cCliente
oParams["considera_data"]  := cConsideraData
oParams["data_de"]         := cDataDe
oParams["data_ate"]        := cDataAte
oParams["modalidade_nova"] := cModalidadeNova
oParams["vendedor"]        := cVendedor
oParams["filiais"]         := cFiliaisIn
oParams["page"]            := nPage
oParams["pageSize"]        := nPageSize

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


// =============================================================================
// Static Function CROMS051MontaErro
// =============================================================================
Static Function CROMS051MontaErro(cCode, cMessage, cDetails)
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
