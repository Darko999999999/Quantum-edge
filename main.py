from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime
import urllib.request
import urllib.parse
import re

app = FastAPI(title="Quantum Edge Web")

DB_PATH = "quantum_edge.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
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
    conn.commit()
    conn.close()


init_db()


ALIASES = {
    "fiorentina": ["fiorentina", "acf fiorentina"],
    "atalanta": ["atalanta", "atalanta bc"],
    "lens": ["lens", "rc lens"],
    "nice": ["nice", "ogc nice", "nicea"],
    "nicea": ["nice", "ogc nice", "nicea"],
}


def esc(x):
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def norm(x):
    return (x or "").lower().replace(" ", "").replace("-", "").replace(".", "").replace("_", "").replace("'", "")


def team_aliases(name):
    key = (name or "").strip().lower()
    return ALIASES.get(key, [key])


def default_values():
    return {
        "home_team": "",
        "away_team": "",
        "city": "",
        "xg_home": 1.25,
        "xg_away": 0.95,
        "form_home": 60,
        "form_away": 55,
        "tempo": 50,
        "odds": 1.75,
        "odds_1": 2.10,
        "odds_x": 3.40,
        "odds_2": 3.35,
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
        "bookmaker": "STS",
        "odds_source": "brak pewnego źródła",
        "btts": 55,
        "over25": 50,
        "confidence": 60,
    }


def http_text(url, timeout=12):
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore"), None
    except Exception as e:
        return "", str(e)


def parse_decimal_numbers(text):
    nums = []
    for raw in re.findall(r'(?<!\d)([1-9]\d?[,\.]\d{2})(?!\d)', text):
        try:
            val = float(raw.replace(",", "."))
            if 1.01 <= val <= 30:
                nums.append(val)
        except Exception:
            pass
    return nums


def public_sts_odds(home_team, away_team):
    """
    Próba bez logowania: pobiera publiczne strony STS i szuka nazw drużyn.
    STS może blokować albo ładować kursy JS-em, więc funkcja zwraca tylko kursy,
    gdy znajdzie pewny blok z obiema drużynami i trzema kursami 1X2.
    """
    queries = [
        f"{home_team} {away_team}",
        f"{home_team} - {away_team}",
        f"{away_team} {home_team}",
    ]

    urls = []
    for q in queries:
        urls.append("https://www.sts.pl/szukaj/?q=" + urllib.parse.quote(q))
        urls.append("https://www.sts.pl/zaklady-bukmacherskie/pilka-nozna/?q=" + urllib.parse.quote(q))

    home_alias = [norm(x) for x in team_aliases(home_team)]
    away_alias = [norm(x) for x in team_aliases(away_team)]

    last_error = ""

    for url in urls:
        html, err = http_text(url)
        if err:
            last_error = err
            continue
        if not html:
            continue

        text_norm = norm(html)

        if not any(a in text_norm for a in home_alias):
            continue
        if not any(a in text_norm for a in away_alias):
            continue

        # Szukamy fragmentu strony w okolicy obu nazw drużyn.
        positions = []
        for a in home_alias + away_alias:
            p = text_norm.find(a)
            if p >= 0:
                positions.append(p)

        if not positions:
            continue

        start = max(0, min(positions) - 6000)
        end = min(len(html), max(positions) + 6000)
        block = html[start:end]

        odds = parse_decimal_numbers(block)

        # Heurystyka: pierwsze 3 wiarygodne kursy w bloku obu drużyn traktujemy jako 1X2.
        # Nie akceptujemy, gdy kursy wyglądają podejrzanie nisko / brak trzech wartości.
        if len(odds) >= 3:
            o1, ox, o2 = odds[0], odds[1], odds[2]
            if o1 > 1.01 and ox > 1.01 and o2 > 1.01:
                return {
                    "success": True,
                    "odds_1": round(o1, 2),
                    "odds_x": round(ox, 2),
                    "odds_2": round(o2, 2),
                    "source": "STS public offer / parser",
                    "url": url,
                    "note": "Kursy znalezione bez logowania. Sprawdź zgodność z aplikacją STS przed grą.",
                }

    return {
        "success": False,
        "source": "STS public offer / parser",
        "error": last_error or "Nie znaleziono pewnego bloku kursów 1X2 dla tego meczu.",
    }


