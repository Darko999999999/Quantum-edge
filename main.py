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
import html as html_lib

app = FastAPI(title="Quantum Edge v21")

DB_PATH = "quantum_edge.db"
ODDS_API_KEY = "4235b3c48084bdd173789f88b6ddadfd"

SPORT_KEYS = [
    "soccer_epl", "soccer_england_championship", "soccer_spain_la_liga",
    "soccer_italy_serie_a", "soccer_germany_bundesliga",
    "soccer_france_ligue_one", "soccer_france_ligue_two",
    "soccer_netherlands_eredivisie", "soccer_portugal_primeira_liga",
    "soccer_scotland_premiership", "soccer_belgium_first_div",
    "soccer_austria_bundesliga", "soccer_turkey_super_league",
    "soccer_greece_super_league", "soccer_denmark_superliga",
    "soccer_sweden_allsvenskan", "soccer_norway_eliteserien",
    "soccer_switzerland_superleague", "soccer_poland_ekstraklasa",
    "soccer_uefa_champs_league", "soccer_uefa_europa_league",
    "soccer_uefa_europa_conference_league"
]

UNDERSTAT_LEAGUES = ["EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1"]

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

ALIASES = {
    "real madryt": "Real Madrid", "real": "Real Madrid", "real madrid": "Real Madrid",
    "atletico bilbao": "Athletic Club", "athletic bilbao": "Athletic Club", "athletic club": "Athletic Club",
    "atletico madryt": "Atletico Madrid", "atletico madrid": "Atletico Madrid",
    "barcelona": "Barcelona", "barca": "Barcelona", "sevilla": "Sevilla", "betis": "Real Betis",
    "real sociedad": "Real Sociedad", "valencia": "Valencia", "walencja": "Valencia",
    "villarreal": "Villarreal", "girona": "Girona", "osasuna": "Osasuna", "mallorca": "Mallorca",
    "celta": "Celta Vigo", "celta vigo": "Celta Vigo",

    "torino": "Torino", "juventus": "Juventus", "inter": "Inter", "inter mediolan": "Inter",
    "milan": "AC Milan", "ac milan": "AC Milan", "roma": "Roma", "lazio": "Lazio",
    "napoli": "Napoli", "atalanta": "Atalanta", "fiorentina": "Fiorentina", "bologna": "Bologna",
    "udinese": "Udinese", "genoa": "Genoa", "verona": "Hellas Verona", "lecce": "Lecce",

    "bayern": "Bayern Munich", "bayern monachium": "Bayern Munich",
    "dortmund": "Borussia Dortmund", "borussia dortmund": "Borussia Dortmund",
    "rb lipsk": "RB Leipzig", "leipzig": "RB Leipzig", "bayer leverkusen": "Bayer Leverkusen",
    "leverkusen": "Bayer Leverkusen", "eintracht": "Eintracht Frankfurt",
    "wolfsburg": "Wolfsburg", "stuttgart": "VfB Stuttgart", "freiburg": "SC Freiburg",

    "psg": "Paris Saint Germain", "paris sg": "Paris Saint Germain",
    "marsylia": "Marseille", "marseille": "Marseille", "lyon": "Lyon",
    "lens": "Lens", "nice": "Nice", "nicea": "Nice", "monaco": "Monaco",
    "lille": "Lille", "rennes": "Rennes", "nantes": "Nantes", "brest": "Brest",

    "manchester city": "Manchester City", "man city": "Manchester City",
    "manchester united": "Manchester United", "man utd": "Manchester United",
    "arsenal": "Arsenal", "liverpool": "Liverpool", "chelsea": "Chelsea",
    "tottenham": "Tottenham", "spurs": "Tottenham", "newcastle": "Newcastle United",
    "aston villa": "Aston Villa", "west ham": "West Ham United", "brighton": "Brighton",
    "everton": "Everton", "wolves": "Wolverhampton Wanderers",

    "lech": "Lech Poznan", "legia": "Legia Warsaw", "rakow": "Rakow Czestochowa",
    "raków": "Rakow Czestochowa", "jagiellonia": "Jagiellonia Bialystok",
    "pogon": "Pogon Szczecin", "pogoń": "Pogon Szczecin", "slask": "Slask Wroclaw",
    "śląsk": "Slask Wroclaw", "widzew": "Widzew Lodz", "gornik": "Gornik Zabrze"
}

