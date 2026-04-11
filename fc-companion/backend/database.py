from __future__ import annotations

"""Camada de persistência SQLite síncrona para eventos e snapshots do save."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine, desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "fc_companion.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"


class Base(DeclarativeBase):
    pass


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    save_uid: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MatchResultRecord(Base):
    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint(
            "save_uid",
            "date_raw",
            "competition_id",
            "home_team_id",
            "away_team_id",
            "my_score",
            "opp_score",
            name="uq_match_results_dedupe",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    date_raw: Mapped[str] = mapped_column(String(40), nullable=False, default="", index=True)
    competition_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    competition_name: Mapped[str] = mapped_column(String(140), nullable=False, default="")
    club_name: Mapped[str] = mapped_column(String(140), nullable=False, default="")
    opponent_name: Mapped[str] = mapped_column(String(140), nullable=False, default="")
    home_team_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    away_team_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    my_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opp_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goal_diff: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome: Mapped[str] = mapped_column(String(1), nullable=False, default="D", index=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class GameSnapshotRecord(Base):
    __tablename__ = "game_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    snapshot_date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    data: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class NarrativeRecord(Base):
    __tablename__ = "narratives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(String(40), nullable=False, default="neutral")
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="template")
    save_uid: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class FeedItemRecord(Base):
    __tablename__ = "feed_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(String(40), nullable=False, default="neutro")
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="template")
    save_uid: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class CoachProfileStateRecord(Base):
    __tablename__ = "coach_profile_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    reputation_score: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    reputation_label: Mapped[str] = mapped_column(String(40), nullable=False, default="estável")
    playstyle_label: Mapped[str] = mapped_column(String(40), nullable=False, default="equilibrado")
    fan_sentiment_score: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    fan_sentiment_label: Mapped[str] = mapped_column(String(40), nullable=False, default="neutro")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class PressConferenceRecord(Base):
    __tablename__ = "press_conferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    game_date: Mapped[Optional[str]] = mapped_column(String(12), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    detected_tone: Mapped[str] = mapped_column(String(30), nullable=False)
    reputation_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    morale_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    headline: Mapped[str] = mapped_column(String(220), nullable=False)
    board_reaction: Mapped[str] = mapped_column(Text, nullable=False)
    locker_room_reaction: Mapped[str] = mapped_column(Text, nullable=False)
    fan_reaction: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class BoardChallengeRecord(Base):
    __tablename__ = "board_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    challenge_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    required_points: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    current_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matches_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class MarketRumorRecord(Base):
    __tablename__ = "market_rumors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    trigger_event: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    headline: Mapped[str] = mapped_column(String(220), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_level: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    target_profile: Mapped[str] = mapped_column(String(80), nullable=False, default="equilibrado")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class EditorialTimelineRecord(Base):
    __tablename__ = "editorial_timeline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    source_event: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class CrisisArcStateRecord(Base):
    __tablename__ = "crisis_arcs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="moderada")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SeasonArcStateRecord(Base):
    __tablename__ = "season_arcs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    theme: Mapped[str] = mapped_column(String(120), nullable=False)
    season_label: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    current_milestone: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_milestones: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    memories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SeasonPayoffRecord(Base):
    __tablename__ = "season_payoffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    season_arc_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    final_score: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    epilogue: Mapped[str] = mapped_column(Text, nullable=False)
    factors_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class LegacyProfileRecord(Base):
    __tablename__ = "legacy_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    seasons_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    best_grade: Mapped[str] = mapped_column(String(10), nullable=False, default="-")
    legacy_rank: Mapped[str] = mapped_column(String(20), nullable=False, default="em_formacao")
    narrative_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class HallOfFameEntryRecord(Base):
    __tablename__ = "hall_of_fame_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    score_impact: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class HallOfFameProfileRecord(Base):
    __tablename__ = "hall_of_fame_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    total_entries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    legacy_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="aspirante")
    highlight_title: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class AchievementRecord(Base):
    __tablename__ = "career_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rarity: Mapped[str] = mapped_column(String(20), nullable=False, default="common")
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class AchievementProfileRecord(Base):
    __tablename__ = "achievement_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    total_achievements: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    career_level: Mapped[str] = mapped_column(String(20), nullable=False, default="iniciante")
    top_achievement: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class MetaAchievementRecord(Base):
    __tablename__ = "meta_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    collection_tag: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class MetaAchievementProfileRecord(Base):
    __tablename__ = "meta_achievement_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    total_meta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    collection_progress_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    prestige_level: Mapped[str] = mapped_column(String(20), nullable=False, default="bronze")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class CareerManagementStateRecord(Base):
    __tablename__ = "career_management_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    locker_room_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    finance_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    tactical_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    academy_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    medical_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class PlayerRelationRecord(Base):
    __tablename__ = "player_relations"
    __table_args__ = (UniqueConstraint("save_uid", "playerid", name="uq_player_relations_save_player"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    playerid: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    player_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    trust: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    role_label: Mapped[str] = mapped_column(String(20), nullable=False, default="rotacao")
    status_label: Mapped[str] = mapped_column(String(20), nullable=False, default="neutro")
    frustration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class FinanceLedgerRecord(Base):
    __tablename__ = "finance_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class ExternalArtifactRecord(Base):
    __tablename__ = "external_artifacts"
    __table_args__ = (UniqueConstraint("save_uid", "artifact_type", name="uq_external_artifacts_save_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class ExternalEventLogRecord(Base):
    __tablename__ = "external_event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    event_id_raw: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    event_name_raw: Mapped[Optional[str]] = mapped_column(String(140), nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    importance: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class CareerFactRecord(Base):
    __tablename__ = "career_facts"
    __table_args__ = (UniqueConstraint("save_uid", "game_date", "dedupe_group", name="uq_career_facts_save_date_group"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    game_date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    fact_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    dedupe_group: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    entities_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    signals_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    editorial_flags_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class NewsDailyPackageRecord(Base):
    __tablename__ = "news_daily_packages"
    __table_args__ = (UniqueConstraint("save_uid", "game_date", name="uq_news_daily_packages_save_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    game_date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    edition_label: Mapped[str] = mapped_column(String(120), nullable=False, default="Diário da Carreira")
    lead_angle: Mapped[str] = mapped_column(String(120), nullable=False, default="contexto diário")
    density_level: Mapped[str] = mapped_column(String(20), nullable=False, default="light")
    stories_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    layout_hints_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class NewsDailyArticleRecord(Base):
    __tablename__ = "news_daily_articles"
    __table_args__ = (UniqueConstraint("package_id", "slot", name="uq_news_daily_articles_package_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    save_uid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    game_date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    slot: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="news")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    impact: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    headline: Mapped[str] = mapped_column(String(220), nullable=False)
    subheadline: Mapped[str] = mapped_column(Text, nullable=False, default="")
    lead: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False, default="")
    club_effects_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    entities_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source_facts_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)


engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _migrate_press_conferences_game_date() -> None:
    """Add game_date column if missing (SQLite)."""
    import sqlite3 as _sqlite3
    db_path = str(DB_PATH)
    try:
        conn = _sqlite3.connect(db_path)
        cur = conn.execute("PRAGMA table_info(press_conferences)")
        cols = {row[1] for row in cur.fetchall()}
        if "game_date" not in cols:
            conn.execute("ALTER TABLE press_conferences ADD COLUMN game_date VARCHAR(12)")
            conn.commit()
        conn.close()
    except Exception:
        pass


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_press_conferences_game_date()


def _serialize_payload(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _deserialize_payload(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_payload": raw}


def _deserialize_json(raw: str, default: Any) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _parse_iso_datetime(raw: Optional[str]) -> datetime:
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.utcnow()


def save_event(event_type: str, payload: Dict[str, Any], save_uid: Optional[str]) -> int:
    with SessionLocal() as session:
        record = EventRecord(
            event_type=event_type,
            payload=_serialize_payload(payload),
            timestamp=datetime.utcnow(),
            save_uid=save_uid,
            processed=False,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id


def insert_event_with_timestamp(
    event_type: str,
    payload: Dict[str, Any],
    timestamp: datetime,
    save_uid: Optional[str],
) -> int:
    with SessionLocal() as session:
        record = EventRecord(
            event_type=event_type,
            payload=_serialize_payload(payload),
            timestamp=timestamp,
            save_uid=save_uid,
            processed=False,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id


def upsert_match_result_from_match_event(
    save_uid: str,
    payload: Dict[str, Any],
    occurred_at: datetime,
) -> Optional[int]:
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    if not save_uid:
        return None
    my_score = _to_int(payload.get("my_score"), 0)
    opp_score = _to_int(payload.get("opp_score"), 0)
    if my_score > opp_score:
        outcome = "W"
        points = 3
    elif my_score < opp_score:
        outcome = "L"
        points = 0
    else:
        outcome = "D"
        points = 1

    date_raw = str(payload.get("date") or "")
    competition_id = _to_int(payload.get("competition_id"), 0)
    home_team_id = _to_int(payload.get("home_team_id"), 0)
    away_team_id = _to_int(payload.get("away_team_id"), 0)
    competition_name = str(payload.get("competition") or payload.get("competition_name") or "")
    club_name = str(payload.get("club_name") or "")
    opponent_name = str(payload.get("opponent_team_name") or payload.get("opponent") or "")
    is_home = bool(payload.get("is_home")) if payload.get("is_home") is not None else True

    with SessionLocal() as session:
        row = MatchResultRecord(
            save_uid=str(save_uid),
            occurred_at=occurred_at,
            date_raw=date_raw,
            competition_id=int(competition_id),
            competition_name=competition_name,
            club_name=club_name,
            opponent_name=opponent_name,
            home_team_id=int(home_team_id),
            away_team_id=int(away_team_id),
            is_home=bool(is_home),
            my_score=int(my_score),
            opp_score=int(opp_score),
            goal_diff=int(my_score - opp_score),
            outcome=outcome,
            points=int(points),
            created_at=datetime.utcnow(),
        )
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = (
                session.execute(
                    select(MatchResultRecord)
                    .where(MatchResultRecord.save_uid == str(save_uid))
                    .where(MatchResultRecord.date_raw == date_raw)
                    .where(MatchResultRecord.competition_id == int(competition_id))
                    .where(MatchResultRecord.home_team_id == int(home_team_id))
                    .where(MatchResultRecord.away_team_id == int(away_team_id))
                    .where(MatchResultRecord.my_score == int(my_score))
                    .where(MatchResultRecord.opp_score == int(opp_score))
                    .limit(1)
                )
                .scalars()
                .first()
            )
            return int(existing.id) if existing else None
        session.refresh(row)
        return int(row.id)


def get_match_results(save_uid: str, limit: int = 5000) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        rows = (
            session.execute(
                select(MatchResultRecord)
                .where(MatchResultRecord.save_uid == save_uid)
                .order_by(MatchResultRecord.occurred_at)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "occurred_at": row.occurred_at.isoformat(),
                "date_raw": row.date_raw,
                "competition_id": row.competition_id,
                "competition_name": row.competition_name,
                "club_name": row.club_name,
                "opponent_name": row.opponent_name,
                "home_team_id": row.home_team_id,
                "away_team_id": row.away_team_id,
                "is_home": row.is_home,
                "my_score": row.my_score,
                "opp_score": row.opp_score,
                "goal_diff": row.goal_diff,
                "outcome": row.outcome,
                "points": row.points,
            }
            for row in rows
        ]


def get_recent_events(limit: int = 20, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(EventRecord).order_by(desc(EventRecord.timestamp)).limit(limit)
        if save_uid:
            stmt = stmt.where(EventRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "event_type": row.event_type,
                "payload": _deserialize_payload(row.payload),
                "timestamp": row.timestamp.isoformat(),
                "save_uid": row.save_uid,
                "processed": row.processed,
            }
            for row in rows
        ]


def get_events_by_type(event_type: str, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(EventRecord).where(EventRecord.event_type == event_type).order_by(desc(EventRecord.timestamp))
        if save_uid:
            stmt = stmt.where(EventRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "event_type": row.event_type,
                "payload": _deserialize_payload(row.payload),
                "timestamp": row.timestamp.isoformat(),
                "save_uid": row.save_uid,
                "processed": row.processed,
            }
            for row in rows
        ]


def save_snapshot(save_uid: str, game_date: str, data: Dict[str, Any]) -> int:
    with SessionLocal() as session:
        snapshot = GameSnapshotRecord(
            save_uid=save_uid,
            snapshot_date=game_date,
            data=json.dumps(data, ensure_ascii=False),
            created_at=datetime.utcnow(),
        )
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)
        return snapshot.id


def save_snapshot_if_new_day(save_uid: Optional[str], state_data: Dict[str, Any]) -> Optional[int]:
    # Evita duplicar snapshot para o mesmo save e mesma data de jogo.
    if not save_uid:
        return None
    game_date = (
        (((state_data.get("meta") or {}).get("game_date") or {}).get("year")),
        (((state_data.get("meta") or {}).get("game_date") or {}).get("month")),
        (((state_data.get("meta") or {}).get("game_date") or {}).get("day")),
    )
    if not all(game_date):
        return None
    date_str = f"{int(game_date[0]):04d}-{int(game_date[1]):02d}-{int(game_date[2]):02d}"
    with SessionLocal() as session:
        stmt = (
            select(GameSnapshotRecord)
            .where(GameSnapshotRecord.save_uid == save_uid)
            .where(GameSnapshotRecord.snapshot_date == date_str)
            .limit(1)
        )
        exists = session.execute(stmt).scalars().first()
        if exists:
            return None
    return save_snapshot(save_uid, date_str, state_data)


def upsert_external_artifact(save_uid: str, artifact_type: str, payload: Dict[str, Any], source_path: Optional[str] = None) -> int:
    with SessionLocal() as session:
        row = session.execute(
            select(ExternalArtifactRecord)
            .where(ExternalArtifactRecord.save_uid == save_uid)
            .where(ExternalArtifactRecord.artifact_type == artifact_type)
            .limit(1)
        ).scalars().first()
        if row is None:
            row = ExternalArtifactRecord(save_uid=save_uid, artifact_type=artifact_type)
            session.add(row)
        row.payload = json.dumps(payload, ensure_ascii=False)
        row.source_path = source_path
        row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return row.id


def get_external_artifact(save_uid: str, artifact_type: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        row = session.execute(
            select(ExternalArtifactRecord)
            .where(ExternalArtifactRecord.save_uid == save_uid)
            .where(ExternalArtifactRecord.artifact_type == artifact_type)
            .limit(1)
        ).scalars().first()
        if row is None:
            return None
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "artifact_type": row.artifact_type,
            "payload": _deserialize_json(row.payload, {}),
            "source_path": row.source_path,
            "updated_at": row.updated_at.isoformat(),
        }


def insert_external_event_log(
    save_uid: str,
    timestamp: datetime,
    payload: Dict[str, Any],
    event_id_raw: Optional[int] = None,
    event_name_raw: Optional[str] = None,
    category: Optional[str] = None,
    importance: Optional[int] = None,
) -> int:
    with SessionLocal() as session:
        row = ExternalEventLogRecord(
            save_uid=save_uid,
            timestamp=timestamp,
            event_id_raw=event_id_raw,
            event_name_raw=event_name_raw,
            category=category,
            importance=importance,
            payload=json.dumps(payload, ensure_ascii=False),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_external_event_logs(save_uid: str, limit: int = 50) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(ExternalEventLogRecord)
            .where(ExternalEventLogRecord.save_uid == save_uid)
            .order_by(desc(ExternalEventLogRecord.timestamp))
            .limit(limit)
        ).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "timestamp": row.timestamp.isoformat(),
                "event_id_raw": row.event_id_raw,
                "event_name_raw": row.event_name_raw,
                "category": row.category,
                "importance": row.importance,
                "payload": _deserialize_json(row.payload, {}),
            }
            for row in rows
        ]


def replace_career_facts(save_uid: str, game_date: str, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(CareerFactRecord)
            .where(CareerFactRecord.save_uid == save_uid)
            .where(CareerFactRecord.game_date == game_date)
        ).scalars().all()
        for row in rows:
            session.delete(row)
        session.flush()
        now = datetime.utcnow()
        for fact in facts:
            editorial_flags = dict(fact.get("editorial_flags") or {})
            row = CareerFactRecord(
                save_uid=save_uid,
                game_date=game_date,
                fact_type=str(fact.get("fact_type") or "generic_fact"),
                category=str(fact.get("category") or "generic"),
                title=str(fact.get("title") or ""),
                summary=str(fact.get("summary") or ""),
                importance=int(fact.get("importance") or 50),
                confidence=float(fact.get("confidence") or 0.5),
                status=str(fact.get("status") or "active"),
                dedupe_group=str(
                    editorial_flags.get("dedupe_group")
                    or fact.get("dedupe_group")
                    or f"{fact.get('fact_type')}_{fact.get('title')}"
                ),
                entities_json=json.dumps(fact.get("entities") or {}, ensure_ascii=False),
                source_refs_json=json.dumps(fact.get("source_refs") or [], ensure_ascii=False),
                signals_json=json.dumps(fact.get("signals") or {}, ensure_ascii=False),
                editorial_flags_json=json.dumps(editorial_flags, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        session.commit()
    return get_career_facts(save_uid=save_uid, game_date=game_date)


def merge_career_facts(save_uid: str, game_date: str, new_facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mescla novos factos no dia por dedupe_group (novos sobrescrevem chave igual) sem apagar os restantes."""
    existing = get_career_facts(save_uid=save_uid, game_date=game_date, limit=500)
    by_dedupe: Dict[str, Dict[str, Any]] = {}
    for ef in existing:
        dg = str(ef.get("dedupe_group") or (ef.get("editorial_flags") or {}).get("dedupe_group") or "").strip()
        if not dg:
            dg = f"_legacy_id_{ef.get('id')}"
        clean = {k: v for k, v in ef.items() if k != "id"}
        by_dedupe[dg] = clean
    for nf in new_facts:
        fact = dict(nf)
        editorial = dict(fact.get("editorial_flags") or {})
        dg = str(editorial.get("dedupe_group") or fact.get("dedupe_group") or "").strip()
        if not dg:
            ft = str(fact.get("fact_type") or "fact")
            dg = f"_nf_{ft}_{abs(hash(json.dumps(fact, sort_keys=True, default=str))) % (10**9)}"
            editorial["dedupe_group"] = dg
            fact["editorial_flags"] = editorial
        by_dedupe[dg] = fact
    return replace_career_facts(save_uid=save_uid, game_date=game_date, facts=list(by_dedupe.values()))


