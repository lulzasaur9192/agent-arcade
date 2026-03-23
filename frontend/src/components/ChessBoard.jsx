import React from 'react';

const PIECE_MAP = {
  'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
  'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
};

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
const RANKS = ['8', '7', '6', '5', '4', '3', '2', '1'];

export default function ChessBoard({ board, lastMove }) {
  if (!board || !Array.isArray(board) || board.length !== 8) {
    return <div className="chess-empty">No board data</div>;
  }

  return (
    <div className="chess-wrapper">
      <div className="chess-board">
        {board.map((row, ri) => (
          row.map((cell, ci) => {
            const isLight = (ri + ci) % 2 === 0;
            const piece = cell ? PIECE_MAP[cell] || cell : null;
            const isWhitePiece = cell && cell === cell.toUpperCase();
            return (
              <div
                key={`${ri}-${ci}`}
                className={`chess-sq ${isLight ? 'light' : 'dark'}${piece ? (isWhitePiece ? ' white-piece' : ' black-piece') : ''}`}
              >
                {ci === 0 && <span className="rank-label">{RANKS[ri]}</span>}
                {ri === 7 && <span className="file-label">{FILES[ci]}</span>}
                {piece && <span className="chess-piece">{piece}</span>}
              </div>
            );
          })
        ))}
      </div>
    </div>
  );
}
