import React from 'react';

export default function ReasoningRenderer({ state }) {
  const puzzle = state.current_puzzle;
  const scores = state.scores || {};
  const maxScore = Math.max(...Object.values(scores), 1);

  return (
    <div className="reasoning-display">
      <div className="reasoning-progress">
        Puzzle {(state.puzzle_index ?? 0) + 1} / {state.total_puzzles ?? 5}
      </div>

      {puzzle && (
        <div className="puzzle-prompt">
          <p>{puzzle.prompt || puzzle.question || JSON.stringify(puzzle)}</p>
        </div>
      )}

      <div className="score-comparison">
        {Object.entries(scores).map(([player, score]) => (
          <div key={player} className="score-col">
            <div className="score-player">{player}</div>
            <div className="score-bar-wrap">
              <div className="score-bar-fill" style={{ height: `${(score / maxScore) * 100}%` }} />
            </div>
            <div className="score-value">{score} pts</div>
          </div>
        ))}
      </div>
    </div>
  );
}
