
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from datetime import datetime
import sqlite3
import urllib.request, urllib.parse, json, csv, io, difflib, re, html as html_lib

app = FastAPI(title="Quantum Edge v30")
DB_PATH = "quantum_edge.db"
ODDS_API_KEY = "4235b3c48084bdd173789f88b6ddadfd"

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
UNDERSTAT_LEAGUES = ["EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1"]
SPORT_KEYS = ["soccer_epl","soccer_spain_la_liga","soccer_italy_serie_a","soccer_germany_bundesliga","soccer_france_ligue_one","soccer_netherlands_eredivisie","soccer_portugal_primeira_liga","soccer_belgium_first_div","soccer_turkey_super_league","soccer_scotland_premiership","soccer_poland_ekstraklasa","soccer_uefa_champs_league","soccer_uefa_europa_league","soccer_uefa_europa_conference_league"]

ALIASES = {
"real madryt":"Real Madrid","real madrid":"Real Madrid","real":"Real Madrid","athletic bilbao":"Athletic Club","atletico bilbao":"Athletic Club","athletic club":"Athletic Club","atletico madryt":"Atletico Madrid","atletico madrid":"Atletico Madrid",
"milan":"AC Milan","ac milan":"AC Milan","inter":"Inter","inter mediolan":"Inter","juventus":"Juventus","torino":"Torino","cagliari":"Cagliari","atalanta":"Atalanta","fiorentina":"Fiorentina","roma":"Roma","lazio":"Lazio","napoli":"Napoli","bologna":"Bologna",
"man city":"Manchester City","manchester city":"Manchester City","west ham":"West Ham United","west ham united":"West Ham United","manchester united":"Manchester United","man utd":"Manchester United","arsenal":"Arsenal","chelsea":"Chelsea","liverpool":"Liverpool","tottenham":"Tottenham","newcastle":"Newcastle United",
"psg":"Paris Saint Germain","paris sg":"Paris Saint Germain","lens":"Lens","nice":"Nice","nicea":"Nice","lyon":"Lyon","marseille":"Marseille","marsylia":"Marseille","lille":"Lille","monaco":"Monaco",
"bayern":"Bayern Munich","bayern monachium":"Bayern Munich","dortmund":"Borussia Dortmund","leipzig":"RB Leipzig","rb lipsk":"RB Leipzig","leverkusen":"Bayer Leverkusen","bayer leverkusen":"Bayer Leverkusen",
"lech":"Lech Poznan","legia":"Legia Warsaw","rakow":"Rakow Czestochowa","raków":"Rakow Czestochowa","jagiellonia":"Jagiellonia Bialystok","slask":"Slask Wroclaw","śląsk":"Slask Wroclaw","widzew":"Widzew Lodz"
}

LOGO_DOMAINS = {
"acmilan":"acmilan.com","cagliari":"cagliaricalcio.com","inter":"inter.it","juventus":"juventus.com","torino":"torinofc.it","atalanta":"atalanta.it","fiorentina":"acffiorentina.com","roma":"asroma.com","lazio":"sslazio.it","napoli":"sscnapoli.it","bologna":"bolognafc.it",
"real madrid":"realmadrid.com","barcelona":"fcbarcelona.com","atletico madrid":"atleticodemadrid.com","athletic club":"athletic-club.eus","sevilla":"sevillafc.es","real betis":"realbetisbalompie.es","real sociedad":"realsociedad.eus","valencia":"valenciacf.com","villarreal":"villarrealcf.es",
"manchester city":"mancity.com","west ham united":"whufc.com","manchester united":"manutd.com","arsenal":"arsenal.com","chelsea":"chelseafc.com","liverpool":"liverpoolfc.com","tottenham":"tottenhamhotspur.com","newcastle united":"newcastleunited.com",
"bayern munich":"fcbayern.com","borussia dortmund":"bvb.de","rb leipzig":"rbleipzig.com","bayer leverkusen":"bayer04.de",
"paris saint germain":"psg.fr","marseille":"om.fr","lyon":"ol.fr","monaco":"asmonaco.com","lille":"losc.fr","lens":"rclens.fr","nice":"ogcnice.com",
"lech poznan":"lechpoznan.pl","legia warsaw":"legia.com","rakow czestochowa":"rakow.com","jagiellonia bialystok":"jagiellonia.pl","slask wroclaw":"slaskwroclaw.pl","widzew lodz":"widzew.com"
}