CSS = """
<style>
*{box-sizing:border-box}
body{margin:0;background:#02060c;color:#eef6ff;font-family:Arial,Helvetica,sans-serif}
.shell{display:grid;grid-template-columns:260px 1fr 320px;min-height:100vh}
.side{background:#06101d;border-right:1px solid #1b314d;padding:22px;position:sticky;top:0;height:100vh}
.logo{font-size:26px;font-weight:900;line-height:1.05;margin-bottom:28px}
.logo span{color:#91ff36;display:block}
.nav a{display:block;color:#cfe3ff;text-decoration:none;padding:12px;border:1px solid #1b314d;border-radius:14px;margin-bottom:10px}
.api{font-size:13px;color:#9fb0c8;line-height:1.8;margin-top:20px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#91ff36;margin-right:8px}
.main{padding:22px}.right{padding:22px;border-left:1px solid #1b314d;background:#050b15}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}
.title{font-size:34px;font-weight:900}
.card,.hero,.topcard{background:rgba(9,18,33,.94);border:1px solid #1f3856;border-radius:20px;padding:18px;margin-bottom:16px;box-shadow:0 18px 44px rgba(0,0,0,.38)}
.hero h1{margin:6px 0 8px;font-size:30px}.label{color:#91ff36;font-weight:900;font-size:13px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
label{display:flex;flex-direction:column;gap:7px;color:#b8c7da;font-size:14px}
input,select{width:100%;padding:13px;border-radius:13px;border:1px solid #28415f;background:#030a14;color:white;font-size:16px}
.actions{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:14px}
.btn{border:0;border-radius:14px;padding:14px;font-size:16px;font-weight:900;cursor:pointer}
.blue{background:#0879ff;color:#fff}.green{background:#20c75a;color:#03120a}.purple{background:#7a35e8;color:#fff}
.match-title{text-align:center;font-size:30px;font-weight:900;margin-bottom:14px}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}
.kpis div,.stat div{background:#050d19;border:1px solid #1b314d;border-radius:14px;padding:12px;text-align:center}
.kpis small,.stat span{display:block;color:#92a4bc;margin-bottom:6px}.kpis strong{color:#91ff36;font-size:21px}
.flow-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.bar-row{margin:13px 0}.bar-label{display:flex;justify-content:space-between;color:#dbe9fa;font-size:14px;margin-bottom:6px}
.bar-bg{height:12px;border-radius:999px;background:#07101d;border:1px solid #28415f;overflow:hidden}.bar-fill{height:100%;background:#91ff36}
.bar-fill.red{background:#ff4f6d}.bar-fill.orange{background:#ffb347}.bar-fill.blue{background:#49a7ff}.bar-fill.purple{background:#b566ff}
.score-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.score{background:#050d19;border:1px solid #1b314d;border-radius:16px;padding:18px;text-align:center}
.score small{color:#92a4bc}.score b{display:block;font-size:36px;color:#91ff36;margin-top:8px}.score.chaos b{color:#ff4f6d}
.stat{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.mini{background:#050d19;border:1px solid #1b314d;border-radius:14px;padding:12px;margin-bottom:10px;color:#d8e6f7}
.mini b{color:#91ff36}.hist-row{display:grid;grid-template-columns:1fr 2fr 1fr 1fr 1fr;gap:8px;background:#050d19;padding:10px;border-radius:12px;margin-bottom:8px}
.muted{color:#b8c7da;line-height:1.5}
@media(max-width:900px){.shell{display:block}.side,.right{position:relative;height:auto;border:0}.main{padding:14px}.form-grid,.actions,.kpis,.flow-grid,.score-grid,.stat,.hist-row{grid-template-columns:1fr}.title{font-size:26px}}
</style>
"""

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
    return str(x).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def norm(x):
    return (x or "").lower().replace(" ","").replace("-","").replace(".","").replace("_","").replace("'","").replace("ą","a").replace("ć","c").replace("ę","e").replace("ł","l").replace("ń","n").replace("ó","o").replace("ś","s").replace("ż","z").replace("ź","z")

def normalize_team_name(name):
    raw = (name or "").strip()
    return ALIASES.get(raw.lower()) or ALIASES.get(norm(raw)) or raw

