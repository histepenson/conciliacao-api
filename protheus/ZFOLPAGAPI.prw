#Include "Protheus.ch"
#INCLUDE "restful.CH"
#Include "APWEBSRV.ch"
#Include "FWCOMMAND.CH"

/*/{Protheus.doc} ZFOLPAGAPI
API REST para a Conferencia Folha (Rancheiro e Ander): 12 endpoints, um por
conta contabil da folha de pagamento, cada um replicando fielmente uma
consulta SQL validada pelo analista que hoje concilia manualmente.

Nao reaproveita nem altera ZFINR130API/ZFINR150API - e uma API nova porque
duas das 12 situacoes dependem de SRD010 (ficha financeira de folha/RH),
tabela fora do escopo de qualquer relatorio de contas a pagar existente,
e porque os filtros de cada situacao nao cabem no formato generico do
FINR150 (E2_BAIXA nem eh retornado por ele hoje).

Tabela fisica e filial NUNCA sao hardcoded (RetSqlName/xFilial) porque a
mesma API roda para duas empresas (Rancheiro e Ander) com o mesmo conjunto
de contas/naturezas - so tabela fisica e filial mudam por tenant.

Cada wsmethod devolve LINHAS CRUAS (nao pre-somadas), agrupadas por fonte
(SE2 e/ou SRD), para permitir drill-down no lado Python. As listas fixas de
natureza (E2_NATUREZ) e codigo de verba (RD_PD) ficam hardcoded aqui - sao
regra de negocio de cada situacao, nao parametro de execucao.

Campos de SRD010 usados aqui (RD_FILIAL, RD_MAT, RD_PD, RD_ROTEIR,
RD_DATARQ, RD_DATPGT, RD_VALOR) foram conferidos contra o dicionario SX3
real do ambiente alvo. RD_DATARQ e RD_MAT/RD_PD/RD_ROTEIR sao caractere
(sem TCSetField "D"); RD_DATPGT e data.

Este arquivo foi escrito sem acesso a um compilador Protheus - a sintaxe
ADVPL segue fielmente o padrao de protheus/ZFINR150API.prw, mas ainda
precisa ser compilado e testado em ambiente real antes do deploy.

@author Equipe Desenvolvimento
@since 10/08/2026
@version 1.0
/*/

wsrestful ZFOLPAGAPI description "Conferencia Folha - 12 situacoes (Rancheiro/Ander)"

	// Filtro usado por: emprestimo-funcionario, fgts, inss, contribuicao-assistencial
	wsdata vencto                 as string

	// Filtro usado por: adiantamento-ferias (SE2), adiantamento-rescisao,
	// fgts-rescisorio, salario, pensao-alimenticia
	wsdata baixa_de               as string
	wsdata baixa_ate              as string

	// Filtro usado por: adiantamento-ferias (SE2), adiantamento-rescisao, fgts-rescisorio
	// Formato MMAAAA (ex: "072026"), usado em E2_HIST LIKE '%MMAAAA%'
	wsdata historico_competencia  as string

	// Filtro usado por: adiantamento-ferias (SRD), ferias-a-pagar
	// Formato AAAAMM (ex: "202606")
	wsdata datarq                 as string

	// Filtros usados por: irrf
	wsdata datarq_de              as string
	wsdata datarq_ate             as string
	wsdata datpgt_maior_que       as string
	wsdata emissao_de             as string
	wsdata emissao_ate            as string

	wsmethod GET emprestimoFunc         description "Emprestimo Funcionario (11203004)"      wssyntax "/api/v1/folhapag/emprestimo-funcionario"      PATH "/api/v1/folhapag/emprestimo-funcionario"
	wsmethod GET adiantamentoFerias     description "Adiantamento de Ferias (11203006)"       wssyntax "/api/v1/folhapag/adiantamento-ferias"         PATH "/api/v1/folhapag/adiantamento-ferias"
	wsmethod GET fgts                   description "FGTS (21102004)"                         wssyntax "/api/v1/folhapag/fgts"                        PATH "/api/v1/folhapag/fgts"
	wsmethod GET irrf                   description "IRRF (21102007)"                         wssyntax "/api/v1/folhapag/irrf"                        PATH "/api/v1/folhapag/irrf"
	wsmethod GET inss                   description "INSS (21102010)"                         wssyntax "/api/v1/folhapag/inss"                        PATH "/api/v1/folhapag/inss"
	wsmethod GET fgtsRescisorio         description "FGTS Rescisorio (21102013)"               wssyntax "/api/v1/folhapag/fgts-rescisorio"             PATH "/api/v1/folhapag/fgts-rescisorio"
	wsmethod GET contribAssist          description "Contribuicao Assistencial (21102015)"     wssyntax "/api/v1/folhapag/contribuicao-assistencial"   PATH "/api/v1/folhapag/contribuicao-assistencial"
	wsmethod GET salario                description "Salario (21103001)"                       wssyntax "/api/v1/folhapag/salario"                     PATH "/api/v1/folhapag/salario"
	wsmethod GET feriasAPagar           description "Ferias a Pagar (21103009)"                wssyntax "/api/v1/folhapag/ferias-a-pagar"              PATH "/api/v1/folhapag/ferias-a-pagar"
	wsmethod GET pensaoAlimenticia      description "Pensao Alimenticia (21103011)"            wssyntax "/api/v1/folhapag/pensao-alimenticia"         PATH "/api/v1/folhapag/pensao-alimenticia"
	wsmethod GET plr                    description "PLR (21103013)"                           wssyntax "/api/v1/folhapag/plr"                         PATH "/api/v1/folhapag/plr"
	wsmethod GET folhaSit03            description "Adiantamento de Rescisao (11203009)"     wssyntax "/api/v1/folhapag/adiant-rescisao"             PATH "/api/v1/folhapag/adiant-rescisao"

