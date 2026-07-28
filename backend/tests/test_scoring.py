import pytest

from app.scoring import (
    best_of_from_games_to_win,
    game_winner,
    games_to_win_from_best_of,
    match_winner,
    other_player,
    server_for_next_point,
    starting_server_for_game,
)


# --- games_to_win_from_best_of -------------------------------------------------

@pytest.mark.parametrize(
    "best_of,expected",
    [(1, 1), (3, 2), (5, 3)],
)
def test_games_to_win_from_best_of(best_of, expected):
    assert games_to_win_from_best_of(best_of) == expected


@pytest.mark.parametrize(
    "best_of",
    [1, 3, 5],
)
def test_best_of_from_games_to_win_round_trips(best_of):
    assert best_of_from_games_to_win(games_to_win_from_best_of(best_of)) == best_of


# --- game_winner (REQ-007) ------------------------------------------------------

def test_game_not_yet_won_below_threshold():
    assert game_winner(10, 9, points_to_win=11) is None


def test_game_won_outright():
    assert game_winner(11, 5, points_to_win=11) == "player_one"
    assert game_winner(3, 11, points_to_win=11) == "player_two"


def test_game_tied_at_deuce_threshold_not_won():
    assert game_winner(10, 10, points_to_win=11) is None


def test_game_one_point_lead_at_deuce_not_won():
    assert game_winner(11, 10, points_to_win=11) is None
    assert game_winner(10, 11, points_to_win=11) is None


def test_game_won_in_deuce_with_two_point_lead():
    assert game_winner(13, 11, points_to_win=11) == "player_one"
    assert game_winner(11, 13, points_to_win=11) == "player_two"


def test_game_won_reaching_threshold_with_big_lead():
    assert game_winner(11, 0, points_to_win=11) == "player_one"


def test_game_winner_with_21_point_format():
    assert game_winner(21, 19, points_to_win=21) == "player_one"
    assert game_winner(20, 19, points_to_win=21) is None
    assert game_winner(20, 20, points_to_win=21) is None
    assert game_winner(22, 20, points_to_win=21) == "player_one"


# --- match_winner (REQ-009) ------------------------------------------------------

def test_match_not_yet_won():
    assert match_winner(1, 1, games_to_win=2) is None


def test_match_won_best_of_3():
    assert match_winner(2, 0, games_to_win=2) == "player_one"
    assert match_winner(2, 1, games_to_win=2) == "player_one"
    assert match_winner(1, 2, games_to_win=2) == "player_two"


def test_match_won_best_of_5():
    assert match_winner(3, 1, games_to_win=3) == "player_one"
    assert match_winner(2, 2, games_to_win=3) is None


# --- other_player / starting_server_for_game -------------------------------------

def test_other_player():
    assert other_player("player_one") == "player_two"
    assert other_player("player_two") == "player_one"


def test_starting_server_alternates_by_game_number():
    assert starting_server_for_game(1) == "player_one"
    assert starting_server_for_game(2) == "player_two"
    assert starting_server_for_game(3) == "player_one"
    assert starting_server_for_game(4) == "player_two"


# --- server_for_next_point (REQ-012) ----------------------------------------------

def test_serve_rotates_every_two_points_in_normal_play():
    # Game 1 (player_one starts). Expected server for each point 1..10:
    # points 1,2 -> player_one; 3,4 -> player_two; 5,6 -> player_one; 7,8 -> player_two; 9,10 -> player_one
    expected = {
        (0, 0): "player_one",  # before point 1
        (1, 0): "player_one",  # before point 2
        (2, 0): "player_two",  # before point 3
        (1, 2): "player_two",  # before point 4 (order of who scored doesn't matter, only total)
        (2, 2): "player_one",  # before point 5
        (3, 2): "player_one",  # before point 6
        (3, 3): "player_two",  # before point 7
        (4, 3): "player_two",  # before point 8
        (4, 4): "player_one",  # before point 9
        (5, 4): "player_one",  # before point 10
    }
    for (p1, p2), server in expected.items():
        assert server_for_next_point(1, p1, p2, points_to_win=11) == server, (p1, p2)


def test_serve_rotates_every_point_once_in_deuce():
    # 11-point game, threshold = 10. At 10-10 (total 20) it's the deuce boundary.
    assert server_for_next_point(1, 10, 10, points_to_win=11) == "player_one"  # point 21
    assert server_for_next_point(1, 11, 10, points_to_win=11) == "player_two"  # point 22
    assert server_for_next_point(1, 10, 11, points_to_win=11) == "player_two"  # point 22 (other order)
    assert server_for_next_point(1, 11, 11, points_to_win=11) == "player_one"  # point 23
    assert server_for_next_point(1, 12, 11, points_to_win=11) == "player_two"  # point 24


def test_serve_boundary_transition_from_every_two_to_every_one():
    # Points 19 and 20 (total 18 and 19) are still a same-server pair (every-2 rule)
    # before the deuce boundary at total=20.
    server_18 = server_for_next_point(1, 9, 9, points_to_win=11)  # before point 19, total=18
    server_19 = server_for_next_point(1, 10, 9, points_to_win=11)  # before point 20, total=19
    assert server_18 == server_19  # same pair
    server_20 = server_for_next_point(1, 10, 10, points_to_win=11)  # before point 21, total=20 (deuce starts)
    assert server_20 != server_18  # rotates into deuce


def test_serve_starting_server_differs_by_game():
    # Same score state (0-0), different games -> different starting server.
    assert server_for_next_point(1, 0, 0, points_to_win=11) == "player_one"
    assert server_for_next_point(2, 0, 0, points_to_win=11) == "player_two"


def test_serve_rotation_with_21_point_format():
    threshold = 20
    # Normal phase: every 2 points.
    assert server_for_next_point(1, 0, 0, points_to_win=21) == "player_one"
    assert server_for_next_point(1, 1, 0, points_to_win=21) == "player_one"
    assert server_for_next_point(1, 2, 0, points_to_win=21) == "player_two"
    # Deuce boundary at 20-20 (total 40).
    assert server_for_next_point(1, 20, 20, points_to_win=21) == "player_one"
    assert server_for_next_point(1, 21, 20, points_to_win=21) == "player_two"