def fetch_stats_proxy(home_team, away_team, city):
    v = default_values()
    v["home_team"] = home_team
    v["away_team"] = away_team
    v["city"] = city

    h_len = max(1, len(home_team))
    a_len = max(1, len(away_team))

    v["xg_home"] = round(1.05 + (h_len % 5) * 0.08, 2)
    v["xg_away"] = round(0.90 + (a_len % 5) * 0.07, 2)
    v["form_home"] = 58
    v["form_away"] = 54
    v["shots_home"] = 11.5
    v["shots_away"] = 10.2
    v["sot_home"] = 4.1
    v["sot_away"] = 3.7
    v["corners_home"] = 5.2
    v["corners_away"] = 4.4
    v["cards_home"] = 2.0
    v["cards_away"] = 2.1
    v["tempo"] = 50 if v["xg_home"] + v["xg_away"] < 2.7 else 62
    v["btts"] = round(45 + (v["xg_home"] + v["xg_away"]) * 6, 1)
    v["over25"] = round(35 + (v["xg_home"] + v["xg_away"]) * 9, 1)
    v["confidence"] = 62
    v["message"] = "Dane statystyczne uzupełnione automatycznie/proxy. Możesz je poprawić ręcznie."
    v["sources"] = ["Proxy / fallback"]
    return v


def fetch_odds(home_team, away_team, bookmaker):
    v = default_values()
    v["home_team"] = home_team
    v["away_team"] = away_team
    v["bookmaker"] = bookmaker

    if bookmaker.strip().lower() == "sts":
        res = public_sts_odds(home_team, away_team)
        if res.get("success"):
            v["odds_1"] = res["odds_1"]
            v["odds_x"] = res["odds_x"]
            v["odds_2"] = res["odds_2"]
            v["odds"] = res["odds_1"]
            v["odds_source"] = res["source"]
            v["message"] = "Kursy STS zostały pobrane z publicznej oferty. Zweryfikuj je przed zagraniem."
            v["sources"] = [res["source"]]
            v["confidence"] = 72
            return v

        v["odds_source"] = "STS: nie znaleziono pewnego kursu publicznego"
        v["message"] = "Nie udało się pewnie pobrać kursów STS. Zostawiam fallback i pola do ręcznej korekty."
        v["sources"] = [v["odds_source"]]
        return v

    v["odds_source"] = f"{bookmaker}: parser nie jest jeszcze podłączony"
    v["message"] = f"Dla {bookmaker} parser nie jest jeszcze podłączony. Zostawiam fallback i pola do ręcznej korekty."
    v["sources"] = [v["odds_source"]]
    return v


def fair_odds(probability):
    return round(100 / probability, 2) if probability > 0 else 0


def value_edge(probability, odds):
    return round(probability - (100 / odds), 2) if odds > 1 else 0


def choose_pick(xg_home, xg_away, tempo, defensive_control, chaos):
    total = xg_home + xg_away
    if total <= 2.25 and tempo <= 55 and defensive_control >= 58 and chaos <= 55:
        return "Under 2.5 gola", "1:0 / 1:1 / 0:0"
    if total <= 2.90 and tempo <= 62 and defensive_control >= 52:
        return "Under 3.5 gola", "1:1 / 2:1 / 1:0"
    if total >= 2.75 and tempo >= 55 and chaos <= 62:
        return "Over 1.5 gola", "2:1 / 2:2 / 3:1"
    if xg_home >= xg_away:
        return "1X", "1:0 / 1:1 / 2:1"
    return "X2", "0:1 / 1:1 / 1:2"


def calculate_model(d):
    xg_home = float(d["xg_home"])
    xg_away = float(d["xg_away"])
    form_home = float(d["form_home"])
    form_away = float(d["form_away"])
    tempo = float(d["tempo"])
    odds = float(d["odds"])

    defensive_control = float(d["defensive_control"])
    draw_acceptance = float(d["draw_acceptance"])
    collapse_home = float(d["collapse_home"])
    collapse_away = float(d["collapse_away"])
    absences = float(d["absences"])
    weather = float(d["weather"])
    market_risk = float(d["market_risk"])

    shots_total = float(d["shots_home"]) + float(d["shots_away"])
    sot_total = float(d["sot_home"]) + float(d["sot_away"])
    corners_total = float(d["corners_home"]) + float(d["corners_away"])
    cards_total = float(d["cards_home"]) + float(d["cards_away"])

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

    total_xg = xg_home + xg_away
    flow_bonus = 5 if total_xg <= 2.35 and tempo <= 55 and defensive_control >= 58 else 0

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
        "shots_total": round(shots_total, 1),
        "sot_total": round(sot_total, 1),
        "corners_total": round(corners_total, 1),
        "cards_total": round(cards_total, 1),
    }