EndwsRestFul


// =============================================================================
// 1) EMPRESTIMO FUNCIONARIO - 11203004
// SE2: natureza 00400006, vencto exato, saldo > 0
// =============================================================================
wsmethod GET emprestimoFunc WSRESTFUL ZFOLPAGAPI
Local aArea      := GetArea()
Local cVencto    := AllTrim(Self:vencto)
Local cSql       := ""
Local cAlias     := GetNextAlias()
Local aLinhas    := {}
Local nTotal     := 0
Local oError     := Nil
Local oParams    := Nil

Self:SetContentType("application/json")

If Empty(cVencto) .Or. Len(cVencto) <> 8
	Self:nStatusCode := 422
	Self:cResponse   := FOLMontaErro("VALIDATION_ERROR", "Parametro vencto e obrigatorio no formato YYYYMMDD", "")
	RestArea(aArea)
Return .T.
EndIf

cSql := FOLSqlSE2Base()
cSql += "   AND SE2.E2_NATUREZ = '00400006' "
cSql += "   AND SE2.E2_VENCTO  = '" + cVencto + "' "
cSql += "   AND SE2.E2_SALDO   > 0 "
cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA "

Begin Sequence
	FOLSE2Val(cSql, cAlias, @aLinhas, @nTotal)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar emprestimo-funcionario", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oParams := JsonObject():New()
oParams["vencto"] := cVencto

Self:SetResponse(FOLMontaRespostaUmGrupo("emprestimo-funcionario", "11203004", ;
	oParams, "SE2", "E2_VALOR", aLinhas, nTotal))

AEval(aLinhas, {|o| FreeObj(o)})
FreeObj(oParams)

RestArea(aArea)
Return .T.


// =============================================================================
// 2) ADIANTAMENTO DE FERIAS - 11203006
// SE2: natureza 00600005, baixa entre, historico LIKE %MMAAAA%
// SRD: datarq = AAAAMM, roteiro <> ADI/PLR, PD in (...), sinal invertido se PD>=406
// =============================================================================
wsmethod GET adiantamentoFerias WSRESTFUL ZFOLPAGAPI
Local aArea       := GetArea()
Local cBaixaDe    := AllTrim(Self:baixa_de)
Local cBaixaAte   := AllTrim(Self:baixa_ate)
Local cHistComp   := AllTrim(Self:historico_competencia)
Local cDatarq     := AllTrim(Self:datarq)
Local cSql        := ""
Local cAliasSE2   := GetNextAlias()
Local cAliasSRD   := GetNextAlias()
Local aLinhasSE2  := {}
Local aLinhasSRD  := {}
Local nTotalSE2   := 0
Local nTotalSRD   := 0
Local oError      := Nil
Local oGrupoSE2   := Nil
Local oGrupoSRD   := Nil
Local aGrupos     := {}
Local oResp       := Nil
Local oParams     := Nil

Self:SetContentType("application/json")

If Empty(cBaixaDe) .Or. Empty(cBaixaAte) .Or. Empty(cHistComp) .Or. Empty(cDatarq)
	Self:nStatusCode := 422
	Self:cResponse   := FOLMontaErro("VALIDATION_ERROR", ;
		"Parametros baixa_de, baixa_ate, historico_competencia e datarq sao obrigatorios", "")
	RestArea(aArea)
Return .T.
EndIf

// SE2
cSql := FOLSqlSE2Base()
cSql += "   AND SE2.E2_NATUREZ = '00600005' "
cSql += "   AND SE2.E2_BAIXA BETWEEN '" + cBaixaDe + "' AND '" + cBaixaAte + "' "
cSql += "   AND SE2.E2_HIST LIKE '%" + cHistComp + "%' "
cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA "

Begin Sequence
	FOLSE2Val(cSql, cAliasSE2, @aLinhasSE2, @nTotalSE2)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar adiantamento-ferias (SE2)", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

// SRD - lista fixa de verbas (rubricas), sinal invertido quando RD_PD >= '406'
cSql := FOLSqlSRDBase()
cSql += "   AND SRD.RD_DATARQ = '" + cDatarq + "' "
cSql += "   AND SRD.RD_ROTEIR NOT IN ('ADI','PLR') "
cSql += "   AND SRD.RD_PD IN ('039','043','047','067','076','125','126','150','151','152','153','154','155','156','319','406','667') "
cSql += " ORDER BY SRD.RD_MAT, SRD.RD_PD "

Begin Sequence
	FOLSRDSgn(cSql, cAliasSRD, @aLinhasSRD, @nTotalSRD)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar adiantamento-ferias (SRD)", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oGrupoSE2 := JsonObject():New()
oGrupoSE2["fonte"]       := "SE2"
oGrupoSE2["campo_valor"] := "E2_VALOR"
oGrupoSE2["total"]       := nTotalSE2
oGrupoSE2["linhas"]      := aLinhasSE2

oGrupoSRD := JsonObject():New()
oGrupoSRD["fonte"]       := "SRD"
oGrupoSRD["campo_valor"] := "RD_VALOR"
oGrupoSRD["total"]       := nTotalSRD
oGrupoSRD["linhas"]      := aLinhasSRD

