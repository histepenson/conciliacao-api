import React, { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import axios from "axios"
import toast from "react-hot-toast"
import '../styles/ConciliarPeriodo.css';
function ConciliarPeriodo() {
  const navigate = useNavigate()
  const [dataBase, setDataBase] = useState("")
  const [contas, setContas] = useState([])
  const [loading, setLoading] = useState(false)
  const [empresaSelecionada, setEmpresaSelecionada] = useState("")
  const [empresas, setEmpresas] = useState([])

  useEffect(() => {
    carregarEmpresas()
  }, [])

  useEffect(() => {
    if (empresaSelecionada) {
      carregarContas()
    }
  }, [empresaSelecionada])

  const carregarEmpresas = async () => {
    try {
      const response = await axios.get(`${import.meta.env.VITE_API_URL}/empresas`)
      setEmpresas(response.data)
    } catch (error) {
      toast.error("Erro ao carregar empresas")
      console.error(error)
    }
  }

  const carregarContas = async () => {
    setLoading(true)
    try {
      const response = await axios.get(
        `${import.meta.env.VITE_API_URL}/plano-contas?empresa_id=${empresaSelecionada}`
      )
      setContas(response.data)
    } catch (error) {
      toast.error("Erro ao carregar contas contábeis")
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const validarDataFechamento = (dataStr) => {
    // Valida formato DD/MM/AAAA
    const regex = /^\d{2}\/\d{2}\/\d{4}$/
    if (!regex.test(dataStr)) {
      return { valido: false, mensagem: "Data inválida. Use o formato DD/MM/AAAA" }
    }

    // Extrai dia, mês e ano
    const [dia, mes, ano] = dataStr.split('/').map(Number)
    
    // Valida se é uma data válida
    const data = new Date(ano, mes - 1, dia)
    if (data.getDate() !== dia || data.getMonth() !== mes - 1 || data.getFullYear() !== ano) {
      return { valido: false, mensagem: "Data inválida" }
    }

    // Verifica se é o último dia do mês
    const ultimoDiaMes = new Date(ano, mes, 0).getDate()
    if (dia !== ultimoDiaMes) {
      return { 
        valido: false, 
        mensagem: `A data deve ser o último dia do mês. Para ${mes.toString().padStart(2, '0')}/${ano}, use ${ultimoDiaMes.toString().padStart(2, '0')}/${mes.toString().padStart(2, '0')}/${ano}` 
      }
    }

    return { valido: true }
  }

  const handleConciliar = (conta) => {
    if (!dataBase) {
      toast.warning("Informe a data-base da conciliação")
      return
    }

    // Valida se é uma data de fechamento (último dia do mês)
    const validacao = validarDataFechamento(dataBase)
    if (!validacao.valido) {
      toast.error(validacao.mensagem)
      return
    }

    // Navega para página de conciliação passando os dados
    navigate("/conciliacoes", {
      state: {
        conta: conta,
        dataBase: dataBase,
        empresaId: empresaSelecionada,
        empresa: empresas.find(e => e.id === parseInt(empresaSelecionada))
      }
    })
  }

  const formatarDataParaBR = () => {
    const hoje = new Date()
    const dia = String(hoje.getDate()).padStart(2, "0")
    const mes = String(hoje.getMonth() + 1).padStart(2, "0")
    const ano = hoje.getFullYear()
    return `${dia}/${mes}/${ano}`
  }

  const preencherUltimoDiaMes = () => {
    const hoje = new Date()
    const ano = hoje.getFullYear()
    const mes = hoje.getMonth() + 1
    
    // Obtém o último dia do mês atual
    const ultimoDia = new Date(ano, mes, 0).getDate()
    
    setDataBase(`${String(ultimoDia).padStart(2, "0")}/${String(mes).padStart(2, "0")}/${ano}`)
  }

  return (
    <div className="conciliar-periodo-container">
      <div className="page-header">
        <h1>Conciliar Período</h1>
        <p>Selecione a empresa, informe a data-base e escolha as contas para conciliação</p>
      </div>

      <div className="filtros-container">
        <div className="filtro-grupo">
          <label>Empresa</label>
          <select
            value={empresaSelecionada}
            onChange={(e) => setEmpresaSelecionada(e.target.value)}
            className="filtro-select"
          >
            <option value="">Selecione uma empresa</option>
            {empresas.map((empresa) => (
              <option key={empresa.id} value={empresa.id}>
                {empresa.codigo} - {empresa.nome}
              </option>
            ))}
          </select>
        </div>

        <div className="filtro-grupo">
          <label>Data-Base da Conciliação</label>
          <div className="data-input-group">
            <input
              type="text"
              placeholder="DD/MM/AAAA"
              value={dataBase}
              onChange={(e) => setDataBase(e.target.value)}
              maxLength={10}
              className="data-input"
            />
            <button onClick={preencherUltimoDiaMes} className="btn-hoje" title="Preencher com último dia do mês atual">
              Mês Atual
            </button>
          </div>
        </div>
      </div>
      
      <div className="helper-text-container">
        <small className="helper-text">
          ⚠️ Informe o último dia do mês (ex: 31/12/2025, 30/11/2025)
        </small>
      </div>

      {loading ? (
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Carregando contas contábeis...</p>
        </div>
      ) : (
        <>
          {empresaSelecionada && contas.length > 0 && (
            <div className="contas-container">
              <div className="contas-header">
                <h2>Contas Contábeis</h2>
                <span className="contas-count">
                  {contas.filter((c) => c.conciliavel).length} conta(s) conciliável(is)
                </span>
              </div>

              <div className="contas-lista">
                {contas.map((conta) => (
                  <div
                    key={conta.id}
                    className={`conta-item ${conta.conciliavel ? "conciliavel" : ""}`}
                  >
                    <div className="conta-info">
                      <div className="conta-codigo">
                        {conta.conta_contabil}
                      </div>
                      <div className="conta-detalhes">
                        <h3>{conta.descricao}</h3>
                        {conta.conciliavel && (
                          <span className="badge-conciliavel">Conciliável</span>
                        )}
                      </div>
                    </div>

                    {conta.conciliavel && (
                      <button
                        onClick={() => handleConciliar(conta)}
                        className="btn-conciliar"
                        disabled={!dataBase}
                      >
                        Conciliar
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {empresaSelecionada && contas.length === 0 && (
            <div className="empty-state">
              <span className="empty-icon">📋</span>
              <h3>Nenhuma conta cadastrada</h3>
              <p>Cadastre contas contábeis para esta empresa</p>
            </div>
          )}

          {!empresaSelecionada && (
            <div className="empty-state">
              <span className="empty-icon">🏢</span>
              <h3>Selecione uma empresa</h3>
              <p>Escolha uma empresa para visualizar as contas contábeis</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default ConciliarPeriodo