def get_career_facts(
    save_uid: str,
    game_date: str,
    eligible_surface: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(CareerFactRecord)
            .where(CareerFactRecord.save_uid == save_uid)
            .where(CareerFactRecord.game_date == game_date)
            .order_by(desc(CareerFactRecord.importance), desc(CareerFactRecord.updated_at))
            .limit(limit)
        ).scalars().all()
        items: List[Dict[str, Any]] = []
        for row in rows:
            editorial_flags = _deserialize_json(row.editorial_flags_json, {})
            if eligible_surface:
                flag_name = f"eligible_for_{eligible_surface}"
                if not bool(editorial_flags.get(flag_name)):
                    continue
            items.append(
                {
                    "id": row.id,
                    "fact_id": str(row.id),
                    "save_uid": row.save_uid,
                    "game_date": row.game_date,
                    "fact_type": row.fact_type,
                    "category": row.category,
                    "title": row.title,
                    "summary": row.summary,
                    "importance": row.importance,
                    "confidence": row.confidence,
                    "status": row.status,
                    "dedupe_group": row.dedupe_group,
                    "entities": _deserialize_json(row.entities_json, {}),
                    "source_refs": _deserialize_json(row.source_refs_json, []),
                    "signals": _deserialize_json(row.signals_json, {}),
                    "editorial_flags": editorial_flags,
                    "created_at": row.created_at.isoformat(),
                    "updated_at": row.updated_at.isoformat(),
                }
            )
        return items


