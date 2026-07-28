def create_match(client, player_one_name="Alice", player_two_name="Bob", points_to_win=11, best_of=3):
    resp = client.post(
        "/matches",
        json={
            "player_one_name": player_one_name,
            "player_two_name": player_two_name,
            "points_to_win": points_to_win,
            "best_of": best_of,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def play_point(client, match_id, winner, tag=None):
    body = {"winner": winner}
    if tag is not None:
        body["tag"] = tag
    return client.post(f"/matches/{match_id}/points", json=body)


# --- Match setup: REQ-001, REQ-002, REQ-003, REQ-004 -----------------------------

def test_create_match_success(client):
    match = create_match(client)
    assert match["status"] == "in_progress"
    assert match["current_game_number"] == 1
    assert match["current_score"] == {"player_one": 0, "player_two": 0}
    assert match["games_won"] == {"player_one": 0, "player_two": 0}
    assert match["serving_player"] == "player_one"
    assert match["winner"] is None
    assert match["points_to_win"] == 11
    assert match["best_of"] == 3
    assert match["games_to_win"] == 2
    assert match["player_one"]["display_name"] == "Alice"
    assert match["player_two"]["display_name"] == "Bob"


def test_create_match_duplicate_names_rejected(client):
    resp = client.post(
        "/matches",
        json={
            "player_one_name": "Alice",
            "player_two_name": "Alice",
            "points_to_win": 11,
            "best_of": 3,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_create_match_blank_name_rejected(client):
    resp = client.post(
        "/matches",
        json={
            "player_one_name": "   ",
            "player_two_name": "Bob",
            "points_to_win": 11,
            "best_of": 3,
        },
    )
    assert resp.status_code == 422


def test_create_match_invalid_points_to_win_rejected(client):
    resp = client.post(
        "/matches",
        json={
            "player_one_name": "Alice",
            "player_two_name": "Bob",
            "points_to_win": 15,
            "best_of": 3,
        },
    )
    assert resp.status_code == 422


def test_create_match_invalid_best_of_rejected(client):
    resp = client.post(
        "/matches",
        json={
            "player_one_name": "Alice",
            "player_two_name": "Bob",
            "points_to_win": 11,
            "best_of": 2,
        },
    )
    assert resp.status_code == 422


def test_get_match_not_found(client):
    resp = client.get("/matches/999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


# --- Live scoring: REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-011, REQ-012 --

def test_record_point_updates_score(client):
    match = create_match(client)
    resp = play_point(client, match["id"], "player_one")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_score"] == {"player_one": 1, "player_two": 0}


def test_serve_rotates_every_two_points(client):
    match = create_match(client, points_to_win=11, best_of=3)
    match_id = match["id"]
    assert client.get(f"/matches/{match_id}").json()["serving_player"] == "player_one"
    play_point(client, match_id, "player_two")
    assert client.get(f"/matches/{match_id}").json()["serving_player"] == "player_one"
    play_point(client, match_id, "player_two")
    assert client.get(f"/matches/{match_id}").json()["serving_player"] == "player_two"


def test_optional_tag_on_point(client):
    match = create_match(client)
    resp = play_point(client, match["id"], "player_one", tag="ace")
    assert resp.status_code == 200
    assert resp.json()["current_score"]["player_one"] == 1


def test_invalid_winner_value_rejected(client):
    match = create_match(client)
    resp = client.post(f"/matches/{match['id']}/points", json={"winner": "nobody"})
    assert resp.status_code == 422


def test_game_win_advances_to_next_game_preserving_games_won(client):
    match = create_match(client, points_to_win=11, best_of=3)
    match_id = match["id"]
    for _ in range(11):
        resp = play_point(client, match_id, "player_one")
    body = resp.json()
    assert body["status"] == "in_progress"  # best_of=3 needs 2 games
    assert body["games_won"] == {"player_one": 1, "player_two": 0}
    assert body["current_game_number"] == 2
    assert body["current_score"] == {"player_one": 0, "player_two": 0}


def test_match_win_best_of_one(client):
    match = create_match(client, points_to_win=11, best_of=1)
    match_id = match["id"]
    for _ in range(11):
        resp = play_point(client, match_id, "player_one")
    body = resp.json()
    assert body["status"] == "completed"
    assert body["winner"] == "player_one"
    assert body["games_won"] == {"player_one": 1, "player_two": 0}
    assert body["serving_player"] is None


def test_deuce_win_requires_two_point_lead(client):
    match = create_match(client, points_to_win=11, best_of=1)
    match_id = match["id"]
    for _ in range(10):
        play_point(client, match_id, "player_one")
    for _ in range(10):
        play_point(client, match_id, "player_two")
    # 10-10, deuce. A single point lead should not end the game.
    resp = play_point(client, match_id, "player_one")
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["current_score"] == {"player_one": 11, "player_two": 10}
    # Second point in a row for the same player wins it (two-point lead).
    resp = play_point(client, match_id, "player_one")
    body = resp.json()
    assert body["status"] == "completed"
    assert body["winner"] == "player_one"
    assert body["current_score"] == {"player_one": 12, "player_two": 10}


def test_point_recording_rejected_after_match_completed(client):
    match = create_match(client, points_to_win=11, best_of=1)
    match_id = match["id"]
    for _ in range(11):
        resp = play_point(client, match_id, "player_one")
    resp = play_point(client, match_id, "player_two")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


# --- Undo: REQ-010 ---------------------------------------------------------------

def test_undo_reverts_score_and_serve(client):
    match = create_match(client)
    match_id = match["id"]
    play_point(client, match_id, "player_two")
    play_point(client, match_id, "player_two")  # serve now player_two's turn
    before_undo = client.get(f"/matches/{match_id}").json()
    assert before_undo["current_score"] == {"player_one": 0, "player_two": 2}
    assert before_undo["serving_player"] == "player_two"

    resp = client.delete(f"/matches/{match_id}/points/last")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_score"] == {"player_one": 0, "player_two": 1}
    assert body["serving_player"] == "player_one"


def test_undo_with_no_points_conflicts(client):
    match = create_match(client)
    resp = client.delete(f"/matches/{match['id']}/points/last")
    assert resp.status_code == 409


def test_undo_not_found(client):
    resp = client.delete("/matches/999/points/last")
    assert resp.status_code == 404


def test_undo_reopens_completed_game_and_match(client):
    match = create_match(client, points_to_win=11, best_of=1)
    match_id = match["id"]
    for _ in range(11):
        play_point(client, match_id, "player_one")
    completed = client.get(f"/matches/{match_id}").json()
    assert completed["status"] == "completed"

    resp = client.delete(f"/matches/{match_id}/points/last")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["winner"] is None
    assert body["current_score"] == {"player_one": 10, "player_two": 0}
    assert body["current_game_number"] == 1
    assert body["serving_player"] is not None


def test_undo_reopens_completed_game_across_game_boundary(client):
    match = create_match(client, points_to_win=11, best_of=3)
    match_id = match["id"]
    for _ in range(11):
        play_point(client, match_id, "player_one")
    mid = client.get(f"/matches/{match_id}").json()
    assert mid["current_game_number"] == 2  # auto-advanced, best_of=3 not decided yet

    resp = client.delete(f"/matches/{match_id}/points/last")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_game_number"] == 1
    assert body["current_score"] == {"player_one": 10, "player_two": 0}
    assert body["games_won"] == {"player_one": 0, "player_two": 0}


# --- Match control: REQ-023, REQ-024 ---------------------------------------------

def test_abandon_removes_match_entirely(client):
    match = create_match(client)
    match_id = match["id"]
    play_point(client, match_id, "player_one")
    resp = client.post(f"/matches/{match_id}/abandon")
    assert resp.status_code == 204
    assert client.get(f"/matches/{match_id}").status_code == 404
    assert client.get(f"/matches/{match_id}/summary").status_code == 404
    history = client.get("/matches").json()["matches"]
    assert all(m["id"] != match_id for m in history)


def test_abandon_conflict_when_already_completed(client):
    match = create_match(client, points_to_win=11, best_of=1)
    match_id = match["id"]
    for _ in range(11):
        play_point(client, match_id, "player_one")
    resp = client.post(f"/matches/{match_id}/abandon")
    assert resp.status_code == 409


def test_reset_clears_points_keeps_setup(client):
    match = create_match(client, points_to_win=11, best_of=3)
    match_id = match["id"]
    play_point(client, match_id, "player_one")
    play_point(client, match_id, "player_two")

    resp = client.post(f"/matches/{match_id}/reset")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_score"] == {"player_one": 0, "player_two": 0}
    assert body["current_game_number"] == 1
    assert body["status"] == "in_progress"
    assert body["player_one"]["display_name"] == "Alice"
    assert body["player_two"]["display_name"] == "Bob"
    assert body["points_to_win"] == 11
    assert body["best_of"] == 3


def test_reset_conflict_when_already_completed(client):
    match = create_match(client, points_to_win=11, best_of=1)
    match_id = match["id"]
    for _ in range(11):
        play_point(client, match_id, "player_one")
    resp = client.post(f"/matches/{match_id}/reset")
    assert resp.status_code == 409


# --- Statistics: REQ-013..018, REQ-021 -------------------------------------------

def test_match_summary_statistics(client):
    match = create_match(client, points_to_win=11, best_of=1)
    match_id = match["id"]

    # Winner sequence verified against the scoring engine to produce a
    # deterministic, independently-computed set of expected stats (see
    # session notes): final score 11-2, player_one serve% = 100 (7/7),
    # player_two serve% = 33 (2/6), longest streaks 6 / 1.
    winners = [
        "player_one", "player_one", "player_two", "player_one", "player_one",
        "player_one", "player_two", "player_one", "player_one", "player_one",
        "player_one", "player_one", "player_one",
    ]
    tags = {2: "unforced_error", 4: "ace", 7: "winner"}
    for i, w in enumerate(winners):
        resp = play_point(client, match_id, w, tag=tags.get(i))
    assert resp.json()["status"] == "completed"

    summary = client.get(f"/matches/{match_id}/summary").json()

    assert summary["status"] == "completed"
    assert summary["winner"] == "player_one"
    assert summary["games_won"] == {"player_one": 1, "player_two": 0}

    assert len(summary["games"]) == 1
    game = summary["games"][0]
    assert game == {
        "game_number": 1,
        "player_one_score": 11,
        "player_two_score": 2,
        "winner": "player_one",
        "point_margin": 9,
    }
    assert summary["closest_game"] == game
    assert summary["largest_margin_game"] == game

    p1_totals = summary["totals"]["player_one"]
    assert p1_totals["points_won"] == 11
    assert p1_totals["serve_points_won_percentage"] == 100
    assert p1_totals["longest_streak"] == 6
    assert p1_totals["tag_counts"] == {"ace": 1, "unforced_error": 0, "winner": 1}

    p2_totals = summary["totals"]["player_two"]
    assert p2_totals["points_won"] == 2
    assert p2_totals["serve_points_won_percentage"] == 33
    assert p2_totals["longest_streak"] == 1
    assert p2_totals["tag_counts"] == {"ace": 0, "unforced_error": 1, "winner": 0}


def test_summary_reopen_matches_original(client):
    """REQ-021: reopening a past match's summary matches what was generated originally."""
    match = create_match(client, points_to_win=11, best_of=1)
    match_id = match["id"]
    for _ in range(11):
        play_point(client, match_id, "player_one")

    first = client.get(f"/matches/{match_id}/summary").json()
    second = client.get(f"/matches/{match_id}/summary").json()
    assert first == second


def test_summary_not_found(client):
    resp = client.get("/matches/999/summary")
    assert resp.status_code == 404


# --- History: REQ-020, REQ-022 ----------------------------------------------------

def test_history_lists_completed_matches_reverse_chronological(client):
    m1 = create_match(client, "Alice", "Bob", points_to_win=11, best_of=1)
    for _ in range(11):
        play_point(client, m1["id"], "player_one")

    m2 = create_match(client, "Carol", "Dave", points_to_win=11, best_of=1)
    for _ in range(11):
        play_point(client, m2["id"], "player_two")

    # In-progress match should not appear in history.
    m3 = create_match(client, "Eve", "Frank", points_to_win=11, best_of=1)

    history = client.get("/matches").json()["matches"]
    ids = [m["id"] for m in history]
    assert m3["id"] not in ids
    assert ids.index(m2["id"]) < ids.index(m1["id"])  # most recent first


def test_delete_match_removes_from_history_and_summary(client):
    match = create_match(client, points_to_win=11, best_of=1)
    match_id = match["id"]
    for _ in range(11):
        play_point(client, match_id, "player_one")

    resp = client.delete(f"/matches/{match_id}")
    assert resp.status_code == 204
    assert client.get(f"/matches/{match_id}/summary").status_code == 404
    history = client.get("/matches").json()["matches"]
    assert all(m["id"] != match_id for m in history)


def test_delete_match_not_found(client):
    resp = client.delete("/matches/999")
    assert resp.status_code == 404