aAdd(aGrupos, oGrupoSE2)
aAdd(aGrupos, oGrupoSRD)

oParams := JsonObject():New()
oParams["baixa_de"]               := cBaixaDe
oParams["baixa_ate"]              := cBaixaAte
oParams["historico_competencia"]  := cHistComp
oParams["datarq"]                 := cDatarq

oResp := JsonObject():New()
oResp["situacao"]        := "adiantamento-ferias"
oResp["conta_contabil"]  := "11203006"
oResp["parametros"]      := oParams
oResp["grupos"]          := aGrupos
oResp["total_geral"]     := nTotalSE2 + nTotalSRD
oResp["total_registros"] := Len(aLinhasSE2) + Len(aLinhasSRD)

Self:SetResponse(oResp:ToJson())
FreeObj(oResp)
FreeObj(oGrupoSE2)
FreeObj(oGrupoSRD)
FreeObj(oParams)
AEval(aLinhasSE2, {|o| FreeObj(o)})
AEval(aLinhasSRD, {|o| FreeObj(o)})

RestArea(aArea)
Return .T.


// =============================================================================
// 3) ADIANTAMENTO DE RESCISAO - 11203009
// SE2: natureza 00600006, (baixa entre OU baixa vazia), historico LIKE %MMAAAA%
// =============================================================================
wsmethod GET folhaSit03 WSRESTFUL ZFOLPAGAPI
Local aArea      := GetArea()
Local cBaixaDe   := AllTrim(Self:baixa_de)
Local cBaixaAte  := AllTrim(Self:baixa_ate)
Local cHistComp  := AllTrim(Self:historico_competencia)
Local cCondBaixa := ""
Local cSql       := ""
Local cAlias     := GetNextAlias()
Local aLinhas    := {}
Local nTotal     := 0
Local oError     := Nil
Local oParams    := Nil

Self:SetContentType("application/json")

If Empty(cBaixaDe) .Or. Empty(cBaixaAte) .Or. Empty(cHistComp)
	Self:nStatusCode := 422
	Self:cResponse   := FOLMontaErro("VALIDATION_ERROR", "Parametros baixa_de, baixa_ate e historico_competencia sao obrigatorios", "")
	RestArea(aArea)
Return .T.
EndIf

cCondBaixa := "SE2.E2_BAIXA BETWEEN '" + cBaixaDe + "' AND '" + cBaixaAte + "' OR SE2.E2_BAIXA = ' '"

cSql := FOLSqlSE2Base()
cSql += "   AND SE2.E2_NATUREZ = '00600006' "
cSql += "   AND (" + cCondBaixa + ") "
cSql += "   AND SE2.E2_HIST LIKE '%" + cHistComp + "%' "
cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA "

Begin Sequence
	FOLSE2Val(cSql, cAlias, @aLinhas, @nTotal)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar adiantamento-rescisao", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oParams := JsonObject():New()
oParams["baixa_de"]              := cBaixaDe
oParams["baixa_ate"]             := cBaixaAte
oParams["historico_competencia"] := cHistComp

Self:SetResponse(FOLMontaRespostaUmGrupo("adiantamento-rescisao", "11203009", ;
	oParams, "SE2", "E2_VALOR", aLinhas, nTotal))

AEval(aLinhas, {|o| FreeObj(o)})
FreeObj(oParams)

RestArea(aArea)
Return .T.


// =============================================================================
// 4) FGTS - 21102004
// SE2: natureza 00600002, vencto exato, saldo > 0
// =============================================================================
wsmethod GET fgts WSRESTFUL ZFOLPAGAPI
Local aArea      := GetArea()
Local cVencto    := AllTrim(Self:vencto)
Local cSql       := ""
Local cAlias     := GetNextAlias()
Local aLinhas    := {}
Local nTotal     := 0
Local oError     := Nil
Local oParams    := Nil

Self:SetContentType("application/json")

If Empty(cVencto) .Or. Len(cVencto) <> 8
	Self:nStatusCode := 422
	Self:cResponse   := FOLMontaErro("VALIDATION_ERROR", "Parametro vencto e obrigatorio no formato YYYYMMDD", "")
	RestArea(aArea)
Return .T.
EndIf

cSql := FOLSqlSE2Base()
cSql += "   AND SE2.E2_NATUREZ = '00600002' "
cSql += "   AND SE2.E2_VENCTO  = '" + cVencto + "' "
cSql += "   AND SE2.E2_SALDO   > 0 "
cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA "

Begin Sequence
	FOLSE2Val(cSql, cAlias, @aLinhas, @nTotal)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar fgts", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oParams := JsonObject():New()
oParams["vencto"] := cVencto

Self:SetResponse(FOLMontaRespostaUmGrupo("fgts", "21102004", oParams, "SE2", "E2_VALOR", aLinhas, nTotal))

AEval(aLinhas, {|o| FreeObj(o)})
FreeObj(oParams)

RestArea(aArea)
Return .T.


// =============================================================================
// 5) IRRF - 21102007
// SRD: datpgt > X, datarq in (dois meses), PD in (420..424)
// SE2: emissao entre, natureza = 'IRF'
// =============================================================================
wsmethod GET irrf WSRESTFUL ZFOLPAGAPI
Local aArea       := GetArea()
Local cDatpgtMai  := AllTrim(Self:datpgt_maior_que)
Local cDatarqDe   := AllTrim(Self:datarq_de)
Local cDatarqAte  := AllTrim(Self:datarq_ate)
Local cEmissaoDe  := AllTrim(Self:emissao_de)
Local cEmissaoAte := AllTrim(Self:emissao_ate)
Local cSql        := ""
Local cAliasSRD   := GetNextAlias()
Local cAliasSE2   := GetNextAlias()
Local aLinhasSRD  := {}
Local aLinhasSE2  := {}
Local nTotalSRD   := 0
Local nTotalSE2   := 0
Local oError      := Nil
Local oGrupoSE2   := Nil
Local oGrupoSRD   := Nil
Local aGrupos     := {}
Local oResp       := Nil
Local oParams     := Nil

