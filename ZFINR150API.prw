#Include "Protheus.ch"
#INCLUDE "restful.CH"
#Include "APWEBSRV.ch"
#Include "FWCOMMAND.CH"

/*/{Protheus.doc} ZFINR150API
API REST equivalente ao relatorio FINR150 (Posicao dos Titulos a Pagar).
Aceita os mesmos parametros do relatorio original e aplica as mesmas
regras de negocio, incluindo calculo de saldo retroativo via SaldoTit().

Endpoint: GET /rest/zfinr150api/api/v1/finr150

Campos por titulo retornado:
  filial, prefixo, numero, parcela, tipo,
  fornecedor, loja, nome_fornecedor,
  natureza, emissao, vencto, vencto_real,
  banco, situacao, valor_original,
  saldo_na_data, saldo_atual, moeda,
  numero_banco, juros, historico,
  dias_vencidos, prazo, codigo_for

@author Equipe Desenvolvimento
@since 02/04/2026
@version 1.0
/*/

wsrestful ZFINR150API description "FINR150 - Posicao dos Titulos a Pagar"

	wsdata page            as string
	wsdata pageSize        as string

	// par33 - DATA BASE (obrigatorio, YYYYMMDD)
	wsdata data_base       as string

	// par01/02 - Numero
	wsdata num_de          as string
	wsdata num_ate         as string

	// par03/04 - Prefixo
	wsdata prefixo_de      as string
	wsdata prefixo_ate     as string

	// par05/06 - Natureza
	wsdata natureza_de     as string
	wsdata natureza_ate    as string

	// par07/08 - Vencimento (YYYYMMDD)
	wsdata vencto_de       as string
	wsdata vencto_ate      as string

	// par09/10 - Banco/Portador
	wsdata banco_de        as string
	wsdata banco_ate       as string

	// par11/12 - Fornecedor
	wsdata fornecedor_de   as string
	wsdata fornecedor_ate  as string

	// par13/14 - Emissao (YYYYMMDD)
	wsdata emissao_de      as string
	wsdata emissao_ate     as string

	// par15 - Moeda
	wsdata moeda           as string

	// par16 - Provisorios (1=Incluir 2=Excluir)
	wsdata provisorios     as string

	// par17 - Reajuste pelo vencimento (1=Nao 2=Sim)
	wsdata reajuste_vencto as string

	// par18/19 - Data contabil (YYYYMMDD)
	wsdata dtcontab_de     as string
	wsdata dtcontab_ate    as string

	// par21 - Saldo retroativo (1=Sim 2=Nao)
	wsdata saldo_retroativo as string

	// par22 - Considera filiais (1=Range 2=Filial corrente)
	wsdata consid_filiais  as string

	// par23/24 - Range de filiais
	wsdata filial_de       as string
	wsdata filial_ate      as string

	// par25/26 - Loja
	wsdata loja_de         as string
	wsdata loja_ate        as string

	// par27 - Adiantamentos (1=Considera 2=Nao considera)
	wsdata adiantamentos   as string

	// par29 - Outras moedas (1=Imprime 2=Nao imprime)
	wsdata outras_moedas   as string

	// par30/31 - Tipos a incluir/excluir (separados por ";")
	wsdata tipos_incluir   as string
	wsdata tipos_excluir   as string

	// par32 - Fluxo de caixa (1=Considera 2=Nao considera)
	wsdata fluxo_caixa     as string

	// par34 - Compoe saldo por (1=DtBaixa 2=Credito 3=DtDigit)
	wsdata comp_saldo_por  as string

	// par35 - Taxa moeda (1=DtReajuste 2=TaxaContratada)
	wsdata taxa_moeda      as string

	// par36 - Titulos emissao futura (1=Sim 2=Nao)
	wsdata emissao_futura  as string

	// par38 - Considera titulos excluidos via FJU (1=Sim 2=Nao)
	wsdata titulos_excluidos as string

	// par39 - Abatimentos (1=Lista 2=Nao Lista 3=Despreza)
	wsdata abatimentos     as string

	wsmethod GET getTitulos description "Busca titulos a pagar na data base" wssyntax "/api/v1/finr150" PATH "/api/v1/finr150"

EndwsRestFul


// =============================================================================
// wsmethod GET ZFINR150API
// =============================================================================
wsmethod GET getTitulos WSRESTFUL ZFINR150API
Local aArea          := GetArea()
Local oResp          := JsonObject():New()
Local oParams        := JsonObject():New()
Local aTitulos       := {}
Local aAllTitulos    := {}
Local oItem          := Nil
Local oError         := Nil
Local cSql           := ""
Local cAlias         := GetNextAlias()
Local cAliasAbat     := GetNextAlias()
Local nSaldo         := 0
Local dDataReaj      := CtoD("")
Local nDecs          := 0
Local nTxMoedSld     := 0
Local lIsTxContr     := .F.
Local nDiasVenc      := 0
Local cPrazo         := ""
Local cCodigoFor     := ""
Local cListDesc      := ""
Local lVerCmpFil     := .F.
Local __oTBxCanc     := Nil
Local cSqlAbat       := ""
Local cMvAbatAll     := ""
Local cSqlFJU        := ""
Local cAliasFJU      := GetNextAlias()
Local cSGBD          := Upper(TCGetDB())
Local lMSSQL         := "MSSQL" $ cSGBD
Local lConSQL        := cSGBD $ "MYSQL.POSTGRES"
Local cConcatPai     := ""
Local lExistFJU      := .F.

// MV_ carregadas via SuperGetMv
Local cMvAbatim      := SuperGetMv("MV_ABATIM",  .F., "")
Local cMvFuAbt       := SuperGetMv("MV_FUABT",   .F., "")
Local cMvProvis      := SuperGetMv("MV_PROVIS",  .F., "")
Local cMvPagAnt      := SuperGetMv("MV_PAGANT",  .F., "")  // adiantamentos pagar (equiv MV_RECANT)
Local cMvCpNeg       := SuperGetMv("MV_CPNEG",   .F., "")  // creditos negativos pagar (equiv MV_CRNEG)
Local cMvBr10925    := SuperGetMv("MV_BR10925", .F., "2")

// Parametros via query string
Local cDataBase        := AllTrim(Self:data_base)
Local cNumDe           := AllTrim(Self:num_de)
Local cNumAte          := AllTrim(Self:num_ate)
Local cPrefixoDe       := AllTrim(Self:prefixo_de)
Local cPrefixoAte      := AllTrim(Self:prefixo_ate)
Local cNaturezaDe      := AllTrim(Self:natureza_de)
Local cNaturezaAte     := AllTrim(Self:natureza_ate)
Local cVenctoDe        := AllTrim(Self:vencto_de)
Local cVenctoAte       := AllTrim(Self:vencto_ate)
Local cBancoDe         := AllTrim(Self:banco_de)
Local cBancoAte        := AllTrim(Self:banco_ate)
Local cFornecedorDe    := AllTrim(Self:fornecedor_de)
Local cFornecedorAte   := AllTrim(Self:fornecedor_ate)
Local cEmissaoDe       := AllTrim(Self:emissao_de)
Local cEmissaoAte      := AllTrim(Self:emissao_ate)
Local cMoeda           := AllTrim(Self:moeda)
Local cProvisorios     := AllTrim(Self:provisorios)
Local cReajusteVencto  := AllTrim(Self:reajuste_vencto)
Local cDtContabDe      := AllTrim(Self:dtcontab_de)
Local cDtContabAte     := AllTrim(Self:dtcontab_ate)
Local cSldRetroativo   := AllTrim(Self:saldo_retroativo)
Local cConsidFiliais   := AllTrim(Self:consid_filiais)
Local cFilialDe        := AllTrim(Self:filial_de)
Local cFilialAte       := AllTrim(Self:filial_ate)
Local cLojaDe          := AllTrim(Self:loja_de)
Local cLojaAte         := AllTrim(Self:loja_ate)
Local cAdiantamentos   := AllTrim(Self:adiantamentos)
Local cOutrasMoedas    := AllTrim(Self:outras_moedas)
Local cTiposIncluir    := AllTrim(Self:tipos_incluir)
Local cTiposExcluir    := AllTrim(Self:tipos_excluir)
Local cFluxoCaixa      := AllTrim(Self:fluxo_caixa)
Local cCompSaldoPor    := AllTrim(Self:comp_saldo_por)
Local cTaxaMoeda       := AllTrim(Self:taxa_moeda)
Local cEmissaoFutura   := AllTrim(Self:emissao_futura)
Local cTitulosExcl     := AllTrim(Self:titulos_excluidos)
Local cAbatimentos     := AllTrim(Self:abatimentos)
Local nPage            := Max(1, Val(AllTrim(Self:page)))
Local nPageSize        := Val(AllTrim(Self:pageSize))