def replace_news_daily_package(
    save_uid: str,
    game_date: str,
    edition_label: str,
    lead_angle: str,
    density_level: str,
    layout_hints: Dict[str, Any],
    stories: List[Dict[str, Any]],
) -> Dict[str, Any]:
    with SessionLocal() as session:
        package = session.execute(
            select(NewsDailyPackageRecord)
            .where(NewsDailyPackageRecord.save_uid == save_uid)
            .where(NewsDailyPackageRecord.game_date == game_date)
            .limit(1)
        ).scalars().first()
        now = datetime.utcnow()
        if package is None:
            package = NewsDailyPackageRecord(
                save_uid=save_uid,
                game_date=game_date,
                created_at=now,
            )
            session.add(package)
            session.flush()
        package.edition_label = edition_label
        package.lead_angle = lead_angle
        package.density_level = density_level
        package.stories_count = len(stories)
        package.layout_hints_json = json.dumps(layout_hints, ensure_ascii=False)
        package.updated_at = now
        existing_articles = session.execute(
            select(NewsDailyArticleRecord).where(NewsDailyArticleRecord.package_id == package.id)
        ).scalars().all()
        for row in existing_articles:
            session.delete(row)
        session.flush()
        used_slots: set[str] = set()

        def _unique_slot(base: str) -> str:
            s = base or "lead"
            if s not in used_slots:
                used_slots.add(s)
                return s
            n = 2
            while f"{s}_{n}" in used_slots:
                n += 1
            out = f"{s}_{n}"
            used_slots.add(out)
            return out

        for story in stories:
            base_slot = str(story.get("slot") or "lead")
            slot_value = _unique_slot(base_slot)
            article = NewsDailyArticleRecord(
                package_id=package.id,
                save_uid=save_uid,
                game_date=game_date,
                slot=slot_value,
                kind=str(story.get("kind") or "news"),
                priority=int(story.get("priority") or 50),
                impact=str(story.get("impact") or "medium"),
                headline=str(story.get("headline") or ""),
                subheadline=str(story.get("subheadline") or ""),
                lead=str(story.get("lead") or ""),
                body_json=json.dumps(story.get("body") or [], ensure_ascii=False),
                why_it_matters=str(story.get("why_it_matters") or ""),
                club_effects_json=json.dumps(story.get("club_effects") or [], ensure_ascii=False),
                tags_json=json.dumps(story.get("tags") or [], ensure_ascii=False),
                entities_json=json.dumps(story.get("entities") or {}, ensure_ascii=False),
                source_facts_json=json.dumps(story.get("source_facts") or [], ensure_ascii=False),
                cover_image_url=story.get("cover_image_url"),
                published_at=_parse_iso_datetime(story.get("published_at")),
                created_at=now,
                updated_at=now,
            )
            session.add(article)
        session.commit()
    package_payload = get_news_daily_package(save_uid=save_uid, game_date=game_date)
    if package_payload is None:
        raise ValueError("Falha ao persistir pacote editorial diário")
    return package_payload