Self:SetContentType("application/json")

If Empty(cDatpgtMai) .Or. Empty(cDatarqDe) .Or. Empty(cDatarqAte) .Or. Empty(cEmissaoDe) .Or. Empty(cEmissaoAte)
	Self:nStatusCode := 422
	Self:cResponse   := FOLMontaErro("VALIDATION_ERROR", ;
		"Parametros datpgt_maior_que, datarq_de, datarq_ate, emissao_de e emissao_ate sao obrigatorios", "")
	RestArea(aArea)
Return .T.
EndIf

// SRD: RD_DATPGT > data E RD_DATARQ dentro do range de competencias informado
cSql := FOLSqlSRDBase()
cSql += "   AND SRD.RD_DATPGT > '" + cDatpgtMai + "' "
cSql += "   AND SRD.RD_DATARQ BETWEEN '" + cDatarqDe + "' AND '" + cDatarqAte + "' "
cSql += "   AND SRD.RD_PD IN ('420','421','422','423','424') "
cSql += " ORDER BY SRD.RD_MAT, SRD.RD_PD "

Begin Sequence
	FOLSRDVal(cSql, cAliasSRD, @aLinhasSRD, @nTotalSRD)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar irrf (SRD)", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

// SE2: natureza fixa 'IRF'
cSql := FOLSqlSE2Base()
cSql += "   AND SE2.E2_NATUREZ = 'IRF' "
cSql += "   AND SE2.E2_EMISSAO BETWEEN '" + cEmissaoDe + "' AND '" + cEmissaoAte + "' "
cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA "

Begin Sequence
	FOLSE2Val(cSql, cAliasSE2, @aLinhasSE2, @nTotalSE2)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar irrf (SE2)", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oGrupoSRD := JsonObject():New()
oGrupoSRD["fonte"]       := "SRD"
oGrupoSRD["campo_valor"] := "RD_VALOR"
oGrupoSRD["total"]       := nTotalSRD
oGrupoSRD["linhas"]      := aLinhasSRD

oGrupoSE2 := JsonObject():New()
oGrupoSE2["fonte"]       := "SE2"
oGrupoSE2["campo_valor"] := "E2_VALOR"
oGrupoSE2["total"]       := nTotalSE2
oGrupoSE2["linhas"]      := aLinhasSE2

aAdd(aGrupos, oGrupoSRD)
aAdd(aGrupos, oGrupoSE2)

oParams := JsonObject():New()
oParams["datpgt_maior_que"] := cDatpgtMai
oParams["datarq_de"]        := cDatarqDe
oParams["datarq_ate"]       := cDatarqAte
oParams["emissao_de"]       := cEmissaoDe
oParams["emissao_ate"]      := cEmissaoAte

oResp := JsonObject():New()
oResp["situacao"]        := "irrf"
oResp["conta_contabil"]  := "21102007"
oResp["parametros"]      := oParams
oResp["grupos"]          := aGrupos
oResp["total_geral"]     := nTotalSRD + nTotalSE2
oResp["total_registros"] := Len(aLinhasSRD) + Len(aLinhasSE2)

Self:SetResponse(oResp:ToJson())
FreeObj(oResp)
FreeObj(oGrupoSE2)
FreeObj(oGrupoSRD)
FreeObj(oParams)
AEval(aLinhasSE2, {|o| FreeObj(o)})
AEval(aLinhasSRD, {|o| FreeObj(o)})

RestArea(aArea)
Return .T.


// =============================================================================
// 6) INSS - 21102010
// SE2: natureza in (3 valores), vencto exato, saldo > 0
// =============================================================================
wsmethod GET inss WSRESTFUL ZFOLPAGAPI
Local aArea      := GetArea()
Local cVencto    := AllTrim(Self:vencto)
Local cSql       := ""
Local cAlias     := GetNextAlias()
Local aLinhas    := {}
Local nTotal     := 0
Local oError     := Nil
Local oParams    := Nil

Self:SetContentType("application/json")

If Empty(cVencto) .Or. Len(cVencto) <> 8
	Self:nStatusCode := 422
	Self:cResponse   := FOLMontaErro("VALIDATION_ERROR", "Parametro vencto e obrigatorio no formato YYYYMMDD", "")
	RestArea(aArea)
Return .T.
EndIf

cSql := FOLSqlSE2Base()
cSql += "   AND SE2.E2_NATUREZ IN ('00600003','00600020','00600021') "
cSql += "   AND SE2.E2_VENCTO  = '" + cVencto + "' "
cSql += "   AND SE2.E2_SALDO   > 0 "
cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA "

Begin Sequence
	FOLSE2Val(cSql, cAlias, @aLinhas, @nTotal)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar inss", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oParams := JsonObject():New()
oParams["vencto"] := cVencto

Self:SetResponse(FOLMontaRespostaUmGrupo("inss", "21102010", oParams, "SE2", "E2_VALOR", aLinhas, nTotal))

AEval(aLinhas, {|o| FreeObj(o)})
FreeObj(oParams)

