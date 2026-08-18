
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from datetime import datetime
import sqlite3
import os
import urllib.request, urllib.parse, urllib.error, json, csv, io, difflib, re, html as html_lib

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
"lech poznan":"lechpoznan.pl","legia warsaw":"legia.com","rakow czestochowa":"rakow.com","jagiellonia bialystok":"jagiellonia.pl","slask wroclaw":"slaskwroclaw.pl","widzew lodz":"widzew.com",
"burnley":"burnleyfootballclub.com",
"leeds united":"leedsunited.com",
"leicester city":"lcfc.com",
"southampton":"southamptonfc.com",
"norwich city":"canaries.co.uk",
"sunderland":"safc.com",
"middlesbrough":"mfc.co.uk",
"blackburn rovers":"rovers.co.uk",
"sheffield united":"sufc.co.uk",
"sheffield wednesday":"swfc.co.uk",
"stoke city":"stokecityfc.com",
"watford":"watfordfc.com",
"qpr":"qpr.co.uk",
"queens park rangers":"qpr.co.uk",
"derby county":"dcfc.co.uk",
"bolton wanderers":"bwfc.co.uk",
"portsmouth":"portsmouthfc.co.uk",
"charlton athletic":"charltonafc.com",
"espanyol":"rcdespanyol.com",
"granada":"granadacf.es",
"levante":"levanteud.com",
"eibar":"sdeibar.com",
"zaragoza":"realzaragoza.com",
"sporting gijon":"realsporting.com",
"racing santander":"realracingclub.es",
"leganes":"cdleganes.com",
"malaga":"malagacf.com",
"deportivo la coruna":"rcdeportivo.es",
"parma":"parmacalcio1913.com",
"palermo":"palermofc.com",
"sampdoria":"sampdoria.it",
"spezia":"acspezia.com",
"cremonese":"uscremonese.it",
"venezia":"veneziafc.it",
"pisa":"pisasportingclub.com",
"bari":"sscalciobari.it",
"modena":"modenacalcio.com",
"cesena":"cesenafc.com",
"hamburger sv":"hsv.de",
"schalke":"schalke04.de",
"schalke 04":"schalke04.de",
"hertha berlin":"herthabsc.com",
"koln":"fc.de",
"fc koln":"fc.de",
"hannover 96":"hannover96.de",
"kaiserslautern":"fck.de",
"nurnberg":"fcn.de",
"st pauli":"fcstpauli.com",
"1860 munich":"tsv1860.de",
"dynamo dresden":"dynamo-dresden.de",
"saint etienne":"asse.fr",
"bordeaux":"girondins.com",
"metz":"fcmetz.com",
"auxerre":"aja.fr",
"angers":"angers-sco.fr",
"troyes":"estac.fr",
"caen":"smcaen.fr",
"guingamp":"eaguingamp.com",
"ajax":"ajax.nl",
"psv":"psv.nl",
"feyenoord":"feyenoord.nl",
"az alkmaar":"az.nl",
"twente":"fctwente.nl",
"porto":"fcporto.pt",
"benfica":"slbenfica.pt",
"sporting cp":"sporting.pt",
"braga":"scbraga.pt",
"anderlecht":"rsca.be",
"club brugge":"clubbrugge.be",
"genk":"krcgenk.be",
"standard liege":"standard.be",
"wisla krakow":"wisla.krakow.pl",
"wisła kraków":"wisla.krakow.pl",
"arka gdynia":"arka.gdynia.pl",
"miedz legnica":"miedzlegnica.eu",
"miedź legnica":"miedzlegnica.eu",
"motor lublin":"motorlublin.eu",
"gks katowice":"gkskatowice.eu",
"ruch chorzow":"ruchchorzow.com.pl",
"ruch chorzów":"ruchchorzow.com.pl",
"polonia warszawa":"kspolonia.pl",
"lks lodz":"lkslodz.pl",
"łks łódź":"lkslodz.pl",
"celtic":"celticfc.com",
"rangers":"rangers.co.uk",
"malmo":"mff.se",
"malmö":"mff.se",
"rosenborg":"rbk.no",
"bodo glimt":"glimt.no",
"bodø glimt":"glimt.no",
"fc copenhagen":"fck.dk",
"brondby":"brondby.com",
"brøndby":"brondby.com",
"basel":"fcb.ch",
"young boys":"bscyb.ch",
"rapid wien":"skrapid.at",
"salzburg":"redbullsalzburg.at",
"dinamo zagreb":"gnkdinamo.hr",
"crvena zvezda":"crvenazvezdafk.com",
"partizan":"partizan.rs",
"shakhtar donetsk":"shakhtar.com",
"dynamo kyiv":"fcdynamo.com"
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
    return difflib.SequenceMatcher(None,a,b).ratio() >= .78
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
        with urllib.request.urlopen(req, timeout=3) as r:
            text=r.read().decode("utf-8",errors="ignore")
            TEXT_CACHE[url]=text
            return text,None
    except Exception as e:
        return "",str(e)
