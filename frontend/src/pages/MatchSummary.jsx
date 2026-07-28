import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";

function playerName(summary, slot) {
  return slot === "player_one"
    ? summary.player_one.display_name
    : summary.player_two.display_name;
}

export default function MatchSummary() {
  const { matchId } = useParams();
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getSummary(matchId).then(setSummary).catch((err) => setError(err.message));
  }, [matchId]);

  if (error) {
    return (
      <div className="card">
        <p className="error">{error}</p>
      </div>
    );
  }
  if (!summary) {
    return (
      <div className="card">
        <p>Loading summary…</p>
      </div>
    );
  }

  const p1 = summary.player_one.display_name;
  const p2 = summary.player_two.display_name;

  return (
    <div className="card">
      <h1>
        {p1} vs {p2}
      </h1>
      <p className="meta">
        {summary.status === "completed" && summary.winner
          ? `Winner: ${playerName(summary, summary.winner)}`
          : "In progress"}{" "}
        · Games {summary.games_won.player_one}–{summary.games_won.player_two}
      </p>

      <h2>Games</h2>
      <table>
        <thead>
          <tr>
            <th>Game</th>
            <th>{p1}</th>
            <th>{p2}</th>
            <th>Winner</th>
            <th>Margin</th>
          </tr>
        </thead>
        <tbody>
          {summary.games.map((g) => (
            <tr key={g.game_number}>
              <td>{g.game_number}</td>
              <td>{g.player_one_score}</td>
              <td>{g.player_two_score}</td>
              <td>{playerName(summary, g.winner)}</td>
              <td>{g.point_margin}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {summary.closest_game && summary.largest_margin_game && (
        <p className="meta">
          Closest game: Game {summary.closest_game.game_number} (margin{" "}
          {summary.closest_game.point_margin}) · Most one-sided: Game{" "}
          {summary.largest_margin_game.game_number} (margin{" "}
          {summary.largest_margin_game.point_margin})
        </p>
      )}

      <h2>Totals</h2>
      <table>
        <thead>
          <tr>
            <th></th>
            <th>{p1}</th>
            <th>{p2}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Points won</td>
            <td>{summary.totals.player_one.points_won}</td>
            <td>{summary.totals.player_two.points_won}</td>
          </tr>
          <tr>
            <td>Serve win %</td>
            <td>{summary.totals.player_one.serve_points_won_percentage ?? "–"}</td>
            <td>{summary.totals.player_two.serve_points_won_percentage ?? "–"}</td>
          </tr>
          <tr>
            <td>Longest streak</td>
            <td>{summary.totals.player_one.longest_streak}</td>
            <td>{summary.totals.player_two.longest_streak}</td>
          </tr>
          <tr>
            <td>Aces</td>
            <td>{summary.totals.player_one.tag_counts.ace}</td>
            <td>{summary.totals.player_two.tag_counts.ace}</td>
          </tr>
          <tr>
            <td>Unforced errors</td>
            <td>{summary.totals.player_one.tag_counts.unforced_error}</td>
            <td>{summary.totals.player_two.tag_counts.unforced_error}</td>
          </tr>
          <tr>
            <td>Winners</td>
            <td>{summary.totals.player_one.tag_counts.winner}</td>
            <td>{summary.totals.player_two.tag_counts.winner}</td>
          </tr>
        </tbody>
      </table>

      <Link to="/history">Back to history</Link>
    </div>
  );
}
