#Include "Protheus.ch"
#Include "restful.ch"
#Include "APWEBSRV.ch"
#Include "MATR900.ch"

wsrestful ZMATR900API description "MATR900 - Kardex Fisico-Financeiro"
    wsdata page                 as string
    wsdata pageSize             as string
    wsdata data_ini             as string
    wsdata data_fim             as string
    wsdata produto_de           as string
    wsdata produto_ate          as string
    wsdata tipo_de              as string
    wsdata tipo_ate             as string
    wsdata grupo_de             as string
    wsdata grupo_ate            as string
    wsdata armazem              as string
    wsdata documento_por        as string
    wsdata moeda                as string
    wsdata ordem                as string
    wsdata lista_sem_movimento  as string
    wsdata considera_filiais    as string
    wsdata tipo_custo           as string
    wsmethod GET getKardex description "Kardex Fisico-Financeiro" wssyntax "/api/v1/matr900" PATH "/api/v1/matr900"
EndwsRestFul

wsmethod GET getKardex WSRESTFUL ZMATR900API
Local aArea := GetArea()
Local oResp := JsonObject():New()
Local oParams := JsonObject():New()
Local aAllLinhas := {}
Local aLinhas := {}
Local oLinha := Nil
Local cAliasTop := GetNextAlias()
Local oError := Nil
Local nPage := Max(1, Val(AllTrim(Self:page)))
Local nPageSize := Val(AllTrim(Self:pageSize))
Local cDataIni := AllTrim(Self:data_ini)
Local cDataFim := AllTrim(Self:data_fim)
Local cProdutoDe := IIf(Empty(AllTrim(Self:produto_de)), Space(TamSX3("B1_COD")[1]), AllTrim(Self:produto_de))
Local cProdutoAte := IIf(Empty(AllTrim(Self:produto_ate)), Repl("Z", TamSX3("B1_COD")[1]), AllTrim(Self:produto_ate))
Local cTipoDe := IIf(Empty(AllTrim(Self:tipo_de)), Space(TamSX3("B1_TIPO")[1]), AllTrim(Self:tipo_de))
Local cTipoAte := IIf(Empty(AllTrim(Self:tipo_ate)), Repl("Z", TamSX3("B1_TIPO")[1]), AllTrim(Self:tipo_ate))
Local cGrupoDe := IIf(Empty(AllTrim(Self:grupo_de)), Space(TamSX3("B1_GRUPO")[1]), AllTrim(Self:grupo_de))
Local cGrupoAte := IIf(Empty(AllTrim(Self:grupo_ate)), Repl("Z", TamSX3("B1_GRUPO")[1]), AllTrim(Self:grupo_ate))
// armazem: vazio = de branco ate ZZZ (todos); informado = igualdade no armazem especifico
Local cLocalInf := IIf(Empty(AllTrim(Self:armazem)), Space(TamSX3("D1_LOCAL")[1]), AllTrim(Self:armazem))
Local cLocalSup := IIf(Empty(AllTrim(Self:armazem)), Repl("Z", TamSX3("D1_LOCAL")[1]), AllTrim(Self:armazem))
Local cLocal    := AllTrim(Self:armazem)  // para oParams e CalcEst quando informado
Local cDocPor := Upper(IIf(Empty(AllTrim(Self:documento_por)), "D", AllTrim(Self:documento_por)))
Local nMoeda := Max(1, Val(IIf(Empty(AllTrim(Self:moeda)), "1", AllTrim(Self:moeda))))
Local nOrdem := Max(1, Val(IIf(Empty(AllTrim(Self:ordem)), "1", AllTrim(Self:ordem))))
Local cSemMov := IIf(Empty(AllTrim(Self:lista_sem_movimento)), "2", AllTrim(Self:lista_sem_movimento))
// considera_filiais: "1"=filial corrente  "2"=todas as filiais (logica original do MATR900)
Local lTodasFil := (AllTrim(Self:considera_filiais) == "2")
Local cTipoCusto := IIf(Empty(AllTrim(Self:tipo_custo)), "1", AllTrim(Self:tipo_custo))
Local dDataIni := CToD("")
Local dDataFim := CToD("")
Local nTotalReg := 0
Local nTotalPages := 1
Local nOffset := 0
Local nRecAtual := 0
Local lHasMore := .F.
Local cSelectD1 := ""
Local cSelectD2 := ""
Local cSelectD3 := ""
Local cWhereD1 := ""
Local cWhereD2 := ""
Local cWhereD3 := ""
Local cWhereD1C := ""
Local cWhereD2C := ""
Local cWhereD3C := ""
Local cWhereB1A := ""
Local cWhereB1C := ""
Local cOrder := ""
Local lCusRep := SuperGetMv("MV_CUSREP", .F., .F.) .And. MA330AvRep() .And. cTipoCusto == "2"
Local cProdImp := GetMV("MV_PRODIMP")
Local cLogPrefix := "[ZMATR900] "

