
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
import sqlite3
import os
import urllib.parse, csv, io, difflib, uuid

from qe_pipeline import PipelineRepository, PipelineRunner
from qe_sources import (
    SOURCE_FAILED,
    SOURCE_INVALID,
    SOURCE_NOT_CONFIGURED,
    SOURCE_SUCCESS,
    HttpClient,
    collect_dap_for_fixture,
    scan_fixtures,
)

app = FastAPI(title="Quantum Edge v30")
DB_PATH = os.getenv("QE_DB_PATH", "quantum_edge.db")

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

SELECT_SCAN_CACHE = {}
SELECT_SCAN_CACHE_LIMIT = 12
SOURCE_HTTP_CLIENT = HttpClient(default_timeout=12, ttl_seconds=300)
try:
    WARSZAWA_TZ = ZoneInfo("Europe/Warsaw")
except Exception:
    WARSZAWA_TZ = None

def _to_warsaw_naive(dt):
    if dt is None:
        return None
    if dt.tzinfo and WARSZAWA_TZ:
        try:
            return dt.astimezone(WARSZAWA_TZ).replace(tzinfo=None)
        except Exception:
            pass
    return dt.replace(tzinfo=None)

def _remember_select_run(rows, sources, scan_date, scored, run_id=None):
    run_id = run_id or str(uuid.uuid4())
    SELECT_SCAN_CACHE[run_id] = {
        "rows": rows,
        "sources": sources,
        "scan_date": scan_date,
        "scored": scored,
        "created": datetime.now().timestamp()
    }
    if len(SELECT_SCAN_CACHE) > SELECT_SCAN_CACHE_LIMIT:
        for old in sorted(SELECT_SCAN_CACHE, key=lambda k: SELECT_SCAN_CACHE[k]["created"])[:len(SELECT_SCAN_CACHE)-SELECT_SCAN_CACHE_LIMIT]:
            SELECT_SCAN_CACHE.pop(old, None)
    return run_id

def _get_select_run(run_id):
    return SELECT_SCAN_CACHE.get(run_id or "")

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

