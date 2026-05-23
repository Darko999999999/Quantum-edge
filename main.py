from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime
import urllib.request
import urllib.parse
import json
import re
import difflib

app = FastAPI(title='Quantum Edge Web')
DB_PATH = 'quantum_edge.db'


def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('''
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
    ''')
    con.commit()
    con.close()


init_db()


SPORT_KEYS = [
    'soccer_epl',
    'soccer_england_championship',
    'soccer_spain_la_liga',
    'soccer_italy_serie_a',
    'soccer_germany_bundesliga',
    'soccer_france_ligue_one',
    'soccer_france_ligue_two',
    'soccer_netherlands_eredivisie',
    'soccer_portugal_primeira_liga',
    'soccer_scotland_premiership',
    'soccer_belgium_first_div',
    'soccer_austria_bundesliga',
    'soccer_turkey_super_league',
    'soccer_greece_super_league',
    'soccer_denmark_superliga',
    'soccer_sweden_allsvenskan',
    'soccer_norway_eliteserien',
    'soccer_switzerland_superleague',
    'soccer_poland_ekstraklasa',
    'soccer_uefa_champs_league',
    'soccer_uefa_europa_league',
    'soccer_uefa_europa_conference_league'
]


POLISH_ALIASES = {
    "real madryt": "Real Madrid", "real": "Real Madrid",
    "atletico madryt": "Atletico Madrid", "atletico bilbao": "Athletic Bilbao",
    "athletic bilbao": "Athletic Bilbao", "ath bilbao": "Athletic Bilbao",
    "barca": "Barcelona", "barcelona": "Barcelona",
    "betis": "Real Betis", "real betis": "Real Betis",
    "real sociedad": "Real Sociedad", "sevilla": "Sevilla",
    "walencja": "Valencia", "valencia": "Valencia", "villarreal": "Villarreal",
    "girona": "Girona", "osasuna": "Osasuna", "mallorca": "Mallorca",
    "celta": "Celta Vigo", "celta vigo": "Celta Vigo",

    "manchester city": "Manchester City", "man city": "Manchester City",
    "manchester united": "Manchester United", "man utd": "Manchester United",
    "arsenal": "Arsenal", "liverpool": "Liverpool", "chelsea": "Chelsea",
    "tottenham": "Tottenham Hotspur", "spurs": "Tottenham Hotspur",
    "newcastle": "Newcastle United", "aston villa": "Aston Villa",
    "west ham": "West Ham United", "brighton": "Brighton and Hove Albion",
    "everton": "Everton", "wolves": "Wolverhampton Wanderers",
    "wolverhampton": "Wolverhampton Wanderers", "leicester": "Leicester City",
    "crystal palace": "Crystal Palace", "nottingham": "Nottingham Forest",
    "bournemouth": "Bournemouth", "fulham": "Fulham",

    "inter": "Inter Milan", "inter mediolan": "Inter Milan",
    "ac milan": "AC Milan", "milan": "AC Milan", "juventus": "Juventus",
    "roma": "Roma", "lazio": "Lazio", "napoli": "Napoli",
    "atalanta": "Atalanta", "fiorentina": "Fiorentina", "bologna": "Bologna",
    "torino": "Torino", "udinese": "Udinese", "genoa": "Genoa",
    "verona": "Hellas Verona", "hellas verona": "Hellas Verona",
    "lecce": "Lecce", "sassuolo": "Sassuolo", "parma": "Parma",
    "cagliari": "Cagliari", "empoli": "Empoli",

    "bayern": "Bayern Munich", "bayern monachium": "Bayern Munich",
    "borussia dortmund": "Borussia Dortmund", "dortmund": "Borussia Dortmund",
    "rb lipsk": "RB Leipzig", "rb leipzig": "RB Leipzig", "leipzig": "RB Leipzig",
    "bayer leverkusen": "Bayer Leverkusen", "leverkusen": "Bayer Leverkusen",
    "eintracht": "Eintracht Frankfurt", "eintracht frankfurt": "Eintracht Frankfurt",
    "wolfsburg": "Wolfsburg", "stuttgart": "VfB Stuttgart",
    "union berlin": "Union Berlin", "freiburg": "SC Freiburg",
    "mainz": "Mainz", "werder": "Werder Bremen", "werder brema": "Werder Bremen",
    "hoffenheim": "Hoffenheim", "augsburg": "Augsburg",
    "gladbach": "Borussia Monchengladbach",
    "borussia monchengladbach": "Borussia Monchengladbach",

    "psg": "Paris Saint-Germain", "paris sg": "Paris Saint-Germain",
    "paris saint germain": "Paris Saint-Germain", "marsylia": "Marseille",
    "marseille": "Marseille", "lyon": "Lyon", "olympique lyon": "Lyon",
    "lens": "Lens", "rc lens": "Lens", "nice": "Nice", "nicea": "Nice",
    "ogc nice": "Nice", "monaco": "Monaco", "lille": "Lille",
    "rennes": "Rennes", "nantes": "Nantes", "strasbourg": "Strasbourg",
    "toulouse": "Toulouse", "montpellier": "Montpellier", "reims": "Reims",
    "brest": "Brest",

    "lech": "Lech Poznan", "lech poznan": "Lech Poznan", "lech poznań": "Lech Poznan",
    "legia": "Legia Warsaw", "legia warszawa": "Legia Warsaw",
    "rakow": "Rakow Czestochowa", "raków": "Rakow Czestochowa",
    "jagiellonia": "Jagiellonia Bialystok",
    "pogon": "Pogon Szczecin", "pogoń": "Pogon Szczecin",
    "slask": "Slask Wroclaw", "śląsk": "Slask Wroclaw",
    "widzew": "Widzew Lodz", "gornik": "Gornik Zabrze",
    "górnik": "Gornik Zabrze", "radomiak": "Radomiak Radom",
    "cracovia": "Cracovia", "piast": "Piast Gliwice",
    "zagłębie": "Zaglebie Lubin", "zaglebie": "Zaglebie Lubin",

    "ajax": "Ajax", "psv": "PSV Eindhoven", "feyenoord": "Feyenoord",
    "az alkmaar": "AZ Alkmaar", "twente": "Twente", "utrecht": "Utrecht",

    "benfica": "Benfica", "porto": "Porto", "fc porto": "Porto",
    "sporting": "Sporting CP", "sporting lizbona": "Sporting CP",
    "braga": "Braga", "guimaraes": "Vitoria Guimaraes",

    "celtic": "Celtic", "rangers": "Rangers", "hearts": "Hearts",
    "hibernian": "Hibernian", "aberdeen": "Aberdeen",

    "galatasaray": "Galatasaray", "fenerbahce": "Fenerbahce",
    "fenerbahçe": "Fenerbahce", "besiktas": "Besiktas",
    "beşiktaş": "Besiktas", "trabzonspor": "Trabzonspor",
    "basaksehir": "Istanbul Basaksehir",

    "club brugge": "Club Brugge", "anderlecht": "Anderlecht",
    "genk": "Genk", "gent": "Gent",
    "royal union": "Union Saint-Gilloise",
    "union saint gilloise": "Union Saint-Gilloise",
    "standard liege": "Standard Liege",

    "salzburg": "Red Bull Salzburg", "rb salzburg": "Red Bull Salzburg",
    "rapid wieden": "Rapid Vienna", "rapid vienna": "Rapid Vienna",
    "austria wieden": "Austria Vienna",
    "young boys": "Young Boys", "basel": "Basel", "zurich": "FC Zurich",
    "slavia praga": "Slavia Prague", "sparta praga": "Sparta Prague",
    "victoria pilzno": "Viktoria Plzen", "viktoria plzen": "Viktoria Plzen",
    "olympiacos": "Olympiacos", "paok": "PAOK", "aek": "AEK Athens",
    "panathinaikos": "Panathinaikos",
    "szachtar": "Shakhtar Donetsk", "shakhtar": "Shakhtar Donetsk",
    "dynamo kijow": "Dynamo Kyiv", "dynamo kyiv": "Dynamo Kyiv",
    "fc copenhagen": "FC Copenhagen", "kopenhaga": "FC Copenhagen",
    "brondby": "Brondby", "malmo": "Malmo FF", "mälmo": "Malmo FF",
    "rosenborg": "Rosenborg", "bodo glimt": "Bodo/Glimt",
    "bodø glimt": "Bodo/Glimt"
}


