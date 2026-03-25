import React from 'react';

const COLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J'];
const STAR_POINTS = new Set(['2-2', '2-6', '6-2', '6-6', '4-4']);

export default function GoRenderer({ state }) {
  const board = state?.board;
  if (!board) return <div className="chess-empty">No board data</div>;

  const size = board.length;
  const captures = state.captures || {};

  return (
    <div className="go-wrapper">
      <div className="go-board" style={{ gridTemplateColumns: `repeat(${size}, 1fr)` }}>
        {board.map((row, ri) =>
          row.map((cell, ci) => {
            const key = `${ri}-${ci}`;
            const isStar = STAR_POINTS.has(key);
            return (
              <div key={key} className="go-intersection">
                {cell === 0 && isStar && <span className="go-star" />}
                {cell === 0 && !isStar && <span className="go-dot" />}
                {cell === 1 && <span className="go-stone black" />}
                {cell === 2 && <span className="go-stone white" />}
                {ci === 0 && <span className="go-rank-label">{size - ri}</span>}
                {ri === size - 1 && <span className="go-file-label">{COLS[ci]}</span>}
              </div>
            );
          })
        )}
      </div>
      <div className="go-captures">
        <span>Black captured: {captures[state.player1_id] || 0}</span>
        <span>White captured: {captures[state.player2_id] || 0}</span>
      </div>
    </div>
  );
}
