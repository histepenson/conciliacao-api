#Include "Protheus.ch"
#INCLUDE "restful.CH"
#Include "APWEBSRV.ch"
#Include "FWCOMMAND.CH"

/*/{Protheus.doc} ZFINR130API
API REST equivalente ao relatorio FINR130 (Posicao dos Titulos a Receber).
Aceita os mesmos parametros do relatorio original e aplica as mesmas
regras de negocio, incluindo calculo de saldo retroativo via SaldoTit().

Endpoint: GET /rest/zfinr130api/api/v1/finr130

@type Function
@author Equipe Desenvolvimento
@since 17/03/2026
@version 5.0
/*/

wsrestful ZFINR130API description "FINR130 - Posicao dos Titulos a Receber"

	wsdata page            as string
	wsdata pageSize        as string

	// par36 - DATA BASE (obrigatorio)
	wsdata data_base       as string

	// par01/02 - Cliente
	wsdata cliente_de      as string
	wsdata cliente_ate     as string

	// par03/04 - Prefixo
	wsdata prefixo_de      as string
	wsdata prefixo_ate     as string

	// par05/06 - Numero
	wsdata num_de          as string
	wsdata num_ate         as string

	// par07/08 - Banco/Portador
	wsdata banco_de        as string
	wsdata banco_ate       as string

	// par09/10 - Vencimento (YYYYMMDD)
	wsdata vencto_de       as string
	wsdata vencto_ate      as string

	// par11/12 - Natureza
	wsdata natureza_de     as string
	wsdata natureza_ate    as string

	// par13/14 - Emissao (YYYYMMDD)
	wsdata emissao_de      as string
	wsdata emissao_ate     as string

	// par15 - Moeda
	wsdata moeda           as string

	// par16 - Provisorios (1=Incluir 2=Excluir)
	wsdata provisorios     as string

	// par17 - Reajuste pelo vencimento (1=Nao 2=Sim)
	wsdata reajuste_vencto as string

	// par18 - Titulos descontados (1=Imprime 2=Nao imprime)
	wsdata tit_descontados as string

	// par20 - Saldo retroativo (1=Sim 2=Nao)
	wsdata saldo_retroativo as string

	// par21 - Considera filiais (1=Range 2=Filial corrente)
	wsdata consid_filiais  as string

	// par22/23 - Range de filiais
	wsdata filial_de       as string
	wsdata filial_ate      as string

	// par24/25 - Loja
	wsdata loja_de         as string
	wsdata loja_ate        as string

	// par26 - Adiantamentos (1=Considera 2=Nao considera)
	wsdata adiantamentos   as string

	// par27/28 - Data contabil (YYYYMMDD)
	wsdata dtcontab_de     as string
	wsdata dtcontab_ate    as string

	// par30 - Outras moedas (1=Imprime 2=Nao imprime)
	wsdata outras_moedas   as string

	// par31/32 - Tipos a incluir/excluir (separados por ";")
	wsdata tipos_incluir   as string
	wsdata tipos_excluir   as string

	// par33 - Abatimentos (1=Lista 2=Nao Lista 3=Despreza)
	wsdata abatimentos     as string

	// par34 - Fluxo de caixa (1=Considera 2=Nao considera)
	wsdata fluxo_caixa     as string

	// par37 - Compoe saldo por (1=DtBaixa 2=Credito 3=DtDigit)
	wsdata comp_saldo_por  as string

	// par38 - Titulos emissao futura (1=Sim 2=Nao)
	wsdata emissao_futura  as string

	// par39 - Taxa moeda (1=DtReajuste 2=TaxaContratada)
	wsdata taxa_moeda      as string

	// par40 - Considera data vencimento (1=VencReal 2=Vencimento)
	wsdata considera_data  as string

	// par43 - Considera titulos excluidos via FJU (1=Sim 2=Nao)
	wsdata titulos_excluidos as string

	wsmethod GET getTitulos description "Busca titulos a receber na data base" wssyntax "/api/v1/finr130" PATH "/api/v1/finr130"

EndwsRestFul


// =============================================================================
// wsmethod GET ZFINR130API
// =============================================================================
wsmethod GET getTitulos WSRESTFUL ZFINR130API
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
Local cCodigoCli     := ""
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

// MV_ carregadas via SuperGetMv
Local cMvAbatim      := SuperGetMv("MV_ABATIM",  .F., "")
Local cMvFuAbt       := SuperGetMv("MV_FUABT",   .F., "")
Local cMvProvis      := SuperGetMv("MV_PROVIS",  .F., "")
Local cMvRecAnt      := SuperGetMv("MV_RECANT",  .F., "")
Local cMvCrNeg       := SuperGetMv("MV_CRNEG",   .F., "")
Local cMvBr10925    := SuperGetMv("MV_BR10925", .F., "2")

// Parametros via query string
Local cDataBase        := AllTrim(Self:data_base)
Local cClienteDe       := AllTrim(Self:cliente_de)
Local cClienteAte      := AllTrim(Self:cliente_ate)
Local cPrefixoDe       := AllTrim(Self:prefixo_de)
Local cPrefixoAte      := AllTrim(Self:prefixo_ate)
Local cNumDe           := AllTrim(Self:num_de)
Local cNumAte          := AllTrim(Self:num_ate)
Local cBancoDe         := AllTrim(Self:banco_de)
Local cBancoAte        := AllTrim(Self:banco_ate)
Local cVenctoDe        := AllTrim(Self:vencto_de)
Local cVenctoAte       := AllTrim(Self:vencto_ate)
Local cNaturezaDe      := AllTrim(Self:natureza_de)
Local cNaturezaAte     := AllTrim(Self:natureza_ate)
Local cEmissaoDe       := AllTrim(Self:emissao_de)
Local cEmissaoAte      := AllTrim(Self:emissao_ate)
Local cMoeda           := AllTrim(Self:moeda)
Local cProvisorios     := AllTrim(Self:provisorios)
Local cReajusteVencto  := AllTrim(Self:reajuste_vencto)
Local cTitDescontados  := AllTrim(Self:tit_descontados)
Local cSldRetroativo   := AllTrim(Self:saldo_retroativo)
Local cConsidFiliais   := AllTrim(Self:consid_filiais)
Local cFilialDe        := AllTrim(Self:filial_de)
Local cFilialAte       := AllTrim(Self:filial_ate)
Local cLojaDe          := AllTrim(Self:loja_de)
Local cLojaAte         := AllTrim(Self:loja_ate)
Local cAdiantamentos   := AllTrim(Self:adiantamentos)
Local cDtContabDe      := AllTrim(Self:dtcontab_de)
Local cDtContabAte     := AllTrim(Self:dtcontab_ate)
Local cOutrasMoedas    := AllTrim(Self:outras_moedas)
Local cTiposIncluir    := AllTrim(Self:tipos_incluir)
Local cTiposExcluir    := AllTrim(Self:tipos_excluir)
Local cAbatimentos     := AllTrim(Self:abatimentos)
Local cFluxoCaixa      := AllTrim(Self:fluxo_caixa)
Local cCompSaldoPor    := AllTrim(Self:comp_saldo_por)
Local cEmissaoFutura   := AllTrim(Self:emissao_futura)
Local cTaxaMoeda       := AllTrim(Self:taxa_moeda)
Local cConsideraData   := AllTrim(Self:considera_data)
Local cTitulosExcl     := AllTrim(Self:titulos_excluidos)
Local nPage            := Max(1, Val(AllTrim(Self:page)))
Local nPageSize        := Val(AllTrim(Self:pageSize))

// Variaveis de conversao e defaults
Local dDataBase      := CtoD("")
Local nMoeda         := 1
Local nProvisorios   := 1
Local nReajVencto    := 1
Local nTitDesc       := 1
Local nSldRetro      := 1
Local nConsidFil     := 2
Local nAdiant        := 1
Local nAbatimentos   := 1
Local nOutrasMoedas  := 1
Local nFluxoCaixa    := 2
Local nCompSaldoPor  := 1
Local nEmissaoFutura := 2
Local nTaxaMoeda     := 1
Local nConsideraData := 1
Local nPar43         := 2
Local lSldRetro      := .T.
Local cFilialSE1     := ""
Local cFilialSE5     := ""
Local dEmissaoDe     := CtoD("")
Local dEmissaoAte    := CtoD("")
Local dVenctoDe      := CtoD("")
Local dVenctoAte     := CtoD("")
Local dDtContabDe    := CtoD("")
Local dDtContabAte   := CtoD("")
Local dUltBaixa      := CtoD("")
Local cCampoVenc     := "E1_VENCREA"
Local nTotalReg      := 0
Local nTotalPages    := 1
Local nOffset        := 0
Local nRecAtual      := 0
Local lAbriuSE5      := .F.
Local nOrdemSE5Ant   := 0
Local lAbriuSE1      := .F.
Local nOrdemSE1Ant   := 0

Self:SetContentType("application/json")

// -------------------------------------------------------------------------
// Validacao obrigatoria: data_base
// -------------------------------------------------------------------------
If Empty(cDataBase) .Or. Len(cDataBase) <> 8
	Self:nStatusCode := 422
	Self:cResponse   := FIN130MontaErro("VALIDATION_ERROR", ;
		"Parametro data_base e obrigatorio no formato YYYYMMDD", "")
	RestArea(aArea)
Return .T.
EndIf

// Inicializa cache do SaldoTit() — identico ao original FINR130 linha 161
// OBRIGATORIO: SaldoTit() requer FWPreparedStatement valido para funcionar
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
// Protege moeda zero (igual ao relatorio original)
If nMoeda == 0
	nMoeda := 1
EndIf
nProvisorios     := IIf(Empty(cProvisorios),    1, Val(cProvisorios))
nReajVencto      := IIf(Empty(cReajusteVencto), 1, Val(cReajusteVencto))
nTitDesc         := IIf(Empty(cTitDescontados), 1, Val(cTitDescontados))
nSldRetro        := IIf(Empty(cSldRetroativo),  1, Val(cSldRetroativo))
nConsidFil       := IIf(Empty(cConsidFiliais),  2, Val(cConsidFiliais))
nAdiant          := IIf(Empty(cAdiantamentos),  1, Val(cAdiantamentos))
nOutrasMoedas    := IIf(Empty(cOutrasMoedas),   1, Val(cOutrasMoedas))
nFluxoCaixa      := IIf(Empty(cFluxoCaixa),     2, Val(cFluxoCaixa))
nCompSaldoPor    := IIf(Empty(cCompSaldoPor),   1, Val(cCompSaldoPor))
nEmissaoFutura   := IIf(Empty(cEmissaoFutura),  2, Val(cEmissaoFutura))
nTaxaMoeda       := IIf(Empty(cTaxaMoeda),      1, Val(cTaxaMoeda))
nConsideraData   := IIf(Empty(cConsideraData),  1, Val(cConsideraData))
nAbatimentos     := IIf(Empty(cAbatimentos),    1, Val(cAbatimentos))
nPar43           := IIf(Empty(cTitulosExcl),    2, Val(cTitulosExcl))

