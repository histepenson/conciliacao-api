#Include "Protheus.ch"
#INCLUDE "restful.CH"
#Include "APWEBSRV.ch"
#Include "FWCOMMAND.CH"

/*/{Protheus.doc} ZCTBR140API
API REST equivalente ao relatorio CTBR140 (Balancete de Conta/Item).
Aceita os parametros principais do relatorio e calcula diretamente via SQL
os saldos de debito, credito, saldo anterior e saldo atual por conta/item
usando a tabela CQ5 (saldos diarios pre-calculados, tipo CT4), com join em
CT1 (plano de contas) e CTD (itens/centros de custo) para descricoes e
indicadores de normal/classe.

Endpoint: GET /rest/api/v1/ctbr140

Calculo de saldos (espelha logica do CTGerPlan/CTBR140 original):
  SALDOANTDB   = SUM(CQ5_DEBITO) ate dBefore   -> debito acumulado anterior
  SALDOANTCR   = SUM(CQ5_CREDIT) ate dBefore   -> credito acumulado anterior
  SALDOANT     = SALDOANTDB - SALDOANTCR        -> positivo = saldo devedor
  SALDODEB     = SUM(CQ5_DEBITO) no periodo     -> sempre positivo
  SALDOCRD     = SUM(CQ5_CREDIT) no periodo     -> sempre positivo
  MOVIMENTO    = SALDODEB - SALDOCRD            -> positivo = debito liquido
  SALDOATU     = SALDOANT + MOVIMENTO           -> positivo = saldo devedor

Interpretacao do sinal via normal_cta:
  "1" (debito normal)  -> positivo = saldo normal
  "2" (credito normal) -> negativo = saldo normal (creditos superam debitos)

@type Function
@author Equipe Desenvolvimento
@since 18/03/2026
@version 2.0
/*/

// =============================================================================
// Registro do endpoint REST
// =============================================================================
wsrestful ZCTBR140API description "CTBR140 - Balancete de Conta/Item"

	// Paginacao
	wsdata page             as string
	wsdata pageSize         as string

	// par01/02 - Periodo
	// data_ini: default = 1o dia do ano de data_fim
	wsdata data_ini         as string   // YYYYMMDD - inicio do periodo
	wsdata data_fim         as string   // YYYYMMDD - fim do periodo (obrigatorio)

	// par03/04 - Range de Conta (CT1_CONTA)
	wsdata conta_de         as string
	wsdata conta_ate        as string

	// par05/06 - Range de Item / Centro de Custo (CTD_ITEM)
	wsdata item_de          as string
	wsdata item_ate         as string

	// par07 - Tipo do balancete (1=Analitico 2=Sintetico 3=Ambos)
	wsdata tipo_balancete   as string

	// par08 - Set of Books (codigo - afeta mascara; nao filtra diretamente)
	wsdata set_of_books     as string

	// par09 - Valores zerados (1=Inclui 2=Exclui) default: 2
	wsdata vlr_zerado       as string

	// par10 - Moeda (default: 1)
	wsdata moeda            as string

	// par12 - Tipo de Lancamento (vazio ou "1" = todos os tipos)
	wsdata tp_lanc          as string

	// par18 - Retorna coluna movimento na resposta (1=Sim 2=Nao) default: 1
	wsdata imp_mov          as string

	// par24 - Dividir valores por (1=Nenhum 2=100 3=1000 4=1000000) default: 1
	wsdata divide_por       as string

	// par26/27 - Saldo anterior calculado ate data_lp em vez de data_ini-1
	wsdata sld_ant_lp       as string   // 1=Usa data_lp  2=Usa data_ini-1  default: 2
	wsdata data_lp          as string   // YYYYMMDD - data base LP para saldo anterior

	// par28 - Filiais (1=Range de filiais  2=Filial corrente) default: 2
	wsdata consid_filiais   as string
	wsdata filial_de        as string
	wsdata filial_ate       as string

	wsmethod GET getBalancete description "Balancete de Conta/Item por periodo" wssyntax "/api/v1/ctbr140" PATH "/api/v1/ctbr140"