def get_news_daily_package(save_uid: str, game_date: str) -> Optional[Dict[str, Any]]:
    """Pacote editorial diário. Enriquece `slot_label` ao ler (histórico sem esse campo no DB)."""
    from front_read_models import enrich_news_story_for_client

    with SessionLocal() as session:
        package = session.execute(
            select(NewsDailyPackageRecord)
            .where(NewsDailyPackageRecord.save_uid == save_uid)
            .where(NewsDailyPackageRecord.game_date == game_date)
            .limit(1)
        ).scalars().first()
        if package is None:
            return None
        articles = session.execute(
            select(NewsDailyArticleRecord)
            .where(NewsDailyArticleRecord.package_id == package.id)
            .order_by(desc(NewsDailyArticleRecord.priority), NewsDailyArticleRecord.id)
        ).scalars().all()
        return {
            "package_id": str(package.id),
            "save_uid": package.save_uid,
            "game_date": package.game_date,
            "edition_label": package.edition_label,
            "lead_angle": package.lead_angle,
            "density_level": package.density_level,
            "stories_count": package.stories_count,
            "layout_hints": _deserialize_json(package.layout_hints_json, {}),
            "created_at": package.created_at.isoformat(),
            "updated_at": package.updated_at.isoformat(),
            "stories": [
                enrich_news_story_for_client(
                    {
                        "article_id": str(row.id),
                        "slot": row.slot,
                        "kind": row.kind,
                        "priority": row.priority,
                        "impact": row.impact,
                        "headline": row.headline,
                        "subheadline": row.subheadline,
                        "lead": row.lead,
                        "body": _deserialize_json(row.body_json, []),
                        "why_it_matters": row.why_it_matters,
                        "club_effects": _deserialize_json(row.club_effects_json, []),
                        "tags": _deserialize_json(row.tags_json, []),
                        "entities": _deserialize_json(row.entities_json, {}),
                        "source_facts": _deserialize_json(row.source_facts_json, []),
                        "cover_image_url": row.cover_image_url,
                        "theme": "dark_editorial",
                        "published_at": row.published_at.isoformat(),
                        "created_at": row.created_at.isoformat(),
                        "updated_at": row.updated_at.isoformat(),
                    }
                )
                for row in articles
            ],
        }


def get_or_create_career_management_state(save_uid: str) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = session.execute(
            select(CareerManagementStateRecord).where(CareerManagementStateRecord.save_uid == save_uid).limit(1)
        ).scalars().first()
        if row:
            return {
                "save_uid": row.save_uid,
                "locker_room": _deserialize_json(row.locker_room_json, {}),
                "finance": _deserialize_json(row.finance_json, {}),
                "tactical": _deserialize_json(row.tactical_json, {}),
                "academy": _deserialize_json(row.academy_json, {}),
                "medical": _deserialize_json(row.medical_json, {}),
                "updated_at": row.updated_at.isoformat(),
            }
        created = CareerManagementStateRecord(save_uid=save_uid, updated_at=datetime.utcnow())
        session.add(created)
        session.commit()
        session.refresh(created)
        return {
            "save_uid": created.save_uid,
            "locker_room": {},
            "finance": {},
            "tactical": {},
            "academy": {},
            "medical": {},
            "updated_at": created.updated_at.isoformat(),
        }


def upsert_career_management_state(
    save_uid: str,
    locker_room: Dict[str, Any],
    finance: Dict[str, Any],
    tactical: Dict[str, Any],
    academy: Dict[str, Any],
    medical: Dict[str, Any],
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = session.execute(
            select(CareerManagementStateRecord).where(CareerManagementStateRecord.save_uid == save_uid).limit(1)
        ).scalars().first()
        if row is None:
            row = CareerManagementStateRecord(save_uid=save_uid)
            session.add(row)
        row.locker_room_json = json.dumps(locker_room, ensure_ascii=False)
        row.finance_json = json.dumps(finance, ensure_ascii=False)
        row.tactical_json = json.dumps(tactical, ensure_ascii=False)
        row.academy_json = json.dumps(academy, ensure_ascii=False)
        row.medical_json = json.dumps(medical, ensure_ascii=False)
        row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return {
            "save_uid": row.save_uid,
            "locker_room": _deserialize_json(row.locker_room_json, {}),
            "finance": _deserialize_json(row.finance_json, {}),
            "tactical": _deserialize_json(row.tactical_json, {}),
            "academy": _deserialize_json(row.academy_json, {}),
            "medical": _deserialize_json(row.medical_json, {}),
            "updated_at": row.updated_at.isoformat(),
        }


def get_player_relations(save_uid: str, limit: int = 200) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = (
            select(PlayerRelationRecord)
            .where(PlayerRelationRecord.save_uid == save_uid)
            .order_by(desc(PlayerRelationRecord.updated_at))
            .limit(limit)
        )
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "playerid": row.playerid,
                "player_name": row.player_name,
                "trust": row.trust,
                "role_label": row.role_label,
                "status_label": row.status_label,
                "frustration": row.frustration,
                "notes": _deserialize_json(row.notes_json, {}),
                "updated_at": row.updated_at.isoformat(),
            }
            for row in rows
        ]