def match_team(api_name, user_name):
    a, b = norm(api_name), norm(normalize_team_name(user_name))
    if not a or not b: return False
    return a == b or b in a or a in b or difflib.SequenceMatcher(None,a,b).ratio() >= 0.60

def safe_float(x):
    try:
        if x in [None,""]: return 0.0
        return float(str(x).replace(",","."))
    except Exception:
        return 0.0

def safe_int(x):
    try:
        if x in [None,""]: return None
        return int(float(str(x).replace(",",".")))
    except Exception:
        return None

def http_text(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"*/*"})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode("utf-8", errors="ignore"), None
    except Exception as e:
        return "", str(e)

def http_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8", errors="ignore")), None
    except Exception as e:
        return None, str(e)

def default_values():
    return {
        "home_team":"", "away_team":"", "city":"",
        "xg_home":0, "xg_away":0, "xga_home":0, "xga_away":0, "xg_source":"brak",
        "form_home":0, "form_away":0, "tempo":0,
        "odds":1.75, "odds_1":0, "odds_x":0, "odds_2":0, "odds_source":"brak",
        "shots_home":0, "shots_away":0, "sot_home":0, "sot_away":0,
        "corners_home":0, "corners_away":0, "cards_home":0, "cards_away":0,
        "bookmaker":"Rynek", "message":"", "sources":"",
        "home_home_matches":"", "home_away_matches":"", "away_home_matches":"", "away_away_matches":""
    }

def row_has_team(row, team):
    return match_team(row.get("HomeTeam",""), team) or match_team(row.get("AwayTeam",""), team)

def team_side(row, team):
    if match_team(row.get("HomeTeam",""), team): return "home"
    if match_team(row.get("AwayTeam",""), team): return "away"
    return None

def load_rows(home, away):
    for url in FOOTBALL_DATA_URLS:
        text, err = http_text(url)
        if err or not text: continue
        try:
            rows = list(csv.DictReader(io.StringIO(text)))
        except Exception:
            continue
        if any(row_has_team(r, home) or row_has_team(r, away) for r in rows if r.get("HomeTeam")):
            return rows, url.split("/")[-1]
    return [], ""

def team_stats(rows, team):
    completed = []
    for r in rows:
        if row_has_team(r, team) and safe_int(r.get("FTHG")) is not None and safe_int(r.get("FTAG")) is not None:
            completed.append(r)
    completed = completed[-5:]
    if not completed: return None
    pts=gf=ga=shots=sot=corners=cards=0
    for r in completed:
        side=team_side(r, team); hg=safe_int(r.get("FTHG")) or 0; ag=safe_int(r.get("FTAG")) or 0
        if side=="home":
            own,opp=hg,ag; shots+=safe_float(r.get("HS")); sot+=safe_float(r.get("HST")); corners+=safe_float(r.get("HC")); cards+=safe_float(r.get("HY"))
        else:
            own,opp=ag,hg; shots+=safe_float(r.get("AS")); sot+=safe_float(r.get("AST")); corners+=safe_float(r.get("AC")); cards+=safe_float(r.get("AY"))
        gf+=own; ga+=opp; pts += 3 if own>opp else 1 if own==opp else 0
    n=len(completed)
    return {"form":round((pts/(n*3))*100,1), "shots":round(shots/n,1), "sot":round(sot/n,1), "corners":round(corners/n,1), "cards":round(cards/n,1)}

def split_matches(rows, team):
    home, away = [], []
    for r in rows:
        if safe_int(r.get("FTHG")) is None or safe_int(r.get("FTAG")) is None: continue
        ht,at=r.get("HomeTeam",""),r.get("AwayTeam",""); hg=safe_int(r.get("FTHG")) or 0; ag=safe_int(r.get("FTAG")) or 0
        txt = ht + " " + str(hg) + ":" + str(ag) + " " + at
        if match_team(ht, team): home.append(txt)
        elif match_team(at, team): away.append(txt)
    return {"home":" | ".join(home[-5:]), "away":" | ".join(away[-5:])}

def parse_understat(text):
    m = re.search(r"teamsData\s*=\s*JSON\.parse\('(.+?)'\)", text, flags=re.S)
    if not m: return None
    try:
        raw = m.group(1).encode("utf-8").decode("unicode_escape")
        raw = html_lib.unescape(raw)
        return json.loads(raw)
    except Exception:
        return None

