// src/components/Shared/DetailItem.jsx
import React from 'react';

// Componente auxiliar para itens de detalhe
function DetailItem({ label, value, icon, highlight }) {
  const className = `detail-item ${highlight ? `highlight-${highlight}` : ''}`
  
  return (
    <div className={className}>
      <span className="detail-icon">{icon}</span>
      <div className="detail-content">
        <div className="detail-label">{label}</div>
        <div className="detail-value">{value}</div>
      </div>
    </div>
  )
}

export default DetailItem;