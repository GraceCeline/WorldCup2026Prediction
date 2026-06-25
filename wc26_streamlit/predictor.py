import joblib
import pandas as pd
import numpy as np
from scipy.stats import poisson
from util import expected_goals, get_winrates, get_latest_elo

# Load once at import time (cached across reruns by Streamlit's @st.cache_resource in app.py)
model, feature_columns = load_model()
feature_columns = joblib.load("../models/feature_columns.pkl")
stats_df = pd.read_csv("../models/team_stats.csv")
FEATURES = [
    'home_team_home_winrate', 'home_team_away_winrate',
    'away_team_home_winrate', 'away_team_away_winrate',
    'elo_diff', 'form_score_diff', 'neutral', 'tournament_weight', 'is_home',
]

def build_features(home_team, away_team):
    home_elo_row = get_latest_elo(home_team)
    away_elo_row = get_latest_elo(away_team)
    is_home = 1 if home_team in HOST_NATIONS else 0
    neutral = 0 if home_team in HOST_NATIONS or away_team in HOST_NATIONS else 1

    elo_diff = home_elo_row["rating"] - away_elo_row["rating"]
    form_score_diff = home_elo_row["form_score"] - away_elo_row["form_score"]

    xg_home, xg_away = expected_goals(home_team, away_team, stats_df)
    goal_diff = np.abs(xg_home - xg_away)

    home_wr = get_winrates(home_team)
    away_wr = get_winrates(away_team)

    row = pd.DataFrame([{
        'elo_diff'              : elo_diff,
        'form_score_diff'       : form_score_diff,
        'neutral'               : int(neutral),
        'tournament_weight'     : TOURNAMENT_WEIGHT,
        'is_home'               : int(is_home),
        'xg_home'               : xg_home,
        'xg_away'               : xg_away,
        'home_team_home_winrate': home_wr["home_winrate"],
        'home_team_away_winrate': home_wr["away_winrate"],
        'away_team_home_winrate': away_wr["home_winrate"],
        'away_team_away_winrate': away_wr["away_winrate"],
    }])[FEATURES]

    return row

# ── test with your example match ──────────────────────────────────────────────
"""
match = {
    "home_team_name_en": "South Korea",
    "away_team_name_en": "Czech Republic",  # will need renaming to Czechia
    "finished"         : "FALSE",
    "type"             : "group"
}

# fix name if needed
if match['away_team_name_en'] == 'Czech Republic':
    match['away_team_name_en'] = 'Czechia'

result = predict_match(match, elo_filtered, wc_filtered, gb_model)
"""

def predict_match(home_team, away_team):
    X = build_features(home_team, away_team)

    proba = model.predict_proba(X)[0]
    classes = model.classes_

    return {
        "home_team": home_team,
        "away_team": away_team,
        "expected_goal_home": X['xg_home'],
        "expected_goal_away": X['xg_away'],
        "probabilities": {str(k): round(float(v), 3) for k, v in zip(classes, proba)},
        "predicted_class": classes[proba.argmax()],
    }