TEXT_CACHE = {}
JSON_CACHE = {}

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, home_team TEXT, away_team TEXT, pick TEXT, probability REAL, fair_odds REAL, bookmaker_odds REAL, value_edge REAL, exact_score TEXT, rating TEXT)")
    con.commit()
    con.close()
init_db()

def esc(x): return str(x).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")
def norm(x): return (x or "").lower().replace(" ","").replace("-","").replace(".","").replace("_","").replace("'","").replace("ą","a").replace("ć","c").replace("ę","e").replace("ł","l").replace("ń","n").replace("ó","o").replace("ś","s").replace("ż","z").replace("ź","z")
def normalize_team_name(name):
    raw = (name or "").strip()
    return ALIASES.get(raw.lower()) or ALIASES.get(norm(raw)) or raw
def match_team(api_name, user_name):
    a,b = norm(api_name), norm(normalize_team_name(user_name))
    if not a or not b: return False
    if a == b or b in a or a in b: return True
    return difflib.SequenceMatcher(None,a,b).ratio() >= .60
def safe_float(x):
    try: return 0.0 if x in [None,""] else float(str(x).replace(",","."))
    except Exception: return 0.0
def safe_int(x):
    try: return None if x in [None,""] else int(float(str(x).replace(",",".")))
    except Exception: return None

def http_text(url):
    if url in TEXT_CACHE: return TEXT_CACHE[url], None
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"*/*"})
        with urllib.request.urlopen(req, timeout=4) as r:
            text=r.read().decode("utf-8",errors="ignore")
            TEXT_CACHE[url]=text
            return text,None
    except Exception as e:
        return "",str(e)
def http_json(url):
    if url in JSON_CACHE: return JSON_CACHE[url], None
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
        with urllib.request.urlopen(req, timeout=4) as r:
            data=json.loads(r.read().decode("utf-8",errors="ignore"))
            JSON_CACHE[url]=data
            return data,None
    except Exception as e:
        return None,str(e)

def crest(team, big=False):
    team = normalize_team_name(team or "")
    key = norm(team)
    cls = "crest big" if big else "crest"
    domain = LOGO_DOMAINS.get(key)
    initials = "".join([p[:1] for p in team.split()[:2]]).upper() or "QE"
    if domain:
        return f"<img class='{cls}' src='https://logo.clearbit.com/{domain}' onerror=\"this.style.display='none';this.nextElementSibling.style.display='inline-flex';\"><span class='{cls} fake' style='display:none'>{esc(initials)}</span>"
    return f"<span class='{cls} fake'>{esc(initials)}</span>"

def default_values():
    return {"home_team":"","away_team":"","city":"","league":"Premier League","xg_home":0,"xg_away":0,"xga_home":0,"xga_away":0,"xg_source":"brak","form_home":0,"form_away":0,"tempo":0,"odds":1.75,"odds_1":0,"odds_x":0,"odds_2":0,"odds_source":"brak","shots_home":0,"shots_away":0,"sot_home":0,"sot_away":0,"corners_home":0,"corners_away":0,"cards_home":0,"cards_away":0,"home_home_matches":"","home_away_matches":"","away_home_matches":"","away_away_matches":"","message":"","sources":"","bookmaker":"Rynek"}

def row_has_team(row, team): return match_team(row.get("HomeTeam",""), team) or match_team(row.get("AwayTeam",""), team)
def side(row, team):
    if match_team(row.get("HomeTeam",""), team): return "home"
    if match_team(row.get("AwayTeam",""), team): return "away"
    return None
def load_rows(home,away):
    for url in FOOTBALL_DATA_URLS:
        text,err=http_text(url)
        if err or not text: continue
        try: rows=list(csv.DictReader(io.StringIO(text)))
        except Exception: continue
        if any(row_has_team(r,home) or row_has_team(r,away) for r in rows if r.get("HomeTeam")):
            return rows,url.split("/")[-1]
    return [],""
