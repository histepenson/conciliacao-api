# services/planodecontas_services.py
from sqlalchemy.orm import Session
from models.planodecontas import PlanoDeContas
from models.conciliacao import Conciliacao
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
import logging

import pandas as pd
#configurar logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)




def listar_planos_de_contas(db: Session, empresa_id: int, skip: int = 0, limit: int = 1000) -> List[PlanoDeContas]:
    return db.query(PlanoDeContas).filter(
        PlanoDeContas.empresa_id == empresa_id
    ).order_by(
        PlanoDeContas.conta_contabil  # ← ADICIONADO: Ordena por código da conta
    ).offset(skip).limit(limit).all()


def buscar_conta(db: Session, id: int) -> Optional[PlanoDeContas]:
    return db.query(PlanoDeContas).filter(PlanoDeContas.id == id).first()


def criar_conta(db: Session, dados: dict) -> PlanoDeContas:
    db_conta = PlanoDeContas(**dados)
    db.add(db_conta)
    db.commit()
    db.refresh(db_conta)
    return db_conta


def atualizar_conta(db: Session, id: int, dados: dict) -> Optional[PlanoDeContas]:
    db_conta = buscar_conta(db, id)
    if not db_conta:
        return None
    for key, value in dados.items():
        setattr(db_conta, key, value)
    db_conta.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_conta)
    return db_conta


def deletar_conta(db: Session, id: int) -> bool:
    db_conta = buscar_conta(db, id)
    if not db_conta:
        return False
    db.delete(db_conta)
    db.commit()
    return True


