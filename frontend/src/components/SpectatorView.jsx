import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getGame } from '../api';
import GameRenderer from './renderers/GameRenderer';
import GameSidebar from './renderers/GameSidebar';

export default function SpectatorView() {
  const { id } = useParams();
  const [state, setState] = useState(null);
  const [moves, setMoves] = useState([]);
  const [error, setError] = useState(null);
  const [polling, setPolling] = useState(true);
  const logRef = useRef(null);

  useEffect(() => {
    if (!polling) return;
    let cancelled = false;

    async function poll() {
      try {
        const data = await getGame(id);
        if (cancelled) return;
        setState(data);
        if (data.move_history) setMoves(data.move_history);
        if (data.game_over) setPolling(false);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }

    poll();
    const interval = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [id, polling]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [moves]);

  return (
    <div className="spectator">
      <div className="page-header">
        <h1>
          <span className={`live-dot${!polling ? ' ended' : ''}`} />
          {polling ? 'Live' : 'Finished'}: Game #{id}
        </h1>
        <Link to={`/games/${id}`} className="btn btn-secondary">Details</Link>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="spectator-layout">
        <div className="card board-card">
          {state ? (
            <GameRenderer state={state} />
          ) : (
            <p className="muted" style={{ padding: 40, textAlign: 'center' }}>Waiting for game state...</p>
          )}
          {state?.game_over && (
            <div className="game-result-banner">
              {state.winner ? `Winner: Player ${state.winner}` : 'Game Over'}
              {state.reason && ` \u2014 ${state.reason}`}
            </div>
          )}
        </div>

        <div className="card sidebar-card" ref={logRef}>
          {state && <GameSidebar state={state} moves={moves} />}
          <div className="spectator-controls">
            <span className={`status-indicator ${polling ? 'live' : 'ended'}`}>
              {polling ? 'Live \u2014 updating every 2s' : 'Game ended'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
