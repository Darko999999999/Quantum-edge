from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3, urllib.request, urllib.parse, json, csv, io
from datetime import datetime

app = FastAPI(title="Quantum Edge Web MVP")
DB_PATH = "quantum_edge.db"
SOFA_BASE = "https://www.sofascore.com/api/v1"

ALIASES = {
    "nicea": "Nice", "lens": "Lens", "rc lens": "Lens",
    "fiorentina": "Fiorentina", "atalanta": "Atalanta",
    "inter": "Inter", "inter mediolan": "Inter", "milan": "Milan",
    "ac milan": "Milan", "juventus": "Juventus", "roma": "Roma",
    "lazio": "Lazio", "napoli": "Napoli", "barcelona": "Barcelona",
    "real": "Real Madrid", "real madryt": "Real Madrid",
    "arsenal": "Arsenal", "chelsea": "Chelsea", "liverpool": "Liverpool",
    "manchester city": "Manchester City", "psg": "Paris Saint-Germain",
    "bayern": "Bayern Munich", "bayern monachium": "Bayern Munich",
}

FD_URLS = [
    "https://www.football-data.co.uk/mmz4281/2526/E0.csv",
    "https://www.football-data.co.uk/mmz4281/2526/I1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/SP1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/D1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/F1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/N1.csv",
    "https://www.football-data.co.uk/mmz4281/2526/P1.csv",
]

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
    return (x or "").lower().replace(" ","").replace("-","").replace(".","").replace("'","")

def fixed(x):
    return ALIASES.get((x or "").strip().lower(), (x or "").strip())