def understat_find(data, team):
    best,bscore=None,0
    q=normalize_team_name(team)
    for _,t in data.items():
        title=t.get("title","")
        score=1.0 if norm(title)==norm(q) else 0.92 if norm(q) in norm(title) or norm(title) in norm(q) else difflib.SequenceMatcher(None,norm(title),norm(q)).ratio()
        if score>bscore:
            best,bscore=t,score
    return best if bscore>=0.58 else None

def understat_avg(team):
    hist=team.get("history", [])[-5:]
    if not hist: return None
    xg=xga=n=0
    for item in hist:
        a=safe_float(item.get("xG")); b=safe_float(item.get("xGA"))
        if a==0 and b==0: continue
        xg+=a; xga+=b; n+=1
    if n==0: return None
    return {"xg":round(xg/n,2), "xga":round(xga/n,2)}

def understat_xg(home, away):
    res={"xg_home":0,"xg_away":0,"xga_home":0,"xga_away":0,"source":""}
    for league in UNDERSTAT_LEAGUES:
        text,err=http_text("https://understat.com/league/" + league)
        if err or not text: continue
        data=parse_understat(text)
        if not data: continue
        ho=understat_find(data,home); aw=understat_find(data,away); found=False; parts=["Understat " + league]
        if ho:
            h=understat_avg(ho)
            if h:
                res["xg_home"],res["xga_home"]=h["xg"],h["xga"]; parts.append("home: " + ho.get("title","")); found=True
        if aw:
            a=understat_avg(aw)
            if a:
                res["xg_away"],res["xga_away"]=a["xg"],a["xga"]; parts.append("away: " + aw.get("title","")); found=True
        if found:
            res["source"]=" | ".join(parts); return res
    return res

def calculate_real_stats(home_team, away_team, city=""):
    v=default_values(); home=normalize_team_name(home_team); away=normalize_team_name(away_team)
    v["home_team"]=home; v["away_team"]=away; v["city"]=city
    rows,src=load_rows(home,away)
    if not rows:
        v["message"]="Brak realnych statystyk Football-Data dla tych drużyn."; v["sources"]="Football-Data: brak danych"; return v
    h=team_stats(rows,home); a=team_stats(rows,away)
    if h:
        v["form_home"],v["shots_home"],v["sot_home"],v["corners_home"],v["cards_home"]=h["form"],h["shots"],h["sot"],h["corners"],h["cards"]
    if a:
        v["form_away"],v["shots_away"],v["sot_away"],v["corners_away"],v["cards_away"]=a["form"],a["shots"],a["sot"],a["corners"],a["cards"]
    ux=understat_xg(home,away)
    v["xg_home"],v["xg_away"],v["xga_home"],v["xga_away"]=ux["xg_home"],ux["xg_away"],ux["xga_home"],ux["xga_away"]
    v["xg_source"]=ux["source"] or "Understat: brak xG"
    sh=split_matches(rows,home); sa=split_matches(rows,away)
    v["home_home_matches"],v["home_away_matches"],v["away_home_matches"],v["away_away_matches"]=sh["home"],sh["away"],sa["home"],sa["away"]
    total_shots=v["shots_home"]+v["shots_away"]; total_sot=v["sot_home"]+v["sot_away"]
    v["tempo"]=62 if total_shots>=25 or total_sot>=9 else 43 if total_shots>0 else 0
    v["message"]="Realne dane pobrane." if (v["xg_home"] or v["xg_away"]) else "Dane Football-Data pobrane. xG = 0, bo Understat nie znalazł danych."
    v["sources"]="Football-Data " + src + " | " + v["xg_source"]
    return v

