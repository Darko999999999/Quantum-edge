from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime
import urllib.request
import urllib.parse
import json

app = FastAPI(title="Quantum Edge Web MVP")
DB_PATH = "quantum_edge.db"
SOFA_BASE = "https://www.sofascore.com/api/v1"

ALIASES = {
    "nicea": "Nice",
    "lens": "Lens",
    "rc lens": "Lens",
    "fiorentina": "Fiorentina",
    "atalanta": "Atalanta",
    "inter": "Inter",
    "inter mediolan": "Inter",
    "milan": "Milan",
    "ac milan": "Milan",
    "juventus": "Juventus",
    "roma": "Roma",
    "lazio": "Lazio",
    "napoli": "Napoli",
    "barcelona": "Barcelona",
    "real": "Real Madrid",
    "real madryt": "Real Madrid",
    "arsenal": "Arsenal",
    "chelsea": "Chelsea",
    "liverpool": "Liverpool",
    "manchester city": "Manchester City",
    "psg": "Paris Saint-Germain",
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
            pick TEXT,
            probability REAL,
            fair_odds REAL,
            bookmaker_odds REAL,
            value_edge REAL,
            exact_score TEXT,
            rating TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


def norm(txt):
    return (txt or "").lower().replace(" ", "").replace("-", "").replace(".", "").replace("_", "")


def fixed_name(txt):
    return ALIASES.get((txt or "").strip().lower(), (txt or "").strip())


def get_json(url):
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://www.sofascore.com/",
                "Origin": "https://www.sofascore.com",
            },
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.loads(response.read().decode("utf-8")), None
    except Exception as e:
        return None, str(e)


def recursive_find_teams(obj, wanted):
    found = []
    wanted_n = norm(wanted)

    if isinstance(obj, dict):
        for key in ["entity", "team"]:
            ent = obj.get(key)
            if isinstance(ent, dict) and "name" in ent and "id" in ent:
                name = ent.get("name", "")
                if wanted_n in norm(name) or norm(name) in wanted_n:
                    found.append(ent)

        if "name" in obj and "id" in obj:
            name = obj.get("name", "")
            if wanted_n in norm(name) or norm(name) in wanted_n:
                found.append(obj)

        for v in obj.values():
            found.extend(recursive_find_teams(v, wanted))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(recursive_find_teams(item, wanted))

    unique = []
    seen = set()
    for item in found:
        iid = item.get("id")
        name = item.get("name", "")
        if iid and iid not in seen:
            seen.add(iid)
            unique.append({"id": iid, "name": name})

    return unique


def search_team(team_name):
    q = fixed_name(team_name)
    urls = [
        SOFA_BASE + "/search/all?q=" + urllib.parse.quote(q),
        SOFA_BASE + "/search/teams?q=" + urllib.parse.quote(q),
    ]

    last_error = None
    for url in urls:
        data, err = get_json(url)
        if err:
            last_error = err
            continue

        teams = recursive_find_teams(data, q)
        if teams:
            return teams[0], None

    return None, last_error


def get_last_matches(team_id):
    url = SOFA_BASE + "/team/" + str(team_id) + "/events/last/0"
    data, err = get_json(url)

    if err or not data:
        return [], err

    matches = []
    goals_for = 0
    goals_against = 0
    points = 0
    count = 0

    for event in data.get("events", [])[:5]:
        home = event.get("homeTeam", {})
        away = event.get("awayTeam", {})
        home_score = event.get("homeScore", {}).get("current")
        away_score = event.get("awayScore", {}).get("current")

        if home_score is None or away_score is None:
            continue

        home_name = home.get("name", "")
        away_name = away.get("name", "")

        if home.get("id") == team_id:
            gf = home_score
            ga = away_score
        else:
            gf = away_score
            ga = home_score

        goals_for += gf
        goals_against += ga
        count += 1

        if gf > ga:
            points += 3
        elif gf == ga:
            points += 1

        matches.append(f"{home_name} {home_score}:{away_score} {away_name}")

    if count == 0:
        return [], None

    form = round((points / (count * 3)) * 100, 1)
    avg_gf = round(goals_for / count, 2)
    avg_ga = round(goals_against / count, 2)

    return {
        "matches": matches,
        "form": form,
        "avg_gf": avg_gf,
        "avg_ga": avg_ga,
    }, None