lSldRetro  := (nSldRetro == 1)
nPageSize  := IIf(nPageSize <= 0 .Or. nPageSize > 500, 100, nPageSize)
nDecs      := MsDecimais(nMoeda)

// Filial
If nConsidFil == 2
	cFilialSE1 := xFilial("SE1")
Else
	cFilialSE1 := ""
EndIf

// Limites padrao dos campos de filtro
cClienteDe   := IIf(Empty(cClienteDe),   Space(TamSX3("E1_CLIENTE")[1]),           PadR(cClienteDe,   TamSX3("E1_CLIENTE")[1]))
cClienteAte  := IIf(Empty(cClienteAte),  Replicate("Z", TamSX3("E1_CLIENTE")[1]),  PadR(cClienteAte,  TamSX3("E1_CLIENTE")[1]))
cLojaDe      := IIf(Empty(cLojaDe),      Space(TamSX3("E1_LOJA")[1]),              PadR(cLojaDe,      TamSX3("E1_LOJA")[1]))
cLojaAte     := IIf(Empty(cLojaAte),     Replicate("Z", TamSX3("E1_LOJA")[1]),     PadR(cLojaAte,     TamSX3("E1_LOJA")[1]))
cPrefixoDe   := IIf(Empty(cPrefixoDe),   Space(TamSX3("E1_PREFIXO")[1]),           PadR(cPrefixoDe,   TamSX3("E1_PREFIXO")[1]))
cPrefixoAte  := IIf(Empty(cPrefixoAte),  Replicate("Z", TamSX3("E1_PREFIXO")[1]), PadR(cPrefixoAte,  TamSX3("E1_PREFIXO")[1]))
cNumDe       := IIf(Empty(cNumDe),       Space(TamSX3("E1_NUM")[1]),               PadR(cNumDe,       TamSX3("E1_NUM")[1]))
cNumAte      := IIf(Empty(cNumAte),      Replicate("Z", TamSX3("E1_NUM")[1]),      PadR(cNumAte,      TamSX3("E1_NUM")[1]))
cBancoDe     := IIf(Empty(cBancoDe),     Space(TamSX3("E1_PORTADO")[1]),           PadR(cBancoDe,     TamSX3("E1_PORTADO")[1]))
cBancoAte    := IIf(Empty(cBancoAte),    Replicate("Z", TamSX3("E1_PORTADO")[1]),  PadR(cBancoAte,    TamSX3("E1_PORTADO")[1]))
cNaturezaDe  := IIf(Empty(cNaturezaDe),  Space(TamSX3("E1_NATUREZ")[1]),           PadR(cNaturezaDe,  TamSX3("E1_NATUREZ")[1]))
cNaturezaAte := IIf(Empty(cNaturezaAte), Replicate("Z", TamSX3("E1_NATUREZ")[1]), PadR(cNaturezaAte, TamSX3("E1_NATUREZ")[1]))

dEmissaoDe   := IIf(Len(cEmissaoDe)  == 8, StoD(cEmissaoDe),  CtoD(""))
dEmissaoAte  := IIf(Len(cEmissaoAte) == 8, StoD(cEmissaoAte), dDataBase)
dVenctoDe    := IIf(Len(cVenctoDe)   == 8, StoD(cVenctoDe),   CtoD(""))
dVenctoAte   := IIf(Len(cVenctoAte)  == 8, StoD(cVenctoAte),  CtoD(""))

// Data contabil: default de='' ate=dDataBase (igual ao Pergunte do relatorio)
dDtContabDe  := IIf(Len(cDtContabDe)  == 8, StoD(cDtContabDe),  CtoD(""))
dDtContabAte := IIf(Len(cDtContabAte) == 8, StoD(cDtContabAte), dDataBase)

// Verificacao de compensacao multi-filial (lVerCmpFil)
lVerCmpFil := !Empty(FwxFilial("SE1")) .And. !Empty(FwxFilial("SE5"))

// -------------------------------------------------------------------------
// Monta SQL principal (fase 1 - titulos normais sem abatimentos)
// Identico ao original FINR130 linha 1069-1070:
// cInsFase1 = query com AND E1_TIPO NOT IN MVABATIM (sempre)
// -------------------------------------------------------------------------
cCampoVenc := IIf(nConsideraData == 2, "E1_VENCTO", "E1_VENCREA")

cSql := " SELECT SE1.E1_FILIAL, SE1.E1_PREFIXO, SE1.E1_NUM, SE1.E1_PARCELA, "
cSql += "        SE1.E1_TIPO, SE1.E1_CLIENTE, SE1.E1_LOJA, SE1.E1_NOMCLI, "
cSql += "        SE1.E1_EMISSAO, SE1.E1_EMIS1, SE1.E1_VENCTO, SE1.E1_VENCREA, "
cSql += "        SE1.E1_PORTADO, SE1.E1_SITUACA, SE1.E1_VALOR, SE1.E1_SALDO, "
cSql += "        SE1.E1_NUMBCO, SE1.E1_JUROS, SE1.E1_HIST, SE1.E1_MOEDA, "
cSql += "        SE1.E1_NATUREZ, SE1.E1_BAIXA, SE1.E1_DECRESC, SE1.E1_ACRESC, "
cSql += "        SE1.E1_TXMOEDA, SE1.E1_FILORIG, SE1.E1_FLUXO, "
cSql += "        SE1.E1_SDACRES, SE1.E1_SDDECRE, SE1.E1_MOVIMEN, "
cSql += "        CASE WHEN EXISTS (SELECT 1 FROM " + RetSqlName("SE5") + " SE5CMP "
cSql += "             WHERE SE5CMP.D_E_L_E_T_ = ' ' "
cSql += "             AND SE5CMP.E5_FILIAL <> SE1.E1_FILIAL "
cSql += "             AND SE5CMP.E5_PREFIXO = SE1.E1_PREFIXO "
cSql += "             AND SE5CMP.E5_NUMERO = SE1.E1_NUM "
cSql += "             AND SE5CMP.E5_PARCELA = SE1.E1_PARCELA "
cSql += "             AND SE5CMP.E5_TIPO = SE1.E1_TIPO "
cSql += "             AND SE5CMP.E5_CLIFOR = SE1.E1_CLIENTE "
cSql += "             AND SE5CMP.E5_LOJA = SE1.E1_LOJA "
cSql += "             AND SE5CMP.E5_MOTBX IN ('CMP','CEC')) THEN 'S' ELSE 'N' END AS E1_TEMCMP "
cSql += " FROM " + RetSqlName("SE1") + " SE1 "
cSql += " WHERE SE1.D_E_L_E_T_ = ' ' "

// Filtro de filial
If nConsidFil == 2
	cSql += "   AND SE1.E1_FILIAL = '" + cFilialSE1 + "' "
ElseIf !Empty(cFilialDe) .And. !Empty(cFilialAte)
	cSql += "   AND SE1.E1_FILIAL BETWEEN '" + PadR(cFilialDe, TamSX3("E1_FILIAL")[1]) + "' AND '" + PadR(cFilialAte, TamSX3("E1_FILIAL")[1]) + "' "
EndIf

cSql += "   AND SE1.E1_CLIENTE BETWEEN '" + cClienteDe  + "' AND '" + cClienteAte  + "' "
cSql += "   AND SE1.E1_LOJA    BETWEEN '" + cLojaDe     + "' AND '" + cLojaAte     + "' "
cSql += "   AND SE1.E1_PREFIXO BETWEEN '" + cPrefixoDe  + "' AND '" + cPrefixoAte  + "' "
cSql += "   AND SE1.E1_NUM     BETWEEN '" + cNumDe      + "' AND '" + cNumAte      + "' "
cSql += "   AND SE1.E1_PORTADO BETWEEN '" + cBancoDe    + "' AND '" + cBancoAte    + "' "
cSql += "   AND SE1.E1_NATUREZ BETWEEN '" + cNaturezaDe + "' AND '" + cNaturezaAte + "' "

// par38/par13/par14 - Emissao (FINR130 linha 1009-1015)
// Cap em dDataBase somente quando emissao_ate >= data_base (igual ao original)
cSql += "   AND SE1.E1_EMISSAO BETWEEN '" + DtoS(dEmissaoDe) + "' AND '"
If nEmissaoFutura == 2 .And. dEmissaoAte >= dDataBase
	cSql += DtoS(dDataBase) + "' "
Else
	cSql += DtoS(dEmissaoAte) + "' "
EndIf

// par27/par28 - Data contabil: aplica SEMPRE (FINR130 linha 1017)
cSql += "   AND SE1.E1_EMIS1 BETWEEN '" + DtoS(dDtContabDe) + "' AND '" + DtoS(dDtContabAte) + "' "

// par09/10 - Vencimento
If !Empty(dVenctoDe)
	cSql += "   AND SE1." + cCampoVenc + " >= '" + DtoS(dVenctoDe) + "' "
EndIf
If !Empty(dVenctoAte)
	cSql += "   AND SE1." + cCampoVenc + " <= '" + DtoS(dVenctoAte) + "' "
EndIf

// par16 - Provisorios
If nProvisorios == 2 .And. !Empty(cMvProvis)
	cSql += "   AND SE1.E1_TIPO NOT IN " + FormatIn(cMvProvis, "|") + " "
EndIf

// par26 - Adiantamentos
If nAdiant == 2 .And. !Empty(cMvRecAnt)
	cSql += "   AND SE1.E1_TIPO NOT IN " + FormatIn(cMvRecAnt + "|" + cMvCrNeg, "|") + " "
EndIf

// par18 - Descontados
If nTitDesc == 2 .And. !Empty(cListDesc)
	cSql += "   AND SE1.E1_SITUACA NOT IN " + FormatIn(cListDesc, "|") + " "
EndIf