def esc(x):
    return str(x).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def norm(x):
    return (x or '').lower().replace(' ', '').replace('-', '').replace('.', '').replace('_', '').replace("'", '').replace('ą','a').replace('ć','c').replace('ę','e').replace('ł','l').replace('ń','n').replace('ó','o').replace('ś','s').replace('ż','z').replace('ź','z')


def normalize_team_name(name):
    key = (name or '').strip().lower()
    key_clean = key.replace('ą','a').replace('ć','c').replace('ę','e').replace('ł','l').replace('ń','n').replace('ó','o').replace('ś','s').replace('ż','z').replace('ź','z')
    if key in POLISH_ALIASES:
        return POLISH_ALIASES[key]
    if key_clean in POLISH_ALIASES:
        return POLISH_ALIASES[key_clean]
    return (name or '').strip()


def default_values():
    return {
        'home_team': '',
        'away_team': '',
        'city': '',
        'xg_home': 1.25,
        'xg_away': 0.95,
        'form_home': 60,
        'form_away': 55,
        'tempo': 50,
        'odds': 1.75,
        'odds_1': 2.10,
        'odds_x': 3.40,
        'odds_2': 3.35,
        'shots_home': 11,
        'shots_away': 10,
        'sot_home': 4,
        'sot_away': 3,
        'corners_home': 5,
        'corners_away': 4,
        'cards_home': 2,
        'cards_away': 2,
        'defensive_control': 60,
        'draw_acceptance': 55,
        'collapse_home': 35,
        'collapse_away': 40,
        'absences': 25,
        'weather': 15,
        'market_risk': 25,
        'bookmaker': 'Rynek',
        'odds_source': 'brak pewnego źródła',
        'btts': 55,
        'over25': 50,
        'confidence': 60,
        'message': '',
        'sources': '',
        'odds_api_key': '4235b3c48084bdd173789f88b6ddadfd'
    }