// Variaveis de conversao e defaults
Local dDataBase      := CtoD("")
Local nMoeda         := 1
Local nProvisorios   := 1
Local nReajVencto    := 1
Local nSldRetro      := 1
Local nConsidFil     := 2
Local nAdiant        := 1
Local nAbatimentos   := 1
Local nOutrasMoedas  := 1
Local nFluxoCaixa    := 2
Local nCompSaldoPor  := 1
Local nEmissaoFutura := 2
Local nTaxaMoeda     := 1
Local nPar38         := 2
Local lSldRetro      := .T.
Local cFilialSE2     := ""
Local cFilialSE5     := ""
Local dEmissaoDe     := CtoD("")
Local dEmissaoAte    := CtoD("")
Local dVenctoDe      := CtoD("")
Local dVenctoAte     := CtoD("")
Local dDtContabDe    := CtoD("")
Local dDtContabAte   := CtoD("")
Local dUltBaixa      := CtoD("")
Local cCampoVenc     := "E2_VENCREA"
Local nTotalReg      := 0
Local nTotalPages    := 1
Local nOffset        := 0
Local nRecAtual      := 0
Local lHasMore       := .F.
Local lAbriuSE2      := .F.
Local nOrdemSE2Ant   := 0
Local lAbriuSE5      := .F.
Local nOrdemSE5Ant   := 0

Self:SetContentType("application/json")

// -------------------------------------------------------------------------
// Validacao obrigatoria: data_base
// -------------------------------------------------------------------------
If Empty(cDataBase) .Or. Len(cDataBase) <> 8
	Self:nStatusCode := 422
	Self:cResponse   := FIN150MontaErro("VALIDATION_ERROR", ;
		"Parametro data_base e obrigatorio no formato YYYYMMDD", "")
	RestArea(aArea)
Return .T.
EndIf

// Inicializa cache do SaldoTit()
__oTBxCanc := FWPreparedStatement():New("")

// FN022LSTCB carrega lista de situacoes de desconto
Begin Sequence
	cListDesc := FN022LSTCB(2)
	Recover
	cListDesc := ""
End Sequence

// -------------------------------------------------------------------------
// Conversao e defaults
// -------------------------------------------------------------------------
dDataBase        := StoD(cDataBase)
nMoeda           := IIf(Empty(cMoeda),          1, Val(cMoeda))
If nMoeda == 0
	nMoeda := 1
EndIf
nProvisorios     := IIf(Empty(cProvisorios),    1, Val(cProvisorios))
nReajVencto      := IIf(Empty(cReajusteVencto), 1, Val(cReajusteVencto))
nSldRetro        := IIf(Empty(cSldRetroativo),  1, Val(cSldRetroativo))
nConsidFil       := IIf(Empty(cConsidFiliais),  2, Val(cConsidFiliais))
nAdiant          := IIf(Empty(cAdiantamentos),  1, Val(cAdiantamentos))
nOutrasMoedas    := IIf(Empty(cOutrasMoedas),   1, Val(cOutrasMoedas))
nFluxoCaixa      := IIf(Empty(cFluxoCaixa),     2, Val(cFluxoCaixa))
nCompSaldoPor    := IIf(Empty(cCompSaldoPor),   1, Val(cCompSaldoPor))
nEmissaoFutura   := IIf(Empty(cEmissaoFutura),  2, Val(cEmissaoFutura))
nTaxaMoeda       := IIf(Empty(cTaxaMoeda),      1, Val(cTaxaMoeda))
nAbatimentos     := IIf(Empty(cAbatimentos),    1, Val(cAbatimentos))
nPar38           := IIf(Empty(cTitulosExcl),    2, Val(cTitulosExcl))

lSldRetro  := (nSldRetro == 1)
nPageSize  := IIf(nPageSize <= 0 .Or. nPageSize > 2000, 2000, nPageSize)
nOffset    := (nPage - 1) * nPageSize
nDecs      := MsDecimais(nMoeda)

// Filial
If nConsidFil == 2
	cFilialSE2 := xFilial("SE2")
Else
	cFilialSE2 := ""
EndIf

// Limites padrao dos campos de filtro
cFornecedorDe  := IIf(Empty(cFornecedorDe),  Space(TamSX3("E2_FORNECE")[1]),           PadR(cFornecedorDe,  TamSX3("E2_FORNECE")[1]))
cFornecedorAte := IIf(Empty(cFornecedorAte), Replicate("Z", TamSX3("E2_FORNECE")[1]),  PadR(cFornecedorAte, TamSX3("E2_FORNECE")[1]))
cLojaDe        := IIf(Empty(cLojaDe),        Space(TamSX3("E2_LOJA")[1]),              PadR(cLojaDe,        TamSX3("E2_LOJA")[1]))
cLojaAte       := IIf(Empty(cLojaAte),       Replicate("Z", TamSX3("E2_LOJA")[1]),     PadR(cLojaAte,       TamSX3("E2_LOJA")[1]))
cPrefixoDe     := IIf(Empty(cPrefixoDe),     Space(TamSX3("E2_PREFIXO")[1]),           PadR(cPrefixoDe,     TamSX3("E2_PREFIXO")[1]))
cPrefixoAte    := IIf(Empty(cPrefixoAte),    Replicate("Z", TamSX3("E2_PREFIXO")[1]), PadR(cPrefixoAte,    TamSX3("E2_PREFIXO")[1]))
cNumDe         := IIf(Empty(cNumDe),         Space(TamSX3("E2_NUM")[1]),               PadR(cNumDe,         TamSX3("E2_NUM")[1]))
cNumAte        := IIf(Empty(cNumAte),        Replicate("Z", TamSX3("E2_NUM")[1]),      PadR(cNumAte,        TamSX3("E2_NUM")[1]))
cBancoDe       := IIf(Empty(cBancoDe),       Space(TamSX3("E2_PORTADO")[1]),           PadR(cBancoDe,       TamSX3("E2_PORTADO")[1]))
cBancoAte      := IIf(Empty(cBancoAte),      Replicate("Z", TamSX3("E2_PORTADO")[1]),  PadR(cBancoAte,      TamSX3("E2_PORTADO")[1]))
cNaturezaDe    := IIf(Empty(cNaturezaDe),    Space(TamSX3("E2_NATUREZ")[1]),           PadR(cNaturezaDe,    TamSX3("E2_NATUREZ")[1]))
cNaturezaAte   := IIf(Empty(cNaturezaAte),   Replicate("Z", TamSX3("E2_NATUREZ")[1]), PadR(cNaturezaAte,   TamSX3("E2_NATUREZ")[1]))

