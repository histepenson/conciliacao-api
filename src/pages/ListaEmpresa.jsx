import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';

import '../styles/form/form-base.css';
import '../styles/form/lista-base.css';

const API_URL = import.meta.env.VITE_API_URL;

export default function ListaEmpresas() {
  const navigate = useNavigate();
  
  // Estados
  const [empresas, setEmpresas] = useState([]);
  const [empresasFiltradas, setEmpresasFiltradas] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [empresaParaEditar, setEmpresaParaEditar] = useState(null);
  const [modalAberto, setModalAberto] = useState(false);
  const [formData, setFormData] = useState({ nome: '', cnpj: '', status: true });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Novos estados para filtros e busca
  const [termoBusca, setTermoBusca] = useState('');
  const [filtroStatus, setFiltroStatus] = useState('todos');
  const [ordenacao, setOrdenacao] = useState({ campo: 'nome', direcao: 'asc' });

  // Buscar empresas com melhor tratamento de erro
  const buscarEmpresas = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/empresas/`, {
        signal: AbortSignal.timeout(10000)
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `Erro ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setEmpresas(Array.isArray(data) ? data : []);
      setEmpresasFiltradas(Array.isArray(data) ? data : []);
    } catch (error) {
      if (error.name === 'TimeoutError') {
        toast.error('⏱️ Tempo de requisição excedido. Tente novamente.');
      } else if (error.name === 'AbortError') {
        toast.error('❌ Requisição cancelada.');
      } else {
        toast.error(`Erro ao carregar empresas: ${error.message}`);
      }
      setEmpresas([]);
      setEmpresasFiltradas([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    buscarEmpresas();
  }, [buscarEmpresas]);

  // Aplicar filtros e busca
  useEffect(() => {
    let resultado = [...empresas];

    // Filtro de busca por nome ou CNPJ
    if (termoBusca.trim()) {
      const termo = termoBusca.toLowerCase();
      resultado = resultado.filter(e => 
        e.nome.toLowerCase().includes(termo) || 
        e.cnpj.replace(/\D/g, '').includes(termo.replace(/\D/g, ''))
      );
    }

    // Filtro de status
    if (filtroStatus !== 'todos') {
      resultado = resultado.filter(e => 
        filtroStatus === 'ativo' ? e.status : !e.status
      );
    }

    // Ordenação
    resultado.sort((a, b) => {
      let valorA = a[ordenacao.campo];
      let valorB = b[ordenacao.campo];
      
      if (ordenacao.campo === 'nome') {
        valorA = valorA.toLowerCase();
        valorB = valorB.toLowerCase();
      }
      
      if (valorA < valorB) return ordenacao.direcao === 'asc' ? -1 : 1;
      if (valorA > valorB) return ordenacao.direcao === 'asc' ? 1 : -1;
      return 0;
    });

    setEmpresasFiltradas(resultado);
  }, [empresas, termoBusca, filtroStatus, ordenacao]);

  // Formatação de CNPJ
  const formatCNPJ = useCallback((value) => {
    return value.replace(/\D/g, '')
      .replace(/(\d{2})(\d)/, "$1.$2")
      .replace(/(\d{3})(\d)/, "$1.$2")
      .replace(/(\d{3})(\d)/, "$1/$2")
      .replace(/(\d{4})(\d)/, "$1-$2")
      .slice(0, 18);
  }, []);

  const formatCNPJDisplay = useCallback((cnpj) => {
    return cnpj ? formatCNPJ(cnpj.replace(/\D/g, "")) : '';
  }, [formatCNPJ]);

  // Validação de CNPJ com algoritmo completo
  const validateCNPJ = useCallback((cnpj) => {
    const digits = cnpj.replace(/\D/g, "");
    
    if (digits.length !== 14) return "CNPJ deve ter 14 dígitos";
    if (/^(\d)\1{13}$/.test(digits)) return "CNPJ inválido";
    
    // Validação dos dígitos verificadores
    let tamanho = digits.length - 2;
    let numeros = digits.substring(0, tamanho);
    const digitos = digits.substring(tamanho);
    let soma = 0;
    let pos = tamanho - 7;
    
    for (let i = tamanho; i >= 1; i--) {
      soma += numeros.charAt(tamanho - i) * pos--;
      if (pos < 2) pos = 9;
    }
    
    let resultado = soma % 11 < 2 ? 0 : 11 - soma % 11;
    if (resultado != digitos.charAt(0)) return "CNPJ inválido";
    
    tamanho = tamanho + 1;
    numeros = digits.substring(0, tamanho);
    soma = 0;
    pos = tamanho - 7;
    
    for (let i = tamanho; i >= 1; i--) {
      soma += numeros.charAt(tamanho - i) * pos--;
      if (pos < 2) pos = 9;
    }
    
    resultado = soma % 11 < 2 ? 0 : 11 - soma % 11;
    if (resultado != digitos.charAt(1)) return "CNPJ inválido";
    
    return null;
  }, []);

  // Validação do formulário
  const validateForm = useCallback(() => {
    const newErrors = {};
    
    if (!formData.nome.trim()) {
      newErrors.nome = "Nome é obrigatório";
    } else if (formData.nome.trim().length < 3) {
      newErrors.nome = "Nome deve ter pelo menos 3 caracteres";
    } else if (formData.nome.trim().length > 100) {
      newErrors.nome = "Nome deve ter no máximo 100 caracteres";
    }
    
    if (!formData.cnpj.trim()) {
      newErrors.cnpj = "CNPJ é obrigatório";
    } else {
      const cnpjError = validateCNPJ(formData.cnpj);
      if (cnpjError) newErrors.cnpj = cnpjError;
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData, validateCNPJ]);

  // Handlers
  const abrirModalEdicao = useCallback((empresa) => {
    setEmpresaParaEditar(empresa);
    setFormData({
      nome: empresa.nome,
      cnpj: formatCNPJDisplay(empresa.cnpj),
      status: empresa.status
    });
    setModalAberto(true);
    setErrors({});
  }, [formatCNPJDisplay]);

  const fecharModal = useCallback(() => {
    if (isSubmitting) return;
    setModalAberto(false);
    setEmpresaParaEditar(null);
    setFormData({ nome: '', cnpj: '', status: true });
    setErrors({});
  }, [isSubmitting]);

  const handleChange = useCallback((e) => {
    const { name, value, type } = e.target;
    let val = value;
    
    if (name === "cnpj") {
      val = formatCNPJ(value);
    } else if (type === "select-one" && name === "status") {
      val = value === "true";
    }
    
    setFormData(prev => ({ ...prev, [name]: val }));
    
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: null }));
    }
  }, [formatCNPJ, errors]);

  const handleSubmitEdicao = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      toast.error("❌ Corrija os erros antes de continuar");
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const response = await fetch(
        `${API_URL}/empresas/${empresaParaEditar.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nome: formData.nome.trim(),
            cnpj: formData.cnpj.replace(/\D/g, ""),
            status: formData.status === true || formData.status === "true",
            updated_at: new Date().toISOString()
          }),
          signal: AbortSignal.timeout(10000)
        }
      );
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || 'Erro ao atualizar empresa');
      }
      
      toast.success("✅ Empresa atualizada com sucesso!");
      fecharModal();
      buscarEmpresas();
    } catch (err) {
      if (err.name === 'TimeoutError') {
        toast.error('⏱️ Tempo de requisição excedido. Tente novamente.');
      } else {
        toast.error(`❌ ${err.message}`);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const excluirEmpresa = async (id, nome) => {
    const confirmacao = window.confirm(
      `⚠️ Tem certeza que deseja excluir a empresa "${nome}"?\n\nEsta ação não pode ser desfeita.`
    );
    
    if (!confirmacao) return;
    
    const toastId = toast.loading('Excluindo empresa...');
    
    try {
      const response = await fetch(`${API_URL}/empresas/${id}`, {
        method: 'DELETE',
        signal: AbortSignal.timeout(10000)
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || 'Erro ao excluir empresa');
      }
      
      toast.success('🗑️ Empresa excluída com sucesso!', { id: toastId });
      buscarEmpresas();
    } catch (err) {
      if (err.name === 'TimeoutError') {
        toast.error('⏱️ Tempo de requisição excedido.', { id: toastId });
      } else {
        toast.error(`❌ ${err.message}`, { id: toastId });
      }
    }
  };

  const alternarOrdenacao = (campo) => {
    setOrdenacao(prev => ({
      campo,
      direcao: prev.campo === campo && prev.direcao === 'asc' ? 'desc' : 'asc'
    }));
  };

  const limparFiltros = () => {
    setTermoBusca('');
    setFiltroStatus('todos');
    setOrdenacao({ campo: 'nome', direcao: 'asc' });
  };

  // Estatísticas das empresas
  const estatisticas = useMemo(() => {
    const total = empresas.length;
    const ativas = empresas.filter(e => e.status).length;
    const inativas = total - ativas;
    return { total, ativas, inativas };
  }, [empresas]);

  // Teclas de atalho
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && modalAberto && !isSubmitting) {
        fecharModal();
      }
      if (e.ctrlKey && e.key === 'n' && !modalAberto) {
        e.preventDefault();
        navigate('/cadastros/empresas/novo');
      }
      if (e.ctrlKey && e.key === 'r' && !isLoading) {
        e.preventDefault();
        buscarEmpresas();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [modalAberto, isSubmitting, isLoading, fecharModal, navigate, buscarEmpresas]);

  return (
    <div className="lista-container">
      <div className="lista-header">
        <div>
          <h1>Empresas</h1>
          <p className="lista-subtitle">
            Gerencie todas as empresas cadastradas no sistema
          </p>
        </div>
        
        {/* Estatísticas */}
        <div className="stats-cards">
          <div className="stat-card">
            <span className="stat-label">Total</span>
            <span className="stat-value">{estatisticas.total}</span>
          </div>
          <div className="stat-card stat-success">
            <span className="stat-label">Ativas</span>
            <span className="stat-value">{estatisticas.ativas}</span>
          </div>
          <div className="stat-card stat-danger">
            <span className="stat-label">Inativas</span>
            <span className="stat-value">{estatisticas.inativas}</span>
          </div>
        </div>
      </div>

      <div className="lista-actions">
        <button
          className="lista-button lista-button-primary"
          onClick={() => navigate('/cadastros/empresas/novo')}
          title="Atalho: Ctrl+N"
        >
          ➕ Nova Empresa
        </button>
        <button
          className="lista-button lista-button-secondary"
          onClick={buscarEmpresas}
          disabled={isLoading}
          title="Atalho: Ctrl+R"
        >
          {isLoading ? '⏳' : '🔄'} Atualizar
        </button>
      </div>

      {/* Filtros e Busca */}
      <div className="filtros-container">
        <div className="filtro-busca">
          <input
            type="text"
            placeholder="🔍 Buscar por nome ou CNPJ..."
            value={termoBusca}
            onChange={(e) => setTermoBusca(e.target.value)}
            className="input-busca"
          />
        </div>
        
        <div className="filtro-status">
          <label>Status:</label>
          <select
            value={filtroStatus}
            onChange={(e) => setFiltroStatus(e.target.value)}
            className="select-filtro"
          >
            <option value="todos">Todos</option>
            <option value="ativo">✅ Apenas Ativos</option>
            <option value="inativo">❌ Apenas Inativos</option>
          </select>
        </div>

        {(termoBusca || filtroStatus !== 'todos') && (
          <button
            className="lista-button lista-button-ghost"
            onClick={limparFiltros}
          >
            ✖️ Limpar Filtros
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p className="loading-text">Carregando empresas...</p>
        </div>
      ) : empresas.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🏢</div>
          <h3>Nenhuma empresa cadastrada</h3>
          <p>Comece cadastrando sua primeira empresa no sistema</p>
          <button
            className="lista-button lista-button-primary"
            onClick={() => navigate('/cadastros/empresas/novo')}
          >
            ➕ Cadastrar primeira empresa
          </button>
        </div>
      ) : empresasFiltradas.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🔍</div>
          <h3>Nenhum resultado encontrado</h3>
          <p>Tente ajustar os filtros de busca</p>
          <button
            className="lista-button lista-button-secondary"
            onClick={limparFiltros}
          >
            ✖️ Limpar Filtros
          </button>
        </div>
      ) : (
        <>
          <div className="results-info">
            Exibindo <strong>{empresasFiltradas.length}</strong> de <strong>{empresas.length}</strong> empresas
          </div>
          
          <div className="lista-table-container">
            <table className="lista-table">
              <thead>
                <tr>
                  <th 
                    onClick={() => alternarOrdenacao('id')}
                    className="sortable"
                    style={{ width: '80px' }}
                  >
                    ID {ordenacao.campo === 'id' && (ordenacao.direcao === 'asc' ? '↑' : '↓')}
                  </th>
                  <th 
                    onClick={() => alternarOrdenacao('nome')}
                    className="sortable"
                  >
                    Nome {ordenacao.campo === 'nome' && (ordenacao.direcao === 'asc' ? '↑' : '↓')}
                  </th>
                  <th 
                    onClick={() => alternarOrdenacao('cnpj')}
                    className="sortable"
                  >
                    CNPJ {ordenacao.campo === 'cnpj' && (ordenacao.direcao === 'asc' ? '↑' : '↓')}
                  </th>
                  <th 
                    onClick={() => alternarOrdenacao('status')}
                    className="sortable"
                  >
                    Status {ordenacao.campo === 'status' && (ordenacao.direcao === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="actions-column">Ações</th>
                </tr>
              </thead>
              <tbody>
                {empresasFiltradas.map(e => (
                  <tr key={e.id} className="table-row-hover">
                    <td style={{ fontWeight: '600', color: '#6366f1' }}>{e.id}</td>
                    <td className="empresa-nome">{e.nome}</td>
                    <td className="monospace">{formatCNPJDisplay(e.cnpj)}</td>
                    <td>
                      <span className={`status-badge ${e.status ? 'status-ativo' : 'status-inativo'}`}>
                        {e.status ? '✅ Ativo' : '❌ Inativo'}
                      </span>
                    </td>
                    <td className="table-actions">
                      <button
                        className="table-action-button table-action-button-edit"
                        onClick={() => abrirModalEdicao(e)}
                        title="Editar empresa"
                      >
                        ✏️ Editar
                      </button>
                      <button
                        className="table-action-button table-action-button-delete"
                        onClick={() => excluirEmpresa(e.id, e.nome)}
                        title="Excluir empresa"
                      >
                        🗑️ Excluir
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Modal de Edição */}
      {modalAberto && (
        <div className="modal-backdrop" onClick={(e) => {
          if (e.target === e.currentTarget && !isSubmitting) fecharModal();
        }}>
          <div className="modal-container">
            <div className="modal-header">
              <h2 className="modal-title">✏️ Editar Empresa</h2>
              <button
                className="modal-close"
                onClick={fecharModal}
                disabled={isSubmitting}
                aria-label="Fechar modal"
              >
                ×
              </button>
            </div>
            
            <form onSubmit={handleSubmitEdicao}>
              <div className="modal-body">
                <div className="form-field">
                  <label htmlFor="id">Código da Empresa</label>
                  <input
                    id="id"
                    type="text"
                    value={empresaParaEditar?.id || ''}
                    disabled
                    style={{ 
                      backgroundColor: '#f3f4f6', 
                      cursor: 'not-allowed',
                      fontWeight: '600',
                      color: '#6366f1'
                    }}
                  />
                </div>

                <div className="form-field">
                  <label htmlFor="nome">Nome da Empresa *</label>
                  <input
                    id="nome"
                    type="text"
                    name="nome"
                    value={formData.nome}
                    onChange={handleChange}
                    className={errors.nome ? "input-error" : ""}
                    placeholder="Digite o nome da empresa"
                    disabled={isSubmitting}
                    autoFocus
                    maxLength={100}
                  />
                  {errors.nome && (
                    <span className="error-text" role="alert">
                      ⚠️ {errors.nome}
                    </span>
                  )}
                </div>

                <div className="form-field">
                  <label htmlFor="cnpj">CNPJ *</label>
                  <input
                    id="cnpj"
                    type="text"
                    name="cnpj"
                    value={formData.cnpj}
                    onChange={handleChange}
                    maxLength={18}
                    className={errors.cnpj ? "input-error" : ""}
                    placeholder="00.000.000/0000-00"
                    disabled={isSubmitting}
                  />
                  {errors.cnpj && (
                    <span className="error-text" role="alert">
                      ⚠️ {errors.cnpj}
                    </span>
                  )}
                </div>

                <div className="form-field">
                  <label htmlFor="status">Status</label>
                  <select
                    id="status"
                    name="status"
                    value={formData.status.toString()}
                    onChange={handleChange}
                    disabled={isSubmitting}
                  >
                    <option value="true">✅ Ativo</option>
                    <option value="false">❌ Inativo</option>
                  </select>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={fecharModal}
                  disabled={isSubmitting}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="primary-button"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? '⏳ Salvando...' : '💾 Salvar Alterações'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}