def fetch_odds_api(home_team, away_team):
    home=normalize_team_name(home_team); away=normalize_team_name(away_team)
    for sport in SPORT_KEYS:
        url="https://api.the-odds-api.com/v4/sports/" + sport + "/odds/?" + urllib.parse.urlencode({"apiKey":ODDS_API_KEY,"regions":"eu,uk","markets":"h2h","oddsFormat":"decimal"})
        data,err=http_json(url)
        if err or not isinstance(data,list): continue
        for event in data:
            ah=event.get("home_team",""); aa=event.get("away_team","")
            direct=match_team(ah,home) and match_team(aa,away); reverse=match_team(ah,away) and match_team(aa,home)
            if not direct and not reverse: continue
            candidates=[]
            for book in event.get("bookmakers",[]):
                for market in book.get("markets",[]):
                    if market.get("key")!="h2h": continue
                    o={"home":None,"draw":None,"away":None}
                    for out in market.get("outcomes",[]):
                        name=out.get("name",""); price=out.get("price")
                        if price is None: continue
                        if name==ah: o["home"]=float(price)
                        elif name==aa: o["away"]=float(price)
                        elif name.lower()=="draw": o["draw"]=float(price)
                    if o["home"] and o["draw"] and o["away"]: candidates.append(o)
            if candidates:
                best={"home":max(c["home"] for c in candidates),"draw":max(c["draw"] for c in candidates),"away":max(c["away"] for c in candidates)}
                if reverse: best["home"],best["away"]=best["away"],best["home"]
                return {"ok":True,"odds_1":round(best["home"],2),"odds_x":round(best["draw"],2),"odds_2":round(best["away"],2),"api_home":ah,"api_away":aa}
    return {"ok":False}

def fetch_odds(home_team, away_team, bookmaker):
    v=default_values(); v["home_team"]=normalize_team_name(home_team); v["away_team"]=normalize_team_name(away_team)
    res=fetch_odds_api(home_team,away_team)
    if res.get("ok"):
        v["odds_1"],v["odds_x"],v["odds_2"]=res["odds_1"],res["odds_x"],res["odds_2"]; v["odds"]=res["odds_1"]
        v["odds_source"]="The Odds API / rynek"; v["message"]="Kursy pobrane: " + res["api_home"] + " vs " + res["api_away"]; v["sources"]="The Odds API"
    else:
        v["message"]="Nie znaleziono kursów."; v["sources"]="The Odds API"
    return v

def current_values_from_form(**kwargs):
    v=default_values()
    for k,val in kwargs.items():
        if k in v: v[k]=val
    return v

STAT_KEYS=["home_team","away_team","city","xg_home","xg_away","xga_home","xga_away","xg_source","form_home","form_away","tempo","shots_home","shots_away","sot_home","sot_away","corners_home","corners_away","cards_home","cards_away","message","sources","home_home_matches","home_away_matches","away_home_matches","away_away_matches"]
ODDS_KEYS=["home_team","away_team","odds","odds_1","odds_x","odds_2","odds_source","message","sources"]

def merge_section(base,update,keys):
    m=dict(base)
    for k in keys:
        if k in update: m[k]=update[k]
    return m

def clamp(x):
    try: x=float(x)
    except Exception: x=0
    return max(0,min(100,x))

def value_edge(prob, odds):
    return round(prob - (100/odds),2) if odds>1 else 0

def fair_odds(prob):
    return round(100/prob,2) if prob>0 else 0

def confidence(v):
    score=0
    if v["xg_home"] or v["xg_away"]: score+=30
    if v["shots_home"] and v["shots_away"]: score+=20
    if v["odds_1"]>1 and v["odds_x"]>1 and v["odds_2"]>1: score+=20
    if v["form_home"] and v["form_away"]: score+=15
    if v["tempo"]: score+=15
    return {"score":score,"label":"HIGH" if score>=75 else "MEDIUM" if score>=50 else "LOW"}

def flow(v):
    total_xg=v["xg_home"]+v["xg_away"]; shots=v["shots_home"]+v["shots_away"]; sot=v["sot_home"]+v["sot_away"]; corners=v["corners_home"]+v["corners_away"]; cards=v["cards_home"]+v["cards_away"]
    fg=abs(v["form_home"]-v["form_away"]); control=55
    if total_xg and total_xg<=2.3: control+=12
    if shots and shots<=22: control+=8
    if v["tempo"] and v["tempo"]<=50: control+=8
    if fg<=15: control+=5
    if cards>=5: control-=8
    if corners>=11: control-=5
    chaos=100-control
    if sot>=9: chaos+=8
    if cards>=5: chaos+=8
    if corners>=11: chaos+=5
    return {"control":round(clamp(control),1),"chaos":round(clamp(chaos),1),"draw":round(clamp(65-fg*.8-max(0,total_xg-2.4)*8),1),"th":round(clamp(45+v["shots_home"]*1.6+v["sot_home"]*2.2),1),"ta":round(clamp(45+v["shots_away"]*1.6+v["sot_away"]*2.2),1)}

