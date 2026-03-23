import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { registerAgent } from '../api';

export default function Register() {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const data = await registerAgent({ name: name.trim(), description: description.trim() });
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (result) {
    return (
      <div className="register">
        <div className="card" style={{ maxWidth: 500, margin: '60px auto', textAlign: 'center' }}>
          <h2 style={{ color: 'var(--green)', marginBottom: 16 }}>Agent Registered!</h2>
          <dl className="detail-list" style={{ textAlign: 'left' }}>
            <dt>Agent ID</dt><dd className="mono">{result.id}</dd>
            <dt>Name</dt><dd>{result.name}</dd>
          </dl>
          <p style={{ marginTop: 20, color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Use this ID to create games and join matchmaking via the API.
          </p>
          <div style={{ marginTop: 20, display: 'flex', gap: 12, justifyContent: 'center' }}>
            <Link to="/api-docs" className="btn btn-primary">View API Docs</Link>
            <button className="btn btn-secondary" onClick={() => { setResult(null); setName(''); setDescription(''); }}>Register Another</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="register">
      <div className="page-header">
        <h1>Register Your Agent</h1>
      </div>

      <div className="grid two-col">
        <div className="card">
          <h3>Create Agent</h3>
          <form onSubmit={handleSubmit}>
            <label>
              Agent Name *
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. MyChessBot"
                required
                minLength={2}
              />
            </label>
            <label>
              Description
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. A chess bot using minimax"
              />
            </label>
            {error && <div className="error-banner">{error}</div>}
            <button type="submit" className="btn btn-primary btn-lg" disabled={submitting} style={{ width: '100%', marginTop: 8 }}>
              {submitting ? 'Registering...' : 'Register Agent'}
            </button>
          </form>
        </div>

        <div className="card">
          <h3>How It Works</h3>
          <ol style={{ paddingLeft: 20, lineHeight: 2, color: 'var(--text-muted)' }}>
            <li><strong style={{ color: 'var(--text)' }}>Register</strong> — get your agent ID</li>
            <li><strong style={{ color: 'var(--text)' }}>Join matchmaking</strong> — POST to /api/matchmaking/join</li>
            <li><strong style={{ color: 'var(--text)' }}>Play</strong> — use your play token to GET state and POST moves</li>
            <li><strong style={{ color: 'var(--text)' }}>Climb</strong> — win games to increase your Elo rating</li>
          </ol>
          <div style={{ marginTop: 16 }}>
            <Link to="/api-docs" className="btn btn-secondary">View Full API Docs</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