RestArea(aArea)
Return .T.


// =============================================================================
// 7) FGTS RESCISORIO - 21102013
// SE2: natureza 00600001, (baixa entre OU vazia), historico LIKE %MMAAAA%
// =============================================================================
wsmethod GET fgtsRescisorio WSRESTFUL ZFOLPAGAPI
Local aArea      := GetArea()
Local cBaixaDe   := AllTrim(Self:baixa_de)
Local cBaixaAte  := AllTrim(Self:baixa_ate)
Local cHistComp  := AllTrim(Self:historico_competencia)
Local cSql       := ""
Local cAlias     := GetNextAlias()
Local aLinhas    := {}
Local nTotal     := 0
Local oError     := Nil
Local oParams    := Nil

Self:SetContentType("application/json")

If Empty(cBaixaDe) .Or. Empty(cBaixaAte) .Or. Empty(cHistComp)
	Self:nStatusCode := 422
	Self:cResponse   := FOLMontaErro("VALIDATION_ERROR", "Parametros baixa_de, baixa_ate e historico_competencia sao obrigatorios", "")
	RestArea(aArea)
Return .T.
EndIf

cSql := FOLSqlSE2Base()
cSql += "   AND SE2.E2_NATUREZ = '00600001' "
cSql += "   AND (SE2.E2_BAIXA BETWEEN '" + cBaixaDe + "' AND '" + cBaixaAte + "' OR SE2.E2_BAIXA = ' ') "
cSql += "   AND SE2.E2_HIST LIKE '%" + cHistComp + "%' "
cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA "

Begin Sequence
	FOLSE2Val(cSql, cAlias, @aLinhas, @nTotal)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar fgts-rescisorio", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oParams := JsonObject():New()
oParams["baixa_de"]              := cBaixaDe
oParams["baixa_ate"]             := cBaixaAte
oParams["historico_competencia"] := cHistComp

Self:SetResponse(FOLMontaRespostaUmGrupo("fgts-rescisorio", "21102013", ;
	oParams, "SE2", "E2_VALOR", aLinhas, nTotal))

AEval(aLinhas, {|o| FreeObj(o)})
FreeObj(oParams)

RestArea(aArea)
Return .T.


// =============================================================================
// 8) CONTRIBUICAO ASSISTENCIAL - 21102015
// SE2: natureza 00600012, vencto exato (sem filtro de saldo)
// =============================================================================
wsmethod GET contribAssist WSRESTFUL ZFOLPAGAPI
Local aArea      := GetArea()
Local cVencto    := AllTrim(Self:vencto)
Local cSql       := ""
Local cAlias     := GetNextAlias()
Local aLinhas    := {}
Local nTotal     := 0
Local oError     := Nil
Local oParams    := Nil

Self:SetContentType("application/json")

If Empty(cVencto) .Or. Len(cVencto) <> 8
	Self:nStatusCode := 422
	Self:cResponse   := FOLMontaErro("VALIDATION_ERROR", "Parametro vencto e obrigatorio no formato YYYYMMDD", "")
	RestArea(aArea)
Return .T.
EndIf

cSql := FOLSqlSE2Base()
cSql += "   AND SE2.E2_NATUREZ = '00600012' "
cSql += "   AND SE2.E2_VENCTO  = '" + cVencto + "' "
cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA "

Begin Sequence
	FOLSE2Val(cSql, cAlias, @aLinhas, @nTotal)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar contribuicao-assistencial", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oParams := JsonObject():New()
oParams["vencto"] := cVencto

Self:SetResponse(FOLMontaRespostaUmGrupo("contribuicao-assistencial", "21102015", oParams, "SE2", "E2_VALOR", aLinhas, nTotal))

AEval(aLinhas, {|o| FreeObj(o)})
FreeObj(oParams)

RestArea(aArea)
Return .T.


// =============================================================================
// 9) SALARIO - 21103001
// SE2: natureza 00600000, baixa entre (sem OR vazia)
// =============================================================================
wsmethod GET salario WSRESTFUL ZFOLPAGAPI
Local aArea      := GetArea()
Local cBaixaDe   := AllTrim(Self:baixa_de)
Local cBaixaAte  := AllTrim(Self:baixa_ate)
Local cSql       := ""
Local cAlias     := GetNextAlias()
Local aLinhas    := {}
Local nTotal     := 0
Local oError     := Nil
Local oParams    := Nil

Self:SetContentType("application/json")

If Empty(cBaixaDe) .Or. Empty(cBaixaAte)
	Self:nStatusCode := 422
	Self:cResponse   := FOLMontaErro("VALIDATION_ERROR", "Parametros baixa_de e baixa_ate sao obrigatorios", "")
	RestArea(aArea)
Return .T.
EndIf

cSql := FOLSqlSE2Base()
cSql += "   AND SE2.E2_NATUREZ = '00600000' "
cSql += "   AND SE2.E2_BAIXA BETWEEN '" + cBaixaDe + "' AND '" + cBaixaAte + "' "
cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA "

Begin Sequence
	FOLSE2Val(cSql, cAlias, @aLinhas, @nTotal)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar salario", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oParams := JsonObject():New()
oParams["baixa_de"]  := cBaixaDe
oParams["baixa_ate"] := cBaixaAte

Self:SetResponse(FOLMontaRespostaUmGrupo("salario", "21103001", oParams, "SE2", "E2_VALOR", aLinhas, nTotal))

AEval(aLinhas, {|o| FreeObj(o)})
FreeObj(oParams)

