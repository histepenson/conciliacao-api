//Bibliotecas
#Include "TOTVS.ch"
#Include "TopConn.ch"

/*/{Protheus.doc} VLDVS1BOL
Valida a condicao de pagamento (VS1_FORPAG) do orcamento (Balcao/Oficina).
Quando a forma de pagamento da condicao informada for BOL (Boleto),
verifica se o cliente do orcamento - considerando todos os cadastros SA1
que compartilham o mesmo CNPJ (A1_CGC), pois o mesmo CNPJ pode ter mais
de um cadastro com inscricoes diferentes - possui titulo(s) vencido(s)
em aberto (SE1, saldo > 0). Se houver, bloqueia a selecao da condicao de
pagamento e exibe um alerta com a relacao dos titulos encontrados.
Chamada a partir do X3_VALID do campo VS1_FORPAG, acrescentada ao final
da expressao existente com ".AND.U_VLDVS1BOL()" (o dicionario invoca com
o prefixo U_, mas a funcao e declarada com o nome puro abaixo).
@type Function
@author Histepenson
@since 2026
@return logical, .T. permite a selecao, .F. bloqueia
/*/
User Function VLDVS1BOL()

    Local cCondPag := M->VS1_FORPAG
    Local cCliFat  := M->VS1_CLIFAT
    Local cLojFat  := M->VS1_LOJA
    Local cCgc     := ""
    Local aTitulos := {}
    Local cMsg     := ""
    Local lRet     := .T.
    Local nI       := 0
    Local aAreaSE4 := {}
    Local aAreaSA1 := {}

    ConOut("[VLDVS1BOL] cCondPag=" + cCondPag + " cCliFat=" + cCliFat + " cLojFat=" + cLojFat)

    If Empty(cCondPag)
        ConOut("[VLDVS1BOL] condicao vazia, libera")
        Return .T.
    EndIf

    aAreaSE4 := SE4->(GetArea())
    SE4->(DbSetOrder(1)) // E4_FILIAL+E4_CODIGO
    If !SE4->(DbSeek(xFilial("SE4") + cCondPag))
        ConOut("[VLDVS1BOL] SE4 nao encontrado para " + cCondPag + ", libera")
        RestArea(aAreaSE4)
        Return .T.
    EndIf
    ConOut("[VLDVS1BOL] E4_FORMA=[" + SE4->E4_FORMA + "]")
    If AllTrim(SE4->E4_FORMA) != "BOL"
        RestArea(aAreaSE4)
        Return .T.
    EndIf
    RestArea(aAreaSE4)

    aAreaSA1 := SA1->(GetArea())
    SA1->(DbSetOrder(1)) // A1_FILIAL+A1_COD+A1_LOJA
    If !SA1->(DbSeek(xFilial("SA1") + cCliFat + cLojFat))
        ConOut("[VLDVS1BOL] SA1 nao encontrado para " + cCliFat + "/" + cLojFat + ", libera")
        RestArea(aAreaSA1)
        Return .T.
    EndIf
    cCgc := AllTrim(SA1->A1_CGC)
    RestArea(aAreaSA1)

    ConOut("[VLDVS1BOL] CGC=[" + cCgc + "]")

    If Empty(cCgc)
        Return .T.
    EndIf

    aTitulos := VVBTitVenc(cCgc)

    ConOut("[VLDVS1BOL] titulos vencidos encontrados=" + cValToChar(Len(aTitulos)))

    If Len(aTitulos) > 0
        cMsg := "Nao e possivel selecionar condicao de pagamento com forma de pagamento BOLETO." + CRLF
        cMsg += "Cliente (CNPJ " + cCgc + ") possui titulo(s) vencido(s) em aberto:" + CRLF + CRLF
        For nI := 1 To Len(aTitulos)
            cMsg += PadR(aTitulos[nI][1] + "-" + aTitulos[nI][2], 9) + " " + ;
                    PadR(aTitulos[nI][3] + " " + aTitulos[nI][4] + "-" + aTitulos[nI][5], 18) + " " + ;
                    "Venc: " + DToC(aTitulos[nI][6]) + "  Saldo: " + Transform(aTitulos[nI][7], "@E 999,999,999.99") + CRLF
        Next nI

        MsgAlert(cMsg, "Titulo(s) vencido(s) em aberto")
        lRet := .F.
    EndIf

