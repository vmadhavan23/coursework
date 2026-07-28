const BASE = "/api";

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!resp.ok) {
    let message = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      if (body?.error?.message) message = body.error.message;
    } catch {
      // response body wasn't JSON; keep the default message
    }
    const error = new Error(message);
    error.status = resp.status;
    throw error;
  }

  if (resp.status === 204) return null;
  return resp.json();
}

export const api = {
  createMatch: (payload) =>
    request("/matches", { method: "POST", body: JSON.stringify(payload) }),
  listMatches: (limit = 20, offset = 0) =>
    request(`/matches?limit=${limit}&offset=${offset}`),
  getMatch: (matchId) => request(`/matches/${matchId}`),
  deleteMatch: (matchId) => request(`/matches/${matchId}`, { method: "DELETE" }),
  recordPoint: (matchId, winner, tag) =>
    request(`/matches/${matchId}/points`, {
      method: "POST",
      body: JSON.stringify(tag ? { winner, tag } : { winner }),
    }),
  undoLastPoint: (matchId) =>
    request(`/matches/${matchId}/points/last`, { method: "DELETE" }),
  getSummary: (matchId) => request(`/matches/${matchId}/summary`),
  abandonMatch: (matchId) => request(`/matches/${matchId}/abandon`, { method: "POST" }),
  resetMatch: (matchId) => request(`/matches/${matchId}/reset`, { method: "POST" }),
};