RestArea(aArea)
Return .T.


// =============================================================================
// 10) FERIAS A PAGAR - 21103009
// SRD: datarq = AAAAMM, roteiro <> ADI/PLR, PD in (lista sem 406/667), sem inverter sinal
// =============================================================================
wsmethod GET feriasAPagar WSRESTFUL ZFOLPAGAPI
Local aArea      := GetArea()
Local cDatarq    := AllTrim(Self:datarq)
Local cSql       := ""
Local cAlias     := GetNextAlias()
Local aLinhas    := {}
Local nTotal     := 0
Local oError     := Nil
Local oParams    := Nil

Self:SetContentType("application/json")

If Empty(cDatarq)
	Self:nStatusCode := 422
	Self:cResponse   := FOLMontaErro("VALIDATION_ERROR", "Parametro datarq e obrigatorio no formato AAAAMM", "")
	RestArea(aArea)
Return .T.
EndIf

cSql := FOLSqlSRDBase()
cSql += "   AND SRD.RD_DATARQ = '" + cDatarq + "' "
cSql += "   AND SRD.RD_ROTEIR NOT IN ('ADI','PLR') "
cSql += "   AND SRD.RD_PD IN ('039','043','047','067','076','125','126','150','151','152','153','154','155','156','319') "
cSql += " ORDER BY SRD.RD_MAT, SRD.RD_PD "

Begin Sequence
	FOLSRDVal(cSql, cAlias, @aLinhas, @nTotal)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar ferias-a-pagar", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oParams := JsonObject():New()
oParams["datarq"] := cDatarq

Self:SetResponse(FOLMontaRespostaUmGrupo("ferias-a-pagar", "21103009", oParams, "SRD", "RD_VALOR", aLinhas, nTotal))

AEval(aLinhas, {|o| FreeObj(o)})
FreeObj(oParams)

RestArea(aArea)
Return .T.


// =============================================================================
// 11) PENSAO ALIMENTICIA - 21103011
// SE2: natureza 00600017, (baixa entre OU vazia)
// =============================================================================
wsmethod GET pensaoAlimenticia WSRESTFUL ZFOLPAGAPI
Local aArea      := GetArea()
Local cBaixaDe   := AllTrim(Self:baixa_de)
Local cBaixaAte  := AllTrim(Self:baixa_ate)
Local cSql       := ""
Local cAlias     := GetNextAlias()
Local aLinhas    := {}
Local nTotal     := 0
Local oError     := Nil
Local oParams    := Nil

Self:SetContentType("application/json")

If Empty(cBaixaDe) .Or. Empty(cBaixaAte)
	Self:nStatusCode := 422
	Self:cResponse   := FOLMontaErro("VALIDATION_ERROR", "Parametros baixa_de e baixa_ate sao obrigatorios", "")
	RestArea(aArea)
Return .T.
EndIf

cSql := FOLSqlSE2Base()
cSql += "   AND SE2.E2_NATUREZ = '00600017' "
cSql += "   AND (SE2.E2_BAIXA BETWEEN '" + cBaixaDe + "' AND '" + cBaixaAte + "' OR SE2.E2_BAIXA = ' ') "
cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA "

Begin Sequence
	FOLSE2Val(cSql, cAlias, @aLinhas, @nTotal)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar pensao-alimenticia", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oParams := JsonObject():New()
oParams["baixa_de"]  := cBaixaDe
oParams["baixa_ate"] := cBaixaAte

Self:SetResponse(FOLMontaRespostaUmGrupo("pensao-alimenticia", "21103011", oParams, "SE2", "E2_VALOR", aLinhas, nTotal))

AEval(aLinhas, {|o| FreeObj(o)})
FreeObj(oParams)

RestArea(aArea)
Return .T.


// =============================================================================
// 12) PLR - 21103013
// SE2: natureza 00600019, sem filtro de tela nenhum - soma E2_SALDO (nao E2_VALOR)
// =============================================================================
wsmethod GET plr WSRESTFUL ZFOLPAGAPI
Local aArea      := GetArea()
Local cSql       := ""
Local cAlias     := GetNextAlias()
Local aLinhas    := {}
Local nTotal     := 0
Local oError     := Nil
Local oParams    := Nil

Self:SetContentType("application/json")

cSql := FOLSqlSE2Base()
cSql += "   AND SE2.E2_NATUREZ = '00600019' "
cSql += " ORDER BY SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NUM, SE2.E2_PARCELA "

Begin Sequence
	FOLSE2Sdo(cSql, cAlias, @aLinhas, @nTotal)
Recover Using oError
	Self:nStatusCode := 500
	Self:cResponse   := FOLMontaErro("INTERNAL_ERROR", "Erro ao consultar plr", oError:Description)
	RestArea(aArea)
Return .T.
End Sequence

oParams := JsonObject():New()

Self:SetResponse(FOLMontaRespostaUmGrupo("plr", "21103013", oParams, "SE2", "E2_SALDO", aLinhas, nTotal))

AEval(aLinhas, {|o| FreeObj(o)})
FreeObj(oParams)

RestArea(aArea)
Return .T.


// =============================================================================
// Static Function FOLSqlSE2Base
// SELECT + FROM + WHERE inicial comuns a todas as situacoes baseadas em SE2.
// Tabela e filial SEMPRE dinamicas (RetSqlName/xFilial) - nunca hardcoded,
// pois a mesma API roda para Rancheiro e Ander.
// =============================================================================
Static Function FOLSqlSE2Base()
Local cSql := ""