Return lRet

/*/{Protheus.doc} VVBTitVenc
Consulta os titulos do SE1 vencidos e em aberto (E1_SALDO > 0 e
E1_VENCTO < GETDATE()) para todos os codigos de cliente (SA1) que
compartilham o CNPJ informado.
@type Function
@author Histepenson
@since 2026
@param cCgc, character, CNPJ (A1_CGC) do cliente
@return array de arrays, {E1_CLIENTE, E1_LOJA, E1_PREFIXO, E1_NUM, E1_PARCELA, E1_VENCTO, E1_SALDO}
/*/
Static Function VVBTitVenc(cCgc)

    Local aArea      := FWGetArea()
    Local aRet       := {}
    Local cAliasQry  := GetNextAlias()
    Local cQry       := ""

    //Monta a query dos titulos vencidos em aberto para os codigos SA1 do mesmo CNPJ
    cQry += " SELECT " + CRLF
    cQry += "     E1_CLIENTE, E1_LOJA, E1_PREFIXO, E1_NUM, E1_PARCELA, " + CRLF
    cQry += "     E1_VENCTO, E1_SALDO " + CRLF
    cQry += " FROM " + CRLF
    cQry += "     " + RetSQLName("SE1") + " SE1 " + CRLF
    cQry += " WHERE " + CRLF
    cQry += "     SE1.D_E_L_E_T_ = ' ' " + CRLF
    cQry += "     AND SE1.E1_SALDO > 0 " + CRLF
    cQry += "     AND SE1.E1_TIPO NOT IN ('RA','NCC') " + CRLF
    cQry += "     AND SE1.E1_VENCTO < GETDATE() " + CRLF
    cQry += "     AND SE1.E1_CLIENTE + SE1.E1_LOJA IN ( " + CRLF
    cQry += "         SELECT A1_COD + A1_LOJA " + CRLF
    cQry += "         FROM " + RetSQLName("SA1") + " SA1 " + CRLF
    cQry += "         WHERE SA1.D_E_L_E_T_ = ' ' " + CRLF
    cQry += "         AND SA1.A1_CGC = '" + cCgc + "' " + CRLF
    cQry += "     ) " + CRLF
    cQry += " ORDER BY E1_VENCTO " + CRLF

    //Abre o alias em memoria - os parenteses em (cAliasQry) sao obrigatorios,
    //senao o comando TCQuery trata "cAliasQry" como nome literal de alias
    TCQuery cQry New Alias (cAliasQry)

    //Garante o tipo Data no campo (TCQuery nao tipa automaticamente)
    TCSetField(cAliasQry, "E1_VENCTO", "D", 8, 0)

    ConOut("[VLDVS1BOL][VENC] titulos encontrados=" + cValToChar((cAliasQry)->(RecCount())))
    While !(cAliasQry)->(Eof())
        ConOut("[VLDVS1BOL][VENC] " + (cAliasQry)->E1_CLIENTE + "-" + (cAliasQry)->E1_LOJA + ;
               " " + (cAliasQry)->E1_PREFIXO + "-" + (cAliasQry)->E1_NUM + "-" + (cAliasQry)->E1_PARCELA + ;
               " VENCTO=" + DToC((cAliasQry)->E1_VENCTO) + ;
               " SALDO=" + cValToChar((cAliasQry)->E1_SALDO))
        AAdd(aRet, {;
            (cAliasQry)->E1_CLIENTE,;
            (cAliasQry)->E1_LOJA,;
            (cAliasQry)->E1_PREFIXO,;
            (cAliasQry)->E1_NUM,;
            (cAliasQry)->E1_PARCELA,;
            (cAliasQry)->E1_VENCTO,;
            (cAliasQry)->E1_SALDO})
        (cAliasQry)->(DbSkip())
    EndDo

    //Fecha o alias
    (cAliasQry)->(DbCloseArea())

    FWRestArea(aArea)

Return aRet
