from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime

app = FastAPI(title="Quantum Edge Web MVP")
DB_PATH = "quantum_edge.db"


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


@app.on_event("startup")
def startup():
    init_db()


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
        "cards_total": cards_total
    }


def page(result=None, history=None, home_team="", away_team="", odds=1.75):
    result_html = ""

    if result:
        result_html = f"""
        <section class="card result">
            <div class="match">{home_team} <span>vs</span> {away_team}</div>
            <div class="grid-3">
                <div><small>Typ</small><strong>{result['pick']}</strong></div>
                <div><small>Probability</small><strong>{result['probability']}%</strong></div>
                <div><small>Value</small><strong>{result['value_edge']} pp</strong></div>
            </div>
            <div class="rating">{result['rating']}</div>
            <div class="stats">
                <div><span>Fair odds</span><b>{result['fair_odds']}</b></div>
                <div><span>Kurs</span><b>{odds}</b></div>
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
.logo {{ font-size: 24px; font-weight: 800; letter-spacing: 1px; }}
.logo span {{ color: #90ff36; }}
a {{ color: #90ff36; text-decoration: none; }}
.nav a {{ margin-left: 12px; border: 1px solid #30445b; padding: 8px 12px; border-radius: 12px; }}
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
button {{
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
    <p>Wpisz dane meczu, a model policzy probability, value i exact score.</p>
</section>
{result_html}
{history_html}
<form action="/analyze" method="post" class="card">
    <h2>Dane meczu</h2>
    <div class="two">
        <label>Gospodarz<input name="home_team" required placeholder="Fiorentina"></label>
        <label>Gość<input name="away_team" required placeholder="Atalanta"></label>
    </div>
    <h3>xG / forma</h3>
    <div class="two">
        <label>xG gospodarz<input type="number" step="0.01" name="xg_home" value="1.25"></label>
        <label>xG gość<input type="number" step="0.01" name="xg_away" value="0.95"></label>
        <label>Forma gospodarz<input type="number" step="1" name="form_home" value="60"></label>
        <label>Forma gość<input type="number" step="1" name="form_away" value="55"></label>
    </div>
    <h3>Statystyki</h3>
    <div class="two">
        <label>Tempo 0-100<input type="number" step="1" name="tempo" value="50"></label>
        <label>Kurs bukmachera<input type="number" step="0.01" name="odds" value="1.75"></label>
        <label>Strzały gospodarz<input type="number" step="0.1" name="shots_home" value="11"></label>
        <label>Strzały gość<input type="number" step="0.1" name="shots_away" value="10"></label>
        <label>Celne gospodarz<input type="number" step="0.1" name="sot_home" value="4"></label>
        <label>Celne gość<input type="number" step="0.1" name="sot_away" value="3"></label>
        <label>Rożne gospodarz<input type="number" step="0.1" name="corners_home" value="5"></label>
        <label>Rożne gość<input type="number" step="0.1" name="corners_away" value="4"></label>
        <label>Kartki gospodarz<input type="number" step="0.1" name="cards_home" value="2"></label>
        <label>Kartki gość<input type="number" step="0.1" name="cards_away" value="2"></label>
    </div>
    <h3>Flow / ryzyko</h3>
    <div class="two">
        <label>Defensive control<input type="number" step="1" name="defensive_control" value="60"></label>
        <label>Akceptacja remisu<input type="number" step="1" name="draw_acceptance" value="55"></label>
        <label>Collapse gospodarz<input type="number" step="1" name="collapse_home" value="35"></label>
        <label>Collapse gość<input type="number" step="1" name="collapse_away" value="40"></label>
        <label>Absencje / rotacje<input type="number" step="1" name="absences" value="25"></label>
        <label>Pogoda<input type="number" step="1" name="weather" value="15"></label>
        <label>Rynek / kursy<input type="number" step="1" name="market_risk" value="25"></label>
    </div>
    <button type="submit">Analizuj mecz</button>
</form>
</div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return page()


@app.post("/analyze", response_class=HTMLResponse)
def analyze(
    home_team: str = Form(...),
    away_team: str = Form(...),
    xg_home: float = Form(1.25),
    xg_away: float = Form(0.95),
    form_home: float = Form(60),
    form_away: float = Form(55),
    tempo: float = Form(50),
    shots_home: float = Form(11),
    shots_away: float = Form(10),
    sot_home: float = Form(4),
    sot_away: float = Form(3),
    corners_home: float = Form(5),
    corners_away: float = Form(4),
    cards_home: float = Form(2),
    cards_away: float = Form(2),
    defensive_control: float = Form(60),
    draw_acceptance: float = Form(55),
    collapse_home: float = Form(35),
    collapse_away: float = Form(40),
    absences: float = Form(25),
    weather: float = Form(15),
    market_risk: float = Form(25),
    odds: float = Form(1.75)
):
    data = locals()
    result = calculate_model(data)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO analyses (
            created_at, home_team, away_team, pick, probability, fair_odds,
            bookmaker_odds, value_edge, exact_score, rating
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        home_team,
        away_team,
        result["pick"],
        result["probability"],
        result["fair_odds"],
        odds,
        result["value_edge"],
        result["exact_score"],
        result["rating"]
    ))
    conn.commit()
    conn.close()
    return page(result=result, home_team=home_team, away_team=away_team, odds=odds)


@app.get("/history", response_class=HTMLResponse)
def history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM analyses ORDER BY id DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return page(history=rows)