EndwsRestFul


// =============================================================================
// wsmethod GET ZCTBR140API
// =============================================================================
wsmethod GET getBalancete WSRESTFUL ZCTBR140API

Local aArea         := GetArea()
Local oResp         := JsonObject():New()
Local oParams       := JsonObject():New()
Local aLinhas       := {}
Local aAllLinhas    := {}
Local oLinha        := Nil
Local oError        := Nil
Local cSql          := ""
Local cAlias        := GetNextAlias()

Local cLogFile
Local cLogConteudo

// Acumuladores por registro
Local nSaldoAntDB   := 0
Local nSaldoAntCR   := 0
Local nSaldoAnt     := 0
Local nDebito       := 0
Local nCredito      := 0
Local nMovimento    := 0
Local nSaldoAtu     := 0
Local lAddItem      := .F.

// Parametros recebidos via query string
Local cDataIni      := AllTrim(Self:data_ini)
Local cDataFim      := AllTrim(Self:data_fim)
Local cContaDe      := AllTrim(Self:conta_de)
Local cContaAte     := AllTrim(Self:conta_ate)
Local cItemDe       := AllTrim(Self:item_de)
Local cItemAte      := AllTrim(Self:item_ate)
Local cTipoBalanc   := AllTrim(Self:tipo_balancete)
Local cVlrZerado    := AllTrim(Self:vlr_zerado)
Local cMoeda        := AllTrim(Self:moeda)
Local cTpLanc       := AllTrim(Self:tp_lanc)
Local cImpMov       := AllTrim(Self:imp_mov)
Local cDividePor    := AllTrim(Self:divide_por)
Local cSldAntLP     := AllTrim(Self:sld_ant_lp)
Local cDataLP       := AllTrim(Self:data_lp)
Local cConsidFil    := AllTrim(Self:consid_filiais)
Local cFilialDe     := AllTrim(Self:filial_de)
Local cFilialAte    := AllTrim(Self:filial_ate)
Local nPage         := Max(1, Val(AllTrim(Self:page)))
Local nPageSize     := Val(AllTrim(Self:pageSize))

// Variaveis de conversao e controle
Local dDataIni      := CtoD("")
Local dDataFim      := CtoD("")
Local dDataLP_      := CtoD("")
Local dBefore       := CtoD("")
Local nMoeda        := 1
Local nTipoBalanc   := 3
Local nDivide       := 1
Local nDividePor    := 1
Local nConsidFil    := 2
Local lSldAntLP     := .F.
Local lInclZeros    := .F.
Local lImpMov       := .T.
Local cFilialCT1    := ""
Local cFilialCTD    := ""
Local cFilialCQ5    := ""
Local cMoedaFmt     := ""
Local nTotalReg     := 0
Local nTotalPages   := 1
Local nOffset       := 0
Local nRecAtual     := 0

// Tamanhos de campos
Local aTamConta     := {}
Local aTamItem      := {}
Local aTamFilial    := {}
Local aTamVlr       := {}
Local nTamConta     := 20   // fallback CT1_CONTA
Local nTamItem      := 9    // fallback CTD_ITEM
Local nTamFilial    := 2    // fallback CQ5_FILIAL
Local nTamVlr       := 20   // fallback CT2_VALOR
Local nDecVlr       := 4    // fallback CT2_VALOR decimais

Local cTpSald
Local cFilCQ5Cond   := ""

Self:SetContentType("application/json")

// -------------------------------------------------------------------------
// Ambiente inicializado pelo framework REST via tenantId no header.
// Nao usar RpcSetEnv/RpcClearEnv — conflita com o contexto do framework.
// -------------------------------------------------------------------------

// -------------------------------------------------------------------------
// Validacao obrigatoria: data_fim
// -------------------------------------------------------------------------
If Empty(cDataFim) .Or. Len(cDataFim) <> 8
	Self:SetResponse(CTB140MontaErro("VALIDATION_ERROR", ;
		"Parametro data_fim e obrigatorio no formato YYYYMMDD", ""))
	RestArea(aArea)