cSql := " SELECT SE2.E2_FILIAL, SE2.E2_PREFIXO, SE2.E2_NUM, SE2.E2_PARCELA, SE2.E2_TIPO, "
cSql += "        SE2.E2_FORNECE, SE2.E2_LOJA, SE2.E2_NOMFOR, SE2.E2_NATUREZ, "
cSql += "        SE2.E2_EMISSAO, SE2.E2_VENCTO, SE2.E2_VENCREA, SE2.E2_BAIXA, "
cSql += "        SE2.E2_VALOR, SE2.E2_SALDO, SE2.E2_HIST "
cSql += " FROM " + RetSqlName("SE2") + " SE2 "
cSql += " WHERE SE2.D_E_L_E_T_ = ' ' "
cSql += "   AND SE2.E2_FILIAL  = '" + xFilial("SE2") + "' "

Return cSql


// =============================================================================
// Static Function FOLSqlSRDBase
// SELECT + FROM + WHERE inicial comuns a todas as situacoes baseadas em SRD
// (ficha financeira de folha/RH). Tabela e filial dinamicas.
// =============================================================================
Static Function FOLSqlSRDBase()
Local cSql := ""

cSql := " SELECT SRD.RD_FILIAL, SRD.RD_MAT, SRD.RD_PD, SRD.RD_ROTEIR, "
cSql += "        SRD.RD_DATARQ, SRD.RD_DATPGT, SRD.RD_VALOR "
cSql += " FROM " + RetSqlName("SRD") + " SRD "
cSql += " WHERE SRD.D_E_L_E_T_ = ' ' "
cSql += "   AND SRD.RD_FILIAL  = '" + xFilial("SRD") + "' "

Return cSql


// =============================================================================
// Static Function FOLSE2Val
// Executa SQL sobre SE2 e preenche aLinhas (JsonObject por linha) e nTotal
// (soma de E2_VALOR), por referencia.
// =============================================================================
Static Function FOLSE2Val(cSql, cAlias, aLinhas, nTotal)
Local oItem := Nil

dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .F., .T.)
TCSetField(cAlias, "E2_EMISSAO", "D", 8, 0)
TCSetField(cAlias, "E2_VENCTO",  "D", 8, 0)
TCSetField(cAlias, "E2_VENCREA", "D", 8, 0)
TCSetField(cAlias, "E2_BAIXA",   "D", 8, 0)
TCSetField(cAlias, "E2_VALOR",   "N", 16, 2)
TCSetField(cAlias, "E2_SALDO",   "N", 16, 2)

(cAlias)->(DbGoTop())
While !(cAlias)->(Eof())
	oItem := JsonObject():New()
	oItem["filial"]     := AllTrim((cAlias)->E2_FILIAL)
	oItem["prefixo"]    := AllTrim((cAlias)->E2_PREFIXO)
	oItem["numero"]     := AllTrim((cAlias)->E2_NUM)
	oItem["parcela"]    := AllTrim((cAlias)->E2_PARCELA)
	oItem["tipo"]       := AllTrim((cAlias)->E2_TIPO)
	oItem["fornecedor"] := AllTrim((cAlias)->E2_FORNECE)
	oItem["loja"]       := AllTrim((cAlias)->E2_LOJA)
	oItem["nome_fornecedor"] := AllTrim((cAlias)->E2_NOMFOR)
	oItem["natureza"]   := AllTrim((cAlias)->E2_NATUREZ)
	oItem["emissao"]    := DToS((cAlias)->E2_EMISSAO)
	oItem["vencto"]     := DToS((cAlias)->E2_VENCTO)
	oItem["vencto_real"]:= DToS((cAlias)->E2_VENCREA)
	oItem["baixa"]      := DToS((cAlias)->E2_BAIXA)
	oItem["valor"]      := (cAlias)->E2_VALOR
	oItem["saldo"]      := (cAlias)->E2_SALDO
	oItem["historico"]  := AllTrim((cAlias)->E2_HIST)

	aAdd(aLinhas, oItem)
	nTotal += (cAlias)->E2_VALOR

	(cAlias)->(DbSkip())
EndDo

(cAlias)->(DbCloseArea())

Return Nil


// =============================================================================
// Static Function FOLSE2Sdo
// Igual a FOLSE2Val, mas soma E2_SALDO em vez de E2_VALOR (usado pelo PLR,
// unica situacao cujo SQL original agrega por saldo).
// =============================================================================
Static Function FOLSE2Sdo(cSql, cAlias, aLinhas, nTotal)
Local oItem := Nil

dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .F., .T.)
TCSetField(cAlias, "E2_EMISSAO", "D", 8, 0)
TCSetField(cAlias, "E2_VENCTO",  "D", 8, 0)
TCSetField(cAlias, "E2_VENCREA", "D", 8, 0)
TCSetField(cAlias, "E2_BAIXA",   "D", 8, 0)
TCSetField(cAlias, "E2_VALOR",   "N", 16, 2)
TCSetField(cAlias, "E2_SALDO",   "N", 16, 2)