def get_json(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.sofascore.com/"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), None
    except Exception as e:
        return None, str(e)

def get_text(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore"), None
    except Exception as e:
        return "", str(e)

def defaults():
    return {
        "home_team":"", "away_team":"", "city":"",
        "xg_home":1.25, "xg_away":0.95,
        "form_home":60, "form_away":55,
        "tempo":50, "odds":1.75,
        "shots_home":11, "shots_away":10,
        "sot_home":4, "sot_away":3,
        "corners_home":5, "corners_away":4,
        "cards_home":2, "cards_away":2,
        "defensive_control":60, "draw_acceptance":55,
        "collapse_home":35, "collapse_away":40,
        "absences":25, "weather":15, "market_risk":25
    }

def find_teams(obj, wanted):
    out, seen = [], set()
    w = norm(wanted)
    def walk(o):
        if isinstance(o, dict):
            for k in ("entity","team"):
                e = o.get(k)
                if isinstance(e, dict) and e.get("id") and e.get("name"):
                    n = norm(e["name"])
                    if w in n or n in w:
                        if e["id"] not in seen:
                            seen.add(e["id"]); out.append({"id":e["id"],"name":e["name"]})
            if o.get("id") and o.get("name"):
                n = norm(o["name"])
                if w in n or n in w:
                    if o["id"] not in seen:
                        seen.add(o["id"]); out.append({"id":o["id"],"name":o["name"]})
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for i in o: walk(i)
    walk(obj)
    return out

def sofa_team(name):
    q = fixed(name)
    for path in ("/search/all?q=", "/search/teams?q="):
        data, err = get_json(SOFA_BASE + path + urllib.parse.quote(q))
        if data:
            teams = find_teams(data, q)
            if teams: return teams[0]
    return None

def sofa_last(team_id):
    data, err = get_json(f"{SOFA_BASE}/team/{team_id}/events/last/0")
    if not data: return None
    rows = []
    gf = ga = pts = cnt = 0
    for ev in data.get("events", [])[:5]:
        h, a = ev.get("homeTeam",{}), ev.get("awayTeam",{})
        hs = ev.get("homeScore",{}).get("current")
        av = ev.get("awayScore",{}).get("current")
        if hs is None or av is None: continue
        if h.get("id") == team_id:
            own, opp = hs, av
        else:
            own, opp = av, hs
        gf += own; ga += opp; cnt += 1
        pts += 3 if own > opp else 1 if own == opp else 0
        rows.append(f"{h.get('name','')} {hs}:{av} {a.get('name','')}")
    if not cnt: return None
    return {"matches":rows, "form":round(pts/(cnt*3)*100,1), "gf":round(gf/cnt,2), "ga":round(ga/cnt,2)}

def fd_match(row, team):
    t = norm(fixed(team))
    h, a = norm(row.get("HomeTeam","")), norm(row.get("AwayTeam",""))
    return t in h or h in t or t in a or a in t

def fd_side(row, team):
    t = norm(fixed(team))
    h, a = norm(row.get("HomeTeam","")), norm(row.get("AwayTeam",""))
    if t in h or h in t: return "H"
    if t in a or a in t: return "A"
    return ""

def football_data(home, away):
    rows = None; src = ""
    for url in FD_URLS:
        text, err = get_text(url)
        if not text: continue
        data = list(csv.DictReader(io.StringIO(text)))
        if any(fd_match(r, home) or fd_match(r, away) for r in data if r.get("HomeTeam")):
            rows = data; src = url.split("/")[-1]; break
    if not rows: return None

    def team_stats(team):
        rs = [r for r in rows if fd_match(r, team) and r.get("FTHG") not in (None,"")]
        rs = rs[-5:]
        if not rs: return None
        pts=gf=ga=shots=sot=corn=cards=0; games=[]
        for r in rs:
            side = fd_side(r, team)
            hg, ag = int(r.get("FTHG") or 0), int(r.get("FTAG") or 0)
            if side == "H":
                own, opp = hg, ag
                sh, st, co, ca = r.get("HS"), r.get("HST"), r.get("HC"), r.get("HY")
            else:
                own, opp = ag, hg
                sh, st, co, ca = r.get("AS"), r.get("AST"), r.get("AC"), r.get("AY")
            pts += 3 if own > opp else 1 if own == opp else 0
            gf += own; ga += opp
            shots += float(sh or 0); sot += float(st or 0); corn += float(co or 0); cards += float(ca or 0)
            games.append(f"{r.get('HomeTeam','')} {hg}:{ag} {r.get('AwayTeam','')}")
        n=len(rs)
        return {"form":round(pts/(n*3)*100,1), "gf":round(gf/n,2), "ga":round(ga/n,2),
                "shots":round(shots/n,1), "sot":round(sot/n,1), "corners":round(corn/n,1),
                "cards":round(cards/n,1), "matches":games}
    return {"source":"Football-Data " + src, "home":team_stats(home), "away":team_stats(away)}

def meteo(city):
    if not city: return None
    geo, err = get_json("https://geocoding-api.open-meteo.com/v1/search?name=" + urllib.parse.quote(city) + "&count=1&language=pl&format=json")
    if not geo or not geo.get("results"): return None
    p = geo["results"][0]
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude":p["latitude"], "longitude":p["longitude"],
        "daily":"temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
        "timezone":"auto", "forecast_days":1
    })
    w, err = get_json(url)
    if not w or not w.get("daily"): return None
    d=w["daily"]
    rain=(d.get("precipitation_sum") or [0])[0] or 0
    wind=(d.get("windspeed_10m_max") or [0])[0] or 0
    tmax=(d.get("temperature_2m_max") or [0])[0]
    tmin=(d.get("temperature_2m_min") or [0])[0]
    risk=10 + (10 if rain>=2 else 0) + (15 if rain>=6 else 0) + (10 if wind>=25 else 0) + (15 if wind>=40 else 0)
    return {"risk":max(5,min(80,risk)), "desc":f"{p.get('name',city)}: {tmin}-{tmax}°C, opad {rain} mm, wiatr {wind} km/h"}

