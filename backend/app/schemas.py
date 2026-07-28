from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

PlayerSlot = Literal["player_one", "player_two"]
Tag = Literal["ace", "unforced_error", "winner"]
MatchStatus = Literal["in_progress", "completed", "abandoned"]


class CreateMatchRequest(BaseModel):
    player_one_name: str = Field(min_length=1)
    player_two_name: str = Field(min_length=1)
    points_to_win: Literal[11, 21]
    best_of: Literal[1, 3, 5]

    @model_validator(mode="after")
    def _validate_names(self):
        one = self.player_one_name.strip()
        two = self.player_two_name.strip()
        if not one or not two:
            raise ValueError("player_one_name and player_two_name must not be blank")
        if one == two:
            raise ValueError("player_one_name and player_two_name must be distinct")
        self.player_one_name = one
        self.player_two_name = two
        return self


class PointRequest(BaseModel):
    winner: PlayerSlot
    tag: Optional[Tag] = None


class Player(BaseModel):
    id: int
    display_name: str


class Score(BaseModel):
    player_one: int
    player_two: int


class Match(BaseModel):
    id: int
    player_one: Player
    player_two: Player
    points_to_win: int
    best_of: int
    games_to_win: int
    status: MatchStatus
    current_game_number: int
    current_score: Score
    games_won: Score
    serving_player: Optional[PlayerSlot]
    winner: Optional[PlayerSlot]
    created_at: str
    completed_at: Optional[str]


class MatchListItem(BaseModel):
    id: int
    player_one: Player
    player_two: Player
    status: MatchStatus
    games_won: Score
    winner: Optional[PlayerSlot]
    created_at: str
    completed_at: Optional[str]


class MatchListResponse(BaseModel):
    matches: list[MatchListItem]


class GameStat(BaseModel):
    game_number: int
    player_one_score: int
    player_two_score: int
    winner: PlayerSlot
    point_margin: int


class TagCounts(BaseModel):
    ace: int
    unforced_error: int
    winner: int


class PlayerStatTotals(BaseModel):
    points_won: int
    serve_points_won_percentage: Optional[float]
    longest_streak: int
    tag_counts: TagCounts


class MatchSummaryTotals(BaseModel):
    player_one: PlayerStatTotals
    player_two: PlayerStatTotals


class MatchSummary(BaseModel):
    match_id: int
    player_one: Player
    player_two: Player
    status: MatchStatus
    winner: Optional[PlayerSlot]
    games_won: Score
    games: list[GameStat]
    totals: MatchSummaryTotals
    closest_game: Optional[GameStat]
    largest_margin_game: Optional[GameStat]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