def fetch_stats(home_team, away_team):
    messages = []
    out = {
        "home_team": home_team,
        "away_team": away_team,
        "xg_home": 1.25,
        "xg_away": 0.95,
        "form_home": 60,
        "form_away": 55,
        "shots_home": 11,
        "shots_away": 10,
        "sot_home": 4,
        "sot_away": 3,
        "corners_home": 5,
        "corners_away": 4,
        "cards_home": 2,
        "cards_away": 2,
        "tempo": 50,
        "last_home": [],
        "last_away": [],
        "message": "",
    }

    h, err_h = search_team(home_team)
    a, err_a = search_team(away_team)

    if not h or not a:
        if err_h or err_a:
            messages.append("SofaScore zablokował pobieranie danych albo nie odpowiedział. Zostawiam wartości ręczne/proxy.")
        else:
            messages.append("Nie znaleziono jednej z drużyn. Zostawiam wartości ręczne/proxy.")

        out["message"] = " ".join(messages)
        return out

    out["home_team"] = h["name"]
    out["away_team"] = a["name"]

    home_form, err1 = get_last_matches(h["id"])
    away_form, err2 = get_last_matches(a["id"])

    if isinstance(home_form, dict):
        out["form_home"] = home_form["form"]
        out["last_home"] = home_form["matches"]

    if isinstance(away_form, dict):
        out["form_away"] = away_form["form"]
        out["last_away"] = away_form["matches"]

    if isinstance(home_form, dict) and isinstance(away_form, dict):
        out["xg_home"] = round((home_form["avg_gf"] * 0.65) + (away_form["avg_ga"] * 0.35), 2)
        out["xg_away"] = round((away_form["avg_gf"] * 0.65) + (home_form["avg_ga"] * 0.35), 2)
        messages.append("Pobrano drużyny i ostatnie mecze z SofaScore. xG jest proxy z ostatnich wyników.")
    else:
        messages.append("Drużyny znalezione, ale ostatnie mecze/statystyki nie zostały pobrane. Zostawiam proxy.")

    out["message"] = " ".join(messages)
    return out


def fair_odds(probability):
    return round(100 / probability, 2) if probability > 0 else 0


def value_edge(probability, odds):
    return round(probability - (100 / odds), 2) if odds > 1 else 0


def choose_pick(xg_home, xg_away, tempo, defensive_control, chaos):
    total_xg = xg_home + xg_away

    if total_xg <= 2.25 and tempo <= 55 and defensive_control >= 58 and chaos <= 55:
        return "Under 2.5 gola", "1:0 / 1:1 / 0:0"

    if total_xg <= 2.90 and tempo <= 62 and defensive_control >= 52:
        return "Under 3.5 gola", "1:1 / 2:1 / 1:0"

    if total_xg >= 2.75 and tempo >= 55 and chaos <= 62:
        return "Over 1.5 gola", "2:1 / 2:2 / 3:1"

    if xg_home >= xg_away:
        return "1X", "1:0 / 1:1 / 2:1"

    return "X2", "0:1 / 1:1 / 1:2"


