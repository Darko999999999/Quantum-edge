from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime
import urllib.request
import urllib.parse
import json
import csv
import io
import difflib
import re

app = FastAPI(title="Quantum Edge Web")
DB_PATH = "quantum_edge.db"

ODDS_API_KEY = "4235b3c48084bdd173789f88b6ddadfd"

SPORT_KEYS = [
    "soccer_epl",
    "soccer_england_championship",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_france_ligue_two",
    "soccer_netherlands_eredivisie",
    "soccer_portugal_primeira_liga",
    "soccer_scotland_premiership",
    "soccer_belgium_first_div",
    "soccer_austria_bundesliga",
    "soccer_turkey_super_league",
    "soccer_greece_super_league",
    "soccer_denmark_superliga",
    "soccer_sweden_allsvenskan",
    "soccer_norway_eliteserien",
    "soccer_switzerland_superleague",
    "soccer_poland_ekstraklasa",
    "soccer_uefa_champs_league",
    "soccer_uefa_europa_league",
    "soccer_uefa_europa_conference_league",
]

FOOTBALL_DATA_URLS = [
    "https://www.football-data.co.uk/mmz4281/2526/E0.csv",
    "https://www.football-data.co.uk/mmz4281/2526/E1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/SP1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/I1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/D1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/F1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/N1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/P1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/SC0.csv",
    "https://www.football-data.co.uk/mmz4281/2526/B1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/T1.csv",
]

UNDERSTAT_LEAGUES = [
    "EPL",
    "La_liga",
    "Serie_A",
    "Bundesliga",
    "Ligue_1",
]

POLISH_ALIASES = {
    "real madryt": "Real Madrid", "real": "Real Madrid",
    "atletico madryt": "Atletico Madrid", "atletico bilbao": "Athletic Bilbao",
    "athletic bilbao": "Athletic Bilbao", "barca": "Barcelona",
    "barcelona": "Barcelona", "betis": "Real Betis", "real betis": "Real Betis",
    "real sociedad": "Real Sociedad", "sevilla": "Sevilla", "walencja": "Valencia",
    "valencia": "Valencia", "villarreal": "Villarreal", "girona": "Girona",
    "osasuna": "Osasuna", "mallorca": "Mallorca", "celta": "Celta Vigo",

    "manchester city": "Manchester City", "man city": "Manchester City",
    "manchester united": "Manchester United", "man utd": "Manchester United",
    "arsenal": "Arsenal", "liverpool": "Liverpool", "chelsea": "Chelsea",
    "tottenham": "Tottenham Hotspur", "spurs": "Tottenham Hotspur",
    "newcastle": "Newcastle United", "aston villa": "Aston Villa",
    "west ham": "West Ham United", "brighton": "Brighton and Hove Albion",
    "everton": "Everton", "wolves": "Wolverhampton Wanderers",
    "wolverhampton": "Wolverhampton Wanderers", "leicester": "Leicester City",
    "crystal palace": "Crystal Palace", "nottingham": "Nottingham Forest",
    "bournemouth": "Bournemouth", "fulham": "Fulham",

    "inter": "Inter Milan", "inter mediolan": "Inter Milan",
    "ac milan": "AC Milan", "milan": "AC Milan", "juventus": "Juventus",
    "roma": "Roma", "lazio": "Lazio", "napoli": "Napoli",
    "atalanta": "Atalanta", "fiorentina": "Fiorentina", "bologna": "Bologna",
    "torino": "Torino", "udinese": "Udinese", "genoa": "Genoa",
    "verona": "Hellas Verona", "hellas verona": "Hellas Verona",
    "lecce": "Lecce", "sassuolo": "Sassuolo", "parma": "Parma",
    "cagliari": "Cagliari", "empoli": "Empoli",

    "bayern": "Bayern Munich", "bayern monachium": "Bayern Munich",
    "borussia dortmund": "Borussia Dortmund", "dortmund": "Borussia Dortmund",
    "rb lipsk": "RB Leipzig", "rb leipzig": "RB Leipzig", "leipzig": "RB Leipzig",
    "bayer leverkusen": "Bayer Leverkusen", "leverkusen": "Bayer Leverkusen",
    "eintracht": "Eintracht Frankfurt", "eintracht frankfurt": "Eintracht Frankfurt",
    "wolfsburg": "Wolfsburg", "stuttgart": "VfB Stuttgart",
    "union berlin": "Union Berlin", "freiburg": "SC Freiburg",
    "mainz": "Mainz", "werder": "Werder Bremen", "werder brema": "Werder Bremen",
    "hoffenheim": "Hoffenheim", "augsburg": "Augsburg",
    "gladbach": "Borussia Monchengladbach",

    "psg": "Paris Saint-Germain", "paris sg": "Paris Saint-Germain",
    "marsylia": "Marseille", "marseille": "Marseille",
    "lyon": "Lyon", "lens": "Lens", "rc lens": "Lens",
    "nice": "Nice", "nicea": "Nice", "ogc nice": "Nice",
    "monaco": "Monaco", "lille": "Lille", "rennes": "Rennes",
    "nantes": "Nantes", "strasbourg": "Strasbourg", "toulouse": "Toulouse",
    "montpellier": "Montpellier", "reims": "Reims", "brest": "Brest",

    "lech": "Lech Poznan", "lech poznan": "Lech Poznan", "lech poznań": "Lech Poznan",
    "legia": "Legia Warsaw", "legia warszawa": "Legia Warsaw",
    "rakow": "Rakow Czestochowa", "raków": "Rakow Czestochowa",
    "jagiellonia": "Jagiellonia Bialystok", "pogon": "Pogon Szczecin",
    "pogoń": "Pogon Szczecin", "slask": "Slask Wroclaw", "śląsk": "Slask Wroclaw",
    "widzew": "Widzew Lodz", "gornik": "Gornik Zabrze", "górnik": "Gornik Zabrze",
    "radomiak": "Radomiak Radom", "cracovia": "Cracovia", "piast": "Piast Gliwice",
    "zagłębie": "Zaglebie Lubin", "zaglebie": "Zaglebie Lubin",

    "ajax": "Ajax", "psv": "PSV Eindhoven", "feyenoord": "Feyenoord",
    "az alkmaar": "AZ Alkmaar", "twente": "Twente", "utrecht": "Utrecht",
    "benfica": "Benfica", "porto": "Porto", "fc porto": "Porto",
    "sporting": "Sporting CP", "sporting lizbona": "Sporting CP", "braga": "Braga",
    "celtic": "Celtic", "rangers": "Rangers", "galatasaray": "Galatasaray",
    "fenerbahce": "Fenerbahce", "besiktas": "Besiktas", "trabzonspor": "Trabzonspor",
    "club brugge": "Club Brugge", "anderlecht": "Anderlecht", "genk": "Genk",
    "gent": "Gent", "salzburg": "Red Bull Salzburg", "rb salzburg": "Red Bull Salzburg",
    "slavia praga": "Slavia Prague", "sparta praga": "Sparta Prague",
    "olympiacos": "Olympiacos", "paok": "PAOK", "aek": "AEK Athens",
    "szachtar": "Shakhtar Donetsk", "shakhtar": "Shakhtar Donetsk",
    "dynamo kijow": "Dynamo Kyiv", "dynamo kyiv": "Dynamo Kyiv",
    "kopenhaga": "FC Copenhagen", "fc copenhagen": "FC Copenhagen",
    "malmo": "Malmo FF", "mälmo": "Malmo FF", "bodo glimt": "Bodo/Glimt",
}


