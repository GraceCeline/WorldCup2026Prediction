"""
main.py  —  WC 2026 Predictor  FastAPI Backend
================================================
Endpoints
---------
GET  /api/matches          → all upcoming matches with win probabilities
GET  /api/matches/{id}     → single match detail
GET  /api/refresh          → manually trigger a data + prediction refresh
GET  /api/status           → last refresh time, model version, match count

Background scheduler refreshes data every 90 minutes automatically.

Run locally:
    uvicorn src.api.main:app --reload --port 8000
"""

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests# 
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from pydantic import BaseModel

from model_store import load_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── config ────────────────────────────────────────────────────────────────────
API_URL = "https://worldcup26.ir/get/games"
WC_API_BASE    = os.getenv("WC_API_BASE", "https://api.football-data.org/v4")
WC_API_KEY     = os.getenv("WC_API_KEY", "")          # set in .env
REFRESH_MINS   = int(os.getenv("REFRESH_MINS", "90")) # how often to pull
WC_COMPETITION = os.getenv("WC_COMPETITION", "WC")    # competition code

# ── in-memory state ───────────────────────────────────────────────────────────
_state: dict[str, Any] = {
    "matches":      [],
    "last_refresh": None,
    "model_version": None,
    "error":        None,
}


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class TeamPrediction(BaseModel):
    name: str
    flag: str            # emoji flag or URL
    win_probability: float
    elo: float | None = None
    fifa_rank: int | None = None

class MatchPrediction(BaseModel):
    match_id: str
    stage: str
    date: str            # ISO-8601
    venue: str
    team_a: TeamPrediction
    team_b: TeamPrediction
    draw_probability: float
    predicted_winner: str
    confidence: str      # "High" / "Medium" / "Low"
    status: str          # "SCHEDULED" | "LIVE" | "FINISHED"

class StatusResponse(BaseModel):
    last_refresh: str | None
    next_refresh_mins: int
    model_version: str | None
    match_count: int
    error: str | None


# ─────────────────────────────────────────────────────────────────────────────
# World Cup API client  (replace with your actual API)
# ─────────────────────────────────────────────────────────────────────────────

def _flag(country: str) -> str:
    FLAGS = {
        "Brazil": "🇧🇷", "Argentina": "🇦🇷", "France": "🇫🇷",
        "Germany": "🇩🇪", "Spain": "🇪🇸", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "Portugal": "🇵🇹", "Netherlands": "🇳🇱", "USA": "🇺🇸",
        "Mexico": "🇲🇽", "Morocco": "🇲🇦", "Japan": "🇯🇵",
        "Canada": "🇨🇦", "Croatia": "🇭🇷", "Senegal": "🇸🇳",
    }
    return FLAGS.get(country, "🏳")