Return .T.
EndIf

// -------------------------------------------------------------------------
// Conversao e defaults
// -------------------------------------------------------------------------
dDataFim     := StoD(cDataFim)
// data_ini default: 1o dia do ano de data_fim (ex: 20240101)
dDataIni     := IIf(Len(cDataIni) == 8, StoD(cDataIni), StoD(Left(cDataFim, 4) + "0101"))

nMoeda       := IIf(Empty(cMoeda),      1, Val(cMoeda))
nTipoBalanc  := IIf(Empty(cTipoBalanc) .Or. Val(cTipoBalanc) == 0, 3, Val(cTipoBalanc))   // 3=Ambos
nDividePor   := IIf(Empty(cDividePor),  1, Val(cDividePor))
nConsidFil   := IIf(Empty(cConsidFil),  2, Val(cConsidFil))
lSldAntLP    := (cSldAntLP == "1")
lInclZeros   := (cVlrZerado == "1")
lImpMov      := (cImpMov != "2")   // default: retorna movimento

// cTpSald: valor real de CQ5_TPSALD (tipo de lancamento).
// No relatorio original e mv_par12 -> cSaldos -> passado para CT4BlnQry/CQ4BlnQry.
// Default "1" (lancamentos normais, conforme SX1 CTR140 par12). "CT4" e o nome da TABELA.
cTpSald := IIf(Empty(cTpLanc), "1", AllTrim(cTpLanc))
nPageSize    := IIf(nPageSize <= 0 .Or. nPageSize > 2000, 2000, nPageSize)

Do Case
	Case nDividePor == 2; nDivide := 100
	Case nDividePor == 3; nDivide := 1000
	Case nDividePor == 4; nDivide := 1000000
	Otherwise;            nDivide := 1
EndCase

// Data de corte para saldo anterior (par26/27)
// lSldAntLP=.T.: usa dDataLP_ como corte (saldo "Long Period")
// lSldAntLP=.F.: usa dDataIni - 1 (dia anterior ao inicio do periodo)
If lSldAntLP .And. Len(cDataLP) == 8
	dDataLP_ := StoD(cDataLP)
	dBefore  := dDataLP_
Else
	dBefore  := dDataIni - 1
EndIf

// Filiais
cFilialCT1 := xFilial("CT1")
cFilialCTD := xFilial("CTD")
cFilialCQ5 := xFilial("CQ5")

// Moeda formatada como 2 chars para CQ5 (1 -> '01', 2 -> '02', etc.)
cMoedaFmt  := PadL(AllTrim(Str(nMoeda)), 2, '0')

ConOut("EMPRESA: " + cValToChar(cEmpAnt))
ConOut("Filial: "  + cValToChar(cFilAnt))

// Obtem tamanhos dos campos com fallback seguro
aTamConta  := TamSX3("CT1_CONTA")
aTamItem   := TamSX3("CTD_ITEM")
aTamFilial := TamSX3("CQ5_FILIAL")
aTamVlr    := TamSX3("CT2_VALOR")
nTamConta  := IIf(Len(aTamConta)  >= 1, aTamConta[1],  20)
nTamItem   := IIf(Len(aTamItem)   >= 1, aTamItem[1],   9)
nTamFilial := IIf(Len(aTamFilial) >= 1, aTamFilial[1], 2)
nTamVlr    := IIf(Len(aTamVlr)   >= 1, aTamVlr[1],    20)
nDecVlr    := IIf(Len(aTamVlr)   >= 2, aTamVlr[2],    4)

ConOut("ZCTBR140API - TamConta=" + cValToChar(nTamConta) + " TamItem=" + cValToChar(nTamItem) + ;
       " TamFilial=" + cValToChar(nTamFilial) + " MoedaFmt=" + cMoedaFmt + ;
       " TpSald=[" + cTpSald + "]")

