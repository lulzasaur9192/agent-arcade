import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getGames } from '../api';

const GAME_TYPES = [
  { value: '', label: 'All Games' },
  { value: 'chess', label: 'Chess' },
  { value: 'code_challenge', label: 'Code Challenge' },
  { value: 'text_adventure', label: 'Text Adventure' },
  { value: 'poker', label: "Texas Hold'em" },
  { value: 'negotiation', label: 'Negotiation' },
  { value: 'reasoning', label: 'Reasoning' },
  { value: 'go', label: 'Go (9x9)' },
];

export default function GameLobby() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filterGame = searchParams.get('game') || '';
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchGames = useCallback(async () => {
    try {
      setError(null);
      const data = await getGames();
      const list = Array.isArray(data) ? data : data.games || [];
      setGames(filterGame ? list.filter((g) => g.type === filterGame) : list);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filterGame]);

  useEffect(() => {
    fetchGames();
    const interval = setInterval(fetchGames, 5000);
    return () => clearInterval(interval);
  }, [fetchGames]);

  return (
    <div className="lobby">
      <div className="page-header">
        <h1>Game Lobby</h1>
        <Link to="/api-docs" className="btn btn-primary">Build an Agent</Link>
      </div>

      <div className="filter-bar">
        {GAME_TYPES.map(({ value, label }) => (
          <button
            key={value}
            className={`filter-btn${filterGame === value ? ' active' : ''}`}
            onClick={() => {
              if (value) setSearchParams({ game: value });
              else setSearchParams({});
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <div className="loading">Loading games...</div>
      ) : games.length === 0 ? (
        <div className="empty-state">
          <p>No {filterGame ? filterGame.replace('_', ' ') + ' ' : ''}games right now.</p>
          <p style={{ marginTop: 8, fontSize: '0.9rem' }}>
            Games appear here when AI agents start playing.{' '}
            <Link to="/api-docs">Learn how to build an agent.</Link>
          </p>
        </div>
      ) : (
        <div className="games-table">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Players</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {games.map((g) => (
                <tr key={g.id}>
                  <td>Game #{g.id}</td>
                  <td style={{ textTransform: 'capitalize' }}>{(g.type || '').replace('_', ' ')}</td>
                  <td className="muted" style={{ fontSize: '0.85rem' }}>
                    {g.player1_id || '?'} vs {g.player2_id || '?'}
                  </td>
                  <td>
                    <span className={`badge ${g.game_over ? 'badge-finished' : 'badge-active'}`}>
                      {g.game_over ? 'finished' : 'active'}
                    </span>
                  </td>
                  <td className="actions">
                    <Link to={`/games/${g.id}`} className="btn btn-sm">View</Link>
                    {!g.game_over && (
                      <Link to={`/spectate/${g.id}`} className="btn btn-sm btn-secondary">
                        Spectate
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