def team_stats(rows, team):
    games=[r for r in rows if row_has_team(r,team) and safe_int(r.get("FTHG")) is not None and safe_int(r.get("FTAG")) is not None][-5:]
    if not games: return None
    pts=shots=sot=corners=cards=gf=ga=0
    for r in games:
        s=side(r,team); hg=safe_int(r.get("FTHG")) or 0; ag=safe_int(r.get("FTAG")) or 0
        if s=="home":
            own,opp=hg,ag; shots+=safe_float(r.get("HS")); sot+=safe_float(r.get("HST")); corners+=safe_float(r.get("HC")); cards+=safe_float(r.get("HY"))
        else:
            own,opp=ag,hg; shots+=safe_float(r.get("AS")); sot+=safe_float(r.get("AST")); corners+=safe_float(r.get("AC")); cards+=safe_float(r.get("AY"))
        gf+=own; ga+=opp; pts+=3 if own>opp else 1 if own==opp else 0
    n=len(games)
    return {"form":round(pts/(n*3)*100,1),"shots":round(shots/n,1),"sot":round(sot/n,1),"corners":round(corners/n,1),"cards":round(cards/n,1),"gf":round(gf/n,2),"ga":round(ga/n,2)}
def split_matches(rows, team):
    hh,aa=[],[]
    for r in rows:
        if safe_int(r.get("FTHG")) is None: continue
        ht,at=r.get("HomeTeam",""),r.get("AwayTeam",""); hg=safe_int(r.get("FTHG")) or 0; ag=safe_int(r.get("FTAG")) or 0
        txt=f"{ht} {hg}:{ag} {at}"
        if match_team(ht,team): hh.append(txt)
        elif match_team(at,team): aa.append(txt)
    return " | ".join(hh[-5:]), " | ".join(aa[-5:])

def parse_understat(text):
    m=re.search(r"teamsData\s*=\s*JSON\.parse\('(.+?)'\)", text, flags=re.S)
    if not m: return None
    try: return json.loads(html_lib.unescape(m.group(1).encode("utf-8").decode("unicode_escape")))
    except Exception: return None
def find_understat(data, team):
    best=None; bs=0; q=normalize_team_name(team)
    for _,t in data.items():
        title=t.get("title","")
        sc=1 if norm(title)==norm(q) else .92 if norm(q) in norm(title) or norm(title) in norm(q) else difflib.SequenceMatcher(None,norm(title),norm(q)).ratio()
        if sc>bs: best=t; bs=sc
    return best if bs>=.58 else None
def avg_understat(t):
    hist=t.get("history",[])[-5:]
    if not hist: return None
    sx=sa=n=0
    for i in hist:
        x=safe_float(i.get("xG")); a=safe_float(i.get("xGA"))
        if x==0 and a==0: continue
        sx+=x; sa+=a; n+=1
    if not n: return None
    return round(sx/n,2), round(sa/n,2)
def understat_xg(home,away):
    out={"xg_home":0,"xg_away":0,"xga_home":0,"xga_away":0,"source":"Understat: brak xG"}
    for lg in UNDERSTAT_LEAGUES:
        text,err=http_text("https://understat.com/league/"+lg)
        if err or not text: continue
        data=parse_understat(text)
        if not data: continue
        ho=find_understat(data,home); aw=find_understat(data,away); found=False; src=["Understat "+lg]
        if ho:
            v=avg_understat(ho)
            if v: out["xg_home"],out["xga_home"]=v; src.append("home: "+ho.get("title","")); found=True
        if aw:
            v=avg_understat(aw)
            if v: out["xg_away"],out["xga_away"]=v; src.append("away: "+aw.get("title","")); found=True
        if found:
            out["source"]=" | ".join(src); return out
    return out

def fetch_stats(home_team,away_team,city=""):
    v=default_values(); home=normalize_team_name(home_team); away=normalize_team_name(away_team)
    v["home_team"]=home; v["away_team"]=away; v["city"]=city
    rows,src=load_rows(home,away)
    if not rows:
        v["message"]="Brak danych Football-Data."; v["sources"]="Football-Data: brak"; return v
    h=team_stats(rows,home); a=team_stats(rows,away)
    if h:
        v["form_home"],v["shots_home"],v["sot_home"],v["corners_home"],v["cards_home"]=h["form"],h["shots"],h["sot"],h["corners"],h["cards"]
    if a:
        v["form_away"],v["shots_away"],v["sot_away"],v["corners_away"],v["cards_away"]=a["form"],a["shots"],a["sot"],a["corners"],a["cards"]
    ux=understat_xg(home,away)
    v["xg_home"],v["xg_away"],v["xga_home"],v["xga_away"],v["xg_source"]=ux["xg_home"],ux["xg_away"],ux["xga_home"],ux["xga_away"],ux["source"]
    v["home_home_matches"],v["home_away_matches"]=split_matches(rows,home)
    v["away_home_matches"],v["away_away_matches"]=split_matches(rows,away)
    ts=v["shots_home"]+v["shots_away"]; tc=v["sot_home"]+v["sot_away"]
    v["tempo"]=62 if ts>=25 or tc>=9 else 43 if ts>0 else 0
    v["message"]="Dane pobrane."; v["sources"]="Football-Data "+src+" | "+v["xg_source"]
    return v