cContaDe  := IIf(Empty(cContaDe),  Space(nTamConta),           PadR(cContaDe,  nTamConta))
cContaAte := IIf(Empty(cContaAte), Replicate("Z", nTamConta),  PadR(cContaAte, nTamConta))
cItemDe   := IIf(Empty(cItemDe),   Space(nTamItem),            PadR(cItemDe,   nTamItem))
cItemAte  := IIf(Empty(cItemAte),  Replicate("Z", nTamItem),   PadR(cItemAte,  nTamItem))

// -------------------------------------------------------------------------
// Monta SQL
// Estrategia: INNER JOIN CT1 x CTD x CQ5 com GROUP BY + CASE WHEN.
// Uma unica passagem na CQ5 substitui as 4 subqueries correlacionadas
// anteriores, eliminando o FwRestSnd() por timeout/volume.
// O INNER JOIN em CQ5 ja garante que so retorna pares (conta,item) com
// saldo real — sem produto cartesiano e sem EXISTS separado.
// -------------------------------------------------------------------------

// Monta condicao de filial CQ5 uma unica vez (usada no JOIN)
If nConsidFil == 2
	cFilCQ5Cond := " CQ5.CQ5_FILIAL = '" + cFilialCQ5 + "' "
ElseIf !Empty(cFilialDe) .And. !Empty(cFilialAte)
	cFilCQ5Cond := " CQ5.CQ5_FILIAL BETWEEN '" + PadR(cFilialDe, nTamFilial) + "' AND '" + PadR(cFilialAte, nTamFilial) + "' "
Else
	cFilCQ5Cond := " CQ5.CQ5_FILIAL = '" + cFilialCQ5 + "' "
EndIf

cSql := " SELECT "
cSql += "   CT1.CT1_CONTA, "
cSql += "   CT1.CT1_DESC01  AS DESCCTA, "
cSql += "   CT1.CT1_NORMAL  AS NORMAL_CTA, "
cSql += "   CT1.CT1_RES     AS CTARES, "
cSql += "   CT1.CT1_CTASUP  AS CTASUP, "
cSql += "   CT1.CT1_CLASSE  AS TIPOCONTA, "
cSql += "   CTD.CTD_ITEM, "
cSql += "   CTD.CTD_DESC01  AS DESCITEM, "
cSql += "   CTD.CTD_NORMAL  AS NORMAL_ITEM, "
cSql += "   CTD.CTD_RES     AS ITEMRES, "
cSql += "   CTD.CTD_ITSUP   AS ITSUP, "
cSql += "   CTD.CTD_CLASSE  AS TIPOITEM, "

// CASE WHEN acumula os 4 saldos em uma unica passagem na CQ5
cSql += "   ISNULL(SUM(CASE WHEN CQ5.CQ5_DATA <  '" + DtoS(dDataIni) + "' THEN CQ5.CQ5_DEBITO ELSE 0 END),0) AS SALDOANTDB, "
cSql += "   ISNULL(SUM(CASE WHEN CQ5.CQ5_DATA <  '" + DtoS(dDataIni) + "' THEN CQ5.CQ5_CREDIT ELSE 0 END),0) AS SALDOANTCR, "
cSql += "   ISNULL(SUM(CASE WHEN CQ5.CQ5_DATA >= '" + DtoS(dDataIni) + "' AND CQ5.CQ5_DATA <= '" + DtoS(dDataFim) + "' THEN CQ5.CQ5_DEBITO ELSE 0 END),0) AS SALDODEB, "
cSql += "   ISNULL(SUM(CASE WHEN CQ5.CQ5_DATA >= '" + DtoS(dDataIni) + "' AND CQ5.CQ5_DATA <= '" + DtoS(dDataFim) + "' THEN CQ5.CQ5_CREDIT ELSE 0 END),0) AS SALDOCRD "