Self:SetContentType("application/json")

// LOG: entrada da requisicao
ConOut(cLogPrefix + "Requisicao recebida | data_ini=" + cDataIni + " data_fim=" + cDataFim + ;
    " page=" + cValToChar(nPage) + " pageSize=" + cValToChar(nPageSize) + ;
    " produto_de=[" + cProdutoDe + "] produto_ate=[" + cProdutoAte + "]" + ;
    " tipo_de=[" + cTipoDe + "] tipo_ate=[" + cTipoAte + "]" + ;
    " grupo_de=[" + cGrupoDe + "] grupo_ate=[" + cGrupoAte + "]" + ;
    " armazem=[" + IIf(Empty(cLocal), "TODOS", cLocal) + "]" + ;
    " local_de=[" + cLocalInf + "] local_ate=[" + cLocalSup + "]" + ;
    " doc_por=" + cDocPor + " moeda=" + cValToChar(nMoeda) + ;
    " todas_filiais=" + IIf(lTodasFil, "S", "N") + " tipo_custo=" + cTipoCusto)

If Len(cDataIni) <> 8 .Or. Len(cDataFim) <> 8
    ConOut(cLogPrefix + "ERRO VALIDACAO: data_ini ou data_fim invalido | data_ini=" + cDataIni + " data_fim=" + cDataFim)
    Self:SetResponse(MTR900ApiErro("VALIDATION_ERROR", "Informe data_ini e data_fim no formato YYYYMMDD", ""))
    FreeObj(oResp)
    FreeObj(oParams)
    RestArea(aArea)
Return .T.
EndIf

dDataIni := StoD(cDataIni)
dDataFim := StoD(cDataFim)
If Empty(dDataIni) .Or. Empty(dDataFim) .Or. dDataIni > dDataFim
    ConOut(cLogPrefix + "ERRO VALIDACAO: periodo invalido | dDataIni=" + DToC(dDataIni) + " dDataFim=" + DToC(dDataFim))
    Self:SetResponse(MTR900ApiErro("VALIDATION_ERROR", "Periodo invalido para o Kardex", cDataIni + "-" + cDataFim))
    FreeObj(oResp)
    FreeObj(oParams)
    RestArea(aArea)
Return .T.
EndIf

nPageSize := IIf(nPageSize <= 0 .Or. nPageSize > 5000, 5000, nPageSize)
nOffset := (nPage - 1) * nPageSize

// mv_par usados internamente pelo CalcEst e funcoes do MATR900
// Precisam estar setados antes do BeginSql e do loop de registros
mv_par01 := dDataIni   // data inicio como tipo D
mv_par02 := dDataFim   // data fim como tipo D
mv_par03 := cProdutoDe
mv_par04 := cProdutoAte
mv_par05 := cTipoDe
mv_par06 := cTipoAte
mv_par07 := cGrupoDe
mv_par08 := cGrupoAte
mv_par09 := cDocPor
mv_par10 := nMoeda
mv_par11 := nOrdem
mv_par12 := cSemMov
mv_par13 := cLocalInf
mv_par14 := cLocalSup
mv_par15 := cTipoCusto

// LOG: parametros normalizados
ConOut(cLogPrefix + "Parametros normalizados | dDataIni=" + DToC(dDataIni) + " dDataFim=" + DToC(dDataFim) + ;
    " pageSize=" + cValToChar(nPageSize) + " lCusRep=" + IIf(lCusRep, "S", "N") + ;
    " cProdImp=[" + cProdImp + "]")

If lCusRep
    cSelectD1 := "% D1_CUSRP" + Str(nMoeda,1,0) + " CUSTO,%"
    cSelectD2 := "% D2_CUSRP" + Str(nMoeda,1,0) + " CUSTO,%"
    cSelectD3 := "% D3_CUSRP" + Str(nMoeda,1,0) + " CUSTO,%"
