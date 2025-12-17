import React, { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from 'react-hot-toast';

// Importar os mesmos estilos da tela de empresas
import '../styles/form/form-base.css';
import '../styles/form/lista-base.css';

const API_URL = import.meta.env.VITE_API_URL;

export default function PlanoContasPage() {
    // Estados
    const [empresaId, setEmpresaId] = useState(null);
    const [empresas, setEmpresas] = useState([]);
    const [lista, setLista] = useState([]);
    const [listaFiltrada, setListaFiltrada] = useState([]);
    const [loading, setLoading] = useState(false);
    const [busca, setBusca] = useState("");
    const [modalAberto, setModalAberto] = useState(false);
    const [modalImportacao, setModalImportacao] = useState(false);
    const [editando, setEditando] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const [form, setForm] = useState({
        conta_contabil: "",
        tipo_conta: "", // 1 = Analítica | 2 = Sintética
        descricao: "",
        conciliavel: false,
        conta_superior: null,
    });


    const [errors, setErrors] = useState({});
    const [arquivo, setArquivo] = useState(null);
    const [uploading, setUploading] = useState(false);

    // Filtros
    const [filtroConciliavel, setFiltroConciliavel] = useState('todos');

    // Buscar empresas disponíveis
    const buscarEmpresas = useCallback(async () => {
        try {
            const res = await axios.get(`${API_URL}/empresas/`, { timeout: 10000 });
            const listaEmpresas = Array.isArray(res.data) ? res.data : [];
            setEmpresas(listaEmpresas);
            
            // Define a primeira empresa como padrão
            if (listaEmpresas.length > 0 && !empresaId) {
                setEmpresaId(listaEmpresas[0].id);
            } else if (listaEmpresas.length === 0) {
                toast.error('⚠️ Nenhuma empresa cadastrada! Cadastre uma empresa primeiro.');
            }
        } catch (error) {
            toast.error('Erro ao carregar empresas');
            setEmpresas([]);
        }
    }, [empresaId]);

    useEffect(() => {
        buscarEmpresas();
    }, [buscarEmpresas]);

    // Carregar dados
    const carregar = useCallback(async () => {
        if (!empresaId) return; // Não carrega se não tiver empresa selecionada
        
        setLoading(true);
        try {
            const res = await axios.get(
                `${API_URL}/plano-contas/`,
                { 
                    params: { empresa_id: empresaId, limit: 1000 },
                    timeout: 10000 
                }
            );
            setLista(Array.isArray(res.data) ? res.data : []);
            setListaFiltrada(Array.isArray(res.data) ? res.data : []);
        } catch (error) {
            toast.error(`Erro ao carregar plano de contas: ${error.response?.data?.detail || error.message}`);
            setLista([]);
            setListaFiltrada([]);
        } finally {
            setLoading(false);
        }
    }, [empresaId]);

    useEffect(() => {
        if (empresaId) {
            carregar();
        }
    }, [carregar, empresaId]);

    // Aplicar filtros
    useEffect(() => {
        let resultado = [...lista];

        // Filtro de busca
        if (busca.trim()) {
            const termo = busca.toLowerCase();
            resultado = resultado.filter(item =>
                item.conta_contabil.toLowerCase().includes(termo) ||
                item.tipo_conta.toLowerCase().includes(termo)
            );
        }

        // Filtro de conciliável
        if (filtroConciliavel !== 'todos') {
            resultado = resultado.filter(item =>
                filtroConciliavel === 'sim' ? item.conciliavel : !item.conciliavel
            );
        }

        setListaFiltrada(resultado);
    }, [lista, busca, filtroConciliavel]);

    // Validação
    const validateForm = useCallback(() => {
        const newErrors = {};

        if (!form.conta_contabil.trim()) {
            newErrors.conta_contabil = "Conta contábil é obrigatória";
        } else if (form.conta_contabil.trim().length < 2) {
            newErrors.conta_contabil = "Conta contábil deve ter pelo menos 2 caracteres";
        }

        if (!form.tipo_conta.trim()) {
            newErrors.tipo_conta = "Tipo da conta é obrigatório";
        }

        if (!form.tipo_conta) {
            newErrors.tipo_conta = "Tipo da conta é obrigatório";
        }

        if (!form.descricao.trim()) {
            newErrors.descricao = "Descrição é obrigatória";
        }
        if (!form.tipo_conta) {
        newErrors.tipo_conta = "Tipo da conta é obrigatório";
        }

        if (!form.descricao.trim()) {
            newErrors.descricao = "Descrição é obrigatória";
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    }, [form]);

    // Handlers
    const abrirModalCadastro = useCallback(() => {
    setForm({
        conta_contabil: "",
        tipo_conta: "",
        descricao: "",
        conciliavel: false,
        conta_superior: null,
    });
    setErrors({});
    setModalAberto(true);
    setEditando(null);
}, []);


    const abrirModalEdicao = useCallback((item) => {
    setForm({
        conta_contabil: item.conta_contabil,
        tipo_conta: String(item.tipo_conta),
        descricao: item.descricao || "",
        conciliavel: item.conciliavel,
        conta_superior: item.conta_superior,
    });
    setErrors({});
    setEditando(item);
    setModalAberto(true);
}, []);


    const fecharModal = useCallback(() => {
        if (isSubmitting || uploading) return;
        setModalAberto(false);
        setModalImportacao(false);
        setEditando(null);
        setForm({
            conta_contabil: "",
            tipo_conta: "",
            conciliavel: false,
            conta_superior: null,
        });
        setErrors({});
        setArquivo(null);
    }, [isSubmitting, uploading]);

    const handleChange = useCallback((e) => {
        const { name, value, type } = e.target;
        let val = value;

        if (type === "select-one" && name === "conciliavel") {
            val = value === "true";
        } else if (name === "conta_superior") {
            val = value || null;
        }

        setForm(prev => ({ ...prev, [name]: val }));

        if (errors[name]) {
            setErrors(prev => ({ ...prev, [name]: null }));
        }
    }, [errors]);

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!validateForm()) {
            toast.error("❌ Corrija os erros antes de continuar");
            return;
        }

        setIsSubmitting(true);

        try {
            if (editando) {
                await axios.put(
                    `${API_URL}/plano-contas/${editando.id}`,
                    { ...form, empresa_id: empresaId },
                    { timeout: 10000 }
                );
                toast.success("✅ Conta atualizada com sucesso!");
            } else {
                await axios.post(
                    `${API_URL}/plano-contas/`,
                    { ...form, empresa_id: empresaId },
                    { timeout: 10000 }
                );
                toast.success("✅ Conta cadastrada com sucesso!");
            }

            fecharModal();
            carregar();
        } catch (error) {
            const errorMsg = error.response?.data?.detail || error.message;
            toast.error(`❌ ${errorMsg}`);
        } finally {
            setIsSubmitting(false);
        }
    };

    const importar = async () => {
    if (!arquivo) {
        toast.error("❌ Selecione um arquivo Excel!");
        return;
    }

    const formData = new FormData();
    formData.append("file", arquivo);
    formData.append("empresa_id", empresaId);

    setUploading(true);
    const toastId = toast.loading('⏳ Importando arquivo, aguarde...');

    try {
        const response = await axios.post(
            `${API_URL}/plano-contas/importar`,
            formData,
            {
                headers: { "Content-Type": "multipart/form-data" },
                timeout: 300000
            }
        );
        
        const resultado = response.data;
        
        // Fechar o toast de loading
        toast.dismiss(toastId);
        
        // Mensagem de sucesso detalhada
        const mensagemSucesso = `
✅ Importação concluída com sucesso!

📊 Resumo:
- ${resultado.importados} contas importadas
- ${resultado.atualizados} contas atualizadas
- ${resultado.erros} erros encontrados
        `.trim();
        
        toast.success(mensagemSucesso, { 
            duration: 8000, // 8 segundos
            style: {
                minWidth: '300px',
                whiteSpace: 'pre-line'
            }
        });

        // Se houver erros, mostrar detalhes
        if (resultado.erros > 0 && resultado.detalhes_erros && resultado.detalhes_erros.length > 0) {
            setTimeout(() => {
                const errosFormatados = resultado.detalhes_erros.slice(0, 5).join('\n');
                const mensagemErro = resultado.detalhes_erros.length > 5 
                    ? `${errosFormatados}\n\n... e mais ${resultado.detalhes_erros.length - 5} erros. Verifique o console para detalhes completos.`
                    : errosFormatados;
                
                toast.error(`⚠️ Erros encontrados:\n\n${mensagemErro}`, {
                    duration: 10000, // 10 segundos
                    style: {
                        minWidth: '400px',
                        whiteSpace: 'pre-line'
                    }
                });
                
                console.warn("📋 Detalhes completos dos erros:", resultado.detalhes_erros);
            }, 1000);
        }

        // Fechar modal e recarregar
        fecharModal();
        await carregar();
        
    } catch (error) {
        toast.dismiss(toastId);
        const errorMsg = error.response?.data?.detail || error.message;
        toast.error(`❌ Erro na importação:\n${errorMsg}`, {
            duration: 8000,
            style: {
                minWidth: '300px',
                whiteSpace: 'pre-line'
            }
        });
        console.error("Erro completo:", error.response?.data || error);
    } finally {
        setUploading(false);
    }
};

    const excluirConta = async (id, conta) => {
        const confirmacao = window.confirm(
            `⚠️ Tem certeza que deseja excluir a conta "${conta}"?\n\nEsta ação não pode ser desfeita.`
        );

        if (!confirmacao) return;

        const toastId = toast.loading('Excluindo conta...');

        try {
            await axios.delete(
                `${API_URL}/plano-contas/${id}`,
                { timeout: 10000 }
            );
            toast.success('🗑️ Conta excluída com sucesso!', { id: toastId });
            carregar();
        } catch (error) {
            const errorMsg = error.response?.data?.detail || error.message;
            toast.error(`❌ ${errorMsg}`, { id: toastId });
        }
    };

    const limparFiltros = () => {
        setBusca('');
        setFiltroConciliavel('todos');
    };

    // Estatísticas
    const estatisticas = useMemo(() => {
        const total = lista.length;
        const conciliaveis = lista.filter(c => c.conciliavel).length;
        const naoConciliaveis = total - conciliaveis;
        return { total, conciliaveis, naoConciliaveis };
    }, [lista]);

    // Teclas de atalho
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape' && (modalAberto || modalImportacao) && !isSubmitting && !uploading) {
                fecharModal();
            }
            if (e.ctrlKey && e.key === 'n' && !modalAberto && !modalImportacao) {
                e.preventDefault();
                abrirModalCadastro();
            }
            if (e.ctrlKey && e.key === 'r' && !loading) {
                e.preventDefault();
                carregar();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [modalAberto, modalImportacao, isSubmitting, uploading, loading, fecharModal, abrirModalCadastro, carregar]);

    // Encontrar empresa selecionada
    const empresaSelecionada = empresas.find(e => e.id === empresaId);

    return (
        <div className="lista-container">
            <div className="lista-header">
                <div>
                    <h1>Plano de Contas</h1>
                    <p className="lista-subtitle">
                        Gerencie o plano de contas contábeis da empresa
                    </p>
                </div>

                {/* Estatísticas */}
                <div className="stats-cards">
                    <div className="stat-card">
                        <span className="stat-label">Total</span>
                        <span className="stat-value">{estatisticas.total}</span>
                    </div>
                    <div className="stat-card stat-success">
                        <span className="stat-label">Conciliáveis</span>
                        <span className="stat-value">{estatisticas.conciliaveis}</span>
                    </div>
                    <div className="stat-card stat-danger">
                        <span className="stat-label">Não Conciliáveis</span>
                        <span className="stat-value">{estatisticas.naoConciliaveis}</span>
                    </div>
                </div>
            </div>

            <div className="lista-actions">
                {empresas.length > 0 && (
                    <div className="filtro-status" style={{ marginRight: '12px' }}>
                        <label>Empresa:</label>
                        <select
                            value={empresaId || ''}
                            onChange={(e) => setEmpresaId(Number(e.target.value))}
                            className="select-filtro"
                        >
                            {empresas.map(emp => (
                                <option key={emp.id} value={emp.id}>
                                    {emp.id} - {emp.nome}
                                </option>
                            ))}
                        </select>
                    </div>
                )}
                
                <button
                    className="lista-button lista-button-primary"
                    onClick={abrirModalCadastro}
                    title="Atalho: Ctrl+N"
                    disabled={!empresaId}
                >
                    ➕ Nova Conta
                </button>
                <button
                    className="lista-button lista-button-secondary"
                    onClick={() => setModalImportacao(true)}
                    disabled={!empresaId}
                >
                    📥 Importar Balancete
                </button>
                <button
                    className="lista-button lista-button-secondary"
                    onClick={carregar}
                    disabled={loading || !empresaId}
                    title="Atalho: Ctrl+R"
                >
                    {loading ? '⏳' : '🔄'} Atualizar
                </button>
            </div>

            {/* Filtros e Busca */}
            <div className="filtros-container">
                <div className="filtro-busca">
                    <input
                        type="text"
                        placeholder="🔍 Buscar por conta ou tipo..."
                        value={busca}
                        onChange={(e) => setBusca(e.target.value)}
                        className="input-busca"
                    />
                </div>

                <div className="filtro-status">
                    <label>Conciliável:</label>
                    <select
                        value={filtroConciliavel}
                        onChange={(e) => setFiltroConciliavel(e.target.value)}
                        className="select-filtro"
                    >
                        <option value="todos">Todos</option>
                        <option value="sim">✅ Apenas Sim</option>
                        <option value="nao">❌ Apenas Não</option>
                    </select>
                </div>

                {(busca || filtroConciliavel !== 'todos') && (
                    <button
                        className="lista-button lista-button-ghost"
                        onClick={limparFiltros}
                    >
                        ✖️ Limpar Filtros
                    </button>
                )}
            </div>

            {loading ? (
                <div className="loading-container">
                    <div className="loading-spinner"></div>
                    <p className="loading-text">Carregando plano de contas...</p>
                </div>
            ) : !empresaId ? (
                <div className="empty-state">
                    <div className="empty-icon">🏢</div>
                    <h3>Nenhuma empresa selecionada</h3>
                    <p>Cadastre uma empresa primeiro para gerenciar o plano de contas</p>
                    <button
                        className="lista-button lista-button-primary"
                        onClick={() => window.location.href = '/cadastros/empresas/novo'}
                    >
                        ➕ Cadastrar Empresa
                    </button>
                </div>
            ) : lista.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-icon">📊</div>
                    <h3>Nenhuma conta cadastrada</h3>
                    <p>Comece cadastrando contas contábeis ou importe um balancete</p>
                    <button
                        className="lista-button lista-button-primary"
                        onClick={abrirModalCadastro}
                    >
                        ➕ Cadastrar primeira conta
                    </button>
                </div>
            ) : listaFiltrada.length === 0 ? (
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
                        Exibindo <strong>{listaFiltrada.length}</strong> de <strong>{lista.length}</strong> contas
                    </div>

                    <div className="lista-table-container">
                        <table className="lista-table">
                            <thead>
                                <tr>
                                    <th style={{ width: '80px' }}>ID</th>
                                    <th>Conta Contábil</th>
                                    <th>Descrição</th>
                                    <th>Tipo</th>
                                    <th>Conciliável</th>
                                    <th>Conta Superior</th>
                                    <th>Data Criação</th>
                                    <th className="actions-column">Ações</th>
                                </tr>
                            </thead>
                          <tbody>
    {listaFiltrada.map(item => (
        <tr key={item.id} className="table-row-hover">
            <td style={{ fontWeight: '600', color: '#050506ff' }}>
                {item.id}
            </td>

            <td className="empresa-nome">
                {item.conta_contabil}
            </td>

            <td>
                {item.descricao}
            </td>

            <td>
                {item.tipo_conta === 1 ? 'Analítica' : 'Sintética'}
            </td>

            <td>
                <span
                    className={`status-badge ${
                        item.conciliavel ? 'status-ativo' : 'status-inativo'
                    }`}
                >
                    {item.conciliavel ? '✅ Sim' : '❌ Não'}
                </span>
            </td>

            <td>
                {item.conta_superior
                    ? lista.find(c => c.id === item.conta_superior)?.conta_contabil || '-'
                    : '-'}
            </td>

            <td>
                {new Date(item.created_at).toLocaleDateString('pt-BR')}
            </td>

            <td className="table-actions">
                <button
                    className="table-action-button table-action-button-edit"
                    onClick={() => abrirModalEdicao(item)}
                    title="Editar conta"
                >
                    ✏️ Editar
                </button>

                <button
                    className="table-action-button table-action-button-delete"
                    onClick={() => excluirConta(item.id, item.conta_contabil)}
                    title="Excluir conta"
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

            {/* Modal de Cadastro/Edição */}
            {modalAberto && (
                <div className="modal-backdrop" onClick={(e) => {
                    if (e.target === e.currentTarget && !isSubmitting) fecharModal();
                }}>
                    <div className="modal-container">
                        <div className="modal-header">
                            <h2 className="modal-title">
                                {editando ? '✏️ Editar Conta' : '➕ Nova Conta'}
                            </h2>
                            <button
                                className="modal-close"
                                onClick={fecharModal}
                                disabled={isSubmitting}
                                aria-label="Fechar modal"
                            >
                                ×
                            </button>
                        </div>

                        <form onSubmit={handleSubmit}>
                            <div className="modal-body">
                                {editando && (
                                    <div className="form-field">
                                        <label htmlFor="id">Código da Conta</label>
                                        <input
                                            id="id"
                                            type="text"
                                            value={editando?.id || ''}
                                            disabled
                                            style={{ 
                                                backgroundColor: '#f3f4f6', 
                                                cursor: 'not-allowed',
                                                fontWeight: '600',
                                                color: '#6366f1'
                                            }}
                                        />
                                    </div>
                                )}

                                <div className="form-field">
                                    <label htmlFor="empresa">Empresa</label>
                                    <input
                                        id="empresa"
                                        type="text"
                                        value={empresaSelecionada ? `${empresaSelecionada.id} - ${empresaSelecionada.nome}` : ''}
                                        disabled
                                        style={{ 
                                            backgroundColor: '#f3f4f6', 
                                            cursor: 'not-allowed'
                                        }}
                                    />
                                </div>

                                <div className="form-field">
                                    <label htmlFor="conta_contabil">Conta Contábil *</label>
                                    <input
                                        id="conta_contabil"
                                        type="text"
                                        name="conta_contabil"
                                        value={form.conta_contabil}
                                        onChange={handleChange}
                                        className={errors.conta_contabil ? "input-error" : ""}
                                        placeholder="Ex: 1.1.01.001"
                                        disabled={isSubmitting}
                                        autoFocus
                                        maxLength={50}
                                    />
                                    {errors.conta_contabil && (
                                        <span className="error-text" role="alert">
                                            ⚠️ {errors.conta_contabil}
                                        </span>
                                    )}
                                </div>

                                <div className="form-field">
                                <label htmlFor="tipo_conta">Tipo da Conta *</label>
                                <select
                                    id="tipo_conta"
                                    name="tipo_conta"
                                    value={form.tipo_conta}
                                    onChange={handleChange}
                                    className={errors.tipo_conta ? "input-error" : ""}
                                    disabled={isSubmitting}
                                >
                                    <option value="">Selecione</option>
                                    <option value="1">1 - Analítica</option>
                                    <option value="2">2 - Sintética</option>
                                </select>

                                {errors.tipo_conta && (
                                    <span className="error-text">⚠️ {errors.tipo_conta}</span>
                                )}
                            </div>

                            <div className="form-field">
                    <label htmlFor="descricao">Descrição *</label>
                        <input
                            id="descricao"
                            type="text"
                            name="descricao"
                            value={form.descricao}
                            onChange={handleChange}
                            className={errors.descricao ? "input-error" : ""}
                            placeholder="Ex: Caixa Geral"
                            disabled={isSubmitting}
                            maxLength={150}
                        />

                        {errors.descricao && (
                            <span className="error-text">⚠️ {errors.descricao}</span>
                        )}
                    </div>



                                <div className="form-field">
                                    <label htmlFor="conciliavel">Conciliável</label>
                                    <select
                                        id="conciliavel"
                                        name="conciliavel"
                                        value={form.conciliavel.toString()}
                                        onChange={handleChange}
                                        disabled={isSubmitting}
                                    >
                                        <option value="false">❌ Não</option>
                                        <option value="true">✅ Sim</option>
                                    </select>
                                </div>

                                <div className="form-field">
                                    <label htmlFor="conta_superior">Conta Superior (opcional)</label>
                                    <select
                                            id="conta_superior"
                                            name="conta_superior"
                                            value={form.conta_superior || ""}
                                            onChange={handleChange}
                                            disabled={isSubmitting}
                                        >
                                            <option value="">Nenhuma</option>
                                            {lista
                                                .filter(c => c.id !== editando?.id)
                                                .map(c => (
                                                    <option key={c.id} value={c.id}>
                                                        {c.conta_contabil} - {c.descricao} {/* código + descrição */}
                                                    </option>
                                                ))}
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
                                    {isSubmitting ? '⏳ Salvando...' : '💾 Salvar'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Modal de Importação */}
            {modalImportacao && (
                <div className="modal-backdrop" onClick={(e) => {
                    if (e.target === e.currentTarget && !uploading) fecharModal();
                }}>
                    <div className="modal-container">
                        <div className="modal-header">
                            <h2 className="modal-title">📥 Importar Plano de Contas</h2>
                            <button
                                className="modal-close"
                                onClick={fecharModal}
                                disabled={uploading}
                                aria-label="Fechar modal"
                            >
                                ×
                            </button>
                        </div>

                        <div className="modal-body">
                            <div className="form-field">
                                <label htmlFor="empresa_import">Empresa</label>
                                <input
                                    id="empresa_import"
                                    type="text"
                                    value={empresaSelecionada ? `${empresaSelecionada.id} - ${empresaSelecionada.nome}` : ''}
                                    disabled
                                    style={{ 
                                        backgroundColor: '#f3f4f6', 
                                        cursor: 'not-allowed'
                                    }}
                                />
                            </div>

                            <div className="form-field">
                                <label htmlFor="arquivo">Arquivo Excel (.xlsx, .xls)</label>
                                <input
                                    id="arquivo"
                                    type="file"
                                    accept=".xlsx,.xls"
                                    onChange={(e) => setArquivo(e.target.files[0])}
                                    disabled={uploading}
                                />
                                {arquivo && (
                                    <p className="lista-subtitle" style={{ marginTop: '8px' }}>
                                        📄 {arquivo.name}
                                    </p>
                                )}
                            </div>

                            <div style={{ marginTop: '16px', padding: '12px', background: '#f0f9ff', borderRadius: '8px', fontSize: '14px' }}>
                                <strong>📋 Colunas obrigatórias:</strong>
                                <ul style={{ marginTop: '8px', marginLeft: '20px' }}>
                                    <li><code>conta_contabil</code> - Código da conta</li>
                                    <li><code>descricao</code> - Descricao conta</li>
                                    <li><code>conciliavel</code> - Sim/Não</li>
                                     <li><code>tipo_conta</code> - 1 analítica | 2 sintética</li>
                                    <li><code>conta_superior</code> - Código da conta pai (opcional)</li>
                                </ul>
                            </div>
                        </div>

                        <div className="modal-footer">
                            <button
                                type="button"
                                className="secondary-button"
                                onClick={fecharModal}
                                disabled={uploading}
                            >
                                Cancelar
                            </button>
                            <button
                                type="button"
                                className="primary-button"
                                onClick={importar}
                                disabled={uploading || !arquivo}
                            >
                                {uploading ? '⏳ Importando...' : '📥 Importar'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}