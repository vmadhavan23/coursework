# Table Tennis Match Stats App — Requirements

## Overview

An open-source, locally-runnable application that lets someone score a table tennis match point-by-point
and automatically generates key match statistics. Aimed at recreational players, club members, and coaches
who want basic post-match insight without any cloud account, network dependency, or specialized hardware.

This is an MVP/demo-scope project. It intentionally omits production concerns (auth, multi-user support,
scaling, hardening) and hardware/video-based tracking — everything is entered manually by a person watching
the match.

## Personas

- **P1 — Casual Player (Self-Scorer)**: A recreational player who plays occasional matches with friends and
  wants to score their own match live, then glance at simple stats afterward (who won, how close it was) to
  compare with past matches. Has no coaching background and wants the app to be effortless to use mid-match.

- **P2 — Sideline Scorer / Coach**: Watches a match from the side (not playing) and scores it for two other
  players in real time, sometimes tagging notable points (aces, unforced errors). Reviews the generated
  stats with the players after the match to point out patterns (e.g., who's stronger on serve, who fades in
  long rallies).

## User Flows

### Flow 1 — Start a New Match
1. User opens the app.
2. User enters names for Player A and Player B.
3. User selects the match format: points needed to win a game (e.g., 11 or 21) and number of games needed to
   win the match (e.g., best of 3 or best of 5).
4. User starts the match; scoring begins at 0–0, Game 1.

### Flow 2 — Live Point-by-Point Scoring
1. During play, after each point, the user selects which player won that point.
2. Optionally, the user tags the point with an outcome type (e.g., ace, unforced error, winner).
3. The app updates the running game score and indicates whose serve is next.
4. If the user makes a mistake, they undo the last recorded point and re-enter it.
5. When a player reaches the points-to-win with the required lead, the app ends the game, records the game
   result, and starts the next game (unless the match is already decided).

### Flow 3 — Match Completion
1. Once a player reaches the required number of games won, the app ends the match.
2. The app saves the completed match locally and shows the match summary with generated statistics.

### Flow 4 — Review Match History
1. From the home screen, the user opens the match history list, showing past matches with date, players,
   and final score.
2. The user selects a past match to view its full statistics summary again.
3. The user may delete a match they no longer want to keep.

### Flow 5 — Abandon or Reset a Match
1. Mid-match, the user chooses to abandon the match without saving a partial result, returning to the home
   screen.
2. Alternatively, the user resets the current match to 0–0 with the same two players and format, discarding
   points scored so far.

### Flow 6 — AI Video Match Report (Post-MVP addendum)
1. The user opens the Analyze Video page and pastes a URL to a match video (YouTube supported).
2. The user submits the URL; the app sends it to an AI model for a best-effort read of the match.
3. The app displays the AI's report: a summary, players identified, an estimated score (if a
   scoreboard was visible), notable moments, a confidence level, and caveats about what could not
   be determined reliably.
4. If the video is not a table tennis match, or could not be analyzed, the app says so plainly
   instead of fabricating statistics.
5. This report is independent of the app's own scored matches — it does not appear in match
   history and does not affect any match's saved statistics.
6. If the report was successfully generated, a summary of it is also added to the knowledge index
   in the background, so it can be referenced later (e.g., alongside completed-match summaries).

## Functional Requirements

### Match Setup

- **REQ-001**: The user must be able to create a new match by entering a name for each of the two players.
  - **Acceptance Criteria**: A new match cannot proceed to scoring unless both player name fields are
    filled in with non-empty, distinct names.

- **REQ-002**: The user must be able to choose the points needed to win a single game (e.g., 11 or 21).
  - **Acceptance Criteria**: The selected points-to-win value is used for all game-win detection in that
    match; changing it takes effect only for a new match, not one already in progress.

- **REQ-003**: The user must be able to choose the match format as best-of-N games (e.g., best of 1, 3, or
  5).
  - **Acceptance Criteria**: The match ends as soon as one player has won enough games to make the
    remaining games mathematically irrelevant (e.g., 2 games in a best-of-3).