// FROM: CT1 INNER JOIN CTD INNER JOIN CQ5
// O INNER JOIN na CQ5 elimina automaticamente pares sem saldo (sem EXISTS separado)
cSql += " FROM " + RetSqlName("CT1") + " CT1 "
cSql += " INNER JOIN " + RetSqlName("CTD") + " CTD "
cSql += "   ON  CTD.CTD_FILIAL = '" + cFilialCTD + "' "
cSql += "   AND CTD.CTD_ITEM   BETWEEN '" + cItemDe + "' AND '" + cItemAte + "' "
cSql += "   AND CTD.D_E_L_E_T_ = ' ' "
cSql += " INNER JOIN " + RetSqlName("CQ5") + " CQ5 "
cSql += "   ON  CQ5.CQ5_CONTA  = CT1.CT1_CONTA "
cSql += "   AND CQ5.CQ5_ITEM   = CTD.CTD_ITEM "
cSql += "   AND CQ5.CQ5_MOEDA  = '" + cMoedaFmt + "' "
cSql += "   AND CQ5.CQ5_TPSALD = '" + cTpSald + "' "
cSql += "   AND CQ5.CQ5_DATA   <= '" + DtoS(dDataFim) + "' "
cSql += "   AND " + cFilCQ5Cond
cSql += "   AND CQ5.D_E_L_E_T_ = ' ' "

// WHERE CT1
cSql += " WHERE CT1.D_E_L_E_T_ = ' ' "
cSql += "   AND CT1.CT1_FILIAL  = '" + cFilialCT1 + "' "
cSql += "   AND CT1.CT1_CONTA   BETWEEN '" + cContaDe + "' AND '" + cContaAte + "' "
cSql += "   AND CT1.CT1_CLASSE  = '2' "   // apenas contas analiticas

// GROUP BY: todos os campos nao-agregados do SELECT
cSql += " GROUP BY CT1.CT1_CONTA, CT1.CT1_DESC01, CT1.CT1_NORMAL, CT1.CT1_RES, CT1.CT1_CTASUP, CT1.CT1_CLASSE, "
cSql += "          CTD.CTD_ITEM,  CTD.CTD_DESC01,  CTD.CTD_NORMAL,  CTD.CTD_RES,  CTD.CTD_ITSUP,  CTD.CTD_CLASSE "

// Ordena para saida coerente com o relatorio original
cSql += " ORDER BY CT1.CT1_CONTA, CTD.CTD_ITEM "

// -------------------------------------------------------------------------
// Executa query e processa registros
// -------------------------------------------------------------------------

// DEBUG: loga nomes fisicos das tabelas e SQL completo para diagnostico
ConOut("ZCTBR140API - TABLE CT1 fisico: [" + RetSqlName("CT1") + "]")
ConOut("ZCTBR140API - TABLE CTD fisico: [" + RetSqlName("CTD") + "]")
ConOut("ZCTBR140API - TABLE CQ5 fisico: [" + RetSqlName("CQ5") + "]")
ConOut("ZCTBR140API - SQL: " + cSql)

// Grava SQL em arquivo para validacao
cLogFile := "C:\Protheus\data\protheus_data_ofc\temp\ctbr140_sql.log"
cLogConteudo := "=== ZCTBR140API - " + DtoS(Date()) + " " + Time() + " ===" + CRLF
cLogConteudo += "CT1=[" + RetSqlName("CT1") + "] CTD=[" + RetSqlName("CTD") + "] CQ5=[" + RetSqlName("CQ5") + "]" + CRLF
cLogConteudo += "TpSald=[" + cTpSald + "] Moeda=[" + cMoedaFmt + "] Filial CQ5=[" + cFilialCQ5 + "]" + CRLF
cLogConteudo += CRLF + cSql + CRLF
MemoWrite(cLogFile, cLogConteudo)
ConOut("ZCTBR140API - SQL gravado em: " + cLogFile)

