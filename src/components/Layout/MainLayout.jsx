// src/components/Layout/MainLayout.jsx
import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import './MainLayout.css'; // <- Adicione esta linha

function MainLayout() {
  return (
    <div className="app-container">
      <Sidebar />
      <main className="main-content-wrapper">
        <Outlet />
      </main>
    </div>
  );
}

export default MainLayout;