- **REQ-004**: The app must prevent starting a match with incomplete or invalid setup (missing player name,
  no format selected).
  - **Acceptance Criteria**: The "Start Match" action is unavailable, or produces a clear message, until
    setup is complete.

### Live Scoring

- **REQ-005**: The user must be able to record which player won the current point with a single action.
  - **Acceptance Criteria**: After the action, the selected player's point total for the current game
    increases by exactly one, and the point is added to the match's point-by-point record.

- **REQ-006**: The app must display the current running score of the game in progress at all times during
  scoring.
  - **Acceptance Criteria**: The displayed score updates immediately after each point is recorded and
    matches the underlying point record.

- **REQ-007**: The app must correctly detect when a game is won, including deuce situations (a player must
  win by at least 2 points once both players reach points-to-win minus 1).
  - **Acceptance Criteria**: A game is marked won only when a player reaches the points-to-win threshold
    with at least a 2-point lead; scores continue past the threshold when tied at (points-to-win − 1) each.

- **REQ-008**: The app must automatically start the next game after a completed game, carrying forward the
  games-won tally for each player, unless the match is already decided.
  - **Acceptance Criteria**: After a game ends, the score resets to 0–0 for the new game while the
    games-won count for each player is preserved and visible.

- **REQ-009**: The app must correctly detect when the match is won, based on the selected best-of-N format.
  - **Acceptance Criteria**: The match ends as soon as a player's games-won count reaches the number
    required to win the match, and no further points can be recorded afterward.

- **REQ-010**: The user must be able to undo the most recently recorded point.
  - **Acceptance Criteria**: Undo reverts the score, serve indicator, and any tag associated with that
    point to their state immediately before that point was recorded; only the single most recent point is
    affected.

- **REQ-011**: The user must be able to optionally tag a recorded point with an outcome type (e.g., ace,
  unforced error, winner shot).
  - **Acceptance Criteria**: Tagging is optional per point; points recorded without a tag are still counted
    correctly toward the score and all statistics that do not depend on tags.

- **REQ-012**: The app must track and display which player is due to serve next, rotating serve every 2
  points (every 1 point once both players reach points-to-win − 1, i.e., deuce).
  - **Acceptance Criteria**: The serve indicator changes to the other player after every 2 recorded points
    during normal play, and after every 1 recorded point once the game is in deuce.

### Statistics Generation

- **REQ-013**: The app must generate a final score summary for the match, showing games won by each player
  and the point score of each individual game.
  - **Acceptance Criteria**: The summary lists every game played in order, with the final point score of
    each, and the overall games-won tally per player.

- **REQ-014**: The app must calculate the total points won by each player across the entire match.
  - **Acceptance Criteria**: The displayed total for each player equals the sum of that player's points
    across all games played in the match.

- **REQ-015**: The app must calculate, for each player, the percentage of points won while serving, when
  serve information is available.
  - **Acceptance Criteria**: The percentage equals (points won on own serve) ÷ (total points served) × 100,
    rounded to a whole number; the statistic is omitted or marked unavailable if serve tracking data is
    incomplete.

- **REQ-016**: The app must identify the longest consecutive-point winning streak achieved by each player
  during the match.
  - **Acceptance Criteria**: The reported streak length equals the longest unbroken run of consecutive
    points won by that player across the full match's point record.

- **REQ-017**: The app must total the tagged outcome counts (e.g., aces, unforced errors, winners) per
  player, for any match where tagging was used.
  - **Acceptance Criteria**: Each displayed tag count equals the number of points in the match record
    tagged with that outcome type for that player; players with no tagged points show a count of zero.

- **REQ-018**: The app must identify the closest game (smallest final point margin) and the most one-sided
  game (largest final point margin) of the match.
  - **Acceptance Criteria**: The identified games' point margins are less than or equal to, and greater
    than or equal to, respectively, the margins of every other game in the match.

### Match History & Local Persistence

- **REQ-019**: The app must save a completed match's full record (players, format, all points, tags,
  timestamp) locally on the device once the match ends.
  - **Acceptance Criteria**: After the match-completion flow finishes, the match appears in local match
    history without requiring any further user action.