Else
    cSelectD1 := "% D1_CUSTO" + IIf(nMoeda > 1, Str(nMoeda,1,0), "") + " CUSTO,%"
    cSelectD2 := "% D2_CUSTO" + Str(nMoeda,1,0) + " CUSTO,%"
    cSelectD3 := "% D3_CUSTO" + Str(nMoeda,1,0) + " CUSTO,%"
EndIf

cWhereD1 := "%AND D1_LOCAL >= '" + cLocalInf + "' AND D1_LOCAL <= '" + cLocalSup + "' AND%"
cWhereD2 := "%AND D2_LOCAL >= '" + cLocalInf + "' AND D2_LOCAL <= '" + cLocalSup + "' AND%"
cWhereD3 := "% D3_LOCAL >= '" + cLocalInf + "' AND D3_LOCAL <= '" + cLocalSup + "' AND"
cWhereD3 += " SB1.B1_COD >= '" + cProdutoDe + "' AND SB1.B1_COD <= '" + cProdutoAte + "' AND"
cWhereD3 += " SB1.B1_FILIAL = '" + xFilial("SB1") + "' AND SB1.B1_TIPO >= '" + cTipoDe + "' AND SB1.B1_TIPO <= '" + cTipoAte + "' AND"
cWhereD3 += " SB1.B1_GRUPO >= '" + cGrupoDe + "' AND SB1.B1_GRUPO <= '" + cGrupoAte + "' AND SB1.B1_COD <> '" + cProdImp + "' AND SB1.D_E_L_E_T_=' ' AND%"
cWhereD1C := IIf(lTodasFil, "% SF4.F4_FILIAL = '" + xFilial("SF4") + "' AND%", "% D1_FILIAL ='" + xFilial("SD1") + "' AND SF4.F4_FILIAL = '" + xFilial("SF4") + "' AND%")
cWhereD2C := IIf(lTodasFil, "% SF4.F4_FILIAL = '" + xFilial("SF4") + "' AND%", "% D2_FILIAL ='" + xFilial("SD2") + "' AND SF4.F4_FILIAL = '" + xFilial("SF4") + "' AND%")
cWhereD3C := IIf(lTodasFil, "%1=1 AND %", "% D3_FILIAL ='" + xFilial("SD3") + "' AND %")
cWhereB1A := "% AND SB1.B1_COD >= '" + cProdutoDe + "' AND SB1.B1_COD <= '" + cProdutoAte + "'%"
cWhereB1C := "% SB1.B1_FILIAL = '" + xFilial("SB1") + "' AND SB1.B1_TIPO >= '" + cTipoDe + "' AND SB1.B1_TIPO <= '" + cTipoAte + "' AND SB1.B1_GRUPO >= '" + cGrupoDe + "' AND SB1.B1_GRUPO <= '" + cGrupoAte + "' AND SB1.B1_COD <> '" + cProdImp + "' AND SB1.D_E_L_E_T_=' '%"

cOrder := "%"
If nOrdem == 1
    cOrder += "2,"
Else
    cOrder += "3,2,"
EndIf
cOrder += "9,12%"

// LOG: antes de executar o SQL
ConOut(cLogPrefix + "Executando BeginSql | alias=" + cAliasTop + ;
    " filial_SB1=" + xFilial("SB1") + " filial_SD1=" + xFilial("SD1") + ;
    " filial_SD2=" + xFilial("SD2") + " filial_SD3=" + xFilial("SD3") + ;
    " filial_SF4=" + xFilial("SF4"))

