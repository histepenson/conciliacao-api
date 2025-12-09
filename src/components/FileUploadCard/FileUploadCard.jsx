// src/components/FileUploadCard/FileUploadCard.jsx
import React from 'react';

// Componente de Upload de Arquivo
function FileUploadCard({ 
  type, 
  title, 
  description, 
  iconColor, 
  file, 
  onFileSelect, 
  onRemove, 
  onDragOver, 
  onDragLeave, 
  onDrop,
  disabled 
}) {
  const handleClick = () => {
    document.getElementById(`file-input-${type}`).click()
  }

  const handleInputChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      onFileSelect(type, selectedFile)
    }
  }

  const icons = {
    origem: (
      <svg style={{ color: iconColor }} className="upload-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    contabil: (
      <svg style={{ color: iconColor }} className="upload-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
      </svg>
    ),
    geral: (
      <svg style={{ color: iconColor }} className="upload-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
    ),
  }

  return (
    <div className="card">
      <div className="upload-section">
        <div className="upload-header">
          {icons[type]}
          <h3 className="upload-title">{title}</h3>
        </div>
        <p className="upload-description">{description}</p>

        {!file ? (
          <div
            className="drop-zone"
            onClick={!disabled ? handleClick : undefined}
            onDragOver={(e) => !disabled && onDragOver(e, type)}
            onDragLeave={(e) => !disabled && onDragLeave(e)}
            onDrop={(e) => !disabled && onDrop(e, type)}
            style={{ cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1 }}
          >
            <input
              id={`file-input-${type}`}
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={handleInputChange}
              style={{ display: 'none' }}
              disabled={disabled}
            />
            <div className="upload-icon-circle">
              <svg width="40" height="40" fill="none" stroke="#6b7280" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <div className="drop-zone-text">Arraste o arquivo ou clique para selecionar</div>
            <div className="drop-zone-subtext">Formatos aceitos: .xlsx, .xls, .csv • Máximo 50MB</div>
          </div>
        ) : (
          <div className="file-preview">
            <div className="file-preview-content">
              <div className="file-info">
                <div className="file-icon">
                  <svg width="30" height="30" fill="none" stroke="#16a34a" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div className="file-details">
                  <div className="file-name">{file.name}</div>
                  <div className="file-meta">
                    {(file.size / 1024 / 1024).toFixed(2)} MB • {file.type || 'Excel'}
                  </div>
                </div>
              </div>
              <button className="remove-btn" onClick={() => onRemove(type)} disabled={disabled}>
                <svg width="24" height="24" fill="none" stroke="#6b7280" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="file-status">
              <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
              </svg>
              Arquivo validado e pronto
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default FileUploadCard;