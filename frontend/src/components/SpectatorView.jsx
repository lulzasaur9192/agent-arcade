import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getGame } from '../api';
import ChessBoard from './ChessBoard';

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
          {state?.board && Array.isArray(state.board) && state.board.length === 8 ? (
            <ChessBoard board={state.board} />
          ) : state ? (
            <pre className="board-display">{JSON.stringify(state, null, 2)}</pre>
          ) : (
            <p className="muted" style={{ padding: 40, textAlign: 'center' }}>Waiting for game state...</p>
          )}
          {state?.game_over && (
            <div className="game-result-banner">
              {state.winner ? `Winner: Player ${state.winner}` : 'Game Over'}
              {state.reason && ` — ${state.reason}`}
            </div>
          )}
        </div>

        <div className="card sidebar-card">
          <div className="sidebar-section">
            <h3>Players</h3>
            {state && (
              <div className="player-info">
                <div className="player-row">
                  <span className="piece-icon">♔</span>
                  <span>White (Player {state.player1_id || '?'})</span>
                  {state.current_player === state.player1_id && <span className="turn-dot" />}
                </div>
                <div className="player-row">
                  <span className="piece-icon">♚</span>
                  <span>Black (Player {state.player2_id || '?'})</span>
                  {state.current_player === state.player2_id && <span className="turn-dot" />}
                </div>
              </div>
            )}
          </div>

          <div className="sidebar-section">
            <h3>Moves ({moves.length})</h3>
            <div className="move-log" ref={logRef}>
              {moves.length === 0 ? (
                <p className="muted">No moves yet.</p>
              ) : (
                <div className="move-pairs">
                  {moves.reduce((pairs, m, i) => {
                    if (i % 2 === 0) pairs.push([m]);
                    else pairs[pairs.length - 1].push(m);
                    return pairs;
                  }, []).map((pair, i) => (
                    <div key={i} className="move-pair">
                      <span className="move-num">{i + 1}.</span>
                      <span className="move-white">{pair[0]}</span>
                      <span className="move-black">{pair[1] || ''}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="spectator-controls">
            <span className={`status-indicator ${polling ? 'live' : 'ended'}`}>
              {polling ? 'Live — updating every 2s' : 'Game ended'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