BeginSql Alias cAliasTop
    SELECT  'SD1' ARQ,
            SB1.B1_COD PRODUTO,
            SB1.B1_TIPO TIPO,
            SB1.B1_UM,
            SB1.B1_GRUPO,
            SB1.B1_DESC,
            SB1.B1_POSIPI,
            D1_SEQCALC SEQCALC,
            D1_DTDIGIT DTDIGIT,
            D1_TES TES,
            D1_CF CF,
            D1_NUMSEQ SEQUENCIA,
            D1_DOC DOCUMENTO,
            D1_SERIE SERIE,
            D1_QUANT QUANTIDADE,
            D1_QTSEGUM QUANT2UM,
            D1_LOCAL ARMAZEM,
            D1_FORNECE PARCEIRO,
            D1_LOJA LOJA,
            D1_TIPO TIPONF,
            %Exp:cSelectD1%
            D1_LOTECTL LOTE,
            SD1.R_E_C_N_O_ NRECNO,
            SD1.D1_LOCAL ARMLOC
    FROM %table:SB1% SB1, %table:SD1% SD1, %table:SF4% SF4
    WHERE SB1.B1_COD = SD1.D1_COD AND %Exp:cWhereD1C%
          SD1.D1_TES = SF4.F4_CODIGO AND SF4.F4_ESTOQUE = 'S' AND
          SD1.D1_DTDIGIT >= %Exp:dDataIni% AND SD1.D1_DTDIGIT <= %Exp:dDataFim% AND SD1.D1_ORIGLAN <> 'LF'
          %Exp:cWhereD1%
          SD1.%NotDel% AND SF4.%NotDel%
          %Exp:cWhereB1A% AND %Exp:cWhereB1C%
    UNION
    SELECT  'SD2',
            SB1.B1_COD,
            SB1.B1_TIPO,
            SB1.B1_UM,
            SB1.B1_GRUPO,
            SB1.B1_DESC,
            SB1.B1_POSIPI,
            D2_SEQCALC,
            D2_EMISSAO,
            D2_TES,
            D2_CF,
            D2_NUMSEQ,
            D2_DOC,
            D2_SERIE,
            D2_QUANT,
            D2_QTSEGUM,
            D2_LOCAL,
            D2_CLIENTE,
            D2_LOJA,
            D2_TIPO,
            %Exp:cSelectD2%
            D2_LOTECTL,
            SD2.R_E_C_N_O_,
            SD2.D2_LOCAL
    FROM %table:SB1% SB1, %table:SD2% SD2, %table:SF4% SF4
    WHERE SB1.B1_COD = SD2.D2_COD AND %Exp:cWhereD2C%
          SD2.D2_TES = SF4.F4_CODIGO AND SF4.F4_ESTOQUE = 'S' AND
          SD2.D2_EMISSAO >= %Exp:dDataIni% AND SD2.D2_EMISSAO <= %Exp:dDataFim% AND SD2.D2_ORIGLAN <> 'LF'
          %Exp:cWhereD2%
          SD2.%NotDel% AND SF4.%NotDel%
          %Exp:cWhereB1A% AND %Exp:cWhereB1C%
    UNION
    SELECT  'SD3',
            SB1.B1_COD,
            SB1.B1_TIPO,
            SB1.B1_UM,
            SB1.B1_GRUPO,
            SB1.B1_DESC,
            SB1.B1_POSIPI,
            D3_SEQCALC,
            D3_EMISSAO,
            D3_TM,
            D3_CF,
            D3_NUMSEQ,
            D3_DOC,
            ' ',
            D3_QUANT,
            D3_QTSEGUM,
            D3_LOCAL,
            D3_CC,
            ' ',
            ' ',
            %Exp:cSelectD3%
            D3_LOTECTL,
            SD3.R_E_C_N_O_,
            SD3.D3_LOCAL
    FROM %table:SB1% SB1, %table:SD3% SD3
    WHERE SB1.B1_COD = SD3.D3_COD AND %Exp:cWhereD3C%
          SD3.D3_EMISSAO >= %Exp:dDataIni% AND SD3.D3_EMISSAO <= %Exp:dDataFim% AND
          %Exp:cWhereD3%
          SD3.%NotDel%
    ORDER BY %Exp:cOrder%
EndSql

Begin Sequence
    DbSelectArea(cAliasTop)
    TcSetField(cAliasTop, "DTDIGIT", "D", TamSx3("D1_DTDIGIT")[1], TamSx3("D1_DTDIGIT")[2])

    // LOG: resultado do SQL
    ConOut(cLogPrefix + "SQL executado | alias=" + cAliasTop + ;
        " EOF=" + IIf((cAliasTop)->(EoF()), "S", "N"))

    While !(cAliasTop)->(Eof())
        oLinha := MTR900ApiLinha(cAliasTop, cLocal, nMoeda, cDocPor, cTipoCusto, dDataFim)
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

        (cAliasTop)->(DbSkip())
    EndDo

    nTotalPages := IIf(lHasMore, nPage + 1, Max(1, nPage))

    // LOG: registros retornados nesta pagina
    ConOut(cLogPrefix + "Pagina montada | registros_retornados=" + cValToChar(Len(aLinhas)) + ;
        " total_processado=" + cValToChar(nTotalReg) + ;
        " hasMore=" + IIf(lHasMore, "S", "N"))

    oParams["data_ini"] := cDataIni
    oParams["data_fim"] := cDataFim
    oParams["produto_de"] := cProdutoDe
    oParams["produto_ate"] := cProdutoAte
    oParams["tipo_de"] := cTipoDe
    oParams["tipo_ate"] := cTipoAte
    oParams["grupo_de"] := cGrupoDe
    oParams["grupo_ate"] := cGrupoAte
    oParams["local"] := cLocal
    oParams["documento_por"] := cDocPor
    oParams["moeda"] := nMoeda
    oParams["ordem"] := nOrdem
    oParams["lista_sem_movimento"] := cSemMov
    oParams["considera_filiais"] := IIf(lTodasFil, "2", "1")
    oParams["tipo_custo"] := cTipoCusto
    oParams["page"] := nPage
    oParams["pageSize"] := nPageSize

    oResp["parametros"] := oParams
    oResp["total_registros"] := nTotalReg
    oResp["total_pages"] := nTotalPages
    oResp["page"] := nPage
    oResp["hasMore"] := lHasMore
    oResp["linhas"] := aLinhas
    Self:SetResponse(oResp:ToJson())

    ConOut(cLogPrefix + "Resposta enviada com sucesso")