dEmissaoDe   := IIf(Len(cEmissaoDe)  == 8, StoD(cEmissaoDe),  CtoD(""))
dEmissaoAte  := IIf(Len(cEmissaoAte) == 8, StoD(cEmissaoAte), dDataBase)
dVenctoDe    := IIf(Len(cVenctoDe)   == 8, StoD(cVenctoDe),   CtoD(""))
dVenctoAte   := IIf(Len(cVenctoAte)  == 8, StoD(cVenctoAte),  CtoD(""))

// Data contabil: default de='' ate=dDataBase
dDtContabDe  := IIf(Len(cDtContabDe)  == 8, StoD(cDtContabDe),  CtoD(""))
dDtContabAte := IIf(Len(cDtContabAte) == 8, StoD(cDtContabAte), dDataBase)

// Verificacao de compensacao multi-filial
lVerCmpFil := !Empty(FwxFilial("SE2")) .And. !Empty(FwxFilial("SE5"))

// Campo de vencimento (par34 nao existe no FINR150 para escolha â€” usa E2_VENCREA fixo)
cCampoVenc := "E2_VENCREA"

// -------------------------------------------------------------------------
// Fase 1: SQL principal â€” titulos normais (excluindo abatimentos)
// -------------------------------------------------------------------------
cSql := " SELECT SE2.E2_FILIAL, SE2.E2_PREFIXO, SE2.E2_NUM, SE2.E2_PARCELA, "
cSql += "        SE2.E2_TIPO, SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NOMFOR, "
cSql += "        SE2.E2_EMISSAO, SE2.E2_EMIS1, SE2.E2_VENCTO, SE2.E2_VENCREA, "
cSql += "        SE2.E2_PORTADO, SE2.E2_VALOR, SE2.E2_SALDO, "
cSql += "        SE2.E2_NUMBCO, SE2.E2_JUROS, SE2.E2_HIST, SE2.E2_MOEDA, "
cSql += "        SE2.E2_NATUREZ, SE2.E2_BAIXA, SE2.E2_DECRESC, SE2.E2_ACRESC, "
cSql += "        SE2.E2_TXMOEDA, SE2.E2_FILORIG, SE2.E2_FLUXO, "
cSql += "        SE2.E2_SDACRES, SE2.E2_SDDECRE, SE2.E2_MOVIMEN, "
cSql += "        CASE WHEN EXISTS (SELECT 1 FROM " + RetSqlName("SE5") + " SE5CMP "
cSql += "             WHERE SE5CMP.D_E_L_E_T_ = ' ' "
cSql += "             AND SE5CMP.E5_FILIAL <> SE2.E2_FILIAL "
cSql += "             AND SE5CMP.E5_PREFIXO = SE2.E2_PREFIXO "
cSql += "             AND SE5CMP.E5_NUMERO = SE2.E2_NUM "
cSql += "             AND SE5CMP.E5_PARCELA = SE2.E2_PARCELA "
cSql += "             AND SE5CMP.E5_TIPO = SE2.E2_TIPO "
cSql += "             AND SE5CMP.E5_CLIFOR = SE2.E2_FORNECE "
cSql += "             AND SE5CMP.E5_LOJA = SE2.E2_LOJA "
cSql += "             AND SE5CMP.E5_MOTBX IN ('CMP','CEC')) THEN 'S' ELSE 'N' END AS E2_TEMCMP "
cSql += " FROM " + RetSqlName("SE2") + " SE2 "
cSql += " WHERE SE2.D_E_L_E_T_ = ' ' "

// Filtro de filial
If nConsidFil == 2
	cSql += "   AND SE2.E2_FILIAL = '" + cFilialSE2 + "' "
ElseIf !Empty(cFilialDe) .And. !Empty(cFilialAte)
	cSql += "   AND SE2.E2_FILORIG BETWEEN '" + PadR(cFilialDe, TamSX3("E2_FILIAL")[1]) + "' AND '" + PadR(cFilialAte, TamSX3("E2_FILIAL")[1]) + "' "
EndIf

cSql += "   AND SE2.E2_FORNECE BETWEEN '" + cFornecedorDe  + "' AND '" + cFornecedorAte  + "' "
cSql += "   AND SE2.E2_LOJA    BETWEEN '" + cLojaDe        + "' AND '" + cLojaAte        + "' "
cSql += "   AND SE2.E2_PREFIXO BETWEEN '" + cPrefixoDe     + "' AND '" + cPrefixoAte     + "' "
cSql += "   AND SE2.E2_NUM     BETWEEN '" + cNumDe         + "' AND '" + cNumAte         + "' "
cSql += "   AND SE2.E2_PORTADO BETWEEN '" + cBancoDe       + "' AND '" + cBancoAte       + "' "
cSql += "   AND SE2.E2_NATUREZ BETWEEN '" + cNaturezaDe    + "' AND '" + cNaturezaAte    + "' "

// Emissao
cSql += "   AND SE2.E2_EMISSAO BETWEEN '" + DtoS(dEmissaoDe) + "' AND '"
If nEmissaoFutura == 2 .And. dEmissaoAte >= dDataBase
	cSql += DtoS(dDataBase) + "' "
Else
	cSql += DtoS(dEmissaoAte) + "' "
EndIf

// Data contabil
cSql += "   AND SE2.E2_EMIS1 BETWEEN '" + DtoS(dDtContabDe) + "' AND '" + DtoS(dDtContabAte) + "' "

// Vencimento
If !Empty(dVenctoDe)
	cSql += "   AND SE2." + cCampoVenc + " >= '" + DtoS(dVenctoDe) + "' "
EndIf
If !Empty(dVenctoAte)
	cSql += "   AND SE2." + cCampoVenc + " <= '" + DtoS(dVenctoAte) + "' "
EndIf

// Provisorios (par16)
If nProvisorios == 2 .And. !Empty(cMvProvis)
	cSql += "   AND SE2.E2_TIPO NOT IN " + FormatIn(cMvProvis, "|") + " "
EndIf

// Adiantamentos (par27)
If nAdiant == 2 .And. !Empty(cMvPagAnt)
	cSql += "   AND SE2.E2_TIPO NOT IN " + FormatIn(cMvPagAnt + IIf(!Empty(cMvCpNeg), "|" + cMvCpNeg, ""), "|") + " "
EndIf

// Descontados (E2_SITUACA nao existe em SE2 - filtro omitido)
// If !Empty(cListDesc)
// 	cSql += "   AND SE2.E2_SITUACA NOT IN " + FormatIn(cListDesc, "|") + " "
// EndIf

// Outras moedas (par29)
If nOutrasMoedas == 2
	cSql += "   AND SE2.E2_MOEDA = " + AllTrim(Str(nMoeda)) + " "
EndIf

// Tipos incluir/excluir - par30 tem precedencia sobre par31, como no original
If !Empty(cTiposIncluir)
	cSql += "   AND SE2.E2_TIPO IN " + FormatIn(cTiposIncluir, ";") + " "
ElseIf !Empty(cTiposExcluir)
	cSql += "   AND SE2.E2_TIPO NOT IN " + FormatIn(cTiposExcluir, ";") + " "
EndIf

// Fluxo de caixa (par32)
If nFluxoCaixa == 1
	cSql += "   AND SE2.E2_FLUXO <> 'N' "
EndIf

// Saldo/Baixa â€” exatamente como original FINR150: (E2_BAIXA=' ') OR (saldo>0 OR baixa>dataBase)
cSql += "   AND ( (SE2.E2_BAIXA = ' ') OR "
If lSldRetro
	cSql += "         (SE2.E2_SALDO > 0 OR SE2.E2_BAIXA > '" + DtoS(dDataBase) + "') "
Else
	cSql += "         (SE2.E2_SALDO > 0) "
EndIf
cSql += "       ) "