// par30 - Outras moedas
If nOutrasMoedas == 2
	cSql += "   AND SE1.E1_MOEDA = " + AllTrim(Str(nMoeda)) + " "
EndIf

// par31 - Tipos incluir
If !Empty(cTiposIncluir)
	cSql += "   AND SE1.E1_TIPO IN " + FormatIn(cTiposIncluir, ";") + " "
EndIf

// par32 - Tipos excluir
If !Empty(cTiposExcluir)
	cSql += "   AND SE1.E1_TIPO NOT IN " + FormatIn(cTiposExcluir, ";") + " "
EndIf

// par34 - Fluxo de caixa
If nFluxoCaixa == 1
	cSql += "   AND SE1.E1_FLUXO <> 'N' "
EndIf

// Saldo/Baixa (FINR130 linha 1052-1053)
If lSldRetro
	cSql += "   AND ( SE1.E1_SALDO > 0 OR ( SE1.E1_BAIXA > '" + DtoS(dDataBase) + "' "
	cSql += "         AND SE1.E1_BAIXA <> '        ' AND SE1.E1_BAIXA <> '00000000' ) ) "
Else
	cSql += "   AND SE1.E1_SALDO > 0 "
EndIf

// par33 - Abatimentos: SEMPRE excluidos da query principal (FINR130 linha 1070)
If !Empty(cMvAbatim)
	cSql += "   AND SE1.E1_TIPO NOT IN " + FormatIn(cMvAbatim, "|") + " "
EndIf
If !Empty(cMvFuAbt)
	cSql += "   AND SE1.E1_TIPO NOT IN " + FormatIn(cMvFuAbt, "|") + " "
EndIf

cSql += " ORDER BY SE1.E1_CLIENTE, SE1.E1_LOJA, SE1.E1_NUM, SE1.E1_PARCELA, SE1.E1_TIPO "

ConOut("[FINR130API] SQL PRINCIPAL: " + cSql)