Recover Using oError
    If Select(cAliasTop) > 0
        (cAliasTop)->(DbCloseArea())
    EndIf
    ConOut(cLogPrefix + "ERRO INTERNO: " + oError:Description + ;
        " | ClassName=" + oError:ClassName + ;
        " | SubCode=" + cValToChar(oError:SubCode))
    Self:SetResponse(MTR900ApiErro("INTERNAL_ERROR", "Erro interno ao consultar Kardex", oError:Description))
    AEval(aAllLinhas, {|o| FreeObj(o)})
    FreeObj(oResp)
    FreeObj(oParams)
    RestArea(aArea)
Return .T.
End Sequence

AEval(aAllLinhas, {|o| FreeObj(o)})
FreeObj(oResp)
FreeObj(oParams)
RestArea(aArea)
Return .T.

Static Function MTR900ApiLinha(cAliasTop, cLocal, nMoeda, cDocPor, cTipoCusto, dDataFim)
Local oLinha     := JsonObject():New()
Local cLocalRec  := AllTrim((cAliasTop)->ARMLOC)
Local cLocalCalc := IIf(Empty(cLocalRec), xFilial("SB2"), cLocalRec)
Local aSaldo     := {}
Local nSaldoQtd  := 0
Local nSaldoVlr  := 0
Local oErrCalc   := Nil
Local nEntQtd    := 0
Local nEntCus    := 0
Local nSaiQtd    := 0
Local nSaiCus    := 0
Local cArq       := AllTrim((cAliasTop)->ARQ)
Local cDocNumero := IIf(cDocPor $ "Ss", AllTrim((cAliasTop)->SEQUENCIA), AllTrim((cAliasTop)->DOCUMENTO))
Local cParceiro  := ""
Local lDev       := .F.

// CalcEst: CalcEst(cProduto, cLocal, dData, [nMoeda])
// 3o parametro = DATA (nao moeda). Retorna array: [1]=qtd, [2..n]=valor por moeda
Begin Sequence
    aSaldo    := CalcEst((cAliasTop)->PRODUTO, cLocalCalc, dDataFim, nMoeda)
    nSaldoQtd := IIf(Len(aSaldo) >= 1,          aSaldo[1], 0)
    nSaldoVlr := IIf(Len(aSaldo) >= nMoeda + 1,  aSaldo[nMoeda + 1], 0)
Recover Using oErrCalc
    ConOut("[ZMATR900] CalcEst ERRO | produto=" + AllTrim((cAliasTop)->PRODUTO) + ;
        " arq=" + cArq + " localCalc=[" + cLocalCalc + "]" + ;
        " erro=" + oErrCalc:Description)
    // saldo fica 0 — movimento registrado sem saldo calculado
End Sequence

Do Case
Case cArq == "SD1"
    lDev := MTR900Dev("SD1", cAliasTop)
    If (cAliasTop)->TES <= "500" .And. !lDev
        nEntQtd := (cAliasTop)->QUANTIDADE
        nEntCus := (cAliasTop)->CUSTO
    Else
        nSaiQtd := IIf(lDev, (cAliasTop)->QUANTIDADE * -1, (cAliasTop)->QUANTIDADE)
        nSaiCus := IIf(lDev, (cAliasTop)->CUSTO * -1, (cAliasTop)->CUSTO)
    EndIf
    cParceiro := IIf(((cAliasTop)->TIPONF) == "C", "C-", "F-") + AllTrim((cAliasTop)->PARCEIRO)