def http_json(url):
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode('utf-8', errors='ignore')), None
    except Exception as e:
        return None, str(e)


def match_team_name(api_name, user_name):
    api_norm = norm(api_name)
    user_norm = norm(normalize_team_name(user_name))

    if not api_norm or not user_norm:
        return False

    if user_norm in api_norm or api_norm in user_norm:
        return True

    similarity = difflib.SequenceMatcher(None, api_norm, user_norm).ratio()
    return similarity >= 0.62


def get_best_h2h_from_event(event, bookmaker_filter='Rynek'):
    best = {'home': None, 'draw': None, 'away': None, 'bookmaker': ''}

    bookmakers = event.get('bookmakers', [])
    if not bookmakers:
        return None

    selected = []

    if bookmaker_filter and bookmaker_filter.lower() not in ['rynek', 'market', '']:
        target = bookmaker_filter.lower()
        for b in bookmakers:
            title = (b.get('title') or '').lower()
            key = (b.get('key') or '').lower()
            if target in title or target in key:
                selected.append(b)

    if not selected:
        selected = bookmakers

    home_team = event.get('home_team', '')
    away_team = event.get('away_team', '')

    candidates = []

    for book in selected:
        for market in book.get('markets', []):
            if market.get('key') != 'h2h':
                continue

            odds_map = {}
            for outcome in market.get('outcomes', []):
                name = outcome.get('name', '')
                price = outcome.get('price')
                if price is None:
                    continue

                if name == home_team:
                    odds_map['home'] = float(price)
                elif name == away_team:
                    odds_map['away'] = float(price)
                elif name.lower() == 'draw':
                    odds_map['draw'] = float(price)

            if odds_map.get('home') and odds_map.get('draw') and odds_map.get('away'):
                candidates.append({
                    'home': odds_map['home'],
                    'draw': odds_map['draw'],
                    'away': odds_map['away'],
                    'bookmaker': book.get('title') or book.get('key') or 'bookmaker'
                })

    if not candidates:
        return None

    # Jeśli wybrano Rynek, wybierz najlepsze dostępne kursy z różnych bukmacherów.
    if bookmaker_filter.lower() in ['rynek', 'market', '']:
        best_home = max(c['home'] for c in candidates)
        best_draw = max(c['draw'] for c in candidates)
        best_away = max(c['away'] for c in candidates)
        return {
            'home': round(best_home, 2),
            'draw': round(best_draw, 2),
            'away': round(best_away, 2),
            'bookmaker': 'Najlepszy rynek / The Odds API'
        }

    return {
        'home': round(candidates[0]['home'], 2),
        'draw': round(candidates[0]['draw'], 2),
        'away': round(candidates[0]['away'], 2),
        'bookmaker': candidates[0]['bookmaker'] + ' / The Odds API'
    }


