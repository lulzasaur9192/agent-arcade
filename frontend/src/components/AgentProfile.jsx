import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';

export default function AgentProfile() {
  const { id } = useParams();
  const [agent, setAgent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/agents/${id}/profile`)
      .then((r) => r.ok ? r.json() : r.json().then((e) => Promise.reject(new Error(e.error))))
      .then(setAgent)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="loading">Loading agent profile...</div>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!agent) return <div className="empty-state">Agent not found.</div>;

  const wins = agent.overall_wins || 0;
  const losses = agent.overall_losses || 0;
  const total = agent.total_games || 0;
  const draws = total - wins - losses;
  const winPct = total > 0 ? (wins / total * 100).toFixed(1) : '—';

  return (
    <div className="agent-profile">
      <div className="page-header">
        <h1>{agent.agent_name || `Agent ${agent.agent_id}`}</h1>
      </div>

      <div className="grid two-col">
        <div className="card">
          <h3>Overview</h3>
          <dl className="detail-list">
            <dt>ID</dt><dd className="mono">{agent.agent_id}</dd>
            <dt>Games Played</dt><dd>{total}</dd>
            <dt>Win Rate</dt><dd>{winPct}%</dd>
          </dl>
        </div>

        <div className="card stats-card">
          <h3>Record</h3>
          <div className="stat-bars">
            <div className="stat-row">
              <span className="stat-label">Wins</span>
              <div className="stat-bar">
                <div className="stat-fill win" style={{ width: `${total > 0 ? wins / total * 100 : 0}%` }} />
              </div>
              <span className="stat-val">{wins}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Losses</span>
              <div className="stat-bar">
                <div className="stat-fill loss" style={{ width: `${total > 0 ? losses / total * 100 : 0}%` }} />
              </div>
              <span className="stat-val">{losses}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Draws</span>
              <div className="stat-bar">
                <div className="stat-fill draw" style={{ width: `${total > 0 ? draws / total * 100 : 0}%` }} />
              </div>
              <span className="stat-val">{draws}</span>
            </div>
          </div>
        </div>
      </div>

      {agent.game_stats && Object.keys(agent.game_stats).length > 0 && (
        <div className="card">
          <h3>Per-Game Stats</h3>
          <table>
            <thead>
              <tr>
                <th>Game</th>
                <th>ELO</th>
                <th>Peak</th>
                <th>W</th>
                <th>L</th>
                <th>D</th>
                <th>Streak</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(agent.game_stats).map(([game, stats]) => (
                <tr key={game}>
                  <td>{game.replace('_', ' ')}</td>
                  <td className="elo">{stats.elo?.toFixed(0)}</td>
                  <td>{stats.peak_elo?.toFixed(0)}</td>
                  <td className="wins">{stats.wins}</td>
                  <td className="losses">{stats.losses}</td>
                  <td>{stats.draws}</td>
                  <td>{stats.streak > 0 ? `+${stats.streak}` : stats.streak}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {agent.badges && agent.badges.length > 0 && (
        <div className="card">
          <h3>Badges</h3>
          <div className="badge-list">
            {agent.badges.map((b, i) => (
              <span key={i} className="badge badge-achievement">{b.badge}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
