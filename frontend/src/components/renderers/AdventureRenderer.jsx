import React from 'react';

export default function AdventureRenderer({ state }) {
  const history = state.move_history || [];

  return (
    <div className="adventure-display">
      <div className="adventure-room">
        <h3>{state.current_room || 'Unknown Room'}</h3>
        <p>{state.description || ''}</p>
      </div>

      {state.inventory && state.inventory.length > 0 && (
        <div className="adventure-inventory">
          <span className="inventory-label">Inventory:</span>
          <div className="inventory-pills">
            {state.inventory.map((item, i) => (
              <span key={i} className="inventory-pill">{item}</span>
            ))}
          </div>
        </div>
      )}

      <div className="adventure-terminal">
        {history.length === 0 ? (
          <p className="muted">No commands yet.</p>
        ) : (
          history.map((entry, i) => (
            <div key={i} className="terminal-line">
              {typeof entry === 'string' ? (
                <span className="terminal-cmd">&gt; {entry}</span>
              ) : (
                <>
                  <span className="terminal-cmd">&gt; {entry.command || entry.move || JSON.stringify(entry)}</span>
                  {entry.response && <span className="terminal-response">{entry.response}</span>}
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
