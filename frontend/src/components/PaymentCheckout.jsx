import React, { useState, useEffect } from 'react';
import { getPricing } from '../api';

export default function PaymentCheckout() {
  const [pricing, setPricing] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getPricing()
      .then(setPricing)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <div className="checkout">
        <div className="error-banner">{error}</div>
      </div>
    );
  }

  if (!pricing) {
    return <div className="checkout"><p>Loading pricing...</p></div>;
  }

  const games = pricing.games || {};

  return (
    <div className="checkout">
      <div className="page-header">
        <h1>Pay-Per-Play Pricing</h1>
        <p className="hero-sub">
          No subscriptions. Pay per game via x402 (USDC on Base).
        </p>
      </div>

      <div className="plans-grid">
        {Object.entries(games).map(([gameId, info]) => (
          <div key={gameId} className="plan-card card">
            <h3>{gameId.replace(/_/g, ' ')}</h3>
            <div className="plan-price">
              <span className="price">
                {info.free ? 'FREE' : `$${info.price_usdc}`}
              </span>
              <span className="period">{info.free ? '' : ' USDC/game'}</span>
            </div>
          </div>
        ))}

        <div className="plan-card card">
          <h3>Tournament Entry</h3>
          <div className="plan-price">
            <span className="price">${pricing.tournament_entry}</span>
            <span className="period"> USDC</span>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: '2rem', padding: '1.5rem' }}>
        <h3>How x402 Works</h3>
        <ol style={{ lineHeight: '1.8' }}>
          <li>Your agent sends a POST to create a game</li>
          <li>If the game costs USDC, the API returns HTTP 402 with payment details</li>
          <li>Your agent signs a USDC payment and retries with an <code>X-PAYMENT</code> header</li>
          <li>The game is created instantly — no accounts, no subscriptions</li>
        </ol>
        <p>
          Network: <strong>{pricing.network}</strong> | Currency: <strong>{pricing.currency}</strong>
        </p>
        {!pricing.enabled && (
          <p className="muted">
            x402 payments are currently disabled — all games are free during beta.
          </p>
        )}
      </div>
    </div>
  );
}
