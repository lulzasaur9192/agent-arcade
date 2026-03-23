import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getGame } from '../api';
import ChessBoard from './ChessBoard';

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
          {game.board && Array.isArray(game.board) && game.board.length === 8 ? (
            <ChessBoard board={game.board} />
          ) : (
            <pre className="board-display">{JSON.stringify(game, null, 2)}</pre>
          )}
        </div>

        <div className="card sidebar-card">
          <h3>Details</h3>
          <dl className="detail-list">
            <dt>Status</dt>
            <dd>
              <span className={`badge ${isOver ? 'badge-finished' : 'badge-active'}`}>
                {isOver ? 'finished' : 'active'}
              </span>
            </dd>
            <dt>Current Turn</dt><dd>Player {game.current_player || '—'}</dd>
            <dt>Moves</dt><dd>{game.move_count ?? game.move_history?.length ?? '—'}</dd>
          </dl>

          {isOver && game.winner && (
            <div className="game-result-banner" style={{ marginTop: 16 }}>
              Winner: Player {game.winner}
              {game.reason && ` — ${game.reason}`}
            </div>
          )}

          {game.move_history && game.move_history.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3>Last Moves</h3>
              <div className="move-pairs">
                {game.move_history.slice(-10).reduce((pairs, m, i, arr) => {
                  const offset = Math.floor((game.move_history.length - arr.length) / 2);
                  if (i % 2 === 0) pairs.push([m]);
                  else pairs[pairs.length - 1].push(m);
                  return pairs;
                }, []).map((pair, i) => {
                  const moveNum = Math.floor((game.move_history.length - 10) / 2) + i + 1;
                  return (
                    <div key={i} className="move-pair">
                      <span className="move-num">{Math.max(1, moveNum)}.</span>
                      <span className="move-white">{pair[0]}</span>
                      <span className="move-black">{pair[1] || ''}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