def fetch_all(home, away, city):
    v = defaults()
    v["home_team"] = fixed(home); v["away_team"] = fixed(away); v["city"] = city
    v["sources"] = []; v["auto_summary"] = []; v["last_home"] = []; v["last_away"] = []

    ht, at = sofa_team(home), sofa_team(away)
    if ht and at:
        v["home_team"], v["away_team"] = ht["name"], at["name"]
        hf, af = sofa_last(ht["id"]), sofa_last(at["id"])
        if hf and af:
            v["form_home"], v["form_away"] = hf["form"], af["form"]
            v["last_home"], v["last_away"] = hf["matches"], af["matches"]
            v["xg_home"] = round(hf["gf"]*0.65 + af["ga"]*0.35, 2)
            v["xg_away"] = round(af["gf"]*0.65 + hf["ga"]*0.35, 2)
            v["sources"].append("SofaScore")
            v["auto_summary"].append("forma i xG proxy z ostatnich meczów")

    fd = football_data(home, away)
    if fd:
        v["sources"].append(fd["source"])
        h, a = fd.get("home"), fd.get("away")
        if h:
            v["form_home"], v["shots_home"], v["sot_home"], v["corners_home"], v["cards_home"] = h["form"], h["shots"] or v["shots_home"], h["sot"] or v["sot_home"], h["corners"] or v["corners_home"], h["cards"] or v["cards_home"]
            if not v["last_home"]: v["last_home"] = h["matches"]
        if a:
            v["form_away"], v["shots_away"], v["sot_away"], v["corners_away"], v["cards_away"] = a["form"], a["shots"] or v["shots_away"], a["sot"] or v["sot_away"], a["corners"] or v["corners_away"], a["cards"] or v["cards_away"]
            if not v["last_away"]: v["last_away"] = a["matches"]
        if h and a:
            v["xg_home"] = round(h["gf"]*0.65 + a["ga"]*0.35, 2)
            v["xg_away"] = round(a["gf"]*0.65 + h["ga"]*0.35, 2)
        v["auto_summary"].append("strzały/celne/rożne/kartki z Football-Data")

    w = meteo(city)
    if w:
        v["weather"] = w["risk"]; v["sources"].append("Open-Meteo"); v["auto_summary"].append("pogoda: " + w["desc"])

    total_shots = float(v["shots_home"]) + float(v["shots_away"])
    total_sot = float(v["sot_home"]) + float(v["sot_away"])
    total_xg = float(v["xg_home"]) + float(v["xg_away"])
    v["tempo"] = 62 if total_shots >= 25 or total_sot >= 9 or total_xg >= 2.8 else 43 if total_shots <= 18 and total_sot <= 6 and total_xg <= 2.2 else 50

    if not v["sources"]:
        v["sources"].append("Proxy ręczne")
        v["auto_summary"].append("brak stabilnych danych zewnętrznych — zostawiono wartości proxy")
    v["message"] = "Dane zostały uzupełnione automatycznie z dostępnych darmowych źródeł."
    return v

def fair_odds(p): return round(100/p,2) if p>0 else 0
def value_edge(p,o): return round(p-(100/o),2) if o>1 else 0

def choose_pick(xh, xa, tempo, dc, chaos):
    total=xh+xa
    if total <= 2.25 and tempo <= 55 and dc >= 58 and chaos <= 55: return "Under 2.5 gola", "1:0 / 1:1 / 0:0"
    if total <= 2.90 and tempo <= 62 and dc >= 52: return "Under 3.5 gola", "1:1 / 2:1 / 1:0"
    if total >= 2.75 and tempo >= 55 and chaos <= 62: return "Over 1.5 gola", "2:1 / 2:2 / 3:1"
    return ("1X","1:0 / 1:1 / 2:1") if xh>=xa else ("X2","0:1 / 1:1 / 1:2")

def model(d):
    xh,xa=float(d["xg_home"]),float(d["xg_away"])
    fh,fa=float(d["form_home"]),float(d["form_away"])
    tempo=float(d["tempo"]); dc=float(d["defensive_control"]); draw=float(d["draw_acceptance"])
    ch=float(d["collapse_home"]); ca=float(d["collapse_away"]); absn=float(d["absences"]); weather=float(d["weather"]); market=float(d["market_risk"]); odds=float(d["odds"])
    shots=float(d["shots_home"])+float(d["shots_away"])
    sot=float(d["sot_home"])+float(d["sot_away"])
    corners=float(d["corners_home"])+float(d["corners_away"])
    cards=float(d["cards_home"])+float(d["cards_away"])
    chaos=round((tempo+ch+ca+absn+weather+market)/6,1)
    stat= (3 if shots>=25 else 0)+(3 if sot>=9 else 0)+(2 if corners>=11 else 0)+(1 if cards>=5 else 0)+(-3 if shots<=18 and sot<=6 else 0)
    flow=5 if xh+xa<=2.35 and tempo<=55 and dc>=58 else 4 if xh+xa>=2.8 and tempo>=60 else 0
    prob=((fh+fa)/2)*0.16 + dc*0.18 + draw*0.06 + (100-chaos)*0.28 + (100-absn)*0.08 + (100-market)*0.08 + 20 + stat + flow
    if chaos>=65: prob-=8
    if absn>=65: prob-=5
    prob=round(max(1,min(95,prob)),1)
    pick, exact = choose_pick(xh,xa,tempo,dc,chaos)
    edge=value_edge(prob,odds)
    rating="TOP VALUE" if edge>5 and prob>=60 and chaos<=45 else "MOCNY TYP" if edge>2 and prob>=60 and chaos<=55 else "LEKKIE VALUE" if edge>0 and prob>=57 else "BRAK VALUE"
    return {"pick":pick,"exact_score":exact,"probability":prob,"fair_odds":fair_odds(prob),"value_edge":edge,"chaos":chaos,"rating":rating,"total_xg":round(xh+xa,2),"shots_total":shots,"sot_total":sot,"corners_total":corners,"cards_total":cards}

