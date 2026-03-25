import React from 'react';
import ChessBoard from '../ChessBoard';

export default function ChessRenderer({ state }) {
  if (!state?.board) return <div className="chess-empty">No board data</div>;
  return <ChessBoard board={state.board} />;
}