def get_player_relation(save_uid: str, playerid: int) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        row = session.execute(
            select(PlayerRelationRecord)
            .where(PlayerRelationRecord.save_uid == save_uid)
            .where(PlayerRelationRecord.playerid == int(playerid))
            .limit(1)
        ).scalars().first()
        if row is None:
            return None
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "playerid": row.playerid,
            "player_name": row.player_name,
            "trust": row.trust,
            "role_label": row.role_label,
            "status_label": row.status_label,
            "frustration": row.frustration,
            "notes": _deserialize_json(row.notes_json, {}),
            "updated_at": row.updated_at.isoformat(),
        }


def upsert_player_relation(
    save_uid: str,
    playerid: int,
    player_name: Optional[str],
    trust: int,
    role_label: str,
    status_label: str,
    frustration: int,
    notes: Dict[str, Any],
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = session.execute(
            select(PlayerRelationRecord)
            .where(PlayerRelationRecord.save_uid == save_uid)
            .where(PlayerRelationRecord.playerid == playerid)
            .limit(1)
        ).scalars().first()
        if row is None:
            row = PlayerRelationRecord(save_uid=save_uid, playerid=playerid)
            session.add(row)
        row.player_name = player_name
        row.trust = int(trust)
        row.role_label = role_label
        row.status_label = status_label
        row.frustration = int(frustration)
        row.notes_json = json.dumps(notes, ensure_ascii=False)
        row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "playerid": row.playerid,
            "player_name": row.player_name,
            "trust": row.trust,
            "role_label": row.role_label,
            "status_label": row.status_label,
            "frustration": row.frustration,
            "notes": _deserialize_json(row.notes_json, {}),
            "updated_at": row.updated_at.isoformat(),
        }