// Abatimentos: excluidos da query apenas quando par39 != 1 (listar)
// Quando par39=1, sao incluidos e processados com saldo negado no loop
If nAbatimentos != 1
	If !Empty(cMvAbatim)
		cSql += "   AND SE2.E2_TIPO NOT IN " + FormatIn(cMvAbatim, "|") + " "
	EndIf
EndIf

If nCompSaldoPor == 2 .And. !Empty(dDataBase)
	cSql += "   AND SE2.E2_EMIS1 <= '" + DtoS(dDataBase) + "' "
EndIf

// Excluir titulos que sao "pai" no FJU quando par38=1 (serao incluidos na Fase FJU)
lExistFJU := FJU->(ColumnPos("FJU_RECPAI")) > 0
If lExistFJU .And. nPar38 == 1
	cSql += "   AND SE2.R_E_C_N_O_ NOT IN ( "
	cSql += "       SELECT PAI.FJU_RECPAI FROM " + RetSqlName("FJU") + " PAI "
	cSql += "       WHERE PAI.D_E_L_E_T_ = ' ' "
	cSql += "         AND PAI.FJU_CART = 'P' "
	cSql += "         AND PAI.FJU_DTEXCL >= '" + DtoS(dDataBase) + "' "
	cSql += "         AND PAI.FJU_EMIS1 <= '" + DtoS(dDataBase) + "') "
EndIf

cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA, SE2.E2_TIPO "

ConOut("[FINR150API] SQL PRINCIPAL: " + cSql)

