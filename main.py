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
    "ac milan": "Milan",
    "juventus": "Juventus",
    "roma": "Roma",
    "lazio": "Lazio",
    "napoli": "Napoli",
    "real": "Real Madrid",
    "real madryt": "Real Madrid",
    "barca": "Barcelona",
    "barcelona": "Barcelona",
    "bayern": "Bayern Munich",
    "bayern monachium": "Bayern Munich",
    "psg": "Paris Saint-Germain",
    "paris": "Paris Saint-Germain",
    "marsylia": "Marseille",
    "marseille": "Marseille",
    "lyon": "Lyon",
    "monaco": "Monaco",
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


@app.on_event("startup")
def startup():
    init_db()


def norm(txt):
    return (txt or "").lower().replace(" ", "").replace("-", "").replace(".", "").replace("_", "")


def fixed_name(txt):
    return ALIASES.get((txt or "").strip().lower(), (txt or "").strip())


def get_json(url, timeout=15):
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        req.add_header("Accept", "application/json,text/plain,*/*")
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception:
        return None


def get_text(url, timeout=15):
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def recursive_find_teams(obj, wanted):
    found = []
    wanted_n = norm(wanted)

    if isinstance(obj, dict):
        for key in ["entity", "team"]:
            if key in obj and isinstance(obj[key], dict):
                ent = obj[key]
                if "name" in ent and "id" in ent:
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


def search_team_sofascore(name):
    q = fixed_name(name)
    urls = [
        SOFA_BASE + "/search/all?q=" + urllib.parse.quote(q),
        SOFA_BASE + "/search/teams?q=" + urllib.parse.quote(q),
    ]

    for url in urls:
        data = get_json(url)
        if not data:
            continue
        teams = recursive_find_teams(data, q)
        if teams:
            return teams[0]

    return None


def scheduled_events_sofascore(date_str):
    data = get_json(SOFA_BASE + "/sport/football/scheduled-events/" + date_str)
    if data and isinstance(data.get("events"), list):
        return data["events"]
    return []


def team_last_events_sofascore(team_id):
    urls = [
        SOFA_BASE + "/team/" + str(team_id) + "/events/last/0",
        SOFA_BASE + "/team/" + str(team_id) + "/events/last/1",
    ]
    for url in urls:
        data = get_json(url)
        if data and isinstance(data.get("events"), list):
            return data["events"]
    return []


def form_from_events(events, team_id):
    points = 0
    gf = 0
    ga = 0
    count = 0
    results = []

    for ev in events[:5]:
        h = ev.get("homeTeam", {})
        a = ev.get("awayTeam", {})
        hs = ev.get("homeScore", {}).get("current")
        aas = ev.get("awayScore", {}).get("current")

        if hs is None or aas is None:
            continue

        h_id = h.get("id")
        a_id = a.get("id")

        if h_id == team_id:
            own = hs
            opp = aas
        elif a_id == team_id:
            own = aas
            opp = hs
        else:
            continue

        gf += own
        ga += opp
        count += 1
        results.append(h.get("name", "") + " " + str(hs) + ":" + str(aas) + " " + a.get("name", ""))

        if own > opp:
            points += 3
        elif own == opp:
            points += 1

    if count == 0:
        return None

    return {
        "form": round((points / (count * 3)) * 100, 1),
        "gf": round(gf / count, 2),
        "ga": round(ga / count, 2),
        "results": results,
    }


def find_match_by_date_sofascore(home_name, away_name, date_str):
    events = scheduled_events_sofascore(date_str)
    home_n = norm(fixed_name(home_name))
    away_n = norm(fixed_name(away_name))

    for ev in events:
        h = ev.get("homeTeam", {}).get("name", "")
        a = ev.get("awayTeam", {}).get("name", "")
        h_n = norm(h)
        a_n = norm(a)

        if (home_n in h_n or h_n in home_n) and (away_n in a_n or a_n in away_n):
            return ev
        if (home_n in a_n or a_n in home_n) and (away_n in h_n or h_n in away_n):
            return ev
    return None


def match_statistics_sofascore(event_id):
    urls = [
        SOFA_BASE + "/event/" + str(event_id) + "/statistics",
        SOFA_BASE + "/event/" + str(event_id) + "/statistics/0",
    ]
    for url in urls:
        data = get_json(url)
        if data:
            return data
    return None


def h2h_events_sofascore(event_id):
    data = get_json(SOFA_BASE + "/event/" + str(event_id) + "/h2h/events")
    if data and isinstance(data.get("events"), list):
        return data["events"]
    return []


