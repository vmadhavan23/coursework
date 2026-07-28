import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";

export default function NewMatch() {
  const navigate = useNavigate();
  const [playerOneName, setPlayerOneName] = useState("");
  const [playerTwoName, setPlayerTwoName] = useState("");
  const [pointsToWin, setPointsToWin] = useState(11);
  const [bestOf, setBestOf] = useState(3);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const trimmedOne = playerOneName.trim();
  const trimmedTwo = playerTwoName.trim();
  const canSubmit =
    trimmedOne.length > 0 && trimmedTwo.length > 0 && trimmedOne !== trimmedTwo;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const match = await api.createMatch({
        player_one_name: trimmedOne,
        player_two_name: trimmedTwo,
        points_to_win: pointsToWin,
        best_of: bestOf,
      });
      navigate(`/matches/${match.id}/score`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card">
      <h1>Start a new match</h1>
      <form onSubmit={handleSubmit}>
        <label>
          Player One
          <input
            value={playerOneName}
            onChange={(e) => setPlayerOneName(e.target.value)}
            placeholder="e.g. Alice"
          />
        </label>
        <label>
          Player Two
          <input
            value={playerTwoName}
            onChange={(e) => setPlayerTwoName(e.target.value)}
            placeholder="e.g. Bob"
          />
        </label>
        <label>
          Points to win a game
          <select
            value={pointsToWin}
            onChange={(e) => setPointsToWin(Number(e.target.value))}
          >
            <option value={11}>11</option>
            <option value={21}>21</option>
          </select>
        </label>
        <label>
          Match format
          <select value={bestOf} onChange={(e) => setBestOf(Number(e.target.value))}>
            <option value={1}>Best of 1</option>
            <option value={3}>Best of 3</option>
            <option value={5}>Best of 5</option>
          </select>
        </label>

        {trimmedOne.length > 0 && trimmedTwo.length > 0 && trimmedOne === trimmedTwo && (
          <p className="error">Player names must be different.</p>
        )}
        {error && <p className="error">{error}</p>}

        <button type="submit" disabled={!canSubmit || submitting}>
          {submitting ? "Starting…" : "Start Match"}
        </button>
      </form>
    </div>
  );
}