// -------------------------------------------------------------------------
// Executa query e processa registros
// -------------------------------------------------------------------------
Begin Sequence

	// Cria objeto de cache para SaldoTit() (substitui __oTBxCanc do relatorio)
	Begin Sequence
		__oTBxCanc := FWPreparedStatement():New()
	Recover
		__oTBxCanc := Nil
	End Sequence

	dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .F., .T.)
	ConOut("[FINR130API] SQL executado - LastRec=" + Str((cAlias)->(LastRec()), 6))
	TCSetField(cAlias, "E1_EMISSAO", "D", 8, 0)
	TCSetField(cAlias, "E1_EMIS1",   "D", 8, 0)
	TCSetField(cAlias, "E1_VENCTO",  "D", 8, 0)
	TCSetField(cAlias, "E1_VENCREA", "D", 8, 0)
	TCSetField(cAlias, "E1_BAIXA",   "D", 8, 0)
	TCSetField(cAlias, "E1_MOVIMEN", "D", 8, 0)
	TCSetField(cAlias, "E1_VALOR",   "N", 16, 2)
	TCSetField(cAlias, "E1_SALDO",   "N", 16, 2)
	TCSetField(cAlias, "E1_JUROS",   "N", 16, 2)
	TCSetField(cAlias, "E1_DECRESC", "N", 16, 2)
	TCSetField(cAlias, "E1_ACRESC",  "N", 16, 2)
	TCSetField(cAlias, "E1_TXMOEDA", "N", 15, 4)
	TCSetField(cAlias, "E1_MOEDA",   "N", 2, 0)
	TCSetField(cAlias, "E1_SDACRES", "N", 16, 2)
	TCSetField(cAlias, "E1_SDDECRE", "N", 16, 2)

	ConOut("[FINR130API] lSldRetro=" + IIf(lSldRetro, "T", "F") + " Select(SE5)=" + Str(Select("SE5"), 3))
    If lSldRetro .And. Select("SE1") == 0
        ChkFile("SE1", .F., "SE1")
        lAbriuSE1 := .T.
    ElseIf lSldRetro
        nOrdemSE1Ant := SE1->(IndexOrd())
    EndIf
	If lSldRetro .And. Select("SE5") == 0
		ChkFile("SE5", .F., "SE5")
		lAbriuSE5 := .T.
		If Empty(SE5->(IndexKey(7)))
			Break 
		EndIf
		SE5->(DbSetorder(7))
		ConOut("[FINR130API] SE5 aberta via ChkFile - Select(SE5)=" + Str(Select("SE5"), 3) + " Order=" + Str(SE5->(IndexOrd()), 2))
	ElseIf lSldRetro
		nOrdemSE5Ant := SE5->(IndexOrd())
		ConOut("[FINR130API] SE5 ja estava aberta - Select(SE5)=" + Str(Select("SE5"), 3))
		If Empty(SE5->(IndexKey(7)))
			Break 
		EndIf
		SE5->(DbSetorder(7))
	EndIf

	ConOut("[FINR130API] RecCnt cAlias=" + Str((cAlias)->(LastRec()), 6) + " dDataBase=" + DtoS(dDataBase))

	(cAlias)->(DbGoTop())

	While !(cAlias)->(Eof())

		// FINR130 linha 1613-1617: em saldo retroativo, nao lista PIS/COF/CSL ja emitidos
		If lSldRetro .And. cMvBr10925 == "1" .And. (cAlias)->E1_EMISSAO <= dDataBase .And. ;
				AllTrim((cAlias)->E1_TIPO) $ "PIS/COF/CSL"
			(cAlias)->(DbSkip())
			Loop
		EndIf

		// par17 - data de reajuste: usa moeda de exibicao (nMoeda=par15), igual ao original
		// (FINR130 linha 1628: RecMoeda(SE1->E1_VENCREA, cMoeda) onde cMoeda=Str(mv_par15))
		dDataReaj := dDataBase
		If (cAlias)->E1_VENCREA < dDataBase .And. nReajVencto == 2 .And. ;
				RecMoeda((cAlias)->E1_VENCREA, nMoeda) > 0
			dDataReaj := (cAlias)->E1_VENCREA
		EndIf

		// par39 - taxa moeda (FINR130 linha 1653)
		nTxMoedSld := IIf(nTaxaMoeda == 2, ;
			IIf(!Empty((cAlias)->E1_TXMOEDA), (cAlias)->E1_TXMOEDA, RecMoeda((cAlias)->E1_EMISSAO, (cAlias)->E1_MOEDA)), ;
			0)
		lIsTxContr := (nTaxaMoeda == 2 .And. !Empty((cAlias)->E1_TXMOEDA))

		If lSldRetro
			// cFilSE5: usa E1_FILIAL do proprio titulo para garantir match com E5_FILIAL em SE5.
			// FwxFilial("SE5") na thread REST retorna apenas o codigo da empresa sem filial ativa
			// (ex: "02   "), enquanto os registros SE5 tem E5_FILIAL com a filial real (ex: "0201").
			// Usando E1_FILIAL o valor ja vem padded do banco exatamente como armazenado em SE5.
			cFilialSE5 := (cAlias)->E1_FILIAL

			ConOut("[FINR130API] SaldoTit PARAMS: PRE=" + AllTrim((cAlias)->E1_PREFIXO) + ;
				" NUM=" + AllTrim((cAlias)->E1_NUM) + " PAR=" + AllTrim((cAlias)->E1_PARCELA) + ;
				" TIPO=" + AllTrim((cAlias)->E1_TIPO) + " CLI=" + AllTrim((cAlias)->E1_CLIENTE) + ;
				" LOJA=" + AllTrim((cAlias)->E1_LOJA) + ;
				" E1_FILIAL=[" + (cAlias)->E1_FILIAL + "] FwxFilial=[" + FwxFilial("SE5") + "]" + ;
				" MOEDA=" + Str(nMoeda, 2) + " dDataReaj=" + DtoS(dDataReaj) + ;
				" dDataBase=" + DtoS(dDataBase) + " SE5Sel=" + Str(Select("SE5"), 3))

            If !FIN130PosSE1((cAlias)->E1_FILIAL, (cAlias)->E1_PREFIXO, (cAlias)->E1_NUM, (cAlias)->E1_PARCELA, ;
                    (cAlias)->E1_TIPO, (cAlias)->E1_CLIENTE, (cAlias)->E1_LOJA)
                ConOut("[FINR130API] SE1 nao posicionada para SaldoTit - titulo descartado")
                (cAlias)->(DbSkip())
                Loop
            EndIf

			// SaldoTit() - 17 parametros identicos ao original (FINR130 linha 1656-1657)
			nSaldo := SaldoTit( ;
				(cAlias)->E1_PREFIXO, ;
				(cAlias)->E1_NUM,     ;
				(cAlias)->E1_PARCELA, ;
				(cAlias)->E1_TIPO,    ;
				(cAlias)->E1_NATUREZ, ;
				"R",                  ;
				(cAlias)->E1_CLIENTE, ;
				nMoeda,               ;
				dDataReaj,            ;
				dDataBase,            ;
				(cAlias)->E1_LOJA,    ;
				cFilialSE5,           ;
				nTxMoedSld,           ;
				nCompSaldoPor,        ;
				.F.,                  ;
				__oTBxCanc,           ;
				lIsTxContr            ;
				)

			ConOut("[FINR130API] SaldoTit RESULT=" + Str(nSaldo, 16, 2) + ;
				" E1_SALDO=" + Str((cAlias)->E1_SALDO, 16, 2) + ;
				" E1_BAIXA=" + DtoS((cAlias)->E1_BAIXA))

			// Compensacoes multi-filial (FINR130 linha 1661-1666)
			If lVerCmpFil .And. AllTrim((cAlias)->E1_TEMCMP) == "S"
				nSaldo -= Round(NoRound(xMoeda( ;
					FRVlCompFil("R", (cAlias)->E1_PREFIXO, (cAlias)->E1_NUM, ;
						(cAlias)->E1_PARCELA, (cAlias)->E1_TIPO, ;
						(cAlias)->E1_CLIENTE, (cAlias)->E1_LOJA, ;
						nCompSaldoPor, {}, , .F., ;
						nMoeda, (cAlias)->E1_MOEDA, nTxMoedSld, dDataReaj, .T.), ;
					(cAlias)->E1_MOEDA, nMoeda, dDataReaj, nDecs + 1, nTxMoedSld), ;
					nDecs + 1), nDecs)
			EndIf

			// dUltBaixa: ultima baixa efetiva ate dDataBase (FINR130 linha 1672-1673)
			dUltBaixa := (cAlias)->E1_BAIXA
			If !Empty(dUltBaixa) .And. dDataBase < dUltBaixa
				// FR130DBX(): busca ultima baixa real ate dDataBase via SE5
				dUltBaixa := FIN130DBX( ;
					(cAlias)->E1_PREFIXO, (cAlias)->E1_NUM, ;
					(cAlias)->E1_PARCELA, (cAlias)->E1_TIPO, ;
					(cAlias)->E1_CLIENTE, (cAlias)->E1_LOJA, ;
					cFilialSE5, dDataBase, nCompSaldoPor)
			EndIf

			// Ajuste decrescimo (FINR130 linha 1677-1682)
			If (cAlias)->E1_DECRESC > 0
				If nMoeda == (cAlias)->E1_MOEDA .And. Str((cAlias)->E1_VALOR, 17, 2) == Str(nSaldo, 17, 2)
					nSaldo -= (cAlias)->E1_DECRESC
				ElseIf Round(NoRound(xMoeda((cAlias)->E1_VALOR, (cAlias)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
						IIf(nTaxaMoeda==2, IIf(!Empty((cAlias)->E1_TXMOEDA), (cAlias)->E1_TXMOEDA, RecMoeda((cAlias)->E1_EMISSAO, (cAlias)->E1_MOEDA)), 0)), nDecs+1), nDecs) == nSaldo
					nSaldo := Round(NoRound(xMoeda((cAlias)->E1_VALOR - (cAlias)->E1_DECRESC, (cAlias)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
						IIf(nTaxaMoeda==2, IIf(!Empty((cAlias)->E1_TXMOEDA), (cAlias)->E1_TXMOEDA, RecMoeda((cAlias)->E1_EMISSAO, (cAlias)->E1_MOEDA)), 0)), nDecs+1), nDecs)
				EndIf
			EndIf

			// Ajuste acrescimo (FINR130 linha 1685-1691)
			If (cAlias)->E1_ACRESC > 0 .And. IIf(Empty(dUltBaixa), .T., dDataBase < dUltBaixa)
				If nMoeda == (cAlias)->E1_MOEDA .And. Str((cAlias)->E1_VALOR, 17, 2) == Str(nSaldo, 17, 2)
					nSaldo += (cAlias)->E1_ACRESC
				ElseIf Round(NoRound(xMoeda((cAlias)->E1_VALOR, (cAlias)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
						IIf(nTaxaMoeda==2, IIf(!Empty((cAlias)->E1_TXMOEDA), (cAlias)->E1_TXMOEDA, RecMoeda((cAlias)->E1_EMISSAO, (cAlias)->E1_MOEDA)), 0)), nDecs+1), nDecs) == nSaldo
					nSaldo := Round(NoRound(xMoeda((cAlias)->E1_VALOR + (cAlias)->E1_ACRESC, (cAlias)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
						IIf(nTaxaMoeda==2, IIf(!Empty((cAlias)->E1_TXMOEDA), (cAlias)->E1_TXMOEDA, RecMoeda((cAlias)->E1_EMISSAO, (cAlias)->E1_MOEDA)), 0)), nDecs+1), nDecs)
				EndIf
			EndIf

		Else
			// Saldo nao-retroativo (FINR130 linha 1777)
			// Inclui E1_SDACRES e E1_SDDECRE; usa RecMoeda como fallback de taxa
			nSaldo := xMoeda( ;
				(cAlias)->E1_SALDO + (cAlias)->E1_SDACRES - (cAlias)->E1_SDDECRE, ;
				(cAlias)->E1_MOEDA, nMoeda, dDataReaj, nDecs + 1, ;
				IIf(nTaxaMoeda==2, ;
					IIf(!Empty((cAlias)->E1_TXMOEDA), (cAlias)->E1_TXMOEDA, RecMoeda((cAlias)->E1_EMISSAO, (cAlias)->E1_MOEDA)), ;
					0))
		EndIf

		nSaldo := Round(NoRound(nSaldo, 3), 2)

		ConOut("[FINR130API] nSaldo FINAL=" + Str(nSaldo, 16, 2) + ;
			" TITULO=" + AllTrim((cAlias)->E1_NUM) + "/" + AllTrim((cAlias)->E1_PARCELA) + ;
			" INCLUIDO=" + IIf(nSaldo > 0, "SIM", "NAO (descartado)"))

		If nSaldo > 0
			nDiasVenc  := dDataBase - (cAlias)->E1_VENCREA
			cPrazo     := IIf(nDiasVenc > 365, "LONGO PRAZO", "CURTO PRAZO")
			cCodigoCli := "C" + AllTrim((cAlias)->E1_CLIENTE) + AllTrim((cAlias)->E1_LOJA)

			oItem := JsonObject():New()
			oItem["filial"]         := AllTrim((cAlias)->E1_FILIAL)
			oItem["prefixo"]        := AllTrim((cAlias)->E1_PREFIXO)
			oItem["numero"]         := AllTrim((cAlias)->E1_NUM)
			oItem["parcela"]        := AllTrim((cAlias)->E1_PARCELA)
			oItem["tipo"]           := AllTrim((cAlias)->E1_TIPO)
			oItem["cliente"]        := AllTrim((cAlias)->E1_CLIENTE)
			oItem["loja"]           := AllTrim((cAlias)->E1_LOJA)
			oItem["nome_cliente"]   := AllTrim((cAlias)->E1_NOMCLI)
			oItem["natureza"]       := AllTrim((cAlias)->E1_NATUREZ)
			oItem["emissao"]        := DToS((cAlias)->E1_EMISSAO)
			oItem["vencto"]         := DToS((cAlias)->E1_VENCTO)
			oItem["vencto_real"]    := DToS((cAlias)->E1_VENCREA)
			oItem["banco"]          := AllTrim((cAlias)->E1_PORTADO)
			oItem["situacao"]       := AllTrim((cAlias)->E1_SITUACA)
			oItem["valor_original"] := (cAlias)->E1_VALOR
			oItem["saldo_na_data"]  := nSaldo
			oItem["saldo_atual"]    := (cAlias)->E1_SALDO
			oItem["moeda"]          := (cAlias)->E1_MOEDA
			oItem["numero_banco"]   := AllTrim((cAlias)->E1_NUMBCO)
			oItem["juros"]          := (cAlias)->E1_JUROS
			oItem["historico"]      := AllTrim((cAlias)->E1_HIST)
			oItem["dias_vencidos"]  := nDiasVenc
			oItem["prazo"]          := cPrazo
			oItem["codigo_cli"]     := cCodigoCli

			aAdd(aAllTitulos, oItem)
		EndIf

		(cAlias)->(DbSkip())
	EndDO

	(cAlias)->(DbCloseArea())

	ConOut("[FINR130API] Fase1 concluida - aAllTitulos=" + Str(Len(aAllTitulos), 6))

	// -------------------------------------------------------------------------
	// Fase 2: Abatimentos (FINR130 linha 1693+)
	// Quando par33 == 1 (Lista), busca titulos do tipo MVABATIM separadamente
	// -------------------------------------------------------------------------
	// FINR130 linha 1167: Fase 2 quando par33 != 3 (Lista OU Nao Lista, nunca Despreza)
	If nAbatimentos != 3 .And. (!Empty(cMvAbatim) .Or. !Empty(cMvFuAbt))
		cSqlAbat   := ""
		cMvAbatAll := ""

		cMvAbatAll := cMvAbatim
		If !Empty(cMvFuAbt)
			cMvAbatAll := IIf(Empty(cMvAbatAll), cMvFuAbt, cMvAbatAll + "|" + cMvFuAbt)
		EndIf

		// Monta concatenacao compativel com o SGBD (replica logica do original linha 983-987)
		If lMSSQL
			cConcatPai := "SE1PAI.E1_PREFIXO + SE1PAI.E1_NUM + SE1PAI.E1_PARCELA + SE1PAI.E1_TIPO + SE1PAI.E1_CLIENTE + SE1PAI.E1_LOJA"
		ElseIf lConSQL
			cConcatPai := "CONCAT(SE1PAI.E1_PREFIXO, SE1PAI.E1_NUM, SE1PAI.E1_PARCELA, SE1PAI.E1_TIPO, SE1PAI.E1_CLIENTE, SE1PAI.E1_LOJA)"
		Else
			cConcatPai := "SE1PAI.E1_PREFIXO || SE1PAI.E1_NUM || SE1PAI.E1_PARCELA || SE1PAI.E1_TIPO || SE1PAI.E1_CLIENTE || SE1PAI.E1_LOJA"
		EndIf

		cSqlAbat := " SELECT SE1.E1_FILIAL, SE1.E1_PREFIXO, SE1.E1_NUM, SE1.E1_PARCELA, "
		cSqlAbat += "        SE1.E1_TIPO, SE1.E1_CLIENTE, SE1.E1_LOJA, SE1.E1_NOMCLI, "
		cSqlAbat += "        SE1.E1_EMISSAO, SE1.E1_EMIS1, SE1.E1_VENCTO, SE1.E1_VENCREA, "
		cSqlAbat += "        SE1.E1_PORTADO, SE1.E1_SITUACA, SE1.E1_VALOR, SE1.E1_SALDO, "
		cSqlAbat += "        SE1.E1_NUMBCO, SE1.E1_JUROS, SE1.E1_HIST, SE1.E1_MOEDA, "
		cSqlAbat += "        SE1.E1_NATUREZ, SE1.E1_BAIXA, SE1.E1_DECRESC, SE1.E1_ACRESC, "
		cSqlAbat += "        SE1.E1_TXMOEDA, SE1.E1_FILORIG, SE1.E1_FLUXO, "
		cSqlAbat += "        SE1.E1_SDACRES, SE1.E1_SDDECRE, SE1.E1_MOVIMEN, "
		cSqlAbat += "        CASE WHEN EXISTS (SELECT 1 FROM " + RetSqlName("SE5") + " SE5CMP "
		cSqlAbat += "             WHERE SE5CMP.D_E_L_E_T_ = ' ' "
		cSqlAbat += "             AND SE5CMP.E5_FILIAL <> SE1.E1_FILIAL "
		cSqlAbat += "             AND SE5CMP.E5_PREFIXO = SE1.E1_PREFIXO "
		cSqlAbat += "             AND SE5CMP.E5_NUMERO = SE1.E1_NUM "
		cSqlAbat += "             AND SE5CMP.E5_PARCELA = SE1.E1_PARCELA "
		cSqlAbat += "             AND SE5CMP.E5_TIPO = SE1.E1_TIPO "
		cSqlAbat += "             AND SE5CMP.E5_CLIFOR = SE1.E1_CLIENTE "
		cSqlAbat += "             AND SE5CMP.E5_LOJA = SE1.E1_LOJA "
		cSqlAbat += "             AND SE5CMP.E5_MOTBX IN ('CMP','CEC')) THEN 'S' ELSE 'N' END AS E1_TEMCMP "
		cSqlAbat += " FROM " + RetSqlName("SE1") + " SE1 "
		cSqlAbat += " WHERE SE1.D_E_L_E_T_ = ' ' "

		If nConsidFil == 2
			cSqlAbat += "   AND SE1.E1_FILIAL = '" + cFilialSE1 + "' "
		ElseIf !Empty(cFilialDe) .And. !Empty(cFilialAte)
			cSqlAbat += "   AND SE1.E1_FILIAL BETWEEN '" + PadR(cFilialDe, TamSX3("E1_FILIAL")[1]) + "' AND '" + PadR(cFilialAte, TamSX3("E1_FILIAL")[1]) + "' "
		EndIf

		// FINR130 linha 1182-1187: filtros de range + vinculacao com titulo pai (E1TITPAI)
		cSqlAbat += "   AND SE1.E1_PREFIXO BETWEEN '" + cPrefixoDe + "' AND '" + cPrefixoAte + "' "
		cSqlAbat += "   AND SE1.E1_NUM BETWEEN '" + cNumDe + "' AND '" + cNumAte + "' "
		cSqlAbat += "   AND SE1.E1_CLIENTE BETWEEN '" + cClienteDe + "' AND '" + cClienteAte + "' "
		cSqlAbat += "   AND SE1.E1_LOJA BETWEEN '" + cLojaDe + "' AND '" + cLojaAte + "' "
		// EXISTS: so inclui abatimento se titulo pai existe na query principal (equivale a cTable do original)
		cSqlAbat += "   AND EXISTS (SELECT 1 FROM " + RetSqlName("SE1") + " SE1PAI "
		cSqlAbat += "       WHERE SE1PAI.D_E_L_E_T_ = ' ' "
		cSqlAbat += "       AND SE1PAI.E1_TIPO NOT IN " + FormatIn(cMvAbatAll, "|") + " "
		cSqlAbat += "       AND " + cConcatPai + " = SE1.E1_TITPAI) "
		cSqlAbat += "   AND SE1.E1_TIPO IN " + FormatIn(cMvAbatAll, "|") + " "

		// FINR130 linha 1189: tipos a excluir (par32) tambem aplicado em Fase 2
		If !Empty(cTiposExcluir)
			cSqlAbat += "   AND SE1.E1_TIPO NOT IN " + FormatIn(cTiposExcluir, ";") + " "
		EndIf

		If lSldRetro
			cSqlAbat += "   AND ( SE1.E1_SALDO > 0 OR ( SE1.E1_BAIXA > '" + DtoS(dDataBase) + "' "
			cSqlAbat += "         AND SE1.E1_BAIXA <> '        ' AND SE1.E1_BAIXA <> '00000000' ) ) "
		Else
			cSqlAbat += "   AND SE1.E1_SALDO > 0 "
		EndIf

		dbUseArea(.T., "TOPCONN", TCGenQry(,, cSqlAbat), cAliasAbat, .F., .T.)
		TCSetField(cAliasAbat, "E1_EMISSAO", "D", 8, 0)
		TCSetField(cAliasAbat, "E1_EMIS1",   "D", 8, 0)
		TCSetField(cAliasAbat, "E1_VENCTO",  "D", 8, 0)
		TCSetField(cAliasAbat, "E1_VENCREA", "D", 8, 0)
		TCSetField(cAliasAbat, "E1_BAIXA",   "D", 8, 0)
		TCSetField(cAliasAbat, "E1_MOVIMEN", "D", 8, 0)
		TCSetField(cAliasAbat, "E1_VALOR",   "N", 16, 2)
		TCSetField(cAliasAbat, "E1_SALDO",   "N", 16, 2)
		TCSetField(cAliasAbat, "E1_JUROS",   "N", 16, 2)
		TCSetField(cAliasAbat, "E1_DECRESC", "N", 16, 2)
		TCSetField(cAliasAbat, "E1_ACRESC",  "N", 16, 2)
		TCSetField(cAliasAbat, "E1_TXMOEDA", "N", 15, 4)
		TCSetField(cAliasAbat, "E1_MOEDA",   "N", 2, 0)
		TCSetField(cAliasAbat, "E1_SDACRES", "N", 16, 2)
		TCSetField(cAliasAbat, "E1_SDDECRE", "N", 16, 2)

		(cAliasAbat)->(DbGoTop())

		While !(cAliasAbat)->(Eof())
			// Abatimento ja fechado antes da data base: saldo = 0, nao incluir (FINR130 linha 1693-1699)
			If ((cAliasAbat)->E1_SALDO == 0) .And. ;
				((!Empty((cAliasAbat)->E1_BAIXA)   .And. (cAliasAbat)->E1_BAIXA   <= dDataBase) .Or. ;
				 (!Empty((cAliasAbat)->E1_MOVIMEN) .And. (cAliasAbat)->E1_MOVIMEN <= dDataBase))
				(cAliasAbat)->(DbSkip())
				Loop
			EndIf

			// Calcula saldo do abatimento da mesma forma que titulo normal
			dDataReaj := dDataBase
			If (cAliasAbat)->E1_VENCREA < dDataBase .And. nReajVencto == 2 .And. ;
					RecMoeda((cAliasAbat)->E1_VENCREA, nMoeda) > 0
				dDataReaj := (cAliasAbat)->E1_VENCREA
			EndIf

			nTxMoedSld := IIf(nTaxaMoeda == 2, ;
				IIf(!Empty((cAliasAbat)->E1_TXMOEDA), (cAliasAbat)->E1_TXMOEDA, RecMoeda((cAliasAbat)->E1_EMISSAO, (cAliasAbat)->E1_MOEDA)), ;
				0)
			lIsTxContr := (nTaxaMoeda == 2 .And. !Empty((cAliasAbat)->E1_TXMOEDA))

			If lSldRetro
				cFilialSE5 := (cAliasAbat)->E1_FILIAL  // usa filial do titulo para match com E5_FILIAL
