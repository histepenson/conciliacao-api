// src/components/AllDifferencesTable/AllDifferencesTable.jsx
import { useState, useMemo } from 'react';
import './AllDifferencesTable.css';

function AllDifferencesTable({ diferencas, resumo }) {
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);
  const [sortConfig, setSortConfig] = useState({ key: 'Diferença Absoluta', direction: 'desc' });
  const [filterStatus, setFilterStatus] = useState('Todos'); // ← Status: OK/DIFERENÇA
  const [searchTerm, setSearchTerm] = useState('');

  // Formatação
  const formatCurrency = (value) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(value || 0);
  };

  // Contar OK e DIFERENÇA
  const contarStatus = () => {
    const comDiferenca = diferencas.filter(d => d['Diferença'] !== 0 || d['Diferença Absoluta'] !== 0).length;
    const ok = diferencas.length - comDiferenca;
    return { ok, comDiferenca };
  };

  const { ok: countOk, comDiferenca: countDiferenca } = contarStatus();

  // Filtrar dados
  const filteredData = useMemo(() => {
    let data = [...diferencas];

    // Filtrar por Status
    if (filterStatus === 'OK') {
      data = data.filter(item => item['Diferença'] === 0 && item['Diferença Absoluta'] === 0);
    } else if (filterStatus === 'DIFERENÇA') {
      data = data.filter(item => item['Diferença'] !== 0 || item['Diferença Absoluta'] !== 0);
    }

    // Busca
    if (searchTerm) {
      data = data.filter(item => 
        item['Código']?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item['Cliente']?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Ordenar
    if (sortConfig.key) {
      data.sort((a, b) => {
        const aVal = a[sortConfig.key] || 0;
        const bVal = b[sortConfig.key] || 0;

        if (typeof aVal === 'number' && typeof bVal === 'number') {
          return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
        }

        return sortConfig.direction === 'asc'
          ? String(aVal).localeCompare(String(bVal))
          : String(bVal).localeCompare(String(aVal));
      });
    }

    return data;
  }, [diferencas, filterStatus, searchTerm, sortConfig]);

  const totalPages = Math.ceil(filteredData.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentData = filteredData.slice(startIndex, endIndex);

  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc'
    }));
  };

  const exportToCSV = () => {
    const headers = ['Código', 'Cliente', 'Valor Financeiro', 'Valor Contabilidade', 'Diferença', 'Status'];
    const csvContent = [
      headers.join(','),
      ...filteredData.map(row => {
        const status = (row['Diferença'] === 0 && row['Diferença Absoluta'] === 0) ? 'OK' : 'DIFERENÇA';
        return [
          `"${row['Código'] || ''}"`,
          `"${row['Cliente'] || ''}"`,
          `"${row['Valor Financeiro'] || ''}"`,
          `"${row['Valor Contabilidade'] || ''}"`,
          `"${row['Diferença'] || ''}"`,
          `"${status}"`
        ].join(',');
      })
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `diferencas_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  return (
    <div className="all-differences-section">
      <div className="card all-differences-card">
        <div className="all-diff-header">
          <div className="header-left">
            <h3 className="all-diff-title">📋 Todas as Diferenças</h3>
            <span className="total-count">{filteredData.length} registros</span>
          </div>
          <button className="export-btn" onClick={exportToCSV}>
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Exportar CSV
          </button>
        </div>

        <div className="filters-container">
          <div className="search-box">
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Buscar por código ou cliente..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
            />
            {searchTerm && (
              <button className="clear-search" onClick={() => setSearchTerm('')}>
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          <div className="filter-group">
            <label>Status:</label>
            <select 
              value={filterStatus} 
              onChange={(e) => {
                setFilterStatus(e.target.value);
                setCurrentPage(1);
              }}
            >
              <option value="Todos">Todos ({diferencas.length})</option>
              <option value="OK">OK ({countOk})</option>
              <option value="DIFERENÇA">Diferença ({countDiferenca})</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Itens por página:</label>
            <select 
              value={itemsPerPage} 
              onChange={(e) => {
                setItemsPerPage(Number(e.target.value));
                setCurrentPage(1);
              }}
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        </div>

        <div className="table-container">
          <table className="full-differences-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('Código')} className="sortable">
                  <div className="th-content">
                    Código
                    <SortIcon columnKey="Código" sortConfig={sortConfig} />
                  </div>
                </th>
                <th onClick={() => handleSort('Cliente')} className="sortable">
                  <div className="th-content">
                    Cliente
                    <SortIcon columnKey="Cliente" sortConfig={sortConfig} />
                  </div>
                </th>
                <th onClick={() => handleSort('Valor Financeiro')} className="sortable">
                  <div className="th-content">
                    Financeiro
                    <SortIcon columnKey="Valor Financeiro" sortConfig={sortConfig} />
                  </div>
                </th>
                <th onClick={() => handleSort('Valor Contabilidade')} className="sortable">
                  <div className="th-content">
                    Contabilidade
                    <SortIcon columnKey="Valor Contabilidade" sortConfig={sortConfig} />
                  </div>
                </th>
                <th onClick={() => handleSort('Diferença')} className="sortable">
                  <div className="th-content">
                    Diferença
                    <SortIcon columnKey="Diferença" sortConfig={sortConfig} />
                  </div>
                </th>
                <th onClick={() => handleSort('Diferença Absoluta')} className="sortable">
                  <div className="th-content">
                    Dif. Absoluta
                    <SortIcon columnKey="Diferença Absoluta" sortConfig={sortConfig} />
                  </div>
                </th>
                <th>
                  <div className="th-content">
                    Status
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {currentData.length > 0 ? (
                currentData.map((diff, index) => (
                  <tr key={index}>
                    <td><code>{diff['Código']}</code></td>
                    <td className="client-name">{diff['Cliente']}</td>
                    <td className="currency">{formatCurrency(diff['Valor Financeiro'])}</td>
                    <td className="currency">{formatCurrency(diff['Valor Contabilidade'])}</td>
                    <td className={`currency ${diff['Diferença'] < 0 ? 'negative' : 'positive'}`}>
                      {formatCurrency(diff['Diferença'])}
                    </td>
                    <td className="currency">{formatCurrency(diff['Diferença Absoluta'])}</td>
                    <td>
                      {(diff['Diferença'] === 0 && diff['Diferença Absoluta'] === 0) ? (
                        <span className="badge badge-ok">OK</span>
                      ) : (
                        <span className="badge badge-diferenca">DIFERENÇA</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7" className="no-data">
                    Nenhum resultado encontrado
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="pagination">
            <div className="pagination-info">
              Mostrando {startIndex + 1} - {Math.min(endIndex, filteredData.length)} de {filteredData.length}
            </div>
            
            <div className="pagination-controls">
              <button
                className="pagination-btn"
                onClick={() => setCurrentPage(1)}
                disabled={currentPage === 1}
              >
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                </svg>
              </button>

              <button
                className="pagination-btn"
                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                disabled={currentPage === 1}
              >
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
                </svg>
              </button>

              {[...Array(totalPages)].map((_, idx) => {
                const page = idx + 1;
                if (
                  page === 1 ||
                  page === totalPages ||
                  (page >= currentPage - 1 && page <= currentPage + 1)
                ) {
                  return (
                    <button
                      key={page}
                      className={`pagination-btn ${page === currentPage ? 'active' : ''}`}
                      onClick={() => setCurrentPage(page)}
                    >
                      {page}
                    </button>
                  );
                } else if (page === currentPage - 2 || page === currentPage + 2) {
                  return <span key={page} className="pagination-ellipsis">...</span>;
                }
                return null;
              })}

              <button
                className="pagination-btn"
                onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                disabled={currentPage === totalPages}
              >
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                </svg>
              </button>

              <button
                className="pagination-btn"
                onClick={() => setCurrentPage(totalPages)}
                disabled={currentPage === totalPages}
              >
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SortIcon({ columnKey, sortConfig }) {
  if (sortConfig.key !== columnKey) {
    return (
      <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ opacity: 0.3 }}>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
      </svg>
    );
  }

  return sortConfig.direction === 'asc' ? (
    <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7" />
    </svg>
  ) : (
    <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
    </svg>
  );
}

export default AllDifferencesTable;