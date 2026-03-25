import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getGames, createGame, getAgents } from '../api';

export default function GameLobby() {
  const [searchParams] = useSearchParams();
  const filterGame = searchParams.get('game') || '';
  const [games, setGames] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ type: filterGame || 'chess', player1_id: '', player2_id: '' });

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
    getAgents().then((d) => setAgents(d.agents || [])).catch(() => {});
    const interval = setInterval(fetchGames, 5000);
    return () => clearInterval(interval);
  }, [fetchGames]);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await createGame(form);
      setShowCreate(false);
      setForm({ type: filterGame || 'chess', player1_id: '', player2_id: '' });
      fetchGames();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="lobby">
      <div className="page-header">
        <h1>Game Lobby {filterGame && <span className="filter-tag">{filterGame}</span>}</h1>
        <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'Cancel' : '+ New Game'}
        </button>
      </div>

      {showCreate && (
        <form className="create-form card" onSubmit={handleCreate}>
          <h3>Create Game</h3>
          <div className="form-row">
            <label>
              Game Type
              <select
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value })}
              >
                <option value="chess">Chess</option>
                <option value="code_challenge">Code Challenge</option>
                <option value="text_adventure">Text Adventure</option>
                <option value="poker">Texas Hold'em</option>
                <option value="negotiation">Negotiation</option>
                <option value="reasoning">Reasoning</option>
                <option value="go">Go (9x9)</option>
              </select>
            </label>
            <label>
              Player 1
              <select
                value={form.player1_id}
                onChange={(e) => setForm({ ...form, player1_id: e.target.value })}
                required
              >
                <option value="">Select agent...</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>{a.name} (#{a.id})</option>
                ))}
              </select>
            </label>
            {form.type !== 'text_adventure' && (
              <label>
                Player 2
                <select
                  value={form.player2_id}
                  onChange={(e) => setForm({ ...form, player2_id: e.target.value })}
                  required
                >
                  <option value="">Select agent...</option>
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>{a.name} (#{a.id})</option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <button type="submit" className="btn btn-primary">Create</button>
        </form>
      )}

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <div className="loading">Loading games...</div>
      ) : games.length === 0 ? (
        <div className="empty-state">
          <p>No active games. Create one to get started!</p>
        </div>
      ) : (
        <div className="games-table">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {games.map((g) => (
                <tr key={g.id}>
                  <td>Game #{g.id}</td>
                  <td>{g.type}</td>
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
