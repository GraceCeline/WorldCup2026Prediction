class MatchSimulator:
    def __init__(self, teams, team_ratings):
        self.teams = teams # List of string of countries
        self.team_ratings = team_ratings
        
    def simulate_knockout_match(self, team1, team2):
        """Simulate a single match"""
        rating1 = self.team_ratings[team1]
        rating2 = self.team_ratings[team2]
        
        win_prob_team1 = 1 / (1 + 10 ** ((rating2 - rating1) / 400))
        
        if stage in ["Quarterfinal", "Semifinal", "Final"]:
            pressure_factor = np.random.normal(0, 0.15)
            win_prob_team1 += pressure_factor
        
        win_prob_team1 = max(0.2, min(0.8, win_prob_team1))
        
        if np.random.random() < win_prob_team1:
            winner = team1
            loser = team2
        else:
            winner = team2
            loser = team1
        
        if abs(rating1 - rating2) < 50 and stage != "Round of 32":
            if np.random.random() < 0.25:  
                pass
        
        return winner, loser, win_prob_team1