def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            home_team TEXT,
            away_team TEXT,
            pick TEXT,
            probability REAL,
            fair_odds REAL,
            bookmaker_odds REAL,
            value_edge REAL,
            exact_score TEXT,
            rating TEXT
        )
    """)
    con.commit()
    con.close()


init_db()


def esc(x):
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def norm(x):
    return (x or "").lower().replace(" ", "").replace("-", "").replace(".", "").replace("_", "").replace("'", "").replace("ą", "a").replace("ć", "c").replace("ę", "e").replace("ł", "l").replace("ń", "n").replace("ó", "o").replace("ś", "s").replace("ż", "z").replace("ź", "z")


def normalize_team_name(name):
    raw = (name or "").strip()
    key = raw.lower()
    key_clean = norm(raw)
    if key in POLISH_ALIASES:
        return POLISH_ALIASES[key]
    if key_clean in POLISH_ALIASES:
        return POLISH_ALIASES[key_clean]
    return raw


def match_team(api_name, user_name):
    a = norm(api_name)
    b = norm(normalize_team_name(user_name))
    if not a or not b:
        return False
    if b in a or a in b:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.62


def default_values():
    return {
        "home_team": "",
        "away_team": "",
        "city": "",
        "xg_home": 0,
        "xg_away": 0,
        "form_home": 0,
        "form_away": 0,
        "tempo": 0,
        "odds": 1.75,
        "odds_1": 0,
        "odds_x": 0,
        "odds_2": 0,
        "shots_home": 0,
        "shots_away": 0,
        "sot_home": 0,
        "sot_away": 0,
        "corners_home": 0,
        "corners_away": 0,
        "cards_home": 0,
        "cards_away": 0,
        "defensive_control": 60,
        "draw_acceptance": 55,
        "collapse_home": 35,
        "collapse_away": 40,
        "absences": 25,
        "weather": 15,
        "market_risk": 25,
        "bookmaker": "Rynek",
        "odds_source": "brak",
        "btts": 0,
        "over25": 0,
        "confidence": 0,
        "message": "",
        "sources": "",
        "last_home": "",
        "last_away": "",
        "home_home_matches": "",
        "home_away_matches": "",
        "away_home_matches": "",
        "away_away_matches": "",
    }



def current_values_from_form(**kwargs):
    v = default_values()
    for k, val in kwargs.items():
        if k in v:
            v[k] = val
    return v


STAT_KEYS = [
    "home_team", "away_team", "city",
    "xg_home", "xg_away", "form_home", "form_away", "tempo",
    "shots_home", "shots_away", "sot_home", "sot_away",
    "corners_home", "corners_away", "cards_home", "cards_away",
    "btts", "over25", "confidence", "message", "sources",
    "last_home", "last_away", "home_home_matches", "home_away_matches", "away_home_matches", "away_away_matches"
]

ODDS_KEYS = [
    "home_team", "away_team", "bookmaker",
    "odds", "odds_1", "odds_x", "odds_2",
    "odds_source", "message", "sources", "confidence"
]


def merge_section(base, update, keys):
    merged = dict(base)
    for k in keys:
        if k in update:
            merged[k] = update[k]
    return merged



def http_text(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/csv,text/plain,*/*"})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode("utf-8", errors="ignore"), None
    except Exception as e:
        return "", str(e)


def http_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8", errors="ignore")), None
    except Exception as e:
        return None, str(e)


def safe_float(x):
    try:
        if x in [None, ""]:
            return 0.0
        return float(str(x).replace(",", "."))
    except Exception:
        return 0.0


def safe_int(x):
    try:
        if x in [None, ""]:
            return None
        return int(float(str(x).replace(",", ".")))
    except Exception:
        return None


def row_has_team(row, team):
    return match_team(row.get("HomeTeam", ""), team) or match_team(row.get("AwayTeam", ""), team)


def team_side(row, team):
    if match_team(row.get("HomeTeam", ""), team):
        return "home"
    if match_team(row.get("AwayTeam", ""), team):
        return "away"
    return None



def understat_team_xg(home_team, away_team):
    """
    Pobiera sezonowe xG/xGA drużyn z Understat dla top 5 lig.
    Jeśli nie znajdzie danych, zwraca 0/0 — bez udawania.
    """
    result = {"xg_home": 0, "xg_away": 0, "source": ""}

    for league in UNDERSTAT_LEAGUES:
        url = "https://understat.com/league/" + league
        text, err = http_text(url)
        if err or not text:
            continue

        m = re.search(r"teamsData\\s*=\\s*JSON\\.parse\\('(.+?)'\\)", text)
        if not m:
            continue

        try:
            raw = m.group(1)
            raw = raw.encode("utf-8").decode("unicode_escape")
            data = json.loads(raw)
        except Exception:
            continue

        found_home = None
        found_away = None

        for _, team in data.items():
            title = team.get("title", "")
            history = team.get("history", [])
            if not history:
                continue

            xg_sum = 0
            xga_sum = 0
            n = 0
            for item in history[-5:]:
                xg_sum += safe_float(item.get("xG"))
                xga_sum += safe_float(item.get("xGA"))
                n += 1

            if n == 0:
                continue

            avg_xg = round(xg_sum / n, 2)
            avg_xga = round(xga_sum / n, 2)

            if match_team(title, home_team):
                found_home = {"team": title, "xg": avg_xg, "xga": avg_xga}
            if match_team(title, away_team):
                found_away = {"team": title, "xg": avg_xg, "xga": avg_xga}

        if found_home or found_away:
            if found_home:
                result["xg_home"] = found_home["xg"]
            if found_away:
                result["xg_away"] = found_away["xg"]
            result["source"] = "Understat " + league
            return result

    return result


def team_home_away_matches(rows, team):
    home_matches = []
    away_matches = []

    for r in rows:
        if safe_int(r.get("FTHG")) is None or safe_int(r.get("FTAG")) is None:
            continue

        ht = r.get("HomeTeam", "")
        at = r.get("AwayTeam", "")
        hg = safe_int(r.get("FTHG")) or 0
        ag = safe_int(r.get("FTAG")) or 0

        if match_team(ht, team):
            home_matches.append(f"{ht} {hg}:{ag} {at}")
        elif match_team(at, team):
            away_matches.append(f"{ht} {hg}:{ag} {at}")

    return {
        "home": " | ".join(home_matches[-5:]),
        "away": " | ".join(away_matches[-5:]),
    }



def load_football_data_rows(home_team, away_team):
    for url in FOOTBALL_DATA_URLS:
        text, err = http_text(url)
        if err or not text:
            continue
        try:
            rows = list(csv.DictReader(io.StringIO(text)))
        except Exception:
            continue
        if any(row_has_team(r, home_team) or row_has_team(r, away_team) for r in rows if r.get("HomeTeam")):
            return rows, url.split("/")[-1]
    return [], ""


def team_stats_from_rows(rows, team):
    completed = []
    for r in rows:
        if not row_has_team(r, team):
            continue
        if safe_int(r.get("FTHG")) is None or safe_int(r.get("FTAG")) is None:
            continue
        completed.append(r)

    completed = completed[-5:]
    if not completed:
        return None

    pts = 0
    gf = 0
    ga = 0
    shots = 0
    sot = 0
    corners = 0
    cards = 0
    matches = []

    for r in completed:
        side = team_side(r, team)
        hg = safe_int(r.get("FTHG")) or 0
        ag = safe_int(r.get("FTAG")) or 0

        if side == "home":
            own, opp = hg, ag
            shots += safe_float(r.get("HS"))
            sot += safe_float(r.get("HST"))
            corners += safe_float(r.get("HC"))
            cards += safe_float(r.get("HY"))
        else:
            own, opp = ag, hg
            shots += safe_float(r.get("AS"))
            sot += safe_float(r.get("AST"))
            corners += safe_float(r.get("AC"))
            cards += safe_float(r.get("AY"))

        gf += own
        ga += opp
        if own > opp:
            pts += 3
        elif own == opp:
            pts += 1

        matches.append(f"{r.get('HomeTeam','')} {hg}:{ag} {r.get('AwayTeam','')}")

    n = len(completed)
    return {
        "form": round((pts / (n * 3)) * 100, 1),
        "gf": round(gf / n, 2),
        "ga": round(ga / n, 2),
        "shots": round(shots / n, 1),
        "sot": round(sot / n, 1),
        "corners": round(corners / n, 1),
        "cards": round(cards / n, 1),
        "matches": matches,
    }


def calculate_real_stats(home_team, away_team, city=""):
    v = default_values()
    home = normalize_team_name(home_team)
    away = normalize_team_name(away_team)
    v["home_team"] = home
    v["away_team"] = away
    v["city"] = city

    rows, source = load_football_data_rows(home, away)
    messages = []

    if not rows:
        v["message"] = "Nie pobrano realnych statystyk. Brak meczu/drużyn w dostępnych plikach Football-Data."
        v["sources"] = "brak realnych danych"
        return v

    h = team_stats_from_rows(rows, home)
    a = team_stats_from_rows(rows, away)

    if h:
        v["form_home"] = h["form"]
        v["shots_home"] = h["shots"]
        v["sot_home"] = h["sot"]
        v["corners_home"] = h["corners"]
        v["cards_home"] = h["cards"]
        v["last_home"] = " | ".join(h["matches"])
        messages.append("pobrano ostatnie mecze gospodarza")
    else:
        messages.append("brak statystyk gospodarza")

    if a:
        v["form_away"] = a["form"]
        v["shots_away"] = a["shots"]
        v["sot_away"] = a["sot"]
        v["corners_away"] = a["corners"]
        v["cards_away"] = a["cards"]
        v["last_away"] = " | ".join(a["matches"])
        messages.append("pobrano ostatnie mecze gościa")
    else:
        messages.append("brak statystyk gościa")

    # Football-Data nie ma xG, więc próbujemy Understat. Jeśli brak danych, zostaje 0.
    uxg = understat_team_xg(home, away)
    v["xg_home"] = uxg.get("xg_home", 0)
    v["xg_away"] = uxg.get("xg_away", 0)

    splits_home = team_home_away_matches(rows, home)
    splits_away = team_home_away_matches(rows, away)
    v["home_home_matches"] = splits_home["home"]
    v["home_away_matches"] = splits_home["away"]
    v["away_home_matches"] = splits_away["home"]
    v["away_away_matches"] = splits_away["away"]

    total_shots = float(v["shots_home"]) + float(v["shots_away"])
    total_sot = float(v["sot_home"]) + float(v["sot_away"])

    if total_shots >= 25 or total_sot >= 9:
        v["tempo"] = 62
    elif total_shots > 0:
        v["tempo"] = 43
    else:
        v["tempo"] = 0

    if h and a:
        avg_goals = h["gf"] + a["gf"]
        v["over25"] = round(max(20, min(80, 35 + avg_goals * 10)), 1)
        v["btts"] = round(max(20, min(80, 38 + (h["gf"] + a["gf"]) * 8 - abs(h["ga"] - a["ga"]) * 3)), 1)
        v["confidence"] = 70
    else:
        v["confidence"] = 35

    if v["xg_home"] or v["xg_away"]:
        v["message"] = "Realne statystyki pobrane z Football-Data + xG z Understat."
    else:
        v["message"] = "Realne statystyki pobrane z Football-Data. xG zostaje 0, bo Understat nie znalazł tej drużyny/ligi."
    extra_xg = (" | " + uxg.get("source", "")) if uxg.get("source") else ""
    v["sources"] = "Football-Data " + source + extra_xg + " | " + ", ".join(messages)
    return v


def get_best_h2h_from_event(event, bookmaker_filter="Rynek"):
    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        return None

    home_team = event.get("home_team", "")
    away_team = event.get("away_team", "")
    candidates = []

    for book in bookmakers:
        if bookmaker_filter and bookmaker_filter.lower() not in ["rynek", "market", ""]:
            title = (book.get("title") or "").lower()
            key = (book.get("key") or "").lower()
            target = bookmaker_filter.lower()
            if target not in title and target not in key:
                continue

        for market in book.get("markets", []):
            if market.get("key") != "h2h":
                continue
            o = {"home": None, "draw": None, "away": None}
            for out in market.get("outcomes", []):
                name = out.get("name", "")
                price = out.get("price")
                if price is None:
                    continue
                if name == home_team:
                    o["home"] = float(price)
                elif name == away_team:
                    o["away"] = float(price)
                elif name.lower() == "draw":
                    o["draw"] = float(price)
            if o["home"] and o["draw"] and o["away"]:
                candidates.append({"home": o["home"], "draw": o["draw"], "away": o["away"], "bookmaker": book.get("title") or book.get("key")})

    if not candidates:
        return None

    if bookmaker_filter.lower() in ["rynek", "market", ""]:
        return {
            "home": round(max(c["home"] for c in candidates), 2),
            "draw": round(max(c["draw"] for c in candidates), 2),
            "away": round(max(c["away"] for c in candidates), 2),
            "bookmaker": "Najlepszy rynek / The Odds API",
        }

    c = candidates[0]
    return {
        "home": round(c["home"], 2),
        "draw": round(c["draw"], 2),
        "away": round(c["away"], 2),
        "bookmaker": c["bookmaker"] + " / The Odds API",
    }


def fetch_odds_api(home_team, away_team, bookmaker):
    home = normalize_team_name(home_team)
    away = normalize_team_name(away_team)

    last_error = ""
    for sport_key in SPORT_KEYS:
        url = "https://api.the-odds-api.com/v4/sports/" + sport_key + "/odds/?" + urllib.parse.urlencode({
            "apiKey": ODDS_API_KEY,
            "regions": "eu,uk",
            "markets": "h2h",
            "oddsFormat": "decimal",
        })
        data, err = http_json(url)
        if err:
            last_error = err
            continue
        if not isinstance(data, list):
            continue

        for event in data:
            api_home = event.get("home_team", "")
            api_away = event.get("away_team", "")
            direct = match_team(api_home, home) and match_team(api_away, away)
            reverse = match_team(api_home, away) and match_team(api_away, home)
            if not direct and not reverse:
                continue

            odds = get_best_h2h_from_event(event, bookmaker)
            if not odds:
                continue

            if reverse:
                odds["home"], odds["away"] = odds["away"], odds["home"]

            return {
                "ok": True,
                "odds_1": odds["home"],
                "odds_x": odds["draw"],
                "odds_2": odds["away"],
                "source": odds["bookmaker"],
                "sport_key": sport_key,
                "api_home": api_home,
                "api_away": api_away,
            }

    return {"ok": False, "error": last_error or "Nie znaleziono meczu/kursów w The Odds API."}


def fetch_odds(home_team, away_team, bookmaker):
    v = default_values()
    v["home_team"] = normalize_team_name(home_team)
    v["away_team"] = normalize_team_name(away_team)
    v["bookmaker"] = bookmaker

    res = fetch_odds_api(home_team, away_team, bookmaker)

    if res.get("ok"):
        v["odds_1"] = res["odds_1"]
        v["odds_x"] = res["odds_x"]
        v["odds_2"] = res["odds_2"]
        v["odds"] = res["odds_1"]
        v["odds_source"] = res["source"]
        v["message"] = "Kursy pobrane z The Odds API. Dopasowany mecz: " + res.get("api_home", "") + " vs " + res.get("api_away", "")
        v["sources"] = res["source"] + " | " + res.get("sport_key", "")
        v["confidence"] = 78
        return v

    v["message"] = "Nie pobrano kursów: " + res.get("error", "")
    v["odds_source"] = "brak"
    v["sources"] = "The Odds API"
    return v


def fair_odds(probability):
    return round(100 / probability, 2) if probability > 0 else 0


def value_edge(probability, odds):
    return round(probability - (100 / odds), 2) if odds > 1 else 0


def choose_pick(xh, xa, tempo, dc, chaos):
    total = xh + xa
    if total and total <= 2.25 and tempo <= 55 and dc >= 58 and chaos <= 55:
        return "Under 2.5 gola", "1:0 / 1:1 / 0:0"
    if total and total <= 2.90 and tempo <= 62 and dc >= 52:
        return "Under 3.5 gola", "1:1 / 2:1 / 1:0"
    if total and total >= 2.75 and tempo >= 55 and chaos <= 62:
        return "Over 1.5 gola", "2:1 / 2:2 / 3:1"
    if xh >= xa:
        return "1X", "1:0 / 1:1 / 2:1"
    return "X2", "0:1 / 1:1 / 1:2"


def calculate_model(v):
    xh = float(v["xg_home"])
    xa = float(v["xg_away"])
    fh = float(v["form_home"])
    fa = float(v["form_away"])
    tempo = float(v["tempo"])
    odds = float(v["odds"])
    dc = float(v["defensive_control"])
    draw = float(v["draw_acceptance"])
    ch = float(v["collapse_home"])
    ca = float(v["collapse_away"])
    absn = float(v["absences"])
    weather = float(v["weather"])
    market = float(v["market_risk"])

    shots = float(v["shots_home"]) + float(v["shots_away"])
    sot = float(v["sot_home"]) + float(v["sot_away"])
    corners = float(v["corners_home"]) + float(v["corners_away"])
    cards = float(v["cards_home"]) + float(v["cards_away"])

    chaos = round((tempo + ch + ca + absn + weather + market) / 6, 1)

    stat_bonus = 0
    if shots >= 25:
        stat_bonus += 3
    if sot >= 9:
        stat_bonus += 3
    if corners >= 11:
        stat_bonus += 2
    if cards >= 5:
        stat_bonus += 1

    probability = ((fh + fa) / 2) * 0.16 + dc * 0.18 + draw * 0.06 + (100 - chaos) * 0.28 + (100 - absn) * 0.08 + (100 - market) * 0.08 + 20 + stat_bonus
    probability = round(max(1, min(95, probability)), 1)

    pick, exact = choose_pick(xh, xa, tempo, dc, chaos)
    edge = value_edge(probability, odds)

    if edge > 5 and probability >= 60 and chaos <= 45:
        rating = "TOP VALUE"
    elif edge > 2 and probability >= 60 and chaos <= 55:
        rating = "MOCNY TYP"
    elif edge > 0 and probability >= 57:
        rating = "LEKKIE VALUE"
    else:
        rating = "BRAK VALUE"

    return {
        "pick": pick,
        "exact_score": exact,
        "probability": probability,
        "fair_odds": fair_odds(probability),
        "value_edge": edge,
        "chaos": chaos,
        "rating": rating,
        "total_xg": round(xh + xa, 2),
        "shots_total": round(shots, 1),
        "sot_total": round(sot, 1),
        "corners_total": round(corners, 1),
        "cards_total": round(cards, 1),
    }



def clamp(value, low=0, high=100):
    try:
        value = float(value)
    except Exception:
        value = 0
    return max(low, min(high, value))


def flow_engine(v):
    xg_total = float(v.get("xg_home", 0) or 0) + float(v.get("xg_away", 0) or 0)
    shots_total = float(v.get("shots_home", 0) or 0) + float(v.get("shots_away", 0) or 0)
    sot_total = float(v.get("sot_home", 0) or 0) + float(v.get("sot_away", 0) or 0)
    corners_total = float(v.get("corners_home", 0) or 0) + float(v.get("corners_away", 0) or 0)
    cards_total = float(v.get("cards_home", 0) or 0) + float(v.get("cards_away", 0) or 0)
    tempo = float(v.get("tempo", 0) or 0)
    defensive = float(v.get("defensive_control", 60) or 60)
    ch = float(v.get("collapse_home", 35) or 35)
    ca = float(v.get("collapse_away", 40) or 40)

    if xg_total > 0:
        attack = clamp(xg_total * 23 + sot_total * 3)
    else:
        attack = clamp(shots_total * 2.2 + sot_total * 4)

    control = clamp(72 - tempo * 0.45 - cards_total * 2 + defensive * 0.35)
    chaos = clamp(tempo * 0.45 + cards_total * 5 + corners_total * 1.6 + ch * 0.15 + ca * 0.15)
    collapse = clamp((ch + ca) / 2 + cards_total * 3 + tempo * 0.12)
    draw_accept = clamp(float(v.get("draw_acceptance", 55) or 55) + (8 if xg_total and xg_total <= 2.2 else 0) - (8 if chaos > 65 else 0))
    transition = clamp(attack * 0.45 + tempo * 0.35 + corners_total * 1.5)

    if control >= 62 and chaos <= 55:
        label = "CONTROL FLOW"
        note = "Mecz wygląda stabilnie: większa szansa na kontrolowany wynik i niższą wariancję."
    elif chaos >= 65:
        label = "CHAOS FLOW"
        note = "Wysoka zmienność: ryzyko szybkiej zmiany wyniku, transition football i bramek po momentum."
    else:
        label = "BALANCED FLOW"
        note = "Mecz pośredni: możliwy scenariusz kontrolowany, ale z ryzykiem faz chaosu."

    return {"control": round(control, 1), "chaos": round(chaos, 1), "collapse": round(collapse, 1), "draw": round(draw_accept, 1), "transition": round(transition, 1), "attack": round(attack, 1), "label": label, "note": note}


def exact_score_engine(v, flow):
    xh = float(v.get("xg_home", 0) or 0)
    xa = float(v.get("xg_away", 0) or 0)
    control = flow["control"]
    chaos = flow["chaos"]
    draw = flow["draw"]

    if xh == 0 and xa == 0:
        sh = float(v.get("shots_home", 0) or 0)
        sa = float(v.get("shots_away", 0) or 0)
        if abs(sh - sa) <= 2 and draw >= 55:
            return {"control": "1:1", "value": "1:0 / 0:1", "chaos": "2:2", "note": "Brak xG — wynik oparty na strzałach, tempie i flow."}
        if sh >= sa:
            return {"control": "1:0", "value": "2:1", "chaos": "2:2 / 3:2", "note": "Brak xG — przewaga gospodarza liczona ze statystyk."}
        return {"control": "0:1", "value": "1:2", "chaos": "2:2 / 2:3", "note": "Brak xG — przewaga gościa liczona ze statystyk."}

    total = xh + xa
    diff = xh - xa

    if control >= 62 and chaos <= 55:
        if total <= 2.1 and abs(diff) < 0.35:
            control_score = "0:0 / 1:1"
        elif diff >= 0.35:
            control_score = "1:0"
        elif diff <= -0.35:
            control_score = "0:1"
        else:
            control_score = "1:1"
    else:
        control_score = "1:1"

    if diff >= 0.45:
        value_score = "2:1"
    elif diff <= -0.45:
        value_score = "1:2"
    elif total >= 2.7:
        value_score = "2:2"
    else:
        value_score = "1:1"

    if chaos >= 65:
        chaos_score = "2:2 / 3:2 / 2:3"
    elif diff >= 0.5:
        chaos_score = "2:1 / 3:1"
    elif diff <= -0.5:
        chaos_score = "1:2 / 1:3"
    else:
        chaos_score = "2:2"

    return {"control": control_score, "value": value_score, "chaos": chaos_score, "note": "Wyniki liczone z xG, tempa, chaosu i przewagi matchupowej."}


def team_profiles(v, flow):
    fh = float(v.get("form_home", 0) or 0)
    fa = float(v.get("form_away", 0) or 0)
    sh = float(v.get("shots_home", 0) or 0)
    sa = float(v.get("shots_away", 0) or 0)
    ch = float(v.get("collapse_home", 35) or 35)
    ca = float(v.get("collapse_away", 40) or 40)

    def profile(form, shots, collapse):
        if collapse >= 60:
            return "Collapse Team"
        if flow["chaos"] >= 65 and shots >= 11:
            return "Chaos / Transition Team"
        if form >= 60 and flow["control"] >= 58:
            return "Control Team"
        if shots <= 9 and form < 50:
            return "Reactive Team"
        return "Balanced Team"

    return {"home": profile(fh, sh, ch), "away": profile(fa, sa, ca)}


def market_engine(v, result=None):
    odds = float(v.get("odds", 0) or 0)
    fair = result.get("fair_odds", 0) if result else 0
    prob = result.get("probability", 0) if result else 0
    edge = result.get("value_edge", 0) if result else 0

    if odds <= 1:
        return {"label": "NO ODDS", "note": "Brak kursu do oceny value.", "edge": 0, "fair": fair, "prob": prob}

    if edge >= 5:
        label = "VALUE FOUND"
        note = "Kurs rynkowy jest wyraźnie wyższy niż fair odds modelu."
    elif edge > 0:
        label = "SMALL VALUE"
        note = "Jest lekkie value, ale wymaga kontroli ryzyka i rynku."
    else:
        label = "NO VALUE"
        note = "Brak przewagi kursowej względem prawdopodobieństwa modelu."

    return {"label": label, "note": note, "edge": edge, "fair": fair, "prob": prob}


def bar(label, value, css=""):
    value = clamp(value)
    return f'<div class="barrow"><div class="barlabel">{esc(label)} <b>{value:.1f}%</b></div><div class="bar"><span class="{css}" style="width:{value}%"></span></div></div>'


def intelligence_dashboard(v, result=None):
    flow = flow_engine(v)
    scores = exact_score_engine(v, flow)
    profiles = team_profiles(v, flow)
    market = market_engine(v, result)

    html = '<section class="card dashboard-card">'
    html += '<h2>🔥 Quantum Flow Engine</h2>'
    html += f'<div class="flow-label">{esc(flow["label"])}</div>'
    html += f'<p>{esc(flow["note"])}</p>'
    html += bar("Control Flow", flow["control"], "good")
    html += bar("Chaos Risk", flow["chaos"], "bad")
    html += bar("Collapse Risk", flow["collapse"], "warn")
    html += bar("Draw Acceptance", flow["draw"], "good")
    html += bar("Transition Advantage", flow["transition"], "warn")
    html += '</section>'

    html += '<section class="card dashboard-card">'
    html += '<h2>⚽ Exact Score Engine</h2>'
    html += '<div class="score-grid">'
    html += f'<div><small>CONTROL</small><strong>{esc(scores["control"])}</strong></div>'
    html += f'<div><small>VALUE</small><strong>{esc(scores["value"])}</strong></div>'
    html += f'<div><small>CHAOS</small><strong>{esc(scores["chaos"])}</strong></div>'
    html += '</div>'
    html += f'<p>{esc(scores["note"])}</p>'
    html += '</section>'

    html += '<section class="card dashboard-card">'
    html += '<h2>📈 Market Intelligence</h2>'
    html += f'<div class="flow-label market">{esc(market["label"])}</div>'
    html += f'<p>{esc(market["note"])}</p>'
    html += '<div class="stats">'
    html += f'<div><span>Model probability</span><b>{market.get("prob", 0)}%</b></div>'
    html += f'<div><span>Fair odds</span><b>{market.get("fair", 0)}</b></div>'
    html += f'<div><span>Market odds</span><b>{v.get("odds", 0)}</b></div>'
    html += f'<div><span>Value edge</span><b>{market.get("edge", 0)} pp</b></div>'
    html += '</div></section>'

    html += '<section class="card dashboard-card">'
    html += '<h2>🧠 Team Profiles</h2>'
    html += '<div class="score-grid">'
    html += f'<div><small>{esc(v.get("home_team","Gospodarz"))}</small><strong>{esc(profiles["home"])}</strong></div>'
    html += f'<div><small>{esc(v.get("away_team","Gość"))}</small><strong>{esc(profiles["away"])}</strong></div>'
    html += '</div>'
    html += '</section>'

    return html


def mini_stats(v):
    html = '<div class="stats">'
    html += f'<div><span>xG</span><b>{v["xg_home"]} - {v["xg_away"]}</b></div>'
    html += f'<div><span>Forma</span><b>{v["form_home"]} - {v["form_away"]}</b></div>'
    html += f'<div><span>Kursy 1X2</span><b>{v["odds_1"]} / {v["odds_x"]} / {v["odds_2"]}</b></div>'
    html += f'<div><span>Źródło kursu</span><b>{esc(v["odds_source"])}</b></div>'
    html += f'<div><span>Strzały</span><b>{v["shots_home"]} - {v["shots_away"]}</b></div>'
    html += f'<div><span>Celne</span><b>{v["sot_home"]} - {v["sot_away"]}</b></div>'
    html += f'<div><span>Rożne</span><b>{v["corners_home"]} - {v["corners_away"]}</b></div>'
    html += f'<div><span>Kartki</span><b>{v["cards_home"]} - {v["cards_away"]}</b></div>'
    html += f'<div><span>BTTS</span><b>{v["btts"]}%</b></div>'
    html += f'<div><span>Over 2.5</span><b>{v["over25"]}%</b></div>'
    html += f'<div><span>Confidence</span><b>{v["confidence"]}%</b></div>'
    html += f'<div><span>Tempo</span><b>{v["tempo"]}/100</b></div>'
    html += '</div>'
    html += '<div class="match-grid">'
    html += '<div class="mini"><b>Gospodarz — u siebie</b><p>' + esc(v.get("home_home_matches", "") or "brak danych") + '</p></div>'
    html += '<div class="mini"><b>Gospodarz — wyjazd</b><p>' + esc(v.get("home_away_matches", "") or "brak danych") + '</p></div>'
    html += '<div class="mini"><b>Gość — u siebie</b><p>' + esc(v.get("away_home_matches", "") or "brak danych") + '</p></div>'
    html += '<div class="mini"><b>Gość — wyjazd</b><p>' + esc(v.get("away_away_matches", "") or "brak danych") + '</p></div>'
    html += '</div>'
    return html


def result_box(result, v):
    if not result:
        return ""
    html = '<section class="card">'
    html += f'<div class="match">{esc(v["home_team"])} <span>vs</span> {esc(v["away_team"])}</div>'
    html += '<div class="grid-3">'
    html += f'<div><small>Typ</small><strong>{esc(result["pick"])}</strong></div>'
    html += f'<div><small>Probability</small><strong>{result["probability"]}%</strong></div>'
    html += f'<div><small>Value</small><strong>{result["value_edge"]} pp</strong></div>'
    html += '</div>'
    html += f'<div class="rating">{esc(result["rating"])}</div>'
    html += '<div class="stats">'
    html += f'<div><span>Fair odds</span><b>{result["fair_odds"]}</b></div>'
    html += f'<div><span>Kurs modelu</span><b>{v["odds"]}</b></div>'
    html += f'<div><span>Chaos risk</span><b>{result["chaos"]}/100</b></div>'
    html += f'<div><span>Exact score</span><b>{esc(result["exact_score"])}</b></div>'
    html += f'<div><span>Suma xG</span><b>{result["total_xg"]}</b></div>'
    html += f'<div><span>Strzały</span><b>{result["shots_total"]}</b></div>'
    html += f'<div><span>Celne</span><b>{result["sot_total"]}</b></div>'
    html += f'<div><span>Rożne</span><b>{result["corners_total"]}</b></div>'
    html += f'<div><span>Kartki</span><b>{result["cards_total"]}</b></div>'
    html += '</div></section>'
    return html


def fetched_box(v):
    if not v.get("message"):
        return ""
    return '<section class="card"><h2>Dane pobrane / uzupełnione</h2><p>' + esc(v["message"]) + '</p><p><b>Źródło:</b> ' + esc(v["sources"]) + '</p>' + mini_stats(v) + '</section>'


def history_box(rows):
    if not rows:
        return ""
    out = '<section class="card"><h2>Historia analiz</h2>'
    for row in rows:
        out += '<div class="history-row">'
        out += f'<div><b>{esc(row[2])} vs {esc(row[3])}</b><small>{esc(row[1])}</small></div>'
        out += f'<div>{esc(row[4])}</div><div>{row[5]}%</div><div>{row[8]} pp</div><div>{esc(row[10])}</div>'
        out += '</div>'
    return out + '</section>'


def page(v=None, result=None, history_rows=None):
    if v is None:
        v = default_values()

    css = """
    <style>
    *{box-sizing:border-box}
    body{margin:0;background:radial-gradient(circle at top,#0f2435 0%,#050912 55%,#03060c 100%);color:#f4f7fb;font-family:Arial,Helvetica,sans-serif}
    .app{max-width:850px;margin:0 auto;padding:18px}
    header{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}
    .logo{font-size:24px;font-weight:800;letter-spacing:1px;line-height:1.1}
    .logo span{color:#90ff36;display:block}
    a{color:#90ff36;text-decoration:none}
    .nav a{margin-left:10px;border:1px solid #30445b;padding:8px 12px;border-radius:12px}
    .card{background:rgba(12,22,36,.92);border:1px solid #22344c;border-radius:18px;padding:18px;margin-bottom:16px;box-shadow:0 14px 38px rgba(0,0,0,.32)}
    .hero h1{margin:8px 0;font-size:26px}
    .label{color:#90ff36;font-size:13px;font-weight:bold}
    .topline{display:flex;align-items:center;justify-content:space-between;gap:10px}
    .iconbar{display:flex;gap:12px}
    .roundbtn{width:58px;height:58px;border-radius:50%;border:1px solid rgba(144,255,54,.45);background:rgba(144,255,54,.10);color:#90ff36;font-size:25px;font-weight:900;margin:0;padding:0}
    .money{color:#b566ff;border-color:rgba(181,102,255,.55);background:rgba(181,102,255,.10)}
    .match{text-align:center;font-size:22px;font-weight:bold;margin-bottom:16px}
    .match span{color:#91a0b5;font-size:14px;margin:0 10px}
    .grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:16px}
    .grid-3 div{background:#091221;border:1px solid #22344c;border-radius:14px;padding:12px}
    small{display:block;color:#98a7ba;margin-bottom:6px}
    strong{color:#90ff36;font-size:22px}
    .rating{text-align:center;padding:12px;border-radius:14px;background:rgba(144,255,54,.10);border:1px solid rgba(144,255,54,.35);color:#90ff36;font-weight:bold;margin-bottom:14px}
    .stats{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
    .stats div{display:flex;justify-content:space-between;background:#08111e;border-radius:12px;padding:10px;gap:8px}
    .stats span{color:#98a7ba}
    .two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    label{display:flex;flex-direction:column;color:#cbd6e3;font-size:14px;gap:6px}
    input,select{width:100%;padding:12px;border-radius:12px;border:1px solid #2d4058;background:#07101d;color:white;font-size:16px}
    button.main{width:100%;margin-top:18px;padding:15px;border:none;border-radius:16px;background:#90ff36;color:#07101d;font-weight:800;font-size:17px}
    .history-row{display:grid;grid-template-columns:2fr 1.2fr .7fr .8fr 1fr;gap:8px;padding:12px 0;border-bottom:1px solid #22344c;align-items:center}
    .mini{background:#08111e;padding:12px;border-radius:12px;margin-top:10px}
    .mini p{color:#cbd6e3;font-size:13px;line-height:1.5}
    .match-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
    .dashboard-card{border-color:rgba(144,255,54,.25)}
    .flow-label{display:inline-block;padding:10px 14px;border-radius:14px;background:rgba(144,255,54,.12);border:1px solid rgba(144,255,54,.35);color:#90ff36;font-weight:800;margin-bottom:8px}
    .flow-label.market{color:#b566ff;border-color:rgba(181,102,255,.45);background:rgba(181,102,255,.12)}
    .barrow{margin:12px 0}.barlabel{display:flex;justify-content:space-between;color:#cbd6e3;font-size:14px;margin-bottom:5px}.bar{height:12px;background:#07101d;border-radius:20px;overflow:hidden;border:1px solid #22344c}.bar span{display:block;height:100%;background:#90ff36;border-radius:20px}.bar span.bad{background:#ff4d4d}.bar span.warn{background:#ffd24d}.bar span.good{background:#90ff36}
    .score-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:10px}.score-grid div{background:#08111e;border:1px solid #22344c;border-radius:14px;padding:12px}.score-grid strong{font-size:18px}
    @media(max-width:560px){.app{padding:14px}.two,.grid-3,.stats,.history-row,.match-grid,.score-grid{grid-template-columns:1fr}}
    </style>
    """

    html = '<!DOCTYPE html><html lang="pl"><head><meta charset="UTF-8"><title>Quantum Edge</title><meta name="viewport" content="width=device-width, initial-scale=1.0">' + css + '</head><body><div class="app">'
    html += '<header><div class="logo">⚛ QUANTUM <span>EDGE</span></div><div class="nav"><a href="/">Analiza</a><a href="/history">Historia</a></div></header>'
    html += '<section class="card hero"><div class="label">REAL DATA ENGINE</div><h1>Quantum Edge Web MVP</h1><p>⚡ pobiera realne statystyki z Football-Data. Jeśli brak danych, nie wpisuje fake/proxy. 💰 pobiera kursy z The Odds API.</p></section>'
    html += result_box(result, v)
    html += intelligence_dashboard(v, result)
    html += fetched_box(v)
    html += history_box(history_rows)

    html += '<form action="/fetch" method="post" class="card"><div class="topline"><h2>Dane meczu</h2><div class="iconbar"><button class="roundbtn" name="mode" value="stats" type="submit">⚡</button><button class="roundbtn money" name="mode" value="odds" type="submit">💰</button></div></div>'
    html += '<div class="two">'
    html += f'<label>Gospodarz<input name="home_team" required value="{esc(v["home_team"])}" placeholder="Real Madryt"></label>'
    html += f'<label>Gość<input name="away_team" required value="{esc(v["away_team"])}" placeholder="Atletico Bilbao"></label>'
    html += f'<label>Miasto meczu / pogoda<input name="city" value="{esc(v["city"])}" placeholder="Madryt"></label>'
    html += '<label>Źródło / bukmacher<select name="bookmaker"><option>Rynek</option><option>bet365</option><option>Betfair</option><option>Unibet</option><option>William Hill</option><option>STS</option><option>Betclic</option><option>Fortuna</option><option>Superbet</option></select></label>'
    hidden_keys = ["xg_home","xg_away","form_home","form_away","tempo","odds","odds_1","odds_x","odds_2","shots_home","shots_away","sot_home","sot_away","corners_home","corners_away","cards_home","cards_away","defensive_control","draw_acceptance","collapse_home","collapse_away","absences","weather","market_risk","btts","over25","confidence","odds_source","last_home","last_away","home_home_matches","home_away_matches","away_home_matches","away_away_matches"]
    for hk in hidden_keys:
        html += f'<input type="hidden" name="{hk}" value="{esc(v.get(hk, ""))}">'
    html += '</div></form>'

    html += '<form action="/analyze" method="post" class="card">'
    html += f'<input type="hidden" name="home_team" value="{esc(v["home_team"])}"><input type="hidden" name="away_team" value="{esc(v["away_team"])}">'

    def inp(label, name, step="0.01"):
        return f'<label>{label}<input type="number" step="{step}" name="{name}" value="{v[name]}"></label>'

    html += '<h3>xG / forma</h3><div class="two">' + inp("xG gospodarz", "xg_home") + inp("xG gość", "xg_away") + inp("Forma gospodarz", "form_home", "1") + inp("Forma gość", "form_away", "1") + '</div>'
    html += '<h3>Kursy</h3><div class="two">' + inp("Główny kurs do modelu", "odds") + inp("Kurs 1", "odds_1") + inp("Kurs X", "odds_x") + inp("Kurs 2", "odds_2") + '</div>'
    html += '<h3>Statystyki</h3><div class="two">' + inp("Tempo 0-100", "tempo", "1") + inp("Strzały gospodarz", "shots_home", "0.1") + inp("Strzały gość", "shots_away", "0.1") + inp("Celne gospodarz", "sot_home", "0.1") + inp("Celne gość", "sot_away", "0.1") + inp("Rożne gospodarz", "corners_home", "0.1") + inp("Rożne gość", "corners_away", "0.1") + inp("Kartki gospodarz", "cards_home", "0.1") + inp("Kartki gość", "cards_away", "0.1") + '</div>'
    html += '<h3>Flow / ryzyko</h3><div class="two">' + inp("Defensive control", "defensive_control", "1") + inp("Akceptacja remisu", "draw_acceptance", "1") + inp("Collapse gospodarz", "collapse_home", "1") + inp("Collapse gość", "collapse_away", "1") + inp("Absencje / rotacje", "absences", "1") + inp("Pogoda", "weather", "1") + inp("Rynek / kursy", "market_risk", "1") + '</div>'
    html += '<button class="main" type="submit">Analizuj mecz</button></form>'
    html += '</div></body></html>'
    return html


@app.get("/", response_class=HTMLResponse)
def home():
    return page()


@app.post("/fetch", response_class=HTMLResponse)
def fetch(
    home_team: str = Form(...),
    away_team: str = Form(...),
    city: str = Form(""),
    bookmaker: str = Form("Rynek"),
    mode: str = Form("stats"),
    xg_home: float = Form(0),
    xg_away: float = Form(0),
    form_home: float = Form(0),
    form_away: float = Form(0),
    tempo: float = Form(0),
    odds: float = Form(1.75),
    odds_1: float = Form(0),
    odds_x: float = Form(0),
    odds_2: float = Form(0),
    shots_home: float = Form(0),
    shots_away: float = Form(0),
    sot_home: float = Form(0),
    sot_away: float = Form(0),
    corners_home: float = Form(0),
    corners_away: float = Form(0),
    cards_home: float = Form(0),
    cards_away: float = Form(0),
    defensive_control: float = Form(60),
    draw_acceptance: float = Form(55),
    collapse_home: float = Form(35),
    collapse_away: float = Form(40),
    absences: float = Form(25),
    weather: float = Form(15),
    market_risk: float = Form(25),
    btts: float = Form(0),
    over25: float = Form(0),
    confidence: float = Form(0),
    odds_source: str = Form("brak"),
    last_home: str = Form(""),
    last_away: str = Form(""),
    home_home_matches: str = Form(""),
    home_away_matches: str = Form(""),
    away_home_matches: str = Form(""),
    away_away_matches: str = Form(""),
):
    current = current_values_from_form(**locals())

    if mode == "odds":
        update = fetch_odds(home_team, away_team, bookmaker)
        v = merge_section(current, update, ODDS_KEYS)
    else:
        update = calculate_real_stats(home_team, away_team, city)
        v = merge_section(current, update, STAT_KEYS)

    # Zachowaj nazwę bukmachera po każdym kliknięciu.
    v["bookmaker"] = bookmaker
    return page(v=v)


@app.post("/analyze", response_class=HTMLResponse)
def analyze(
    home_team: str = Form(...),
    away_team: str = Form(...),
    xg_home: float = Form(0),
    xg_away: float = Form(0),
    form_home: float = Form(0),
    form_away: float = Form(0),
    tempo: float = Form(0),
    odds: float = Form(1.75),
    odds_1: float = Form(0),
    odds_x: float = Form(0),
    odds_2: float = Form(0),
    shots_home: float = Form(0),
    shots_away: float = Form(0),
    sot_home: float = Form(0),
    sot_away: float = Form(0),
    corners_home: float = Form(0),
    corners_away: float = Form(0),
    cards_home: float = Form(0),
    cards_away: float = Form(0),
    defensive_control: float = Form(60),
    draw_acceptance: float = Form(55),
    collapse_home: float = Form(35),
    collapse_away: float = Form(40),
    absences: float = Form(25),
    weather: float = Form(15),
    market_risk: float = Form(25),
):
    v = default_values()
    data = locals()
    for k in v:
        if k in data:
            v[k] = data[k]

    result = calculate_model(v)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO analyses (created_at, home_team, away_team, pick, probability, fair_odds, bookmaker_odds, value_edge, exact_score, rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M"), home_team, away_team, result["pick"], result["probability"], result["fair_odds"], odds, result["value_edge"], result["exact_score"], result["rating"]),
    )
    con.commit()
    con.close()

    return page(v=v, result=result)


@app.get("/history", response_class=HTMLResponse)
def history():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT * FROM analyses ORDER BY id DESC LIMIT 50")
    rows = cur.fetchall()
    con.close()
    return page(history_rows=rows)
