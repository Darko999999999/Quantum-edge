
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime
import urllib.request, urllib.parse, json, csv, io, difflib, re, html as html_lib

app = FastAPI(title="Quantum Edge v24")
DB_PATH = "quantum_edge.db"
ODDS_API_KEY = "4235b3c48084bdd173789f88b6ddadfd"

SPORT_KEYS = ["soccer_epl","soccer_england_championship","soccer_spain_la_liga","soccer_italy_serie_a","soccer_germany_bundesliga","soccer_france_ligue_one","soccer_france_ligue_two","soccer_netherlands_eredivisie","soccer_portugal_primeira_liga","soccer_scotland_premiership","soccer_belgium_first_div","soccer_austria_bundesliga","soccer_turkey_super_league","soccer_greece_super_league","soccer_denmark_superliga","soccer_sweden_allsvenskan","soccer_norway_eliteserien","soccer_switzerland_superleague","soccer_poland_ekstraklasa","soccer_uefa_champs_league","soccer_uefa_europa_league","soccer_uefa_europa_conference_league"]
UNDERSTAT_LEAGUES = ["EPL","La_liga","Serie_A","Bundesliga","Ligue_1"]
FOOTBALL_DATA_URLS = ["https://www.football-data.co.uk/mmz4281/2526/E0.csv","https://www.football-data.co.uk/mmz4281/2526/E1.csv","https://www.football-data.co.uk/mmz4281/2526/SP1.csv","https://www.football-data.co.uk/mmz4281/2526/I1.csv","https://www.football-data.co.uk/mmz4281/2526/D1.csv","https://www.football-data.co.uk/mmz4281/2526/F1.csv","https://www.football-data.co.uk/mmz4281/2526/N1.csv","https://www.football-data.co.uk/mmz4281/2526/P1.csv","https://www.football-data.co.uk/mmz4281/2526/SC0.csv","https://www.football-data.co.uk/mmz4281/2526/B1.csv","https://www.football-data.co.uk/mmz4281/2526/T1.csv"]

POLISH_ALIASES = {
"real madryt":"Real Madrid","real":"Real Madrid","real madrid":"Real Madrid","atletico bilbao":"Athletic Club","athletic bilbao":"Athletic Club","athletic club":"Athletic Club","atletico madryt":"Atletico Madrid","atletico madrid":"Atletico Madrid","barcelona":"Barcelona","barca":"Barcelona","sevilla":"Sevilla","betis":"Real Betis","real sociedad":"Real Sociedad","valencia":"Valencia","walencja":"Valencia","villarreal":"Villarreal","girona":"Girona","osasuna":"Osasuna","mallorca":"Mallorca","celta":"Celta Vigo","celta vigo":"Celta Vigo",
"torino":"Torino","juventus":"Juventus","inter":"Inter","inter mediolan":"Inter","milan":"AC Milan","ac milan":"AC Milan","roma":"Roma","lazio":"Lazio","napoli":"Napoli","atalanta":"Atalanta","fiorentina":"Fiorentina","bologna":"Bologna","udinese":"Udinese","genoa":"Genoa","verona":"Hellas Verona","lecce":"Lecce","sassuolo":"Sassuolo","cagliari":"Cagliari",
"bayern":"Bayern Munich","bayern monachium":"Bayern Munich","dortmund":"Borussia Dortmund","borussia dortmund":"Borussia Dortmund","rb lipsk":"RB Leipzig","leipzig":"RB Leipzig","bayer leverkusen":"Bayer Leverkusen","leverkusen":"Bayer Leverkusen","eintracht":"Eintracht Frankfurt","wolfsburg":"Wolfsburg","stuttgart":"VfB Stuttgart","freiburg":"SC Freiburg",
"psg":"Paris Saint Germain","paris sg":"Paris Saint Germain","marsylia":"Marseille","marseille":"Marseille","lyon":"Lyon","lens":"Lens","nice":"Nice","nicea":"Nice","monaco":"Monaco","lille":"Lille","rennes":"Rennes","nantes":"Nantes","brest":"Brest",
"manchester city":"Manchester City","man city":"Manchester City","manchester united":"Manchester United","man utd":"Manchester United","arsenal":"Arsenal","liverpool":"Liverpool","chelsea":"Chelsea","tottenham":"Tottenham","spurs":"Tottenham","newcastle":"Newcastle United","aston villa":"Aston Villa","west ham":"West Ham United","brighton":"Brighton","everton":"Everton","wolves":"Wolverhampton Wanderers",
"lech":"Lech Poznan","legia":"Legia Warsaw","rakow":"Rakow Czestochowa","raków":"Rakow Czestochowa","jagiellonia":"Jagiellonia Bialystok","pogon":"Pogon Szczecin","pogoń":"Pogon Szczecin","slask":"Slask Wroclaw","śląsk":"Slask Wroclaw","widzew":"Widzew Lodz","gornik":"Gornik Zabrze"
}

TEAM_BADGE_CACHE = {}
TEXT_CACHE = {}
JSON_CACHE = {}

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, home_team TEXT, away_team TEXT, pick TEXT, probability REAL, fair_odds REAL, bookmaker_odds REAL, value_edge REAL, exact_score TEXT, rating TEXT)')
    con.commit()
    con.close()

init_db()

def esc(x):
    return str(x).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def norm(x):
    return (x or "").lower().replace(" ","").replace("-","").replace(".","").replace("_","").replace("'","").replace("ą","a").replace("ć","c").replace("ę","e").replace("ł","l").replace("ń","n").replace("ó","o").replace("ś","s").replace("ż","z").replace("ź","z")

def normalize_team_name(name):
    raw = (name or "").strip()
    return POLISH_ALIASES.get(raw.lower()) or POLISH_ALIASES.get(norm(raw)) or raw

def match_team(api_name, user_name):
    a, b = norm(api_name), norm(normalize_team_name(user_name))
    if not a or not b:
        return False
    if a == b or b in a or a in b:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.60

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