def clean_number(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    txt = str(val).replace("%", "").replace(",", ".").strip()
    try:
        return float(txt)
    except Exception:
        return None


def extract_stat_value(stats_data, keywords, side):
    side_keys = {
        "home": ["home", "homeValue", "homeTeam"],
        "away": ["away", "awayValue", "awayTeam"],
    }

    if isinstance(stats_data, dict):
        for _, v in stats_data.items():
            if isinstance(v, (dict, list)):
                found = extract_stat_value(v, keywords, side)
                if found is not None:
                    return found

    if isinstance(stats_data, list):
        for item in stats_data:
            if isinstance(item, dict):
                name = str(item.get("name", item.get("type", item.get("key", "")))).lower()
                if any(kw.lower() in name for kw in keywords):
                    for sk in side_keys[side]:
                        if sk in item:
                            val = item.get(sk)
                            if isinstance(val, dict):
                                val = val.get("value")
                            val = clean_number(val)
                            if val is not None:
                                return val

                found = extract_stat_value(item, keywords, side)
                if found is not None:
                    return found
    return None


def understat_team_url(team_name):
    # Understat ma tylko wybrane top ligi. To próba po nazwie drużyny.
    slug = fixed_name(team_name).replace(" ", "_")
    return "https://understat.com/team/" + urllib.parse.quote(slug)


def fetch_understat_proxy(home_name, away_name):
    out = {
        "xg_home": None,
        "xg_away": None,
        "message": "",
    }

    # Understat często blokuje/zmienia strukturę, więc ten moduł działa jako miękki parser.
    # Jeśli znajdzie JSON z xG, podmieni proxy. Jeśli nie, aplikacja zostawia dane z SofaScore/proxy.
    msgs = []

    for side, name in [("home", home_name), ("away", away_name)]:
        html = get_text(understat_team_url(name), timeout=10)
        if not html:
            msgs.append(f"Understat: brak danych dla {name}.")
            continue

        # Szukamy wartości xG w zakodowanym JS. To prosty fallback, nie pełny parser.
        matches = re.findall(r'"xG":"([0-9.]+)".*?"xGA":"([0-9.]+)"', html)
        if matches:
            try:
                # ostatnie 5 wpisów
                last = matches[-5:]
                avg_xg = sum(float(x[0]) for x in last) / len(last)
                if side == "home":
                    out["xg_home"] = round(avg_xg, 2)
                else:
                    out["xg_away"] = round(avg_xg, 2)
                msgs.append(f"Understat: pobrano xG dla {name}.")
            except Exception:
                msgs.append(f"Understat: nie udało się policzyć xG dla {name}.")
        else:
            msgs.append(f"Understat: nie znaleziono xG dla {name}.")

    out["message"] = " ".join(msgs)
    return out


def geocode_city(city):
    if not city:
        return None
    url = "https://geocoding-api.open-meteo.com/v1/search?name=" + urllib.parse.quote(city) + "&count=1&language=pl&format=json"
    data = get_json(url, timeout=10)
    if data and data.get("results"):
        r = data["results"][0]
        return r.get("latitude"), r.get("longitude"), r.get("name")
    return None


def fetch_weather(city, date_str):
    geo = geocode_city(city)
    if not geo:
        return {"risk": 15, "message": "Pogoda: brak lokalizacji."}

    lat, lon, city_name = geo
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        + urllib.parse.urlencode({
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
            "timezone": "auto",
            "start_date": date_str,
            "end_date": date_str,
        })
    )
    data = get_json(url, timeout=10)
    if not data or not data.get("daily"):
        return {"risk": 15, "message": "Pogoda: brak prognozy."}

    d = data["daily"]
    rain = (d.get("precipitation_sum") or [0])[0] or 0
    wind = (d.get("windspeed_10m_max") or [0])[0] or 0
    tmax = (d.get("temperature_2m_max") or [0])[0]
    tmin = (d.get("temperature_2m_min") or [0])[0]

    risk = 10
    if rain >= 2:
        risk += 10
    if rain >= 6:
        risk += 15
    if wind >= 25:
        risk += 10
    if wind >= 40:
        risk += 15
    if tmax is not None and (tmax >= 32 or tmax <= 0):
        risk += 10

    risk = max(5, min(80, risk))
    msg = f"Pogoda {city_name}: opad {rain} mm, wiatr {wind} km/h, temp. {tmin}-{tmax}°C. Ryzyko {risk}/100."
    return {"risk": risk, "message": msg}


