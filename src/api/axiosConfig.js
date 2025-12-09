// src/api/axiosConfig.js

import axios from 'axios';

// Configuração da API
const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'multipart/form-data',
  },
});

export default api; // ⬅️ ESSENCIAL: Exportar a instância