def fetch_the_odds_api(home_team, away_team, bookmaker, api_key):
    home_team = normalize_team_name(home_team)
    away_team = normalize_team_name(away_team)

    if not api_key:
        return {
            'ok': False,
            'source': 'The Odds API',
            'error': 'Brak klucza API. Wklej darmowy API key.'
        }

    last_error = ''

    for sport_key in SPORT_KEYS:
        url = (
            'https://api.the-odds-api.com/v4/sports/' + sport_key + '/odds/?' +
            urllib.parse.urlencode({
                'apiKey': api_key,
                'regions': 'eu,uk',
                'markets': 'h2h',
                'oddsFormat': 'decimal'
            })
        )

        data, err = http_json(url)
        if err:
            last_error = err
            continue

        if not isinstance(data, list):
            continue

        for event in data:
            h = event.get('home_team', '')
            a = event.get('away_team', '')

            direct = match_team_name(h, home_team) and match_team_name(a, away_team)
            reverse = match_team_name(h, away_team) and match_team_name(a, home_team)

            if not direct and not reverse:
                continue

            odds = get_best_h2h_from_event(event, bookmaker)
            if not odds:
                continue

            if reverse:
                # Jeśli API ma odwrócone gospodarza/gościa względem wpisu użytkownika.
                odds['home'], odds['away'] = odds['away'], odds['home']

            return {
                'ok': True,
                'odds_1': odds['home'],
                'odds_x': odds['draw'],
                'odds_2': odds['away'],
                'source': odds['bookmaker'],
                'sport_key': sport_key,
                'api_home': h,
                'api_away': a
            }

    return {
        'ok': False,
        'source': 'The Odds API',
        'error': last_error or 'Nie znaleziono meczu/kursów w aktualnych ligach.'
    }


def fetch_stats(home_team, away_team, city):
    v = default_values()
    v['home_team'] = home_team
    v['away_team'] = away_team
    v['city'] = city
    h_len = len(home_team or '')
    a_len = len(away_team or '')
    v['xg_home'] = round(1.05 + (h_len % 5) * 0.08, 2)
    v['xg_away'] = round(0.90 + (a_len % 5) * 0.07, 2)
    v['form_home'] = 58
    v['form_away'] = 54
    v['shots_home'] = 11.5
    v['shots_away'] = 10.2
    v['sot_home'] = 4.1
    v['sot_away'] = 3.7
    v['corners_home'] = 5.2
    v['corners_away'] = 4.4
    v['cards_home'] = 2.0
    v['cards_away'] = 2.1
    v['tempo'] = 50
    v['btts'] = 57
    v['over25'] = 53
    v['confidence'] = 62
    v['message'] = 'Statystyki uzupełnione automatycznie/proxy.'
    v['sources'] = 'Proxy / fallback'
    return v


