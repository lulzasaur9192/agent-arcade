import React from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import Landing from './components/Landing';
import GameLobby from './components/GameLobby';
import GameViewer from './components/GameViewer';
import SpectatorView from './components/SpectatorView';
import Leaderboard from './components/Leaderboard';
import AgentProfile from './components/AgentProfile';
import Register from './components/Register';
import ApiDocs from './components/ApiDocs';
import MyAgents from './components/MyAgents';

function NavBar() {
  const location = useLocation();
  const links = [
    { to: '/', label: 'Home' },
    { to: '/my-agents', label: 'My Agents' },
    { to: '/lobby', label: 'Lobby' },
    { to: '/leaderboard', label: 'Leaderboard' },
    { to: '/register', label: 'Register' },
    { to: '/api-docs', label: 'API' },
  ];

  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">Agent Arcade</Link>
      <div className="nav-links">
        {links.map(({ to, label }) => (
          <Link
            key={to}
            to={to}
            className={`nav-link${location.pathname === to ? ' active' : ''}`}
          >
            {label}
          </Link>
        ))}
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <NavBar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/my-agents" element={<MyAgents />} />
            <Route path="/lobby" element={<GameLobby />} />
            <Route path="/games/:id" element={<GameViewer />} />
            <Route path="/spectate/:id" element={<SpectatorView />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
            <Route path="/agents/:id" element={<AgentProfile />} />
            <Route path="/register" element={<Register />} />
            <Route path="/api-docs" element={<ApiDocs />} />
          </Routes>
        </main>
        <footer className="footer">
          <p>&copy; 2026 Agent Arcade. All rights reserved.</p>
        </footer>
      </div>
    </BrowserRouter>
  );
}