// -------------------------------------------------------------------------
// Executa query e processa registros
// -------------------------------------------------------------------------
Begin Sequence

	Begin Sequence
		__oTBxCanc := FWPreparedStatement():New()
	Recover
		__oTBxCanc := Nil
	End Sequence

	dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .F., .T.)
	ConOut("[FINR150API] SQL executado - LastRec=" + Str((cAlias)->(LastRec()), 6))
	TCSetField(cAlias, "E2_EMISSAO", "D", 8, 0)
	TCSetField(cAlias, "E2_EMIS1",   "D", 8, 0)
	TCSetField(cAlias, "E2_VENCTO",  "D", 8, 0)
	TCSetField(cAlias, "E2_VENCREA", "D", 8, 0)
	TCSetField(cAlias, "E2_BAIXA",   "D", 8, 0)
	TCSetField(cAlias, "E2_MOVIMEN", "D", 8, 0)
	TCSetField(cAlias, "E2_VALOR",   "N", 16, 2)
	TCSetField(cAlias, "E2_SALDO",   "N", 16, 2)
	TCSetField(cAlias, "E2_JUROS",   "N", 16, 2)
	TCSetField(cAlias, "E2_DECRESC", "N", 16, 2)
	TCSetField(cAlias, "E2_ACRESC",  "N", 16, 2)
	TCSetField(cAlias, "E2_TXMOEDA", "N", 15, 4)
	TCSetField(cAlias, "E2_MOEDA",   "N", 2, 0)
	TCSetField(cAlias, "E2_SDACRES", "N", 16, 2)
	TCSetField(cAlias, "E2_SDDECRE", "N", 16, 2)

	// Abre SE2 e SE5 para SaldoTit() quando saldo retroativo
	ConOut("[FINR150API] lSldRetro=" + IIf(lSldRetro, "T", "F") + " Select(SE5)=" + Str(Select("SE5"), 3))
	If lSldRetro .And. Select("SE2") == 0
		ChkFile("SE2", .F., "SE2")
		lAbriuSE2 := .T.
	ElseIf lSldRetro
		nOrdemSE2Ant := SE2->(IndexOrd())
	EndIf
	If lSldRetro .And. Select("SE5") == 0
		ChkFile("SE5", .F., "SE5")
		lAbriuSE5 := .T.
		If Empty(SE5->(IndexKey(7)))
			Break
		EndIf
		SE5->(DbSetorder(7))
	ElseIf lSldRetro
		nOrdemSE5Ant := SE5->(IndexOrd())
		If Empty(SE5->(IndexKey(7)))
			Break
		EndIf
		SE5->(DbSetorder(7))
	EndIf

	(cAlias)->(DbGoTop())

	While !(cAlias)->(Eof())

		// Ignora PIS/COF/CSL ja emitidos (equivalente ao FINR130)
		If lSldRetro .And. cMvBr10925 == "1" .And. (cAlias)->E2_EMISSAO <= dDataBase .And. ;
				AllTrim((cAlias)->E2_TIPO) $ "PIS/COF/CSL"
			(cAlias)->(DbSkip())
			Loop
		EndIf

		dDataReaj := dDataBase
		If (cAlias)->E2_VENCREA < dDataBase .And. nReajVencto == 2 .And. ;
				RecMoeda((cAlias)->E2_VENCREA, nMoeda) > 0
			dDataReaj := (cAlias)->E2_VENCREA
		EndIf

		nTxMoedSld := IIf(nTaxaMoeda == 2, ;
			IIf(!Empty((cAlias)->E2_TXMOEDA), (cAlias)->E2_TXMOEDA, RecMoeda((cAlias)->E2_EMISSAO, (cAlias)->E2_MOEDA)), ;
			0)
		lIsTxContr := (nTaxaMoeda == 2 .And. !Empty((cAlias)->E2_TXMOEDA))

		If lSldRetro
			// Usa E2_FILIAL do titulo para garantir match com E5_FILIAL
			cFilialSE5 := (cAlias)->E2_FILIAL

			If !FIN150PosSE2((cAlias)->E2_FILIAL, (cAlias)->E2_PREFIXO, (cAlias)->E2_NUM, ;
					(cAlias)->E2_PARCELA, (cAlias)->E2_TIPO, (cAlias)->E2_FORNECE, (cAlias)->E2_LOJA)
				ConOut("[FINR150API] SE2 nao posicionada para SaldoTit - titulo descartado")
				(cAlias)->(DbSkip())
				Loop
			EndIf

			// SaldoTit() â€” parametro carteira = "P" (pagar)
			nSaldo := SaldoTit( ;
				(cAlias)->E2_PREFIXO, ;
				(cAlias)->E2_NUM,     ;
				(cAlias)->E2_PARCELA, ;
				(cAlias)->E2_TIPO,    ;
				(cAlias)->E2_NATUREZ, ;
				"P",                  ;
				(cAlias)->E2_FORNECE, ;
				nMoeda,               ;
				dDataReaj,            ;
				dDataBase,            ;
				(cAlias)->E2_LOJA,    ;
				cFilialSE5,           ;
				nTxMoedSld,           ;
				nCompSaldoPor,        ;
				.F.,                  ;
				__oTBxCanc,           ;
				lIsTxContr            ;
				)

			// Compensacoes multi-filial
			If lVerCmpFil .And. AllTrim((cAlias)->E2_TEMCMP) == "S"
				nSaldo -= Round(NoRound(xMoeda( ;
					FRVlCompFil("P", (cAlias)->E2_PREFIXO, (cAlias)->E2_NUM, ;
						(cAlias)->E2_PARCELA, (cAlias)->E2_TIPO, ;
						(cAlias)->E2_FORNECE, (cAlias)->E2_LOJA, ;
						nCompSaldoPor, {}, , .F., ;
						nMoeda, (cAlias)->E2_MOEDA, nTxMoedSld, dDataReaj, .T.), ;
					(cAlias)->E2_MOEDA, nMoeda, dDataReaj, nDecs + 1, nTxMoedSld), ;
					nDecs + 1), nDecs)
			EndIf

		Else
			// Saldo nao-retroativo
			nSaldo := xMoeda( ;
				(cAlias)->E2_SALDO + (cAlias)->E2_SDACRES - (cAlias)->E2_SDDECRE, ;
				(cAlias)->E2_MOEDA, nMoeda, dDataReaj, nDecs + 1, ;
				IIf(nTaxaMoeda==2, ;
					IIf(!Empty((cAlias)->E2_TXMOEDA), (cAlias)->E2_TXMOEDA, RecMoeda((cAlias)->E2_EMISSAO, (cAlias)->E2_MOEDA)), ;
					0))
		EndIf

		// Skip quando saldo=0 e tem movimentacao (original: nSaldo==0 AND !EMPTY(E2_MOVIMEN))
		If nSaldo == 0 .And. !Empty((cAlias)->E2_MOVIMEN)
			(cAlias)->(DbSkip())
			Loop
		EndIf

		// Desconta abatimentos dos titulos normais (original: SomaAbat quando nao eh abatimento e par39!=1)
		If !( AllTrim((cAlias)->E2_TIPO) $ cMvAbatim ) .And. ;
			!( AllTrim((cAlias)->E2_TIPO) $ ( AllTrim(cMvPagAnt) + '/' + AllTrim(cMvCpNeg) ) ) .And. ;
			!( AllTrim((cAlias)->E2_TIPO) $ ( AllTrim(cMvPagAnt) + '/' + AllTrim(cMvProvis) + '/' + AllTrim(cMvCpNeg) ) ) .And. ;
			nAbatimentos != 1 .And. ;
			!(nSldRetro == 2 .And. nSaldo == 0)
			Begin Sequence
				nSaldo -= SomaAbat((cAlias)->E2_PREFIXO, (cAlias)->E2_NUM, (cAlias)->E2_PARCELA, ;
					"P", nMoeda, dDataReaj, (cAlias)->E2_FORNECE, (cAlias)->E2_LOJA)
			Recover
			End Sequence
		EndIf

		nSaldo := Round(NoRound(nSaldo, 3), 2)

		// Abatimentos tem saldo negado (original: SE2->E2_TIPO $ MVABATIM, nSaldo *= -1)
		If AllTrim((cAlias)->E2_TIPO) $ cMvAbatim .And. nSaldo > 0
			nSaldo := nSaldo * -1
		EndIf

		If nSaldo > 0
			nDiasVenc  := dDataBase - (cAlias)->E2_VENCREA
			cPrazo     := IIf(nDiasVenc > 365, "LONGO PRAZO", "CURTO PRAZO")
			cCodigoFor := "F" + AllTrim((cAlias)->E2_FORNECE) + AllTrim((cAlias)->E2_LOJA)

			oItem := JsonObject():New()
			oItem["filial"]           := AllTrim((cAlias)->E2_FILIAL)
			oItem["prefixo"]          := AllTrim((cAlias)->E2_PREFIXO)
			oItem["numero"]           := AllTrim((cAlias)->E2_NUM)
			oItem["parcela"]          := AllTrim((cAlias)->E2_PARCELA)
			oItem["tipo"]             := AllTrim((cAlias)->E2_TIPO)
			oItem["fornecedor"]       := AllTrim((cAlias)->E2_FORNECE)
			oItem["loja"]             := AllTrim((cAlias)->E2_LOJA)
			oItem["nome_fornecedor"]  := AllTrim((cAlias)->E2_NOMFOR)
			oItem["natureza"]         := AllTrim((cAlias)->E2_NATUREZ)
			oItem["emissao"]          := DToS((cAlias)->E2_EMISSAO)
			oItem["vencto"]           := DToS((cAlias)->E2_VENCTO)
			oItem["vencto_real"]      := DToS((cAlias)->E2_VENCREA)
			oItem["banco"]            := AllTrim((cAlias)->E2_PORTADO)
			oItem["valor_original"]   := (cAlias)->E2_VALOR
			oItem["saldo_na_data"]    := nSaldo
			oItem["saldo_atual"]      := (cAlias)->E2_SALDO
			oItem["moeda"]            := (cAlias)->E2_MOEDA
			oItem["numero_banco"]     := AllTrim((cAlias)->E2_NUMBCO)
			oItem["juros"]            := (cAlias)->E2_JUROS
			oItem["historico"]        := AllTrim((cAlias)->E2_HIST)
			oItem["dias_vencidos"]    := nDiasVenc
			oItem["prazo"]            := cPrazo
			oItem["codigo_for"]       := cCodigoFor

			nTotalReg++
			If nTotalReg > (nOffset + nPageSize)
				lHasMore := .T.
				FreeObj(oItem)
			ElseIf nTotalReg > nOffset
				aAdd(aTitulos, oItem)
			Else
				FreeObj(oItem)
			EndIf
		EndIf

		If lHasMore
			Exit
		EndIf

		(cAlias)->(DbSkip())
	EndDO

	(cAlias)->(DbCloseArea())
	ConOut("[FINR150API] Fase principal concluida - titulosPagina=" + Str(Len(aTitulos), 6) + ;
		" totalProcessado=" + Str(nTotalReg, 6) + " hasMore=" + IIf(lHasMore, "S", "N"))

	// -------------------------------------------------------------------------
	// Fase 2: Titulos excluidos via FJU (par38 == 1)
	// -------------------------------------------------------------------------
	If !lHasMore .And. lExistFJU .And. nPar38 == 1
		cSqlFJU   := ""
		cAliasFJU := GetNextAlias()

		cSqlFJU := " SELECT SE2.E2_FILIAL, SE2.E2_PREFIXO, SE2.E2_NUM, SE2.E2_PARCELA, "
		cSqlFJU += "        SE2.E2_TIPO, SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NOMFOR, "
		cSqlFJU += "        SE2.E2_EMISSAO, SE2.E2_EMIS1, SE2.E2_VENCTO, SE2.E2_VENCREA, "
		cSqlFJU += "        SE2.E2_PORTADO, SE2.E2_VALOR, SE2.E2_SALDO, "
		cSqlFJU += "        SE2.E2_NUMBCO, SE2.E2_JUROS, SE2.E2_HIST, SE2.E2_MOEDA, "
		cSqlFJU += "        SE2.E2_NATUREZ, SE2.E2_BAIXA, SE2.E2_DECRESC, SE2.E2_ACRESC, "
		cSqlFJU += "        SE2.E2_TXMOEDA, SE2.E2_FILORIG, SE2.E2_FLUXO, "
		cSqlFJU += "        SE2.E2_SDACRES, SE2.E2_SDDECRE, SE2.E2_MOVIMEN, "
		cSqlFJU += "        CASE WHEN EXISTS (SELECT 1 FROM " + RetSqlName("SE5") + " SE5CMP "
		cSqlFJU += "             WHERE SE5CMP.D_E_L_E_T_ = ' ' "
		cSqlFJU += "             AND SE5CMP.E5_FILIAL <> SE2.E2_FILIAL "
		cSqlFJU += "             AND SE5CMP.E5_PREFIXO = SE2.E2_PREFIXO "
		cSqlFJU += "             AND SE5CMP.E5_NUMERO = SE2.E2_NUM "
		cSqlFJU += "             AND SE5CMP.E5_PARCELA = SE2.E2_PARCELA "
		cSqlFJU += "             AND SE5CMP.E5_TIPO = SE2.E2_TIPO "
		cSqlFJU += "             AND SE5CMP.E5_CLIFOR = SE2.E2_FORNECE "
		cSqlFJU += "             AND SE5CMP.E5_LOJA = SE2.E2_LOJA "
		cSqlFJU += "             AND SE5CMP.E5_MOTBX IN ('CMP','CEC')) THEN 'S' ELSE 'N' END AS E2_TEMCMP "
		cSqlFJU += " FROM " + RetSqlName("SE2") + " SE2 "
		cSqlFJU += " INNER JOIN " + RetSqlName("FJU") + " FJU "
		cSqlFJU += "   ON SE2.E2_FILIAL  = FJU.FJU_FILIAL "
		cSqlFJU += "  AND SE2.E2_PREFIXO = FJU.FJU_PREFIX "
		cSqlFJU += "  AND SE2.E2_NUM     = FJU.FJU_NUM "
		cSqlFJU += "  AND SE2.E2_PARCELA = FJU.FJU_PARCEL "
		cSqlFJU += "  AND SE2.E2_TIPO    = FJU.FJU_TIPO "
		cSqlFJU += "  AND SE2.E2_FORNECE = FJU.FJU_CLIFOR "
		cSqlFJU += "  AND SE2.E2_LOJA    = FJU.FJU_LOJA "
		cSqlFJU += " WHERE SE2.D_E_L_E_T_ = '*' "
		cSqlFJU += "   AND FJU.D_E_L_E_T_ = ' ' "
		cSqlFJU += "   AND FJU.FJU_CART   = 'P' "
		cSqlFJU += "   AND FJU.FJU_EMIS   <= '" + DtoS(dDataBase) + "' "
		cSqlFJU += "   AND FJU.FJU_DTEXCL >= '" + DtoS(dDataBase) + "' "
		cSqlFJU += "   AND SE2.R_E_C_N_O_ = FJU.FJU_RECORI "
		cSqlFJU += "   AND FJU.FJU_RECORI IN ( SELECT MAX(LASTFJU.FJU_RECORI) FROM " + RetSqlName("FJU") + " LASTFJU "
		cSqlFJU += "                          WHERE LASTFJU.FJU_FILIAL = FJU.FJU_FILIAL "
		cSqlFJU += "                            AND LASTFJU.FJU_PREFIX = FJU.FJU_PREFIX "
		cSqlFJU += "                            AND LASTFJU.FJU_NUM    = FJU.FJU_NUM "
		cSqlFJU += "                            AND LASTFJU.FJU_PARCEL = FJU.FJU_PARCEL "
		cSqlFJU += "                            AND LASTFJU.FJU_TIPO   = FJU.FJU_TIPO "
		cSqlFJU += "                            AND LASTFJU.FJU_CLIFOR = FJU.FJU_CLIFOR "
		cSqlFJU += "                            AND LASTFJU.FJU_LOJA   = FJU.FJU_LOJA "
		cSqlFJU += "                            AND LASTFJU.FJU_DTEXCL = FJU.FJU_DTEXCL ) "
		cSqlFJU += "   AND (SELECT COUNT(*) FROM " + RetSqlName("SE2") + " NOTDEL "
		cSqlFJU += "         WHERE NOTDEL.E2_FILIAL  = FJU.FJU_FILIAL "
		cSqlFJU += "           AND NOTDEL.E2_PREFIXO = FJU.FJU_PREFIX "
		cSqlFJU += "           AND NOTDEL.E2_NUM     = FJU.FJU_NUM "
		cSqlFJU += "           AND NOTDEL.E2_PARCELA = FJU.FJU_PARCEL "
		cSqlFJU += "           AND NOTDEL.E2_TIPO    = FJU.FJU_TIPO "
		cSqlFJU += "           AND NOTDEL.E2_FORNECE = FJU.FJU_CLIFOR "
		cSqlFJU += "           AND NOTDEL.E2_LOJA    = FJU.FJU_LOJA "
		cSqlFJU += "           AND FJU.FJU_RECPAI    = 0 "
		cSqlFJU += "           AND NOTDEL.E2_EMIS1   <= '" + DtoS(dDataBase) + "' "
		cSqlFJU += "           AND NOTDEL.D_E_L_E_T_ = ' ') = 0 "
		cSqlFJU += "   AND FJU.FJU_RECORI NOT IN (SELECT PAI.FJU_RECPAI FROM " + RetSqlName("FJU") + " PAI "
		cSqlFJU += "                                WHERE PAI.D_E_L_E_T_ = ' ' "
		cSqlFJU += "                                  AND PAI.FJU_CART = 'P' "
		cSqlFJU += "                                  AND PAI.FJU_DTEXCL >= '" + DtoS(dDataBase) + "' "
		cSqlFJU += "                                  AND PAI.FJU_EMIS1 <= '" + DtoS(dDataBase) + "') "
		cSqlFJU += "   AND SE2.E2_FORNECE BETWEEN '" + cFornecedorDe + "' AND '" + cFornecedorAte + "' "
		cSqlFJU += "   AND SE2.E2_LOJA    BETWEEN '" + cLojaDe + "' AND '" + cLojaAte + "' "
		cSqlFJU += "   AND SE2.E2_PREFIXO BETWEEN '" + cPrefixoDe + "' AND '" + cPrefixoAte + "' "
		cSqlFJU += "   AND SE2.E2_NUM     BETWEEN '" + cNumDe + "' AND '" + cNumAte + "' "
		cSqlFJU += "   AND SE2.E2_PORTADO BETWEEN '" + cBancoDe + "' AND '" + cBancoAte + "' "
		cSqlFJU += "   AND SE2.E2_NATUREZ BETWEEN '" + cNaturezaDe + "' AND '" + cNaturezaAte + "' "
		cSqlFJU += "   AND SE2.E2_EMIS1 BETWEEN '" + DtoS(dDtContabDe) + "' AND '" + DtoS(dDtContabAte) + "' "
		If nConsidFil == 2
			cSqlFJU += "   AND SE2.E2_FILIAL = '" + cFilialSE2 + "' "
		ElseIf !Empty(cFilialDe) .And. !Empty(cFilialAte)
			cSqlFJU += "   AND SE2.E2_FILORIG BETWEEN '" + PadR(cFilialDe, TamSX3("E2_FILIAL")[1]) + "' AND '" + PadR(cFilialAte, TamSX3("E2_FILIAL")[1]) + "' "
		EndIf
		If !Empty(cTiposIncluir)
			cSqlFJU += "   AND SE2.E2_TIPO IN " + FormatIn(cTiposIncluir, ";") + " "
		ElseIf !Empty(cTiposExcluir)
			cSqlFJU += "   AND SE2.E2_TIPO NOT IN " + FormatIn(cTiposExcluir, ";") + " "
		EndIf
		If nFluxoCaixa == 1
			cSqlFJU += "   AND SE2.E2_FLUXO <> 'N' "
		EndIf
		If nProvisorios == 2 .And. !Empty(cMvProvis)
			cSqlFJU += "   AND SE2.E2_TIPO NOT IN " + FormatIn(cMvProvis, "|") + " "
		EndIf
		If nAdiant == 2 .And. !Empty(cMvPagAnt)
			cSqlFJU += "   AND SE2.E2_TIPO NOT IN " + FormatIn(cMvPagAnt + IIf(!Empty(cMvCpNeg), "|" + cMvCpNeg, ""), "|") + " "
		EndIf
		If nCompSaldoPor == 2
			cSqlFJU += "   AND SE2.E2_EMIS1 <= '" + DtoS(dDataBase) + "' "
		EndIf
		cSqlFJU += "   AND ( (SE2.E2_BAIXA = ' ') OR "
		If lSldRetro
			cSqlFJU += "         (SE2.E2_SALDO > 0 OR SE2.E2_BAIXA > '" + DtoS(dDataBase) + "') "
		Else
			cSqlFJU += "         (SE2.E2_SALDO > 0) "
		EndIf
		cSqlFJU += "       ) "
		If nOutrasMoedas == 2
			cSqlFJU += "   AND SE2.E2_MOEDA = " + AllTrim(Str(nMoeda)) + " "
		EndIf
		If nAbatimentos != 1 .And. !Empty(cMvAbatim)
			cSqlFJU += "   AND SE2.E2_TIPO NOT IN " + FormatIn(cMvAbatim, "|") + " "
		EndIf

		dbUseArea(.T., "TOPCONN", TCGenQry(,, cSqlFJU), cAliasFJU, .F., .T.)
		TCSetField(cAliasFJU, "E2_EMISSAO", "D", 8, 0)
		TCSetField(cAliasFJU, "E2_EMIS1",   "D", 8, 0)
		TCSetField(cAliasFJU, "E2_VENCTO",  "D", 8, 0)
		TCSetField(cAliasFJU, "E2_VENCREA", "D", 8, 0)
		TCSetField(cAliasFJU, "E2_BAIXA",   "D", 8, 0)
		TCSetField(cAliasFJU, "E2_MOVIMEN", "D", 8, 0)
		TCSetField(cAliasFJU, "E2_VALOR",   "N", 16, 2)
		TCSetField(cAliasFJU, "E2_SALDO",   "N", 16, 2)
		TCSetField(cAliasFJU, "E2_JUROS",   "N", 16, 2)
		TCSetField(cAliasFJU, "E2_DECRESC", "N", 16, 2)
		TCSetField(cAliasFJU, "E2_ACRESC",  "N", 16, 2)
		TCSetField(cAliasFJU, "E2_TXMOEDA", "N", 15, 4)
		TCSetField(cAliasFJU, "E2_MOEDA",   "N", 2, 0)
		TCSetField(cAliasFJU, "E2_SDACRES", "N", 16, 2)
		TCSetField(cAliasFJU, "E2_SDDECRE", "N", 16, 2)
		(cAliasFJU)->(DbGoTop())
		While !(cAliasFJU)->(Eof())
			If lSldRetro .And. cMvBr10925 == "1" .And. (cAliasFJU)->E2_EMISSAO <= dDataBase .And. ;
					AllTrim((cAliasFJU)->E2_TIPO) $ "PIS/COF/CSL"
				(cAliasFJU)->(DbSkip())
				Loop
			EndIf
			dDataReaj := dDataBase
			If (cAliasFJU)->E2_VENCREA < dDataBase .And. nReajVencto == 2 .And. ;
					RecMoeda((cAliasFJU)->E2_VENCREA, nMoeda) > 0
				dDataReaj := (cAliasFJU)->E2_VENCREA
			EndIf
			nTxMoedSld := IIf(nTaxaMoeda == 2, IIf(!Empty((cAliasFJU)->E2_TXMOEDA), (cAliasFJU)->E2_TXMOEDA, RecMoeda((cAliasFJU)->E2_EMISSAO, (cAliasFJU)->E2_MOEDA)), 0)
			lIsTxContr := (nTaxaMoeda == 2 .And. !Empty((cAliasFJU)->E2_TXMOEDA))
			If lSldRetro
				cFilialSE5 := (cAliasFJU)->E2_FILIAL
				If !FIN150PosSE2((cAliasFJU)->E2_FILIAL, (cAliasFJU)->E2_PREFIXO, (cAliasFJU)->E2_NUM, ;
						(cAliasFJU)->E2_PARCELA, (cAliasFJU)->E2_TIPO, (cAliasFJU)->E2_FORNECE, (cAliasFJU)->E2_LOJA)
					(cAliasFJU)->(DbSkip())
					Loop
				EndIf
				nSaldo := SaldoTit((cAliasFJU)->E2_PREFIXO, (cAliasFJU)->E2_NUM, (cAliasFJU)->E2_PARCELA, (cAliasFJU)->E2_TIPO, ;
					(cAliasFJU)->E2_NATUREZ, "P", (cAliasFJU)->E2_FORNECE, nMoeda, dDataReaj, dDataBase, ;
					(cAliasFJU)->E2_LOJA, cFilialSE5, nTxMoedSld, nCompSaldoPor, .F., __oTBxCanc, lIsTxContr)
			Else
				nSaldo := xMoeda((cAliasFJU)->E2_SALDO + (cAliasFJU)->E2_SDACRES - (cAliasFJU)->E2_SDDECRE, ;
					(cAliasFJU)->E2_MOEDA, nMoeda, dDataReaj, nDecs + 1, IIf(nTaxaMoeda==2, ;
					IIf(!Empty((cAliasFJU)->E2_TXMOEDA), (cAliasFJU)->E2_TXMOEDA, RecMoeda((cAliasFJU)->E2_EMISSAO, (cAliasFJU)->E2_MOEDA)), 0))
			EndIf
			nSaldo := Round(NoRound(nSaldo, 3), 2)
			If nSaldo > 0
				nDiasVenc  := dDataBase - (cAliasFJU)->E2_VENCREA
				cPrazo     := IIf(nDiasVenc > 365, "LONGO PRAZO", "CURTO PRAZO")
				cCodigoFor := "F" + AllTrim((cAliasFJU)->E2_FORNECE) + AllTrim((cAliasFJU)->E2_LOJA)
				oItem := JsonObject():New()
				oItem["filial"]           := AllTrim((cAliasFJU)->E2_FILIAL)
				oItem["prefixo"]          := AllTrim((cAliasFJU)->E2_PREFIXO)
				oItem["numero"]           := AllTrim((cAliasFJU)->E2_NUM)
				oItem["parcela"]          := AllTrim((cAliasFJU)->E2_PARCELA)
				oItem["tipo"]             := AllTrim((cAliasFJU)->E2_TIPO)
				oItem["fornecedor"]       := AllTrim((cAliasFJU)->E2_FORNECE)
				oItem["loja"]             := AllTrim((cAliasFJU)->E2_LOJA)
				oItem["nome_fornecedor"]  := AllTrim((cAliasFJU)->E2_NOMFOR)
				oItem["natureza"]         := AllTrim((cAliasFJU)->E2_NATUREZ)
				oItem["emissao"]          := DToS((cAliasFJU)->E2_EMISSAO)
				oItem["vencto"]           := DToS((cAliasFJU)->E2_VENCTO)
				oItem["vencto_real"]      := DToS((cAliasFJU)->E2_VENCREA)
				oItem["banco"]            := AllTrim((cAliasFJU)->E2_PORTADO)
				oItem["situacao"]         := ""
				oItem["valor_original"]   := (cAliasFJU)->E2_VALOR
				oItem["saldo_na_data"]    := nSaldo
				oItem["saldo_atual"]      := (cAliasFJU)->E2_SALDO
				oItem["moeda"]            := (cAliasFJU)->E2_MOEDA
				oItem["numero_banco"]     := AllTrim((cAliasFJU)->E2_NUMBCO)
				oItem["juros"]            := (cAliasFJU)->E2_JUROS
				oItem["historico"]        := AllTrim((cAliasFJU)->E2_HIST)
				oItem["dias_vencidos"]    := nDiasVenc
				oItem["prazo"]            := cPrazo
				oItem["codigo_for"]       := cCodigoFor
				nTotalReg++
				If nTotalReg > (nOffset + nPageSize)
					lHasMore := .T.
					FreeObj(oItem)
				ElseIf nTotalReg > nOffset
					aAdd(aTitulos, oItem)
				Else
					FreeObj(oItem)
				EndIf
			EndIf
			If lHasMore
				Exit
			EndIf
			(cAliasFJU)->(DbSkip())
		EndDo
		(cAliasFJU)->(DbCloseArea())
	EndIf

	// Fecha SE2 aberta para SaldoTit()
	If lSldRetro .And. Select("SE2") > 0 .And. lAbriuSE2
		SE2->(DbCloseArea())
	ElseIf lSldRetro .And. Select("SE2") > 0 .And. nOrdemSE2Ant > 0
		SE2->(DbSetOrder(nOrdemSE2Ant))
	EndIf

	// Fecha SE5 aberta para SaldoTit()
	If lSldRetro .And. Select("SE5") > 0 .And. lAbriuSE5
		SE5->(DbCloseArea())
	ElseIf lSldRetro .And. Select("SE5") > 0 .And. nOrdemSE5Ant > 0
		SE5->(DbSetOrder(nOrdemSE5Ant))
	EndIf

	If !Empty(__oTBxCanc)
		FreeObj(__oTBxCanc)
		__oTBxCanc := Nil
	EndIf

	// Paginacao real: nTotalReg representa os registros validos processados
	// ate preencher a pagina solicitada e detectar se existe proxima pagina.
	nTotalPages := IIf(lHasMore, nPage + 1, Max(1, nPage))