def fetch_upcoming_matches() -> list[dict]:
    """
    Fetch upcoming/live WC matches from your API.

    Returns a normalised list of raw match dicts.
    Replace the body with your actual API client code.
    """
    if WC_API_KEY:
        import requests
        url = f"{WC_API_BASE}/competitions/{WC_COMPETITION}/matches?status=SCHEDULED"
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        raw_matches = r.json().get("matches", [])
        return [
            {
                "id":       str(m["id"]),
                "stage":    m.get("stage", "GROUP_STAGE"),
                "date":     m["utcDate"],
                "venue":    m.get("venue", "TBD"),
                "team_a":   m["homeTeam"]["name"],
                "team_b":   m["awayTeam"]["name"],
                "status":   m["status"],
                # your API may expose ELO / rank — add fields here
                "elo_a":    None,
                "elo_b":    None,
                "rank_a":   None,
                "rank_b":   None,
            }
            for m in raw_matches
        ]

    # ── DEMO data when no API key is configured ───────────────────────────────
    import random
    rng = random.Random(42)
    matchups = [
        ("Brazil",      "Argentina",   "Group A", "2026-06-15T18:00:00Z", "MetLife Stadium"),
        ("France",      "Germany",     "Group B", "2026-06-15T21:00:00Z", "AT&T Stadium"),
        ("Spain",       "Portugal",    "Group C", "2026-06-16T18:00:00Z", "Rose Bowl"),
        ("England",     "Netherlands", "Group D", "2026-06-16T21:00:00Z", "SoFi Stadium"),
        ("USA",         "Mexico",      "Group E", "2026-06-17T18:00:00Z", "Estadio Azteca"),
        ("Morocco",     "Japan",       "Group F", "2026-06-17T21:00:00Z", "Levi's Stadium"),
        ("Canada",      "Croatia",     "Group G", "2026-06-18T18:00:00Z", "BC Place"),
        ("Senegal",     "Brazil",      "Group H", "2026-06-18T21:00:00Z", "Gillette Stadium"),
        ("Argentina",   "Spain",       "R16",     "2026-06-26T18:00:00Z", "MetLife Stadium"),
        ("France",      "England",     "R16",     "2026-06-26T21:00:00Z", "AT&T Stadium"),
        ("Brazil",      "France",      "QF",      "2026-07-04T18:00:00Z", "Rose Bowl"),
        ("Argentina",   "England",     "QF",      "2026-07-04T21:00:00Z", "SoFi Stadium"),
        ("Brazil",      "Argentina",   "SF",      "2026-07-14T18:00:00Z", "MetLife Stadium"),
        ("France",      "England",     "Final",   "2026-07-19T18:00:00Z", "MetLife Stadium"),
    ]
    return [
        {
            "id":     str(i + 1),
            "stage":  stage,
            "date":   date,
            "venue":  venue,
            "team_a": a,
            "team_b": b,
            "status": "SCHEDULED",
            "elo_a":  rng.randint(1600, 2000),
            "elo_b":  rng.randint(1600, 2000),
            "rank_a": rng.randint(1, 30),
            "rank_b": rng.randint(1, 30),
        }
        for i, (a, b, stage, date, venue) in enumerate(matchups)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Feature builder  →  replace with your real feature engineering
# ─────────────────────────────────────────────────────────────────────────────

import numpy as np

# Rough Elo lookup for demo — in production, pull from your feature store
_ELO_TABLE = {
    "Brazil": 2068, "France": 2003, "Argentina": 2141, "Spain": 1975,
    "England": 1959, "Germany": 1903, "Portugal": 1966, "Netherlands": 1934,
    "USA": 1700, "Mexico": 1788, "Morocco": 1742, "Japan": 1761,
    "Canada": 1715, "Croatia": 1843, "Senegal": 1745,
}


def build_features(match: dict) -> np.ndarray:
    """
    Build the feature vector for one match.
    Must match the exact column order used when the model was trained.
    """
    elo_a   = match.get("elo_a") or _ELO_TABLE.get(match["team_a"], 1700)
    elo_b   = match.get("elo_b") or _ELO_TABLE.get(match["team_b"], 1700)
    rank_a  = match.get("rank_a") or _RANK_TABLE.get(match["team_a"], 30)
    rank_b  = match.get("rank_b") or _RANK_TABLE.get(match["team_b"], 30)

    stage_weight = {
        "GROUP_STAGE": 0, "Group A": 0, "Group B": 0, "Group C": 0,
        "Group D": 0, "Group E": 0, "Group F": 0, "Group G": 0, "Group H": 0,
        "R16": 1, "QF": 2, "SF": 3, "Final": 4,
    }.get(match.get("stage", "Group"), 0)

    return np.array([[
        elo_a - elo_b,        # elo_diff
        rank_b - rank_a,      # rank_diff  (lower rank = better)
        elo_a / 2000,         # form_a proxy
        elo_b / 2000,         # form_b proxy
        0.5,                  # h2h_wins_a (placeholder)
        0.5,                  # h2h_wins_b (placeholder)
        1.5,                  # avg_goals_a (placeholder)
        1.5,                  # avg_goals_b (placeholder)
        stage_weight / 4,     # stage_encoded
        1.0,                  # neutral_ground (WC always neutral)
        3.0 / 10,             # days_rest_a (placeholder)
        3.0 / 10,             # days_rest_b (placeholder)
    ]])


def _confidence(prob: float) -> str:
    if prob >= 0.65: return "High"
    if prob >= 0.52: return "Medium"
    return "Low"


# ─────────────────────────────────────────────────────────────────────────────
# Core refresh logic
# ─────────────────────────────────────────────────────────────────────────────

def _load_model_once():
    """Load model at startup; cache in _state."""
    try:
        bundle = load_model("latest")
        _state["_model"]       = bundle["model"]
        _state["model_version"] = bundle["version"]
        log.info(f"Model loaded: {bundle['version']}")
    except FileNotFoundError:
        log.warning("No saved model found — using random baseline predictions.")
        _state["_model"]       = None
        _state["model_version"] = "baseline-random"


def _predict(match: dict) -> tuple[float, float, float]:
    """
    Returns (prob_a_wins, prob_draw, prob_b_wins).
    Falls back to Elo-based heuristic when no trained model is available.
    """
    model = _state.get("_model")
    if model is not None:
        X = build_features(match)
        proba = model.predict_proba(X)[0]
        # Binary model: proba = [P(B wins), P(A wins)]
        p_a = float(proba[1])
        p_b = float(proba[0])
        p_draw = max(0.0, 1 - p_a - p_b) * 0.22   # inject small draw mass
        total = p_a + p_b + p_draw
        return p_a / total, p_draw / total, p_b / total

    # Elo-based fallback
    elo_a = _ELO_TABLE.get(match["team_a"], 1700)
    elo_b = _ELO_TABLE.get(match["team_b"], 1700)
    e_a   = 1 / (1 + 10 ** ((elo_b - elo_a) / 400))
    e_b   = 1 - e_a
    p_draw = 0.22
    p_a    = e_a * (1 - p_draw)
    p_b    = e_b * (1 - p_draw)
    return p_a, p_draw, p_b


def refresh_predictions() -> None:
    """Fetch latest matches, run predictions, update _state."""
    log.info("Refreshing match predictions …")
    try:
        raw_matches = fetch_upcoming_matches()
        results = []
        for m in raw_matches:
            p_a, p_draw, p_b = _predict(m)
            winner = m["team_a"] if p_a > p_b else m["team_b"]
            results.append(MatchPrediction(
                match_id   = m["id"],
                stage      = m["stage"],
                date       = m["date"],
                venue      = m["venue"],
                status     = m["status"],
                team_a = TeamPrediction(
                    name=m["team_a"], flag=_flag(m["team_a"]),
                    win_probability=round(p_a, 4),
                    elo=m.get("elo_a") or _ELO_TABLE.get(m["team_a"]),
                    fifa_rank=m.get("rank_a") or _RANK_TABLE.get(m["team_a"]),
                ),
                team_b = TeamPrediction(
                    name=m["team_b"], flag=_flag(m["team_b"]),
                    win_probability=round(p_b, 4),
                    elo=m.get("elo_b") or _ELO_TABLE.get(m["team_b"]),
                    fifa_rank=m.get("rank_b") or _RANK_TABLE.get(m["team_b"]),
                ),
                draw_probability   = round(p_draw, 4),
                predicted_winner   = winner,
                confidence         = _confidence(max(p_a, p_b)),
            ).model_dump())

        _state["matches"]      = results
        _state["last_refresh"] = datetime.now(timezone.utc).isoformat()
        _state["error"]        = None
        log.info(f"Refreshed {len(results)} matches.")

    except Exception as exc:
        log.error(f"Refresh failed: {exc}")
        _state["error"] = str(exc)


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="WC 2026 Predictor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    _load_model_once()
    refresh_predictions()          # immediate first load

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        refresh_predictions,
        trigger="interval",
        minutes=REFRESH_MINS,
        id="refresh",
    )
    scheduler.start()
    log.info(f"Scheduler running — refresh every {REFRESH_MINS} min.")


@app.get("/api/matches", response_model=list[MatchPrediction])
def get_matches(stage: str | None = None):
    matches = _state["matches"]
    if stage:
        matches = [m for m in matches if m["stage"].upper() == stage.upper()]
    return matches


@app.get("/api/matches/{match_id}", response_model=MatchPrediction)
def get_match(match_id: str):
    for m in _state["matches"]:
        if m["match_id"] == match_id:
            return m
    raise HTTPException(status_code=404, detail="Match not found")


@app.get("/api/refresh")
def manual_refresh(background_tasks: BackgroundTasks):
    background_tasks.add_task(refresh_predictions)
    return {"message": "Refresh triggered", "next_check": "~5 seconds"}


@app.get("/api/status", response_model=StatusResponse)
def get_status():
    return StatusResponse(
        last_refresh   = _state["last_refresh"],
        next_refresh_mins = REFRESH_MINS,
        model_version  = _state["model_version"],
        match_count    = len(_state["matches"]),
        error          = _state["error"],
    )


@app.get("/health")
def health():
    return {"status": "ok"}