def calculate_model(data):
    xg_home = data["xg_home"]
    xg_away = data["xg_away"]
    form_home = data["form_home"]
    form_away = data["form_away"]
    tempo = data["tempo"]
    shots_home = data["shots_home"]
    shots_away = data["shots_away"]
    sot_home = data["sot_home"]
    sot_away = data["sot_away"]
    corners_home = data["corners_home"]
    corners_away = data["corners_away"]
    cards_home = data["cards_home"]
    cards_away = data["cards_away"]
    defensive_control = data["defensive_control"]
    draw_acceptance = data["draw_acceptance"]
    collapse_home = data["collapse_home"]
    collapse_away = data["collapse_away"]
    absences = data["absences"]
    weather = data["weather"]
    market_risk = data["market_risk"]
    odds = data["odds"]

    total_xg = xg_home + xg_away
    shots_total = shots_home + shots_away
    sot_total = sot_home + sot_away
    corners_total = corners_home + corners_away
    cards_total = cards_home + cards_away

    chaos = round((tempo + collapse_home + collapse_away + absences + weather + market_risk) / 6, 1)

    stat_bonus = 0
    if shots_total >= 25:
        stat_bonus += 3
    if sot_total >= 9:
        stat_bonus += 3
    if corners_total >= 11:
        stat_bonus += 2
    if cards_total >= 5:
        stat_bonus += 1
    if shots_total <= 18 and sot_total <= 6:
        stat_bonus -= 3

    flow_bonus = 0
    if total_xg <= 2.35 and tempo <= 55 and defensive_control >= 58:
        flow_bonus = 5
    elif total_xg >= 2.8 and tempo >= 60:
        flow_bonus = 4

    probability = (
        ((form_home + form_away) / 2) * 0.16
        + defensive_control * 0.18
        + draw_acceptance * 0.06
        + (100 - chaos) * 0.28
        + (100 - absences) * 0.08
        + (100 - market_risk) * 0.08
        + 20
        + stat_bonus
        + flow_bonus
    )

    if chaos >= 65:
        probability -= 8
    if absences >= 65:
        probability -= 5

    probability = round(max(1, min(95, probability)), 1)
    fair = fair_odds(probability)
    edge = value_edge(probability, odds)
    pick, exact = choose_pick(xg_home, xg_away, tempo, defensive_control, chaos)

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
        "fair_odds": fair,
        "value_edge": edge,
        "chaos": chaos,
        "rating": rating,
        "total_xg": round(total_xg, 2),
        "shots_total": shots_total,
        "sot_total": sot_total,
        "corners_total": corners_total,
        "cards_total": cards_total,
    }


def default_values():
    return {
        "home_team": "",
        "away_team": "",
        "xg_home": 1.25,
        "xg_away": 0.95,
        "form_home": 60,
        "form_away": 55,
        "tempo": 50,
        "odds": 1.75,
        "shots_home": 11,
        "shots_away": 10,
        "sot_home": 4,
        "sot_away": 3,
        "corners_home": 5,
        "corners_away": 4,
        "cards_home": 2,
        "cards_away": 2,
        "defensive_control": 60,
        "draw_acceptance": 55,
        "collapse_home": 35,
        "collapse_away": 40,
        "absences": 25,
        "weather": 15,
        "market_risk": 25,
    }


def html_list(title, items):
    if not items:
        return ""
    lis = "".join([f"<li>{x}</li>" for x in items])
    return f"<div class='mini'><b>{title}</b><ul>{lis}</ul></div>"