If !FIN130PosSE1((cAliasAbat)->E1_FILIAL, (cAliasAbat)->E1_PREFIXO, (cAliasAbat)->E1_NUM, (cAliasAbat)->E1_PARCELA, ;
        (cAliasAbat)->E1_TIPO, (cAliasAbat)->E1_CLIENTE, (cAliasAbat)->E1_LOJA)
    ConOut("[FINR130API] SE1 nao posicionada para SaldoTit abatimento - titulo descartado")
    (cAliasAbat)->(DbSkip())
    Loop
EndIf
				nSaldo := SaldoTit( ;
					(cAliasAbat)->E1_PREFIXO, (cAliasAbat)->E1_NUM, ;
					(cAliasAbat)->E1_PARCELA,  (cAliasAbat)->E1_TIPO, ;
					(cAliasAbat)->E1_NATUREZ,  "R", ;
					(cAliasAbat)->E1_CLIENTE,  nMoeda, dDataReaj, dDataBase, ;
					(cAliasAbat)->E1_LOJA,     cFilialSE5, nTxMoedSld, ;
					nCompSaldoPor, .F., __oTBxCanc, lIsTxContr)

				dUltBaixa := (cAliasAbat)->E1_BAIXA
				If !Empty(dUltBaixa) .And. dDataBase < dUltBaixa
					dUltBaixa := FIN130DBX( ;
						(cAliasAbat)->E1_PREFIXO, (cAliasAbat)->E1_NUM, ;
						(cAliasAbat)->E1_PARCELA,  (cAliasAbat)->E1_TIPO, ;
						(cAliasAbat)->E1_CLIENTE,  (cAliasAbat)->E1_LOJA, ;
						cFilialSE5, dDataBase, nCompSaldoPor)
				EndIf

				If (cAliasAbat)->E1_DECRESC > 0
					If nMoeda == (cAliasAbat)->E1_MOEDA .And. Str((cAliasAbat)->E1_VALOR, 17, 2) == Str(nSaldo, 17, 2)
						nSaldo -= (cAliasAbat)->E1_DECRESC
					ElseIf Round(NoRound(xMoeda((cAliasAbat)->E1_VALOR, (cAliasAbat)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
							IIf(nTaxaMoeda==2, IIf(!Empty((cAliasAbat)->E1_TXMOEDA), (cAliasAbat)->E1_TXMOEDA, RecMoeda((cAliasAbat)->E1_EMISSAO, (cAliasAbat)->E1_MOEDA)), 0)), nDecs+1), nDecs) == nSaldo
						nSaldo := Round(NoRound(xMoeda((cAliasAbat)->E1_VALOR - (cAliasAbat)->E1_DECRESC, (cAliasAbat)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
							IIf(nTaxaMoeda==2, IIf(!Empty((cAliasAbat)->E1_TXMOEDA), (cAliasAbat)->E1_TXMOEDA, RecMoeda((cAliasAbat)->E1_EMISSAO, (cAliasAbat)->E1_MOEDA)), 0)), nDecs+1), nDecs)
					EndIf
				EndIf

				If (cAliasAbat)->E1_ACRESC > 0 .And. IIf(Empty(dUltBaixa), .T., dDataBase < dUltBaixa)
					If nMoeda == (cAliasAbat)->E1_MOEDA .And. Str((cAliasAbat)->E1_VALOR, 17, 2) == Str(nSaldo, 17, 2)
						nSaldo += (cAliasAbat)->E1_ACRESC
					ElseIf Round(NoRound(xMoeda((cAliasAbat)->E1_VALOR, (cAliasAbat)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
							IIf(nTaxaMoeda==2, IIf(!Empty((cAliasAbat)->E1_TXMOEDA), (cAliasAbat)->E1_TXMOEDA, RecMoeda((cAliasAbat)->E1_EMISSAO, (cAliasAbat)->E1_MOEDA)), 0)), nDecs+1), nDecs) == nSaldo
						nSaldo := Round(NoRound(xMoeda((cAliasAbat)->E1_VALOR + (cAliasAbat)->E1_ACRESC, (cAliasAbat)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
							IIf(nTaxaMoeda==2, IIf(!Empty((cAliasAbat)->E1_TXMOEDA), (cAliasAbat)->E1_TXMOEDA, RecMoeda((cAliasAbat)->E1_EMISSAO, (cAliasAbat)->E1_MOEDA)), 0)), nDecs+1), nDecs)
					EndIf
				EndIf
			Else
				nSaldo := xMoeda( ;
					(cAliasAbat)->E1_SALDO + (cAliasAbat)->E1_SDACRES - (cAliasAbat)->E1_SDDECRE, ;
					(cAliasAbat)->E1_MOEDA, nMoeda, dDataReaj, nDecs + 1, ;
					IIf(nTaxaMoeda==2, ;
						IIf(!Empty((cAliasAbat)->E1_TXMOEDA), (cAliasAbat)->E1_TXMOEDA, RecMoeda((cAliasAbat)->E1_EMISSAO, (cAliasAbat)->E1_MOEDA)), ;
						0))
			EndIf

			nSaldo := Round(NoRound(nSaldo, 3), 2)

			If nSaldo > 0
				nDiasVenc  := dDataBase - (cAliasAbat)->E1_VENCREA
				cPrazo     := IIf(nDiasVenc > 365, "LONGO PRAZO", "CURTO PRAZO")
				cCodigoCli := "C" + AllTrim((cAliasAbat)->E1_CLIENTE) + AllTrim((cAliasAbat)->E1_LOJA)

				oItem := JsonObject():New()
				oItem["filial"]         := AllTrim((cAliasAbat)->E1_FILIAL)
				oItem["prefixo"]        := AllTrim((cAliasAbat)->E1_PREFIXO)
				oItem["numero"]         := AllTrim((cAliasAbat)->E1_NUM)
				oItem["parcela"]        := AllTrim((cAliasAbat)->E1_PARCELA)
				oItem["tipo"]           := AllTrim((cAliasAbat)->E1_TIPO)
				oItem["cliente"]        := AllTrim((cAliasAbat)->E1_CLIENTE)
				oItem["loja"]           := AllTrim((cAliasAbat)->E1_LOJA)
				oItem["nome_cliente"]   := AllTrim((cAliasAbat)->E1_NOMCLI)
				oItem["natureza"]       := AllTrim((cAliasAbat)->E1_NATUREZ)
				oItem["emissao"]        := DToS((cAliasAbat)->E1_EMISSAO)
				oItem["vencto"]         := DToS((cAliasAbat)->E1_VENCTO)
				oItem["vencto_real"]    := DToS((cAliasAbat)->E1_VENCREA)
				oItem["banco"]          := AllTrim((cAliasAbat)->E1_PORTADO)
				oItem["situacao"]       := AllTrim((cAliasAbat)->E1_SITUACA)
				oItem["valor_original"] := (cAliasAbat)->E1_VALOR
				oItem["saldo_na_data"]  := nSaldo
				oItem["saldo_atual"]    := (cAliasAbat)->E1_SALDO
				oItem["moeda"]          := (cAliasAbat)->E1_MOEDA
				oItem["numero_banco"]   := AllTrim((cAliasAbat)->E1_NUMBCO)
				oItem["juros"]          := (cAliasAbat)->E1_JUROS
				oItem["historico"]      := AllTrim((cAliasAbat)->E1_HIST)
				oItem["dias_vencidos"]  := nDiasVenc
				oItem["prazo"]          := cPrazo
				oItem["codigo_cli"]     := cCodigoCli

				aAdd(aAllTitulos, oItem)
			EndIf

			(cAliasAbat)->(DbSkip())
		EndDO

		(cAliasAbat)->(DbCloseArea())
	EndIf

	// -------------------------------------------------------------------------
	// Fase 3: Titulos excluidos via FJU (par43 == 1) (FINR130 linha 1079-1130)
	// -------------------------------------------------------------------------
	If nPar43 == 1
		cSqlFJU   := ""
		cAliasFJU := GetNextAlias()

		cSqlFJU := " SELECT SE1.E1_FILIAL, SE1.E1_PREFIXO, SE1.E1_NUM, SE1.E1_PARCELA, "
		cSqlFJU += "        SE1.E1_TIPO, SE1.E1_CLIENTE, SE1.E1_LOJA, SE1.E1_NOMCLI, "
		cSqlFJU += "        SE1.E1_EMISSAO, SE1.E1_EMIS1, SE1.E1_VENCTO, SE1.E1_VENCREA, "
		cSqlFJU += "        SE1.E1_PORTADO, SE1.E1_SITUACA, SE1.E1_VALOR, SE1.E1_SALDO, "
		cSqlFJU += "        SE1.E1_NUMBCO, SE1.E1_JUROS, SE1.E1_HIST, SE1.E1_MOEDA, "
		cSqlFJU += "        SE1.E1_NATUREZ, SE1.E1_BAIXA, SE1.E1_DECRESC, SE1.E1_ACRESC, "
		cSqlFJU += "        SE1.E1_TXMOEDA, SE1.E1_FILORIG, SE1.E1_FLUXO, "
		cSqlFJU += "        SE1.E1_SDACRES, SE1.E1_SDDECRE, SE1.E1_MOVIMEN, "
		cSqlFJU += "        CASE WHEN EXISTS (SELECT 1 FROM " + RetSqlName("SE5") + " SE5CMP "
		cSqlFJU += "             WHERE SE5CMP.D_E_L_E_T_ = ' ' "
		cSqlFJU += "             AND SE5CMP.E5_FILIAL <> SE1.E1_FILIAL "
		cSqlFJU += "             AND SE5CMP.E5_PREFIXO = SE1.E1_PREFIXO "
		cSqlFJU += "             AND SE5CMP.E5_NUMERO = SE1.E1_NUM "
		cSqlFJU += "             AND SE5CMP.E5_PARCELA = SE1.E1_PARCELA "
		cSqlFJU += "             AND SE5CMP.E5_TIPO = SE1.E1_TIPO "
		cSqlFJU += "             AND SE5CMP.E5_CLIFOR = SE1.E1_CLIENTE "
		cSqlFJU += "             AND SE5CMP.E5_LOJA = SE1.E1_LOJA "
		cSqlFJU += "             AND SE5CMP.E5_MOTBX IN ('CMP','CEC')) THEN 'S' ELSE 'N' END AS E1_TEMCMP "
		cSqlFJU += " FROM " + RetSqlName("SE1") + " SE1 "
		cSqlFJU += " INNER JOIN " + RetSqlName("FJU") + " FJU "
		cSqlFJU += "   ON SE1.E1_FILORIG = FJU.FJU_FILIAL "
		cSqlFJU += "  AND SE1.E1_PREFIXO = FJU.FJU_PREFIX "
		cSqlFJU += "  AND SE1.E1_NUM     = FJU.FJU_NUM "
		cSqlFJU += "  AND SE1.E1_PARCELA = FJU.FJU_PARCEL "
		cSqlFJU += "  AND SE1.E1_TIPO    = FJU.FJU_TIPO "
		cSqlFJU += "  AND SE1.E1_CLIENTE = FJU.FJU_CLIFOR "
		cSqlFJU += "  AND SE1.E1_LOJA    = FJU.FJU_LOJA "
		cSqlFJU += " WHERE SE1.D_E_L_E_T_ = '*' "
		cSqlFJU += "   AND FJU.D_E_L_E_T_ = ' ' "
		cSqlFJU += "   AND FJU.FJU_CART   = 'R' "
		cSqlFJU += "   AND FJU.FJU_EMIS   <= '" + DtoS(dDataBase) + "' "
		cSqlFJU += "   AND FJU.FJU_DTEXCL >= '" + DtoS(dDataBase) + "' "
		cSqlFJU += "   AND SE1.E1_CLIENTE BETWEEN '" + cClienteDe + "' AND '" + cClienteAte + "' "

		If nConsidFil == 2
			cSqlFJU += "   AND SE1.E1_FILIAL = '" + cFilialSE1 + "' "
		EndIf

		If !Empty(cMvAbatim)
			cSqlFJU += "   AND SE1.E1_TIPO NOT IN " + FormatIn(cMvAbatim, "|") + " "
		EndIf

		dbUseArea(.T., "TOPCONN", TCGenQry(,, cSqlFJU), cAliasFJU, .F., .T.)
		TCSetField(cAliasFJU, "E1_EMISSAO", "D", 8, 0)
		TCSetField(cAliasFJU, "E1_EMIS1",   "D", 8, 0)
		TCSetField(cAliasFJU, "E1_VENCTO",  "D", 8, 0)
		TCSetField(cAliasFJU, "E1_VENCREA", "D", 8, 0)
		TCSetField(cAliasFJU, "E1_BAIXA",   "D", 8, 0)
		TCSetField(cAliasFJU, "E1_MOVIMEN", "D", 8, 0)
		TCSetField(cAliasFJU, "E1_VALOR",   "N", 16, 2)
		TCSetField(cAliasFJU, "E1_SALDO",   "N", 16, 2)
		TCSetField(cAliasFJU, "E1_JUROS",   "N", 16, 2)
		TCSetField(cAliasFJU, "E1_DECRESC", "N", 16, 2)
		TCSetField(cAliasFJU, "E1_ACRESC",  "N", 16, 2)
		TCSetField(cAliasFJU, "E1_TXMOEDA", "N", 15, 4)
		TCSetField(cAliasFJU, "E1_MOEDA",   "N", 2, 0)
		TCSetField(cAliasFJU, "E1_SDACRES", "N", 16, 2)
		TCSetField(cAliasFJU, "E1_SDDECRE", "N", 16, 2)

		(cAliasFJU)->(DbGoTop())

		While !(cAliasFJU)->(Eof())

			If lSldRetro .And. cMvBr10925 == "1" .And. (cAliasFJU)->E1_EMISSAO <= dDataBase .And. ;
					AllTrim((cAliasFJU)->E1_TIPO) $ "PIS/COF/CSL"
				(cAliasFJU)->(DbSkip())
				Loop
			EndIf

			dDataReaj := dDataBase
			If (cAliasFJU)->E1_VENCREA < dDataBase .And. nReajVencto == 2 .And. ;
					RecMoeda((cAliasFJU)->E1_VENCREA, nMoeda) > 0
				dDataReaj := (cAliasFJU)->E1_VENCREA
			EndIf

			nTxMoedSld := IIf(nTaxaMoeda == 2, ;
				IIf(!Empty((cAliasFJU)->E1_TXMOEDA), (cAliasFJU)->E1_TXMOEDA, RecMoeda((cAliasFJU)->E1_EMISSAO, (cAliasFJU)->E1_MOEDA)), ;
				0)
			lIsTxContr := (nTaxaMoeda == 2 .And. !Empty((cAliasFJU)->E1_TXMOEDA))

			If lSldRetro
				cFilialSE5 := (cAliasFJU)->E1_FILIAL