Case cArq == "SD2"
    lDev := MTR900Dev("SD2", cAliasTop)
    If (cAliasTop)->TES <= "500" .Or. lDev
        nEntQtd := IIf(lDev, (cAliasTop)->QUANTIDADE * -1, (cAliasTop)->QUANTIDADE)
        nEntCus := IIf(lDev, (cAliasTop)->CUSTO * -1, (cAliasTop)->CUSTO)
    Else
        nSaiQtd := (cAliasTop)->QUANTIDADE
        nSaiCus := (cAliasTop)->CUSTO
    EndIf
    cParceiro := IIf(((cAliasTop)->TIPONF) $ "B|D", "F-", "C-") + AllTrim((cAliasTop)->PARCEIRO)
Case cArq == "SD3"
    If (cAliasTop)->TES <= "500"
        nEntQtd := (cAliasTop)->QUANTIDADE
        nEntCus := (cAliasTop)->CUSTO
    Else
        nSaiQtd := (cAliasTop)->QUANTIDADE
        nSaiCus := (cAliasTop)->CUSTO
    EndIf
    cParceiro := IIf(!Empty(AllTrim((cAliasTop)->PARCEIRO)), "CC" + AllTrim((cAliasTop)->PARCEIRO), "")
EndCase

oLinha["Codigo"] := AllTrim((cAliasTop)->PRODUTO)
oLinha["Descricao"] := AllTrim((cAliasTop)->B1_DESC)
oLinha["UM"] := AllTrim((cAliasTop)->B1_UM)
oLinha["Tipo"] := AllTrim((cAliasTop)->TIPO)
oLinha["Grupo"] := AllTrim((cAliasTop)->B1_GRUPO)
oLinha["Custo Medio"] := IIf(nSaldoQtd <> 0, Round(nSaldoVlr / nSaldoQtd, 2), 0)
oLinha["Qtd Saldo"] := Round(nSaldoQtd, 2)
oLinha["Vlr Total Saldo"] := Round(nSaldoVlr, 2)
oLinha["Posicao IPI"] := AllTrim((cAliasTop)->B1_POSIPI)
oLinha["Endereco"] := ""
oLinha["Operacao Data"] := DtoC((cAliasTop)->DTDIGIT)
oLinha["ARM"] := AllTrim((cAliasTop)->ARMLOC)
oLinha["TES"] := AllTrim((cAliasTop)->TES)
oLinha["CF"] := AllTrim((cAliasTop)->CF)
oLinha["Documento Numero"] := cDocNumero
oLinha["Entradas Quantidade"] := Round(nEntQtd, 2)
oLinha["Entradas Custo Total"] := Round(nEntCus, 2)
oLinha["Custo Medio do Movimento"] := IIf((cAliasTop)->QUANTIDADE != 0, Round((cAliasTop)->CUSTO / (cAliasTop)->QUANTIDADE, 2), 0)
oLinha["Saidas Quantidade"] := Round(nSaiQtd, 2)
oLinha["Saidas Custo Total"] := Round(nSaiCus, 2)
oLinha["Saldo Quantidade"] := Round(nSaldoQtd, 2)
oLinha["Saldo Valor Total"] := Round(nSaldoVlr, 2)
oLinha["CLI/FOR/CC/PJ/OP/OS"] := cParceiro
Return oLinha

/*
  MTR900Dev - Verifica se o movimento e uma devolucao consultando F4_DUPLIC na SF4.
  SD1 (entrada): devolucao quando F4_DUPLIC = 'D' (devolucao de compra/entrada)
  SD2 (saida):   devolucao quando F4_DUPLIC = 'D' (devolucao de venda/saida)
  Replicado aqui pois MTR900Dev esta no matr900.prx e nao e visivel pela API REST.
*/
Static Function MTR900Dev(cTabela, cAliasTop)
Local lDev    := .F.
Local cTES    := AllTrim((cAliasTop)->TES)
Local cFilSF4 := xFilial("SF4")
Local cChave  := cFilSF4 + cTES

If Select("SF4") > 0
    lDev := ( Posicione("SF4", 1, cChave, "F4_DUPLIC") == "D" )
EndIf

Return lDev

Static Function MTR900ApiErro(cCodigo, cMensagem, cDetalhe)
Local oErro := JsonObject():New()
oErro["erro"] := .T.
oErro["codigo"] := cCodigo
oErro["mensagem"] := cMensagem
oErro["detalhe"] := cDetalhe
oErro["status"] := IIf(cCodigo == "INTERNAL_ERROR", 500, 400)
Return oErro:ToJson()
