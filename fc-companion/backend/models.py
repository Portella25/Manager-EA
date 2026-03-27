from __future__ import annotations

"""Modelos Pydantic usados para validar estado do jogo e eventos internos."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MetaDate(BaseModel):
    day: Optional[int] = None
    month: Optional[int] = None
    year: Optional[int] = None


class Meta(BaseModel):
    timestamp: int
    save_uid: Optional[str] = None
    export_version: Optional[str] = None
    game_date: Optional[MetaDate] = None
    season: Optional[int] = None
    is_in_career_mode: bool = False
    career_type: Optional[str] = None
    source: Optional[str] = None


class Manager(BaseModel):
    manager_name: Optional[str] = None
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    season: Optional[int] = None
    current_date: Optional[MetaDate] = None
    reputation: Optional[int] = None
    career_type: Optional[str] = None
    pap_player_id: Optional[int] = None
    national_team_id: Optional[int] = None


class Club(BaseModel):
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    transfer_budget: Optional[float] = None
    wage_budget: Optional[float] = None
    clubworth: Optional[float] = None
    popularity: Optional[int] = None
    domestic_prestige: Optional[int] = None
    international_prestige: Optional[int] = None


class Player(BaseModel):
    playerid: int
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    commonname: Optional[str] = None
    player_name: Optional[str] = None
    overall: Optional[int] = None
    potential: Optional[int] = None
    age: Optional[int] = None
    birthdate: Optional[str] = None
    nationality: Optional[int] = None
    position: Optional[int] = None
    morale: Optional[int] = None
    form: Optional[int] = None
    sharpness: Optional[int] = None
    fitness: Optional[int] = None
    contract_valid_until: Optional[str] = None
    is_injured: Optional[bool] = None
    value: Optional[float] = None
    wage: Optional[float] = None
    jersey_number: Optional[int] = None
    playstyle: List[Optional[int]] = Field(default_factory=list)


class Fixture(BaseModel):
    id: int
    competition_id: Optional[int] = None
    competition_name: Optional[str] = None
    home_team_id: Optional[int] = None
    home_team_name: Optional[str] = None
    away_team_id: Optional[int] = None
    away_team_name: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_penalties: Optional[int] = None
    away_penalties: Optional[int] = None
    is_completed: bool = False
    date_raw: Optional[int] = None
    time_raw: Optional[int] = None


class PartialStats(BaseModel):
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0


class TotalStats(PartialStats):
    points: int = 0


class Standing(BaseModel):
    team_id: int
    team_name: Optional[str] = None
    competition_id: Optional[int] = None
    home: PartialStats = Field(default_factory=PartialStats)
    away: PartialStats = Field(default_factory=PartialStats)
    total: TotalStats = Field(default_factory=TotalStats)


class Injury(BaseModel):
    playerid: int
    player_name: Optional[str] = None
    injury_type: Optional[str] = None
    games_remaining: Optional[int] = None
    severity: Optional[Literal["leve", "moderada", "grave"]] = None

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {"leve", "moderada", "grave"}
        if value not in allowed:
            raise ValueError("severity deve ser: leve, moderada ou grave")
        return value


class TransferOffer(BaseModel):
    playerid: int
    player_name: Optional[str] = None
    from_team_id: Optional[int] = None
    from_team_name: Optional[str] = None
    offer_amount: Optional[float] = None
    offer_type: Optional[str] = None
    status: Optional[str] = None


class CareerEvent(BaseModel):
    event_id: Optional[int] = None
    event_name: Optional[str] = None
    timestamp: Optional[int] = None


class TransferHistory(BaseModel):
    playerid: int
    player_name: str
    from_team_id: int
    from_team_name: str
    to_team_id: int
    to_team_name: str
    fee: Optional[float] = None


class GameEvent(BaseModel):
    event_type: str
    payload: Dict[str, Any]
    timestamp: datetime
    save_uid: Optional[str] = None
    severity: Optional[int] = 3  # Adicionado para o Motor Híbrido

class GameState(BaseModel):
    # Permite ler state.json mesmo se o Lua adicionar campos extras no futuro.
    model_config = ConfigDict(extra="ignore")

    meta: Meta
    manager: Optional[Manager] = None
    club: Optional[Club] = None
    squad: List[Player] = Field(default_factory=list)
    fixtures: List[Fixture] = Field(default_factory=list)
    standings: List[Standing] = Field(default_factory=list)
    injuries: List[Injury] = Field(default_factory=list)
    transfer_offers: List[TransferOffer] = Field(default_factory=list)
    transfer_history: List[TransferHistory] = Field(default_factory=list)
    events: List[CareerEvent] = Field(default_factory=list)


class InternalEventIn(BaseModel):
    event_type: str
    payload: Dict[str, Any]
    timestamp: datetime
    save_uid: Optional[str] = None
    severity: Optional[int] = 3

class NarrativeRecord(BaseModel):
    id: int
    event_type: str
    title: str
    content: str
    tone: str
    source: str
    created_at: datetime
    save_uid: Optional[str] = None


class NarrativeIn(BaseModel):
    event_type: str
    payload: Dict[str, Any]
    save_uid: Optional[str] = None


class NarrativeOut(BaseModel):
    title: str
    content: str
    tone: str
    source: str


class FeedItemRecord(BaseModel):
    id: int
    event_type: str
    channel: str
    title: str
    content: str
    tone: str
    source: str
    created_at: datetime
    save_uid: Optional[str] = None


class CoachProfileRecord(BaseModel):
    save_uid: str
    reputation_score: int
    reputation_label: str
    playstyle_label: str
    fan_sentiment_score: int
    fan_sentiment_label: str
    updated_at: datetime


class PressConferenceIn(BaseModel):
    question: str
    answer: str
    save_uid: Optional[str] = None


class PressConferenceOut(BaseModel):
    id: int
    detected_tone: str
    reputation_delta: int
    morale_delta: int
    headline: str
    board_reaction: str
    locker_room_reaction: str
    fan_reaction: str
    created_at: datetime


class MarketRumorIn(BaseModel):
    trigger_event: str
    payload: Dict[str, Any]
    save_uid: Optional[str] = None


class MarketRumorRecord(BaseModel):
    id: int
    trigger_event: str
    headline: str
    content: str
    confidence_level: int
    target_profile: str
    created_at: datetime
    save_uid: Optional[str] = None


class TimelineEntryIn(BaseModel):
    source_event: str
    payload: Dict[str, Any]
    save_uid: Optional[str] = None


class TimelineEntryRecord(BaseModel):
    id: int
    save_uid: Optional[str] = None
    source_event: str
    phase: str
    title: str
    content: str
    importance: int
    created_at: datetime


class CrisisTriggerIn(BaseModel):
    save_uid: str
    reason: str
    severity: Optional[str] = "moderada"


class CrisisArcRecord(BaseModel):
    id: int
    save_uid: str
    trigger_type: str
    status: str
    severity: str
    summary: str
    current_step: int
    max_steps: int
    started_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None


class SeasonArcTriggerIn(BaseModel):
    save_uid: str
    title: str
    theme: str
    season_label: Optional[str] = None


class SeasonArcMemoryIn(BaseModel):
    save_uid: str
    memory_text: str
    source_event: Optional[str] = None


class SeasonArcRecord(BaseModel):
    id: int
    save_uid: str
    title: str
    theme: str
    season_label: str
    status: str
    current_milestone: int
    max_milestones: int
    memories: List[Dict[str, Any]]
    started_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None


class SeasonPayoffIn(BaseModel):
    save_uid: str
    summary_hint: Optional[str] = None


class SeasonPayoffRecord(BaseModel):
    id: int
    save_uid: str
    season_arc_id: int
    final_score: int
    grade: str
    title: str
    epilogue: str
    factors: Dict[str, Any]
    created_at: datetime


class HallOfFameEntryRecord(BaseModel):
    id: int
    save_uid: str
    category: str
    title: str
    description: str
    score_impact: int
    source: str
    created_at: datetime


class HallOfFameProfileRecord(BaseModel):
    save_uid: str
    total_entries: int
    legacy_score: float
    tier: str
    highlight_title: Optional[str] = None
    updated_at: datetime


class AchievementRecord(BaseModel):
    id: int
    save_uid: str
    code: str
    title: str
    description: str
    rarity: str
    points: int
    source: str
    created_at: datetime


class AchievementProfileRecord(BaseModel):
    save_uid: str
    total_achievements: int
    total_points: int
    career_level: str
    top_achievement: Optional[str] = None
    updated_at: datetime


class MetaAchievementRecord(BaseModel):
    id: int
    save_uid: str
    code: str
    title: str
    description: str
    collection_tag: str
    points: int
    created_at: datetime


class MetaAchievementProfileRecord(BaseModel):
    save_uid: str
    total_meta: int
    collection_progress: Dict[str, Any]
    prestige_level: str
    updated_at: datetime


class CareerManagementStateOut(BaseModel):
    save_uid: str
    locker_room: Dict[str, Any]
    finance: Dict[str, Any]
    tactical: Dict[str, Any]
    academy: Dict[str, Any]
    medical: Dict[str, Any]
    updated_at: datetime


class PlayerRelationOut(BaseModel):
    id: int
    save_uid: str
    playerid: int
    player_name: Optional[str] = None
    trust: int
    role_label: str
    status_label: str
    frustration: int
    notes: Dict[str, Any]
    updated_at: datetime


class FinanceLedgerRecord(BaseModel):
    id: int
    save_uid: str
    period: str
    kind: str
    amount: float
    description: str
    created_at: datetime


class CareerManagementPatchIn(BaseModel):
    save_uid: str
    locker_room: Optional[Dict[str, Any]] = None
    finance: Optional[Dict[str, Any]] = None
    tactical: Optional[Dict[str, Any]] = None
    academy: Optional[Dict[str, Any]] = None
    medical: Optional[Dict[str, Any]] = None


class PlayerRelationPatchIn(BaseModel):
    save_uid: str
    playerid: int
    player_name: Optional[str] = None
    trust: Optional[int] = None
    role_label: Optional[str] = None
    status_label: Optional[str] = None
    frustration: Optional[int] = None
    notes: Optional[Dict[str, Any]] = None