If !FIN130PosSE1((cAliasFJU)->E1_FILIAL, (cAliasFJU)->E1_PREFIXO, (cAliasFJU)->E1_NUM, (cAliasFJU)->E1_PARCELA, ;
        (cAliasFJU)->E1_TIPO, (cAliasFJU)->E1_CLIENTE, (cAliasFJU)->E1_LOJA)
    ConOut("[FINR130API] SE1 nao posicionada para SaldoTit FJU - titulo descartado")
    (cAliasFJU)->(DbSkip())
    Loop
EndIf
				nSaldo := SaldoTit( ;
					(cAliasFJU)->E1_PREFIXO, (cAliasFJU)->E1_NUM, ;
					(cAliasFJU)->E1_PARCELA,  (cAliasFJU)->E1_TIPO, ;
					(cAliasFJU)->E1_NATUREZ,  "R", ;
					(cAliasFJU)->E1_CLIENTE,  nMoeda, dDataReaj, dDataBase, ;
					(cAliasFJU)->E1_LOJA,     cFilialSE5, nTxMoedSld, ;
					nCompSaldoPor, .F., __oTBxCanc, lIsTxContr)

				If lVerCmpFil .And. AllTrim((cAliasFJU)->E1_TEMCMP) == "S"
					nSaldo -= Round(NoRound(xMoeda( ;
						FRVlCompFil("R", (cAliasFJU)->E1_PREFIXO, (cAliasFJU)->E1_NUM, ;
							(cAliasFJU)->E1_PARCELA, (cAliasFJU)->E1_TIPO, ;
							(cAliasFJU)->E1_CLIENTE, (cAliasFJU)->E1_LOJA, ;
							nCompSaldoPor, {}, , .F., ;
							nMoeda, (cAliasFJU)->E1_MOEDA, nTxMoedSld, dDataReaj, .T.), ;
						(cAliasFJU)->E1_MOEDA, nMoeda, dDataReaj, nDecs + 1, nTxMoedSld), ;
						nDecs + 1), nDecs)
				EndIf

				dUltBaixa := (cAliasFJU)->E1_BAIXA
				If !Empty(dUltBaixa) .And. dDataBase < dUltBaixa
					dUltBaixa := FIN130DBX( ;
						(cAliasFJU)->E1_PREFIXO, (cAliasFJU)->E1_NUM, ;
						(cAliasFJU)->E1_PARCELA,  (cAliasFJU)->E1_TIPO, ;
						(cAliasFJU)->E1_CLIENTE,  (cAliasFJU)->E1_LOJA, ;
						cFilialSE5, dDataBase, nCompSaldoPor)
				EndIf

				If (cAliasFJU)->E1_DECRESC > 0
					If nMoeda == (cAliasFJU)->E1_MOEDA .And. Str((cAliasFJU)->E1_VALOR, 17, 2) == Str(nSaldo, 17, 2)
						nSaldo -= (cAliasFJU)->E1_DECRESC
					ElseIf Round(NoRound(xMoeda((cAliasFJU)->E1_VALOR, (cAliasFJU)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
							IIf(nTaxaMoeda==2, IIf(!Empty((cAliasFJU)->E1_TXMOEDA), (cAliasFJU)->E1_TXMOEDA, RecMoeda((cAliasFJU)->E1_EMISSAO, (cAliasFJU)->E1_MOEDA)), 0)), nDecs+1), nDecs) == nSaldo
						nSaldo := Round(NoRound(xMoeda((cAliasFJU)->E1_VALOR - (cAliasFJU)->E1_DECRESC, (cAliasFJU)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
							IIf(nTaxaMoeda==2, IIf(!Empty((cAliasFJU)->E1_TXMOEDA), (cAliasFJU)->E1_TXMOEDA, RecMoeda((cAliasFJU)->E1_EMISSAO, (cAliasFJU)->E1_MOEDA)), 0)), nDecs+1), nDecs)
					EndIf
				EndIf

				If (cAliasFJU)->E1_ACRESC > 0 .And. IIf(Empty(dUltBaixa), .T., dDataBase < dUltBaixa)
					If nMoeda == (cAliasFJU)->E1_MOEDA .And. Str((cAliasFJU)->E1_VALOR, 17, 2) == Str(nSaldo, 17, 2)
						nSaldo += (cAliasFJU)->E1_ACRESC
					ElseIf Round(NoRound(xMoeda((cAliasFJU)->E1_VALOR, (cAliasFJU)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
							IIf(nTaxaMoeda==2, IIf(!Empty((cAliasFJU)->E1_TXMOEDA), (cAliasFJU)->E1_TXMOEDA, RecMoeda((cAliasFJU)->E1_EMISSAO, (cAliasFJU)->E1_MOEDA)), 0)), nDecs+1), nDecs) == nSaldo
						nSaldo := Round(NoRound(xMoeda((cAliasFJU)->E1_VALOR + (cAliasFJU)->E1_ACRESC, (cAliasFJU)->E1_MOEDA, nMoeda, dDataReaj, nDecs+1, ;
							IIf(nTaxaMoeda==2, IIf(!Empty((cAliasFJU)->E1_TXMOEDA), (cAliasFJU)->E1_TXMOEDA, RecMoeda((cAliasFJU)->E1_EMISSAO, (cAliasFJU)->E1_MOEDA)), 0)), nDecs+1), nDecs)
					EndIf
				EndIf

				If AllTrim((cAliasFJU)->E1_TIPO) == "RA"
					nSaldo -= FIN130TipoBA((cAliasFJU)->E1_FILIAL, (cAliasFJU)->E1_PREFIXO, (cAliasFJU)->E1_NUM, ;
						(cAliasFJU)->E1_PARCELA, (cAliasFJU)->E1_TIPO, (cAliasFJU)->E1_CLIENTE, (cAliasFJU)->E1_LOJA, dDataBase)
				EndIf
			Else
				nSaldo := xMoeda( ;
					(cAliasFJU)->E1_SALDO + (cAliasFJU)->E1_SDACRES - (cAliasFJU)->E1_SDDECRE, ;
					(cAliasFJU)->E1_MOEDA, nMoeda, dDataReaj, nDecs + 1, ;
					IIf(nTaxaMoeda==2, ;
						IIf(!Empty((cAliasFJU)->E1_TXMOEDA), (cAliasFJU)->E1_TXMOEDA, RecMoeda((cAliasFJU)->E1_EMISSAO, (cAliasFJU)->E1_MOEDA)), ;
						0))
			EndIf

			nSaldo := Round(NoRound(nSaldo, 3), 2)

			If nSaldo > 0
				nDiasVenc  := dDataBase - (cAliasFJU)->E1_VENCREA
				cPrazo     := IIf(nDiasVenc > 365, "LONGO PRAZO", "CURTO PRAZO")
				cCodigoCli := "C" + AllTrim((cAliasFJU)->E1_CLIENTE) + AllTrim((cAliasFJU)->E1_LOJA)

				oItem := JsonObject():New()
				oItem["filial"]         := AllTrim((cAliasFJU)->E1_FILIAL)
				oItem["prefixo"]        := AllTrim((cAliasFJU)->E1_PREFIXO)
				oItem["numero"]         := AllTrim((cAliasFJU)->E1_NUM)
				oItem["parcela"]        := AllTrim((cAliasFJU)->E1_PARCELA)
				oItem["tipo"]           := AllTrim((cAliasFJU)->E1_TIPO)
				oItem["cliente"]        := AllTrim((cAliasFJU)->E1_CLIENTE)
				oItem["loja"]           := AllTrim((cAliasFJU)->E1_LOJA)
				oItem["nome_cliente"]   := AllTrim((cAliasFJU)->E1_NOMCLI)
				oItem["natureza"]       := AllTrim((cAliasFJU)->E1_NATUREZ)
				oItem["emissao"]        := DToS((cAliasFJU)->E1_EMISSAO)
				oItem["vencto"]         := DToS((cAliasFJU)->E1_VENCTO)
				oItem["vencto_real"]    := DToS((cAliasFJU)->E1_VENCREA)
				oItem["banco"]          := AllTrim((cAliasFJU)->E1_PORTADO)
				oItem["situacao"]       := AllTrim((cAliasFJU)->E1_SITUACA)
				oItem["valor_original"] := (cAliasFJU)->E1_VALOR
				oItem["saldo_na_data"]  := nSaldo
				oItem["saldo_atual"]    := (cAliasFJU)->E1_SALDO
				oItem["moeda"]          := (cAliasFJU)->E1_MOEDA
				oItem["numero_banco"]   := AllTrim((cAliasFJU)->E1_NUMBCO)
				oItem["juros"]          := (cAliasFJU)->E1_JUROS
				oItem["historico"]      := AllTrim((cAliasFJU)->E1_HIST)
				oItem["dias_vencidos"]  := nDiasVenc
				oItem["prazo"]          := cPrazo
				oItem["codigo_cli"]     := cCodigoCli

				aAdd(aAllTitulos, oItem)
			EndIf

			(cAliasFJU)->(DbSkip())
		EndDO

		(cAliasFJU)->(DbCloseArea())
	EndIf

    If lSldRetro .And. Select("SE1") > 0 .And. lAbriuSE1
        SE1->(DbCloseArea())
    ElseIf lSldRetro .And. Select("SE1") > 0 .And. nOrdemSE1Ant > 0
        SE1->(DbSetOrder(nOrdemSE1Ant))
    EndIf

	// Fecha SE5 aberta para SaldoTit() (encerra apos todas as fases)
	If lSldRetro .And. Select("SE5") > 0 .And. lAbriuSE5
		SE5->(DbCloseArea())
	ElseIf lSldRetro .And. Select("SE5") > 0 .And. nOrdemSE5Ant > 0
		SE5->(DbSetOrder(nOrdemSE5Ant))
	EndIf

	// Libera objeto de cache
	If !Empty(__oTBxCanc)
		FreeObj(__oTBxCanc)
		__oTBxCanc := Nil
	EndIf

    // Paginacao sobre registros validos
    nTotalReg   := Len(aAllTitulos)
    nTotalPages := Max(1, Int((nTotalReg + nPageSize - 1) / nPageSize))
    nOffset     := (nPage - 1) * nPageSize

    nRecAtual := 0
    While nRecAtual < nPageSize .And. (nOffset + nRecAtual + 1) <= nTotalReg
        aAdd(aTitulos, aAllTitulos[nOffset + nRecAtual + 1])
        nRecAtual++
    EndDo

