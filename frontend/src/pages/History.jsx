import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

export default function History() {
  const [matches, setMatches] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.listMatches();
      setMatches(data.matches);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleDelete(matchId) {
    if (!window.confirm("Delete this match from history? This cannot be undone.")) return;
    try {
      await api.deleteMatch(matchId);
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="card">
      <h1>Match History</h1>
      {error && <p className="error">{error}</p>}
      {matches === null ? (
        <p>Loading…</p>
      ) : matches.length === 0 ? (
        <p>No completed matches yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Players</th>
              <th>Score</th>
              <th>Winner</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {matches.map((m) => (
              <tr key={m.id}>
                <td>{new Date(m.completed_at ?? m.created_at).toLocaleString()}</td>
                <td>
                  {m.player_one.display_name} vs {m.player_two.display_name}
                </td>
                <td>
                  {m.games_won.player_one}–{m.games_won.player_two}
                </td>
                <td>
                  {m.winner === "player_one"
                    ? m.player_one.display_name
                    : m.winner === "player_two"
                    ? m.player_two.display_name
                    : "–"}
                </td>
                <td>
                  <Link to={`/matches/${m.id}/summary`}>View</Link>{" "}
                  <button onClick={() => handleDelete(m.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
