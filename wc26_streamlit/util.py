import pandas as pd
import numpy as np
from scipy.stats import poisson
import joblib

wc_filtered = pd.read_csv("../models/elo_ratings.csv")
elo_df = pd.read_csv("../models/elo_snapshot.csv")
elo_df = elo_df["year" == 2026]
avg_elo = elo_df["rating"].sum() / len(elo_df)
stats_df = pd.read_csv("../models/team_stats.csv")
HOST_NATIONS     = ['United States', 'Canada', 'Mexico']
TOURNAMENT_WEIGHT = 5

def expected_goals(home_team, away_team, stats_df):
    h = team_stats(home_team, stats_df)
    a = team_stats(away_team, stats_df)

    # Expected goals = attack strength × opponent defense weakness × league avg
    xg_home = h['attack_home'] * a['defense_away'] * avg_home_scored
    xg_away = a['attack_away'] * h['defense_home'] * avg_away_scored

    return round(xg_home, 3), round(xg_away, 3)

def match_probabilities_neutral(team_a, team_b, df, max_goals=10):
    xg_a, xg_b = expected_goals_neutral(team_a, team_b, df)

    prob_matrix = np.outer(
        [poisson.pmf(i, xg_a) for i in range(max_goals)],
        [poisson.pmf(i, xg_b) for i in range(max_goals)]
    )

    p_a_win = np.tril(prob_matrix, -1).sum()
    p_b_win = np.triu(prob_matrix,  1).sum()
    p_draw  = np.trace(prob_matrix)

    return {
        'team_a'   : team_a,
        'team_b'   : team_b,
        'xg_a'     : xg_a,
        'xg_b'     : xg_b,
        'p_a_win'  : round(p_a_win, 3),
        'p_draw'   : round(p_draw,  3),
        'p_b_win'  : round(p_b_win, 3),
    }

def get_winrates(country):
    rows = elo_df[elo_df["country"] == country]
    if rows.empty:
        raise ValueError(f"No winrate data found for {team_name}")
    return rows.iloc[0]

def get_latest_elo(country):
    rows = elo_df[elo_df["country"] == country]
    if rows.empty:
        raise ValueError(f"No Elo data found for {country}")
    return rows.sort_values("year").iloc[-1]

def load_model():
    return joblib.load("models/match_outcome_model.pkl"), joblib.load("models/feature_columns.pkl")