import React from 'react';

export default function CodeChallengeRenderer({ state }) {
  const challenge = state.challenge;
  const scores = state.scores || {};
  const history = state.move_history || [];
  const lastEntry = history.length > 0 ? history[history.length - 1] : null;

  return (
    <div className="codechallenge-display">
      <div className="codechallenge-round">
        Round {state.current_round ?? 1} / {state.max_rounds ?? 3}
      </div>

      {challenge && (
        <div className="challenge-card">
          <h3>{challenge.title || challenge.name || 'Challenge'}</h3>
          <p>{challenge.description || challenge.prompt || ''}</p>
        </div>
      )}

      <div className="score-comparison">
        {Object.entries(scores).map(([player, score]) => (
          <div key={player} className="score-col">
            <div className="score-player">{player}</div>
            <div className="score-value">{score} pts</div>
          </div>
        ))}
      </div>

      {lastEntry && (
        <div className="submission-result">
          <h4>Last Submission</h4>
          <p>
            {typeof lastEntry === 'object'
              ? `${lastEntry.player || '?'}: ${lastEntry.passed ?? '?'}/${lastEntry.total ?? '?'} tests passed`
              : String(lastEntry)}
          </p>
        </div>
      )}
    </div>
  );
}
