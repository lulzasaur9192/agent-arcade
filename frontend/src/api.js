const API_BASE = '/api';

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || `Request failed: ${res.status}`);
    }
    return res.json();
  } catch (err) {
    if (err.name === 'TypeError') {
      throw new Error('Network error — is the backend running?');
    }
    throw err;
  }
}

// Games
export const getGames = () => request('/games');
export const getGame = (id) => request(`/games/${id}`);
export const createGame = (data) =>
  request('/games/create', { method: 'POST', body: JSON.stringify(data) });

// Leaderboard
export const getLeaderboard = (gameType = '') =>
  request(gameType ? `/leaderboard/${encodeURIComponent(gameType)}` : '/leaderboard');

// Agents
export const getAgents = () => request('/agents');
export const getAgent = (id) => request(`/agents/${id}/profile`);
export const registerAgent = (data) =>
  request('/agents/register', { method: 'POST', body: JSON.stringify(data) });

// Matchmaking
export const joinMatchmaking = (data) =>
  request('/matchmaking/join', { method: 'POST', body: JSON.stringify(data) });

// Spectator
export const getReplay = (id) => request(`/games/${id}/replay`);

// Pricing
export const getPricing = () => request('/pricing');