def page(result=None, values=None, fetched=None, history=None):
    if values is None:
        values = default_values()

    result_html = ""
    if result:
        result_html = f"""
        <section class="card result">
            <div class="match">{values['home_team']} <span>vs</span> {values['away_team']}</div>
            <div class="grid-3">
                <div><small>Typ</small><strong>{result['pick']}</strong></div>
                <div><small>Probability</small><strong>{result['probability']}%</strong></div>
                <div><small>Value</small><strong>{result['value_edge']} pp</strong></div>
            </div>
            <div class="rating">{result['rating']}</div>
            <div class="stats">
                <div><span>Fair odds</span><b>{result['fair_odds']}</b></div>
                <div><span>Kurs</span><b>{values['odds']}</b></div>
                <div><span>Chaos risk</span><b>{result['chaos']}/100</b></div>
                <div><span>Exact score</span><b>{result['exact_score']}</b></div>
                <div><span>Suma xG</span><b>{result['total_xg']}</b></div>
                <div><span>Strzały</span><b>{result['shots_total']}</b></div>
                <div><span>Celne</span><b>{result['sot_total']}</b></div>
                <div><span>Rożne</span><b>{result['corners_total']}</b></div>
                <div><span>Kartki</span><b>{result['cards_total']}</b></div>
            </div>
        </section>
        """

    fetched_html = ""
    if fetched:
        fetched_html = f"""
        <section class="card">
            <h2>Dane pobrane</h2>
            <p>{fetched.get('message','')}</p>
            {html_list('Ostatnie mecze gospodarza', fetched.get('last_home', []))}
            {html_list('Ostatnie mecze gościa', fetched.get('last_away', []))}
        </section>
        """

    history_html = ""
    if history:
        rows = ""
        for r in history:
            rows += f"""
            <div class="history-row">
                <div><b>{r[2]} vs {r[3]}</b><small>{r[1]}</small></div>
                <div>{r[4]}</div>
                <div>{r[5]}%</div>
                <div>{r[8]} pp</div>
                <div>{r[10]}</div>
            </div>
            """
        history_html = f"<section class='card'><h2>Historia analiz</h2>{rows}</section>"

    v = values

    return f"""
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>Quantum Edge MVP</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
* {{ box-sizing: border-box; }}
body {{
    margin: 0;
    background: radial-gradient(circle at top, #0f2435 0%, #050912 55%, #03060c 100%);
    color: #f4f7fb;
    font-family: Arial, Helvetica, sans-serif;
}}
.app {{ max-width: 760px; margin: 0 auto; padding: 18px; }}
header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }}
.logo {{ font-size: 24px; font-weight: 800; letter-spacing: 1px; line-height: 1.1; }}
.logo span {{ color: #90ff36; display:block; }}
a {{ color: #90ff36; text-decoration: none; }}
.nav a {{ margin-left: 10px; border: 1px solid #30445b; padding: 8px 12px; border-radius: 12px; }}
.card {{
    background: rgba(12, 22, 36, 0.92);
    border: 1px solid #22344c;
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 16px;
    box-shadow: 0 14px 38px rgba(0,0,0,0.32);
}}
.hero h1 {{ margin: 8px 0; font-size: 26px; }}
.label {{ color: #90ff36; font-size: 13px; font-weight: bold; }}
.topline {{ display:flex; align-items:center; justify-content:space-between; gap:10px; }}
.fetch-mini {{
    width: 48px;
    height: 48px;
    border-radius: 50%;
    border: 1px solid rgba(144,255,54,0.45);
    background: rgba(144,255,54,0.10);
    color: #90ff36;
    font-size: 22px;
    font-weight: 900;
    margin: 0;
    padding: 0;
}}
.match {{ text-align: center; font-size: 22px; font-weight: bold; margin-bottom: 16px; }}
.match span {{ color: #91a0b5; font-size: 14px; margin: 0 10px; }}
.grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 16px; }}
.grid-3 div {{ background: #091221; border: 1px solid #22344c; border-radius: 14px; padding: 12px; }}
small {{ display: block; color: #98a7ba; margin-bottom: 6px; }}
strong {{ color: #90ff36; font-size: 22px; }}
.rating {{
    text-align: center;
    padding: 12px;
    border-radius: 14px;
    background: rgba(144,255,54,0.10);
    border: 1px solid rgba(144,255,54,0.35);
    color: #90ff36;
    font-weight: bold;
    margin-bottom: 14px;
}}
.stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
.stats div {{ display: flex; justify-content: space-between; background: #08111e; border-radius: 12px; padding: 10px; }}
.stats span {{ color: #98a7ba; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
label {{ display: flex; flex-direction: column; color: #cbd6e3; font-size: 14px; gap: 6px; }}
input {{
    width: 100%;
    padding: 12px;
    border-radius: 12px;
    border: 1px solid #2d4058;
    background: #07101d;
    color: white;
    font-size: 16px;
}}
button.main {{
    width: 100%;
    margin-top: 18px;
    padding: 15px;
    border: none;
    border-radius: 16px;
    background: #90ff36;
    color: #07101d;
    font-weight: 800;
    font-size: 17px;
}}
.history-row {{
    display: grid;
    grid-template-columns: 2fr 1.2fr 0.7fr 0.8fr 1fr;
    gap: 8px;
    padding: 12px 0;
    border-bottom: 1px solid #22344c;
    align-items: center;
}}
.mini {{ background:#08111e; padding:12px; border-radius:12px; margin-top:10px; }}
.mini ul {{ margin:8px 0 0 18px; padding:0; color:#cbd6e3; }}
@media (max-width: 560px) {{
    .app {{ padding: 14px; }}
    .two, .grid-3, .stats, .history-row {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<div class="app">
<header>
    <div class="logo">⚛ QUANTUM <span>EDGE</span></div>
    <div class="nav"><a href="/">Analiza</a><a href="/history">Historia</a></div>
</header>

<section class="card hero">
    <div class="label">ANALIZA MECZU</div>
    <h1>Quantum Edge Web MVP</h1>
    <p>Wpisz drużyny. Mała ikonka ⚡ próbuje pobrać statystyki z internetu, ale możesz też analizować ręcznie.</p>
</section>

{result_html}
{fetched_html}
{history_html}

<form action="/fetch" method="post" class="card">
    <div class="topline">
        <h2>Dane meczu</h2>
        <button class="fetch-mini" type="submit" title="Pobierz statystyki">⚡</button>
    </div>
    <div class="two">
        <label>Gospodarz<input name="home_team" required value="{v['home_team']}" placeholder="Lens"></label>
        <label>Gość<input name="away_team" required value="{v['away_team']}" placeholder="Nice"></label>
    </div>
</form>

<form action="/analyze" method="post" class="card">
    <input type="hidden" name="home_team" value="{v['home_team']}">
    <input type="hidden" name="away_team" value="{v['away_team']}">

    <h3>xG / forma</h3>
    <div class="two">
        <label>xG gospodarz<input type="number" step="0.01" name="xg_home" value="{v['xg_home']}"></label>
        <label>xG gość<input type="number" step="0.01" name="xg_away" value="{v['xg_away']}"></label>
        <label>Forma gospodarz<input type="number" step="1" name="form_home" value="{v['form_home']}"></label>
        <label>Forma gość<input type="number" step="1" name="form_away" value="{v['form_away']}"></label>
    </div>

    <h3>Statystyki</h3>
    <div class="two">
        <label>Tempo 0-100<input type="number" step="1" name="tempo" value="{v['tempo']}"></label>
        <label>Kurs bukmachera<input type="number" step="0.01" name="odds" value="{v['odds']}"></label>
        <label>Strzały gospodarz<input type="number" step="0.1" name="shots_home" value="{v['shots_home']}"></label>
        <label>Strzały gość<input type="number" step="0.1" name="shots_away" value="{v['shots_away']}"></label>
        <label>Celne gospodarz<input type="number" step="0.1" name="sot_home" value="{v['sot_home']}"></label>
        <label>Celne gość<input type="number" step="0.1" name="sot_away" value="{v['sot_away']}"></label>
        <label>Rożne gospodarz<input type="number" step="0.1" name="corners_home" value="{v['corners_home']}"></label>
        <label>Rożne gość<input type="number" step="0.1" name="corners_away" value="{v['corners_away']}"></label>
        <label>Kartki gospodarz<input type="number" step="0.1" name="cards_home" value="{v['cards_home']}"></label>
        <label>Kartki gość<input type="number" step="0.1" name="c