def exact(v,f):
    xh,xa=v["xg_home"],v["xg_away"]
    note="Wynik z realnego xG." if (xh or xa) else "Brak xG — wynik z formy/strzałów/kursów."
    if xh==0 and xa==0:
        xh=max(.45,min(2.6,(v["form_home"]*.035+v["shots_home"]*.09+v["sot_home"]*.22+(max(0,3.2-v["odds_1"])*.25 if v["odds_1"]>1 else 0))/3.2))
        xa=max(.35,min(2.4,(v["form_away"]*.035+v["shots_away"]*.09+v["sot_away"]*.22+(max(0,3.2-v["odds_2"])*.25 if v["odds_2"]>1 else 0))/3.2))
    diff=xh-xa; total=xh+xa
    if f["chaos"]>=64 or v["tempo"]>=60:
        if diff>=.45: return {"control":"2:1","value":"3:1","chaos":"3:2","note":note}
        if diff<=-.45: return {"control":"1:2","value":"1:3","chaos":"2:3","note":note}
        return {"control":"1:1","value":"2:2","chaos":"3:2 / 2:3","note":note}
    if diff>=.55: return {"control":"1:0 / 2:0","value":"2:1","chaos":"3:1","note":note}
    if diff<=-.55: return {"control":"0:1 / 0:2","value":"1:2","chaos":"1:3","note":note}
    if total<=2.2: return {"control":"1:1 / 0:0","value":"1:0 / 0:1","chaos":"2:1 / 1:2","note":note}
    return {"control":"1:1","value":"2:1 / 1:2","chaos":"2:2","note":note}

def calc(v):
    f=flow(v); prob=round(max(1,min(95,35+((v["form_home"]+v["form_away"])/2)*.22+(100-f["chaos"])*.22)),1)
    edge=value_edge(prob,v["odds"]); rating="TOP VALUE" if edge>5 and prob>=60 else "LEKKIE VALUE" if edge>0 and prob>=57 else "BRAK VALUE"
    if v["odds"]>=4.5 and prob>=60: prob=55; edge=value_edge(prob,v["odds"]); rating="⚠️ MARKET CONFLICT"
    return {"pick":"1X" if v["form_home"]>=v["form_away"] else "X2","probability":prob,"fair_odds":fair_odds(prob),"value_edge":edge,"rating":rating,"exact_score":exact(v,f)["control"]}

def bar(label,val,cls=""):
    return '<div class="bar-row"><div class="bar-label">{} <b>{}%</b></div><div class="bar-bg"><div class="bar-fill {}" style="width:{}%"></div></div></div>'.format(esc(label),round(clamp(val),1),cls,clamp(val))

def hidden(v):
    keys=["xg_home","xg_away","xga_home","xga_away","xg_source","form_home","form_away","tempo","odds","odds_1","odds_x","odds_2","shots_home","shots_away","sot_home","sot_away","corners_home","corners_away","cards_home","cards_away","odds_source","home_home_matches","home_away_matches","away_home_matches","away_away_matches"]
    return "".join('<input type="hidden" name="{}" value="{}">'.format(k,esc(v.get(k,""))) for k in keys)

def stat_block(v):
    rows=[("xG",str(v["xg_home"])+" - "+str(v["xg_away"])),("xGA",str(v["xga_home"])+" - "+str(v["xga_away"])),("Forma",str(v["form_home"])+" - "+str(v["form_away"])),("Kursy",str(v["odds_1"])+" / "+str(v["odds_x"])+" / "+str(v["odds_2"])),("Strzały",str(v["shots_home"])+" - "+str(v["shots_away"])),("Celne",str(v["sot_home"])+" - "+str(v["sot_away"])),("Rożne",str(v["corners_home"])+" - "+str(v["corners_away"])),("Kartki",str(v["cards_home"])+" - "+str(v["cards_away"]))]
    return '<div class="stat">' + "".join('<div><span>{}</span><b>{}</b></div>'.format(a,esc(b)) for a,b in rows) + '</div>'