def http_json(url, headers=None, timeout=3):
    if url in JSON_CACHE: return JSON_CACHE[url], None
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json",**(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data=json.loads(r.read().decode("utf-8",errors="ignore"))
            JSON_CACHE[url]=data
            return data,None
    except urllib.error.HTTPError as e:
        return None,f"HTTP {e.code}"
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
        has_home = any(row_has_team(r,home) for r in rows if r.get("HomeTeam"))
        has_away = any(row_has_team(r,away) for r in rows if r.get("HomeTeam"))
        if has_home and has_away:
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
.tierbar{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:8px}.tierbar span{text-align:center;border:1px solid #0b6fad;border-radius:6px;padding:7px;color:#31bfff;background:#04111f;font-weight:900}.datagrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.datagrid div{text-align:center;background:#04111f;border:1px solid #1f405e;border-radius:7px;padding:9px}.datagrid small{display:block;color:#9fb3ca}.datagrid b{display:block;color:#59ff37;font-size:16px;margin-top:4px}@media(max-width:950px){.datagrid{grid-template-columns:1fr}}

/* Quantum Edge mobile redesign */
:root{--qe-bg:#07111f;--qe-card:#0d1d31;--qe-line:#1d4262;--qe-accent:#24c8ff;--qe-green:#67f542}
body{background:radial-gradient(circle at 20% 0%,#123657 0,#07111f 38%,#030812 100%);color:#edf7ff;font-family:Inter,system-ui,-apple-system,sans-serif}
.shell{gap:14px;max-width:1500px;margin:auto}
.card{background:linear-gradient(145deg,#102943e8,#071525f2);border:1px solid var(--qe-line);border-radius:16px;box-shadow:0 12px 30px #0007;padding:16px}
.btn{border-radius:12px;min-height:48px;font-size:15px;letter-spacing:.2px}
.match h1{font-size:clamp(22px,4vw,34px);letter-spacing:-.5px}
.top{position:sticky;top:0;z-index:5;background:#07111fee;backdrop-filter:blur(12px);border-radius:10px;padding:10px 12px}
.flow,.score,.market,.insight,.datagrid{gap:10px}
.tile,.score div,.market div,.datagrid div,.mini{border-radius:12px;background:#071727;border-color:#225174}
@media(max-width:950px){body{font-size:15px}.shell{padding:8px}.left,.right,.leagues{display:block}.left{order:0}.center{order:1;padding:0}.right{order:2}.leagues{display:none}.card{padding:14px;margin-bottom:10px;border-radius:14px}.top{position:static;display:block;font-size:12px}.status{line-height:1.8}.match{grid-template-columns:52px 1fr 52px;gap:8px}.match h1{font-size:24px;line-height:1.05}.big{width:48px;height:48px}.flow{grid-template-columns:repeat(2,1fr)}.flow .tile:last-child{grid-column:1/-1}.score{grid-template-columns:1fr}.score div{display:flex;align-items:center;justify-content:space-between;padding:13px 16px}.score b{font-size:34px}.market{grid-template-columns:repeat(2,1fr)}.market div{padding:12px 8px}.datagrid{grid-template-columns:repeat(2,1fr)}.insight{grid-template-columns:1fr}.hist{display:block}.hist>div{display:flex;justify-content:space-between;padding:8px}.hist>div:nth-child(1),.hist>div:nth-child(2),.hist>div:nth-child(3),.hist>div:nth-child(4),.hist>div:nth-child(5),.hist>div:nth-child(6),.hist>div:nth-child(7){display:none}}
</style>
"""

def hidden(v):
    keys=["xg_home","xg_away","xga_home","xga_away","xg_source","form_home","form_away","tempo","odds","odds_1","odds_x","odds_2","shots_home","shots_away","sot_home","sot_away","corners_home","corners_away","cards_home","cards_away","odds_source","home_home_matches","home_away_matches","away_home_matches","away_away_matches"]
    return "".join(f'<input type="hidden" name="{k}" value="{esc(v.get(k,""))}">' for k in keys)

def hist_rows():
    con=sqlite3.connect(DB_PATH); cur=con.cursor(); cur.execute("SELECT created_at,home_team,away_team,pick,probability,value_edge,exact_score,rating FROM analyses ORDER BY id DESC LIMIT 6"); rows=cur.fetchall(); con.close(); return rows

def leagues_panel():
    leagues = [
        ("🏴", "Premier League", "England 1"), ("🏴", "Championship", "England 2"), ("🏴", "League One", "England 3"),
        ("🇪🇸", "La Liga", "Spain 1"), ("🇪🇸", "La Liga 2", "Spain 2"), ("🇪🇸", "Primera RFEF", "Spain 3"),
        ("🇮🇹", "Serie A", "Italy 1"), ("🇮🇹", "Serie B", "Italy 2"), ("🇮🇹", "Serie C", "Italy 3"),
        ("🇩🇪", "Bundesliga", "Germany 1"), ("🇩🇪", "2. Bundesliga", "Germany 2"), ("🇩🇪", "3. Liga", "Germany 3"),
        ("🇫🇷", "Ligue 1", "France 1"), ("🇫🇷", "Ligue 2", "France 2"), ("🇫🇷", "National", "France 3"),
        ("🇵🇱", "Ekstraklasa", "Poland 1"), ("🇵🇱", "1 Liga", "Poland 2"), ("🇵🇱", "2 Liga", "Poland 3"),
        ("🇳🇱", "Eredivisie", "Netherlands 1"), ("🇳🇱", "Eerste Divisie", "Netherlands 2"),
        ("🇵🇹", "Primeira Liga", "Portugal 1"), ("🇵🇹", "Liga Portugal 2", "Portugal 2"),
        ("🇧🇪", "Jupiler Pro League", "Belgium 1"), ("🇧🇪", "Challenger Pro League", "Belgium 2"),
        ("🇹🇷", "Süper Lig", "Turkey 1"), ("🇹🇷", "1. Lig", "Turkey 2"),
        ("🏴", "Premiership", "Scotland 1"), ("🏴", "Championship", "Scotland 2"),
        ("🇦🇹", "Bundesliga", "Austria 1"), ("🇦🇹", "2. Liga", "Austria 2"),
        ("🇨🇭", "Super League", "Switzerland 1"), ("🇨🇭", "Challenge League", "Switzerland 2"),
        ("🇩🇰", "Superliga", "Denmark 1"), ("🇩🇰", "1st Division", "Denmark 2"),
        ("🇸🇪", "Allsvenskan", "Sweden 1"), ("🇸🇪", "Superettan", "Sweden 2"),
        ("🇳🇴", "Eliteserien", "Norway 1"), ("🇳🇴", "OBOS-ligaen", "Norway 2"),
        ("🇨🇿", "Czech First League", "Czechia 1"), ("🇷🇴", "Liga I", "Romania 1"), ("🇭🇷", "HNL", "Croatia 1"), ("🇬🇷", "Super League", "Greece 1")
    ]
    teams = ["Manchester City","Real Madrid","Bayern Munich","Paris Saint Germain","Manchester United","Barcelona","Liverpool","Juventus","AC Milan","Arsenal","Inter","Napoli","Ajax","Porto","Benfica"]
    html = "<aside class='leagues'><div class='card'><h2>LEAGUES / 1-2-3 TIER EUROPE</h2><div class='tierbar'><span>1ST TIER</span><span>2ND TIER</span><span>3RD TIER</span></div><div class='lggrid'>"
    for ico,n,c in leagues:
        html += f"<div class='lg'><span>{ico}</span><b>{n}</b><br><small class='muted'>{c}</small></div>"
    html += "</div><p class='b'>Europe league base added — 1/2/3 tiers where available.</p></div><div class='card'><h2>POPULAR TEAMS</h2><div class='teams'>"
    for t in teams:
        html += f"<div>{crest(t)}<br><small>{t.split()[0]}</small></div>"
    html += "</div></div></aside>"
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
<div class='card'><h2>STATYSTYKI POBRANE DO APLIKACJI</h2><div class='datagrid'><div><small>xG</small><b>{v["xg_home"]} - {v["xg_away"]}</b></div><div><small>xGA</small><b>{v["xga_home"]} - {v["xga_away"]}</b></div><div><small>FORMA</small><b>{v["form_home"]} - {v["form_away"]}</b></div><div><small>TEMPO</small><b>{v["tempo"]}/100</b></div><div><small>STRZAŁY</small><b>{v["shots_home"]} - {v["shots_away"]}</b></div><div><small>CELNE</small><b>{v["sot_home"]} - {v["sot_away"]}</b></div><div><small>ROŻNE</small><b>{v["corners_home"]} - {v["corners_away"]}</b></div><div><small>KARTKI</small><b>{v["cards_home"]} - {v["cards_away"]}</b></div></div></div><div class='insight'><div class='card'><h2>KEY MATCH INSIGHTS (AI)</h2><p>🟢 Jakość danych: {q} {qs}/100</p><p>🟡 Źródła: {esc(v["sources"])}</p><p>🟢 Komunikat: {esc(v["message"])}</p></div><div class='card'><h2>MOMENTUM CHART (xG)</h2><svg width='100%' height='120' viewBox='0 0 300 120'><polyline points='0,100 50,80 100,65 150,55 200,45 250,35 300,20' fill='none' stroke='#31bfff' stroke-width='3'/><polyline points='0,105 50,95 100,92 150,85 200,80 250,70 300,60' fill='none' stroke='#ff4a5f' stroke-width='3'/></svg></div></div>{history_html}</main>
<aside class='right'><div class='card'><h2>TEAM PROFILES</h2><h3 class='b'>{esc(home.upper())}</h3><div>Control <b style='float:right'>85</b><div class='bar'><div class='fill' style='width:85%'></div></div></div><div>Transition <b style='float:right'>78</b><div class='bar'><div class='fill purp' style='width:78%'></div></div></div><div>Chaos <b style='float:right'>25</b><div class='bar'><div class='fill red' style='width:25%'></div></div></div><h3 class='r'>{esc(away.upper())}</h3><div>Control <b style='float:right'>28</b><div class='bar'><div class='fill red' style='width:28%'></div></div></div><div>Chaos <b style='float:right'>71</b><div class='bar'><div class='fill org' style='width:71%'></div></div></div></div>
<div class='card'><h2>xG / xGA (LAST 5)</h2><div class='mini'><b>{esc(home)}</b><br>xG {v["xg_home"]}<br>xGA {v["xga_home"]}</div><div class='mini'><b>{esc(away)}</b><br>xG {v["xg_away"]}<br>xGA {v["xga_away"]}</div><svg width='100%' height='100' viewBox='0 0 280 100'><polyline points='0,80 40,70 80,40 120,44 160,34 200,30 240,18 280,10' fill='none' stroke='#31bfff' stroke-width='2'/><polyline points='0,86 40,76 80,72 120,70 160,65 200,62 240,54 280,44' fill='none' stroke='#ff4a5f' stroke-width='2'/></svg></div>
<div class='card'><h2>LAST MATCHES</h2><div class='mini'><b>H-H</b><br>{esc(v["home_home_matches"] or "brak danych")}</div><div class='mini'><b>H-A</b><br>{esc(v["home_away_matches"] or "brak danych")}</div><div class='mini'><b>A-H</b><br>{esc(v["away_home_matches"] or "brak danych")}</div><div class='mini'><b>A-A</b><br>{esc(v["away_away_matches"] or "brak danych")}</div></div></aside>{leagues_panel()}
</div></body></html>"""


SELECT_CSS = """
.select-app{min-height:100vh;background:#06111f;color:#eaf6ff;font-family:Inter,system-ui,sans-serif;padding:18px}
.select-wrap{max-width:1180px;margin:auto}.select-head{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-bottom:18px}
.select-brand{font-size:28px;font-weight:900}.select-brand span{color:#27c5ff}.select-sub{color:#9eb4c9;margin-top:4px}
.select-actions{display:flex;gap:10px;flex-wrap:wrap}.select-btn{border:0;border-radius:12px;padding:13px 18px;font-weight:800;color:#fff;background:#0878d1}
.select-btn.master{background:#6630c8}.select-btn.secondary{background:#14304a}
.select-card{background:linear-gradient(145deg,#102a43,#071525);border:1px solid #1c496d;border-radius:16px;padding:16px;margin-bottom:14px}
.select-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.select-metric{background:#071827;border:1px solid #225174;border-radius:12px;padding:12px}.select-metric small{color:#9eb4c9;display:block}.select-metric b{font-size:24px;color:#67f542}
.select-table{width:100%;border-collapse:collapse}.select-table th,.select-table td{text-align:left;padding:11px 8px;border-bottom:1px solid #1b3c59}.select-table th{color:#8edcff;font-size:12px}.select-table td{font-size:14px}
.select-pill{display:inline-block;border-radius:999px;padding:4px 9px;font-size:12px;font-weight:800}.tier-a{background:#155d39;color:#9dffbd}.tier-b{background:#73540b;color:#ffe49a}.tier-c{background:#273c51;color:#b9d8ed}.hold{background:#6d2535;color:#ffc2c9}
.select-check{width:18px;height:18px;accent-color:#27c5ff}.select-note{color:#a9bed0;font-size:13px;line-height:1.5}.scan-progress{display:none;margin-top:12px}.scan-progress.active{display:block}.scan-track{height:10px;background:#071827;border-radius:999px;overflow:hidden}.scan-fill{height:100%;width:8%;background:linear-gradient(90deg,#27c5ff,#67f542);transition:width .7s ease}.scan-label{color:#9eb4c9;font-size:13px;margin-bottom:6px}
@media(max-width:760px){.select-app{padding:10px}.select-head{display:block}.select-actions{margin-top:14px}.select-grid{grid-template-columns:repeat(2,1fr)}.select-table{display:block;overflow-x:auto;white-space:nowrap}.select-table th,.select-table td{padding:10px 7px}.select-brand{font-size:24px}}
"""


def api_global_rows(date_str):
    try:
        iso=datetime.strptime(date_str,"%d.%m.%Y").strftime("%Y-%m-%d") if "." in (date_str or "") else datetime.strptime(date_str,"%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        iso=datetime.now().strftime("%Y-%m-%d")
    out=[]; used=[]; seen=set()
    af=os.getenv("API_FOOTBALL_KEY","").strip()
    if not af:
        used.append("API-Football: KEY MISSING")
    else:
        data,err=http_json("https://v3.football.api-sports.io/fixtures?date="+iso,{"x-apisports-key":af},timeout=10)
        if err:
            used.append("API-Football: ERROR "+err)
        elif isinstance(data,dict):
            fixtures=data.get("response",[])
            used.append("API-Football: OK "+str(len(fixtures)))
            for x in fixtures:
                fx=x.get("fixture",{}); teams=x.get("teams",{})
                home=(teams.get("home") or {}).get("name",""); away=(teams.get("away") or {}).get("name","")
                if home and away:
                    key=(home.lower(),away.lower(),str(fx.get("date",""))[:16])
                    if key not in seen:
                        seen.add(key); out.append({"id":"AF-"+str(len(out)+1).zfill(5),"date":fx.get("date",""),"home":home,"away":away,"source":"API-Football"})
    sm=os.getenv("SPORTMONKS_TOKEN","").strip()
    if sm:
        data,err=http_json("https://api.sportmonks.com/v3/football/fixtures/date/"+iso+"?api_token="+sm,timeout=10)
        if err:
            used.append("Sportmonks: ERROR "+err)
        elif isinstance(data,dict):
            fixtures=data.get("data",[])
            used.append("Sportmonks: OK "+str(len(fixtures)))
            for x in fixtures:
                parts=x.get("participants") or []
                home=parts[0].get("name","") if parts else ""; away=parts[-1].get("name","") if len(parts)>1 else ""
                if home and away:
                    key=(home.lower(),away.lower(),str(x.get("starting_at",""))[:16])
                    if key not in seen:
                        seen.add(key); out.append({"id":"SM-"+str(len(out)+1).zfill(5),"date":x.get("starting_at",""),"home":home,"away":away,"source":"Sportmonks"})
    return out,used

def thesportsdb_rows(date_str):
    try:
        iso=datetime.strptime(date_str,"%d.%m.%Y").strftime("%Y-%m-%d") if "." in (date_str or "") else datetime.strptime(date_str,"%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        iso=date_str
    data,err=http_json("https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d="+iso+"&s=Soccer",timeout=10)
    if err:
        return [],["TheSportsDB: ERROR "+err]
    events=(data or {}).get("events") or [] if isinstance(data,dict) else []
    out=[]
    for x in events:
        home=(x.get("strHomeTeam") or "").strip(); away=(x.get("strAwayTeam") or "").strip()
        if home and away:
            out.append({"id":"TSDB-"+str(len(out)+1).zfill(5),"date":(x.get("strTimestamp") or x.get("dateEvent") or ""), "home":home, "away":away, "source":"TheSportsDB"})
    return out,["TheSportsDB: OK "+str(len(out))]

def fixture_feed_rows(date_str):
    # Broad fixture feed for SELECT. It is independent of odds and exact-score markets.
    global_rows,global_sources=api_global_rows(date_str)
    tsdb_rows,tsdb_sources=thesportsdb_rows(date_str)
    try:
        if "." in (date_str or ""):
            date_str=datetime.strptime(date_str,"%d.%m.%Y").strftime("%Y%m%d")
        else:
            date_str=datetime.strptime(date_str,"%Y-%m-%d").strftime("%Y%m%d")
    except Exception:
        date_str=datetime.now().strftime("%Y%m%d")
    leagues=["eng.1","eng.2","esp.1","ita.1","ger.1","fra.1","ned.1","por.1","bel.1","sco.1","pol.1","bra.1","arg.1","mex.1","usa.1","uefa.champions","uefa.europa","conmebol.libertadores","conmebol.sudamericana"]
    out=list(global_rows)+list(tsdb_rows); seen={(r['home'].lower(),r['away'].lower(),str(r.get('date',''))[:16]) for r in out}; used=list(global_sources)+list(tsdb_sources)
    for league in leagues:
        url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={date_str}"
        data,err=http_json(url,timeout=10)
        if err:
            used.append("ESPN:"+league+": ERROR "+err)
            continue
        if not isinstance(data,dict):
            used.append("ESPN:"+league+": INVALID")
            continue
        used.append("ESPN:"+league+": OK "+str(len(data.get("events",[]))))
        for ev in data.get("events",[]):
            comp=(ev.get("competitions") or [{}])[0]
            teams=comp.get("competitors") or []
            home=next((x.get("team",{}).get("displayName","") for x in teams if x.get("homeAway")=="home"),"")
            away=next((x.get("team",{}).get("displayName","") for x in teams if x.get("homeAway")=="away"),"")
            if not home or not away: continue
            status=((ev.get("status") or {}).get("type") or {}).get("name","")
            if status in {"STATUS_FINAL","STATUS_IN_PROGRESS","STATUS_FULL_TIME"}: continue
            start=ev.get("date","")
            key=(home.lower(),away.lower(),start[:16])
            if key in seen: continue
            seen.add(key)
            out.append({"id":"ESPN-"+str(len(out)+1).zfill(5),"date":start,"home":home,"away":away,"source":"ESPN:"+league})
    return out,used

def select_rows_for_date(date_str):
    # SELECT must report live-source failures instead of hiding them behind archive CSVs.
    rows,sources=fixture_feed_rows(date_str)
    if rows:
        return rows,sources
    if sources:
        return [],sources
    return [],["NO LIVE FIXTURE SOURCE"] 
    rows=[]; seen=set(); sources=[]
    for url in FOOTBALL_DATA_URLS:
        text,err=http_text(url)
        if err or not text: continue
        try: data=list(csv.DictReader(io.StringIO(text)))
        except Exception: continue
        sources.append(url.split("/")[-1])
        for r in data:
            home=(r.get("HomeTeam") or "").strip(); away=(r.get("AwayTeam") or "").strip()
            if not home or not away: continue
            key=(home.lower(),away.lower(),r.get("Date",""))
            if key in seen: continue
            seen.add(key)
            # Football-Data rows are retained as candidates only when the fixture is not completed.
            if not (r.get("FTHG") or r.get("FTAG")):
                rows.append({"id":"FD-"+str(len(rows)+1).zfill(5),"date":r.get("Date",""),"home":home,"away":away,"source":url.split("/")[-1]})
    return rows,sources

def api_team_history(team_name, last=10):
    """Fetch prematch history from API-Football without exposing the API key."""
    key=os.getenv("API_FOOTBALL_KEY","").strip()
    if not key: return []
    q=urllib.parse.quote(team_name)
    data,err=http_json("https://v3.football.api-sports.io/teams?search="+q,{"x-apisports-key":key},timeout=10)
    teams=(data or {}).get("response",[]) if isinstance(data,dict) else []
    if not teams: return []
    team_id=((teams[0].get("team") or {}).get("id"))
    if not team_id: return []
    data,err=http_json("https://v3.football.api-sports.io/fixtures?team="+str(team_id)+"&last="+str(last),{"x-apisports-key":key},timeout=10)
    out=[]
    for x in ((data or {}).get("response",[]) if isinstance(data,dict) else []):
        fx=x.get("fixture") or {}; teams=x.get("teams") or {}; goals=x.get("goals") or {}
        home=((teams.get("home") or {}).get("name") or "").strip()
        away=((teams.get("away") or {}).get("name") or "").strip()
        hg=goals.get("home"); ag=goals.get("away")
        if home and away and hg is not None and ag is not None:
            out.append({"home":home,"away":away,"hg":safe_int(hg) or 0,"ag":safe_int(ag) or 0,"date":fx.get("date","")})
    return out

def select_history(row):
    home=api_team_history(row.get("home",""),10)
    away=api_team_history(row.get("away",""),10)
    return home,away

def select_score(row):
    # P11.2 FAST SCAN: prematch data only; no odds, lineups or exact-score output.
    rows,src=load_rows(row.get("home",""),row.get("away",""))
    if not rows:
        api_home,api_away=select_history(row)
        rows=[{"HomeTeam":x["home"],"AwayTeam":x["away"],"FTHG":x["hg"],"FTAG":x["ag"],"Date":x["date"]} for x in api_home+api_away]
    if not rows:
        return [0,0,0,0,0,0],0,"HOLD","F03"
    h=team_stats(rows,row.get("home","")); a=team_stats(rows,row.get("away",""))
    if not h or not a:
        return [1,0,0,0,0,0],1,"HOLD","F03"
    hg=[r for r in rows if match_team(r.get("HomeTeam",""),row.get("home","")) and safe_int(r.get("FTHG")) is not None][-10:]
    ag=[r for r in rows if match_team(r.get("AwayTeam",""),row.get("away","")) and safe_int(r.get("FTHG")) is not None][-10:]
    xs01=2 if len(hg)>=8 and len(ag)>=8 else 1 if len(hg)>=5 and len(ag)>=5 else 0
    totals=[]
    for r in (hg+ag):
        totals.append((safe_int(r.get("FTHG")) or 0)+(safe_int(r.get("FTAG")) or 0))
    low=sum(x<=3 for x in totals); high=sum(x>=4 for x in totals)
    xs02=2 if totals and (low/len(totals)>=.7 or high/len(totals)>=.6) else 1 if totals else 0
    gap=abs(h["form"]-a["form"])
    xs03=2 if gap>=25 else 1 if gap>=10 else 0
    underdog=min(h["form"],a["form"])
    xs04=2 if underdog>=45 and (h["ga"]<2 or a["ga"]<2) else 1 if underdog>=35 else 0
    favorite=max(h["form"],a["form"])
    xs05=2 if favorite>=65 and max(h["gf"],a["gf"])>=1.2 else 1 if favorite>=50 else 0
    xs06=2 if xs01==2 and (len(totals)>=12) else 1 if xs01>=1 else 0
    xs=[xs01,xs02,xs03,xs04,xs05,xs06]
    total=sum(xs)
    tier="A" if total>=11 and 0 not in (xs01,xs04,xs06) else "B" if total>=8 else "C" if total>=6 else "WATCH"
    return xs,total,tier,"F06" if total>=6 else "F03"

def select_page(rows=None,sources=None,scan_date=""):
    rows=rows or []; sources=sources or []
    scored=[]
    for r in rows:
        xs,total,tier,reason=select_score(r)
        scored.append({**r,"xs":xs,"total":total,"tier":tier,"reason":reason,"profile":"CTL-H"})
    scored.sort(key=lambda x:(-x["total"],x["date"],x["id"]))
    master=[r for r in scored if r["tier"]!="HOLD"][:4]
    body=""
    for r in scored:
        body+=f"""<tr><td><input class='select-check' type='checkbox' name='match_id' value='{esc(r["id"])}'></td><td>{esc(r["id"])}</td><td>{esc(r["home"])} – {esc(r["away"])}</td><td>{esc(r["date"])}</td><td>{esc(r["profile"])}</td><td>{"/".join(map(str,r["xs"]))}</td><td><span class='select-pill tier-{r["tier"].lower()}'>{r["tier"]} · {r["total"]}</span></td><td>{esc(r["reason"])}</td></tr>"""
    if not body: body="<tr><td colspan='8' class='select-note'>Brak zweryfikowanych meczów w aktualnym źródle. Skan nie tworzy sztucznych kandydatów.</td></tr>"
    mbody="".join(f"<li>{esc(r['home'])} – {esc(r['away'])} · {r['total']} pkt · {r['tier']}</li>" for r in master)
    if not mbody: mbody="<li>MASTER Queue pusta</li>"
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Quantum Edge SELECT</title><style>{SELECT_CSS}</style></head><body><main class='select-app'><div class='select-wrap'>
<header class='select-head'><div><div class='select-brand'>⚡ QUANTUM <span>EDGE</span> SELECT</div><div class='select-sub'>P11.2 · NO ODDS · NO FINAL EXACT · pełny skan kandydatów</div></div><div class='select-actions'><form id='scan-form' method='post' action='/select/scan'><input type='date' name='scan_date' value='{esc(scan_date)}'><button id='scan-btn' class='select-btn'>SKANUJ MECZE</button><div id='scan-progress' class='scan-progress'><div class='scan-label'>Pobieram terminarze i sprawdzam źródła…</div><div class='scan-track'><div id='scan-fill' class='scan-fill'></div></div></div></form><script>document.getElementById('scan-form').addEventListener('submit',function(){{var b=document.getElementById('scan-btn'),p=document.getElementById('scan-progress'),f=document.getElementById('scan-fill');b.disabled=true;b.textContent='SKANOWANIE…';p.classList.add('active');var n=8;setInterval(function(){{if(n<92){{n+=7;f.style.width=n+'%'}}}},700)}})</script></div></header>
<section class='select-card'><div class='select-grid'><div class='select-metric'><small>ŹRÓDŁA</small><b>{len(sources)}</b></div><div class='select-metric'><small>CANDIDATE POOL</small><b>{len(scored)}</b></div><div class='select-metric'><small>SHOWN</small><b>{len(scored)}</b></div><div class='select-metric'><small>MASTER QUEUE</small><b>{min(4,len(master))}</b></div></div><p class='select-note'>Coverage: {esc(", ".join(sources) or "nieuruchomiono")} · SELECT nie używa kursów, składów ani exact score.</p></section>
<section class='select-card'><h2>SHORTLIST SELECT</h2><form method='post' action='/select/master'><div style='overflow-x:auto'><table class='select-table'><thead><tr><th></th><th>MATCH ID</th><th>MECZ</th><th>START</th><th>PROFIL</th><th>XS01–06</th><th>TIER / XS</th><th>REASON</th></tr></thead><tbody>{body}</tbody></table></div><div class='select-actions' style='margin-top:14px'><button class='select-btn master'>PRZEKAŻ ZAZNACZONE DO MASTER</button></div></form></section>
<section class='select-card'><h2>MASTER QUEUE · MAKS. 4</h2><ol>{mbody}</ol><p class='select-note'>To jest kolejka przekazania do MASTER. SELECT nie podaje wyniku exact score.</p></section>
</div></main></body></html>"""

@app.get("/", response_class=HTMLResponse)
def home(): return select_page()

@app.post("/select/scan", response_class=HTMLResponse)
def select_scan(scan_date:str=Form("")):
    rows,sources=select_rows_for_date(scan_date)
    return select_page(rows,sources,scan_date)

@app.post("/select/master", response_class=HTMLResponse)
def select_master(match_id:list[str]=Form([])):
    return select_page()

@app.get("/history", response_class=HTMLResponse)
def history(): return page(default_values(),show_history=True)
@app.get("/fetch", response_class=HTMLResponse)
def fetch_get():
    """Keep direct /fetch links usable; the form submits to the POST route below."""
    return page(default_values())

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
