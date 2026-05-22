from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
from datetime import datetime

app = FastAPI(title="Quantum Edge Web MVP")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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


def fair_odds(probability):
    if probability <= 0:
        return 0
    return round(100 / probability, 2)


def value_edge(probability, odds):
    if odds <= 1:
        return 0
    return round(probability - (100 / odds), 2)


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
        rating = "🔥 TOP VALUE"
    elif edge > 2 and probability >= 60 and chaos <= 55:
        rating = "✅ MOCNY TYP"
    elif edge > 0 and probability >= 57:
        rating = "⚠️ LEKKIE VALUE"
    else:
        rating = "❌ BRAK VALUE"

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


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "result": None})


@app.post("/analyze", response_class=HTMLResponse)
def analyze(
    request: Request,
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

    return templates.TemplateResponse("index.html", {
        "request": request,
        "result": result,
        "home_team": home_team,
        "away_team": away_team,
        "odds": odds
    })


@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM analyses ORDER BY id DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()

    return templates.TemplateResponse("history.html", {"request": request, "rows": rows})
