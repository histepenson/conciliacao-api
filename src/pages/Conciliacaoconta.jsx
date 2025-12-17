import React, { useState, useEffect } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import axios from "axios"
import { toast } from "react-toastify"
import "./ConciliacaoConta.css"

function ConciliacaoConta() {
  const location = useLocation()
  const navigate = useNavigate()
  const { conta, dataBase, empresaId } = location.state || {}

  const [arquivos, setArquivos] = useState([])
  const [uploading, setUploading] = useState(false)
  const [analisando, setAnalisando] = useState(false)
  const [resultadoAnalise, setResultadoAnalise] = useState(null)
  const [dragActive, setDragActive] = useState(false)

  useEffect(() => {
    if (!conta || !dataBase || !empresaId) {
      toast.error("Dados de conciliação não encontrados")
      navigate("/conciliacoes/periodo")
    }
  }, [conta, dataBase, empresaId, navigate])

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files)
    }
  }

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files)
    }
  }

  const handleFiles = (fileList) => {
    const novosArquivos = Array.from(fileList).map((file) => ({
      file,
      nome: file.name,
      tamanho: file.size,
      tipo: file.type,
      id: Date.now() + Math.random()
    }))

    setArquivos((prev) => [...prev, ...novosArquivos])
    toast.success(`${novosArquivos.length} arquivo(s) adicionado(s)`)
  }

  const removerArquivo = (id) => {
    setArquivos((prev) => prev.filter((arq) => arq.id !== id))
    toast.info("Arquivo removido")
  }

  const formatarTamanho = (bytes) => {
    if (bytes === 0) return "0 Bytes"
    const k = 1024
    const sizes = ["Bytes", "KB", "MB", "GB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + " " + sizes[i]
  }

  const realizarUpload = async () => {
    if (arquivos.length === 0) {
      toast.warning("Adicione pelo menos um arquivo")
      return
    }

    setUploading(true)

    try {
      const formData = new FormData()
      arquivos.forEach((arq) => {
        formData.append("files", arq.file)
      })
      formData.append("conta_id", conta.id)
      formData.append("data_base", dataBase)
      formData.append("empresa_id", empresaId)

      const response = await axios.post(
        `${import.meta.env.VITE_API_URL}/conciliacoes/upload`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data"
          }
        }
      )

      toast.success("Arquivos enviados com sucesso!")
      analisarConciliacao(response.data.upload_id)
    } catch (error) {
      toast.error("Erro ao enviar arquivos")
      console.error(error)
    } finally {
      setUploading(false)
    }
  }

  const analisarConciliacao = async (uploadId) => {
    setAnalisando(true)

    try {
      const response = await axios.post(
        `${import.meta.env.VITE_API_URL}/conciliacoes/analisar`,
        {
          upload_id: uploadId,
          conta_id: conta.id,
          data_base: dataBase
        }
      )

      setResultadoAnalise(response.data)
      toast.success("Análise concluída!")
    } catch (error) {
      toast.error("Erro ao analisar conciliação")
      console.error(error)
    } finally {
      setAnalisando(false)
    }
  }

  const efetivarConciliacao = async () => {
    if (!resultadoAnalise) {
      toast.warning("Realize a análise antes de efetivar")
      return
    }

    try {
      await axios.post(
        `${import.meta.env.VITE_API_URL}/conciliacoes/efetivar`,
        {
          analise_id: resultadoAnalise.id,
          conta_id: conta.id,
          data_base: dataBase,
          empresa_id: empresaId
        }
      )

      toast.success("Conciliação efetivada com sucesso!")
      
      setTimeout(() => {
        navigate("/conciliacoes/periodo")
      }, 2000)
    } catch (error) {
      toast.error("Erro ao efetivar conciliação")
      console.error(error)
    }
  }

  const voltarParaLista = () => {
    navigate("/conciliacoes/periodo")
  }

  if (!conta) return null

  return (
    <div className="conciliacao-conta-container">
      {/* HEADER */}
      <div className="conciliacao-header">
        <button onClick={voltarParaLista} className="btn-voltar">
          ← Voltar
        </button>
        
        <div className="header-info">
          <h1>Conciliação de Conta</h1>
          <div className="info-badges">
            <div className="info-badge">
              <span className="badge-label">Conta:</span>
              <span className="badge-value">{conta.codigo} - {conta.descricao}</span>
            </div>
            <div className="info-badge">
              <span className="badge-label">Data-Base:</span>
              <span className="badge-value">{dataBase}</span>
            </div>
          </div>
        </div>
      </div>

      {/* UPLOAD AREA */}
      <div className="upload-section">
        <h2>Upload de Arquivos</h2>
        
        <div
          className={`dropzone ${dragActive ? "active" : ""}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <div className="dropzone-content">
            <span className="dropzone-icon">📁</span>
            <p className="dropzone-text">
              Arraste arquivos aqui ou clique para selecionar
            </p>
            <p className="dropzone-hint">
              Formatos suportados: XLSX, XLS, CSV
            </p>
            <input
              type="file"
              multiple
              accept=".xlsx,.xls,.csv"
              onChange={handleFileInput}
              className="file-input"
              id="fileInput"
            />
            <label htmlFor="fileInput" className="btn-selecionar">
              Selecionar Arquivos
            </label>
          </div>
        </div>

        {/* LISTA DE ARQUIVOS */}
        {arquivos.length > 0 && (
          <div className="arquivos-lista">
            <h3>Arquivos Selecionados ({arquivos.length})</h3>
            {arquivos.map((arq) => (
              <div key={arq.id} className="arquivo-item">
                <div className="arquivo-info">
                  <span className="arquivo-icon">📄</span>
                  <div className="arquivo-detalhes">
                    <p className="arquivo-nome">{arq.nome}</p>
                    <p className="arquivo-tamanho">{formatarTamanho(arq.tamanho)}</p>
                  </div>
                </div>
                <button
                  onClick={() => removerArquivo(arq.id)}
                  className="btn-remover"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="upload-actions">
          <button
            onClick={realizarUpload}
            disabled={arquivos.length === 0 || uploading || analisando}
            className="btn-upload"
          >
            {uploading ? "Enviando..." : "Enviar e Analisar"}
          </button>
        </div>
      </div>

      {/* ANÁLISE */}
      {analisando && (
        <div className="analise-loading">
          <div className="spinner"></div>
          <p>Analisando conciliação...</p>
        </div>
      )}

      {/* RESULTADO */}
      {resultadoAnalise && (
        <div className="resultado-section">
          <h2>Resultado da Análise</h2>
          
          <div className="resultado-cards">
            <div className="resultado-card">
              <span className="card-label">Total de Registros</span>
              <span className="card-value">{resultadoAnalise.total_registros}</span>
            </div>
            <div className="resultado-card">
              <span className="card-label">Valor Total</span>
              <span className="card-value">
                {new Intl.NumberFormat("pt-BR", {
                  style: "currency",
                  currency: "BRL"
                }).format(resultadoAnalise.valor_total || 0)}
              </span>
            </div>
            <div className="resultado-card success">
              <span className="card-label">Conciliados</span>
              <span className="card-value">{resultadoAnalise.conciliados}</span>
            </div>
            <div className="resultado-card warning">
              <span className="card-label">Pendentes</span>
              <span className="card-value">{resultadoAnalise.pendentes}</span>
            </div>
          </div>

          {resultadoAnalise.observacoes && (
            <div className="observacoes">
              <h3>Observações</h3>
              <p>{resultadoAnalise.observacoes}</p>
            </div>
          )}

          <div className="resultado-actions">
            <button
              onClick={efetivarConciliacao}
              className="btn-efetivar"
            >
              Efetivar Conciliação
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default ConciliacaoConta