def html_list(title, items):
    if not items: return ""
    return "<div class='mini'><b>"+esc(title)+"</b><ul>"+"".join("<li>"+esc(i)+"</li>" for i in items)+"</ul></div>"

def page(result=None, values=None, fetched=None, history=None):
    v = values or defaults()
    result_html = ""
    if result:
        result_html = f"""
        <section class="card result">
          <div class="match">{esc(v['home_team'])} <span>vs</span> {esc(v['away_team'])}</div>
          <div class="grid-3"><div><small>Typ</small><strong>{esc(result['pick'])}</strong></div><div><small>Probability</small><strong>{result['probability']}%</strong></div><div><small>Value</small><strong>{result['value_edge']} pp</strong></div></div>
          <div class="rating">{esc(result['rating'])}</div>
          <div class="stats">
            <div><span>Fair odds</span><b>{result['fair_odds']}</b></div><div><span>Kurs</span><b>{v['odds']}</b></div>
            <div><span>Chaos risk</span><b>{result['chaos']}/100</b></div><div><span>Exact score</span><b>{esc(result['exact_score'])}</b></div>
            <div><span>Suma xG</span><b>{result['total_xg']}</b></div><div><span>Strzały</span><b>{result['shots_total']}</b></div>
            <div><span>Celne</span><b>{result['sot_total']}</b></div><div><span>Rożne</span><b>{result['corners_total']}</b></div>
            <div><span>Kartki</span><b>{result['cards_total']}</b></div>
          </div>
        </section>"""
    fetched_html = ""
    if fetched:
        fetched_html = f"""
        <section class="card">
          <h2>Dane pobrane automatycznie</h2>
          <p>{esc(fetched.get('message',''))}</p><p><b>Źródła użyte:</b> {esc(', '.join(fetched.get('sources',[])))}</p>
          {html_list('Uzupełnione dane', fetched.get('auto_summary', []))}
          <div class="stats">
            <div><span>xG</span><b>{fetched['xg_home']} - {fetched['xg_away']}</b></div><div><span>Forma</span><b>{fetched['form_home']} - {fetched['form_away']}</b></div>
            <div><span>Strzały</span><b>{fetched['shots_home']} - {fetched['shots_away']}</b></div><div><span>Celne</span><b>{fetched['sot_home']} - {fetched['sot_away']}</b></div>
            <div><span>Rożne</span><b>{fetched['corners_home']} - {fetched['corners_away']}</b></div><div><span>Kartki</span><b>{fetched['cards_home']} - {fetched['cards_away']}</b></div>
            <div><span>Tempo</span><b>{fetched['tempo']}/100</b></div><div><span>Pogoda</span><b>{fetched['weather']}/100</b></div>
          </div>
          {html_list('Ostatnie mecze gospodarza', fetched.get('last_home', []))}
          {html_list('Ostatnie mecze gościa', fetched.get('last_away', []))}
        </section>"""
    history_html = ""
    if history:
        rows = "".join(f"<div class='history-row'><div><b>{esc(r[2])} vs {esc(r[3])}</b><small>{esc(r[1])}</small></div><div>{esc(r[4])}</div><div>{r[5]}%</div><div>{r[8]} pp</div><div>{esc(r[10])}</div></div>" for r in history)
        history_html = f"<section class='card'><h2>Historia analiz</h2>{rows}</section>"
    return f"""<!DOCTYPE html><html lang="pl"><head><meta charset="UTF-8"><title>Quantum Edge MVP</title><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at top,#0f2435 0%,#050912 55%,#03060c 100%);color:#f4f7fb;font-family:Arial,Helvetica,sans-serif}} .app{{max-width:760px;margin:0 auto;padding:18px}} header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}} .logo{{font-size:24px;font-weight:800;letter-spacing:1px;line-height:1.1}} .logo span{{color:#90ff36;display:block}} a{{color:#90ff36;text-decoration:none}} .nav a{{margin-left:10px;border:1px solid #30445b;padding:8px 12px;border-radius:12px}} .card{{background:rgba(12,22,36,.92);border:1px solid #22344c;border-radius:18px;padding:18px;margin-bottom:16px;box-shadow:0 14px 38px rgba(0,0,0,.32)}} .hero h1{{margin:8px 0;font-size:26px}} .label{{color:#90ff36;font-size:13px;font-weight:bold}} .topline{{display:flex;align-items:center;justify-content:space-between;gap:10px}} .fetch-mini{{width:48px;height:48px;border-radius:50%;border:1px solid rgba(144,255,54,.45);background:rgba(144,255,54,.10);color:#90ff36;font-size:22px;font-weight:900;margin:0;padding:0}} .match{{text-align:center;font-size:22px;font-weight:bold;margin-bottom:16px}} .match span{{color:#91a0b5;font-size:14px;margin:0 10px}} .grid-3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:16px}} .grid-3 div{{background:#091221;border:1px solid #22344c;border-radius:14px;padding:12px}} small{{display:block;color:#98a7ba;margin-bottom:6px}} strong{{color:#90ff36;font-size:22px}} .rating{{text-align:center;padding:12px;border-radius:14px;background:rgba(144,255,54,.10);border:1px solid rgba(144,255,54,.35);color:#90ff36;font-weight:bold;margin-bottom:14px}} .stats{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}} .stats div{{display:flex;justify-content:space-between;background:#08111e;border-radius:12px;padding:10px}} .stats span{{color:#98a7ba}} .two{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} label{{display:flex;flex-direction:column;color:#cbd6e3;font-size:14px;gap:6px}} input{{width:100%;padding:12px;border-radius:12px;border:1px solid #2d4058;background:#07101d;color:white;font-size:16px}} button.main{{width:100%;margin-top:18px;padding:15px;border:none;border-radius:16px;background:#90ff36;color:#07101d;font-weight:800;font-size:17px}} .history-row{{display:grid;grid-template-columns:2fr 1.2fr .7fr .8fr 1fr;gap:8px;padding:12px 0;border-bottom:1px solid #22344c;align-items:center}} .mini{{background:#08111e;padding:12px;border-radius:12px;margin-top:10px}} .mini ul{{margin:8px 0 0 18px;padding:0;color:#cbd6e3}} @media(max-width:560px){{.app{{padding:14px}}.two,.grid-3,.stats,.history-row{{grid-template-columns:1fr}}}}
</style></head><body><div class="app"><header><div class="logo">⚛ QUANTUM <span>EDGE</span></div><div class="nav"><a href="/">Analiza</a><a href="/history">Historia</a></div></header>
<section class="card hero"><div class="label">ANALIZA MECZU</div><h1>Quantum Edge Web MVP</h1><p>Ikonka ⚡ sama przeszukuje dostępne darmowe źródła i uzupełnia dane. Potem możesz je poprawić ręcznie.</p></section>
{result_html}{fetched_html}{history_html}
<form action="/fetch" method="post" class="card"><div class="topline"><h2>Dane meczu</h2><button class="fetch-mini" type="submit" title="Pobierz statystyki">⚡</button></div><div class="two"><label>Gospodarz<input name="home_team" required value="{esc(v['home_team'])}" placeholder="Lens"></label><label>Gość<input name="away_team" required value="{esc(v['away_team'])}" placeholder="Nice"></label><label>Miasto meczu / pogoda<input name="city" value="{esc(v.get('city',''))}" placeholder="Lens"></label></div></form>
<form action="/analyze" method="post" class="card"><input type="hidden" name="home_team" value="{esc(v['home_team'])}"><input type="hidden" name="away_team" value="{esc(v['away_team'])}"><h3>xG / forma</h3><div class="two"><label>xG gospodarz<input type="number" step="0.01" name="xg_home" value="{v['xg_home']}"></label><label>xG gość<input type="number" step="0.01" name="xg_away" value="{v['xg_away']}"></label><label>Forma gospodarz<input type="number" step="1" name="form_home" value="{v['form_home']}"></label><label>Forma gość<input type="number" step="1" name="form_away" value="{v['form_away']}"></label></div><h3>Statystyki</h3><div class="two"><label>Tempo 0-100<input type="number" step="1" name="tempo" value="{v['tempo']}"></label><label>Kurs bukmachera<input type="number" step="0.01" name="odds" value="{v['odds']}"></label><label>Strzały gospodarz<input type="number" step="0.1" name="shots_home" value="{v['shots_home']}"></label><label>Strzały gość<input type="number" step="0.1" name="shots_away" value="{v['shots_away']}"></label><label>Celne gospodarz<input type="number" step="0.1" name="sot_home" value="{v['sot_home']}"></label><label>Celne gość<input type="number" step="0.1" name="sot_away" value="{v['sot_away']}"></label><label>Rożne gospodarz<input type="number" step="0.1" name="corners_home" value="{v['corners_home']}"></label><label>Rożne gość<input type="number" step="0.1" name="corners_away" value="{v['corners_away']}"></label><label>Kartki gospodarz<input type="number" step="0.1" name="cards_home" value="{v['cards_home']}"></label><label>Kartki gość<input type="number" step="0.1" name="cards_away" value="{v['cards_away']}"></label></div><h3>Flow / ryzyko</h3><div class="two"><label>Defensive control<input type="number" step="1" name="defensive_control" value="{v['defensive_control']}"></label><label>Akceptacja remisu<input type="number" step="1" name="draw_acceptance" value="{v['draw_acceptance']}"></label><label>Collapse gospodarz<input type="number" step="1" name="collapse_home" value="{v['collapse_home']}"></label><label>Collapse gość<input type="number" step="1" name="collapse_away" value="{v['collapse_away']}"></label><label>Absencje / rotacje<input type="number" step="1" name="absences" value="{v['absences']}"></label><label>Pogoda<input type="number" step="1" name="weather" value="{v['weather']}"></label><label>Rynek / kursy<input type="number" step="1" name="market_risk" value="{v['market_risk']}"></label></div><button class="main" type="submit">Analizuj mecz</button></form></div></body></html>"""