Recover Using oError
    If Select(cAlias) > 0
        (cAlias)->(DbCloseArea())
    EndIf
    If Select(cAliasAbat) > 0
        (cAliasAbat)->(DbCloseArea())
    EndIf
    If Select("SE1") > 0 .And. lAbriuSE1
        SE1->(DbCloseArea())
    ElseIf Select("SE1") > 0 .And. nOrdemSE1Ant > 0
        SE1->(DbSetOrder(nOrdemSE1Ant))
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
    Self:cResponse   := FIN130MontaErro("INTERNAL_ERROR", ;
        "Erro interno ao consultar titulos a receber", oError:Description)
    FreeObj(oResp)
    FreeObj(oParams)
    AEval(aAllTitulos, {|o| FreeObj(o)})
    RestArea(aArea)
Return .T.
End Sequence

// Monta resposta
oParams["data_base"]        := cDataBase
oParams["filial"]           := cFilialSE1
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
oResp["titulos"]         := aTitulos

Self:SetResponse( oResp:ToJson() )
FreeObj(oResp)

// Destroi cache do SaldoTit() — identico ao original FINR130 linha 86/146
If Select("SE1") > 0 .And. lAbriuSE1
    SE1->(DbCloseArea())
ElseIf Select("SE1") > 0 .And. nOrdemSE1Ant > 0
    SE1->(DbSetOrder(nOrdemSE1Ant))