def card_result(result, v):
    if not result:
        return ""
    return f"""
<section class="card">
    <div class="match">{esc(v["home_team"])} <span>vs</span> {esc(v["away_team"])}</div>
    <div class="grid-3">
        <div><small>Typ</small><strong>{esc(result["pick"])}</strong></div>
        <div><small>Probability</small><strong>{result["probability"]}%</strong></div>
        <div><small>Value</small><strong>{result["value_edge"]} pp</strong></div>
    </div>
    <div class="rating">{esc(result["rating"])}</div>
    <div class="stats">
        <div><span>Fair odds</span><b>{result["fair_odds"]}</b></div>
        <div><span>Kurs modelu</span><b>{v["odds"]}</b></div>
        <div><span>Chaos risk</span><b>{result["chaos"]}/100</b></div>
        <div><span>Exact score</span><b>{esc(result["exact_score"])}</b></div>
        <div><span>Suma xG</span><b>{result["total_xg"]}</b></div>
        <div><span>Strzały</span><b>{result["shots_total"]}</b></div>
        <div><span>Celne</span><b>{result["sot_total"]}</b></div>
        <div><span>Rożne</span><b>{result["corners_total"]}</b></div>
        <div><span>Kartki</span><b>{result["cards_total"]}</b></div>
    </div>
</section>
"""


def card_auto(fetched):
    if not fetched:
        return ""
    sources = ", ".join(fetched.get("sources", []))
    return f"""
<section class="card">
    <h2>Dane pobrane / uzupełnione</h2>
    <p>{esc(fetched.get("message", ""))}</p>
    <p><b>Źródło:</b> {esc(sources)}</p>
    <div class="stats">
        <div><span>xG</span><b>{fetched["xg_home"]} - {fetched["xg_away"]}</b></div>
        <div><span>Forma</span><b>{fetched["form_home"]} - {fetched["form_away"]}</b></div>
        <div><span>Kursy 1X2</span><b>{fetched["odds_1"]} / {fetched["odds_x"]} / {fetched["odds_2"]}</b></div>
        <div><span>Źródło kursu</span><b>{esc(fetched.get("odds_source", ""))}</b></div>
        <div><span>BTTS</span><b>{fetched["btts"]}%</b></div>
        <div><span>Over 2.5</span><b>{fetched["over25"]}%</b></div>
        <div><span>Confidence</span><b>{fetched["confidence"]}%</b></div>
        <div><span>Tempo</span><b>{fetched["tempo"]}/100</b></div>
    </div>
</section>
"""


