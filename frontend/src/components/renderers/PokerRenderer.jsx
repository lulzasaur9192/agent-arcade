import React from 'react';

const SUIT_SYMBOLS = { H: '\u2665', D: '\u2666', C: '\u2663', S: '\u2660' };
const RED_SUITS = new Set(['H', 'D']);

function Card({ card }) {
  if (!card || card === '??') {
    return <div className="poker-card hidden">??</div>;
  }
  const rank = card.slice(0, -1);
  const suit = card.slice(-1);
  const isRed = RED_SUITS.has(suit);
  return (
    <div className={`poker-card${isRed ? ' red' : ''}`}>
      <span className="card-rank">{rank}</span>
      <span className="card-suit">{SUIT_SYMBOLS[suit] || suit}</span>
    </div>
  );
}

function EmptySlot() {
  return <div className="poker-card empty" />;
}

const PHASES = ['pre-flop', 'flop', 'turn', 'river', 'showdown'];

export default function PokerRenderer({ state }) {
  const p1 = state.player1_id;
  const p2 = state.player2_id;
  const chips = state.chips || {};
  const holeCards = state.hole_cards || {};
  const community = state.community_cards || [];
  const bets = state.bets || {};
  const phase = (state.phase || 'pre-flop').toUpperCase().replace('-', '-');

  const communitySlots = [];
  for (let i = 0; i < 5; i++) {
    communitySlots.push(community[i] || null);
  }

  return (
    <div className="poker-table">
      <div className="poker-player-bar top">
        <span className="poker-player-name">{p2 || 'Player 2'}</span>
        <span className="poker-chips">{chips[p2] ?? '?'} chips</span>
        {state.dealer === p2 && <span className="poker-dealer">D</span>}
        {bets[p2] > 0 && <span className="poker-bet">Bet: {bets[p2]}</span>}
      </div>

      <div className="poker-hole-cards top">
        {(holeCards[p2] || ['??', '??']).map((c, i) => <Card key={i} card={c} />)}
      </div>

      <div className="poker-phase">{phase}</div>

      <div className="poker-community">
        {communitySlots.map((c, i) => c ? <Card key={i} card={c} /> : <EmptySlot key={i} />)}
      </div>

      <div className="poker-pot">Pot: {state.pot ?? 0}</div>

      <div className="poker-hole-cards bottom">
        {(holeCards[p1] || ['??', '??']).map((c, i) => <Card key={i} card={c} />)}
      </div>

      <div className="poker-player-bar bottom">
        <span className="poker-player-name">{p1 || 'Player 1'}</span>
        <span className="poker-chips">{chips[p1] ?? '?'} chips</span>
        {state.dealer === p1 && <span className="poker-dealer">D</span>}
        {bets[p1] > 0 && <span className="poker-bet">Bet: {bets[p1]}</span>}
      </div>

      <div className="poker-hand-info">
        Hand {state.hand_number ?? 1}/10
      </div>
    </div>
  );
}