Begin Sequence

	// lShare=.T. (compartilhado/leitura), lReadOnly=.F.
	dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .T., .F.)
	ConOut("ZCTBR140API - alias: " + cAlias)

	ConOut("ZCTBR140API - dbUseArea OK, lendo campos...")
	// Declara tipo dos campos numericos agregados (necessario para TOPCONN)
	TCSetField(cAlias, "SALDOANTDB", "N", nTamVlr, nDecVlr)
	TCSetField(cAlias, "SALDOANTCR", "N", nTamVlr, nDecVlr)
	TCSetField(cAlias, "SALDODEB",   "N", nTamVlr, nDecVlr)
	TCSetField(cAlias, "SALDOCRD",   "N", nTamVlr, nDecVlr)

	(cAlias)->(DbGoTop())
	ConOut("ZCTBR140API - cursor Eof()=" + cValToChar((cAlias)->(Eof())) + " RecCount=" + cValToChar((cAlias)->(LastRec())))
	While !(cAlias)->(Eof())

		// Le saldos brutos da CQ5
		nSaldoAntDB := (cAlias)->SALDOANTDB
		nSaldoAntCR := (cAlias)->SALDOANTCR
		nDebito     := (cAlias)->SALDODEB
		nCredito    := (cAlias)->SALDOCRD

		// Calcula saldo anterior signed (positivo = devedor)
		nSaldoAnt  := nSaldoAntDB - nSaldoAntCR
		// Movimento do periodo: debito liquido (positivo = mais debito)
		// SALDOATU = SALDOANT + DEB - CR  (formula padrao contabil)
		nMovimento := nDebito - nCredito
		// Saldo atual acumulado (positivo = saldo devedor)
		nSaldoAtu  := nSaldoAnt + nMovimento

		// Aplica fator de divisao (par24)
		If nDivide > 1
			nSaldoAntDB := nSaldoAntDB / nDivide
			nSaldoAntCR := nSaldoAntCR / nDivide
			nSaldoAnt   := nSaldoAnt   / nDivide
			nDebito     := nDebito     / nDivide
			nCredito    := nCredito    / nDivide
			nMovimento  := nMovimento  / nDivide
			nSaldoAtu   := nSaldoAtu   / nDivide
		EndIf

		// Decide se inclui o item na resposta
		lAddItem := .T.

		// par09: exclui registros com todos os saldos zerados
		If !lInclZeros
			If Round(nSaldoAnt, 2) == 0 .And. Round(nDebito,  2) == 0 .And. ;
			   Round(nCredito,  2) == 0 .And. Round(nSaldoAtu, 2) == 0
				lAddItem := .F.
			EndIf
		EndIf

		// par07: filtra por tipo (analitico/sintetico) via CT1_CLASSE (TIPOCONTA)
		// e CTD_CLASSE (TIPOITEM). "2"=analitico "1"=sintetico
		// nTipoBalanc: 1=So analitico  2=So sintetico  3=Ambos
		If lAddItem
			If nTipoBalanc == 1 .And. AllTrim((cAlias)->TIPOITEM) != "2"
				lAddItem := .F.   // quer so analitico mas este e sintetico
			ElseIf nTipoBalanc == 2 .And. AllTrim((cAlias)->TIPOITEM) == "2"
				lAddItem := .F.   // quer so sintetico mas este e analitico
			EndIf
		EndIf

		ConOut("ZCTBR140API - item=" + AllTrim((cAlias)->CTD_ITEM) + " tipoitem=[" + AllTrim((cAlias)->TIPOITEM) + "] lAddItem=" + cValToChar(lAddItem) + " nTipoBalanc=" + cValToChar(nTipoBalanc) + " saldoAtu=" + cValToChar(nSaldoAtu))
		If lAddItem
			oLinha := JsonObject():New()
			oLinha["conta"]        := AllTrim((cAlias)->CT1_CONTA)
			oLinha["item"]         := AllTrim((cAlias)->CTD_ITEM)
			oLinha["desc_conta"]   := AllTrim((cAlias)->DESCCTA)
			oLinha["desc_item"]    := AllTrim((cAlias)->DESCITEM)
			oLinha["normal_cta"]   := AllTrim((cAlias)->NORMAL_CTA)    // "1"=D  "2"=C
			oLinha["ctares"]       := AllTrim((cAlias)->CTARES)         // codigo reduzido da conta
			oLinha["ctasup"]       := AllTrim((cAlias)->CTASUP)         // conta superior
			oLinha["tipoconta"]    := AllTrim((cAlias)->TIPOCONTA)      // classe da conta (CT1_CLASSE)
			oLinha["normal_item"]  := AllTrim((cAlias)->NORMAL_ITEM)   // "1"=D  "2"=C
			oLinha["itemres"]      := AllTrim((cAlias)->ITEMRES)        // codigo reduzido do item
			oLinha["itsup"]        := AllTrim((cAlias)->ITSUP)          // item superior
			oLinha["tipoitem"]     := AllTrim((cAlias)->TIPOITEM)       // classe do item (CTD_CLASSE)
			oLinha["saldo_ant_db"] := Round(nSaldoAntDB, 2)  // debito acumulado anterior
			oLinha["saldo_ant_cr"] := Round(nSaldoAntCR, 2)  // credito acumulado anterior
			oLinha["saldo_ant"]    := Round(nSaldoAnt,   2)  // signed: positivo=devedor
			oLinha["debito"]       := Round(nDebito,     2)  // sempre positivo
			oLinha["credito"]      := Round(nCredito,    2)  // sempre positivo
			If lImpMov
				oLinha["movimento"] := Round(nMovimento, 2)  // positivo=credito liquido
			EndIf
			oLinha["saldo_atu"]    := Round(nSaldoAtu,   2)  // signed: positivo=devedor

			aAdd(aAllLinhas, oLinha)
		EndIf

		(cAlias)->(DbSkip())
	EndDo

	(cAlias)->(DbCloseArea())

	// Paginacao sobre registros filtrados em memoria
	nTotalReg   := Len(aAllLinhas)
	nTotalPages := Max(1, Int((nTotalReg + nPageSize - 1) / nPageSize))
	nOffset     := (nPage - 1) * nPageSize

	ConOut("ZCTBR140API - aAllLinhas=" + cValToChar(nTotalReg) + " page=" + cValToChar(nPage) + " pageSize=" + cValToChar(nPageSize) + " offset=" + cValToChar(nOffset))

	nRecAtual := 0
	While nRecAtual < nPageSize .And. (nOffset + nRecAtual + 1) <= nTotalReg
		aAdd(aLinhas, aAllLinhas[nOffset + nRecAtual + 1])
		nRecAtual++
	EndDo

	ConOut("ZCTBR140API - aLinhas=" + cValToChar(Len(aLinhas)) + " totalPages=" + cValToChar(nTotalPages))

	Recover Using oError
	If Select(cAlias) > 0
		(cAlias)->(DbCloseArea())
	EndIf
	ConOut("ZCTBR140API - ERRO RECOVER: " + oError:Description)
	SetRestFail(500,"Erro ")

	Self:SetResponse( CTB140MontaErro("INTERNAL_ERROR", ;
		"Erro interno ao consultar balancete", oError:Description))
	FreeObj(oResp)
	FreeObj(oParams)
	AEval(aAllLinhas, {|o| FreeObj(o)})
	RestArea(aArea)