def save_finance_ledger_entry(save_uid: str, period: str, kind: str, amount: float, description: str) -> int:
    with SessionLocal() as session:
        row = FinanceLedgerRecord(
            save_uid=save_uid,
            period=period,
            kind=kind,
            amount=float(amount),
            description=description,
            created_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_finance_ledger(limit: int = 30, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(FinanceLedgerRecord).order_by(desc(FinanceLedgerRecord.created_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(FinanceLedgerRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "period": row.period,
                "kind": row.kind,
                "amount": row.amount,
                "description": row.description,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def save_narrative(
    event_type: str,
    title: str,
    content: str,
    tone: str,
    source: str,
    save_uid: Optional[str],
) -> int:
    with SessionLocal() as session:
        row = NarrativeRecord(
            event_type=event_type,
            title=title,
            content=content,
            tone=tone,
            source=source,
            save_uid=save_uid,
            created_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_narratives(limit: int = 20, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(NarrativeRecord).order_by(desc(NarrativeRecord.created_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(NarrativeRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "event_type": row.event_type,
                "title": row.title,
                "content": row.content,
                "tone": row.tone,
                "source": row.source,
                "save_uid": row.save_uid,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def get_narratives_by_event_type(event_type: str, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = (
            select(NarrativeRecord)
            .where(NarrativeRecord.event_type == event_type)
            .order_by(desc(NarrativeRecord.created_at))
        )
        if save_uid:
            stmt = stmt.where(NarrativeRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "event_type": row.event_type,
                "title": row.title,
                "content": row.content,
                "tone": row.tone,
                "source": row.source,
                "save_uid": row.save_uid,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def save_feed_item(
    event_type: str,
    channel: str,
    title: str,
    content: str,
    tone: str,
    source: str,
    save_uid: Optional[str],
) -> int:
    with SessionLocal() as session:
        row = FeedItemRecord(
            event_type=event_type,
            channel=channel,
            title=title,
            content=content,
            tone=tone,
            source=source,
            save_uid=save_uid,
            created_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_feed(limit: int = 30, save_uid: Optional[str] = None, channel: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(FeedItemRecord).order_by(desc(FeedItemRecord.created_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(FeedItemRecord.save_uid == save_uid)
        if channel:
            stmt = stmt.where(FeedItemRecord.channel == channel)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "event_type": row.event_type,
                "channel": row.channel,
                "title": row.title,
                "content": row.content,
                "tone": row.tone,
                "source": row.source,
                "save_uid": row.save_uid,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def get_or_create_coach_profile(save_uid: str) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = (
            session.execute(select(CoachProfileStateRecord).where(CoachProfileStateRecord.save_uid == save_uid).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            row = CoachProfileStateRecord(
                save_uid=save_uid,
                reputation_score=50,
                reputation_label="estável",
                playstyle_label="equilibrado",
                fan_sentiment_score=50,
                fan_sentiment_label="neutro",
                updated_at=datetime.utcnow(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        return {
            "save_uid": row.save_uid,
            "reputation_score": row.reputation_score,
            "reputation_label": row.reputation_label,
            "playstyle_label": row.playstyle_label,
            "fan_sentiment_score": row.fan_sentiment_score,
            "fan_sentiment_label": row.fan_sentiment_label,
            "updated_at": row.updated_at.isoformat(),
        }


def update_coach_profile(
    save_uid: str,
    reputation_score: int,
    reputation_label: str,
    playstyle_label: str,
    fan_sentiment_score: int,
    fan_sentiment_label: str,
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = (
            session.execute(select(CoachProfileStateRecord).where(CoachProfileStateRecord.save_uid == save_uid).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            row = CoachProfileStateRecord(save_uid=save_uid)
            session.add(row)
        row.reputation_score = int(reputation_score)
        row.reputation_label = reputation_label
        row.playstyle_label = playstyle_label
        row.fan_sentiment_score = int(fan_sentiment_score)
        row.fan_sentiment_label = fan_sentiment_label
        row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return {
            "save_uid": row.save_uid,
            "reputation_score": row.reputation_score,
            "reputation_label": row.reputation_label,
            "playstyle_label": row.playstyle_label,
            "fan_sentiment_score": row.fan_sentiment_score,
            "fan_sentiment_label": row.fan_sentiment_label,
            "updated_at": row.updated_at.isoformat(),
        }


def save_press_conference(
    save_uid: Optional[str],
    question: str,
    answer: str,
    detected_tone: str,
    reputation_delta: int,
    morale_delta: int,
    headline: str,
    board_reaction: str,
    locker_room_reaction: str,
    fan_reaction: str,
    game_date: Optional[str] = None,
) -> int:
    with SessionLocal() as session:
        row = PressConferenceRecord(
            save_uid=save_uid,
            game_date=game_date,
            question=question,
            answer=answer,
            detected_tone=detected_tone,
            reputation_delta=reputation_delta,
            morale_delta=morale_delta,
            headline=headline,
            board_reaction=board_reaction,
            locker_room_reaction=locker_room_reaction,
            fan_reaction=fan_reaction,
            created_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_press_conferences(limit: int = 20, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(PressConferenceRecord).order_by(desc(PressConferenceRecord.created_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(PressConferenceRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "game_date": row.game_date,
                "question": row.question,
                "answer": row.answer,
                "detected_tone": row.detected_tone,
                "reputation_delta": row.reputation_delta,
                "morale_delta": row.morale_delta,
                "headline": row.headline,
                "board_reaction": row.board_reaction,
                "locker_room_reaction": row.locker_room_reaction,
                "fan_reaction": row.fan_reaction,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def count_press_conferences_for_game_date(save_uid: str, game_date: str) -> int:
    with SessionLocal() as session:
        stmt = (
            select(PressConferenceRecord)
            .where(PressConferenceRecord.save_uid == save_uid)
            .where(PressConferenceRecord.game_date == game_date)
        )
        return len(session.execute(stmt).scalars().all())


def get_recent_match_event_payloads(save_uid: str, limit: int = 5) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = (
            select(EventRecord)
            .where(EventRecord.save_uid == save_uid)
            .where(EventRecord.event_type.in_(["MATCH_COMPLETED", "match_won", "match_lost", "match_drawn"]))
            .order_by(desc(EventRecord.timestamp))
            .limit(limit)
        )
        rows = session.execute(stmt).scalars().all()
        # Converte payload híbrido para o formato esperado pelo Board Engine
        payloads = []
        for row in rows:
            payload = _deserialize_payload(row.payload)
            if row.event_type != "MATCH_COMPLETED":
                # Sempre coloca my_score como home para simplificar o extract_result
                adapted = {
                    "home_score": payload.get("my_score"),
                    "away_score": payload.get("opp_score"),
                }
                payloads.append(adapted)
            else:
                payloads.append(payload)
        return payloads


def get_match_events(save_uid: str, limit: int = 5000) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        rows = (
            session.execute(
                select(EventRecord)
                .where(EventRecord.save_uid == save_uid)
                .where(EventRecord.event_type.in_(["MATCH_COMPLETED", "match_won", "match_lost", "match_drawn"]))
                .order_by(EventRecord.timestamp)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": row.id,
                "event_type": row.event_type,
                "payload": _deserialize_payload(row.payload),
                "timestamp": row.timestamp,
                "save_uid": row.save_uid,
            }
            for row in rows
        ]


def get_active_board_challenge(save_uid: str, challenge_type: str = "ULTIMATUM") -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        row = (
            session.execute(
                select(BoardChallengeRecord)
                .where(BoardChallengeRecord.save_uid == save_uid)
                .where(BoardChallengeRecord.challenge_type == challenge_type)
                .where(BoardChallengeRecord.status == "active")
                .order_by(desc(BoardChallengeRecord.created_at))
                .limit(1)
            )
            .scalars()
            .first()
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "challenge_type": row.challenge_type,
            "title": row.title,
            "description": row.description,
            "status": row.status,
            "required_points": row.required_points,
            "current_points": row.current_points,
            "matches_remaining": row.matches_remaining,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }


def create_board_challenge(
    save_uid: str,
    challenge_type: str,
    title: str,
    description: str,
    required_points: int,
    matches_remaining: int,
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = BoardChallengeRecord(
            save_uid=save_uid,
            challenge_type=challenge_type,
            title=title,
            description=description,
            status="active",
            required_points=required_points,
            current_points=0,
            matches_remaining=matches_remaining,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            resolved_at=None,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "challenge_type": row.challenge_type,
            "title": row.title,
            "description": row.description,
            "status": row.status,
            "required_points": row.required_points,
            "current_points": row.current_points,
            "matches_remaining": row.matches_remaining,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "resolved_at": None,
        }


def update_board_challenge_progress(
    challenge_id: int,
    points_earned: int,
    status: str,
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = (
            session.execute(select(BoardChallengeRecord).where(BoardChallengeRecord.id == challenge_id).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            raise ValueError("challenge não encontrado")
        row.current_points = int(row.current_points) + int(points_earned)
        row.matches_remaining = max(0, int(row.matches_remaining) - 1)
        row.status = status
        row.updated_at = datetime.utcnow()
        if status in {"completed", "failed"}:
            row.resolved_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "challenge_type": row.challenge_type,
            "title": row.title,
            "description": row.description,
            "status": row.status,
            "required_points": row.required_points,
            "current_points": row.current_points,
            "matches_remaining": row.matches_remaining,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }


def get_recent_board_challenges(limit: int = 20, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(BoardChallengeRecord).order_by(desc(BoardChallengeRecord.created_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(BoardChallengeRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "challenge_type": row.challenge_type,
                "title": row.title,
                "description": row.description,
                "status": row.status,
                "required_points": row.required_points,
                "current_points": row.current_points,
                "matches_remaining": row.matches_remaining,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            }
            for row in rows
        ]


def save_market_rumor(
    save_uid: Optional[str],
    trigger_event: str,
    headline: str,
    content: str,
    confidence_level: int,
    target_profile: str,
) -> int:
    with SessionLocal() as session:
        row = MarketRumorRecord(
            save_uid=save_uid,
            trigger_event=trigger_event,
            headline=headline,
            content=content,
            confidence_level=int(confidence_level),
            target_profile=target_profile,
            created_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_market_rumors(
    limit: int = 20,
    save_uid: Optional[str] = None,
    trigger_event: Optional[str] = None,
) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(MarketRumorRecord).order_by(desc(MarketRumorRecord.created_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(MarketRumorRecord.save_uid == save_uid)
        if trigger_event:
            stmt = stmt.where(MarketRumorRecord.trigger_event == trigger_event)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "trigger_event": row.trigger_event,
                "headline": row.headline,
                "content": row.content,
                "confidence_level": row.confidence_level,
                "target_profile": row.target_profile,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def save_timeline_entry(
    save_uid: Optional[str],
    source_event: str,
    phase: str,
    title: str,
    content: str,
    importance: int,
) -> int:
    with SessionLocal() as session:
        row = EditorialTimelineRecord(
            save_uid=save_uid,
            source_event=source_event,
            phase=phase,
            title=title,
            content=content,
            importance=int(importance),
            created_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_timeline_entries(
    limit: int = 30,
    save_uid: Optional[str] = None,
    phase: Optional[str] = None,
    source_event: Optional[str] = None,
) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(EditorialTimelineRecord).order_by(desc(EditorialTimelineRecord.created_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(EditorialTimelineRecord.save_uid == save_uid)
        if phase:
            stmt = stmt.where(EditorialTimelineRecord.phase == phase)
        if source_event:
            stmt = stmt.where(EditorialTimelineRecord.source_event == source_event)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "source_event": row.source_event,
                "phase": row.phase,
                "title": row.title,
                "content": row.content,
                "importance": row.importance,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def get_active_crisis_arc(save_uid: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        row = (
            session.execute(
                select(CrisisArcStateRecord)
                .where(CrisisArcStateRecord.save_uid == save_uid)
                .where(CrisisArcStateRecord.status == "active")
                .order_by(desc(CrisisArcStateRecord.started_at))
                .limit(1)
            )
            .scalars()
            .first()
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "trigger_type": row.trigger_type,
            "status": row.status,
            "severity": row.severity,
            "summary": row.summary,
            "current_step": row.current_step,
            "max_steps": row.max_steps,
            "started_at": row.started_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }


def create_crisis_arc(
    save_uid: str,
    trigger_type: str,
    severity: str,
    summary: str,
    max_steps: int,
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = CrisisArcStateRecord(
            save_uid=save_uid,
            trigger_type=trigger_type,
            status="active",
            severity=severity,
            summary=summary,
            current_step=1,
            max_steps=int(max_steps),
            started_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            resolved_at=None,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "trigger_type": row.trigger_type,
            "status": row.status,
            "severity": row.severity,
            "summary": row.summary,
            "current_step": row.current_step,
            "max_steps": row.max_steps,
            "started_at": row.started_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "resolved_at": None,
        }


def update_crisis_arc_progress(
    crisis_id: int,
    status: str,
    step_increment: int = 1,
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = (
            session.execute(select(CrisisArcStateRecord).where(CrisisArcStateRecord.id == crisis_id).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            raise ValueError("crisis arc não encontrado")
        row.current_step = int(row.current_step) + int(step_increment)
        row.status = status
        row.updated_at = datetime.utcnow()
        if status in {"resolved", "collapsed"}:
            row.resolved_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "trigger_type": row.trigger_type,
            "status": row.status,
            "severity": row.severity,
            "summary": row.summary,
            "current_step": row.current_step,
            "max_steps": row.max_steps,
            "started_at": row.started_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }


def get_recent_crisis_arcs(limit: int = 20, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(CrisisArcStateRecord).order_by(desc(CrisisArcStateRecord.started_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(CrisisArcStateRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "trigger_type": row.trigger_type,
                "status": row.status,
                "severity": row.severity,
                "summary": row.summary,
                "current_step": row.current_step,
                "max_steps": row.max_steps,
                "started_at": row.started_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            }
            for row in rows
        ]


def get_active_season_arc(save_uid: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        row = (
            session.execute(
                select(SeasonArcStateRecord)
                .where(SeasonArcStateRecord.save_uid == save_uid)
                .where(SeasonArcStateRecord.status == "active")
                .order_by(desc(SeasonArcStateRecord.started_at))
                .limit(1)
            )
            .scalars()
            .first()
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "title": row.title,
            "theme": row.theme,
            "season_label": row.season_label,
            "status": row.status,
            "current_milestone": row.current_milestone,
            "max_milestones": row.max_milestones,
            "memories": _deserialize_payload(row.memories_json).get("items", []),
            "started_at": row.started_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }


def create_season_arc(
    save_uid: str,
    title: str,
    theme: str,
    season_label: str,
    max_milestones: int = 5,
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = SeasonArcStateRecord(
            save_uid=save_uid,
            title=title,
            theme=theme,
            season_label=season_label,
            status="active",
            current_milestone=1,
            max_milestones=int(max_milestones),
            memories_json=json.dumps({"items": []}, ensure_ascii=False),
            started_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            resolved_at=None,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "title": row.title,
            "theme": row.theme,
            "season_label": row.season_label,
            "status": row.status,
            "current_milestone": row.current_milestone,
            "max_milestones": row.max_milestones,
            "memories": [],
            "started_at": row.started_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "resolved_at": None,
        }


def append_season_arc_memory(arc_id: int, memory_text: str, source_event: Optional[str] = None) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = (
            session.execute(select(SeasonArcStateRecord).where(SeasonArcStateRecord.id == arc_id).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            raise ValueError("season arc não encontrado")
        current = _deserialize_payload(row.memories_json)
        items = current.get("items", [])
        items.append(
            {
                "text": memory_text,
                "source_event": source_event,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        if len(items) > 100:
            items = items[-100:]
        row.memories_json = json.dumps({"items": items}, ensure_ascii=False)
        row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "title": row.title,
            "theme": row.theme,
            "season_label": row.season_label,
            "status": row.status,
            "current_milestone": row.current_milestone,
            "max_milestones": row.max_milestones,
            "memories": items,
            "started_at": row.started_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }


def update_season_arc_progress(arc_id: int, status: str, milestone_increment: int = 1) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = (
            session.execute(select(SeasonArcStateRecord).where(SeasonArcStateRecord.id == arc_id).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            raise ValueError("season arc não encontrado")
        row.current_milestone = int(row.current_milestone) + int(milestone_increment)
        row.status = status
        row.updated_at = datetime.utcnow()
        if status in {"resolved", "failed"}:
            row.resolved_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "title": row.title,
            "theme": row.theme,
            "season_label": row.season_label,
            "status": row.status,
            "current_milestone": row.current_milestone,
            "max_milestones": row.max_milestones,
            "memories": _deserialize_payload(row.memories_json).get("items", []),
            "started_at": row.started_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }


def get_recent_season_arcs(limit: int = 20, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(SeasonArcStateRecord).order_by(desc(SeasonArcStateRecord.started_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(SeasonArcStateRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "title": row.title,
                "theme": row.theme,
                "season_label": row.season_label,
                "status": row.status,
                "current_milestone": row.current_milestone,
                "max_milestones": row.max_milestones,
                "memories": _deserialize_payload(row.memories_json).get("items", []),
                "started_at": row.started_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            }
            for row in rows
        ]


def save_season_payoff(
    save_uid: str,
    season_arc_id: int,
    final_score: int,
    grade: str,
    title: str,
    epilogue: str,
    factors: Dict[str, Any],
) -> int:
    with SessionLocal() as session:
        row = SeasonPayoffRecord(
            save_uid=save_uid,
            season_arc_id=int(season_arc_id),
            final_score=int(final_score),
            grade=grade,
            title=title,
            epilogue=epilogue,
            factors_json=json.dumps(factors, ensure_ascii=False),
            created_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_season_payoffs(limit: int = 10, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(SeasonPayoffRecord).order_by(desc(SeasonPayoffRecord.created_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(SeasonPayoffRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "season_arc_id": row.season_arc_id,
                "final_score": row.final_score,
                "grade": row.grade,
                "title": row.title,
                "epilogue": row.epilogue,
                "factors": _deserialize_payload(row.factors_json),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def get_legacy_profile(save_uid: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        row = (
            session.execute(select(LegacyProfileRecord).where(LegacyProfileRecord.save_uid == save_uid).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "seasons_count": row.seasons_count,
            "average_score": float(row.average_score),
            "best_grade": row.best_grade,
            "legacy_rank": row.legacy_rank,
            "narrative_summary": row.narrative_summary,
            "updated_at": row.updated_at.isoformat(),
        }


def upsert_legacy_profile(
    save_uid: str,
    seasons_count: int,
    average_score: float,
    best_grade: str,
    legacy_rank: str,
    narrative_summary: str,
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = (
            session.execute(select(LegacyProfileRecord).where(LegacyProfileRecord.save_uid == save_uid).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            row = LegacyProfileRecord(save_uid=save_uid)
            session.add(row)
        row.seasons_count = int(seasons_count)
        row.average_score = float(average_score)
        row.best_grade = best_grade
        row.legacy_rank = legacy_rank
        row.narrative_summary = narrative_summary
        row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "seasons_count": row.seasons_count,
            "average_score": float(row.average_score),
            "best_grade": row.best_grade,
            "legacy_rank": row.legacy_rank,
            "narrative_summary": row.narrative_summary,
            "updated_at": row.updated_at.isoformat(),
        }


def save_hall_of_fame_entry(
    save_uid: str,
    category: str,
    title: str,
    description: str,
    score_impact: int,
    source: str,
) -> int:
    with SessionLocal() as session:
        row = HallOfFameEntryRecord(
            save_uid=save_uid,
            category=category,
            title=title,
            description=description,
            score_impact=int(score_impact),
            source=source,
            created_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_hall_of_fame_entries(limit: int = 20, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(HallOfFameEntryRecord).order_by(desc(HallOfFameEntryRecord.created_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(HallOfFameEntryRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "category": row.category,
                "title": row.title,
                "description": row.description,
                "score_impact": row.score_impact,
                "source": row.source,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def get_hall_of_fame_profile(save_uid: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        row = (
            session.execute(select(HallOfFameProfileRecord).where(HallOfFameProfileRecord.save_uid == save_uid).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "total_entries": row.total_entries,
            "legacy_score": float(row.legacy_score),
            "tier": row.tier,
            "highlight_title": row.highlight_title,
            "updated_at": row.updated_at.isoformat(),
        }


def upsert_hall_of_fame_profile(
    save_uid: str,
    total_entries: int,
    legacy_score: float,
    tier: str,
    highlight_title: Optional[str],
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = (
            session.execute(select(HallOfFameProfileRecord).where(HallOfFameProfileRecord.save_uid == save_uid).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            row = HallOfFameProfileRecord(save_uid=save_uid)
            session.add(row)
        row.total_entries = int(total_entries)
        row.legacy_score = float(legacy_score)
        row.tier = tier
        row.highlight_title = highlight_title
        row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "total_entries": row.total_entries,
            "legacy_score": float(row.legacy_score),
            "tier": row.tier,
            "highlight_title": row.highlight_title,
            "updated_at": row.updated_at.isoformat(),
        }


def has_achievement(save_uid: str, code: str) -> bool:
    with SessionLocal() as session:
        row = (
            session.execute(
                select(AchievementRecord)
                .where(AchievementRecord.save_uid == save_uid)
                .where(AchievementRecord.code == code)
                .limit(1)
            )
            .scalars()
            .first()
        )
        return row is not None


def save_achievement(
    save_uid: str,
    code: str,
    title: str,
    description: str,
    rarity: str,
    points: int,
    source: str,
) -> int:
    with SessionLocal() as session:
        row = AchievementRecord(
            save_uid=save_uid,
            code=code,
            title=title,
            description=description,
            rarity=rarity,
            points=int(points),
            source=source,
            created_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_achievements(limit: int = 20, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(AchievementRecord).order_by(desc(AchievementRecord.created_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(AchievementRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "code": row.code,
                "title": row.title,
                "description": row.description,
                "rarity": row.rarity,
                "points": row.points,
                "source": row.source,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def get_achievement_profile(save_uid: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        row = (
            session.execute(select(AchievementProfileRecord).where(AchievementProfileRecord.save_uid == save_uid).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "total_achievements": row.total_achievements,
            "total_points": row.total_points,
            "career_level": row.career_level,
            "top_achievement": row.top_achievement,
            "updated_at": row.updated_at.isoformat(),
        }


def upsert_achievement_profile(
    save_uid: str,
    total_achievements: int,
    total_points: int,
    career_level: str,
    top_achievement: Optional[str],
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = (
            session.execute(select(AchievementProfileRecord).where(AchievementProfileRecord.save_uid == save_uid).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            row = AchievementProfileRecord(save_uid=save_uid)
            session.add(row)
        row.total_achievements = int(total_achievements)
        row.total_points = int(total_points)
        row.career_level = career_level
        row.top_achievement = top_achievement
        row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "total_achievements": row.total_achievements,
            "total_points": row.total_points,
            "career_level": row.career_level,
            "top_achievement": row.top_achievement,
            "updated_at": row.updated_at.isoformat(),
        }


def has_meta_achievement(save_uid: str, code: str) -> bool:
    with SessionLocal() as session:
        row = (
            session.execute(
                select(MetaAchievementRecord)
                .where(MetaAchievementRecord.save_uid == save_uid)
                .where(MetaAchievementRecord.code == code)
                .limit(1)
            )
            .scalars()
            .first()
        )
        return row is not None


def save_meta_achievement(
    save_uid: str,
    code: str,
    title: str,
    description: str,
    collection_tag: str,
    points: int,
) -> int:
    with SessionLocal() as session:
        row = MetaAchievementRecord(
            save_uid=save_uid,
            code=code,
            title=title,
            description=description,
            collection_tag=collection_tag,
            points=int(points),
            created_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_meta_achievements(limit: int = 20, save_uid: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        stmt = select(MetaAchievementRecord).order_by(desc(MetaAchievementRecord.created_at)).limit(limit)
        if save_uid:
            stmt = stmt.where(MetaAchievementRecord.save_uid == save_uid)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "save_uid": row.save_uid,
                "code": row.code,
                "title": row.title,
                "description": row.description,
                "collection_tag": row.collection_tag,
                "points": row.points,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def get_meta_achievement_profile(save_uid: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        row = (
            session.execute(select(MetaAchievementProfileRecord).where(MetaAchievementProfileRecord.save_uid == save_uid).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "total_meta": row.total_meta,
            "collection_progress": _deserialize_payload(row.collection_progress_json),
            "prestige_level": row.prestige_level,
            "updated_at": row.updated_at.isoformat(),
        }


def upsert_meta_achievement_profile(
    save_uid: str,
    total_meta: int,
    collection_progress: Dict[str, Any],
    prestige_level: str,
) -> Dict[str, Any]:
    with SessionLocal() as session:
        row = (
            session.execute(select(MetaAchievementProfileRecord).where(MetaAchievementProfileRecord.save_uid == save_uid).limit(1))
            .scalars()
            .first()
        )
        if row is None:
            row = MetaAchievementProfileRecord(save_uid=save_uid)
            session.add(row)
        row.total_meta = int(total_meta)
        row.collection_progress_json = json.dumps(collection_progress, ensure_ascii=False)
        row.prestige_level = prestige_level
        row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "save_uid": row.save_uid,
            "total_meta": row.total_meta,
            "collection_progress": _deserialize_payload(row.collection_progress_json),
            "prestige_level": row.prestige_level,
            "updated_at": row.updated_at.isoformat(),
        }