def http_text(url):
    if url in TEXT_CACHE:
        return TEXT_CACHE[url], None
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0", "Accept":"*/*"})
        with urllib.request.urlopen(req, timeout=5) as response:
            text = response.read().decode("utf-8", errors="ignore")
            TEXT_CACHE[url] = text
            return text, None
    except Exception as e:
        return "", str(e)

def http_json(url):
    if url in JSON_CACHE:
        return JSON_CACHE[url], None
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0", "Accept":"application/json"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8", errors="ignore"))
            JSON_CACHE[url] = data
            return data, None
    except Exception as e:
        return None, str(e)

def get_team_badge(team_name):
    key = norm(team_name)
    if key in TEAM_BADGE_CACHE:
        return TEAM_BADGE_CACHE[key]
    q = urllib.parse.quote(normalize_team_name(team_name))
    data, err = http_json("https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t=" + q)
    badge = ""
    if not err and isinstance(data, dict) and data.get("teams"):
        t = data["teams"][0]
        badge = t.get("strBadge") or t.get("strLogo") or ""
    TEAM_BADGE_CACHE[key] = badge
    return badge

def crest_img(team_name, cls="crest"):
    badge = get_team_badge(team_name)
    if badge:
        return '<img class="' + cls + '" src="' + esc(badge) + '" alt="' + esc(team_name) + '">'
    initials = "".join([p[:1] for p in str(team_name).split()[:2]]).upper() or "QE"
    return '<div class="' + cls + ' crest-fallback">' + esc(initials) + '</div>'

def default_values():
    return {"home_team":"","away_team":"","city":"","xg_home":0,"xg_away":0,"xga_home":0,"xga_away":0,"xg_source":"brak","form_home":0,"form_away":0,"tempo":0,"odds":1.75,"odds_1":0,"odds_x":0,"odds_2":0,"odds_source":"brak","shots_home":0,"shots_away":0,"sot_home":0,"sot_away":0,"corners_home":0,"corners_away":0,"cards_home":0,"cards_away":0,"bookmaker":"Rynek","message":"","sources":"","home_home_matches":"","home_away_matches":"","away_home_matches":"","away_away_matches":"","btts":0,"over25":0,"confidence":0}

def row_has_team(row, team):
    return match_team(row.get("HomeTeam",""), team) or match_team(row.get("AwayTeam",""), team)

def team_side(row, team):
    if match_team(row.get("HomeTeam",""), team):
        return "home"
    if match_team(row.get("AwayTeam",""), team):
        return "away"
    return None

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
    completed = [r for r in rows if row_has_team(r, team) and safe_int(r.get("FTHG")) is not None and safe_int(r.get("FTAG")) is not None][-5:]
    if not completed:
        return None
    pts = gf = ga = shots = sot = corners = cards = 0
    for r in completed:
        side = team_side(r, team)
        hg, ag = safe_int(r.get("FTHG")) or 0, safe_int(r.get("FTAG")) or 0
        if side == "home":
            own, opp = hg, ag
            shots += safe_float(r.get("HS")); sot += safe_float(r.get("HST")); corners += safe_float(r.get("HC")); cards += safe_float(r.get("HY"))
        else:
            own, opp = ag, hg
            shots += safe_float(r.get("AS")); sot += safe_float(r.get("AST")); corners += safe_float(r.get("AC")); cards += safe_float(r.get("AY"))
        gf += own; ga += opp; pts += 3 if own > opp else 1 if own == opp else 0
    n = len(completed)
    return {"form":round((pts/(n*3))*100,1),"gf":round(gf/n,2),"ga":round(ga/n,2),"shots":round(shots/n,1),"sot":round(sot/n,1),"corners":round(corners/n,1),"cards":round(cards/n,1)}

def team_home_away_matches(rows, team):
    home_matches, away_matches = [], []
    for r in rows:
        if safe_int(r.get("FTHG")) is None or safe_int(r.get("FTAG")) is None:
            continue
        ht, at = r.get("HomeTeam",""), r.get("AwayTeam","")
        hg, ag = safe_int(r.get("FTHG")) or 0, safe_int(r.get("FTAG")) or 0
        txt = f"{ht} {hg}:{ag} {at}"
        if match_team(ht, team):
            home_matches.append(txt)
        elif match_team(at, team):
            away_matches.append(txt)
    return {"home":" | ".join(home_matches[-5:]), "away":" | ".join(away_matches[-5:])}

def parse_understat_json_blob(text):
    m = re.search(r"teamsData\s*=\s*JSON\.parse\('(.+?)'\)", text, flags=re.S)
    if not m:
        return None
    try:
        raw = m.group(1).encode("utf-8").decode("unicode_escape")
        return json.loads(html_lib.unescape(raw))
    except Exception:
        return None

def understat_find_team(data, team_name):
    best, best_score = None, 0
    q = normalize_team_name(team_name)
    for _, team in data.items():
        title = team.get("title","")
        score = 1.0 if norm(title) == norm(q) else 0.92 if norm(q) in norm(title) or norm(title) in norm(q) else difflib.SequenceMatcher(None, norm(title), norm(q)).ratio()
        if score > best_score:
            best, best_score = team, score
    return best if best_score >= 0.58 else None

def understat_avg(team):
    hist = team.get("history", [])[-5:]
    if not hist:
        return None
    xg_sum = xga_sum = n = 0
    for item in hist:
        xg, xga = safe_float(item.get("xG")), safe_float(item.get("xGA"))
        if xg == 0 and xga == 0:
            continue
        xg_sum += xg; xga_sum += xga; n += 1
    if n == 0:
        return None
    return {"xg":round(xg_sum/n,2), "xga":round(xga_sum/n,2)}

def understat_team_xg(home_team, away_team):
    result = {"xg_home":0,"xg_away":0,"xga_home":0,"xga_away":0,"source":""}
    for league in UNDERSTAT_LEAGUES:
        text, err = http_text("https://understat.com/league/" + league)
        if err or not text:
            continue
        data = parse_understat_json_blob(text)
        if not data:
            continue
        home_obj, away_obj = understat_find_team(data, home_team), understat_find_team(data, away_team)
        found, src = False, ["Understat " + league]
        if home_obj:
            h = understat_avg(home_obj)
            if h:
                result["xg_home"], result["xga_home"] = h["xg"], h["xga"]; src.append("home: " + home_obj.get("title","")); found = True
        if away_obj:
            a = understat_avg(away_obj)
            if a:
                result["xg_away"], result["xga_away"] = a["xg"], a["xga"]; src.append("away: " + away_obj.get("title","")); found = True
        if found:
            result["source"] = " | ".join(src)
            return result
    return result

def calculate_real_stats(home_team, away_team, city=""):
    v = default_values()
    home, away = normalize_team_name(home_team), normalize_team_name(away_team)
    v["home_team"], v["away_team"], v["city"] = home, away, city
    rows, source = load_football_data_rows(home, away)
    if not rows:
        v["message"] = "Brak realnych statystyk z Football-Data dla tych drużyn."
        v["sources"] = "Football-Data: brak danych"
        return v
    h, a = team_stats_from_rows(rows, home), team_stats_from_rows(rows, away)
    if h:
        v["form_home"], v["shots_home"], v["sot_home"], v["corners_home"], v["cards_home"] = h["form"], h["shots"], h["sot"], h["corners"], h["cards"]
    if a:
        v["form_away"], v["shots_away"], v["sot_away"], v["corners_away"], v["cards_away"] = a["form"], a["shots"], a["sot"], a["corners"], a["cards"]
    uxg = understat_team_xg(home, away)
    v["xg_home"], v["xg_away"], v["xga_home"], v["xga_away"] = uxg["xg_home"], uxg["xg_away"], uxg["xga_home"], uxg["xga_away"]
    v["xg_source"] = uxg["source"] or "Understat: brak xG"
    sp_h, sp_a = team_home_away_matches(rows, home), team_home_away_matches(rows, away)
    v["home_home_matches"], v["home_away_matches"], v["away_home_matches"], v["away_away_matches"] = sp_h["home"], sp_h["away"], sp_a["home"], sp_a["away"]
    total_shots = float(v["shots_home"]) + float(v["shots_away"])
    total_sot = float(v["sot_home"]) + float(v["sot_away"])
    v["tempo"] = 62 if total_shots >= 25 or total_sot >= 9 else 43 if total_shots > 0 else 0
    v["btts"], v["over25"], v["confidence"] = (55, 50, 70) if h and a else (0, 0, 35)
    v["message"] = "Realne statystyki Football-Data + " + ("realne xG Understat." if (v["xg_home"] or v["xg_away"]) else "xG = 0, bo Understat nie znalazł danych.")
    v["sources"] = "Football-Data " + source + " | " + v["xg_source"]
    return v

def fetch_odds_api(home_team, away_team, bookmaker):
    home, away = normalize_team_name(home_team), normalize_team_name(away_team)
    for sport_key in SPORT_KEYS:
        url = "https://api.the-odds-api.com/v4/sports/" + sport_key + "/odds/?" + urllib.parse.urlencode({"apiKey":ODDS_API_KEY, "regions":"eu,uk", "markets":"h2h", "oddsFormat":"decimal"})
        data, err = http_json(url)
        if err or not isinstance(data, list):
            continue
        for event in data:
            api_home, api_away = event.get("home_team",""), event.get("away_team","")
            direct = match_team(api_home, home) and match_team(api_away, away)
            reverse = match_team(api_home, away) and match_team(api_away, home)
            if not direct and not reverse:
                continue
            candidates = []
            for book in event.get("bookmakers", []):
                for market in book.get("markets", []):
                    if market.get("key") != "h2h":
                        continue
                    out = {"home":None, "draw":None, "away":None}
                    for o in market.get("outcomes", []):
                        name, price = o.get("name",""), o.get("price")
                        if price is None:
                            continue
                        if name == api_home: out["home"] = float(price)
                        elif name == api_away: out["away"] = float(price)
                        elif name.lower() == "draw": out["draw"] = float(price)
                    if out["home"] and out["draw"] and out["away"]:
                        candidates.append(out)
            if candidates:
                best = {"home":max(c["home"] for c in candidates), "draw":max(c["draw"] for c in candidates), "away":max(c["away"] for c in candidates)}
                if reverse:
                    best["home"], best["away"] = best["away"], best["home"]
                return {"ok":True,"odds_1":round(best["home"],2),"odds_x":round(best["draw"],2),"odds_2":round(best["away"],2),"source":"The Odds API / rynek","api_home":api_home,"api_away":api_away}
    return {"ok":False,"error":"Nie znaleziono meczu/kursów."}

def fetch_odds(home_team, away_team, bookmaker):
    v = default_values()
    v["home_team"], v["away_team"], v["bookmaker"] = normalize_team_name(home_team), normalize_team_name(away_team), bookmaker
    res = fetch_odds_api(home_team, away_team, bookmaker)
    if res.get("ok"):
        v["odds_1"], v["odds_x"], v["odds_2"], v["odds"] = res["odds_1"], res["odds_x"], res["odds_2"], res["odds_1"]
        v["odds_source"], v["message"], v["sources"] = res["source"], "Kursy pobrane. Dopasowany mecz: " + res.get("api_home","") + " vs " + res.get("api_away",""), res["source"]
        return v
    v["message"], v["sources"] = "Nie pobrano kursów: " + res.get("error",""), "The Odds API"
    return v

def current_values_from_form(**kwargs):
    v = default_values()
    for k, val in kwargs.items():
        if k in v:
            v[k] = val
    return v

STAT_KEYS = ["home_team","away_team","city","xg_home","xg_away","xga_home","xga_away","xg_source","form_home","form_away","tempo","shots_home","shots_away","sot_home","sot_away","corners_home","corners_away","cards_home","cards_away","btts","over25","confidence","message","sources","home_home_matches","home_away_matches","away_home_matches","away_away_matches"]
ODDS_KEYS = ["home_team","away_team","bookmaker","odds","odds_1","odds_x","odds_2","odds_source","message","sources"]

def merge_section(base, update, keys):
    merged = dict(base)
    for k in keys:
        if k in update:
            merged[k] = update[k]
    return merged

def clamp(value, low=0, high=100):
    try: value = float(value)
    except Exception: value = 0
    return max(low, min(high, value))

def fair_odds(probability):
    return round(100 / probability, 2) if probability > 0 else 0

def value_edge(probability, odds):
    return round(probability - (100 / odds), 2) if odds > 1 else 0

def data_confidence_engine(v):
    score = 0
    if float(v.get("xg_home",0) or 0) or float(v.get("xg_away",0) or 0): score += 30
    if float(v.get("shots_home",0) or 0) and float(v.get("shots_away",0) or 0): score += 20
    if float(v.get("odds_1",0) or 0) > 1 and float(v.get("odds_x",0) or 0) > 1 and float(v.get("odds_2",0) or 0) > 1: score += 20
    if float(v.get("form_home",0) or 0) and float(v.get("form_away",0) or 0): score += 15
    if float(v.get("tempo",0) or 0): score += 15
    label = "HIGH" if score >= 75 else "MEDIUM" if score >= 50 else "LOW"
    return {"score":score, "label":label}

def flow_engine(v):
    xg_total = float(v.get("xg_home",0) or 0) + float(v.get("xg_away",0) or 0)
    shots_total = float(v.get("shots_home",0) or 0) + float(v.get("shots_away",0) or 0)
    sot_total = float(v.get("sot_home",0) or 0) + float(v.get("sot_away",0) or 0)
    corners_total = float(v.get("corners_home",0) or 0) + float(v.get("corners_away",0) or 0)
    cards_total = float(v.get("cards_home",0) or 0) + float(v.get("cards_away",0) or 0)
    tempo = float(v.get("tempo",0) or 0)
    form_gap = abs(float(v.get("form_home",0) or 0)-float(v.get("form_away",0) or 0))
    control = 55
    if xg_total and xg_total <= 2.3: control += 12
    if shots_total and shots_total <= 22: control += 8
    if tempo and tempo <= 50: control += 8
    if form_gap <= 15: control += 5
    if cards_total >= 5: control -= 8
    if corners_total >= 11: control -= 5
    chaos = 100 - control
    if sot_total >= 9: chaos += 8
    if cards_total >= 5: chaos += 8
    if corners_total >= 11: chaos += 5
    return {"control":round(clamp(control),1),"chaos":round(clamp(chaos),1),"draw":round(clamp(65-form_gap*0.8-max(0,xg_total-2.4)*8),1),"collapse_home":round(clamp(38+float(v.get("cards_home",0) or 0)*6-float(v.get("form_home",0) or 0)*0.12),1),"collapse_away":round(clamp(42+float(v.get("cards_away",0) or 0)*6-float(v.get("form_away",0) or 0)*0.12),1),"transition_home":round(clamp(45+float(v.get("shots_home",0) or 0)*1.6+float(v.get("sot_home",0) or 0)*2.2),1),"transition_away":round(clamp(45+float(v.get("shots_away",0) or 0)*1.6+float(v.get("sot_away",0) or 0)*2.2),1)}

def exact_score_engine(v, flow):
    xh, xa = float(v.get("xg_home",0) or 0), float(v.get("xg_away",0) or 0)
    note = "Wynik z realnego xG i flow."
    if xh == 0 and xa == 0:
        fh, fa, sh, sa = float(v.get("form_home",0) or 0), float(v.get("form_away",0) or 0), float(v.get("shots_home",0) or 0), float(v.get("shots_away",0) or 0)
        soth, sota = float(v.get("sot_home",0) or 0), float(v.get("sot_away",0) or 0)
        o1, o2 = float(v.get("odds_1",0) or 0), float(v.get("odds_2",0) or 0)
        xh = max(0.45, min(2.6, ((fh*.035)+(sh*.09)+(soth*.22)+(max(0,3.2-o1)*.25 if o1>1 else 0))/3.2))
        xa = max(0.35, min(2.4, ((fa*.035)+(sa*.09)+(sota*.22)+(max(0,3.2-o2)*.25 if o2>1 else 0))/3.2))
        note = "Brak xG — wynik z formy/strzałów/kursów."
    diff, total = xh-xa, xh+xa
    if flow["chaos"] >= 64 or float(v.get("tempo",0) or 0) >= 60:
        if diff >= .45: return {"control":"2:1","value":"3:1","chaos":"3:2","note":note}
        if diff <= -.45: return {"control":"1:2","value":"1:3","chaos":"2:3","note":note}
        return {"control":"1:1","value":"2:2","chaos":"3:2 / 2:3","note":note}
    if diff >= .55: return {"control":"1:0 / 2:0","value":"2:1","chaos":"3:1","note":note}
    if diff <= -.55: return {"control":"0:1 / 0:2","value":"1:2","chaos":"1:3","note":note}
    if total <= 2.2: return {"control":"1:1 / 0:0","value":"1:0 / 0:1","chaos":"2:1 / 1:2","note":note}
    return {"control":"1:1","value":"2:1 / 1:2","chaos":"2:2","note":note}

def calculate_model(v):
    fh, fa = float(v.get("form_home",0) or 0), float(v.get("form_away",0) or 0)
    odds = float(v.get("odds",1.75) or 1.75)
    flow = flow_engine(v)
    prob = round(max(1, min(95, 35 + ((fh+fa)/2)*0.22 + (100-flow["chaos"])*0.22)), 1)
    edge = value_edge(prob, odds)
    if odds >= 4.5 and prob >= 60:
        prob, edge, rating = 55.0, value_edge(55, odds), "⚠️ MARKET CONFLICT"
    elif edge > 5 and prob >= 60:
        rating = "TOP VALUE"
    elif edge > 0 and prob >= 57:
        rating = "LEKKIE VALUE"
    else:
        rating = "BRAK VALUE"
    pick = "1X" if fh >= fa else "X2"
    exact = exact_score_engine(v, flow)
    return {"pick":pick,"probability":prob,"fair_odds":fair_odds(prob),"value_edge":edge,"rating":rating,"exact_score":exact["control"],"chaos":flow["chaos"],"warnings":[]}

def bar(label, value, cls=""):
    return f'<div class="bar-row"><div class="bar-label">{esc(label)} <b>{round(clamp(value),1)}%</b></div><div class="bar-bg"><div class="bar-fill {cls}" style="width:{clamp(value)}%"></div></div></div>'

def history_rows():
    con = sqlite3.connect(DB_PATH); cur = con.cursor()
    cur.execute("SELECT id, created_at, home_team, away_team, pick, probability, fair_odds, bookmaker_odds, value_edge, exact_score, rating FROM analyses ORDER BY id DESC LIMIT 100")
    rows = cur.fetchall(); con.close(); return rows

CSS = """
<style>
*{box-sizing:border-box}
body{margin:0;background:#000;color:#f3f8ff;font-family:Inter,Arial,Helvetica,sans-serif;font-size:14px}
.shell{display:grid;grid-template-columns:260px minmax(720px,1fr) 330px 360px;min-height:100vh;background:radial-gradient(circle at top,#06172a 0,#02070e 52%,#000 100%)}
.side{background:linear-gradient(180deg,#04111e,#02060b);border-right:1px solid #12324f;padding:18px;position:sticky;top:0;height:100vh;overflow:auto}
.main{padding:16px;max-width:1120px}
.right{padding:16px;border-left:1px solid #12324f;background:rgba(4,11,20,.94);overflow:auto}
.leaguebar{padding:16px;border-left:1px solid #12324f;background:rgba(3,9,17,.96);overflow:auto}
.logo{font-size:24px;font-weight:900;line-height:1.05;margin-bottom:18px;color:#fff;letter-spacing:.5px}
.logo span{color:#00c8ff;display:block}
.nav a{display:flex;align-items:center;gap:10px;color:#dbe9ff;text-decoration:none;padding:12px;border:1px solid #14304d;border-radius:9px;margin-bottom:8px;background:rgba(8,20,36,.55)}
.nav a:hover,.nav a:first-child{border-color:#00a6ff;background:rgba(0,136,255,.16);color:#42cfff}
.api{font-size:12px;color:#9fb0c8;line-height:1.8;margin-top:14px}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#21dc37;margin-right:8px;box-shadow:0 0 8px #21dc37}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;border-bottom:1px solid #102d49;padding-bottom:10px}.title{font-size:28px;font-weight:900}
.card,.hero,.v20-hero,.sidebox{background:linear-gradient(180deg,rgba(7,18,33,.96),rgba(2,9,18,.96));border:1px solid #153754;border-radius:10px;padding:14px;margin-bottom:12px;box-shadow:0 14px 36px rgba(0,0,0,.38)}
.hero h1{margin:5px 0 6px;font-size:24px}.label{color:#41c8ff;font-weight:900;font-size:12px;letter-spacing:.5px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.sideform{display:grid;grid-template-columns:1fr;gap:8px}
label{display:flex;flex-direction:column;gap:6px;color:#aebcd0;font-size:12px}
input,select{width:100%;padding:10px;border-radius:8px;border:1px solid #244260;background:#020812;color:white;font-size:13px}
.actions{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:12px}.sideactions{display:grid;grid-template-columns:1fr;gap:8px;margin-top:10px}
.btn{border:0;border-radius:8px;padding:11px;font-size:13px;font-weight:900;cursor:pointer;text-transform:uppercase}
.blue{background:linear-gradient(180deg,#0879ff,#034baf);color:#fff}.green{background:linear-gradient(180deg,#16c958,#068832);color:#fff}.purple{background:linear-gradient(180deg,#7e3be8,#5124a2);color:#fff}
.match-card{text-align:left}.match-title{font-size:24px;font-weight:900;display:flex;align-items:center;justify-content:space-between;gap:14px}.match-mid{display:flex;align-items:center;justify-content:center;gap:14px}.vs{color:#9ab2cd;font-size:16px}
.crest{width:52px;height:52px;object-fit:contain;filter:drop-shadow(0 0 10px rgba(0,166,255,.35))}.bigcrest{width:64px;height:64px;object-fit:contain;filter:drop-shadow(0 0 12px rgba(0,166,255,.45))}
.crest-fallback{display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background:#0b1b2d;border:1px solid #234866;color:#91ff36;font-weight:900}
.v20-kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:12px}.v20-kpis div,.stat div{background:#030b15;border:1px solid #14324f;border-radius:8px;padding:10px;text-align:center}.v20-kpis small,.stat span{display:block;color:#8fa3bb;margin-bottom:5px;font-size:11px}.v20-kpis strong{color:#91ff36;font-size:18px}
.flow-cards{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.flow-tile{border:1px solid #234866;border-radius:8px;padding:10px;text-align:center;background:#03101d}.flow-tile b{font-size:30px;display:block;margin:4px 0}.flow-tile.green b{color:#52ff47}.flow-tile.red b{color:#ff4f6d}.flow-tile.purple b{color:#b566ff}.flow-tile.orange b{color:#ffc13b}.flow-tile.blue b{color:#49a7ff}.flow-tile small{font-size:10px;color:#cbd8e9}
.bar-row{margin:10px 0}.bar-label{display:flex;justify-content:space-between;color:#dbe9fa;font-size:12px;margin-bottom:5px}.bar-bg{height:9px;border-radius:999px;background:#07101d;border:1px solid #203d5c;overflow:hidden}.bar-fill{height:100%;background:#29dd34}.bar-fill.red{background:#ff4f6d}.bar-fill.orange{background:#ffb347}.bar-fill.blue{background:#49a7ff}.bar-fill.purple{background:#b566ff}
.score-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}.score{background:#030b15;border:1px solid #14324f;border-radius:9px;padding:16px;text-align:center}.score small{color:#92a4bc;font-size:11px}.score b{display:block;font-size:38px;color:#52ff47;margin-top:8px}.score.value b{color:#ffc13b}.score.chaos b{color:#ff4f6d}
.market-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.market-grid div{background:#030b15;border:1px solid #14324f;border-radius:8px;padding:9px;text-align:center}.market-grid small{color:#8fa3bb;font-size:11px}.market-grid b{display:block;color:#52ff47;margin-top:5px}
.stat{display:grid;grid-template-columns:1fr 1fr;gap:8px}.mini{background:#030b15;border:1px solid #14324f;border-radius:9px;padding:10px;margin-bottom:9px;color:#d8e6f7;font-size:12px}.mini b{color:#91ff36}.hist-row{display:grid;grid-template-columns:1fr 2fr 1fr 1fr 1fr;gap:8px;background:#030b15;padding:9px;border-radius:9px;margin-bottom:7px}.muted{color:#adbbcf;line-height:1.45}
.teamline{display:grid;grid-template-columns:62px 1fr;gap:10px;align-items:center;margin-bottom:10px}.teamline h3{margin:0;color:#49a7ff}.teamline p{margin:3px 0 0;color:#b8c7da}
.league-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.league-card{text-align:center;background:#030b15;border:1px solid #14324f;border-radius:9px;padding:10px;min-height:88px}.league-logo{font-size:28px;display:block;margin-bottom:6px}.league-card b{display:block;font-size:11px}.league-card small{color:#8fa3bb;font-size:10px}.team-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.team-card{text-align:center}.team-card .crest{width:42px;height:42px}.team-card small{display:block;color:#d8e6f7;font-size:10px}.quick-logos{display:flex;align-items:center;justify-content:space-around;margin:10px 0}.quick-logos .crest{width:48px;height:48px}
@media(max-width:1250px){.shell{grid-template-columns:240px minmax(620px,1fr) 300px}.leaguebar{display:none}}
@media(max-width:950px){.shell{display:block}.side,.right,.leaguebar{position:relative;height:auto;border:0}.main{padding:12px}.form-grid,.actions,.v20-kpis,.flow-cards,.score-grid,.stat,.hist-row,.market-grid,.league-grid,.team-grid{grid-template-columns:1fr}.title{font-size:24px}.match-title{font-size:22px}.bigcrest{width:54px;height:54px}}
</style>
"""

def stat_block(v):
    return f'<div class="stat"><div><span>xG</span><b>{v["xg_home"]} - {v["xg_away"]}</b></div><div><span>xGA</span><b>{v["xga_home"]} - {v["xga_away"]}</b></div><div><span>Forma</span><b>{v["form_home"]} - {v["form_away"]}</b></div><div><span>Kursy</span><b>{v["odds_1"]} / {v["odds_x"]} / {v["odds_2"]}</b></div><div><span>Strzały</span><b>{v["shots_home"]} - {v["shots_away"]}</b></div><div><span>Celne</span><b>{v["sot_home"]} - {v["sot_away"]}</b></div><div><span>Rożne</span><b>{v["corners_home"]} - {v["corners_away"]}</b></div><div><span>Kartki</span><b>{v["cards_home"]} - {v["cards_away"]}</b></div></div>'

def hidden(v):
    keys = ["xg_home","xg_away","xga_home","xga_away","xg_source","form_home","form_away","tempo","odds","odds_1","odds_x","odds_2","shots_home","shots_away","sot_home","sot_away","corners_home","corners_away","cards_home","cards_away","odds_source","home_home_matches","home_away_matches","away_home_matches","away_away_matches"]
    return "".join([f'<input type="hidden" name="{k}" value="{esc(v.get(k,""))}">' for k in keys])


def leagues_sidebar():
    leagues = [
        ("🏴", "Premier League", "England"), ("🇪🇸", "La Liga", "Spain"), ("🇩🇪", "Bundesliga", "Germany"), ("🇮🇹", "Serie A", "Italy"),
        ("🇫🇷", "Ligue 1", "France"), ("🇳🇱", "Eredivisie", "Netherlands"), ("🇵🇹", "Primeira Liga", "Portugal"), ("🇧🇪", "Jupiler Pro League", "Belgium"),
        ("🇹🇷", "Süper Lig", "Turkey"), ("🏴", "Premiership", "Scotland"), ("🇸🇪", "Allsvenskan", "Sweden"), ("🇳🇴", "Eliteserien", "Norway"),
        ("🇵🇱", "Ekstraklasa", "Poland"), ("🇨🇿", "Czech Liga", "Czechia"), ("🇦🇹", "Bundesliga", "Austria"), ("🇩🇰", "Superliga", "Denmark"),
        ("🇨🇭", "Super League", "Switzerland"), ("🇬🇷", "Super League", "Greece"), ("🇭🇷", "HNL", "Croatia"), ("🇷🇸", "SuperLiga", "Serbia"),
        ("🇷🇴", "Liga I", "Romania"), ("🇧🇬", "First League", "Bulgaria"), ("🇺🇦", "Premier League", "Ukraine"), ("🇸🇰", "Super Liga", "Slovakia"),
        ("🇭🇺", "NB I", "Hungary"), ("🇫🇮", "Veikkausliiga", "Finland"), ("🇮🇪", "Premier Division", "Ireland"), ("🇮🇸", "Besta deild", "Iceland")
    ]
    teams = ["Manchester City","Real Madrid","Bayern Munich","Paris Saint Germain","Manchester United","Barcelona","Liverpool","Juventus","AC Milan","Arsenal"]
    out = '<aside class="leaguebar">'
    out += '<div class="card"><h2>Leagues</h2><div class="league-grid">'
    for icon, name, country in leagues:
        out += f'<div class="league-card"><span class="league-logo">{icon}</span><b>{esc(name)}</b><small>{esc(country)}</small></div>'
    out += '</div><p class="muted">Dodana wizualna baza lig Europy: poziom 1, 2 i 3. Herby drużyn pobierane z TheSportsDB.</p></div>'
    out += '<div class="card"><h2>Popular Teams</h2><div class="team-grid">'
    for t in teams:
        out += f'<div class="team-card">{crest_img(t)}<small>{esc(t)}</small></div>'
    out += '</div></div></aside>'
    return out

def dashboard(v, result=None, hist=False):
    if result is None:
        result = calculate_model(v) if (v.get("home_team") or v.get("away_team")) else None
    flow = flow_engine(v)
    exact = exact_score_engine(v, flow)
    conf = data_confidence_engine(v)
    hist_html = ""
    if hist:
        rows = history_rows()
        hist_html = '<div class="card"><h2>Analysis History</h2>'
        if not rows:
            hist_html += '<p class="muted">Historia jest pusta. Kliknij „Analizuj”, żeby zapisać analizę.</p>'
        for r in rows:
            hist_html += f'<div class="hist-row"><span>{esc(r[1])}</span><span>{esc(r[2])} vs {esc(r[3])}</span><span>{esc(r[4])}</span><span>{r[5]}%</span><span>{esc(r[10])}</span></div>'
        hist_html += '</div>'
    result_html = ""
    if result:
        result_html = f'<div class="v20-hero match-card"><div class="match-title">{crest_img(v["home_team"], "bigcrest")} <span>{esc(v["home_team"])}</span> <span class="vs">VS</span> <span>{esc(v["away_team"])}</span> {crest_img(v["away_team"], "bigcrest")}</div><div class="v20-kpis"><div><small>TIP</small><strong>{esc(result["pick"])}</strong></div><div><small>PROBABILITY</small><strong>{result["probability"]}%</strong></div><div><small>VALUE EDGE</small><strong>{result["value_edge"]} pp</strong></div><div><small>RATING</small><strong>{esc(result["rating"])}</strong></div><div><small>DATA QUALITY</small><strong>{conf["label"]} {conf["score"]}/100</strong></div></div></div>'
    form = f'<div class="card"><h2>Match Search</h2><form action="/fetch" method="post"><div class="form-grid"><label>Gospodarz<input name="home_team" value="{esc(v["home_team"])}" placeholder="Real Madryt"></label><label>Gość<input name="away_team" value="{esc(v["away_team"])}" placeholder="Atletico Bilbao"></label><label>Miasto<input name="city" value="{esc(v["city"])}" placeholder="Madryt"></label><label>Źródło / bukmacher<select name="bookmaker"><option>Rynek</option><option>bet365</option><option>STS</option><option>Betclic</option><option>Superbet</option></select></label></div>{hidden(v)}<div class="actions"><button class="btn blue" name="mode" value="stats">⚡ GET STATS</button><button class="btn green" name="mode" value="odds">💰 GET ODDS</button><button class="btn purple" formaction="/analyze" name="mode" value="analyze">🔥 ANALYZE</button></div></form></div>'
    main_html = f'<main class="main"><div class="top"><div class="title">Quantum Edge v24</div><div class="muted">LIVE CLOCK&nbsp; {datetime.now().strftime("%H:%M:%S")}</div></div><div class="hero"><div class="label">PROFESSIONAL AI DASHBOARD</div><h1>Flow Engine / Exact Score / Market Intelligence</h1><p class="muted">Układ jak terminal: desktop + mobile, herby drużyn z TheSportsDB, szybsze pobieranie.</p></div>{hist_html}{result_html}<div class="card"><h2>Flow Engine 2.0</h2><div class="flow-cards"><div class="flow-tile green"><small>CONTROL FLOW</small><b>{flow["control"]}</b></div><div class="flow-tile red"><small>CHAOS FLOW</small><b>{flow["chaos"]}</b></div><div class="flow-tile purple"><small>TRANSITION</small><b>{max(flow["transition_home"], flow["transition_away"])}</b></div><div class="flow-tile orange"><small>COLLAPSE</small><b>{max(flow["collapse_home"], flow["collapse_away"])}</b></div><div class="flow-tile blue"><small>DRAW</small><b>{flow["draw"]}</b></div></div></div><div class="card"><h2>Exact Score Engine 2.0</h2><div class="score-grid"><div class="score"><small>CONTROL SCENARIO</small><b>{exact["control"]}</b></div><div class="score value"><small>VALUE SCENARIO</small><b>{exact["value"]}</b></div><div class="score chaos"><small>CHAOS SCENARIO</small><b>{exact["chaos"]}</b></div></div><p class="muted">{esc(exact["note"])}</p></div><div class="card"><h2>Market Intelligence</h2><div class="market-grid"><div><small>FAIR ODDS</small><b>{result["fair_odds"] if result else 0}</b></div><div><small>BEST ODDS</small><b>{v["odds"]}</b></div><div><small>VALUE EDGE</small><b>{result["value_edge"] if result else 0} pp</b></div><div><small>CLV</small><b>watch</b></div><div><small>TRAP ALERT</small><b>{"LOW" if conf["label"] == "HIGH" else "CHECK"}</b></div></div></div><div class="card"><h2>Key Match Data</h2><p class="muted">{esc(v["message"])}</p><p class="muted">Źródła: {esc(v["sources"])}</p>{stat_block(v)}</div>{form}</main>'
    right_html = f'<aside class="right"><div class="card"><h2>Team Profiles</h2><div class="teamline">{crest_img(v["home_team"] or "Home")}<div><h3>{esc(v["home_team"] or "Gospodarz")}</h3><p>Control / Transition profile</p></div></div>{bar("Control", flow["control"])}{bar("Transition", flow["transition_home"], "purple")}{bar("Chaos", flow["chaos"], "red")}<div class="teamline">{crest_img(v["away_team"] or "Away")}<div><h3>{esc(v["away_team"] or "Gość")}</h3><p>Chaos / Reactive profile</p></div></div>{bar("Transition", flow["transition_away"], "purple")}{bar("Collapse", flow["collapse_away"], "orange")}</div><div class="card"><h2>xG / xGA</h2><div class="mini"><b>{esc(v["home_team"] or "Home")}</b><br>xG {v["xg_home"]} / xGA {v["xga_home"]}</div><div class="mini"><b>{esc(v["away_team"] or "Away")}</b><br>xG {v["xg_away"]} / xGA {v["xga_away"]}</div><p class="muted">{esc(v["xg_source"])}</p></div><div class="card"><h2>Last Matches</h2><div class="mini"><b>H-H</b><br>{esc(v["home_home_matches"] or "brak danych")}</div><div class="mini"><b>H-A</b><br>{esc(v["home_away_matches"] or "brak danych")}</div><div class="mini"><b>A-H</b><br>{esc(v["away_home_matches"] or "brak danych")}</div><div class="mini"><b>A-A</b><br>{esc(v["away_away_matches"] or "brak danych")}</div></div></aside>'
    side_html = f"""
      <aside class="side">
        <div class="logo">⚡ QUANTUM <span>EDGE</span></div>
        <div class="nav"><a href="/">🏠 Dashboard</a><a href="/">🔴 Live</a><a href="/history">↺ History</a><a href="/">🔎 Value Finder</a><a href="/">🏆 Leagues</a><a href="/">⚙ Settings</a></div>
        <div class="sidebox"><h3>Match Search</h3>
          <form action="/fetch" method="post" class="sideform">
            <label>Home<input name="home_team" value="{esc(v["home_team"])}" placeholder="Search teams..."></label>
            <label>Away<input name="away_team" value="{esc(v["away_team"])}" placeholder="Away team..."></label>
            <label>City<input name="city" value="{esc(v["city"])}" placeholder="City"></label>
            {hidden(v)}
            <div class="sideactions"><button class="btn blue" name="mode" value="stats">⚡ GET STATS</button><button class="btn green" name="mode" value="odds">💰 GET ODDS</button><button class="btn purple" formaction="/analyze" name="mode" value="analyze">🔥 ANALYZE</button></div>
          </form>
        </div>
        <div class="sidebox"><h3>Quick Stats</h3><div class="quick-logos">{crest_img(v["home_team"] or "Home")} {crest_img(v["away_team"] or "Away")}</div><div class="mini">Data Quality: <b>{conf["label"]} {conf["score"]}/100</b></div><div class="mini">xG: <b>{v["xg_home"]} - {v["xg_away"]}</b></div><div class="mini">Form: <b>{v["form_home"]} - {v["form_away"]}</b></div></div>
        <div class="api"><div><span class="dot"></span>Odds API</div><div><span class="dot"></span>Understat</div><div><span class="dot"></span>Football-Data</div><div><span class="dot"></span>TheSportsDB badges</div><div>Model: v24</div></div>
      </aside>
    """
    return f'<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Quantum Edge v24</title><meta name="viewport" content="width=device-width,initial-scale=1">{CSS}</head><body><div class="shell">{side_html}{main_html}{right_html}{leagues_sidebar()}</div></body></html>' 

@app.get("/", response_class=HTMLResponse)
def home():
    return dashboard(default_values())

@app.get("/history", response_class=HTMLResponse)
def history():
    return dashboard(default_values(), hist=True)

@app.post("/fetch", response_class=HTMLResponse)
def fetch(home_team: str = Form(""), away_team: str = Form(""), city: str = Form(""), bookmaker: str = Form("Rynek"), mode: str = Form("stats"), xg_home: float = Form(0), xg_away: float = Form(0), xga_home: float = Form(0), xga_away: float = Form(0), xg_source: str = Form("brak"), form_home: float = Form(0), form_away: float = Form(0), tempo: float = Form(0), odds: float = Form(1.75), odds_1: float = Form(0), odds_x: float = Form(0), odds_2: float = Form(0), shots_home: float = Form(0), shots_away: float = Form(0), sot_home: float = Form(0), sot_away: float = Form(0), corners_home: float = Form(0), corners_away: float = Form(0), cards_home: float = Form(0), cards_away: float = Form(0), odds_source: str = Form("brak"), home_home_matches: str = Form(""), home_away_matches: str = Form(""), away_home_matches: str = Form(""), away_away_matches: str = Form("")):
    current = current_values_from_form(**locals())
    if mode == "odds":
        update = fetch_odds(home_team, away_team, bookmaker)
        v = merge_section(current, update, ODDS_KEYS)
    else:
        update = calculate_real_stats(home_team, away_team, city)
        v = merge_section(current, update, STAT_KEYS)
    v["bookmaker"] = bookmaker
    return dashboard(v)

@app.post("/analyze", response_class=HTMLResponse)
def analyze(home_team: str = Form(""), away_team: str = Form(""), city: str = Form(""), bookmaker: str = Form("Rynek"), xg_home: float = Form(0), xg_away: float = Form(0), xga_home: float = Form(0), xga_away: float = Form(0), xg_source: str = Form("brak"), form_home: float = Form(0), form_away: float = Form(0), tempo: float = Form(0), odds: float = Form(1.75), odds_1: float = Form(0), odds_x: float = Form(0), odds_2: float = Form(0), shots_home: float = Form(0), shots_away: float = Form(0), sot_home: float = Form(0), sot_away: float = Form(0), corners_home: float = Form(0), corners_away: float = Form(0), cards_home: float = Form(0), cards_away: float = Form(0), odds_source: str = Form("brak"), home_home_matches: str = Form(""), home_away_matches: str = Form(""), away_home_matches: str = Form(""), away_away_matches: str = Form("")):
    v = current_values_from_form(**locals())
    result = calculate_model(v)
    con = sqlite3.connect(DB_PATH); cur = con.cursor()
    cur.execute("INSERT INTO analyses (created_at, home_team, away_team, pick, probability, fair_odds, bookmaker_odds, value_edge, exact_score, rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (datetime.now().strftime("%Y-%m-%d %H:%M"), home_team, away_team, result["pick"], result["probability"], result["fair_odds"], odds, result["value_edge"], result["exact_score"], result["rating"]))
    con.commit(); con.close()
    return dashboard(v, result=result)
