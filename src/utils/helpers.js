// src/components/ResultDisplay/helpers.js

export const formatCurrency = (value) => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(value || 0)
}

export const getBadgeClass = (origem) => {
  const map = {
    'Ambos': 'success',
    'Só Financeiro': 'warning',
    'Só Contabilidade': 'info'
  }
  return map[origem] || 'default'
}