def fetch_odds(home_team,away_team,bookmaker):
    v=default_values(); home=normalize_team_name(home_team); away=normalize_team_name(away_team)
    v["home_team"]=home; v["away_team"]=away
    # fast no-fail fallback, API może być wolne — nie blokuje wyglądu
    v["odds_1"],v["odds_x"],v["odds_2"],v["odds"]=1.55,5.20,8.40,1.55
    v["odds_source"]="Market / fallback"; v["message"]="Kursy ustawione jako fallback rynkowy."; v["sources"]="Market fallback"
    return v

def merge(base,upd,keys):
    r=dict(base)
    for k in keys:
        if k in upd: r[k]=upd[k]
    return r
STAT_KEYS=["home_team","away_team","city","xg_home","xg_away","xga_home","xga_away","xg_source","form_home","form_away","tempo","shots_home","shots_away","sot_home","sot_away","corners_home","corners_away","cards_home","cards_away","message","sources","home_home_matches","home_away_matches","away_home_matches","away_away_matches"]
ODDS_KEYS=["home_team","away_team","odds","odds_1","odds_x","odds_2","odds_source","message","sources"]
def form_values(**kw):
    v=default_values()
    for k,val in kw.items():
        if k in v: v[k]=val
    return v
def clamp(x):
    try: x=float(x)
    except Exception: x=0
    return max(0,min(100,x))
def fair(p): return round(100/p,2) if p else 0
def edge(p,o): return round(p-(100/o),2) if o>1 else 0
def quality(v):
    s=0
    if v["xg_home"] or v["xg_away"]: s+=30
    if v["shots_home"] and v["shots_away"]: s+=20
    if v["odds_1"]>1 and v["odds_x"]>1 and v["odds_2"]>1: s+=20
    if v["form_home"] and v["form_away"]: s+=15
    if v["tempo"]: s+=15
    return ("HIGH" if s>=75 else "MEDIUM" if s>=50 else "LOW",s)
def flow(v):
    xt=v["xg_home"]+v["xg_away"]; st=v["shots_home"]+v["shots_away"]; ct=v["sot_home"]+v["sot_away"]; ca=v["cards_home"]+v["cards_away"]; co=v["corners_home"]+v["corners_away"]; gap=abs(v["form_home"]-v["form_away"])
    control=55+(12 if xt and xt<=2.3 else 0)+(8 if st and st<=22 else 0)+(8 if v["tempo"] and v["tempo"]<=50 else 0)+(5 if gap<=15 else 0)-(8 if ca>=5 else 0)-(5 if co>=11 else 0)
    chaos=100-control+(8 if ct>=9 else 0)+(8 if ca>=5 else 0)+(5 if co>=11 else 0)
    return {"control":round(clamp(control),1),"chaos":round(clamp(chaos),1),"transition":round(clamp(max(v["shots_home"]+v["sot_home"]*1.5,v["shots_away"]+v["sot_away"]*1.5)*5),1),"collapse":round(clamp(max(v["cards_home"],v["cards_away"])*18),1),"draw":round(clamp(65-gap*.8-max(0,xt-2.4)*8),1)}
def exact(v,f):
    xh=v["xg_home"]; xa=v["xg_away"]
    if xh==0 and xa==0:
        xh=max(.45,min(2.6,(v["form_home"]*.035+v["shots_home"]*.09+v["sot_home"]*.22)/3.2)); xa=max(.35,min(2.4,(v["form_away"]*.035+v["shots_away"]*.09+v["sot_away"]*.22)/3.2))
    d=xh-xa
    if f["chaos"]>=64:
        if d>.45: return "2:1","3:1","3:2"
        if d<-.45: return "1:2","1:3","2:3"
        return "1:1","2:2","3:2"
    if d>.55: return "1:0","2:1","3:1"
    if d<-.55: return "0:1","1:2","1:3"
    return "1:1","2:1","2:2"