EndIf
If !Empty(__oTBxCanc)
	__oTBxCanc:Destroy()
	__oTBxCanc := Nil
EndIf

RestArea(aArea)

Return .T.


// =============================================================================
// Static Function FIN130DBX
// Busca a data da ultima baixa efetiva ate dDataBase para o titulo informado.
// Equivalente exato ao FR130DBX() do relatorio original:
//   - Usa FK1 (movimentacao detalhada) + FinBuscaFK7 para obter FK1_IDDOC
//   - Exclui motivos PCC/IRF/ISS/IMR/CMP (igual linha 3053 do original)
//   - NOT EXISTS FK1EST com FK1_TPDOC='ES' (igual linhas 3058-3067 do original)
//   - Condicao OR entre FK1_DATA/FK1_DTDISP/FK1_DTDIGI (igual linhas 3054-3056)
//
// @param cPrefixo    Prefixo do titulo (E1_PREFIXO)
// @param cNumero     Numero do titulo (E1_NUM)
// @param cParcela    Parcela do titulo (E1_PARCELA)
// @param cTipo       Tipo do titulo (E1_TIPO)
// @param cCliente    Codigo do cliente (E1_CLIENTE)
// @param cLoja       Loja do cliente (E1_LOJA)
// @param cFilSE5     Nao usado (mantido por compatibilidade de assinatura)
// @param dDataBase   Data base para limite superior da busca
// @param nCompSaldo  1=FK1_DATA  2=FK1_DTDISP  3=FK1_DTDIGI
// @return Date       Ultima data de baixa ate dDataBase, ou CtoD("") se nao encontrada
// =============================================================================
Static Function FIN130DBX(cPrefixo, cNumero, cParcela, cTipo, cCliente, cLoja, cFilSE5, dDataBase, nCompSaldo)
	Local cAliasDBX := GetNextAlias()
	Local cCampo    := "FK1_DATA"
	Local cFilFK1   := FwXFilial("FK1")
	Local cChaveTit := FwXFilial("SE1") + "|" + AllTrim(cPrefixo) + "|" + AllTrim(cNumero) + "|" + AllTrim(cParcela) + "|" + AllTrim(cTipo) + "|" + AllTrim(cCliente) + "|" + AllTrim(cLoja)
	Local cIdDoc    := FinBuscaFK7(cChaveTit, "SE1")
	Local cSqlDBX   := ""
	Local dRet      := CtoD("")


	Do Case
		Case nCompSaldo == 2
			cCampo := "FK1_DTDISP"
		Case nCompSaldo == 3
			cCampo := "FK1_DTDIGI"
		OtherWise
			cCampo := "FK1_DATA"
	EndCase

	If Empty(cIdDoc)
		Return dRet
	EndIf

	// Replica exatamente a query do FR130DBX (linhas 3049-3067 do FINR130.PRX)
	cSqlDBX := " SELECT MAX(FK1." + cCampo + ") AS ULTBAIXA "
	cSqlDBX += " FROM " + RetSqlName("FK1") + " FK1 "
	cSqlDBX += " WHERE FK1.FK1_FILIAL = '" + cFilFK1 + "' "
	cSqlDBX += "   AND FK1.FK1_IDDOC  = '" + cIdDoc  + "' "
	cSqlDBX += "   AND FK1.FK1_MOTBX NOT IN ('PCC', 'IRF', 'ISS', 'IMR', 'CMP') "
	cSqlDBX += "   AND ((FK1.FK1_DATA  <= '" + DtoS(dDataBase) + "') "
	cSqlDBX += "     OR (FK1.FK1_DTDISP <= '" + DtoS(dDataBase) + "') "
	cSqlDBX += "     OR (FK1.FK1_DTDIGI <= '" + DtoS(dDataBase) + "')) "
	cSqlDBX += "   AND FK1.D_E_L_E_T_ = ' ' "
	cSqlDBX += "   AND NOT EXISTS ( "
	cSqlDBX += "       SELECT FK1EST.FK1_IDDOC "
	cSqlDBX += "       FROM " + RetSqlName("FK1") + " FK1EST "
	cSqlDBX += "       WHERE FK1EST.FK1_FILIAL = '" + cFilFK1 + "' "
	cSqlDBX += "         AND FK1EST.FK1_IDDOC  = '" + cIdDoc  + "' "
	cSqlDBX += "         AND FK1EST.FK1_SEQ    = FK1.FK1_SEQ "
	cSqlDBX += "         AND FK1EST.FK1_TPDOC  = 'ES' "
	cSqlDBX += "         AND ((FK1EST.FK1_DATA  <= '" + DtoS(dDataBase) + "') "
	cSqlDBX += "           OR (FK1EST.FK1_DTDISP <= '" + DtoS(dDataBase) + "') "
	cSqlDBX += "           OR (FK1EST.FK1_DTDIGI <= '" + DtoS(dDataBase) + "')) "
	cSqlDBX += "         AND FK1EST.D_E_L_E_T_ = ' ') "

	Begin Sequence
		dbUseArea(.T., "TOPCONN", TCGenQry(,, cSqlDBX), cAliasDBX, .F., .T.)
		TCSetField(cAliasDBX, "ULTBAIXA", "D", 8, 0)

		If !(cAliasDBX)->(Eof())
			If !Empty((cAliasDBX)->ULTBAIXA)
				dRet := (cAliasDBX)->ULTBAIXA
			EndIf
		EndIf

		(cAliasDBX)->(DbCloseArea())
	Recover
		If Select(cAliasDBX) > 0
			(cAliasDBX)->(DbCloseArea())
		EndIf
	End Sequence

Return dRet


Static Function FIN130PosSE1(kFilial, cPrefixo, cNumero, cParcela, cTipo, cCliente, cLoja)
	Local lFound := .F.
	If Select("SE1") == 0
		Return .F.
	EndIf
	SE1->(DbSetOrder(1))
	lFound := SE1->(MsSeek(kFilial + cPrefixo + cNumero + cParcela + cTipo + cCliente + cLoja))
	If !lFound
		ConOut("[FINR130API] FIN130PosSE1 nao encontrou chave " + kFilial + "/" + AllTrim(cPrefixo) + "/" + ;
			AllTrim(cNumero) + "/" + AllTrim(cParcela) + "/" + AllTrim(cTipo) + "/" + AllTrim(cCliente) + "/" + AllTrim(cLoja))
	EndIf
Return lFound
// =============================================================================
// Static Function FIN130TipoBA
// Replica o abatimento de baixas do tipo RA para aproximar o comportamento do FINR130.
// =============================================================================
Static Function FIN130TipoBA(kFilial, cPrefixo, cNumero, cParcela, cTipo, cCliente, cLoja, dDataBase)
	Local cAliasBA := GetNextAlias()
	Local cSqlBA   := ""
	Local nValorBA := 0
	cSqlBA := " SELECT COALESCE(SUM(E5_VALOR),0) VALORBA "
	cSqlBA += " FROM " + RetSqlName("SE5") + " SE5 "
	cSqlBA += " WHERE SE5.D_E_L_E_T_ = ' ' "
	cSqlBA += "   AND SE5.E5_FILIAL  = '" + cFilial  + "' "
	cSqlBA += "   AND SE5.E5_PREFIXO = '" + cPrefixo + "' "
	cSqlBA += "   AND SE5.E5_NUMERO  = '" + cNumero  + "' "
	cSqlBA += "   AND SE5.E5_PARCELA = '" + cParcela + "' "
	cSqlBA += "   AND SE5.E5_TIPO    = '" + cTipo    + "' "
	cSqlBA += "   AND SE5.E5_CLIFOR  = '" + cCliente + "' "
	cSqlBA += "   AND SE5.E5_LOJA    = '" + cLoja    + "' "
	cSqlBA += "   AND SE5.E5_DATA    <= '" + DtoS(dDataBase) + "' "
	cSqlBA += "   AND SE5.E5_TIPODOC = 'BA' "
	Begin Sequence
		dbUseArea(.T., "TOPCONN", TCGenQry(,, cSqlBA), cAliasBA, .F., .T.)
		TCSetField(cAliasBA, "VALORBA", "N", 16, 2)
		If !(cAliasBA)->(Eof())
			nValorBA := (cAliasBA)->VALORBA
		EndIf
		(cAliasBA)->(DbCloseArea())
	Recover
		If Select(cAliasBA) > 0
			(cAliasBA)->(DbCloseArea())
		EndIf
	End Sequence
Return nValorBA
// =============================================================================
// Static Function FIN130MontaErro
// =============================================================================
Static Function FIN130MontaErro(cCode, cMessage, cDetails)
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






