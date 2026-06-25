from scipy.stats import poisson

class Poisson:
    def team_stats(team, df):
        home_matches = df[df['home_team'] == team].dropna(subset=['home_score', 'away_score'])
        away_matches = df[df['away_team'] == team].dropna(subset=['home_score', 'away_score'])
    
        home_played = len(home_matches)
        away_played = len(away_matches)
    
        attack_home  = (home_matches['home_score'].sum() / home_played) / avg_home_scored if home_played else 1.0
        attack_away  = (away_matches['away_score'].sum() / away_played) / avg_away_scored if away_played else 1.0
    
        defense_home = (home_matches['away_score'].sum() / home_played) / avg_home_conceded if home_played else 1.0
        defense_away = (away_matches['home_score'].sum() / away_played) / avg_away_conceded if away_played else 1.0
    
        return {
            'team': team,
            'attack_home':   round(attack_home,  3),
            'attack_away':   round(attack_away,  3),
            'defense_home':  round(defense_home, 3),
            'defense_away':  round(defense_away, 3),
            'home_played':   home_played,
            'away_played':   away_played,
        }

    def expected_goals(home_team, away_team, df):
        h = team_stats(home_team, df)
        a = team_stats(away_team, df)
    
        # Expected goals = attack strength × opponent defense weakness × league avg
        xg_home = h['attack_home'] * a['defense_away'] * avg_home_scored
        xg_away = a['attack_away'] * h['defense_home'] * avg_away_scored
    
        return round(xg_home, 3), round(xg_away, 3)
    
    # xg_h, xg_a = expected_goals('Brazil', 'Germany', wc_filtered)
    # print(f"Expected goals — Brazil (home): {xg_h}  |  Germany (away): {xg_a}")

    def match_probabilities(home_team, away_team, df, max_goals=10):
        xg_h, xg_a = expected_goals(home_team, away_team, df)
    
        # Probability matrix for each scoreline
        prob_matrix = np.outer(
            [poisson.pmf(i, xg_h) for i in range(max_goals)],
            [poisson.pmf(i, xg_a) for i in range(max_goals)]
        )
    
        p_home_win = np.tril(prob_matrix, -1).sum()  # home scores more
        p_away_win = np.triu(prob_matrix,  1).sum()  # away scores more
        p_draw     = np.trace(prob_matrix)
    
        return {
            'home_team'   : home_team,
            'away_team'   : away_team,
            'xg_home'     : xg_h,
            'xg_away'     : xg_a,
            'p_home_win'  : round(p_home_win, 3),
            'p_draw'      : round(p_draw,     3),
            'p_away_win'  : round(p_away_win, 3),
        }
    
    result = match_probabilities('Brazil', 'Germany', wc_filtered)
    print(pd.Series(result).to_string())

# ── 5. Run for multiple fixtures ──────────────────────────────────────────────
"""
fixtures = [
    ('Brazil',    'Germany'),
    ('France',    'Argentina'),
    ('Spain',     'England'),
    ('Portugal',  'Netherlands'),
]

predictions = pd.DataFrame([match_probabilities(h, a, wc_filtered) for h, a in fixtures])
print(predictions.to_string(index=False))
"""