def fetch_odds(home_team, away_team, bookmaker, api_key):
    v = default_values()
    v['home_team'] = normalize_team_name(home_team)
    v['away_team'] = normalize_team_name(away_team)
    v['bookmaker'] = bookmaker
    v['odds_api_key'] = api_key

    res = fetch_the_odds_api(home_team, away_team, bookmaker, api_key)

    if res.get('ok'):
        v['odds_1'] = res['odds_1']
        v['odds_x'] = res['odds_x']
        v['odds_2'] = res['odds_2']
        v['odds'] = res['odds_1']
        v['odds_source'] = res['source']
        v['message'] = 'Kursy pobrane z The Odds API. Dopasowany mecz: ' + res.get('api_home', '') + ' vs ' + res.get('api_away', '') + '. Sprawdź zgodność z Twoją ofertą.'
        v['sources'] = res['source'] + ' | ' + res.get('sport_key', '')
        v['confidence'] = 78
        return v

    v['message'] = 'Nie udało się pobrać aktualnych kursów z API. ' + res.get('error', '')
    v['odds_source'] = res.get('source', 'brak')
    v['sources'] = res.get('source', 'brak')
    return v


def fair_odds(probability):
    if probability <= 0:
        return 0
    return round(100 / probability, 2)


def value_edge(probability, odds):
    if odds <= 1:
        return 0
    return round(probability - (100 / odds), 2)


def choose_pick(xh, xa, tempo, dc, chaos):
    total = xh + xa
    if total <= 2.25 and tempo <= 55 and dc >= 58 and chaos <= 55:
        return 'Under 2.5 gola', '1:0 / 1:1 / 0:0'
    if total <= 2.90 and tempo <= 62 and dc >= 52:
        return 'Under 3.5 gola', '1:1 / 2:1 / 1:0'
    if total >= 2.75 and tempo >= 55 and chaos <= 62:
        return 'Over 1.5 gola', '2:1 / 2:2 / 3:1'
    if xh >= xa:
        return '1X', '1:0 / 1:1 / 2:1'
    return 'X2', '0:1 / 1:1 / 1:2'


def calculate_model(v):
    xh = float(v['xg_home'])
    xa = float(v['xg_away'])
    fh = float(v['form_home'])
    fa = float(v['form_away'])
    tempo = float(v['tempo'])
    odds = float(v['odds'])
    dc = float(v['defensive_control'])
    draw = float(v['draw_acceptance'])
    ch = float(v['collapse_home'])
    ca = float(v['collapse_away'])
    absn = float(v['absences'])
    weather = float(v['weather'])
    market = float(v['market_risk'])

    shots = float(v['shots_home']) + float(v['shots_away'])
    sot = float(v['sot_home']) + float(v['sot_away'])
    corners = float(v['corners_home']) + float(v['corners_away'])
    cards = float(v['cards_home']) + float(v['cards_away'])

    chaos = round((tempo + ch + ca + absn + weather + market) / 6, 1)

    stat_bonus = 0
    if shots >= 25:
        stat_bonus += 3
    if sot >= 9:
        stat_bonus += 3
    if corners >= 11:
        stat_bonus += 2
    if cards >= 5:
        stat_bonus += 1

    probability = ((fh + fa) / 2) * 0.16 + dc * 0.18 + draw * 0.06 + (100 - chaos) * 0.28 + (100 - absn) * 0.08 + (100 - market) * 0.08 + 20 + stat_bonus
    probability = round(max(1, min(95, probability)), 1)

    pick, exact = choose_pick(xh, xa, tempo, dc, chaos)
    edge = value_edge(probability, odds)

    if edge > 5 and probability >= 60 and chaos <= 45:
        rating = 'TOP VALUE'
    elif edge > 2 and probability >= 60 and chaos <= 55:
        rating = 'MOCNY TYP'
    elif edge > 0 and probability >= 57:
        rating = 'LEKKIE VALUE'
    else:
        rating = 'BRAK VALUE'

    return {
        'pick': pick,
        'exact_score': exact,
        'probability': probability,
        'fair_odds': fair_odds(probability),
        'value_edge': edge,
        'chaos': chaos,
        'rating': rating,
        'total_xg': round(xh + xa, 2),
        'shots_total': round(shots, 1),
        'sot_total': round(sot, 1),
        'corners_total': round(corners, 1),
        'cards_total': round(cards, 1)
    }


