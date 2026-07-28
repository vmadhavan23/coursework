"""Pure scoring rules for a single table tennis match. No I/O, no persistence —
unit-testable in isolation against plain integers/strings.

Design assumption (not specified by requirements.md, so documented here): the
starting server alternates by game number — player_one serves first in game 1,
player_two serves first in game 2, and so on — matching standard table tennis
convention of alternating who opens serve each game.
"""

from typing import Literal

PlayerSlot = Literal["player_one", "player_two"]


def other_player(player: PlayerSlot) -> PlayerSlot:
    return "player_two" if player == "player_one" else "player_one"


def games_to_win_from_best_of(best_of: int) -> int:
    """best_of 1 -> 1, best_of 3 -> 2, best_of 5 -> 3."""
    return best_of // 2 + 1


def best_of_from_games_to_win(games_to_win: int) -> int:
    """Inverse of games_to_win_from_best_of; the mapping is injective over
    the supported best_of values {1, 3, 5}, so this recovers the original."""
    return 2 * games_to_win - 1


def game_winner(
    player_one_score: int, player_two_score: int, points_to_win: int
) -> PlayerSlot | None:
    """REQ-007: deuce-aware game win detection. A player wins once they reach
    points_to_win with at least a 2-point lead; ties at (points_to_win - 1)
    each continue play (deuce)."""
    hi = max(player_one_score, player_two_score)
    lo = min(player_one_score, player_two_score)
    if hi >= points_to_win and hi - lo >= 2:
        return "player_one" if player_one_score > player_two_score else "player_two"
    return None


def match_winner(
    player_one_games: int, player_two_games: int, games_to_win: int
) -> PlayerSlot | None:
    """REQ-009: match win detection from the best-of-N format."""
    if player_one_games >= games_to_win:
        return "player_one"
    if player_two_games >= games_to_win:
        return "player_two"
    return None


def starting_server_for_game(game_number: int) -> PlayerSlot:
    return "player_one" if game_number % 2 == 1 else "player_two"


def server_for_next_point(
    game_number: int,
    prior_player_one_score: int,
    prior_player_two_score: int,
    points_to_win: int,
) -> PlayerSlot:
    """REQ-012: who serves the point about to be played, given the game's
    starting server and the scores immediately before this point.

    Serve rotates every 2 points in normal play, every 1 point once both
    players have reached (points_to_win - 1) each (deuce). Expressed as a
    single "service turn" counter so the two regimes join up continuously
    at the deuce boundary.
    """
    starting_server = starting_server_for_game(game_number)
    threshold = points_to_win - 1
    total_prior = prior_player_one_score + prior_player_two_score

    if total_prior <= 2 * threshold:
        turn = total_prior // 2
    else:
        turn = threshold + (total_prior - 2 * threshold)

    return starting_server if turn % 2 == 0 else other_player(starting_server)