@app.get("/", response_class=HTMLResponse)
def home():
    return page()

@app.post("/fetch", response_class=HTMLResponse)
def fetch(home_team: str = Form(...), away_team: str = Form(...), city: str = Form("")):
    fetched = fetch_all(home_team, away_team, city)
    values = defaults()
    for k in values:
        if k in fetched: values[k] = fetched[k]
    return page(values=values, fetched=fetched)

@app.post("/analyze", response_class=HTMLResponse)
def analyze(home_team: str = Form(...), away_team: str = Form(...), xg_home: float = Form(1.25), xg_away: float = Form(0.95), form_home: float = Form(60), form_away: float = Form(55), tempo: float = Form(50), shots_home: float = Form(11), shots_away: float = Form(10), sot_home: float = Form(4), sot_away: float = Form(3), corners_home: float = Form(5), corners_away: float = Form(4), cards_home: float = Form(2), cards_away: float = Form(2), defensive_control: float = Form(60), draw_acceptance: float = Form(55), collapse_home: float = Form(35), collapse_away: float = Form(40), absences: float = Form(25), weather: float = Form(15), market_risk: float = Form(25), odds: float = Form(1.75)):
    data = locals()
    res = model(data)
    con = sqlite3.connect(DB_PATH); cur = con.cursor()
    cur.execute("INSERT INTO analyses (created_at,home_team,away_team,pick,probability,fair_odds,bookmaker_odds,value_edge,exact_score,rating) VALUES (?,?,?,?,?,?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d %H:%M"), home_team, away_team, res["pick"], res["probability"], res["fair_odds"], odds, res["value_edge"], res["exact_score"], res["rating"]))
    con.commit(); con.close()
    vals = defaults()
    for k in vals:
        if k in data: vals[k] = data[k]
    return page(result=res, values=vals)

@app.get("/history", response_class=HTMLResponse)
def history():
    con = sqlite3.connect(DB_PATH); cur = con.cursor()
    cur.execute("SELECT * FROM analyses ORDER BY id DESC LIMIT 50")
    rows = cur.fetchall(); con.close()
    return page(history=rows)
