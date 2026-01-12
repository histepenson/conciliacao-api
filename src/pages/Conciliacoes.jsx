import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import api from '../api/axiosConfig';
import '../assets/styles/App.css';
import FileUploadCard from '../components/FileUploadCard/FileUploadCard.jsx';
import ResultDisplay from '../components/ResultDisplay/ResultDisplay.jsx';
import * as XLSX from 'xlsx'

function Conciliacoes() {
  const location = useLocation();
  const navigate = useNavigate();
  const { conta, dataBase, empresaId, empresa } = location.state || {};

  const [files, setFiles] = useState({
    origem: null,
    contabil: null,
    geral: null,
  })

  const [isProcessing, setIsProcessing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Verifica se tem os dados da conciliação
  useEffect(() => {
    if (!conta || !dataBase || !empresaId) {
      alert('Dados da conciliação não encontrados. Redirecionando...');
      navigate('/conciliacoes/periodo');
    }
  }, [conta, dataBase, empresaId, navigate]);

  // Função para voltar
  const voltarParaSelecao = () => {
    navigate('/conciliacoes/periodo');
  };

  // Função para lidar com drag over
  const handleDragOver = (e, type) => {
    e.preventDefault()
    e.currentTarget.classList.add('drag-over')
  }

  // Função para lidar com drag leave
  const handleDragLeave = (e) => {
    e.preventDefault()
    e.currentTarget.classList.remove('drag-over')
  }

  // Função para lidar com drop
  const handleDrop = (e, type) => {
    e.preventDefault()
    e.currentTarget.classList.remove('drag-over')
    
    const file = e.dataTransfer.files[0]
    if (file) {
      handleFileSelect(type, file)
    }
  }

  // Função para selecionar arquivo
  const handleFileSelect = (type, file) => {
    const allowedTypes = [
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
      'text/csv'
    ]
    
    if (!allowedTypes.includes(file.type) && !file.name.match(/\.(xlsx|xls|csv)$/i)) {
      alert('Formato inválido! Use apenas .xlsx, .xls ou .csv')
      return
    }

    if (file.size > 50 * 1024 * 1024) {
      alert('Arquivo muito grande! Máximo 50MB')
      return
    }

    setFiles(prev => ({ ...prev, [type]: file }))
    setError(null)
  }

  // Função para remover arquivo
  const removeFile = (type) => {
    setFiles(prev => ({ ...prev, [type]: null }))
  }

  // Função para limpar tudo
  const resetAll = () => {
    setFiles({ origem: null, contabil: null, geral: null })
    setResult(null)
    setError(null)
  }
const readFileAsJson = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = (e) => {
      const data = new Uint8Array(e.target.result)
      const workbook = XLSX.read(data, { type: 'array' })
      const sheetName = workbook.SheetNames[0]
      const sheet = workbook.Sheets[sheetName]
      const json = XLSX.utils.sheet_to_json(sheet, { defval: null })
      resolve(json)
    }

    reader.onerror = reject
    reader.readAsArrayBuffer(file)
  })
}
// Adicione esta função logo após a função readFileAsJson

