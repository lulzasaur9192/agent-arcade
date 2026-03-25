import React from 'react';

const RESOURCE_COLORS = { gold: '#f59e0b', wood: '#92400e', stone: '#6b7280' };

export default function NegotiationRenderer({ state }) {
  const pool = state.pool || {};
  const maxVal = Math.max(...Object.values(pool), 1);
  const proposal = state.current_proposal;

  return (
    <div className="negotiation-display">
      <div className="negotiation-round">
        Round {state.round ?? 1} / {state.max_rounds ?? 10}
        <div className="round-progress">
          <div className="round-fill" style={{ width: `${((state.round || 1) / (state.max_rounds || 10)) * 100}%` }} />
        </div>
      </div>

      <div className="resource-pool">
        <h4>Resource Pool (value: {state.pool_value ?? '?'})</h4>
        {Object.entries(pool).map(([name, amount]) => (
          <div key={name} className="resource-bar-row">
            <span className="resource-label">{name}</span>
            <div className="resource-bar">
              <div
                className="resource-fill"
                style={{
                  width: `${(amount / maxVal) * 100}%`,
                  background: RESOURCE_COLORS[name] || 'var(--primary)',
                }}
              />
            </div>
            <span className="resource-value">{amount}</span>
          </div>
        ))}
      </div>

      {proposal && (
        <div className="proposal-section">
          <h4>Current Proposal</h4>
          <div className="proposal-split">
            {Object.entries(proposal).map(([player, alloc]) => (
              <div key={player} className="proposal-col">
                <strong>{player}</strong>
                {typeof alloc === 'object' && Object.entries(alloc).map(([r, v]) => (
                  <div key={r} className="proposal-item">
                    <span style={{ color: RESOURCE_COLORS[r] || 'var(--text)' }}>{r}</span>: {v}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
