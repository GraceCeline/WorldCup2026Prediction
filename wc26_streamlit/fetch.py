import requests
import streamlit as st

API_BASE = "https://api.football-data.org/v4"

def get_upcoming_matches(competition_code="WC"):
    headers = {"X-Auth-Token": st.secrets["FOOTBALL_DATA_API_KEY"]}
    url = f"{API_BASE}/competitions/{competition_code}/matches?status=SCHEDULED"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["matches"]