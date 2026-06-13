class Elo:
    def expected_score(rating_diff):
        """Expected score (win probability) for team A against team B."""
        return 1 / (1 + 10 ** ((rating_diff) / 400))
    
    def update_elo(rating_a, rating_b, result, k=30, is_neutral=False):
        """
        result: 1 = A wins, 0.5 = draw, 0 = B wins
        k     : sensitivity — FIFA uses 30-60 depending on match importance
        
        Returns updated (rating_a, rating_b)
        """
        adj_a, adj_b = adjust_for_home(rating_a, rating_b, is_neutral)
    
        exp_a = expected_score(adj_a, adj_b)
        exp_b = 1 - exp_a
    
        new_a = rating_a + k * (result - exp_a)
        new_b = rating_b + k * ((1 - result) - exp_b)
    
        return round(new_a, 2), round(new_b, 2)
    
    def adjust_for_home(home_rating, away_rating, is_neutral=False):
        if is_neutral:
            return home_rating, away_rating
        return home_rating + 100, away_rating # FIFA rule