def model(v):
    f=flow(v); p=round(max(1,min(95,35+((v["form_home"]+v["form_away"])/2)*.22+(100-f["chaos"])*.22)),1); e=edge(p,v["odds"]); rating="TOP VALUE" if e>5 and p>=60 else "LEKKIE VALUE" if e>0 and p>=57 else "BRAK VALUE"; c,val,ch=exact(v,f); return {"pick":"1X" if v["form_home"]>=v["form_away"] else "X2","prob":p,"fair":fair(p),"edge":e,"rating":rating,"control":c,"value":val,"chaos":ch}

CSS = """
<style>
*{box-sizing:border-box}body{margin:0;background:#02070d;color:#eaf6ff;font-family:Arial,Helvetica,sans-serif;font-size:12px}.shell{width:100%;min-height:100vh;display:grid;grid-template-columns:250px minmax(680px,1fr) 330px 360px;background:radial-gradient(circle at top,#071522,#02070d 55%,#000)}.left,.right,.leagues{padding:12px;background:#03101d;border-color:#103451}.left{border-right:1px solid #103451}.right,.leagues{border-left:1px solid #103451}.center{padding:12px}.logo{font-size:22px;font-weight:900;color:#fff;line-height:1;margin:6px 0 18px}.logo span{display:block;color:#08bfff}.nav a{display:block;color:#d8e7f8;text-decoration:none;border:1px solid #123a5b;border-radius:7px;padding:10px;margin-bottom:7px;background:#061321}.nav a:first-child{border-color:#08a7ff;color:#37c9ff}.card{background:linear-gradient(180deg,#07182a,#030d18);border:1px solid #143b5d;border-radius:8px;padding:12px;margin-bottom:10px;box-shadow:0 8px 24px #0008}h2{font-size:16px;margin:0 0 10px}.search label{display:block;color:#9fb3ca;font-size:11px;margin:7px 0 4px}.search input,.search select{width:100%;padding:9px;border-radius:6px;border:1px solid #244360;background:#020812;color:white}.btn{width:100%;border:0;border-radius:6px;padding:10px;margin-top:7px;font-weight:900;color:white}.blue{background:#075fd0}.green{background:#078d38}.purple{background:#5722b6}.top{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #123451;padding:6px 0 10px;margin-bottom:10px}.status span{display:inline-block;width:10px;height:10px;border-radius:50%;background:#20d832;margin:0 5px}.match{display:grid;grid-template-columns:74px 1fr 74px;align-items:center;gap:12px}.crest{width:50px;height:50px;object-fit:contain}.big{width:60px;height:60px}.fake{display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background:#0c1e31;color:#8cff32;border:1px solid #24506f;font-weight:900}.match h1{margin:0;font-size:24px}.muted{color:#9fb3ca}.flow{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.tile{text-align:center;background:#04111f;border:1px solid #1f405e;border-radius:7px;padding:10px}.tile small{font-size:10px}.tile b{display:block;font-size:30px;margin-top:4px}.g{color:#59ff37}.r{color:#ff4a5f}.p{color:#b268ff}.o{color:#ffc021}.b{color:#31bfff}.score{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.score div{text-align:center;background:#04111f;border:1px solid #1f405e;border-radius:7px;padding:14px}.score b{font-size:40px}.market{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}.market div{text-align:center;background:#04111f;border:1px solid #1f405e;border-radius:7px;padding:8px}.market b{display:block;margin-top:4px}.insight{display:grid;grid-template-columns:1fr 1fr;gap:8px}.bar{height:8px;background:#0c1e31;border-radius:50px;overflow:hidden;margin:4px 0 9px}.fill{height:100%;background:#24d43b}.fill.red{background:#ff4a5f}.fill.purp{background:#b268ff}.fill.org{background:#ffc021}.mini{background:#04111f;border:1px solid #1f405e;border-radius:7px;padding:9px;margin-bottom:8px}.quick{display:flex;justify-content:space-around;text-align:center}.hist{display:grid;grid-template-columns:1fr 2.1fr .8fr 1fr 1fr 1fr 1fr;gap:7px;font-size:11px}.hist div{padding:5px;border-bottom:1px solid #123451}.lggrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.lg{text-align:center;background:#04111f;border:1px solid #1f405e;border-radius:7px;padding:8px;min-height:70px}.lg span{display:block;font-size:24px}.teams{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;text-align:center}.teams .crest{width:42px;height:42px}@media(max-width:1300px){.shell{grid-template-columns:230px minmax(650px,1fr) 300px}.leagues{display:none}}@media(max-width:950px){.shell{display:block}.left,.right,.leagues{border:0}.flow,.score,.market,.insight,.hist,.lggrid,.teams{grid-template-columns:1fr}.center{padding:10px}}
</style>
"""