Recover Using oError
	If Select(cAlias) > 0
		(cAlias)->(DbCloseArea())
	EndIf
	If Select(cAliasAbat) > 0
		(cAliasAbat)->(DbCloseArea())
	EndIf
	If Select(cAliasFJU) > 0
		(cAliasFJU)->(DbCloseArea())
	EndIf
	If Select("SE2") > 0 .And. lAbriuSE2
		SE2->(DbCloseArea())
	ElseIf Select("SE2") > 0 .And. nOrdemSE2Ant > 0
		SE2->(DbSetOrder(nOrdemSE2Ant))
	EndIf
	If Select("SE5") > 0 .And. lAbriuSE5
		SE5->(DbCloseArea())
	ElseIf Select("SE5") > 0 .And. nOrdemSE5Ant > 0
		SE5->(DbSetOrder(nOrdemSE5Ant))
	EndIf
	If !Empty(__oTBxCanc)
		__oTBxCanc:Destroy()
		__oTBxCanc := Nil
	EndIf
	Self:nStatusCode := 500
	Self:cResponse   := FIN150MontaErro("INTERNAL_ERROR", ;
		"Erro interno ao consultar titulos a pagar", oError:Description)
	FreeObj(oResp)
	FreeObj(oParams)
	AEval(aAllTitulos, {|o| FreeObj(o)})
	RestArea(aArea)