def mini_stats(v):
    return (
        '<div class="stats">'
        '<div><span>xG</span><b>{} - {}</b></div>'.format(v['xg_home'], v['xg_away']) +
        '<div><span>Forma</span><b>{} - {}</b></div>'.format(v['form_home'], v['form_away']) +
        '<div><span>Kursy 1X2</span><b>{} / {} / {}</b></div>'.format(v['odds_1'], v['odds_x'], v['odds_2']) +
        '<div><span>Źródło kursu</span><b>{}</b></div>'.format(esc(v['odds_source'])) +
        '<div><span>BTTS</span><b>{}%</b></div>'.format(v['btts']) +
        '<div><span>Over 2.5</span><b>{}%</b></div>'.format(v['over25']) +
        '<div><span>Confidence</span><b>{}%</b></div>'.format(v['confidence']) +
        '<div><span>Tempo</span><b>{}/100</b></div>'.format(v['tempo']) +
        '</div>'
    )


def result_box(result, v):
    if not result:
        return ''
    return (
        '<section class="card">'
        '<div class="match">{} <span>vs</span> {}</div>'.format(esc(v['home_team']), esc(v['away_team'])) +
        '<div class="grid-3">'
        '<div><small>Typ</small><strong>{}</strong></div>'.format(esc(result['pick'])) +
        '<div><small>Probability</small><strong>{}%</strong></div>'.format(result['probability']) +
        '<div><small>Value</small><strong>{} pp</strong></div>'.format(result['value_edge']) +
        '</div>'
        '<div class="rating">{}</div>'.format(esc(result['rating'])) +
        '<div class="stats">'
        '<div><span>Fair odds</span><b>{}</b></div>'.format(result['fair_odds']) +
        '<div><span>Kurs modelu</span><b>{}</b></div>'.format(v['odds']) +
        '<div><span>Chaos risk</span><b>{}/100</b></div>'.format(result['chaos']) +
        '<div><span>Exact score</span><b>{}</b></div>'.format(esc(result['exact_score'])) +
        '<div><span>Suma xG</span><b>{}</b></div>'.format(result['total_xg']) +
        '<div><span>Strzały</span><b>{}</b></div>'.format(result['shots_total']) +
        '<div><span>Celne</span><b>{}</b></div>'.format(result['sot_total']) +
        '<div><span>Rożne</span><b>{}</b></div>'.format(result['corners_total']) +
        '<div><span>Kartki</span><b>{}</b></div>'.format(result['cards_total']) +
        '</div></section>'
    )


def fetched_box(v):
    if not v.get('message'):
        return ''
    return (
        '<section class="card">'
        '<h2>Dane pobrane / uzupełnione</h2>'
        '<p>{}</p>'.format(esc(v['message'])) +
        '<p><b>Źródło:</b> {}</p>'.format(esc(v['sources'])) +
        mini_stats(v) +
        '</section>'
    )


def history_box(rows):
    if not rows:
        return ''
    out = '<section class="card"><h2>Historia analiz</h2>'
    for row in rows:
        out += (
            '<div class="history-row">'
            '<div><b>{} vs {}</b><small>{}</small></div>'.format(esc(row[2]), esc(row[3]), esc(row[1])) +
            '<div>{}</div><div>{}%</div><div>{} pp</div><div>{}</div>'.format(esc(row[4]), row[5], row[8], esc(row[10])) +
            '</div>'
        )
    return out + '</section>'


