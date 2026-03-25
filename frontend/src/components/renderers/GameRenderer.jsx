import React from 'react';
import ChessRenderer from './ChessRenderer';
import GoRenderer from './GoRenderer';
import PokerRenderer from './PokerRenderer';
import NegotiationRenderer from './NegotiationRenderer';
import ReasoningRenderer from './ReasoningRenderer';
import AdventureRenderer from './AdventureRenderer';
import CodeChallengeRenderer from './CodeChallengeRenderer';

const RENDERERS = {
  chess: ChessRenderer,
  go: GoRenderer,
  poker: PokerRenderer,
  negotiation: NegotiationRenderer,
  reasoning: ReasoningRenderer,
  text_adventure: AdventureRenderer,
  code_challenge: CodeChallengeRenderer,
};

export default function GameRenderer({ state }) {
  if (!state) return null;

  const gameType = state.type || (state.board && Array.isArray(state.board) && state.board.length === 8 ? 'chess' : null);
  const Renderer = RENDERERS[gameType];

  if (Renderer) return <Renderer state={state} />;

  return <pre className="board-display">{JSON.stringify(state, null, 2)}</pre>;
}
