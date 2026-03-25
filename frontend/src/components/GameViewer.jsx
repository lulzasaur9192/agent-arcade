import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getGame } from '../api';
import GameRenderer from './renderers/GameRenderer';
import GameSidebar from './renderers/GameSidebar';

export default function GameViewer() {
  const { id } = useParams();
  const [game, setGame] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getGame(id);
        if (!cancelled) setGame(data);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 3000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [id]);

  if (loading) return <div className="loading">Loading game...</div>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!game) return <div className="empty-state">Game not found.</div>;

  const isOver = game.game_over;

  return (
    <div className="game-viewer">
      <div className="page-header">
        <h1>Game #{id}</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          {!isOver && <Link to={`/spectate/${id}`} className="btn btn-primary">Watch Live</Link>}
          <Link to="/lobby" className="btn btn-secondary">Back to Lobby</Link>
        </div>
      </div>

      <div className="spectator-layout">
        <div className="card board-card">
          <GameRenderer state={game} />
          {isOver && (
            <div className="game-result-banner">
              {game.winner ? `Winner: Player ${game.winner}` : 'Game Over'}
              {game.reason && ` \u2014 ${game.reason}`}
            </div>
          )}
        </div>

        <div className="card sidebar-card">
          <div className="sidebar-section">
            <h3>Details</h3>
            <dl className="detail-list">
              <dt>Status</dt>
              <dd>
                <span className={`badge ${isOver ? 'badge-finished' : 'badge-active'}`}>
                  {isOver ? 'finished' : 'active'}
                </span>
              </dd>
              <dt>Type</dt><dd>{game.type || 'chess'}</dd>
              <dt>Moves</dt><dd>{game.move_count ?? game.move_history?.length ?? '\u2014'}</dd>
            </dl>
          </div>
          <GameSidebar state={game} />
        </div>
      </div>
    </div>
  );
}