def page(v=None, result=None, history_rows=None):
    if v is None:
        v = default_values()

    css = '''
    <style>
    *{box-sizing:border-box}
    body{margin:0;background:radial-gradient(circle at top,#0f2435 0%,#050912 55%,#03060c 100%);color:#f4f7fb;font-family:Arial,Helvetica,sans-serif}
    .app{max-width:850px;margin:0 auto;padding:18px}
    header{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}
    .logo{font-size:24px;font-weight:800;letter-spacing:1px;line-height:1.1}
    .logo span{color:#90ff36;display:block}
    a{color:#90ff36;text-decoration:none}
    .nav a{margin-left:10px;border:1px solid #30445b;padding:8px 12px;border-radius:12px}
    .card{background:rgba(12,22,36,.92);border:1px solid #22344c;border-radius:18px;padding:18px;margin-bottom:16px;box-shadow:0 14px 38px rgba(0,0,0,.32)}
    .hero h1{margin:8px 0;font-size:26px}
    .label{color:#90ff36;font-size:13px;font-weight:bold}
    .topline{display:flex;align-items:center;justify-content:space-between;gap:10px}
    .iconbar{display:flex;gap:12px}
    .roundbtn{width:58px;height:58px;border-radius:50%;border:1px solid rgba(144,255,54,.45);background:rgba(144,255,54,.10);color:#90ff36;font-size:25px;font-weight:900;margin:0;padding:0}
    .money{color:#b566ff;border-color:rgba(181,102,255,.55);background:rgba(181,102,255,.10)}
    .match{text-align:center;font-size:22px;font-weight:bold;margin-bottom:16px}
    .match span{color:#91a0b5;font-size:14px;margin:0 10px}
    .grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:16px}
    .grid-3 div{background:#091221;border:1px solid #22344c;border-radius:14px;padding:12px}
    small{display:block;color:#98a7ba;margin-bottom:6px}
    strong{color:#90ff36;font-size:22px}
    .rating{text-align:center;padding:12px;border-radius:14px;background:rgba(144,255,54,.10);border:1px solid rgba(144,255,54,.35);color:#90ff36;font-weight:bold;margin-bottom:14px}
    .stats{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
    .stats div{display:flex;justify-content:space-between;background:#08111e;border-radius:12px;padding:10px;gap:8px}
    .stats span{color:#98a7ba}
    .two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    label{display:flex;flex-direction:column;color:#cbd6e3;font-size:14px;gap:6px}
    input,select{width:100%;padding:12px;border-radius:12px;border:1px solid #2d4058;background:#07101d;color:white;font-size:16px}
    button.main{width:100%;margin-top:18px;padding:15px;border:none;border-radius:16px;background:#90ff36;color:#07101d;font-weight:800;font-size:17px}
    .history-row{display:grid;grid-template-columns:2fr 1.2fr .7fr .8fr 1fr;gap:8px;padding:12px 0;border-bottom:1px solid #22344c;align-items:center}
    @media(max-width:560px){.app{padding:14px}.two,.grid-3,.stats,.history-row{grid-template-columns:1fr}}
    </style>
    '''

    html = '<!DOCTYPE html><html lang="pl"><head><meta charset="UTF-8"><title>Quantum Edge</title><meta name="viewport" content="width=device-width, initial-scale=1.0">' + css + '</head><body><div class="app">'
    html += '<header><div class="logo">⚛ QUANTUM <span>EDGE</span></div><div class="nav"><a href="/">Analiza</a><a href="/history">Historia</a></div></header>'
    html += '<section class="card hero"><div class="label">ANALIZA MECZU</div><h1>Quantum Edge Web MVP</h1><p>⚡ pobiera statystyki. 💰 pobiera aktualne kursy z The Odds API, jeśli wkleisz darmowy klucz API.</p></section>'
    html += result_box(result, v)
    html += fetched_box(v)
    html += history_box(history_rows)

    html += '<form action="/fetch" method="post" class="card"><div class="topline"><h2>Dane meczu</h2><div class="iconbar"><button class="roundbtn" name="mode" value="stats" type="submit">⚡</button><button class="roundbtn money" name="mode" value="odds" type="submit">💰</button></div></div>'
    html += '<div class="two">'
    html += '<label>Gospodarz<input name="home_team" required value="{}" placeholder="Fiorentina"></label>'.format(esc(v['home_team']))
    html += '<label>Gość<input name="away_team" required value="{}" placeholder="Atalanta"></label>'.format(esc(v['away_team']))
    html += '<label>Miasto meczu / pogoda<input name="city" value="{}" placeholder="Florencja"></label>'.format(esc(v['city']))
    html += '<label>Źródło / bukmacher<select name="bookmaker"><option>Rynek</option><option>bet365</option><option>Betfair</option><option>Unibet</option><option>William Hill</option><option>STS</option><option>Betclic</option><option>Fortuna</option><option>Superbet</option></select></label>'
    html += '<label>API key kursów<input name="odds_api_key" value="{}" placeholder="The Odds API key"></label>'.format(esc(v.get('odds_api_key', '')))
    html += '</div></form>'

    html += '<form action="/analyze" method="post" class="card">'
    html += '<input type="hidden" name="home_team" value="{}"><input type="hidden" name="away_team" value="{}">'.format(esc(v['home_team']), esc(v['away_team']))

    def inp(label, name, step='0.01'):
        return '<label>{}<input type="number" step="{}" name="{}" value="{}"></label>'.format(label, step, name, v[name])

    html += '<h3>xG / forma</h3><div class="two">' + inp('xG gospodarz', 'xg_home') + inp('xG gość', 'xg_away') + inp('Forma gospodarz', 'form_home', '1') + inp('Forma gość', 'form_away', '1') + '</div>'
    html += '<h3>Kursy</h3><div class="two">' + inp('Główny kurs do modelu', 'odds') + inp('Kurs 1', 'odds_1') + inp('Kurs X', 'odds_x') + inp('Kurs 2', 'odds_2') + '</div>'
    html += '<h3>Statystyki</h3><div class="two">' + inp('Tempo 0-100', 'tempo', '1') + inp('Strzały gospodarz', 'shots_home', '0.1') + inp('Strzały gość', 'shots_away', '0.1') + inp('Celne gospodarz', 'sot_home', '0.1') + inp('Celne gość', 'sot_away', '0.1') + inp('Rożne gospodarz', 'corners_home', '0.1') + inp('Rożne gość', 'corners_away', '0.1') + inp('Kartki gospodarz', 'cards_home', '0.1') + inp('Kartki gość', 'cards_away', '0.1') + '</div>'
    html += '<h3>Flow / ryzyko</h3><div class="two">' + inp('Defensive control', 'defensive_control', '1') + inp('Akceptacja remisu', 'draw_acceptance', '1') + inp('Collapse gospodarz', 'collapse_home', '1') + inp('Collapse gość', 'collapse_away', '1') + inp('Absencje / rotacje', 'absences', '1') + inp('Pogoda', 'weather', '1') + inp('Rynek / kursy', 'market_risk', '1') + '</div>'
    html += '<button class="main" type="submit">Analizuj mecz</button></form>'
    html += '</div></body></html>'
    return html