Return .T.
End Sequence

// Monta resposta
oParams["data_ini"]       := DtoS(dDataIni)
oParams["data_fim"]       := DtoS(dDataFim)
oParams["data_corte_ant"] := DtoS(dBefore)    // data usada para calcular saldo anterior
oParams["conta_de"]       := AllTrim(cContaDe)
oParams["conta_ate"]      := AllTrim(cContaAte)
oParams["item_de"]        := AllTrim(cItemDe)
oParams["item_ate"]       := AllTrim(cItemAte)
oParams["moeda"]          := nMoeda
oParams["moeda_fmt"]      := cMoedaFmt
oParams["tipo_balancete"] := nTipoBalanc
oParams["divide_por"]     := nDivide
oParams["filial_cq5"]     := cFilialCQ5
oParams["page"]           := nPage
oParams["pageSize"]       := nPageSize

oResp["parametros"]      := oParams
oResp["total_registros"] := nTotalReg
oResp["total_pages"]     := nTotalPages
oResp["page"]            := nPage
oResp["linhas"]          := aLinhas

Self:SetResponse(oResp:ToJson())
FreeObj(oResp)
RestArea(aArea)

Return .T.


// =============================================================================
// Static Function CTB140MontaErro
// =============================================================================
Static Function CTB140MontaErro(cCode, cMessage, cDetails)
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
