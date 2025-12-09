import { useState } from 'react'; // Esta linha deve estar presente
import api from '../api/axiosConfig';
import '../assets/styles/App.css';
import FileUploadCard from '../components/FileUploadCard/FileUploadCard.jsx';
import ResultDisplay from '../components/ResultDisplay/ResultDisplay.jsx';

function Conciliacoes() {
  const [files, setFiles] = useState({
    origem: null,
    contabil: null,
    geral: null,
  })

  const [isProcessing, setIsProcessing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

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

  // Função para processar arquivos
  const processFiles = async () => {
    setIsProcessing(true)
    setError(null)
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('arquivo_origem', files.origem)
      formData.append('arquivo_contabil', files.contabil)
      formData.append('arquivo_geral_contabilidade', files.geral)

      console.log('📤 Enviando arquivos para API...')

      const response = await api.post('/conciliacao/processar', formData)

      console.log('✅ Resposta recebida:', response.data)
      setResult(response.data)

    } catch (err) {
      console.error('❌ Erro ao processar:', err)
      setError(
        err.response?.data?.detail || 
        err.message || 
        'Erro ao processar arquivos. Verifique se a API está rodando.'
      )
    } finally {
      setIsProcessing(false)
    }
  }

  const allFilesUploaded = files.origem && files.contabil && files.geral
  const pendingCount = 3 - Object.values(files).filter(Boolean).length

  return (
    <div className="container">
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
        title="1. Arquivo Origem (Financeiro)"
        description="financeiro.xlsx - Base de dados financeira com títulos a receber"
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
        description="fcontabilidade.xlsx - Saldos contábeis por cliente"
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
        description="base_geral.xlsx - Lançamentos contábeis detalhados"
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