def parse_datetime_any(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_warsaw_naive(value)
    raw = str(value).strip()
    if not raw:
        return None
    patterns = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%Y%m%d",
        "%Y/%m/%d",
    ]
    for p in patterns:
        try:
            dt = datetime.strptime(raw, p)
            return _to_warsaw_naive(dt)
        except Exception:
            pass
    try:
        if raw.endswith("Z"):
            dt = datetime.fromisoformat(raw[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(raw)
        return _to_warsaw_naive(dt)
    except Exception:
        return None

def normalize_query_date(value, default=None):
    default = default or datetime.now()
    dt = parse_datetime_any(value)
    return dt if dt else default

def date_query(value, default=None):
    return normalize_query_date(value, default).strftime("%Y-%m-%d")

def date_query_compact(value, default=None):
    return normalize_query_date(value, default).strftime("%Y%m%d")

def format_event_date(value):
    dt = parse_datetime_any(value)
    if not dt:
        return str(value or "")
    return dt.strftime("%d.%m.%Y")

def format_event_datetime(value):
    dt = parse_datetime_any(value)
    if not dt:
        return str(value or "")
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        return dt.strftime("%d.%m.%Y")
    return dt.strftime("%d.%m.%Y %H:%M")

def fixture_sort_key(value):
    dt = parse_datetime_any(value)
    return dt or datetime.max

def fixture_dedupe_key(home, away, dt_value):
    dt = parse_datetime_any(dt_value)
    ts = dt.strftime("%Y%m%d%H%M") if dt else str(dt_value or "")[:16]
    return (str(home or "").strip().lower(), str(away or "").strip().lower(), ts)

def http_text(url):
    text,error,_elapsed=SOURCE_HTTP_CLIENT.get_text(url,headers={"Accept":"*/*"},timeout=8,ttl=3600)
    return text,error
def http_json(url, headers=None, timeout=3):
    data,error,_elapsed=SOURCE_HTTP_CLIENT.get_json(url,headers=headers,timeout=timeout,ttl=300)
    return data,error

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
    return {"home_team":"","away_team":"","city":"","league":"Premier League","match_date":date_query(datetime.now()),"xg_home":0,"xg_away":0,"xga_home":0,"xga_away":0,"xg_source":"brak","form_home":0,"form_away":0,"tempo":0,"odds":0,"odds_1":0,"odds_x":0,"odds_2":0,"odds_source":"DISABLED_FOR_DECISION","shots_home":0,"shots_away":0,"sot_home":0,"sot_away":0,"corners_home":0,"corners_away":0,"cards_home":0,"cards_away":0,"home_home_matches":"","home_away_matches":"","away_home_matches":"","away_away_matches":"","message":"","sources":"","bookmaker":"Rynek"}

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
        if home and away:
            if has_home and has_away:
                return rows,url.split("/")[-1]
            continue
        if home and not away:
            if has_home:
                return rows,url.split("/")[-1]
            continue
        if away and not home:
            if has_away:
                return rows,url.split("/")[-1]
            continue
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
def fetch_odds(home_team,away_team,bookmaker):
    v=default_values(); home=normalize_team_name(home_team); away=normalize_team_name(away_team)
    v["home_team"]=home; v["away_team"]=away
    v["odds_source"]="DISABLED_FOR_DECISION"
    v["message"]="Brak zweryfikowanego źródła kursów — nie podstawiono wartości zastępczych."
    v["sources"]="Rynek: NOT_CONFIGURED"
    return v

def merge(base,upd,keys):
    r=dict(base)
    for k in keys:
        if k in upd: r[k]=upd[k]
    return r
ODDS_KEYS=["home_team","away_team","odds","odds_1","odds_x","odds_2","odds_source","message","sources"]
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


def run_legacy_engine_from_contract(contract, progress_callback):
    """Run the existing v30 calculation only from DAP's immutable facts."""
    progress_callback("ENGINE.LEGACY", 25, "RUNNING", "Wczytano zamrożony pakiet DAP")
    engine_input = ((contract.get("immutable_facts_package") or {}).get("engine_input") or {})
    values = default_values()
    for key, value in engine_input.items():
        if key in values:
            values[key] = value
    # External prices do not decide the exact-score output.  No fake fallback
    # odds are allowed into the engine input.
    values["odds"] = 0
    values["odds_1"] = values["odds_x"] = values["odds_2"] = 0
    result = model(values)
    result["bookmaker_odds"] = 0
    result["edge"] = 0
    result["rating"] = "LEGACY v30 · BRAK DANYCH RYNKOWYCH"
    progress_callback("ENGINE.LEGACY", 100, "COMPLETED", "Istniejący model v30 zakończony")
    return result


def collect_dap_for_app(fixture, progress_callback):
    return collect_dap_for_fixture(
        fixture,
        progress_callback,
        client=SOURCE_HTTP_CLIENT,
    )


PIPELINE_REPOSITORY = PipelineRepository(DB_PATH)
PIPELINE_RUNNER = PipelineRunner(
    PIPELINE_REPOSITORY,
    collect_dap_for_app,
    run_legacy_engine_from_contract,
)

LEAGUE_CODE_BY_LABEL = {
    "Premier League": "eng.1",
    "English Premier League": "eng.1",
    "Championship": "eng.2",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Eredivisie": "ned.1",
    "Primeira Liga": "por.1",
    "Ekstraklasa": "pol.1",
}


def resolve_fixture_for_analysis(home_team, away_team, match_date, league):
    """Create an auditable identity request; DAP performs live resolution."""
    scan_date = date_query(match_date, datetime.now())
    league_code = LEAGUE_CODE_BY_LABEL.get(league, "eng.1" if "premier" in str(league).lower() else None)
    # Browser-provided stats are never copied here. If the named match cannot
    # be confirmed by DAP adapters, the sparse identity remains incomplete and
    # the critical gate closes with FAIL/STOP.
    return {
        "home": normalize_team_name(home_team),
        "away": normalize_team_name(away_team),
        "kickoff": scan_date,
        "date": scan_date,
        "competition": league if league not in ("", "All Countries") else None,
        "phase": None,
        "league_code": league_code,
        "status": None,
        "venue_name": None,
        "neutral": None,
        "source": "FORM_IDENTITY_REQUEST",
        "_source_results": [],
    }

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

def dap_panel(run=None):
    if not run:
        return "<div class='card'><h2>DAP OUTPUT CONTRACT</h2><p class='muted'>DAP nie został uruchomiony. Silniki i zapis wyniku są niedostępne.</p></div>"
    contract = run.get("dap_contract") or {}
    status = contract.get("status_dap") or "—"
    handover = contract.get("handover_status") or "—"
    metrics = "DC {dc} · SC {sc} · DF {df} · DI {di} · FDC {fdc}".format(
        dc=contract.get("dc", "—"), sc=contract.get("sc", "—"),
        df=contract.get("df", "—"), di=contract.get("di", "—"),
        fdc=contract.get("fdc", "—"),
    )
    critical = [item for item in contract.get("dap_items") or [] if item.get("classification") == "CRITICAL"]
    critical_html = "".join(
        "<div class='mini'><b>{}</b> · {} · {}</div>".format(
            esc(item.get("id")),
            "OK" if item.get("available") else "BRAK",
            esc(item.get("conflict") or "NONE"),
        )
        for item in critical
    ) or "<div class='mini'>Brak zamkniętego zestawu krytycznego.</div>"
    sources = contract.get("source_register") or []
    source_html = " · ".join(
        "{}: {} ({})".format(
            esc(source.get("source") or "źródło"),
            esc(source.get("status") or "UNKNOWN"),
            esc(source.get("records", 0)),
        )
        for source in sources
    ) or "brak"
    return """<div class='card'><h2>DAP OUTPUT CONTRACT</h2>
    <p><b>RUN:</b> {run_id} · <b>STATE:</b> {state}</p>
    <p><b>DAP:</b> {status} · <b>HANDOVER:</b> {handover}</p>
    <p class='muted'>{metrics}</p>{critical}
    <p class='muted'><b>Źródła:</b> {sources}</p></div>""".format(
        run_id=esc(run.get("run_id") or "—"), state=esc(run.get("state") or "—"),
        status=esc(status), handover=esc(handover), metrics=esc(metrics),
        critical=critical_html, sources=source_html,
    )


def page(v=None,result=None,show_history=False,dap_report=None):
    v=v or default_values(); res=result
    if res:
        f=flow(v); c,val,ch=res["control"],res["value"],res["chaos"]
    else:
        f={"control":"—","chaos":"—","transition":"—","collapse":"—","draw":"—"}
        c=val=ch="—"
    q,qs=quality(v)
    rows=hist_rows()
    history_html="<div class='card'><h2>ANALYSIS HISTORY</h2><div class='hist'><div>DATE</div><div>MATCH</div><div>TIP</div><div>VALUE</div><div>EXACT</div><div>RESULT</div><div>CLV</div>"
    if rows:
        for r in rows:
            history_html+=f"<div>{esc(format_event_date(r[0]))}</div><div>{esc(r[1])} vs {esc(r[2])}</div><div>{esc(r[3])}</div><div>{esc(r[5]) if r[5] else 'N/D'}</div><div>{esc(r[6])}</div><div>N/D</div><div>N/D</div>"
    else:
        history_html += "<div class='muted'>Brak zapisanych analiz.</div>"
    history_html+="</div></div>"
    contract = (dap_report or {}).get("dap_contract") or {}
    frozen_fixture = ((contract.get("immutable_facts_package") or {}).get("fixture") or {})
    home=v["home_team"] or frozen_fixture.get("home") or "—"; away=v["away_team"] or frozen_fixture.get("away") or "—"
    display_date = frozen_fixture.get("kickoff") or v.get("match_date") or datetime.now()
    display_venue = frozen_fixture.get("venue_name") or "stadion niepotwierdzony"
    dap_status = contract.get("status_dap") or "NOT RUN"
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Quantum Edge v30</title>{CSS}</head><body><div class='shell'>
<aside class='left'><div class='logo'>⚡ QUANTUM<span>EDGE</span></div><div class='nav'><a href='/'>⌂ DASHBOARD</a><a href='/'>◉ LIVE</a><a href='/history'>↺ HISTORY</a><a href='/'>⌕ VALUE FINDER</a><a href='/'>🏆 LEAGUES</a><a href='/'>⚙ SETTINGS</a></div>
<div class='card search'><h2>MATCH SEARCH</h2><form action='/fetch' method='post'><label>TEAM HOME</label><input name='home_team' value='{esc(v["home_team"])}' placeholder='Search teams...'><label>TEAM AWAY</label><input name='away_team' value='{esc(v["away_team"])}'><label>DATA MECZU</label><input type='date' name='match_date' value='{esc(v.get("match_date") or date_query(datetime.now()))}'><label>ROZGRYWKI</label><select name='league'><option>Premier League</option><option>Championship</option><option>La Liga</option><option>Serie A</option><option>Bundesliga</option><option>Ligue 1</option><option>Ekstraklasa</option></select>{hidden(v)}<button class='btn blue' name='mode' value='stats'>⚡ PODGLĄD DANYCH</button><button class='btn green' name='mode' value='odds'>💰 STATUS KURSÓW</button><button class='btn purple' formaction='/analyze' name='mode' value='analyze'>🔥 URUCHOM DAP + ANALIZĘ</button></form></div>
<div class='card'><h2>QUICK STATS</h2><div class='quick'><div>{crest(home)}<br>{esc(home)}</div><div>{crest(away)}<br>{esc(away)}</div></div><div class='mini'>WIN % <b>{v["form_home"]}</b> - <b>{v["form_away"]}</b></div><div class='mini'>AVG xG <b>{v["xg_home"]}</b> - <b>{v["xg_away"]}</b></div><div class='mini'>Stan analizy: <b>{esc((dap_report or {}).get("state") or "NIE URUCHOMIONO")}</b></div></div><p class='muted'>Quantum Edge v30</p></aside>
<main class='center'><div class='top'><div class='status'>DAP STATUS: <b>{esc(dap_status)}</b></div><div>UTC <span class='b'>{datetime.utcnow().strftime("%H:%M:%S")}</span></div></div>
<div class='card match'><div>{crest(home, True)}</div><div><small class='b'>{esc(frozen_fixture.get("competition") or v.get("league") or "ROZGRYWKI NIEPOTWIERDZONE")}</small><h1>{esc(home)} vs {esc(away)}</h1><div class='muted'>📅 {esc(format_event_datetime(display_date))} | 🏟 {esc(display_venue)}</div></div><div>{crest(away, True)}</div></div>
{dap_panel(dap_report)}
<div class='card'><h2>FLOW ENGINE 2.0</h2><div class='flow'><div class='tile'><small>CONTROL FLOW</small><b class='g'>{f["control"]}</b></div><div class='tile'><small>CHAOS FLOW</small><b class='r'>{f["chaos"]}</b></div><div class='tile'><small>TRANSITION POWER</small><b class='p'>{f["transition"]}</b></div><div class='tile'><small>COLLAPSE RISK</small><b class='o'>{f["collapse"]}</b></div><div class='tile'><small>DRAW ACCEPTANCE</small><b class='b'>{f["draw"]}</b></div></div></div>
<div class='card'><h2>EXACT SCORE ENGINE 2.0</h2><div class='score'><div><small>CONTROL SCENARIO</small><b class='g'>{c}</b></div><div><small>VALUE SCENARIO</small><b class='o'>{val}</b></div><div><small>CHAOS SCENARIO</small><b class='r'>{ch}</b></div></div></div>
<div class='card'><h2>MARKET INTELLIGENCE</h2><div class='market'><div><small>FAIR ODDS</small><b class='g'>{res["fair"] if res else "—"}</b></div><div><small>BEST ODDS</small><b class='o'>N/D</b></div><div><small>VALUE EDGE</small><b class='g'>N/D</b></div><div><small>CLV</small><b>N/D</b></div><div><small>STEAM MOVE</small><b>N/D</b></div><div><small>TRAP ALERT</small><b>N/D</b></div></div></div>
<div class='card'><h2>STATYSTYKI POBRANE DO APLIKACJI</h2><div class='datagrid'><div><small>xG</small><b>{v["xg_home"]} - {v["xg_away"]}</b></div><div><small>xGA</small><b>{v["xga_home"]} - {v["xga_away"]}</b></div><div><small>FORMA</small><b>{v["form_home"]} - {v["form_away"]}</b></div><div><small>TEMPO</small><b>{v["tempo"]}/100</b></div><div><small>STRZAŁY</small><b>{v["shots_home"]} - {v["shots_away"]}</b></div><div><small>CELNE</small><b>{v["sot_home"]} - {v["sot_away"]}</b></div><div><small>ROŻNE</small><b>{v["corners_home"]} - {v["corners_away"]}</b></div><div><small>KARTKI</small><b>{v["cards_home"]} - {v["cards_away"]}</b></div></div></div><div class='insight'><div class='card'><h2>DATA COVERAGE</h2><p>Jakość wejścia modelu: {q} {qs}/100</p><p>Źródła: {esc(v["sources"])}</p><p>Komunikat: {esc(v["message"])}</p></div><div class='card'><h2>MOMENTUM (xG)</h2><p class='muted'>Brak zweryfikowanej serii czasowej — wykres nie jest generowany z wartości zastępczych.</p></div></div>{history_html}</main>
<aside class='right'><div class='card'><h2>TEAM PROFILES</h2><h3 class='b'>{esc(home.upper())}</h3><div class='mini'>Profil dostępny dopiero po ukończeniu DAP i silnika.</div><h3 class='r'>{esc(away.upper())}</h3><div class='mini'>Brak wartości zastępczych.</div></div>
<div class='card'><h2>xG / xGA (LAST 5)</h2><div class='mini'><b>{esc(home)}</b><br>xG {v["xg_home"]}<br>xGA {v["xga_home"]}</div><div class='mini'><b>{esc(away)}</b><br>xG {v["xg_away"]}<br>xGA {v["xga_away"]}</div></div>
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
.select-check{width:18px;height:18px;accent-color:#27c5ff}.select-note{color:#a9bed0;font-size:13px;line-height:1.5}.scan-progress{display:none;margin-top:12px}.scan-progress.active{display:block}.scan-track{height:10px;background:#071827;border-radius:999px;overflow:hidden}.scan-fill{height:100%;width:35%;background:linear-gradient(90deg,#27c5ff,#67f542);animation:source-wait 1.4s ease-in-out infinite alternate}.scan-label{color:#9eb4c9;font-size:13px;margin-bottom:6px}@keyframes source-wait{from{transform:translateX(-100%)}to{transform:translateX(280%)}}
@media(max-width:760px){.select-app{padding:10px}.select-head{display:block}.select-actions{margin-top:14px}.select-grid{grid-template-columns:repeat(2,1fr)}.select-table{display:block;overflow-x:auto;white-space:nowrap}.select-table th,.select-table td{padding:10px 7px}.select-brand{font-size:24px}}
"""


def fixture_feed_rows(date_str):
    # SELECT and DAP share the same normalized fixture adapters and statuses.
    return scan_fixtures(date_query(date_str, datetime.now()),client=SOURCE_HTTP_CLIENT)

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

def scan_match_rows(scan_date):
    center=normalize_query_date(scan_date, datetime.now())
    day=date_query(center, datetime.now())
    rows,sources=select_rows_for_date(day)
    return rows, sources, day

def select_ranked(rows):
    scored=[]
    for r in rows:
        xs,total,tier,reason=select_score(r)
        scored.append({**r,"xs":xs,"total":total,"tier":tier,"reason":reason,"profile":"CTL-H"})
    scored.sort(key=lambda x:(-x["total"],fixture_sort_key(x.get("date")),x["id"]))
    master=[r for r in scored if r["tier"] in ("A","B")][:4]
    return scored,master

def persist_selected_matches(rows):
    # Kept as one compatibility entry point, but it no longer persists
    # directly. Every selected match must complete the global runner.
    return [PIPELINE_RUNNER.run(dict(row)) for row in (rows or [])]


def pipeline_results_page(outcomes):
    items=[]
    for outcome in outcomes or []:
        contract=outcome.get("dap_contract") or {}
        items.append(
            "<li><b>{}</b> · DAP {} · {} · {}</li>".format(
                esc(outcome.get("run_id") or "—"),
                esc(contract.get("status_dap") or "—"),
                esc(contract.get("handover_status") or "—"),
                esc(outcome.get("state") or "—"),
            )
        )
    return """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Quantum Edge · DAP</title><style>{css}</style></head><body><main class='select-app'><div class='select-wrap'><section class='select-card'><h2>WYNIKI PRZEPŁYWU DAP</h2><ol>{items}</ol><p class='select-note'>Wynik analizy istnieje wyłącznie dla stanu COMPLETED. DAP_BLOCKED nie uruchamia silnika i niczego nie dopisuje do historii.</p><div class='select-actions'><a class='select-btn' href='/history'>HISTORIA</a><a class='select-btn secondary' href='/'>SELECT</a></div></section></div></main></body></html>""".format(css=SELECT_CSS,items="".join(items) or "<li>Brak uruchomień.</li>")

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

def thesportsdb_history(team_id, last=10):
    if not team_id: return []
    data,err=http_json("https://www.thesportsdb.com/api/v1/json/3/eventslast.php?id="+str(team_id),timeout=10)
    out=[]
    for x in ((data or {}).get("results") or [] if isinstance(data,dict) else []):
        hg=safe_int(x.get("intHomeScore")); ag=safe_int(x.get("intAwayScore"))
        if x.get("strHomeTeam") and x.get("strAwayTeam") and hg is not None and ag is not None:
            out.append({"home":x.get("strHomeTeam"),"away":x.get("strAwayTeam"),"hg":hg,"ag":ag,"date":x.get("dateEvent","")})
    return out[:last]

def select_history(row):
    home=api_team_history(row.get("home",""),10)
    away=api_team_history(row.get("away",""),10)
    if len(home)<5 and row.get("home_id"):
        home=thesportsdb_history(row.get("home_id"),10)
    if len(away)<5 and row.get("away_id"):
        away=thesportsdb_history(row.get("away_id"),10)
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

def select_page(rows=None,sources=None,scan_date="",run_id="",message="",scored=None):
    rows=rows or []; sources=sources or []
    scan_date = date_query(scan_date, datetime.now())
    normalized_sources=[]
    for source in sources:
        if isinstance(source, dict):
            normalized_sources.append(source)
        else:
            label=str(source)
            normalized_sources.append({
                "source":label.split(":")[0],
                "status":SOURCE_FAILED if "ERROR" in label else SOURCE_SUCCESS,
                "records":0,
                "error":label if "ERROR" in label else None,
            })
    provider_status={}
    for source in normalized_sources:
        provider=(source.get("source") or "UNKNOWN").split(":")[0]
        statuses=provider_status.setdefault(provider,[])
        statuses.append(source.get("status") or "UNKNOWN")
    working_sources=sorted(provider for provider,statuses in provider_status.items() if SOURCE_SUCCESS in statuses)
    failed_sources=[source for source in normalized_sources if source.get("status") in {SOURCE_FAILED,SOURCE_INVALID,SOURCE_NOT_CONFIGURED}]
    status_details=" · ".join(
        "{}: {} ({})".format(source.get("source"),source.get("status"),source.get("records",0))
        for source in normalized_sources
    )
    if isinstance(scored, tuple) and len(scored)==2:
        scored,master = scored
    elif scored is None:
        scored,master = select_ranked(rows)
    else:
        scored = scored
        master=[r for r in scored if r["tier"] in ("A","B")][:4]
    body=""
    for r in scored:
        body+=f"""<tr><td><input class='select-check' type='checkbox' name='match_id' value='{esc(r["id"])}'></td><td>{esc(r["id"])}</td><td>{esc(r["home"])} – {esc(r["away"])}</td><td>{esc(format_event_datetime(r["date"]))}</td><td>{esc(r["profile"])}</td><td>{"/".join(map(str,r["xs"]))}</td><td><span class='select-pill tier-{r["tier"].lower()}'>{r["tier"]} · {r["total"]}</span></td><td>{esc(r["reason"])}</td></tr>"""
    if not body: body="<tr><td colspan='8' class='select-note'>Brak zweryfikowanych meczów w aktualnym źródle. Skan nie tworzy sztucznych kandydatów.</td></tr>"
    mbody="".join(f"<li>{esc(r['home'])} – {esc(r['away'])} · {r['total']} pkt · {r['tier']}</li>" for r in master)
    if not mbody: mbody="<li>MASTER Queue pusta</li>"
    alert = f"<section class='select-card'><p class='select-note'>{esc(message)}</p></section>" if message else ""
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Quantum Edge SELECT</title><style>{SELECT_CSS}</style></head><body><main class='select-app'><div class='select-wrap'>
<header class='select-head'><div><div class='select-brand'>⚡ QUANTUM <span>EDGE</span> SELECT</div><div class='select-sub'>P11.2 · NO ODDS · NO FINAL EXACT · pełny skan kandydatów</div></div><div class='select-actions'><form id='scan-form' method='post' action='/select/scan'><input type='date' name='scan_date' value='{esc(scan_date)}'><button id='scan-btn' class='select-btn'>SKANUJ MECZE</button><div id='scan-progress' class='scan-progress'><div class='scan-label'>Żądanie źródłowe trwa; wynik pojawi się po odpowiedzi adapterów.</div><div class='scan-track'><div id='scan-fill' class='scan-fill'></div></div></div></form><script>document.getElementById('scan-form').addEventListener('submit',function(){{var b=document.getElementById('scan-btn'),p=document.getElementById('scan-progress');b.disabled=true;b.textContent='SKANOWANIE…';p.classList.add('active')}})</script></div></header>
{alert}
<section class='select-card'><div class='select-grid'><div class='select-metric'><small>DOSTAWCY</small><b>{len(provider_status)}</b></div><div class='select-metric'><small>CANDIDATE POOL</small><b>{len(scored)}</b></div><div class='select-metric'><small>SHOWN</small><b>{len(scored)}</b></div><div class='select-metric'><small>MASTER QUEUE</small><b>{min(4,len(master))}</b></div></div><p class='select-note'>Coverage: {esc(", ".join(working_sources) or "brak działającego źródła")} · Niedostępne/niepoprawne ścieżki: {len(failed_sources)} · SELECT nie używa kursów, składów ani exact score.</p><p class='select-note'>{esc(status_details or "Brak uruchomionych adapterów.")}</p></section>
<section class='select-card'><h2>SHORTLIST SELECT</h2><form method='post' action='/select/master'><input type='hidden' name='run_id' value='{esc(run_id)}'><div style='overflow-x:auto'><table class='select-table'><thead><tr><th></th><th>MATCH ID</th><th>MECZ</th><th>START</th><th>PROFIL</th><th>XS01–06</th><th>TIER / XS</th><th>REASON</th></tr></thead><tbody>{body}</tbody></table></div><div class='select-actions' style='margin-top:14px'><button class='select-btn master'>PRZEKAŻ ZAZNACZONE DO MASTER</button></div></form></section>
<section class='select-card'><h2>MASTER QUEUE · MAKS. 4</h2><ol>{mbody}</ol><p class='select-note'>To jest kolejka przekazania do MASTER. SELECT nie podaje wyniku exact score.</p></section>
</div></main></body></html>"""

@app.get("/", response_class=HTMLResponse)
def home():
    scan_date=date_query(datetime.now())
    run_id=_remember_select_run([],[],scan_date, ([],[]))
    return select_page([],[],scan_date,run_id=run_id,scored=([],[]),message="Wybierz datę i uruchom jawny skan. Otwarcie strony nie uruchamia źródeł, DAP ani silników.")

@app.post("/select/scan", response_class=HTMLResponse)
def select_scan(scan_date:str=Form("")):
    rows,sources,scan_date=scan_match_rows(scan_date)
    scored,master=select_ranked(rows)
    run_id=_remember_select_run(rows,sources,scan_date, (scored,master))
    message="Skan zakończony. Nie uruchomiono DAP, silników ani zapisu. Zaznacz mecze, które chcesz jawnie przekazać dalej."
    if not scored:
        message="Skan zakończony bez kandydatów. Nie uruchomiono DAP, silników ani zapisu."
    return select_page(rows,sources,scan_date,run_id=run_id,scored=(scored,master),message=message)

@app.post("/select/master", response_class=HTMLResponse)
def select_master(run_id:str=Form(""),match_id:list=Form([])):
    run=_get_select_run(run_id)
    if not run:
        scan_date=date_query(datetime.now())
        run_id=_remember_select_run([],[],scan_date,([],[]))
        return select_page([],[],scan_date,run_id=run_id,scored=([],[]),message="Sesja skanu wygasła. Uruchom skan ponownie; niczego nie przeanalizowano automatycznie.")
    scored,master=run.get("scored", ([],[]))
    by_id={r.get("id"):r for r in scored}
    chosen=[by_id.get(x) for x in match_id if by_id.get(x)]
    if not chosen:
        return select_page(run["rows"],run["sources"],run["scan_date"],run_id=run_id,scored=(scored,master),message="Nie zaznaczono meczu. MASTER nie wybiera już domyślnego kandydata i niczego nie uruchomił.")
    outcomes=persist_selected_matches(chosen[:4])
    return pipeline_results_page(outcomes)

@app.get("/history", response_class=HTMLResponse)
def history(): return page(default_values(),show_history=True)
@app.get("/fetch", response_class=HTMLResponse)
def fetch_get():
    """Keep direct /fetch links usable; the form submits to the POST route below."""
    return page(default_values())

@app.post("/fetch", response_class=HTMLResponse)
def fetch(home_team:str=Form(""),away_team:str=Form(""),city:str=Form(""),league:str=Form("Premier League"),match_date:str=Form(""),mode:str=Form("stats"),xg_home:float=Form(0),xg_away:float=Form(0),xga_home:float=Form(0),xga_away:float=Form(0),xg_source:str=Form(""),form_home:float=Form(0),form_away:float=Form(0),tempo:float=Form(0),odds:float=Form(0),odds_1:float=Form(0),odds_x:float=Form(0),odds_2:float=Form(0),shots_home:float=Form(0),shots_away:float=Form(0),sot_home:float=Form(0),sot_away:float=Form(0),corners_home:float=Form(0),corners_away:float=Form(0),cards_home:float=Form(0),cards_away:float=Form(0),odds_source:str=Form(""),home_home_matches:str=Form(""),home_away_matches:str=Form(""),away_home_matches:str=Form(""),away_away_matches:str=Form("")):
    v=default_values()
    v["home_team"]=normalize_team_name(home_team); v["away_team"]=normalize_team_name(away_team); v["city"]=city
    if mode=="odds":
        v=merge(v,fetch_odds(home_team,away_team,"Rynek"),ODDS_KEYS)
    else:
        v["message"]="Statystyki wejściowe są kompletowane wyłącznie przez audytowalny DAP. Ten podgląd nie uruchomił DAP ani modelu."
        v["sources"]="DAP: NOT RUN"
    v["match_date"]=date_query(match_date,datetime.now()); v["league"]=league
    return page(v)
@app.post("/analyze", response_class=HTMLResponse)
def analyze(home_team:str=Form(""),away_team:str=Form(""),city:str=Form(""),league:str=Form("Premier League"),match_date:str=Form(""),xg_home:float=Form(0),xg_away:float=Form(0),xga_home:float=Form(0),xga_away:float=Form(0),xg_source:str=Form(""),form_home:float=Form(0),form_away:float=Form(0),tempo:float=Form(0),odds:float=Form(0),odds_1:float=Form(0),odds_x:float=Form(0),odds_2:float=Form(0),shots_home:float=Form(0),shots_away:float=Form(0),sot_home:float=Form(0),sot_away:float=Form(0),corners_home:float=Form(0),corners_away:float=Form(0),cards_home:float=Form(0),cards_away:float=Form(0),odds_source:str=Form(""),home_home_matches:str=Form(""),home_away_matches:str=Form(""),away_home_matches:str=Form(""),away_away_matches:str=Form("")):
    fixture=resolve_fixture_for_analysis(home_team,away_team,match_date,league)
    run=PIPELINE_RUNNER.run(fixture)
    contract=run.get("dap_contract") or {}
    engine_input=((contract.get("immutable_facts_package") or {}).get("engine_input") or {})
    v=default_values()
    for key,value in engine_input.items():
        if key in v: v[key]=value
    v["home_team"]=fixture.get("home") or normalize_team_name(home_team)
    v["away_team"]=fixture.get("away") or normalize_team_name(away_team)
    v["match_date"]=date_query(fixture.get("kickoff") or match_date,datetime.now())
    v["league"]=fixture.get("competition") or league
    v["message"]="DAP zakończony: {}".format(contract.get("handover_status") or run.get("error") or run.get("state"))
    result=run.get("engine_result") if run.get("state")=="COMPLETED" else None
    return page(v,result,dap_report=run)


@app.get("/api/runs/{run_id}")
def analysis_run(run_id:str):
    run=PIPELINE_REPOSITORY.get_run(run_id)
    if not run:
        return JSONResponse({"error":"RUN_NOT_FOUND"},status_code=404)
    return JSONResponse(run)