Return .T.
End Sequence

// Monta resposta
oParams["data_base"]        := cDataBase
oParams["filial"]           := cFilialSE2
oParams["moeda"]            := nMoeda
oParams["saldo_retroativo"] := nSldRetro
oParams["comp_saldo_por"]   := nCompSaldoPor
oParams["provisorios"]      := nProvisorios
oParams["adiantamentos"]    := nAdiant
oParams["abatimentos"]      := nAbatimentos
oParams["page"]             := nPage
oParams["pageSize"]         := nPageSize

oResp["parametros"]      := oParams
oResp["total_registros"] := nTotalReg
oResp["totalPages"]      := nTotalPages
oResp["page"]            := nPage
oResp["hasMore"]         := lHasMore
oResp["titulos"]         := aTitulos

Self:SetResponse(oResp:ToJson())
FreeObj(oResp)

If Select("SE2") > 0 .And. lAbriuSE2
	SE2->(DbCloseArea())
ElseIf Select("SE2") > 0 .And. nOrdemSE2Ant > 0
	SE2->(DbSetOrder(nOrdemSE2Ant))
EndIf
If !Empty(__oTBxCanc)
	__oTBxCanc:Destroy()
	__oTBxCanc := Nil
EndIf

RestArea(aArea)

Return .T.


