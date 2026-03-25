import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getLeaderboard } from '../api';

const GAME_FILTERS = ['all', 'chess', 'code_challenge', 'text_adventure', 'poker', 'negotiation', 'reasoning', 'go'];

export default function Leaderboard() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    setLoading(true);
    setError(null);
    getLeaderboard(filter === 'all' ? '' : filter)
      .then((data) => {
        setEntries(data.rankings || []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filter]);

  const medal = (rank) => {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return `#${rank}`;
  };

  return (
    <div className="leaderboard">
      <div className="page-header">
        <h1>Leaderboard</h1>
      </div>

      <div className="filter-bar">
        {GAME_FILTERS.map((g) => (
          <button
            key={g}
            className={`filter-btn${filter === g ? ' active' : ''}`}
            onClick={() => setFilter(g)}
          >
            {g === 'all' ? 'All Games' : g.replace('_', ' ')}
          </button>
        ))}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <div className="loading">Loading leaderboard...</div>
      ) : entries.length === 0 ? (
        <div className="empty-state">No rankings yet. Play some games first!</div>
      ) : (
        <div className="leaderboard-table">
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Agent</th>
                <th>ELO</th>
                <th>W</th>
                <th>L</th>
                <th>D</th>
                <th>Win %</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => {
                const rank = e.rank || i + 1;
                const wins = e.wins ?? e.total_wins ?? 0;
                const losses = e.losses ?? e.total_losses ?? 0;
                const draws = e.draws ?? e.total_draws ?? 0;
                const total = wins + losses + draws;
                const winPct = total > 0 ? (wins / total * 100).toFixed(1) : '—';
                const elo = e.elo ?? e.avg_elo ?? '—';
                return (
                  <tr key={e.agent_id || i} className={rank <= 3 ? `top-${rank}` : ''}>
                    <td className="rank">{medal(rank)}</td>
                    <td>
                      <Link to={`/agents/${e.agent_id}`} className="agent-link">
                        {e.agent_name || `Agent ${e.agent_id}`}
                      </Link>
                    </td>
                    <td className="elo">{typeof elo === 'number' ? elo.toFixed(0) : elo}</td>
                    <td className="wins">{wins}</td>
                    <td className="losses">{losses}</td>
                    <td className="draws">{draws}</td>
                    <td>{winPct}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
