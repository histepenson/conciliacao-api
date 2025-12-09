// src/components/ResultDisplay/ResultDisplay.jsx
import React from 'react';
import DetailItem from '../Shared/DetailItem';
import { formatCurrency, getBadgeClass } from './helpers';
import AllDifferencesTable from '../AllDifferencesTable/AllDifferencesTable';

function ResultDisplay({ result }) {
  const { resumo, diferencas } = result; // ← MUDADO de diferencas_top10 para diferencas

  // 🔍 DEBUG AUTOMÁTICO
  console.log('=================================');
  console.log('🔍 RESULT COMPLETO:', result);
  console.log('🔍 diferencas existe?', result.diferencas ? '✅ SIM' : '❌ NÃO');
  console.log('🔍 diferencas length:', result.diferencas?.length);
  console.log('🔍 Condição OK?', result.diferencas && result.diferencas.length > 0 ? '✅ SIM' : '❌ NÃO');
  console.log('=================================');

  return (
    <div className="result-section">
      {/* Cards de Resumo */}
      <div className="result-cards-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#3b82f6' }}>
            <svg width="24" height="24" fill="none" stroke="white" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div className="stat-content">
            <div className="stat-label">Total Registros</div>
            <div className="stat-value">{resumo?.total_registros || 0}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#22c55e' }}>
            <svg width="24" height="24" fill="none" stroke="white" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="stat-content">
            <div className="stat-label">Em Ambas Bases</div>
            <div className="stat-value">{resumo?.registros_ambos || 0}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#f59e0b' }}>
            <svg width="24" height="24" fill="none" stroke="white" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div className="stat-content">
            <div className="stat-label">Com Diferenças</div>
            <div className="stat-value">{resumo?.registros_com_diferenca || 0}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#ef4444' }}>
            <svg width="24" height="24" fill="none" stroke="white" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="stat-content">
            <div className="stat-label">Diferença Total</div>
            <div className="stat-value" style={{ fontSize: '18px' }}>
              {formatCurrency(resumo?.diferenca_total)}
            </div>
          </div>
        </div>
      </div>

      {/* Resumo Detalhado */}
      <div className="card result-details">
        <h3 className="result-title">📊 Resumo da Análise</h3>
        <div className="details-grid">
          <DetailItem 
            label="Financeiro Normalizado" 
            value={resumo?.financeiro_normalizado || 0} 
            icon="📄"
          />
          <DetailItem 
            label="Contabilidade Normalizada" 
            value={resumo?.contabilidade_normalizada || 0} 
            icon="📄"
          />
          <DetailItem 
            label="Só no Financeiro" 
            value={resumo?.registros_so_financeiro || 0} 
            icon="⚠️"
            highlight="warning"
          />
          <DetailItem 
            label="Só na Contabilidade" 
            value={resumo?.registros_so_contabilidade || 0} 
            icon="⚠️"
            highlight="warning"
          />
          <DetailItem 
            label="Valor Total Financeiro" 
            value={formatCurrency(resumo?.valor_total_financeiro)} 
            icon="💰"
          />
          <DetailItem 
            label="Valor Total Contabilidade" 
            value={formatCurrency(resumo?.valor_total_contabilidade)} 
            icon="💰"
          />
          <DetailItem 
            label="Maior Diferença" 
            value={formatCurrency(resumo?.maior_diferenca)} 
            icon="📈"
            highlight="error"
          />
          <DetailItem 
            label="Diferença Absoluta Total" 
            value={formatCurrency(resumo?.diferenca_absoluta_total)} 
            icon="📊"
          />
        </div>
      </div>

      {/* Tabela Completa de Todas as Diferenças */}
      {diferencas && diferencas.length > 0 && (
        <AllDifferencesTable 
          diferencas={diferencas} 
          resumo={resumo}
        />
      )}

      {/* Análise Concluída - Final */}
      {result.arquivo_diferencas && (
        <div className="card success-card">
          <div className="success-icon">
            <svg width="48" height="48" fill="none" stroke="#22c55e" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="success-content">
            <h3>✅ Análise Concluída!</h3>
            <p>Arquivo Excel com diferenças detalhadas foi gerado com sucesso.</p>
            <p className="success-note">
              O arquivo contém 5 abas: Todas Diferenças, Com Diferenças, Só Financeiro, 
              Só Contabilidade e Resumo.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default ResultDisplay;