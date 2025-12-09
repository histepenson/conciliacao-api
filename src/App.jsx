// src/App.jsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './components/Layout/MainLayout';
import Conciliacoes from './pages/Conciliacoes';
import Cadastros from './pages/Cadastros';
import './assets/styles/App.css'; // Certifique-se de que seu arquivo CSS principal está aqui

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          {/* Rota padrão: redireciona para Conciliações */}
          <Route index element={<Navigate to="/conciliacoes" replace />} />
          
          {/* Módulos */}
          <Route path="conciliacoes" element={<Conciliacoes />} />
          <Route path="cadastros" element={<Cadastros />} />

          {/* Rota 404/Não Encontrada */}
          <Route path="*" element={<h1>Página Não Encontrada</h1>} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;