def page(v=None,result=None,hist=False):
    if v is None: v=default_values()
    f=flow(v); ex=exact(v,f); c=confidence(v)
    if result is None and (v["home_team"] or v["away_team"]): result=calc(v)
    res_html=""
    if result:
        res_html='<div class="topcard"><div class="match-title">{} <span class="muted">vs</span> {}</div><div class="kpis"><div><small>Typ</small><strong>{}</strong></div><div><small>Probability</small><strong>{}%</strong></div><div><small>Value</small><strong>{} pp</strong></div><div><small>Rating</small><strong>{}</strong></div><div><small>Data Quality</small><strong>{} {}/100</strong></div></div></div>'.format(esc(v["home_team"]),esc(v["away_team"]),esc(result["pick"]),result["probability"],result["value_edge"],esc(result["rating"]),c["label"],c["score"])
    hist_html=""
    if hist:
        con=sqlite3.connect(DB_PATH); cur=con.cursor(); cur.execute("SELECT * FROM analyses ORDER BY id DESC LIMIT 50"); rows=cur.fetchall(); con.close()
        hist_html='<div class="card"><h2>Historia analiz</h2>'
        if not rows: hist_html += '<p class="muted">Historia jest pusta.</p>'
        for r in rows: hist_html += '<div class="hist-row"><span>{}</span><span>{} vs {}</span><span>{}</span><span>{}%</span><span>{}</span></div>'.format(esc(r[1]),esc(r[2]),esc(r[3]),esc(r[4]),r[5],esc(r[10]))
        hist_html += '</div>'
    form_html='<div class="card"><h2>Dane meczu</h2><form action="/fetch" method="post"><div class="form-grid"><label>Gospodarz<input name="home_team" value="{}" placeholder="Real Madryt"></label><label>Gość<input name="away_team" value="{}" placeholder="Atletico Bilbao"></label><label>Miasto<input name="city" value="{}" placeholder="Madryt"></label><label>Źródło / bukmacher<select name="bookmaker"><option>Rynek</option><option>bet365</option><option>STS</option><option>Betclic</option><option>Superbet</option></select></label></div>{}<div class="actions"><button class="btn blue" name="mode" value="stats">⚡ Statystyki</button><button class="btn green" name="mode" value="odds">💰 Kursy</button><button class="btn purple" formaction="/analyze" name="mode" value="analyze">🔥 Analizuj</button></div></form></div>'.format(esc(v["home_team"]),esc(v["away_team"]),esc(v["city"]),hidden(v))
    main='<main class="main"><div class="top"><div class="title">Quantum Edge v21 Dashboard</div><div class="muted">{}</div></div><div class="hero"><div class="label">PROFESSIONAL DASHBOARD</div><h1>AI Flow / Exact Score / Value Engine</h1><p class="muted">Jeden plik main.py. Nowy układ desktop/mobile bez starego HTML/CSS.</p></div>{}{}{}<div class="card"><h2>🔥 Flow Engine</h2><div class="flow-grid"><div>{}{}{}</div><div>{}{}</div></div></div><div class="card"><h2>⚽ Exact Score Engine</h2><div class="score-grid"><div class="score"><small>CONTROL</small><b>{}</b></div><div class="score"><small>VALUE</small><b>{}</b></div><div class="score chaos"><small>CHAOS</small><b>{}</b></div></div><p class="muted">{}</p></div><div class="card"><h2>📊 Dane pobrane</h2><p class="muted">{}</p><p class="muted">Źródła: {}</p>{}</div></main>'.format(datetime.now().strftime("%H:%M"),hist_html,res_html,form_html,bar("Control Flow",f["control"]),bar("Chaos Risk",f["chaos"],"red"),bar("Draw Acceptance",f["draw"],"blue"),bar("Home Transition",f["th"],"purple"),bar("Away Transition",f["ta"],"purple"),esc(ex["control"]),esc(ex["value"]),esc(ex["chaos"]),esc(ex["note"]),esc(v["message"]),esc(v["sources"]),stat_block(v))
    right='<aside class="right"><div class="card"><h2>🧠 Team Profiles</h2><div class="mini"><b>{}</b><br>Control/Transition profile</div><div class="mini"><b>{}</b><br>Chaos/Reactive profile</div></div><div class="card"><h2>🏠 Ostatnie mecze</h2><div class="mini"><b>Gospodarz u siebie</b><br>{}</div><div class="mini"><b>Gospodarz wyjazd</b><br>{}</div><div class="mini"><b>Gość u siebie</b><br>{}</div><div class="mini"><b>Gość wyjazd</b><br>{}</div></div><div class="card"><h2>📈 Market</h2><div class="mini"><b>Źródło kursu</b><br>{}</div></div></aside>'.format(esc(v["home_team"] or "Gospodarz"),esc(v["away_team"] or "Gość"),esc(v["home_home_matches"] or "brak danych"),esc(v["home_away_matches"] or "brak danych"),esc(v["away_home_matches"] or "brak danych"),esc(v["away_away_matches"] or "brak danych"),esc(v["odds_source"]))
    side='<aside class="side"><div class="logo">⚡ QUANTUM <span>EDGE</span></div><div class="nav"><a href="/">Dashboard</a><a href="/history">Historia</a><a href="/">Value Finder</a></div><div class="api"><div><span class="dot"></span>Odds API</div><div><span class="dot"></span>Understat</div><div><span class="dot"></span>Football-Data</div><div>Model: v21</div></div></aside>'
    return '<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Quantum Edge v21</title><meta name="viewport" content="width=device-width,initial-scale=1">{}</head><body><div class="shell">{}{}{}</div></body></html>'.format(CSS,side,main,right)