- **REQ-020**: The app must display a list of previously saved matches in reverse-chronological order
  (most recent first).
  - **Acceptance Criteria**: Each list entry shows at least the match date, player names, and final score;
    order matches the saved timestamps from newest to oldest.

- **REQ-021**: The user must be able to select a past match from history and view its full statistics
  summary again.
  - **Acceptance Criteria**: The reopened summary matches exactly what was generated and shown when the
    match originally completed.

- **REQ-022**: The user must be able to delete a saved match from local history.
  - **Acceptance Criteria**: After deletion, the match no longer appears in the history list or in any
    future statistics views, and the action cannot be undone.

### Match Control

- **REQ-023**: The user must be able to abandon an in-progress match without it being saved to history.
  - **Acceptance Criteria**: After abandoning, no record of that match's points or partial score appears
    anywhere in local history.

- **REQ-024**: The user must be able to reset an in-progress match back to 0–0 with the same two players
  and format.
  - **Acceptance Criteria**: After reset, all previously recorded points for that match are cleared, the
    score returns to 0–0, and the same player names and format remain selected.

### AI Video Analysis (Post-MVP addendum)

- **REQ-025**: The user must be able to submit a video URL (YouTube supported) and receive an
  AI-generated best-effort estimate of that match's statistics.
  - **Acceptance Criteria**: Submitting a valid `http(s)` video URL returns a summary, an estimated
    final score when determinable, notable moments, a confidence level, and caveats explaining what
    could not be determined reliably.
- **REQ-026**: The app must clearly indicate when a video cannot be meaningfully analyzed as a table
  tennis match, rather than fabricating statistics for it.
  - **Acceptance Criteria**: For a video that is not a table tennis match, or that could not be
    watched/analyzed, the response marks it as not analyzable with an explanatory summary, no
    estimated score, and no fabricated player stats.
- **REQ-027**: Video analysis must be fully independent of the app's own scored matches — it must not
  read, write, or otherwise affect match/point data, match history, or the scoring engine.
  - **Acceptance Criteria**: Analyzing any number of videos never creates, modifies, or deletes any
    row in match/game/point storage, and never appears in match history.
- **REQ-028**: Video analysis must fail safely and clearly when its AI provider is not configured,
  rather than crashing or silently doing nothing.
  - **Acceptance Criteria**: With no provider credential configured, submitting a video URL returns a
    clear "not configured" error instead of a server error or a fabricated response.
- **REQ-029**: When a submitted video is successfully analyzed, a summary of that analysis must be
  added to the knowledge index (RAG) for future reference, on a best-effort basis.
  - **Acceptance Criteria**: After a video is analyzed and found to be analyzable, a text summary of
    the report (summary, players, estimated score, notable moments, confidence, caveats) is submitted
    for indexing; indexing failures (including no indexing provider configured) never cause the video
    analysis response to fail or be delayed beyond the indexing call itself. A video that could not be
    analyzed does not add anything to the index.

## Out of Scope for MVP

- User accounts, login, or any authentication/authorization.
- Cloud sync, multi-device access, or network-based multiplayer scoring.
- Video, camera, or sensor-based automatic point/shot detection **as a scoring input** — see note below.
- Shot-by-shot spatial analytics (ball placement, spin, speed).
- Tournament brackets, league standings, or multi-match scheduling.
- Data export/import, backups, or sharing to external services.
- Any hardening for concurrent users, large data volumes, or production-level reliability.

> **Note on REQ-025–029**: these were added post-MVP, at the project owner's explicit request, as a
> standalone AI-generated video *report* feature. This does not contradict the "no automatic
> point/shot detection" exclusion above: the AI's output is a separate, clearly-labeled estimate
> shown on its own page, never fed into the scoring engine, match history, or any match's saved
> statistics as ground truth. REQ-029's indexing is likewise separate from match/point storage — it
> only adds a document to the knowledge index used for reference, the same OpenRAG index that
> completed matches are already (best-effort) added to.
