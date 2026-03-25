import React from 'react';

function formatMove(entry, gameType) {
  if (typeof entry === 'string') return entry;
  if (!entry || typeof entry !== 'object') return JSON.stringify(entry);

  switch (gameType) {
    case 'poker':
      return `${entry.player || '?'}: ${entry.action || '?'}${entry.amount ? ' ' + entry.amount : ''}`;
    case 'negotiation':
      if (entry.action === 'propose' && entry.proposal) {
        const alloc = Object.entries(entry.proposal).map(([k, v]) => `${k}:${v}`).join(', ');
        return `${entry.player || '?'}: propose {${alloc}}`;
      }
      return `${entry.player || '?'}: ${entry.action || JSON.stringify(entry)}`;
    case 'reasoning':
      return `${entry.player || '?'}: answered '${entry.answer ?? '?'}' ${entry.correct ? '\u2713' : '\u2717'}`;
    case 'code_challenge':
      return `${entry.player || '?'}: submitted (${entry.passed ?? '?'}/${entry.total ?? '?'} passed)`;
    case 'text_adventure':
      return entry.command || entry.move || JSON.stringify(entry);
    default:
      return JSON.stringify(entry);
  }
}

function PlayerSection({ state }) {
  const type = state.type;
  const p1 = state.player1_id || state.player_id || '?';
  const p2 = state.player2_id || '';

  switch (type) {
    case 'chess':
      return (
        <div className="player-info">
          <div className="player-row">
            <span className="piece-icon">{'\u2654'}</span>
            <span>White ({p1})</span>
            {state.current_player === p1 && <span className="turn-dot" />}
          </div>
          <div className="player-row">
            <span className="piece-icon">{'\u265A'}</span>
            <span>Black ({p2})</span>
            {state.current_player === p2 && <span className="turn-dot" />}
          </div>
        </div>
      );
    case 'go':
      return (
        <div className="player-info">
          <div className="player-row">
            <span className="piece-icon">{'\u25CF'}</span>
            <span>Black ({p1})</span>
            {state.current_player === p1 && <span className="turn-dot" />}
          </div>
          <div className="player-row">
            <span className="piece-icon">{'\u25CB'}</span>
            <span>White ({p2})</span>
            {state.current_player === p2 && <span className="turn-dot" />}
          </div>
          {state.captures && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
              Captures: B {state.captures[p1] || 0} | W {state.captures[p2] || 0}
            </div>
          )}
        </div>
      );
    case 'poker':
      return (
        <div className="player-info">
          {[p1, p2].filter(Boolean).map(p => (
            <div key={p} className="player-row">
              <span>{p}: {state.chips?.[p] ?? '?'} chips</span>
              {state.dealer === p && <span className="poker-dealer">D</span>}
              {state.current_player === p && <span className="turn-dot" />}
            </div>
          ))}
        </div>
      );
    case 'negotiation':
      return (
        <div className="player-info">
          {[p1, p2].filter(Boolean).map(p => (
            <div key={p} className="player-row">
              <span>{p}</span>
              {state.current_player === p && <span className="turn-dot" />}
            </div>
          ))}
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Round {state.round || 1}/{state.max_rounds || 10}
          </div>
        </div>
      );
    case 'reasoning':
    case 'code_challenge':
      return (
        <div className="player-info">
          {Object.entries(state.scores || {}).map(([p, s]) => (
            <div key={p} className="player-row">
              <span>{p}: {s} pts</span>
              {state.current_player === p && <span className="turn-dot" />}
            </div>
          ))}
        </div>
      );
    case 'text_adventure':
      return (
        <div className="player-info">
          <div className="player-row">
            <span>{p1}</span>
          </div>
        </div>
      );
    default:
      return (
        <div className="player-info">
          <div className="player-row"><span>{p1}</span></div>
          {p2 && <div className="player-row"><span>{p2}</span></div>}
        </div>
      );
  }
}

export default function GameSidebar({ state, moves }) {
  const type = state?.type || 'chess';
  const moveList = moves || state?.move_history || [];
  const isPaired = type === 'chess' || type === 'go';

  return (
    <>
      <div className="sidebar-section">
        <h3>Players</h3>
        {state && <PlayerSection state={state} />}
      </div>

      <div className="sidebar-section">
        <h3>Moves ({moveList.length})</h3>
        <div className="move-log">
          {moveList.length === 0 ? (
            <p className="muted">No moves yet.</p>
          ) : isPaired ? (
            <div className="move-pairs">
              {moveList.reduce((pairs, m, i) => {
                if (i % 2 === 0) pairs.push([m]);
                else pairs[pairs.length - 1].push(m);
                return pairs;
              }, []).map((pair, i) => (
                <div key={i} className="move-pair">
                  <span className="move-num">{i + 1}.</span>
                  <span className="move-white">{typeof pair[0] === 'string' ? pair[0] : formatMove(pair[0], type)}</span>
                  <span className="move-black">{pair[1] ? (typeof pair[1] === 'string' ? pair[1] : formatMove(pair[1], type)) : ''}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="move-list-flat">
              {moveList.map((m, i) => (
                <div key={i} className="move-entry">
                  <span className="move-num">{i + 1}.</span>
                  <span>{formatMove(m, type)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