def ordenar_contas_hierarquicamente(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ordena as contas respeitando a hierarquia:
    1. Primeiro por tipo (sintéticas antes de analíticas)
    2. Depois por nível hierárquico (profundidade)
    3. Por último pelo código da conta
    
    Args:
        df: DataFrame com as contas
        
    Returns:
        DataFrame ordenado
    """
    # Criar coluna auxiliar com o tamanho do código (nível hierárquico)
    df['_nivel'] = df['conta_contabil'].astype(str).str.len()
    
    # Ordenar por:
    # 1. tipo_conta (1=sintética primeiro, 2=analítica depois)
    # 2. nível hierárquico (menor nível primeiro - contas mais no topo)
    # 3. código da conta (ordem numérica)
    df_ordenado = df.sort_values(
        by=['tipo_conta', '_nivel', 'conta_contabil'],
        ascending=[True, True, True]
    )
    
    # Remover coluna auxiliar
    df_ordenado = df_ordenado.drop(columns=['_nivel'])
    
    return df_ordenado.reset_index(drop=True)


def validar_estrutura_arquivo(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Valida se o arquivo possui a estrutura esperada
    
    Args:
        df: DataFrame a ser validado
        
    Returns:
        Tupla (é_válido, lista_de_erros)
    """
    erros = []
    
    # Verificar colunas obrigatórias
    colunas_esperadas = ['conta_contabil', 'descricao', 'conciliavel', 'tipo_conta', 'conta_superior']
    colunas_faltantes = set(colunas_esperadas) - set(df.columns)
    
    if colunas_faltantes:
        erros.append(f"Colunas faltantes: {', '.join(colunas_faltantes)}")
    
    # Verificar se há registros
    if df.empty:
        erros.append("Arquivo não contém registros")
    
    # Verificar tipos de conta válidos
    if 'tipo_conta' in df.columns:
        tipos_invalidos = df[~df['tipo_conta'].isin(['1', '2', 1, 2])]['tipo_conta'].unique()
        if len(tipos_invalidos) > 0:
            erros.append(f"Tipos de conta inválidos encontrados: {tipos_invalidos}")
    
    return len(erros) == 0, erros


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza os nomes das colunas do Excel para o formato esperado.
    Aceita variações com acentos, maiúsculas, espaços, underscores, etc.
    """
    import unicodedata
    import re

    def limpar_nome(nome: str) -> str:
        nome = str(nome).strip().lower()
        nome = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode('ascii')
        nome = re.sub(r'[\s\-]+', '_', nome)
        nome = re.sub(r'[^a-z0-9_]', '', nome)
        return nome

    mapeamento = {
        'conta_contabil': ['conta_contabil', 'contacontabil', 'conta', 'codigo', 'cod', 'codigo_conta', 'cod_conta'],
        'descricao': ['descricao', 'desc', 'nome', 'nome_conta', 'descricao_conta'],
        'tipo_conta': ['tipo_conta', 'tipoconta', 'tipo', 'tp_conta', 'tipo_de_conta'],
        'conta_superior': ['conta_superior', 'contasuperior', 'conta_pai', 'pai', 'superior', 'conta_mae'],
        'conciliavel': ['conciliavel', 'concilia', 'conc', 'reconciliavel'],
    }

    colunas_normalizadas = {limpar_nome(col): col for col in df.columns}
    rename_map = {}

    for campo_esperado, variacoes in mapeamento.items():
        for variacao in variacoes:
            if variacao in colunas_normalizadas:
                rename_map[colunas_normalizadas[variacao]] = campo_esperado
                break

    if rename_map:
        df = df.rename(columns=rename_map)
        logger.info(f"Colunas mapeadas: {rename_map}")

    return df


def preparar_dados_importacao(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Separa as contas em sintéticas e analíticas,
    ordenadas corretamente para importação

    Args:
        df: DataFrame com os dados do plano de contas

    Returns:
        Tupla (df_sinteticas, df_analiticas)
    """
    logger.info(f"Preparando dados para importação...")

    logger.info(f"Total de registros lidos: {len(df)}")
    logger.info(f"Colunas do arquivo: {list(df.columns)}")

    # Normalizar nomes de colunas
    df = normalizar_colunas(df)

    # Validar estrutura
    valido, erros = validar_estrutura_arquivo(df)
    if not valido:
        raise ValueError(f"Erro na validação do arquivo:\n" + "\n".join(erros))

    # Normalizar conta_contabil como string
    df['conta_contabil'] = df['conta_contabil'].str.strip()

    # Normalizar conta_superior como string (vazio/NaN → None)
    df['conta_superior'] = df['conta_superior'].str.strip()
    df.loc[df['conta_superior'].isna() | (df['conta_superior'] == ''), 'conta_superior'] = None

    # Remover contas duplicadas (manter a última ocorrência)
    total_antes = len(df)
    df = df.drop_duplicates(subset=['conta_contabil'], keep='last')
    duplicatas_removidas = total_antes - len(df)
    if duplicatas_removidas > 0:
        logger.warning(f"Removidas {duplicatas_removidas} contas duplicadas do arquivo")

    # Ordenar hierarquicamente
    df_ordenado = ordenar_contas_hierarquicamente(df)

    # Normalizar tipo_conta para string
    df_ordenado['tipo_conta'] = df_ordenado['tipo_conta'].astype(str).str.strip()

    # Separar sintéticas e analíticas
    df_sinteticas = df_ordenado[df_ordenado['tipo_conta'] == '1'].copy()
    df_analiticas = df_ordenado[df_ordenado['tipo_conta'] == '2'].copy()

    logger.info(f"Contas sintéticas: {len(df_sinteticas)}")
    logger.info(f"Contas analíticas: {len(df_analiticas)}")

    return df_sinteticas, df_analiticas

def converter_conciliavel(valor) -> bool:
    if pd.isna(valor):
        return False

    if isinstance(valor, bool):
        return valor

    if isinstance(valor, (int, float)):
        return valor == 1

    valor_str = str(valor).strip().upper()

    if valor_str in ("1", "SIM", "S", "YES", "Y", "TRUE", "VERDADEIRO"):
        return True
    if valor_str in ("0", "NAO", "NÃO", "N", "NO", "FALSE", "FALSO", ""):
        return False

    raise ValueError(
        f"Valor inválido para conciliavel: '{valor}'. "
        "Use: 1/0, Sim/Não, S/N, True/False."
    )



def importar_plano_contas(df_sinteticas: pd.DataFrame, df_analiticas: pd.DataFrame, empresa_id: int, db: Session) -> Dict:
    """
    Função principal de importação do plano de contas
    
    Processo:
    1. Importa primeiro as contas sintéticas
    2. Importa depois as contas analíticas
    
    Args:
        df_sinteticas: DataFrame com as contas sintéticas
        df_analiticas: DataFrame com as contas analíticas
        empresa_id: ID da empresa
        db: Sessão do banco de dados
        
    Returns:
        Dicionário com estatísticas da importação
    """
    logger.info("="*80)
    logger.info("INICIANDO IMPORTAÇÃO DO PLANO DE CONTAS")
    logger.info("="*80)
    
    try:
        # Verificar contas existentes da empresa
        contas_existentes = db.query(PlanoDeContas).filter(
            PlanoDeContas.empresa_id == empresa_id
        ).count()

        if contas_existentes > 0:
            # Verificar se há conciliações vinculadas antes de deletar
            conciliacoes_vinculadas = db.query(Conciliacao).filter(
                Conciliacao.empresa_id == empresa_id
            ).count()

            if conciliacoes_vinculadas > 0:
                raise ValueError(
                    f"Não é possível reimportar o plano de contas: existem {conciliacoes_vinculadas} "
                    f"conciliação(ões) vinculada(s) a esta empresa. "
                    f"Remova as conciliações antes de reimportar."
                )

            logger.info(f"Removendo {contas_existentes} contas existentes da empresa {empresa_id} para reimportação...")
            db.query(PlanoDeContas).filter(
                PlanoDeContas.empresa_id == empresa_id
            ).delete(synchronize_session=False)
            db.flush()
            logger.info(f"✓ Contas existentes removidas")

        estatisticas = {
            'total_contas': len(df_sinteticas) + len(df_analiticas),
            'sinteticas_importadas': 0,
            'analiticas_importadas': 0,
            'contas_removidas': contas_existentes,
            'erros': []
        }
        
        # FASE 1: Importar contas sintéticas
        logger.info("\n" + "="*80)
        logger.info("FASE 1: IMPORTANDO CONTAS SINTÉTICAS")
        logger.info("="*80)
        
        for idx, conta in df_sinteticas.iterrows():
            try:
                # Preparar conta_superior (código contábil da conta superior)
                conta_superior = None
                if pd.notna(conta['conta_superior']) and str(conta['conta_superior']).strip():
                    conta_superior = str(conta['conta_superior']).strip()
                
                logger.info(f"Importando sintética: {conta['conta_contabil']} - {conta['descricao']}")
                
                # Criar conta no banco - atribuição direta
                db_conta = PlanoDeContas()
                db_conta.conta_contabil = str(conta['conta_contabil'])
                db_conta.descricao = conta['descricao']
                db_conta.conciliavel = converter_conciliavel(conta['conciliavel'])
                db_conta.tipo_conta = str(conta['tipo_conta']).strip()
                db_conta.conta_superior = conta_superior
                db_conta.empresa_id = empresa_id
                
                db.add(db_conta)
                
                estatisticas['sinteticas_importadas'] += 1
                
            except Exception as e:
                erro_msg = f"Erro ao importar conta {conta['conta_contabil']}: {str(e)}"
                logger.error(erro_msg)
                estatisticas['erros'].append(erro_msg)
                db.rollback()  # Rollback apenas desta conta com erro
        
        # Commit das contas sintéticas
        db.commit()
        logger.info(f"✓ Commit de {estatisticas['sinteticas_importadas']} contas sintéticas")
        
        # FASE 2: Importar contas analíticas
        logger.info("\n" + "="*80)
        logger.info("FASE 2: IMPORTANDO CONTAS ANALÍTICAS")
        logger.info("="*80)
        
        for idx, conta in df_analiticas.iterrows():
            try:
                # Preparar conta_superior (código contábil da conta superior)
                conta_superior = None
                if pd.notna(conta['conta_superior']) and str(conta['conta_superior']).strip():
                    conta_superior = str(conta['conta_superior']).strip()
                
                logger.info(f"Importando analítica: {conta['conta_contabil']} - {conta['descricao']}")
                
                # Criar conta no banco - atribuição direta
                db_conta = PlanoDeContas()
                db_conta.conta_contabil = str(conta['conta_contabil'])
                db_conta.descricao = conta['descricao']
                db_conta.conciliavel = converter_conciliavel(conta['conciliavel'])
                db_conta.tipo_conta = str(conta['tipo_conta']).strip()
                db_conta.conta_superior = conta_superior
                db_conta.empresa_id = empresa_id
                
                db.add(db_conta)
                
                estatisticas['analiticas_importadas'] += 1
                
            except Exception as e:
                erro_msg = f"Erro ao importar conta {conta['conta_contabil']}: {str(e)}"
                logger.error(erro_msg)
                estatisticas['erros'].append(erro_msg)
                db.rollback()  # Rollback apenas desta conta com erro
        
        # Commit das contas analíticas
        db.commit()
        logger.info(f"✓ Commit de {estatisticas['analiticas_importadas']} contas analíticas")
        
        # Resumo final
        logger.info("\n" + "="*80)
        logger.info("RESUMO DA IMPORTAÇÃO")
        logger.info("="*80)
        logger.info(f"Total de contas no arquivo: {estatisticas['total_contas']}")
        logger.info(f"Contas sintéticas importadas: {estatisticas['sinteticas_importadas']}")
        logger.info(f"Contas analíticas importadas: {estatisticas['analiticas_importadas']}")
        logger.info(f"Total importado: {estatisticas['sinteticas_importadas'] + estatisticas['analiticas_importadas']}")
        
        if estatisticas['erros']:
            logger.warning(f"\nErros encontrados: {len(estatisticas['erros'])}")
            for erro in estatisticas['erros']:
                logger.warning(f"  - {erro}")
        else:
            logger.info("\n✓ Importação concluída com sucesso!")
        
        return estatisticas
        
    except Exception as e:
        logger.error(f"\nERRO FATAL na importação: {str(e)}")
        db.rollback()  # Rollback completo em caso de erro fatal
        raise