const processFiles = async () => {
  setIsProcessing(true)
  setError(null)
  setResult(null)

  try {
    console.log('🔄 Iniciando processamento...')
    
    // 1. Ler arquivos
    const origemRegistros = await readFileAsJson(files.origem)
    const contabilRegistros = await readFileAsJson(files.contabil)
    const geralRegistros = await readFileAsJson(files.geral)

    console.log('📊 Registros lidos:')
    console.log('  - Origem:', origemRegistros.length)
    console.log('  - Contábil:', contabilRegistros.length)
    console.log('  - Geral:', geralRegistros.length)

    // 2. Montar payload conforme API
    const payload = {
      base_origem: {
        registros: origemRegistros
      },
      base_contabil_filtrada: {
        conta_contabil: conta.conta_contabil,
        registros: contabilRegistros
      },
      base_contabil_geral: {
        registros: geralRegistros
      },
      parametros: {
        data_base: dataBase,
        empresa_id: empresaId,
        empresa_nome: empresa?.nome
      }
    }

    console.log('📤 Payload montado:', {
      origem_count: payload.base_origem.registros.length,
      contabil_count: payload.base_contabil_filtrada.registros.length,
      geral_count: payload.base_contabil_geral.registros.length,
      conta: payload.base_contabil_filtrada.conta_contabil,
      data_base: payload.parametros.data_base
    })

    // 3. Chamar API
    console.log('🌐 Chamando API /conciliacoes/contabil...')
    const response = await api.post('/conciliacoes/contabil', payload)

    console.log('✅ Resposta recebida:', response.data)
    console.log('📊 Resumo:', response.data.resumo)
    console.log('📊 Diferenças origem maior:', response.data.diferencas_origem_maior?.length || 0)
    console.log('📊 Diferenças contábil maior:', response.data.diferencas_contabilidade_maior?.length || 0)

    // 4. Garantir que o result esteja no formato certo
    if (response.data) {
      const resultData = {
        resumo: response.data.resumo || {},
        diferencas_origem_maior: response.data.diferencas_origem_maior || [],
        diferencas_contabilidade_maior: response.data.diferencas_contabilidade_maior || [],
        observacoes: response.data.observacoes || [],
        alertas: response.data.alertas || []
      }
      
      console.log('💾 Salvando resultado no estado:', resultData)
      setResult(resultData)
      
      // Verificar se tem dados vazios
      if (resultData.resumo.total_origem === 0 && resultData.resumo.total_destino === 0) {
        console.warn('⚠️ ATENÇÃO: Totais zerados! Verifique os dados de entrada.')
      }
    } else {
      console.error('❌ Resposta vazia da API')
      setError('Resposta vazia da API')
    }

  } catch (err) {
    console.error('❌ Erro detalhado:', {
      message: err.message,
      response: err.response?.data,
      status: err.response?.status
    })
    
    setError(
      err.response?.data?.detail ||
      err.message ||
      'Erro ao processar conciliação'
    )
  } finally {
    setIsProcessing(false)
  }
}

  // Função para efetivar conciliação (preparada para implementação futura)
  const efetivarConciliacao = async () => {
    if (!result) {
      alert('Processe os arquivos antes de efetivar a conciliação');
      return;
    }

    try {
      // TODO: Implementar chamada à API para efetivar a conciliação
      console.log('📝 Efetivando conciliação:', {
        conta: conta,
        dataBase: dataBase,
        empresaId: empresaId,
        empresa: empresa,
        result: result
      });

      // Placeholder - implementar endpoint /conciliacao/efetivar
      // const response = await api.post('/conciliacao/efetivar', {
      //   conta_contabil: conta.conta_contabil,
      //   data_base: dataBase,
      //   empresa_id: empresaId,
      
      //   resultado: result
      // });

      alert('Conciliação efetivada com sucesso!');
      
      // Aguarda e volta para seleção
      setTimeout(() => {
        navigate('/conciliacoes/periodo');
      }, 1500);

    } catch (err) {
      console.error('❌ Erro ao efetivar:', err);
      alert('Erro ao efetivar conciliação');
    }
  };

  const allFilesUploaded = files.origem && files.contabil && files.geral
  const pendingCount = 3 - Object.values(files).filter(Boolean).length

  // Se não tem dados, não renderiza nada (useEffect vai redirecionar)
  if (!conta || !dataBase) {
    return null;
  }

  return (
    <div className="container">
      {/* Contexto da Conciliação - FIXO NO TOPO */}
      <div className="card" style={{ 
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 
        color: 'white',
        marginBottom: '1.5rem',
        position: 'sticky',
        top: '0',
        zIndex: 100,
        boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ margin: '0 0 0.5rem 0', fontSize: '1.5rem', fontWeight: '600' }}>
              🎯 Conciliação em Andamento
            </h2>
            <div style={{ display: 'flex', gap: '2rem', fontSize: '0.95rem' }}>
              <div>
                <strong>Conta:</strong> {conta.conta_contabil} - {conta.descricao}
              </div>
              <div>
                <strong>Data-Base:</strong> {dataBase}
              </div>
              {empresa && (
                <div>
                  <strong>Empresa:</strong> {empresa.codigo} - {empresa.nome}
                </div>
              )}
            </div>
          </div>
          <button 
            onClick={voltarParaSelecao}
            style={{
              background: 'rgba(255,255,255,0.2)',
              border: '1px solid rgba(255,255,255,0.3)',
              color: 'white',
              padding: '0.5rem 1rem',
              borderRadius: '0.5rem',
              cursor: 'pointer',
              fontSize: '0.875rem',
              fontWeight: '500',
              transition: 'all 0.2s'
            }}
            onMouseOver={(e) => e.target.style.background = 'rgba(255,255,255,0.3)'}
            onMouseOut={(e) => e.target.style.background = 'rgba(255,255,255,0.2)'}
          >
            ← Voltar
          </button>
        </div>
      </div>

      {/* Header */}
      <div className="header">
        <h1>📤 Módulo de Conciliações</h1>
        <p>Faça upload dos 3 arquivos para análise automatizada</p>
      </div>

      {/* Status Bar */}
      <div className="card status-bar">
        <div className="status-item">
          <div className={`status-dot ${files.origem ? 'active' : ''}`}></div>
          <span className={`status-label ${files.origem ? 'active' : ''}`}>Origem</span>
        </div>
        <div className="status-item">
          <div className={`status-dot ${files.contabil ? 'active' : ''}`}></div>
          <span className={`status-label ${files.contabil ? 'active' : ''}`}>Contábil</span>
        </div>
        <div className="status-item">
          <div className={`status-dot ${files.geral ? 'active' : ''}`}></div>
          <span className={`status-label ${files.geral ? 'active' : ''}`}>Base Geral</span>
        </div>
      </div>

      {/* Upload Cards */}
      <FileUploadCard
        type="origem"
        title="1. Arquivo Origem"
        description="origem.xlsx - Base de dados de origem (exemplo: financeir, faturamento, etc)"
        iconColor="#3b82f6"
        file={files.origem}
        onFileSelect={handleFileSelect}
        onRemove={removeFile}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        disabled={isProcessing}
      />

      <FileUploadCard
        type="contabil"
        title="2. Arquivo Contábil"
        description="contabilidade.xlsx - Saldos contábeis"
        iconColor="#22c55e"
        file={files.contabil}
        onFileSelect={handleFileSelect}
        onRemove={removeFile}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        disabled={isProcessing}
      />

      <FileUploadCard
        type="geral"
        title="3. Base Geral Contabilidade"
        description="base_geral.xlsx - Todos lançamentos contábeis detalhados"
        iconColor="#a855f7"
        file={files.geral}
        onFileSelect={handleFileSelect}
        onRemove={removeFile}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        disabled={isProcessing}
      />

      {/* Actions */}
      <div className="card actions-card">
        <div className="action-status">
          {allFilesUploaded ? (
            <>
              <svg width="24" height="24" fill="none" stroke="#22c55e" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
              </svg>
              <span style={{ color: '#22c55e' }}>Todos os arquivos prontos!</span>
            </>
          ) : (
            <>
              <svg width="24" height="24" fill="none" stroke="#6b7280" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{pendingCount} arquivo(s) pendente(s)</span>
            </>
          )}
        </div>
        <div className="action-buttons">
          <button 
            className="btn btn-ghost" 
            onClick={resetAll}
            disabled={isProcessing || (!files.origem && !files.contabil && !files.geral)}
          >
            Limpar Tudo
          </button>
          <button 
            className="btn btn-primary" 
            onClick={processFiles}
            disabled={!allFilesUploaded || isProcessing}
          >
            {isProcessing ? (
              <>
                <svg className="loading-spinner" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Processando...
              </>
            ) : (
              <>
                <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                Processar Conciliação
              </>
            )}
          </button>
        </div>
      </div>

      {/* Botão Efetivar Conciliação - Aparece após processamento */}
      {result && (
        <div className="card" style={{ 
          background: '#10b981', 
          padding: '1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ color: 'white' }}>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.25rem', fontWeight: '600' }}>
              ✅ Análise Concluída
            </h3>
            <p style={{ margin: 0, opacity: 0.9, fontSize: '0.95rem' }}>
              Revise os resultados e clique em "Efetivar" para confirmar a conciliação
            </p>
          </div>
          <button 
            onClick={efetivarConciliacao}
            style={{
              background: 'white',
              color: '#10b981',
              border: 'none',
              padding: '0.875rem 2rem',
              borderRadius: '0.5rem',
              fontSize: '1rem',
              fontWeight: '600',
              cursor: 'pointer',
              boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
              transition: 'all 0.2s'
            }}
            onMouseOver={(e) => {
              e.target.style.transform = 'translateY(-2px)';
              e.target.style.boxShadow = '0 6px 8px rgba(0,0,0,0.15)';
            }}
            onMouseOut={(e) => {
              e.target.style.transform = 'translateY(0)';
              e.target.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
            }}
          >
            Efetivar Conciliação
          </button>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="error-message">
          <strong>❌ Erro:</strong> {error}
        </div>
      )}

      {/* Result */}
      {result && <ResultDisplay result={result} />}

      {/* Info Box */}
      <div className="card info-card">
        <div className="info-content">
          <div className="info-icon">
            <svg width="24" height="24" fill="none" stroke="white" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="info-text">
            <h4>O que será processado?</h4>
            <ul>
              <li>Normalização automática das bases de dados</li>
              <li>Matching inteligente entre Financeiro e Contabilidade</li>
              <li>Identificação de diferenças e divergências</li>
              <li>Classificação por prazo (Longo/Curto prazo)</li>
              <li>Geração de relatório Excel com análise detalhada</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Conciliacoes;