@app.get("/", response_class=HTMLResponse)
def home():
    return page(default_values())

@app.get("/history", response_class=HTMLResponse)
def history():
    return page(default_values(), hist=True)

@app.post("/fetch", response_class=HTMLResponse)
def fetch(home_team: str = Form(""), away_team: str = Form(""), city: str = Form(""), bookmaker: str = Form("Rynek"), mode: str = Form("stats"), xg_home: float = Form(0), xg_away: float = Form(0), xga_home: float = Form(0), xga_away: float = Form(0), xg_source: str = Form("brak"), form_home: float = Form(0), form_away: float = Form(0), tempo: float = Form(0), odds: float = Form(1.75), odds_1: float = Form(0), odds_x: float = Form(0), odds_2: float = Form(0), shots_home: float = Form(0), shots_away: float = Form(0), sot_home: float = Form(0), sot_away: float = Form(0), corners_home: float = Form(0), corners_away: float = Form(0), cards_home: float = Form(0), cards_away: float = Form(0), odds_source: str = Form("brak"), home_home_matches: str = Form(""), home_away_matches: str = Form(""), away_home_matches: str = Form(""), away_away_matches: str = Form("")):
    current=current_values_from_form(**locals())
    if mode=="odds":
        v=merge_section(current,fetch_odds(home_team,away_team,bookmaker),ODDS_KEYS)
    else:
        v=merge_section(current,calculate_real_stats(home_team,away_team,city),STAT_KEYS)
    return page(v)

@app.post("/analyze", response_class=HTMLResponse)
def analyze(home_team: str = Form(""), away_team: str = Form(""), city: str = Form(""), bookmaker: str = Form("Rynek"), xg_home: float = Form(0), xg_away: float = Form(0), xga_home: float = Form(0), xga_away: float = Form(0), xg_source: str = Form("brak"), form_home: float = Form(0), form_away: float = Form(0), tempo: float = Form(0), odds: float = Form(1.75), odds_1: float = Form(0), odds_x: float = Form(0), odds_2: float = Form(0), shots_home: float = Form(0), shots_away: float = Form(0), sot_home: float = Form(0), sot_away: float = Form(0), corners_home: float = Form(0), corners_away: float = Form(0), cards_home: float = Form(0), cards_away: float = Form(0), odds_source: str = Form("brak"), home_home_matches: str = Form(""), home_away_matches: str = Form(""), away_home_matches: str = Form(""), away_away_matches: str = Form("")):
    v=current_values_from_form(**locals()); result=calc(v)
    con=sqlite3.connect(DB_PATH); cur=con.cursor()
    cur.execute("INSERT INTO analyses (created_at, home_team, away_team, pick, probability, fair_odds, bookmaker_odds, value_edge, exact_score, rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (datetime.now().strftime("%Y-%m-%d %H:%M"), home_team, away_team, result["pick"], result["probability"], fair_odds(result["probability"]), odds, result["value_edge"], result["exact_score"], result["rating"]))
    con.commit(); con.close()
    return page(v,result)