(cAlias)->(DbGoTop())
While !(cAlias)->(Eof())
	oItem := JsonObject():New()
	oItem["filial"]     := AllTrim((cAlias)->E2_FILIAL)
	oItem["prefixo"]    := AllTrim((cAlias)->E2_PREFIXO)
	oItem["numero"]     := AllTrim((cAlias)->E2_NUM)
	oItem["parcela"]    := AllTrim((cAlias)->E2_PARCELA)
	oItem["tipo"]       := AllTrim((cAlias)->E2_TIPO)
	oItem["fornecedor"] := AllTrim((cAlias)->E2_FORNECE)
	oItem["loja"]       := AllTrim((cAlias)->E2_LOJA)
	oItem["nome_fornecedor"] := AllTrim((cAlias)->E2_NOMFOR)
	oItem["natureza"]   := AllTrim((cAlias)->E2_NATUREZ)
	oItem["emissao"]    := DToS((cAlias)->E2_EMISSAO)
	oItem["vencto"]     := DToS((cAlias)->E2_VENCTO)
	oItem["vencto_real"]:= DToS((cAlias)->E2_VENCREA)
	oItem["baixa"]      := DToS((cAlias)->E2_BAIXA)
	oItem["valor"]      := (cAlias)->E2_VALOR
	oItem["saldo"]      := (cAlias)->E2_SALDO
	oItem["historico"]  := AllTrim((cAlias)->E2_HIST)

	aAdd(aLinhas, oItem)
	nTotal += (cAlias)->E2_SALDO

	(cAlias)->(DbSkip())
EndDo

(cAlias)->(DbCloseArea())

Return Nil


// =============================================================================
// Static Function FOLSRDVal
// Executa SQL sobre SRD e preenche aLinhas/nTotal (soma simples de RD_VALOR,
// sem inversao de sinal).
// =============================================================================
Static Function FOLSRDVal(cSql, cAlias, aLinhas, nTotal)
Local oItem := Nil

dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .F., .T.)
TCSetField(cAlias, "RD_DATPGT", "D", 8, 0)
TCSetField(cAlias, "RD_VALOR",  "N", 16, 2)

(cAlias)->(DbGoTop())
While !(cAlias)->(Eof())
	oItem := JsonObject():New()
	oItem["filial"]   := AllTrim((cAlias)->RD_FILIAL)
	oItem["matricula"]:= AllTrim((cAlias)->RD_MAT)
	oItem["pd"]       := AllTrim((cAlias)->RD_PD)
	oItem["roteiro"]  := AllTrim((cAlias)->RD_ROTEIR)
	oItem["datarq"]   := AllTrim((cAlias)->RD_DATARQ)
	oItem["datpgt"]   := DToS((cAlias)->RD_DATPGT)
	oItem["valor"]    := (cAlias)->RD_VALOR

	aAdd(aLinhas, oItem)
	nTotal += (cAlias)->RD_VALOR

	(cAlias)->(DbSkip())
EndDo

(cAlias)->(DbCloseArea())

Return Nil


// =============================================================================
// Static Function FOLSRDSgn
// Igual a FOLSRDVal, mas inverte o sinal de RD_VALOR quando RD_PD >= '406'
// (regra especifica de adiantamento-ferias, replicando o CASE WHEN do SQL
// original do analista).
// =============================================================================
Static Function FOLSRDSgn(cSql, cAlias, aLinhas, nTotal)
Local oItem  := Nil
Local nValor := 0

dbUseArea(.T., "TOPCONN", TCGenQry(,, cSql), cAlias, .F., .T.)
TCSetField(cAlias, "RD_DATPGT", "D", 8, 0)
TCSetField(cAlias, "RD_VALOR",  "N", 16, 2)

(cAlias)->(DbGoTop())
While !(cAlias)->(Eof())
	nValor := (cAlias)->RD_VALOR
	If (cAlias)->RD_PD >= "406"
		nValor := nValor * -1
	EndIf

	oItem := JsonObject():New()
	oItem["filial"]        := AllTrim((cAlias)->RD_FILIAL)
	oItem["matricula"]     := AllTrim((cAlias)->RD_MAT)
	oItem["pd"]            := AllTrim((cAlias)->RD_PD)
	oItem["roteiro"]       := AllTrim((cAlias)->RD_ROTEIR)
	oItem["datarq"]        := AllTrim((cAlias)->RD_DATARQ)
	oItem["datpgt"]        := DToS((cAlias)->RD_DATPGT)
	oItem["valor_original"]:= (cAlias)->RD_VALOR
	oItem["valor"]         := nValor

	aAdd(aLinhas, oItem)
	nTotal += nValor

	(cAlias)->(DbSkip())
EndDo

(cAlias)->(DbCloseArea())

Return Nil


// =============================================================================
// Static Function FOLMontaRespostaUmGrupo
// Monta o JSON de resposta para situacoes de fonte unica (10 das 12).
// =============================================================================
Static Function FOLMontaRespostaUmGrupo(cSituacao, cContaContabil, oParams, cFonte, cCampoValor, aLinhas, nTotal)
Local oResp   := JsonObject():New()
Local oGrupo  := JsonObject():New()
Local aGrupos := {}
Local cJson   := ""

oGrupo["fonte"]       := cFonte
oGrupo["campo_valor"] := cCampoValor
oGrupo["total"]       := nTotal
oGrupo["linhas"]      := aLinhas
aAdd(aGrupos, oGrupo)

oResp["situacao"]        := cSituacao
oResp["conta_contabil"]  := cContaContabil
oResp["parametros"]      := oParams
oResp["grupos"]          := aGrupos
oResp["total_geral"]     := nTotal
oResp["total_registros"] := Len(aLinhas)

cJson := oResp:ToJson()
FreeObj(oResp)
FreeObj(oGrupo)

Return cJson


// =============================================================================
// Static Function FOLMontaErro
// =============================================================================
Static Function FOLMontaErro(cCode, cMessage, cDetails)
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
