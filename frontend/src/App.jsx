import { Link, Route, Routes } from "react-router-dom";
import History from "./pages/History.jsx";
import LiveScoring from "./pages/LiveScoring.jsx";
import MatchSummary from "./pages/MatchSummary.jsx";
import NewMatch from "./pages/NewMatch.jsx";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" className="brand">
          Table Tennis Stats
        </Link>
        <nav>
          <Link to="/">New Match</Link>
          <Link to="/history">History</Link>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<NewMatch />} />
          <Route path="/matches/:matchId/score" element={<LiveScoring />} />
          <Route path="/matches/:matchId/summary" element={<MatchSummary />} />
          <Route path="/history" element={<History />} />
        </Routes>
      </main>
    </div>
  );
}
