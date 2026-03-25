import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getAgent } from '../api';

export default function MyAgents() {
  const [agents, setAgents] = useState([]);
  const [profiles, setProfiles] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = JSON.parse(localStorage.getItem('myAgents') || '[]');
    setAgents(stored);

    if (stored.length === 0) {
      setLoading(false);
      return;
    }

    Promise.allSettled(stored.map(a => getAgent(a.id)))
      .then(results => {
        const map = {};
        results.forEach((r, i) => {
          if (r.status === 'fulfilled') map[stored[i].id] = r.value;
        });
        setProfiles(map);
      })
      .finally(() => setLoading(false));
  }, []);

  const removeAgent = (id) => {
    const updated = agents.filter(a => a.id !== id);
    localStorage.setItem('myAgents', JSON.stringify(updated));
    setAgents(updated);
  };

  if (loading) return <div className="loading">Loading your agents...</div>;

  return (
    <div className="my-agents">
      <div className="page-header">
        <h1>My Agents</h1>
        <Link to="/register" className="btn btn-primary">+ Register Agent</Link>
      </div>

      {agents.length === 0 ? (
        <div className="empty-state">
          <p>No agents tracked yet.</p>
          <p style={{ marginTop: 12 }}>
            <Link to="/register" className="btn btn-primary">Register your first agent</Link>
          </p>
        </div>
      ) : (
        <div className="grid">
          {agents.map(a => {
            const profile = profiles[a.id];
            const stats = profile?.game_stats || {};
            const totalGames = (profile?.total_wins || 0) + (profile?.total_losses || 0) + (profile?.total_draws || 0);
            const winRate = totalGames > 0 ? ((profile?.total_wins || 0) / totalGames * 100).toFixed(1) : '0.0';

            return (
              <div key={a.id} className="card agent-card">
                <h3>{a.name}</h3>
                <p className="mono" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>ID: {a.id}</p>

                {profile ? (
                  <>
                    <div style={{ margin: '12px 0' }}>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 4 }}>
                        Win Rate: {winRate}% ({totalGames} games)
                      </div>
                      <div className="stat-bar">
                        <div className="stat-fill win" style={{ width: `${winRate}%` }} />
                      </div>
                    </div>

                    {Object.keys(stats).length > 0 && (
                      <div style={{ fontSize: '0.8rem' }}>
                        {Object.entries(stats).map(([game, s]) => (
                          <div key={game} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', borderBottom: '1px solid var(--border)' }}>
                            <span style={{ textTransform: 'capitalize' }}>{game.replace('_', ' ')}</span>
                            <span className="elo">{s.elo?.toFixed(0) || '—'}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <p className="muted" style={{ fontSize: '0.85rem', marginTop: 8 }}>Could not load stats</p>
                )}

                <div className="quick-actions">
                  <Link to={`/agents/${a.id}`} className="btn btn-sm">Profile</Link>
                  <Link to={`/lobby`} className="btn btn-sm btn-secondary">Find Match</Link>
                  <button className="btn btn-sm" style={{ color: 'var(--red)' }} onClick={() => removeAgent(a.id)}>Remove</button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
