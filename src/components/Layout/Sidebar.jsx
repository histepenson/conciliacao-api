import React, { useState } from 'react';

function Sidebar() {
  const [cadastrosOpen, setCadastrosOpen] = useState(false);
  const [activeMenu, setActiveMenu] = useState('');

  return (
    <div className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <div className="logo-container">
          <div className="logo-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <div className="logo-text">
            <h2>Conciliação</h2>
            <span className="logo-subtitle">AI Solutions</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <div className="nav-section">
          <span className="nav-section-title">MENU PRINCIPAL</span>
          
          {/* Cadastros com Submenu */}
          <div className="nav-item-wrapper">
            <button 
              className={`nav-item ${cadastrosOpen ? 'active' : ''}`}
              onClick={() => setCadastrosOpen(!cadastrosOpen)}
            >
              <div className="nav-item-content">
                <span className="nav-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </span>
                <span className="nav-text">Cadastros</span>
                <svg 
                  className={`chevron ${cadastrosOpen ? 'open' : ''}`}
                  width="16" 
                  height="16" 
                  viewBox="0 0 24 24" 
                  fill="none" 
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
              </div>
              <div className="nav-indicator"></div>
            </button>
            
            {/* Submenu */}
            <div className={`submenu ${cadastrosOpen ? 'open' : ''}`}>
              <button 
                className={`submenu-item ${activeMenu === 'balancete' ? 'active' : ''}`}
                onClick={() => setActiveMenu('balancete')}
              >
                <span className="submenu-icon">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                </span>
                <span className="submenu-text">Balancete</span>
              </button>
            </div>
          </div>

          <button 
            className={`nav-item ${activeMenu === 'conciliacoes' ? 'active' : ''}`}
            onClick={() => setActiveMenu('conciliacoes')}
          >
            <div className="nav-item-content">
              <span className="nav-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </span>
              <span className="nav-text">Conciliações</span>
            </div>
            <div className="nav-indicator"></div>
          </button>
        </div>

        {/* Seção de Ações Rápidas */}
        <div className="nav-section">
          <span className="nav-section-title">AÇÕES RÁPIDAS</span>
          
          <button className="nav-item quick-action">
            <div className="nav-item-content">
              <span className="nav-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                </svg>
              </span>
              <span className="nav-text">Nova Conciliação</span>
            </div>
          </button>

          <button className="nav-item quick-action">
            <div className="nav-item-content">
              <span className="nav-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </span>
              <span className="nav-text">Relatórios</span>
            </div>
          </button>
        </div>
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="user-info">
          <div className="user-avatar">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <div className="user-details">
            <span className="user-name">Usuário</span>
            <span className="user-role">Administrador</span>
          </div>
        </div>
        
        <div className="footer-actions">
          <button className="footer-btn" title="Configurações">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
          
          <button className="footer-btn" title="Sair">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
        
        <div className="copyright">
          <p>© 2024 AI Solutions</p>
          <span>v1.0.0</span>
        </div>
      </div>

      <style>{`
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }

        .sidebar {
          width: 280px;
          height: 100vh;
          background: linear-gradient(180deg, #1a1f2e 0%, #0f1419 100%);
          color: #e1e8f0;
          display: flex;
          flex-direction: column;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        .sidebar-header {
          padding: 24px 20px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .logo-container {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .logo-icon {
          color: #60a5fa;
        }

        .logo-text h2 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
          color: #fff;
        }

        .logo-subtitle {
          font-size: 11px;
          color: #94a3b8;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .sidebar-nav {
          flex: 1;
          overflow-y: auto;
          padding: 16px 12px;
        }

        .nav-section {
          margin-bottom: 24px;
        }

        .nav-section-title {
          display: block;
          padding: 0 12px 8px;
          font-size: 11px;
          font-weight: 600;
          color: #64748b;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .nav-item-wrapper {
          margin-bottom: 4px;
        }

        .nav-item {
          display: flex;
          align-items: center;
          width: 100%;
          padding: 10px 12px;
          margin-bottom: 4px;
          background: transparent;
          border: none;
          border-radius: 8px;
          color: #cbd5e1;
          text-decoration: none;
          transition: all 0.2s;
          cursor: pointer;
          position: relative;
          text-align: left;
        }

        .nav-item:hover {
          background: rgba(96, 165, 250, 0.1);
          color: #60a5fa;
        }

        .nav-item.active {
          background: rgba(96, 165, 250, 0.15);
          color: #60a5fa;
        }

        .nav-item-content {
          display: flex;
          align-items: center;
          gap: 12px;
          flex: 1;
        }

        .nav-icon {
          display: flex;
          align-items: center;
        }

        .nav-text {
          font-size: 14px;
          font-weight: 500;
        }

        .chevron {
          margin-left: auto;
          transition: transform 0.3s ease;
        }

        .chevron.open {
          transform: rotate(180deg);
        }

        .nav-indicator {
          position: absolute;
          left: 0;
          top: 50%;
          transform: translateY(-50%);
          width: 3px;
          height: 0;
          background: #60a5fa;
          border-radius: 0 3px 3px 0;
          transition: height 0.2s;
        }

        .nav-item.active .nav-indicator {
          height: 70%;
        }

        .submenu {
          max-height: 0;
          overflow: hidden;
          transition: max-height 0.3s ease-out;
          padding-left: 20px;
        }

        .submenu.open {
          max-height: 200px;
          padding-top: 4px;
        }

        .submenu-item {
          display: flex;
          align-items: center;
          gap: 10px;
          width: 100%;
          padding: 8px 12px;
          margin: 4px 0;
          border-radius: 6px;
          background: transparent;
          border: none;
          color: #94a3b8;
          text-decoration: none;
          font-size: 13px;
          transition: all 0.2s;
          cursor: pointer;
          text-align: left;
        }

        .submenu-item:hover {
          background: rgba(96, 165, 250, 0.08);
          color: #60a5fa;
        }

        .submenu-item.active {
          background: rgba(96, 165, 250, 0.12);
          color: #60a5fa;
          font-weight: 500;
        }

        .submenu-icon {
          display: flex;
          align-items: center;
        }

        .quick-action {
          border: 1px dashed rgba(96, 165, 250, 0.3);
        }

        .quick-action:hover {
          border-color: #60a5fa;
        }

        .sidebar-footer {
          padding: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .user-info {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 8px;
          margin-bottom: 12px;
        }

        .user-avatar {
          width: 40px;
          height: 40px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          flex-shrink: 0;
        }

        .user-details {
          display: flex;
          flex-direction: column;
        }

        .user-name {
          font-size: 14px;
          font-weight: 500;
          color: #fff;
        }

        .user-role {
          font-size: 12px;
          color: #94a3b8;
        }

        .footer-actions {
          display: flex;
          gap: 8px;
          justify-content: center;
          margin-bottom: 12px;
        }

        .footer-btn {
          padding: 8px;
          background: rgba(255, 255, 255, 0.05);
          border: none;
          border-radius: 6px;
          color: #94a3b8;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .footer-btn:hover {
          background: rgba(96, 165, 250, 0.1);
          color: #60a5fa;
        }

        .copyright {
          text-align: center;
          padding-top: 12px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .copyright p {
          margin: 0 0 4px 0;
          font-size: 11px;
          color: #64748b;
        }

        .copyright span {
          font-size: 10px;
          color: #475569;
        }
      `}</style>
    </div>
  );
}

export default Sidebar;