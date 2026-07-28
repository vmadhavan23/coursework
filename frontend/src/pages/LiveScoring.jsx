import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";

const TAG_OPTIONS = [
  { value: "", label: "No tag" },
  { value: "ace", label: "Ace" },
  { value: "unforced_error", label: "Unforced error" },
  { value: "winner", label: "Winner shot" },
];

export default function LiveScoring() {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const [match, setMatch] = useState(null);
  const [error, setError] = useState(null);
  const [tag, setTag] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await api.getMatch(matchId);
      setMatch(data);
    } catch (err) {
      setError(err.message);
    }
  }, [matchId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function withBusy(fn) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function recordPoint(winner) {
    withBusy(async () => {
      const updated = await api.recordPoint(matchId, winner, tag || undefined);
      setMatch(updated);
      setTag("");
    });
  }

  function undo() {
    withBusy(async () => {
      const updated = await api.undoLastPoint(matchId);
      setMatch(updated);
    });
  }

  function abandon() {
    if (!window.confirm("Abandon this match without saving it?")) return;
    withBusy(async () => {
      await api.abandonMatch(matchId);
      navigate("/");
    });
  }

  function reset() {
    if (!window.confirm("Reset the score to 0-0? This clears all points so far.")) return;
    withBusy(async () => {
      const updated = await api.resetMatch(matchId);
      setMatch(updated);
    });
  }

  if (!match) {
    return (
      <div className="card">
        {error ? <p className="error">{error}</p> : <p>Loading match…</p>}
      </div>
    );
  }

  const { player_one, player_two, current_score, games_won, serving_player, status } = match;

  return (
    <div className="card">
      <h1>
        {player_one.display_name} vs {player_two.display_name}
      </h1>
      <p className="meta">
        Game {match.current_game_number} · First to {match.points_to_win} · Best of{" "}
        {match.best_of}
      </p>

      <div className="scoreboard">
        <div className={`player-score ${serving_player === "player_one" ? "serving" : ""}`}>
          <div className="name">{player_one.display_name}</div>
          <div className="score">{current_score.player_one}</div>
          <div className="games-won">Games: {games_won.player_one}</div>
        </div>
        <div className="vs">–</div>
        <div className={`player-score ${serving_player === "player_two" ? "serving" : ""}`}>
          <div className="name">{player_two.display_name}</div>
          <div className="score">{current_score.player_two}</div>
          <div className="games-won">Games: {games_won.player_two}</div>
        </div>
      </div>

      {status === "completed" ? (
        <div className="completed-banner">
          <p>
            Match complete — winner:{" "}
            {match.winner === "player_one" ? player_one.display_name : player_two.display_name}
          </p>
          <button onClick={() => navigate(`/matches/${matchId}/summary`)}>
            View Summary
          </button>
        </div>
      ) : (
        <>
          <label className="tag-select">
            Tag next point (optional)
            <select value={tag} onChange={(e) => setTag(e.target.value)}>
              {TAG_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <div className="point-buttons">
            <button disabled={busy} onClick={() => recordPoint("player_one")}>
              Point: {player_one.display_name}
            </button>
            <button disabled={busy} onClick={() => recordPoint("player_two")}>
              Point: {player_two.display_name}
            </button>
          </div>
        </>
      )}

      {error && <p className="error">{error}</p>}

      <div className="control-buttons">
        <button disabled={busy} onClick={undo}>
          Undo Last Point
        </button>
        {status !== "completed" && (
          <>
            <button disabled={busy} onClick={reset}>
              Reset Match
            </button>
            <button disabled={busy} className="danger" onClick={abandon}>
              Abandon Match
            </button>
          </>
        )}
      </div>
    </div>
  );
}
