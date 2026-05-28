from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
import requests, csv, io, sqlite3, json, os, time, hashlib, difflib
from datetime import datetime

app = FastAPI(title="Quantum Edge v34")

DB_PATH = "quantum_edge.db"
CACHE_DIR = "qe_cache"
CACHE_TTL = 60 * 60 * 12
os.makedirs(CACHE_DIR, exist_ok=True)

# Ligi dostępne do wyboru.
# Football-Data działa stabilnie głównie dla top lig i części 2 lig.
# Niższe ligi bez stabilnego CSV zostają jako widoczne opcje do dalszej integracji API.
LEAGUES = {
    "auto": {"country": "AUTO", "tier": "AUTO", "name": "AUTO - wyszukaj", "url": ""},

    "england_premier": {"country": "England", "tier": "1", "name": "Premier League", "url": "https://www.football-data.co.uk/mmz4281/2526/E0.csv"},
    "england_championship": {"country": "England", "tier": "2", "name": "Championship", "url": "https://www.football-data.co.uk/mmz4281/2526/E1.csv"},
    "england_league_one": {"country": "England", "tier": "3", "name": "League One", "url": "https://www.football-data.co.uk/mmz4281/2526/E2.csv"},
    "england_league_two": {"country": "England", "tier": "4", "name": "League Two", "url": "https://www.football-data.co.uk/mmz4281/2526/E3.csv"},

    "spain_laliga": {"country": "Spain", "tier": "1", "name": "La Liga", "url": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv"},
    "spain_laliga2": {"country": "Spain", "tier": "2", "name": "La Liga 2", "url": "https://www.football-data.co.uk/mmz4281/2526/SP2.csv"},
    "spain_primera_rfef": {"country": "Spain", "tier": "3", "name": "Primera RFEF", "url": ""},

    "italy_serie_a": {"country": "Italy", "tier": "1", "name": "Serie A", "url": "https://www.football-data.co.uk/mmz4281/2526/I1.csv"},
    "italy_serie_b": {"country": "Italy", "tier": "2", "name": "Serie B", "url": "https://www.football-data.co.uk/mmz4281/2526/I2.csv"},
    "italy_serie_c": {"country": "Italy", "tier": "3", "name": "Serie C", "url": ""},

    "germany_bundesliga": {"country": "Germany", "tier": "1", "name": "Bundesliga", "url": "https://www.football-data.co.uk/mmz4281/2526/D1.csv"},
    "germany_bundesliga2": {"country": "Germany", "tier": "2", "name": "2. Bundesliga", "url": "https://www.football-data.co.uk/mmz4281/2526/D2.csv"},
    "germany_3liga": {"country": "Germany", "tier": "3", "name": "3. Liga", "url": ""},

    "france_ligue1": {"country": "France", "tier": "1", "name": "Ligue 1", "url": "https://www.football-data.co.uk/mmz4281/2526/F1.csv"},
    "france_ligue2": {"country": "France", "tier": "2", "name": "Ligue 2", "url": "https://www.football-data.co.uk/mmz4281/2526/F2.csv"},
    "france_national": {"country": "France", "tier": "3", "name": "National", "url": ""},

    "poland_ekstraklasa": {"country": "Poland", "tier": "1", "name": "Ekstraklasa", "url": "https://www.football-data.co.uk/new/POL.csv"},
    "poland_1liga": {"country": "Poland", "tier": "2", "name": "1 Liga", "url": ""},
    "poland_2liga": {"country": "Poland", "tier": "3", "name": "2 Liga", "url": ""},

    "netherlands_eredivisie": {"country": "Netherlands", "tier": "1", "name": "Eredivisie", "url": "https://www.football-data.co.uk/mmz4281/2526/N1.csv"},
    "netherlands_eerste": {"country": "Netherlands", "tier": "2", "name": "Eerste Divisie", "url": ""},
    "portugal_primeira": {"country": "Portugal", "tier": "1", "name": "Primeira Liga", "url": "https://www.football-data.co.uk/mmz4281/2526/P1.csv"},
    "portugal_liga2": {"country": "Portugal", "tier": "2", "name": "Liga Portugal 2", "url": ""},
    "belgium_first": {"country": "Belgium", "tier": "1", "name": "First Division A", "url": "https://www.football-data.co.uk/mmz4281/2526/B1.csv"},
    "belgium_second": {"country": "Belgium", "tier": "2", "name": "Challenger Pro League", "url": ""},
    "turkey_superlig": {"country": "Turkey", "tier": "1", "name": "Super Lig", "url": "https://www.football-data.co.uk/mmz4281/2526/T1.csv"},
    "turkey_1lig": {"country": "Turkey", "tier": "2", "name": "1. Lig", "url": ""},
    "scotland_premiership": {"country": "Scotland", "tier": "1", "name": "Premiership", "url": "https://www.football-data.co.uk/mmz4281/2526/SC0.csv"},
    "scotland_championship": {"country": "Scotland", "tier": "2", "name": "Championship", "url": "https://www.football-data.co.uk/mmz4281/2526/SC1.csv"},

    "austria_bundesliga": {"country": "Austria", "tier": "1", "name": "Bundesliga", "url": ""},
    "switzerland_super": {"country": "Switzerland", "tier": "1", "name": "Super League", "url": ""},
    "denmark_superliga": {"country": "Denmark", "tier": "1", "name": "Superliga", "url": ""},
    "sweden_allsvenskan": {"country": "Sweden", "tier": "1", "name": "Allsvenskan", "url": ""},
    "norway_eliteserien": {"country": "Norway", "tier": "1", "name": "Eliteserien", "url": ""},
    "czech_first": {"country": "Czechia", "tier": "1", "name": "Czech First League", "url": ""},
    "romania_liga1": {"country": "Romania", "tier": "1", "name": "Liga I", "url": ""},
    "croatia_hnl": {"country": "Croatia", "tier": "1", "name": "HNL", "url": ""},
    "greece_super": {"country": "Greece", "tier": "1", "name": "Super League", "url": ""},
}

ALIASES = {
    "real madryt": "Real Madrid", "milan": "AC Milan", "ac milan": "AC Milan",
    "cagliari": "Cagliari", "man city": "Manchester City", "manchester city": "Manchester City",
    "west ham": "West Ham United", "west ham united": "West Ham United",
    "leverkusen": "Bayer Leverkusen", "bayern": "Bayern Munich",
    "psg": "Paris Saint Germain", "lech": "Lech Poznan", "legia": "Legia Warsaw",
    "rakow": "Rakow Czestochowa", "raków": "Rakow Czestochowa",
}

LOGO_DOMAINS = {
    "ac milan": "acmilan.com", "cagliari": "cagliaricalcio.com", "inter": "inter.it",
    "juventus": "juventus.com", "torino": "torinofc.it", "napoli": "sscnapoli.it",
    "manchester city": "mancity.com", "west ham united": "whufc.com",
    "manchester united": "manutd.com", "arsenal": "arsenal.com", "chelsea": "chelseafc.com",
    "liverpool": "liverpoolfc.com", "real madrid": "realmadrid.com",
    "barcelona": "fcbarcelona.com", "bayern munich": "fcbayern.com",
    "borussia dortmund": "bvb.de", "bayer leverkusen": "bayer04.de",
    "paris saint germain": "psg.fr", "lech poznan": "lechpoznan.pl",
    "legia warsaw": "legia.com", "rakow czestochowa": "rakow.com",
}

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS squads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team TEXT UNIQUE,
        notes TEXT,
        updated_at TEXT
    )""")
    con.commit()
    con.close()

init_db()

def norm(x):
    return (x or "").lower().replace("ą","a").replace("ć","c").replace("ę","e").replace("ł","l").replace("ń","n").replace("ó","o").replace("ś","s").replace("ż","z").replace("ź","z").strip()

def display_name(team):
    t = (team or "").strip()
    return ALIASES.get(norm(t), t)

def esc(x):
    return str(x).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def badge(team):
    team = display_name(team)
    domain = LOGO_DOMAINS.get(norm(team))
    initials = "".join([p[:1] for p in team.split()[:2]]).upper() or "QE"
    if domain:
        return f"<img class='crest' src='https://logo.clearbit.com/{domain}' onerror=\"this.style.display='none';this.nextElementSibling.style.display='flex';\"><span class='crest fake' style='display:none'>{initials}</span>"
    return f"<span class='crest fake'>{initials}</span>"

def cache_path(url):
    h = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, h + ".csv")

def get_rows_for_league(league_key):
    src = LEAGUES.get(league_key, LEAGUES["auto"])
    url = src.get("url", "")
    if not url:
        return [], "Brak stabilnego CSV dla tej ligi — opcja dodana do UI, wymaga API/źródła danych"

    path = cache_path(url)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < CACHE_TTL:
        text = open(path, "r", encoding="utf-8", errors="ignore").read()
        return list(csv.DictReader(io.StringIO(text))), "cache plikowy"

    r = requests.get(url, timeout=8)
    r.raise_for_status()
    text = r.text
    open(path, "w", encoding="utf-8").write(text)
    return list(csv.DictReader(io.StringIO(text))), "internet"

def get_rows_auto(home, away):
    for key, meta in LEAGUES.items():
        if key == "auto" or not meta.get("url"):
            continue
        try:
            rows, source = get_rows_for_league(key)
            if team_exists(home, rows) or team_exists(away, rows):
                return rows, f"{meta['country']} - {meta['name']} / {source}", key
        except Exception:
            continue
    return [], "AUTO: brak dopasowania", "auto"

def team_exists(team, rows):
    q = norm(display_name(team))
    for r in rows:
        if norm(r.get("HomeTeam","")) == q or norm(r.get("AwayTeam","")) == q:
            return True
    return False

def similar(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()

def is_team(row_name, query):
    a, b = norm(row_name), norm(display_name(query))
    return a == b or b in a or a in b or similar(a,b) > 0.78

def avg(values):
    vals = [v for v in values if isinstance(v, (int, float))]
    return round(sum(vals)/len(vals), 2) if vals else 0

def get_float(row, key):
    try:
        val = row.get(key, "")
        if val == "" or val is None:
            return None
        return float(val)
    except Exception:
        return None

def team_stats(team, rows):
    games = []
    for r in rows:
        if is_team(r.get("HomeTeam",""), team) or is_team(r.get("AwayTeam",""), team):
            games.append(r)
    games = games[-8:]

    goals_for = []
    goals_against = []
    shots = []
    shots_against = []
    sot = []
    sot_against = []
    corners = []
    corners_against = []
    cards = []
    cards_against = []
    points = []
    home_games = []
    away_games = []

    for r in games:
        home = is_team(r.get("HomeTeam",""), team)
        htg, atg = get_float(r, "FTHG"), get_float(r, "FTAG")
        if htg is None or atg is None:
            continue

        if home:
            gf, ga = htg, atg
            s, sa = get_float(r,"HS"), get_float(r,"AS")
            st, sta = get_float(r,"HST"), get_float(r,"AST")
            c, ca = get_float(r,"HC"), get_float(r,"AC")
            y, ya = get_float(r,"HY"), get_float(r,"AY")
            home_games.append(f"{r.get('HomeTeam')} {int(htg)}:{int(atg)} {r.get('AwayTeam')}")
        else:
            gf, ga = atg, htg
            s, sa = get_float(r,"AS"), get_float(r,"HS")
            st, sta = get_float(r,"AST"), get_float(r,"HST")
            c, ca = get_float(r,"AC"), get_float(r,"HC")
            y, ya = get_float(r,"AY"), get_float(r,"HY")
            away_games.append(f"{r.get('HomeTeam')} {int(htg)}:{int(atg)} {r.get('AwayTeam')}")

        goals_for.append(gf)
        goals_against.append(ga)
        if s is not None: shots.append(s)
        if sa is not None: shots_against.append(sa)
        if st is not None: sot.append(st)
        if sta is not None: sot_against.append(sta)
        if c is not None: corners.append(c)
        if ca is not None: corners_against.append(ca)
        if y is not None: cards.append(y)
        if ya is not None: cards_against.append(ya)

        points.append(3 if gf > ga else 1 if gf == ga else 0)

    form = round((sum(points)/(len(points)*3))*100, 1) if points else 0
    return {
        "matches": len(games),
        "form": form,
        "goals_for": avg(goals_for),
        "goals_against": avg(goals_against),
        "shots": avg(shots),
        "shots_against": avg(shots_against),
        "sot": avg(sot),
        "sot_against": avg(sot_against),
        "corners": avg(corners),
        "corners_against": avg(corners_against),
        "cards": avg(cards),
        "cards_against": avg(cards_against),
        "home_games": " | ".join(home_games[-5:]),
        "away_games": " | ".join(away_games[-5:]),
    }

def squad_notes(team):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT notes FROM squads WHERE team=?", (display_name(team),))
    row = cur.fetchone()
    con.close()
    return row[0] if row else ""

def save_squad(team, notes):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("INSERT INTO squads(team, notes, updated_at) VALUES(?,?,?) ON CONFLICT(team) DO UPDATE SET notes=excluded.notes, updated_at=excluded.updated_at",
                (display_name(team), notes, datetime.now().strftime("%Y-%m-%d %H:%M")))
    con.commit()
    con.close()

CSS = """
<style>
body{margin:0;background:#02070d;color:#eaf6ff;font-family:Arial,Helvetica,sans-serif}
.shell{display:grid;grid-template-columns:260px 1fr 360px;min-height:100vh}
.side,.right{background:#03101d;border-color:#123a5b;padding:16px}
.side{border-right:1px solid #123a5b}.right{border-left:1px solid #123a5b}
.main{padding:16px}
.logo{font-size:28px;font-weight:900;color:white;line-height:1;margin-bottom:20px}.logo span{display:block;color:#0fc8ff}
.card{background:linear-gradient(180deg,#07182a,#030d18);border:1px solid #164060;border-radius:12px;padding:16px;margin-bottom:14px;box-shadow:0 8px 24px #0008}
h1,h2{margin-top:0}.green{color:#59ff37}.blue{color:#31bfff}.red{color:#ff4a5f}.yellow{color:#ffc021}.purple{color:#b268ff}
input,select,textarea{width:100%;box-sizing:border-box;padding:11px;background:#020812;color:white;border:1px solid #244360;border-radius:8px;margin:6px 0 12px}
textarea{min-height:110px}
button{width:100%;padding:12px;border:0;border-radius:8px;background:#1267e8;color:white;font-weight:900;margin-top:6px;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.stat{background:#04111f;border:1px solid #1f405e;border-radius:10px;padding:12px;text-align:center}
.stat small{color:#9fb3ca;display:block}.stat b{font-size:22px;color:#59ff37}
.match{display:grid;grid-template-columns:80px 1fr 80px;gap:14px;align-items:center}
.crest{width:62px;height:62px;object-fit:contain}.fake{display:flex;align-items:center;justify-content:center;border-radius:50%;background:#0c1e31;color:#8cff32;border:1px solid #24506f;font-weight:900}
.league-list{max-height:460px;overflow:auto}.league{display:flex;justify-content:space-between;border-bottom:1px solid #123a5b;padding:7px 0;font-size:13px}
.badge{padding:3px 7px;border:1px solid #235879;border-radius:999px;color:#31bfff}
.games{font-size:12px;color:#c9d7e8;line-height:1.45}
@media(max-width:1000px){.shell{display:block}.grid{grid-template-columns:1fr}.side,.right{border:0}}
</style>
"""

def league_options(selected="auto"):
    out = ""
    for key, meta in LEAGUES.items():
        sel = "selected" if key == selected else ""
        out += f"<option value='{key}' {sel}>{meta['country']} - {meta['name']} / tier {meta['tier']}</option>"
    return out

def page(home="", away="", league_key="auto", result=None, error=""):
    home = display_name(home)
    away = display_name(away)
    if result is None:
        result = {}

    hs = result.get("home_stats", {})
    aw = result.get("away_stats", {})
    source = result.get("source", "")
    used_league = result.get("league_key", league_key)

    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quantum Edge v34</title>{CSS}</head>
<body>
<div class="shell">
<aside class="side">
<div class="logo">⚡ QUANTUM<span>EDGE</span></div>
<div class="card">
<h2>Match Search</h2>
<form method="post" action="/analyze">
<label>Gospodarz</label>
<input name="home" value="{esc(home)}" placeholder="np. Lech Poznan">
<label>Gość</label>
<input name="away" value="{esc(away)}" placeholder="np. Legia Warsaw">
<label>Kraj / Liga</label>
<select name="league_key">{league_options(used_league)}</select>
<button type="submit">⚡ FAST STATS</button>
</form>
</div>
<div class="card">
<h2>Kadra / absencje</h2>
<form method="post" action="/squad">
<label>Drużyna</label><input name="team" value="{esc(home)}">
<label>Notatki kadrowe</label><textarea name="notes" placeholder="Kontuzje, zawieszenia, rotacje, przewidywany skład...">{esc(squad_notes(home))}</textarea>
<button type="submit">Zapisz kadrę</button>
</form>
</div>
</aside>

<main class="main">
<div class="card match">
<div>{badge(home or "Home")}</div>
<div><div class="blue">Quantum Edge v34</div><h1>{esc(home or "Home")} vs {esc(away or "Away")}</h1><div>Źródło: {esc(source or "brak")}</div></div>
<div>{badge(away or "Away")}</div>
</div>

{"<div class='card red'><h2>Błąd</h2><pre>"+esc(error)+"</pre></div>" if error else ""}

<div class="card">
<h2>Statystyki pobrane do aplikacji</h2>
<div class="grid">
<div class="stat"><small>Forma %</small><b>{hs.get("form",0)} - {aw.get("form",0)}</b></div>
<div class="stat"><small>Gole</small><b>{hs.get("goals_for",0)} - {aw.get("goals_for",0)}</b></div>
<div class="stat"><small>Gole stracone</small><b>{hs.get("goals_against",0)} - {aw.get("goals_against",0)}</b></div>
<div class="stat"><small>Mecze w próbie</small><b>{hs.get("matches",0)} - {aw.get("matches",0)}</b></div>
<div class="stat"><small>Strzały</small><b>{hs.get("shots",0)} - {aw.get("shots",0)}</b></div>
<div class="stat"><small>Strzały przeciw</small><b>{hs.get("shots_against",0)} - {aw.get("shots_against",0)}</b></div>
<div class="stat"><small>Celne</small><b>{hs.get("sot",0)} - {aw.get("sot",0)}</b></div>
<div class="stat"><small>Celne przeciw</small><b>{hs.get("sot_against",0)} - {aw.get("sot_against",0)}</b></div>
<div class="stat"><small>Rożne</small><b>{hs.get("corners",0)} - {aw.get("corners",0)}</b></div>
<div class="stat"><small>Rożne przeciw</small><b>{hs.get("corners_against",0)} - {aw.get("corners_against",0)}</b></div>
<div class="stat"><small>Kartki</small><b>{hs.get("cards",0)} - {aw.get("cards",0)}</b></div>
<div class="stat"><small>Kartki przeciw</small><b>{hs.get("cards_against",0)} - {aw.get("cards_against",0)}</b></div>
</div>
</div>

<div class="card">
<h2>Ostatnie mecze home/away</h2>
<div class="grid">
<div class="stat games"><small>{esc(home)} u siebie</small>{esc(hs.get("home_games","brak"))}</div>
<div class="stat games"><small>{esc(home)} wyjazd</small>{esc(hs.get("away_games","brak"))}</div>
<div class="stat games"><small>{esc(away)} u siebie</small>{esc(aw.get("home_games","brak"))}</div>
<div class="stat games"><small>{esc(away)} wyjazd</small>{esc(aw.get("away_games","brak"))}</div>
</div>
</div>

<div class="card">
<h2>Ustawienia modelu</h2>
<div class="grid">
<div class="stat"><small>Cache</small><b>12h</b></div>
<div class="stat"><small>Tryb ligi</small><b>{esc(LEAGUES.get(used_league, {}).get("name", used_league))}</b></div>
<div class="stat"><small>Źródło</small><b>Football-Data</b></div>
<div class="stat"><small>Kadra</small><b>SQLite</b></div>
</div>
</div>
</main>

<aside class="right">
<div class="card">
<h2>Ligi w aplikacji</h2>
<div class="league-list">
{''.join([f"<div class='league'><span>{esc(m['country'])} - {esc(m['name'])}</span><span class='badge'>tier {esc(m['tier'])}</span></div>" for m in LEAGUES.values()])}
</div>
</div>
<div class="card">
<h2>Notatki kadrowe</h2>
<div><b>{esc(home)}</b><p>{esc(squad_notes(home)) or "brak notatek"}</p></div>
<div><b>{esc(away)}</b><p>{esc(squad_notes(away)) or "brak notatek"}</p></div>
</div>
</aside>
</div>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def index():
    return page()

@app.post("/analyze", response_class=HTMLResponse)
def analyze(home: str = Form(""), away: str = Form(""), league_key: str = Form("auto")):
    try:
        home_d = display_name(home)
        away_d = display_name(away)

        if league_key == "auto":
            rows, source, used = get_rows_auto(home_d, away_d)
        else:
            rows, source = get_rows_for_league(league_key)
            used = league_key

        if not rows:
            return page(home_d, away_d, used, error=source)

        result = {
            "home_stats": team_stats(home_d, rows),
            "away_stats": team_stats(away_d, rows),
            "source": source,
            "league_key": used,
        }
        return page(home_d, away_d, used, result=result)
    except Exception as e:
        return page(home, away, league_key, error=str(e))

@app.post("/squad", response_class=HTMLResponse)
def squad(team: str = Form(""), notes: str = Form("")):
    save_squad(team, notes)
    return page(home=team, result={"source": "Zapisano notatki kadrowe", "league_key": "auto"})