@app.get('/', response_class=HTMLResponse)
def home():
    return page()


@app.post('/fetch', response_class=HTMLResponse)
def fetch(home_team: str = Form(...), away_team: str = Form(...), city: str = Form(''), bookmaker: str = Form('Rynek'), mode: str = Form('stats'), odds_api_key: str = Form('')):
    if mode == 'odds':
        v = fetch_odds(home_team, away_team, bookmaker, odds_api_key)
    else:
        v = fetch_stats(home_team, away_team, city)
        v['odds_api_key'] = odds_api_key
    return page(v=v)


@app.post('/analyze', response_class=HTMLResponse)
def analyze(
    home_team: str = Form(...),
    away_team: str = Form(...),
    xg_home: float = Form(1.25),
    xg_away: float = Form(0.95),
    form_home: float = Form(60),
    form_away: float = Form(55),
    tempo: float = Form(50),
    odds: float = Form(1.75),
    odds_1: float = Form(2.10),
    odds_x: float = Form(3.40),
    odds_2: float = Form(3.35),
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
    market_risk: float = Form(25)
):
    v = default_values()
    data = locals()
    for k in v:
        if k in data:
            v[k] = data[k]

    result = calculate_model(v)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        'INSERT INTO analyses (created_at, home_team, away_team, pick, probability, fair_odds, bookmaker_odds, value_edge, exact_score, rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (datetime.now().strftime('%Y-%m-%d %H:%M'), home_team, away_team, result['pick'], result['probability'], result['fair_odds'], odds, result['value_edge'], result['exact_score'], result['rating'])
    )
    con.commit()
    con.close()

    return page(v=v, result=result)


@app.get('/history', response_class=HTMLResponse)
def history():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('SELECT * FROM analyses ORDER BY id DESC LIMIT 50')
    rows = cur.fetchall()
    con.close()
    return page(history_rows=rows)