// =============================================================================
// =============================================================================
// Static Function FIN150DBX
// Busca ultima baixa efetiva ate dDataBase para o titulo SE2 informado.
// Equivalente ao FR150DBx do original, consultando SE5.
// =============================================================================
Static Function FIN150DBX(cPrefixo, cNumero, cParcela, cTipo, cFornece, cLoja, cFilSE5, dDataBase, nCompSaldo)
	Local cAliasDBX := GetNextAlias()
	Local cSqlDBX   := ""
	Local dRet      := CtoD("")

	Default nCompSaldo := 1

	cSqlDBX := " SELECT MAX(SE5.E5_DATA) AS ULTBAIXA "
	cSqlDBX += " FROM " + RetSqlName("SE5") + " SE5 "
	cSqlDBX += " WHERE SE5.E5_FILIAL = '" + cFilSE5 + "' "
	cSqlDBX += "   AND SE5.E5_PREFIXO = '" + cPrefixo + "' "
	cSqlDBX += "   AND SE5.E5_NUMERO  = '" + cNumero  + "' "
	cSqlDBX += "   AND SE5.E5_PARCELA = '" + cParcela + "' "
	cSqlDBX += "   AND SE5.E5_TIPO    = '" + cTipo    + "' "
	cSqlDBX += "   AND SE5.E5_CLIFOR  = '" + cFornece + "' "
	cSqlDBX += "   AND SE5.E5_LOJA    = '" + cLoja    + "' "
	cSqlDBX += "   AND SE5.E5_TIPODOC IN ('BA','VL') "
	cSqlDBX += "   AND SE5.E5_RECPAG  = 'P' "
	cSqlDBX += "   AND SE5.E5_SITUACA <> 'C' "
	cSqlDBX += "   AND SE5.E5_DATA <= '" + DtoS(dDataBase) + "' "
	cSqlDBX += "   AND SE5.D_E_L_E_T_ = ' ' "
	cSqlDBX += "   AND NOT EXISTS (SELECT 1 "
	cSqlDBX += "                     FROM " + RetSqlName("SE5") + " A "
	cSqlDBX += "                    WHERE A.E5_FILIAL  = SE5.E5_FILIAL "
	cSqlDBX += "                      AND A.E5_PREFIXO = SE5.E5_PREFIXO "
	cSqlDBX += "                      AND A.E5_NUMERO  = SE5.E5_NUMERO "
	cSqlDBX += "                      AND A.E5_PARCELA = SE5.E5_PARCELA "
	cSqlDBX += "                      AND A.E5_CLIFOR  = SE5.E5_CLIFOR "
	cSqlDBX += "                      AND A.E5_LOJA    = SE5.E5_LOJA "
	cSqlDBX += "                      AND A.E5_SEQ     = SE5.E5_SEQ "
	cSqlDBX += "                      AND A.E5_TIPODOC = 'ES' "
	cSqlDBX += "                      AND A.E5_RECPAG  = 'R' "
	cSqlDBX += "                      AND A.D_E_L_E_T_ = ' ') "

	Begin Sequence
		dbUseArea(.T., "TOPCONN", TCGenQry(,, cSqlDBX), cAliasDBX, .F., .T.)
		TCSetField(cAliasDBX, "ULTBAIXA", "D", 8, 0)
		If !(cAliasDBX)->(Eof()) .And. !Empty((cAliasDBX)->ULTBAIXA)
			dRet := (cAliasDBX)->ULTBAIXA
		EndIf
		(cAliasDBX)->(DbCloseArea())
	Recover
		If Select(cAliasDBX) > 0
			(cAliasDBX)->(DbCloseArea())
		EndIf
	End Sequence

Return dRet

// =============================================================================
// Static Function FIN150PosSE2
// Posiciona SE2 para uso pelo SaldoTit().
// =============================================================================
Static Function FIN150PosSE2(ccFilial, cPrefixo, cNumero, cParcela, cTipo, cFornece, cLoja)
	Local lFound := .F.
	If Select("SE2") == 0
		Return .F.
	EndIf
	SE2->(DbSetOrder(1))
	lFound := SE2->(MsSeek(ccFilial + cPrefixo + cNumero + cParcela + cTipo + cFornece + cLoja))
	If !lFound
		ConOut("[FINR150API] FIN150PosSE2 nao encontrou chave " + ccFilial + "/" + AllTrim(cPrefixo) + "/" + ;
			AllTrim(cNumero) + "/" + AllTrim(cParcela) + "/" + AllTrim(cTipo) + "/" + AllTrim(cFornece) + "/" + AllTrim(cLoja))
	EndIf
Return lFound


// =============================================================================
// Static Function FIN150MontaErro
// =============================================================================
Static Function FIN150MontaErro(cCode, cMessage, cDetails)
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