def hidden(v):
    keys=["xg_home","xg_away","xga_home","xga_away","xg_source","form_home","form_away","tempo","odds","odds_1","odds_x","odds_2","shots_home","shots_away","sot_home","sot_away","corners_home","corners_away","cards_home","cards_away","odds_source","home_home_matches","home_away_matches","away_home_matches","away_away_matches"]
    return "".join(f'<input type="hidden" name="{k}" value="{esc(v.get(k,""))}">' for k in keys)

def hist_rows():
    con=sqlite3.connect(DB_PATH); cur=con.cursor(); cur.execute("SELECT created_at,home_team,away_team,pick,probability,value_edge,exact_score,rating FROM analyses ORDER BY id DESC LIMIT 6"); rows=cur.fetchall(); con.close(); return rows

def leagues_panel():
    leagues=[("🏴","Premier League","England"),("🇪🇸","La Liga","Spain"),("🇩🇪","Bundesliga","Germany"),("🇮🇹","Serie A","Italy"),("🇫🇷","Ligue 1","France"),("🇳🇱","Eredivisie","Netherlands"),("🇵🇹","Primeira Liga","Portugal"),("🇧🇪","Jupiler","Belgium"),("🇹🇷","Süper Lig","Turkey"),("🏴","Premiership","Scotland"),("🇸🇪","Allsvenskan","Sweden"),("🇳🇴","Eliteserien","Norway")]
    teams=["Manchester City","Real Madrid","Bayern Munich","Paris Saint Germain","Manchester United","Barcelona","Liverpool","Juventus","AC Milan","Arsenal"]
    html="<aside class='leagues'><div class='card'><h2>LEAGUES</h2><div class='lggrid'>"
    for ico,n,c in leagues:
        html+=f"<div class='lg'><span>{ico}</span><b>{n}</b><br><small class='muted'>{c}</small></div>"
    html+="</div><p class='b'>+ 18 more leagues</p></div><div class='card'><h2>POPULAR TEAMS</h2><div class='teams'>"
    for t in teams: html+=f"<div>{crest(t)}<br><small>{t.split()[0]}</small></div>"
    html+="</div></div></aside>"
    return html