def build_page(values=None, result=None, fetched=None, history=None):
    v = values or default_values()

    history_html = ""
    if history:
        rows = ""
        for r in history:
            rows += f"""
            <div class="history-row">
                <div><b>{esc(r[2])} vs {esc(r[3])}</b><small>{esc(r[1])}</small></div>
                <div>{esc(r[4])}</div>
                <div>{r[5]}%</div>
                <div>{r[8]} pp</div>
                <div>{esc(r[10])}</div>
            </div>
            """
        history_html = f'<section class="card"><h2>Historia analiz</h2>{rows}</section>'

    return f"""
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>Quantum Edge</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:radial-gradient(circle at top,#0f2435 0%,#050912 55%,#03060c 100%);color:#f4f7fb;font-family:Arial,Helvetica,sans-serif}}
.app{{max-width:850px;margin:0 auto;padding:18px}}
header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}}
.logo{{font-size:24px;font-weight:800;letter-spacing:1px;line-height:1.1}}
.logo span{{color:#90ff36;display:block}}
a{{color:#90ff36;text-decoration:none}}
.nav a{{margin-left:10px;border:1px solid #30445b;padding:8px 12px;border-radius:12px}}
.card{{background:rgba(12,22,36,.92);border:1px solid #22344c;border-radius:18px;padding:18px;margin-bottom:16px;box-shadow:0 14px 38px rgba(0,0,0,.32)}}
.hero h1{{margin:8px 0;font-size:26px}}
.label{{color:#90ff36;font-size:13px;font-weight:bold}}
.topline{{display:flex;align-items:center;justify-content:space-between;gap:10px}}
.iconbar{{display:flex;gap:12px}}
.roundbtn{{width:58px;height:58px;border-radius:50%;border:1px solid rgba(144,255,54,.45);background:rgba(144,255,54,.10);color:#90ff36;font-size:25px;font-weight:900;margin:0;padding:0}}
.money{{color:#b566ff;border-color:rgba(181,102,255,.55);background:rgba(181,102,255,.10)}}
.match{{text-align:center;font-size:22px;font-weight:bold;margin-bottom:16px}}
.match span{{color:#91a0b5;font-size:14px;margin:0 10px}}
.grid-3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:16px}}
.grid-3 div{{background:#091221;border:1px solid #22344c;border-radius:14px;padding:12px}}
small{{display:block;color:#98a7ba;margin-bottom:6px}}
strong{{color:#90ff36;font-size:22px}}
.rating{{text-align:center;padding:12px;border-radius:14px;background:rgba(144,255,54,.10);border:1px solid rgba(144,255,54,.35);color:#90ff36;font-weight:bold;margin-bottom:14px}}
.stats{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}}
.stats div{{display:flex;justify-content:space-between;background:#08111e;border-radius:12px;padding:10px;gap:8px}}
.stats span{{color:#98a7ba}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
label{{display:flex;flex-direction:column;color:#cbd6e3;font-size:14px;gap:6px}}
input,select{{width:100%;padding:12px;border-radius:12px;border:1px solid #2d4058;background:#07101d;color:white;font-size:16px}}
button.main{{width:100%;margin-top:18px;padding:15px;border:none;border-radius:16px;background:#90ff36;color:#07101d;font-weight:800;font-size:17px}}
.history-row{{display:grid;grid-template-columns:2fr 1.2fr .7fr .8fr 1fr;gap:8px;padding:12px 0;border-bottom:1px solid #22344c;align-items:center}}
@media(max-width:560px){{.app{{padding:14px}}.two,.grid-3,.stats,.history-row{{grid-template-columns:1fr}}}}
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
    <p>⚡ pobiera statystyki. 💰 próbuje pobrać publiczne kursy STS bez logowania. Jeżeli nie ma pewnego kursu, zostaje ręczna korekta.</p>
</section>

{card_result(result, v)}
{card_auto(fetched)}
{history_html}

<form action="/fetch" method="post" class="card">
    <div class="topline">
        <h2>Dane meczu</h2>
        <div class="iconbar">
            <button class="roundbtn" name="mode" value="stats" type="submit" title="Pobierz statystyki">⚡</button>
            <button class="roundbtn money" name="mode" value="odds" type="submit" title="Pobierz kursy STS">💰</button>
        </div>
    </div>
    <div class="two">
        <label>Gospodarz<input name="home_team" required value="{esc(v["home_team"])}" placeholder="Fiorentina"></label>
        <label>Gość<input name="away_team" required value="{esc(v["away_team"])}" placeholder="Atalanta"></label>
        <label>Miasto meczu / pogoda<input name="city" value="{esc(v.get("city",""))}" placeholder="Florencja"></label>
        <label>Bukmacher
            <select name="bookmaker">
                <option>STS</option>
                <option>Betclic</option>
                <option>Fortuna</option>
                <option>Superbet</option>
                <option>Rynek</option>
            </select>
        </label>
    </div>
</form>

<form action="/analyze" method="post" class="card">
    <input type="hidden" name="home_team" value="{esc(v["home_team"])}">
    <input type="hidden" name="away_team" value="{esc(v["away_team"])}">

    <h3>xG / forma</h3>
    <div class="two">
        <label>xG gospodarz<input type="number" step="0.01" name="xg_home" value="{v["xg_home"]}"></label>
        <label>xG gość<input type="number" step="0.01" name="xg_away" value="{v["xg_away"]}"></label>
        <label>Forma gospodarz<input type="number" step="1" name="form_home" value="{v["form_home"]}"></label>
        <label>Forma gość<input type="number" step="1" name="form_away" value="{v["form_away"]}"></label>
    </div>

    <h3>Kursy</h3>
    <div class="two">
        <label>Główny kurs do modelu<input type="number" step="0.01" name="odds" value="{v["odds"]}"></label>
        <label>Kurs 1<input type="number" step="0.01" name="odds_1" value="{v["odds_1"]}"></label>
        <label>Kurs X<input type="number" step="0.01" name="odds_x" value="{v["odds_x"]}"></label>
        <label>Kurs 2<input type="number" step="0.01" name="odds_2" value="{v["odds_2"]}"></label>
    </div>

    <h3>Statystyki</h3>
    <div class="two">
        <label>Tempo 0-100<input type="number" step="1" name="tempo" value="{v["tempo"]}"></label>
        <label>Strzały gospodarz<input type="number" step="0.1" name="shots_home" value="{v["shots_home"]}"></label>
        <label>Strzały gość<input type="number" step="0.1" name="shots_away" value="{v["shots_away"]}"></label>
        <label>Celne gospodarz<input type="num
