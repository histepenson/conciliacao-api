import React, { useEffect } from 'react'
import { Toaster } from 'react-hot-toast'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'

import MainLayout from './components/Layout/MainLayout'

// Páginas
import Conciliacoes from './pages/Conciliacoes'
import ConciliarPeriodo from './pages/ConciliarPeriodo'
import Cadastros from './pages/Cadastros'
import CadastroEmpresa from './pages/CadastroEmpresa'
import ListaEmpresa from './pages/ListaEmpresa'
import PlanoDeContas from './pages/PlanoDeContas'

import './assets/styles/App.css'

function App() {
  // 🔎 Debug da variável de ambiente
  useEffect(() => {
    console.log('API_URL:', import.meta.env.VITE_API_URL)
  }, [])

  return (
    <Router>
      <Toaster
        position="top-right"
        reverseOrder={false}
        toastOptions={{
          duration: 3000,
          style: {
            background: '#fff',
            color: '#1f2937',
            padding: '16px',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
          },
          success: {
            iconTheme: {
              primary: '#10b981',
              secondary: '#fff',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444',
              secondary: '#fff',
            },
          },
        }}
      />

      <Routes>
        <Route path="/" element={<MainLayout />}>
          {/* Redirecionamento padrão */}
          <Route index element={<Navigate to="/conciliacoes" replace />} />

          {/* CONCILIAÇÕES */}
          <Route path="conciliacoes" element={<Conciliacoes />} />
          <Route path="conciliacoes/periodo" element={<ConciliarPeriodo />} />

          {/* CADASTROS */}
          <Route path="cadastros" element={<Cadastros />} />
          <Route path="cadastros/empresas" element={<ListaEmpresa />} />
          <Route path="cadastros/empresas/novo" element={<CadastroEmpresa />} />
          <Route path="cadastros/planocontas" element={<PlanoDeContas />} />

          {/* FALLBACK */}
          <Route path="*" element={<h1>Página Não Encontrada</h1>} />
        </Route>
      </Routes>
    </Router>
  )
}

export default App