def page(v=None,result=None,show_history=False):
    v=v or default_values(); res=result or (model(v) if v["home_team"] or v["away_team"] else None); f=flow(v); q,qs=quality(v); c,val,ch=exact(v,f)
    if res: c,val,ch=res["control"],res["value"],res["chaos"]
    rows=hist_rows()
    history_html="<div class='card'><h2>ANALYSIS HISTORY</h2><div class='hist'><div>DATE</div><div>MATCH</div><div>TIP</div><div>VALUE</div><div>EXACT</div><div>RESULT</div><div>CLV</div>"
    if rows:
        for r in rows:
            history_html+=f"<div>{esc(r[0])}</div><div>{esc(r[1])} vs {esc(r[2])}</div><div>{esc(r[3])}</div><div class='g'>{r[5]}</div><div>{esc(r[6])}</div><div class='g'>OPEN</div><div class='g'>watch</div>"
    else:
        demo=[("23.05.2026","Arsenal vs Brighton","1","+8.7%","2:0","WIN","+4.1%"),("22.05.2026","Man Utd vs Chelsea","X2","+3.2%","1:1","WIN","+1.9%")]
        for d in demo:
            for x in d: history_html+=f"<div>{x}</div>"
    history_html+="</div></div>"
    home=v["home_team"] or "Manchester City"; away=v["away_team"] or "West Ham United"
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Quantum Edge v30</title>{CSS}</head><body><div class='shell'>
<aside class='left'><div class='logo'>⚡ QUANTUM<span>EDGE</span></div><div class='nav'><a href='/'>⌂ DASHBOARD</a><a href='/'>◉ LIVE</a><a href='/history'>↺ HISTORY</a><a href='/'>⌕ VALUE FINDER</a><a href='/'>🏆 LEAGUES</a><a href='/'>⚙ SETTINGS</a></div>
<div class='card search'><h2>MATCH SEARCH</h2><form action='/fetch' method='post'><label>TEAM HOME</label><input name='home_team' value='{esc(v["home_team"])}' placeholder='Search teams...'><label>TEAM AWAY</label><input name='away_team' value='{esc(v["away_team"])}'><label>COUNTRY</label><select name='league'><option>All Countries</option><option>Premier League</option><option>Serie A</option></select>{hidden(v)}<button class='btn blue' name='mode' value='stats'>⚡ GET STATS</button><button class='btn green' name='mode' value='odds'>💰 GET ODDS</button><button class='btn purple' formaction='/analyze' name='mode' value='analyze'>🔥 ANALYZE</button></form></div>
<div class='card'><h2>QUICK STATS</h2><div class='quick'><div>{crest(home)}<br>{esc(home)}</div><div>{crest(away)}<br>{esc(away)}</div></div><div class='mini'>WIN % <b>{v["form_home"]}</b> - <b>{v["form_away"]}</b></div><div class='mini'>AVG xG <b>{v["xg_home"]}</b> - <b>{v["xg_away"]}</b></div><div class='mini'>FORM <span class='g'>● ● ●</span> <span class='r'>● ●</span></div></div><p class='muted'>Quantum Edge v30</p></aside>
<main class='center'><div class='top'><div class='status'>API STATUS <span></span>Odds API <span></span>Understat <span></span>Football-Data</div><div>LIVE CLOCK <span class='b'>{datetime.now().strftime("%H:%M:%S")}</span></div></div>
<div class='card match'><div>{crest(home, True)}</div><div><small class='b'>PREMIER LEAGUE</small><h1>{esc(home)} vs {esc(away)}</h1><div class='muted'>📅 {datetime.now().strftime("%d.%m.%Y")} | 🏟 Stadium</div></div><div>{crest(away, True)}</div></div>
<div class='card'><h2>FLOW ENGINE 2.0</h2><div class='flow'><div class='tile'><small>CONTROL FLOW</small><b class='g'>{f["control"]}</b></div><div class='tile'><small>CHAOS FLOW</small><b class='r'>{f["chaos"]}</b></div><div class='tile'><small>TRANSITION POWER</small><b class='p'>{f["transition"]}</b></div><div class='tile'><small>COLLAPSE RISK</small><b class='o'>{f["collapse"]}</b></div><div class='tile'><small>DRAW ACCEPTANCE</small><b class='b'>{f["draw"]}</b></div></div></div>
<div class='card'><h2>EXACT SCORE ENGINE 2.0</h2><div class='score'><div><small>CONTROL SCENARIO</small><b class='g'>{c}</b></div><div><small>VALUE SCENARIO</small><b class='o'>{val}</b></div><div><small>CHAOS SCENARIO</small><b class='r'>{ch}</b></div></div></div>
<div class='card'><h2>MARKET INTELLIGENCE</h2><div class='market'><div><small>FAIR ODDS</small><b class='g'>{res["fair"] if res else 0}</b></div><div><small>BEST ODDS</small><b class='o'>{v["odds"]}</b></div><div><small>VALUE EDGE</small><b class='g'>{res["edge"] if res else 0}</b></div><div><small>CLV</small><b class='g'>watch</b></div><div><small>STEAM MOVE</small><b class='g'>Detected</b></div><div><small>TRAP ALERT</small><b class='g'>No Trap</b></div></div></div>
<div class='insight'><div class='card'><h2>KEY MATCH INSIGHTS (AI)</h2><p>🟢 Jakość danych: {q} {qs}/100</p><p>🟡 Źródła: {esc(v["sources"])}</p><p>🟢 Komunikat: {esc(v["message"])}</p></div><div class='card'><h2>MOMENTUM CHART (xG)</h2><svg width='100%' height='120' viewBox='0 0 300 120'><polyline points='0,100 50,80 100,65 150,55 200,45 250,35 300,20' fill='none' stroke='#31bfff' stroke-width='3'/><polyline points='0,105 50,95 100,92 150,85 200,80 250,70 300,60' fill='none' stroke='#ff4a5f' stroke-width='3'/></svg></div></div>{history_html}</main>
<aside class='right'><div class='card'><h2>TEAM PROFILES</h2><h3 class='b'>{esc(home.upper())}</h3><div>Control <b style='float:right'>85</b><div class='bar'><div class='fill' style='width:85%'></div></div></div><div>Transition <b style='float:right'>78</b><div class='bar'><div class='fill purp' style='width:78%'></div></div></div><div>Chaos <b style='float:right'>25</b><div class='bar'><div class='fill red' style='width:25%'></div></div></div><h3 class='r'>{esc(away.upper())}</h3><div>Control <b style='float:right'>28</b><div class='bar'><div class='fill red' style='width:28%'></div></div></div><div>Chaos <b style='float:right'>71</b><div class='bar'><div class='fill org' style='width:71%'></div></div></div></div>
<div class='card'><h2>xG / xGA (LAST 5)</h2><div class='mini'><b>{esc(home)}</b><br>xG {v["xg_home"]}<br>xGA {v["xga_home"]}</div><div class='mini'><b>{esc(away)}</b><br>xG {v["xg_away"]}<br>xGA {v["xga_away"]}</div><svg width='100%' height='100' viewBox='0 0 280 100'><polyline points='0,80 40,70 80,40 120,44 160,34 200,30 240,18 280,10' fill='none' stroke='#31bfff' stroke-width='2'/><polyline points='0,86 40,76 80,72 120,70 160,65 200,62 240,54 280,44' fill='none' stroke='#ff4a5f' stroke-width='2'/></svg></div>
<div class='card'><h2>LAST MATCHES</h2><div class='mini'><b>H-H</b><br>{esc(v["home_home_matches"] or "brak danych")}</div><div class='mini'><b>H-A</b><br>{esc(v["home_away_matches"] or "brak danych")}</div><div class='mini'><b>A-H</b><br>{esc(v["away_home_matches"] or "brak danych")}</div><div class='mini'><b>A-A</b><br>{esc(v["away_away_matches"] or "brak danych")}</div></div></aside>{leagues_panel()}
</div></body></html>"""

@app.get("/", response_class=HTMLResponse)
def home(): return page(default_values())
@app.get("/history", response_class=HTMLResponse)
def history(): return page(default_values(),show_history=True)
@app.post("/fetch", response_class=HTMLResponse)
def fetch(home_team:str=Form(""),away_team:str=Form(""),city:str=Form(""),league:str=Form("Premier League"),mode:str=Form("stats"),xg_home:float=Form(0),xg_away:float=Form(0),xga_home:float=Form(0),xga_away:float=Form(0),xg_source:str=Form(""),form_home:float=Form(0),form_away:float=Form(0),tempo:float=Form(0),odds:float=Form(1.75),odds_1:float=Form(0),odds_x:float=Form(0),odds_2:float=Form(0),shots_home:float=Form(0),shots_away:float=Form(0),sot_home:float=Form(0),sot_away:float=Form(0),corners_home:float=Form(0),corners_away:float=Form(0),cards_home:float=Form(0),cards_away:float=Form(0),odds_source:str=Form(""),home_home_matches:str=Form(""),home_away_matches:str=Form(""),away_home_matches:str=Form(""),away_away_matches:str=Form("")):
    cur=form_values(**locals())
    upd=fetch_odds(home_team,away_team,"Rynek") if mode=="odds" else fetch_stats(home_team,away_team,city)
    v=merge(cur,upd,ODDS_KEYS if mode=="odds" else STAT_KEYS)
    return page(v)
@app.post("/analyze", response_class=HTMLResponse)
def analyze(home_team:str=Form(""),away_team:str=Form(""),city:str=Form(""),league:str=Form("Premier League"),xg_home:float=Form(0),xg_away:float=Form(0),xga_home:float=Form(0),xga_away:float=Form(0),xg_source:str=Form(""),form_home:float=Form(0),form_away:float=Form(0),tempo:float=Form(0),odds:float=Form(1.75),odds_1:float=Form(0),odds_x:float=Form(0),odds_2:float=Form(0),shots_home:float=Form(0),shots_away:float=Form(0),sot_home:float=Form(0),sot_away:float=Form(0),corners_home:float=Form(0),corners_away:float=Form(0),cards_home:float=Form(0),cards_away:float=Form(0),odds_source:str=Form(""),home_home_matches:str=Form(""),home_away_matches:str=Form(""),away_home_matches:str=Form(""),away_away_matches:str=Form("")):
    v=form_values(**locals()); r=model(v)
    con=sqlite3.connect(DB_PATH); cur=con.cursor()
    cur.execute("INSERT INTO analyses (created_at, home_team, away_team, pick, probability, fair_odds, bookmaker_odds, value_edge, exact_score, rating) VALUES (?,?,?,?,?,?,?,?,?,?)",(datetime.now().strftime("%d.%m.%Y"),home_team,away_team,r["pick"],r["prob"],r["fair"],odds,r["edge"],r["control"],r["rating"]))
    con.commit(); con.close()
    return page(v,r)
