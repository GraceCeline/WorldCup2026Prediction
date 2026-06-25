# app.py

import streamlit as st
from fetch_fixtures import get_upcoming_matches
from predictor import predict_match_full

st.set_page_config(page_title="World Cup 2026 Predictor", layout="centered")
st.title("🏆 World Cup 2026 — Match Predictor")

HOST_NATIONS = ["United States", "Mexico", "Canada"]

with st.spinner("Fetching upcoming fixtures..."):
    try:
        matches = get_upcoming_matches()
    except Exception as e:
        st.error(f"Could not fetch fixtures: {e}")
        matches = []

if not matches:
    st.info("No upcoming fixtures found.")
else:
    st.caption(f"{len(matches)} upcoming matches")

    for match in matches:
        home_team = match["homeTeam"]["name"]
        away_team = match["awayTeam"]["name"]
        match_date = match["utcDate"][:10]

        is_neutral = home_team not in HOST_NATIONS
        is_home_flag = 0 if is_neutral else 1

        with st.container(border=True):
            st.subheader(f"{home_team} vs {away_team}")
            st.caption(f"📅 {match_date}")

            try:
                result = predict_match_full(
                    home_team, away_team,
                    neutral=is_neutral, is_home=is_home_flag
                )

                col_ml, col_poisson = st.columns(2)

                with col_ml:
                    st.markdown("**Gradient Boosting**")
                    for label, pct in result["ml_probabilities"].items():
                        st.metric(label, f"{pct}%")

                with col_poisson:
                    st.markdown("**Poisson (xG-based)**")
                    p = result["poisson_probabilities"]
                    st.metric("Home win", f"{p['p_home_win']}%")
                    st.metric("Draw", f"{p['p_draw']}%")
                    st.metric("Away win", f"{p['p_away_win']}%")

                st.caption(
                    f"xG — {home_team}: {result['xg_home']} | {away_team}: {result['xg_away']} "
                    f"(goal diff: {result['expected_goal_difference']:+.2f})"
                )

            except ValueError as e:
                st.warning(f"Could not generate prediction: {e}")