def fetch_all_sources(home_input, away_input, date_str, city):
    data = {
        "home_team": home_input,
        "away_team": away_input,
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
        "weather": 15,
        "message": "",
        "h2h": [],
        "last_home": [],
        "last_away": [],
        "sources": [],
    }

    messages = []

    home_team = search_team_sofascore(home_input)
    away_team = search_team_sofascore(away_input)

    fh = None
    fa = None

    if home_team:
        data["home_team"] = home_team["name"]
        home_events = team_last_events_sofascore(home_team["id"])
        fh = form_from_events(home_events, home_team["id"])
        if fh:
            data["form_home"] = fh["form"]
            data["last_home"] = fh["results"]
        data["sources"].append("SofaScore: gospodarz")
    else:
        messages.append("SofaScore: nie znaleziono gospodarza.")

    if away_team:
        data["away_team"] = away_team["name"]
        away_events = team_last_events_sofascore(away_team["id"])
        fa = form_from_events(away_events, away_team["id"])
        if fa:
            data["form_away"] = fa["form"]
            data["last_away"] = fa["results"]
        data["sources"].append("SofaScore: gość")
    else:
        messages.append("SofaScore: nie znaleziono gościa.")

    if fh and fa:
        data["xg_home"] = round((fh["gf"] * 0.65) + (fa["ga"] * 0.35), 2)
        data["xg_away"] = round((fa["gf"] * 0.65) + (fh["ga"] * 0.35), 2)
        messages.append("SofaScore/proxy: policzono formę i xG proxy z ostatnich meczów.")

    event = find_match_by_date_sofascore(home_input, away_input, date_str)

    if event:
        event_id = event.get("id")
        data["home_team"] = event.get("homeTeam", {}).get("name", data["home_team"])
        data["away_team"] = event.get("awayTeam", {}).get("name", data["away_team"])
        data["sources"].append("SofaScore: mecz")

        stats = match_statistics_sofascore(event_id)
        if stats:
            sh = extract_stat_value(stats, ["total shots", "shots"], "home")
            sa = extract_stat_value(stats, ["total shots", "shots"], "away")
            soh = extract_stat_value(stats, ["shots on target", "shots on goal"], "home")
            soa = extract_stat_value(stats, ["shots on target", "shots on goal"], "away")
            ch = extract_stat_value(stats, ["corner"], "home")
            ca = extract_stat_value(stats, ["corner"], "away")
            yh = extract_stat_value(stats, ["yellow cards"], "home")
            ya = extract_stat_value(stats, ["yellow cards"], "away")

            if sh is not None:
                data["shots_home"] = sh
            if sa is not None:
                data["shots_away"] = sa
            if soh is not None:
                data["sot_home"] = soh
            if soa is not None:
                data["sot_away"] = soa
            if ch is not None:
                data["corners_home"] = ch
            if ca is not None:
                data["corners_away"] = ca
            if yh is not None:
                data["cards_home"] = yh
            if ya is not None:
                data["cards_away"] = ya

            messages.append("SofaScore: pobrano dostępne statystyki meczu.")
        else:
            messages.append("SofaScore: mecz znaleziony, ale brak statystyk live/przedmeczowych.")

        h2h = h2h_events_sofascore(event_id)
        for ev in h2h[:5]:
            h = ev.get("homeTeam", {}).get("name", "")
            a = ev.get("awayTeam", {}).get("name", "")
            hs = ev.get("homeScore", {}).get("current")
            aas = ev.get("awayScore", {}).get("current")
            data["h2h"].append(f"{h} {hs}:{aas} {a}")
    else:
        messages.append("SofaScore: nie znaleziono konkretnego meczu po dacie.")

    under = fetch_understat_proxy(data["home_team"], data["away_team"])
    if under["xg_home"] is not None:
        data["xg_home"] = under["xg_home"]
        data["sources"].append("Understat: xG gospodarz")
    if under["xg_away"] is not None:
        data["xg_away"] = under["xg_away"]
        data["sources"].append("Understat: xG gość")
    messages.append(under["message"])

    weather = fetch_weather(city, date_str)
    data["weather"] = weather["risk"]
    data["sources"].append("Open-Meteo: pogoda")
    messages.append(weather["message"])

    # tempo proxy
    total_shots = data["shots_home"] + data["shots_away"]
    total_sot = data["sot_home"] + data["sot_away"]
    if total_shots >= 25 or total_sot >= 9:
        data["tempo"] = 62
    elif total_shots <= 18 and total_sot <= 6:
        data["tempo"] = 43
    else:
        data["tempo"] = 50

    data["message"] = " ".join([m for m in messages if m])
    return data


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
      
