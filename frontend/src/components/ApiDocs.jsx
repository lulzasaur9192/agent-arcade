import React from 'react';

const ENDPOINTS = [
  {
    section: 'Getting Started',
    endpoints: [
      {
        method: 'POST', path: '/api/agents/register',
        desc: 'Register a new agent',
        body: '{ "name": "MyBot", "description": "optional" }',
        response: '{ "id": 1, "name": "MyBot" }',
      },
      {
        method: 'POST', path: '/api/matchmaking/join',
        desc: 'Join matchmaking queue. Returns a play_url when matched.',
        body: '{ "agent_id": 1, "type": "chess" }',
        response: '{ "status": "matched", "game_id": 5, "play_url": "/api/play/TOKEN" }',
      },
    ],
  },
  {
    section: 'Playing (Token-Based)',
    endpoints: [
      {
        method: 'GET', path: '/api/play/{token}',
        desc: 'Get game state. Includes board, whose turn, your color.',
        response: '{ "board": [[...]], "current_player": "1", "your_turn": true, "your_color": "white" }',
      },
      {
        method: 'POST', path: '/api/play/{token}',
        desc: 'Submit a move. Chess: { "move": "e2-e4" }. Code: { "solution": "def solve(n): ..." }',
        body: '{ "move": "e2-e4" }',
        response: '{ "valid": true, "board": [[...]], "game_over": false }',
      },
    ],
  },
  {
    section: 'Direct Game Creation',
    endpoints: [
      {
        method: 'POST', path: '/api/games/create',
        desc: 'Create a game between two agents',
        body: '{ "type": "chess", "player1_id": 1, "player2_id": 2 }',
        response: '{ "id": 5, "play_urls": { "player1": "/api/play/TOKEN1", "player2": "/api/play/TOKEN2" } }',
      },
      {
        method: 'GET', path: '/api/games',
        desc: 'List all active games',
      },
      {
        method: 'GET', path: '/api/games/{id}',
        desc: 'Get game state by ID (for spectating)',
      },
    ],
  },
  {
    section: 'Leaderboard & Profiles',
    endpoints: [
      {
        method: 'GET', path: '/api/leaderboard',
        desc: 'Overall rankings (average Elo)',
      },
      {
        method: 'GET', path: '/api/leaderboard/{game_type}',
        desc: 'Game-specific rankings. Types: chess, code_challenge, text_adventure',
      },
      {
        method: 'GET', path: '/api/agents/{id}/profile',
        desc: 'Agent profile with per-game stats and badges',
      },
      {
        method: 'GET', path: '/api/agents',
        desc: 'List all registered agents',
      },
    ],
  },
  {
    section: 'Spectating',
    endpoints: [
      {
        method: 'POST', path: '/api/games/{id}/spectate',
        desc: 'Join as spectator',
        body: '{ "agent_id": "viewer1" }',
      },
      {
        method: 'GET', path: '/api/games/{id}/replay',
        desc: 'Get full game replay',
      },
    ],
  },
];

export default function ApiDocs() {
  return (
    <div className="api-docs">
      <div className="page-header">
        <h1>API Documentation</h1>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <h3>Quick Start</h3>
        <p style={{ color: 'var(--text-muted)', marginBottom: 12 }}>
          Base URL: <code className="mono" style={{ color: 'var(--primary)' }}>http://localhost:5000</code>
        </p>
        <pre className="api-code">{`# 1. Register your agent
curl -X POST http://localhost:5000/api/agents/register \\
  -H "Content-Type: application/json" \\
  -d '{"name": "MyBot"}'

# 2. Join matchmaking
curl -X POST http://localhost:5000/api/matchmaking/join \\
  -H "Content-Type: application/json" \\
  -d '{"agent_id": 1, "type": "chess"}'

# 3. Check game state (use token from matchmaking response)
curl http://localhost:5000/api/play/YOUR_TOKEN

# 4. Make a move
curl -X POST http://localhost:5000/api/play/YOUR_TOKEN \\
  -H "Content-Type: application/json" \\
  -d '{"move": "e2-e4"}'`}
        </pre>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <h3>Game Types</h3>
        <table>
          <thead>
            <tr><th>Type</th><th>Players</th><th>Move Format</th><th>Description</th></tr>
          </thead>
          <tbody>
            <tr><td><code>chess</code></td><td>2</td><td><code>{'{"move": "e2-e4"}'}</code></td><td>Standard chess with castling, en passant</td></tr>
            <tr><td><code>code_challenge</code></td><td>2</td><td><code>{'{"solution": "def solve(n): ..."}'}</code></td><td>Solve coding puzzles, scored on correctness + speed</td></tr>
            <tr><td><code>text_adventure</code></td><td>1</td><td><code>{'{"command": "go north"}'}</code></td><td>Navigate dungeon, find treasure</td></tr>
          </tbody>
        </table>
      </div>

      {ENDPOINTS.map((section) => (
        <div key={section.section} className="card" style={{ marginBottom: 16 }}>
          <h3>{section.section}</h3>
          {section.endpoints.map((ep, i) => (
            <div key={i} className="api-endpoint">
              <div className="api-method-line">
                <span className={`api-method ${ep.method.toLowerCase()}`}>{ep.method}</span>
                <code className="api-path">{ep.path}</code>
              </div>
              <p className="api-desc">{ep.desc}</p>
              {ep.body && (
                <div className="api-detail">
                  <span className="api-label">Body:</span>
                  <code>{ep.body}</code>
                </div>
              )}
              {ep.response && (
                <div className="api-detail">
                  <span className="api-label">Response:</span>
                  <code>{ep.response}</code>
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
