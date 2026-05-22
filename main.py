from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime
import urllib.request
import urllib.parse
import json
import re

app = FastAPI(title="Quantum Edge Web MVP")

DB_PATH = "quantum_edge.db"

SOFA_BASE = "https://www.sofascore.com/api/v1"

ALIASES = {
    "nicea": "Nice",
    "lens": "Lens",
    "rc lens": "Lens",
    "fiorentina": "Fiorentina",
    "atalanta": "Atalanta",
    "inter mediolan": "Inter",
    "inter": "Inter",
    "milan": "Milan",
    "juventus": "Juventus",
    "roma": "Roma",
    "napoli": "Napoli",
    "barcelona": "Barcelona",
    "real madryt": "Real Madrid",
    "real": "Real Madrid",
    "arsenal": "Arsenal",
    "chelsea": "Chelsea",
    "liverpool": "Liverpool",
    "manchester city": "Manchester City",
    "psg": "Paris Saint-Germain"
}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            home_team TEXT,
            away_team TEXT,
            result TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


def normalize_team(name):
    name = name.strip().lower()

    if name in ALIASES:
        return ALIASES[name]

    return name.title()


def api_get(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def search_team(team_name):
    query = urllib.parse.quote(team_name)

    url = f"{SOFA_BASE}/search/all/{query}"

    data = api_get(url)

    teams = []

    for item in data.get("results", []):
        entity = item.get("entity", {})

        if entity.get("type") == "team":
            teams.append({
                "id": entity.get("id"),
                "name": entity.get("name")
            })

    return teams


def get_last_matches(team_id):
    url = f"{SOFA_BASE}/team/{team_id}/events/last/5"

    data = api_get(url)

    matches = []

    for event in data.get("events", []):
        home = event["homeTeam"]["name"]
        away = event["awayTeam"]["name"]

        home_score = event.get("homeScore", {}).get("current", 0)
        away_score = event.get("awayScore", {}).get("current", 0)

        matches.append(
            f"{home} {home_score}:{away_score} {away}"
        )

    return matches


def simple_probability(xg_home, xg_away):
    total = xg_home + xg_away

    if total <= 2:
        return "UNDER FLOW"

    if total <= 3:
        return "BALANCED"

    return "OVER FLOW"


def exact_score(xg_home, xg_away):
    total = xg_home + xg_away

    if total <= 1.8:
        return "1:0"

    if total <= 2.4:
        return "1:1"

    if total <= 3:
        return "2:1"

    return "3:1"


@app.get("/", response_class=HTMLResponse)
def home():

    html = """
    <html>
    <head>
        <title>Quantum Edge</title>

        <style>

        body{
            background:#07111f;
            color:white;
            font-family:Arial;
            padding:20px;
        }

        .box{
            background:#0d1b2e;
            padding:20px;
            border-radius:18px;
            margin-bottom:20px;
        }

        input{
            width:100%;
            padding:14px;
            border-radius:12px;
            border:none;
            margin-top:8px;
            margin-bottom:14px;
            background:#101d33;
            color:white;
            font-size:16px;
        }

        button{
            width:100%;
            padding:16px;
            border:none;
            border-radius:14px;
            background:#5cff5c;
            font-size:18px;
            font-weight:bold;
        }

        h1{
            color:#7cff4f;
        }

        </style>

    </head>

    <body>

        <h1>QUANTUM EDGE</h1>

        <div class="box">

            <h2>Pobieranie statystyk</h2>

            <form action="/fetch" method="post">

                <label>Gospodarz</label>
                <input name="home_team" placeholder="Lens">

                <label>Gość</label>
                <input name="away_team" placeholder="Nice">

                <button type="submit">
                    Pobierz statystyki
                </button>

            </form>

        </div>

    </body>
    </html>
    """

    return html


@app.post("/fetch", response_class=HTMLResponse)
def fetch(
    home_team: str = Form(...),
    away_team: str = Form(...)
):

    try:

        home_team = normalize_team(home_team)
        away_team = normalize_team(away_team)

        home_search = search_team(home_team)
        away_search = search_team(away_team)

        if not home_search or not away_search:
            return "<h1>Nie znaleziono drużyn</h1>"

        home_id = home_search[0]["id"]
        away_id = away_search[0]["id"]

        home_matches = get_last_matches(home_id)
        away_matches = get_last_matches(away_id)

        xg_home = round(1.1 + len(home_matches) * 0.08, 2)
        xg_away = round(0.9 + len(away_matches) * 0.07, 2)

        flow = simple_probability(xg_home, xg_away)
        score = exact_score(xg_home, xg_away)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            INSERT INTO analyses (
                created_at,
                home_team,
                away_team,
                result
            )
            VALUES (?, ?, ?, ?)
        """, (
            str(datetime.now()),
            home_team,
            away_team,
            score
        ))

        conn.commit()
        conn.close()

        html = f"""
        <html>
        <head>

        <style>

        body{{
            background:#07111f;
            color:white;
            font-family:Arial;
            padding:20px;
        }}

        .box{{
            background:#0d1b2e;
            padding:20px;
            border-radius:18px;
            margin-bottom:20px;
        }}

        h1{{
            color:#7cff4f;
        }}

        li{{
            margin-bottom:10px;
        }}

        </style>

        </head>

        <body>

        <h1>{home_team} vs {away_team}</h1>

        <div class="box">

            <h2>Model</h2>

            <p><b>Flow:</b> {flow}</p>
            <p><b>Exact score:</b> {score}</p>
            <p><b>xG:</b> {xg_home} - {xg_away}</p>

        </div>

        <div class="box">

            <h2>Ostatnie mecze gospodarza</h2>

            <ul>
                {''.join([f"<li>{m}</li>" for m in home_matches])}
            </ul>

        </div>

        <div class="box">

            <h2>Ostatnie mecze gości</h2>

            <ul>
                {''.join([f"<li>{m}</li>" for m in away_matches])}
            </ul>

        </div>

        </body>
        </html>
        """

        return html

    except Exception as e:
        return f"<h1>Błąd:</h1><pre>{str(e)}</pre>"
