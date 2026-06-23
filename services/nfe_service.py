"""
NF-e Service — parse, persistência, De-Para automático e alertas.
"""
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from models.certificado_digital import CertificadoDigital
from models.estoque_alerta import EstoqueAlerta, TipoAlerta
from models.nfe import NfeEntrada, NfeEntradaItem, NfeSaida, NfeSaidaItem, StatusNfe
from models.produto_fornecedor import OperacaoConversao, ProdutoFornecedor
from services import task_service
from services.certificado_service import carregar_pfx
from services.sefaz_service import buscar_nfes_sefaz

_NF_NS = "http://www.portalfiscal.inf.br/nfe"


# ─────────────────────────────────────────
# PARSE XML
# ─────────────────────────────────────────

def _txt(el, tag: str, default=None):
    """Extrai texto de um subelemento, retorna default se ausente."""
    node = el.find(f"{{{_NF_NS}}}{tag}")
    return node.text.strip() if node is not None and node.text else default


def _dec(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None


def _parse_date(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor[:10]).date()
    except ValueError:
        return None


def _parse_nfe_xml(xml_str: str) -> dict | None:
    """
    Extrai campos relevantes de um XML de NF-e.
    Retorna dict com: tipo, chave_acesso, numero_nf, serie, data_emissao,
    data_autorizacao, cnpj_emitente, razao_emitente, cnpj_dest, razao_dest,
    valor_total, status, itens[].
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return None

    def find(tag):
        return root.find(f".//{{{_NF_NS}}}{tag}")

    def findtext(tag, default=None):
        el = find(tag)
        return el.text.strip() if el is not None and el.text else default

    inf_nfe = find("infNFe")
    if inf_nfe is None:
        return None

    chave = inf_nfe.get("Id", "").replace("NFe", "")

    # Status — 100=autorizada, 101/102=cancelada, 110/301=denegada
    c_stat = findtext("cStat", "100")
    status_map = {"100": StatusNfe.autorizada, "101": StatusNfe.cancelada,
                  "102": StatusNfe.cancelada, "110": StatusNfe.denegada, "301": StatusNfe.denegada}
    status = status_map.get(c_stat, StatusNfe.autorizada)

    ide = inf_nfe.find(f"{{{_NF_NS}}}ide")
    emit = inf_nfe.find(f"{{{_NF_NS}}}emit")
    dest = inf_nfe.find(f"{{{_NF_NS}}}dest")
    total = inf_nfe.find(f".//{{{_NF_NS}}}ICMSTot")
    prot = root.find(f".//{{{_NF_NS}}}infProt")

    cnpj_emit = _txt(emit, "CNPJ") or _txt(emit, "CPF") or "" if emit is not None else ""
    cnpj_dest = _txt(dest, "CNPJ") or _txt(dest, "CPF") if dest is not None else None

    # Data autorização vem do protocolo; data emissão do ide
    data_aut = _parse_date(_txt(prot, "dhRecbto") if prot is not None else None)
    data_emis = _parse_date(_txt(ide, "dhEmi") if ide is not None else None)

    itens = []
    for i, det in enumerate(inf_nfe.findall(f"{{{_NF_NS}}}det"), start=1):
        prod = det.find(f"{{{_NF_NS}}}prod")
        if prod is None:
            continue
        itens.append({
            "numero_item": i,
            "codigo_produto": _txt(prod, "cProd"),
            "descricao": _txt(prod, "xProd"),
            "ncm": _txt(prod, "NCM"),
            "cfop": _txt(prod, "CFOP"),
            "unidade_comercial": _txt(prod, "uCom"),
            "quantidade": _dec(_txt(prod, "qCom")),
            "valor_unitario": _dec(_txt(prod, "vUnCom")),
            "valor_total_item": _dec(_txt(prod, "vProd")),
        })

    return {
        "chave_acesso": chave,
        "numero_nf": _txt(ide, "nNF") if ide is not None else None,
        "serie": _txt(ide, "serie") if ide is not None else None,
        "data_emissao": data_emis,
        "data_autorizacao": data_aut or data_emis,
        "cnpj_emitente": cnpj_emit,
        "razao_emitente": _txt(emit, "xNome") if emit is not None else None,
        "cnpj_destinatario": cnpj_dest,
        "razao_destinatario": _txt(dest, "xNome") if dest is not None else None,
        "valor_total": _dec(_txt(total, "vNF") if total is not None else None),
        "status": status,
        "itens": itens,
    }


# ─────────────────────────────────────────
# DE-PARA AUTOMÁTICO
# ─────────────────────────────────────────

def _aplicar_depara(db: Session, empresa_id: int, cnpj_fornecedor: str, item_data: dict) -> tuple[int | None, Decimal | None, str | None]:
    """Tenta vincular item ao produto interno. Retorna (produto_id, qtd_convertida, unidade_convertida)."""
    codigo = item_data.get("codigo_produto")
    if not codigo:
        return None, None, None

    depara = db.query(ProdutoFornecedor).filter(
        ProdutoFornecedor.empresa_id == empresa_id,
        ProdutoFornecedor.cnpj_fornecedor == cnpj_fornecedor,
        ProdutoFornecedor.codigo_produto_fornecedor == codigo,
    ).first()

    if not depara:
        return None, None, None

    qtd = item_data.get("quantidade")
    if qtd is None:
        return depara.produto_id, None, depara.unidade_convertida

    fator = Decimal(str(depara.fator_conversao))
    if depara.operacao_conversao == "multiplicar":
        qtd_convertida = qtd * fator
    else:
        qtd_convertida = qtd / fator

    return depara.produto_id, qtd_convertida, depara.unidade_convertida


# ─────────────────────────────────────────
# PERSISTÊNCIA DE NF
# ─────────────────────────────────────────

def _salvar_nfe_entrada(db: Session, empresa_id: int, dados: dict) -> tuple[NfeEntrada, int]:
    """Persiste NF de entrada. Retorna (nfe, qtd_itens_pendentes)."""
    nfe = NfeEntrada(
        empresa_id=empresa_id,
        chave_acesso=dados["chave_acesso"],
        numero_nf=dados["numero_nf"],
        serie=dados["serie"],
        data_emissao=dados["data_emissao"],
        data_autorizacao=dados["data_autorizacao"],
        cnpj_emitente=dados["cnpj_emitente"],
        razao_social_emitente=dados["razao_emitente"],
        valor_total=dados["valor_total"],
        status=dados["status"],
    )
    db.add(nfe)
    db.flush()

    pendentes = 0
    for item_data in dados["itens"]:
        prod_id, qtd_conv, unid_conv = _aplicar_depara(db, empresa_id, dados["cnpj_emitente"], item_data)
        vinculo_pendente = prod_id is None

        item = NfeEntradaItem(
            nfe_entrada_id=nfe.id,
            numero_item=item_data["numero_item"],
            codigo_produto_fornecedor=item_data["codigo_produto"],
            descricao_produto=item_data["descricao"],
            ncm=item_data["ncm"],
            cfop=item_data["cfop"],
            unidade_comercial=item_data["unidade_comercial"],
            quantidade=item_data["quantidade"],
            valor_unitario=item_data["valor_unitario"],
            valor_total_item=item_data["valor_total_item"],
            produto_id=prod_id,
            quantidade_convertida=qtd_conv,
            unidade_convertida=unid_conv,
            vinculo_pendente=vinculo_pendente,
        )
        db.add(item)

        if vinculo_pendente and item_data.get("codigo_produto"):
            pendentes += 1

    return nfe, pendentes


def _salvar_nfe_saida(db: Session, empresa_id: int, cnpj_empresa: str, dados: dict) -> tuple[NfeSaida, int]:
    """Persiste NF de saída. Retorna (nfe, qtd_itens_pendentes)."""
    nfe = NfeSaida(
        empresa_id=empresa_id,
        chave_acesso=dados["chave_acesso"],
        numero_nf=dados["numero_nf"],
        serie=dados["serie"],
        data_emissao=dados["data_emissao"],
        data_autorizacao=dados["data_autorizacao"],
        cnpj_destinatario=dados["cnpj_destinatario"],
        razao_social_destinatario=dados["razao_destinatario"],
        valor_total=dados["valor_total"],
        status=dados["status"],
    )
    db.add(nfe)
    db.flush()

    pendentes = 0
    for item_data in dados["itens"]:
        prod_id, qtd_conv, unid_conv = _aplicar_depara(db, empresa_id, cnpj_empresa, item_data)
        vinculo_pendente = prod_id is None

        item = NfeSaidaItem(
            nfe_saida_id=nfe.id,
            numero_item=item_data["numero_item"],
            codigo_produto_empresa=item_data["codigo_produto"],
            descricao_produto=item_data["descricao"],
            ncm=item_data["ncm"],
            cfop=item_data["cfop"],
            unidade_comercial=item_data["unidade_comercial"],
            quantidade=item_data["quantidade"],
            valor_unitario=item_data["valor_unitario"],
            valor_total_item=item_data["valor_total_item"],
            produto_id=prod_id,
            quantidade_convertida=qtd_conv,
            unidade_convertida=unid_conv,
            vinculo_pendente=vinculo_pendente,
        )
        db.add(item)

        if vinculo_pendente and item_data.get("codigo_produto"):
            pendentes += 1

    return nfe, pendentes


# ─────────────────────────────────────────
# IMPORTAÇÃO MANUAL DE XML (NF DE SAÍDA)
# ─────────────────────────────────────────

def importar_nfe_saida_xml(db: Session, empresa_id: int, xml_bytes: bytes) -> dict:
    """
    Importa uma NF de saída a partir do XML completo (nfeProc) gerado pela
    própria empresa na emissão. A SEFAZ (DistDFe) não devolve o XML completo
    de notas emitidas pela empresa, apenas o resumo — por isso a importação
    de saída é feita via upload do XML já existente no emissor.
    """
    from models.empresa import Empresa

    try:
        xml_str = xml_bytes.decode("utf-8")
    except UnicodeDecodeError:
        xml_str = xml_bytes.decode("latin-1")

    dados = _parse_nfe_xml(xml_str)
    if not dados:
        return {"status": "erro", "mensagem": "XML invalido ou nao reconhecido"}

    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    cnpj_empresa = re.sub(r"\D", "", empresa.cnpj) if empresa and empresa.cnpj else None

    if cnpj_empresa and dados["cnpj_emitente"] != cnpj_empresa:
        return {
            "status": "erro",
            "numero_nf": dados["numero_nf"],
            "mensagem": f"NF {dados['numero_nf']}: emitente ({dados['cnpj_emitente']}) "
                        f"nao corresponde ao CNPJ da empresa ({cnpj_empresa})",
        }

    existe = db.query(NfeSaida).filter(
        NfeSaida.empresa_id == empresa_id,
        NfeSaida.chave_acesso == dados["chave_acesso"],
    ).first()
    if existe:
        return {"status": "duplicada", "numero_nf": dados["numero_nf"], "chave_acesso": dados["chave_acesso"]}

    _, pendentes = _salvar_nfe_saida(db, empresa_id, cnpj_empresa or dados["cnpj_emitente"], dados)

    if pendentes > 0:
        db.add(EstoqueAlerta(
            empresa_id=empresa_id,
            tipo=TipoAlerta.sem_depara,
            referencia_id=None,
            mensagem=f"NF saida {dados['numero_nf']}: {pendentes} item(ns) sem De-Para",
        ))

    db.commit()
    return {
        "status": "importada",
        "numero_nf": dados["numero_nf"],
        "chave_acesso": dados["chave_acesso"],
        "pendentes_vinculo": pendentes,
    }


# ─────────────────────────────────────────
# IMPORTAÇÃO ASSÍNCRONA (BackgroundTask)
# ─────────────────────────────────────────

def importar_nfes_background(
    db: Session,
    empresa_id: int,
    cnpj_certificado: str,
    data_inicio: Optional[date],
    data_fim: Optional[date],
    task_id: str,
) -> None:
    """
    Executado como BackgroundTask. Consulta SEFAZ, persiste NFs e gera alertas.
    """
    try:
        cert = db.query(CertificadoDigital).filter(
            CertificadoDigital.empresa_id == empresa_id,
            CertificadoDigital.cnpj_certificado == cnpj_certificado,
        ).first()

        if not cert:
            task_service.falhar_task(task_id, f"Certificado para CNPJ {cnpj_certificado} nao encontrado")
            return

        pfx_bytes, senha_bytes = carregar_pfx(db, cert.id)
        cnpj = cnpj_certificado

        total_importadas = 0
        total_pendentes = 0
        processadas = 0

        def _persistir_nsu(novo_nsu: str) -> None:
            cert.ultimo_nsu = novo_nsu
            db.commit()

        ult_nsu_inicial = cert.ultimo_nsu or "000000000000000"

        for doc in buscar_nfes_sefaz(
            cnpj, pfx_bytes, senha_bytes,
            ult_nsu=ult_nsu_inicial, on_nsu_update=_persistir_nsu,
        ):
            xml_str = doc["xml_str"]
            chave = doc["chave_acesso"]

            dados = _parse_nfe_xml(xml_str)
            if not dados:
                continue

            # Filtra pelo período (se informado)
            data_ref = dados["data_autorizacao"] or dados["data_emissao"]
            if data_inicio and data_fim and data_ref and not (data_inicio <= data_ref <= data_fim):
                continue

            # Determina se é entrada ou saída pelo destinatário
            is_entrada = dados["cnpj_destinatario"] == cnpj or dados["cnpj_emitente"] != cnpj

            if is_entrada:
                # Verifica duplicidade
                existe = db.query(NfeEntrada).filter(
                    NfeEntrada.empresa_id == empresa_id,
                    NfeEntrada.chave_acesso == chave,
                ).first()
                if not existe:
                    _, pendentes = _salvar_nfe_entrada(db, empresa_id, dados)
                    total_importadas += 1
                    total_pendentes += pendentes

                    if pendentes > 0:
                        db.add(EstoqueAlerta(
                            empresa_id=empresa_id,
                            tipo=TipoAlerta.sem_depara,
                            referencia_id=None,
                            mensagem=f"NF {dados['numero_nf']} ({dados['cnpj_emitente']}): {pendentes} item(ns) sem De-Para",
                        ))
            else:
                existe = db.query(NfeSaida).filter(
                    NfeSaida.empresa_id == empresa_id,
                    NfeSaida.chave_acesso == chave,
                ).first()
                if not existe:
                    _, pendentes = _salvar_nfe_saida(db, empresa_id, cnpj, dados)
                    total_importadas += 1
                    total_pendentes += pendentes

                    if pendentes > 0:
                        db.add(EstoqueAlerta(
                            empresa_id=empresa_id,
                            tipo=TipoAlerta.sem_depara,
                            referencia_id=None,
                            mensagem=f"NF saida {dados['numero_nf']}: {pendentes} item(ns) sem De-Para",
                        ))

            processadas += 1
            task_service.atualizar_task(task_id, progresso=processadas)

            # Commit em lotes de 50 para não sobrecarregar a transação
            if processadas % 50 == 0:
                db.commit()

        db.commit()
        task_service.concluir_task(task_id, total_importadas, total_pendentes)

    except Exception as exc:
        db.rollback()
        task_service.falhar_task(task_id, str(exc))


# ─────────────────────────────────────────
# CANCELAMENTO DE NF (estorno)
# ─────────────────────────────────────────

def cancelar_nfe_entrada(db: Session, nfe_id: int) -> NfeEntrada:
    from models.estoque import EstoqueMovimentacao
    nfe = db.query(NfeEntrada).filter(NfeEntrada.id == nfe_id).first()
    if not nfe or nfe.status == StatusNfe.cancelada:
        return nfe

    nfe.status = StatusNfe.cancelada

    for item in nfe.itens:
        if item.produto_id and item.quantidade_convertida:
            db.add(EstoqueMovimentacao(
                empresa_id=nfe.empresa_id,
                produto_id=item.produto_id,
                data_movimentacao=date.today(),
                tipo="estorno",
                quantidade=-item.quantidade_convertida,
                documento_origem=nfe.chave_acesso,
                justificativa=f"Cancelamento NF {nfe.numero_nf}",
            ))

    db.commit()
    return nfe


def cancelar_nfe_saida(db: Session, nfe_id: int) -> NfeSaida:
    from models.estoque import EstoqueMovimentacao
    nfe = db.query(NfeSaida).filter(NfeSaida.id == nfe_id).first()
    if not nfe or nfe.status == StatusNfe.cancelada:
        return nfe

    nfe.status = StatusNfe.cancelada

    for item in nfe.itens:
        if item.produto_id and item.quantidade_convertida:
            db.add(EstoqueMovimentacao(
                empresa_id=nfe.empresa_id,
                produto_id=item.produto_id,
                data_movimentacao=date.today(),
                tipo="estorno",
                quantidade=item.quantidade_convertida,
                documento_origem=nfe.chave_acesso,
                justificativa=f"Cancelamento NF saida {nfe.numero_nf}",
            ))

    db.commit()
    return nfe


# ─────────────────────────────────────────
# VÍNCULO MANUAL + REPROCESSAMENTO
# ─────────────────────────────────────────

def _registrar_depara(
    db: Session,
    empresa_id: int,
    produto_id: int,
    cnpj_fornecedor: str,
    razao_social_fornecedor: str | None,
    codigo_produto_fornecedor: str | None,
    descricao_fornecedor: str | None,
    unidade_comercial: str | None,
) -> "ProdutoFornecedor | None":
    """Cria ou atualiza o De-Para (produto_fornecedor) ao vincular um item manualmente,
    para que proximas NFs com o mesmo codigo/fornecedor sejam reconhecidas automaticamente."""
    if not codigo_produto_fornecedor:
        return None

    unidade = unidade_comercial or "UN"

    depara = db.query(ProdutoFornecedor).filter(
        ProdutoFornecedor.empresa_id == empresa_id,
        ProdutoFornecedor.cnpj_fornecedor == cnpj_fornecedor,
        ProdutoFornecedor.codigo_produto_fornecedor == codigo_produto_fornecedor,
    ).first()

    if depara:
        depara.produto_id = produto_id
        if razao_social_fornecedor:
            depara.razao_social_fornecedor = razao_social_fornecedor
        if descricao_fornecedor:
            depara.descricao_fornecedor = descricao_fornecedor
        return depara

    depara = ProdutoFornecedor(
        produto_id=produto_id,
        empresa_id=empresa_id,
        cnpj_fornecedor=cnpj_fornecedor,
        razao_social_fornecedor=razao_social_fornecedor,
        codigo_produto_fornecedor=codigo_produto_fornecedor,
        descricao_fornecedor=descricao_fornecedor,
        unidade_compra=unidade,
        fator_conversao=1,
        operacao_conversao=OperacaoConversao.multiplicar,
        unidade_convertida=unidade,
    )
    db.add(depara)
    return depara


def vincular_item_entrada(db: Session, item_id: int, produto_id: int) -> NfeEntradaItem:
    from fastapi import HTTPException
    from models.produto import Produto

    item = db.query(NfeEntradaItem).filter(NfeEntradaItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item nao encontrado")

    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(404, "Produto nao encontrado")

    nfe = item.nfe

    depara = _registrar_depara(
        db, nfe.empresa_id, produto_id,
        cnpj_fornecedor=nfe.cnpj_emitente,
        razao_social_fornecedor=nfe.razao_social_emitente,
        codigo_produto_fornecedor=item.codigo_produto_fornecedor,
        descricao_fornecedor=item.descricao_produto,
        unidade_comercial=item.unidade_comercial,
    )
    db.flush()

    item.produto_id = produto_id
    item.vinculo_pendente = False

    if depara and item.quantidade:
        fator = Decimal(str(depara.fator_conversao))
        if depara.operacao_conversao == "multiplicar":
            item.quantidade_convertida = item.quantidade * fator
        else:
            item.quantidade_convertida = item.quantidade / fator
        item.unidade_convertida = depara.unidade_convertida

    db.commit()
    db.refresh(item)

    periodo = nfe.data_emissao or nfe.data_autorizacao
    if periodo:
        from services.estoque_service import apurar_saldo
        apurar_saldo(db, nfe.empresa_id, produto_id, periodo)

    return item


def vincular_item_saida(db: Session, item_id: int, produto_id: int) -> NfeSaidaItem:
    from fastapi import HTTPException
    from models.empresa import Empresa
    from models.produto import Produto

    item = db.query(NfeSaidaItem).filter(NfeSaidaItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item nao encontrado")
    if not db.query(Produto).filter(Produto.id == produto_id).first():
        raise HTTPException(404, "Produto nao encontrado")

    nfe = item.nfe
    empresa = db.query(Empresa).filter(Empresa.id == nfe.empresa_id).first()
    cnpj_empresa = re.sub(r"\D", "", empresa.cnpj) if empresa and empresa.cnpj else None

    if cnpj_empresa:
        _registrar_depara(
            db, nfe.empresa_id, produto_id,
            cnpj_fornecedor=cnpj_empresa,
            razao_social_fornecedor=empresa.nome if empresa else None,
            codigo_produto_fornecedor=item.codigo_produto_empresa,
            descricao_fornecedor=item.descricao_produto,
            unidade_comercial=item.unidade_comercial,
        )

    item.produto_id = produto_id
    item.vinculo_pendente = False
    db.commit()
    db.refresh(item)

    periodo = nfe.data_emissao or nfe.data_autorizacao
    if periodo:
        from services.estoque_service import apurar_saldo
        apurar_saldo(db, nfe.empresa_id, produto_id, periodo)

    return item


def reprocessar_nfe_entrada(db: Session, nfe_id: int) -> int:
    """Reaplica De-Para em todos os itens pendentes. Retorna qtd de itens vinculados."""
    nfe = db.query(NfeEntrada).filter(NfeEntrada.id == nfe_id).first()
    if not nfe:
        return 0

    vinculados = 0
    produtos_afetados: set[int] = set()
    for item in db.query(NfeEntradaItem).filter(
        NfeEntradaItem.nfe_entrada_id == nfe_id,
        NfeEntradaItem.vinculo_pendente == True,  # noqa
    ).all():
        prod_id, qtd_conv, unid_conv = _aplicar_depara(db, nfe.empresa_id, nfe.cnpj_emitente, {
            "codigo_produto": item.codigo_produto_fornecedor,
            "quantidade": item.quantidade,
        })
        if prod_id:
            item.produto_id = prod_id
            item.quantidade_convertida = qtd_conv
            item.unidade_convertida = unid_conv
            item.vinculo_pendente = False
            vinculados += 1
            produtos_afetados.add(prod_id)

    db.commit()

    periodo = nfe.data_emissao or nfe.data_autorizacao
    if periodo and produtos_afetados:
        from services.estoque_service import apurar_saldo
        for prod_id in produtos_afetados:
            apurar_saldo(db, nfe.empresa_id, prod_id, periodo)

    return vinculados
