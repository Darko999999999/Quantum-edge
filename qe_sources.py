"""Source adapters and DAP collection for Quantum Edge.

Every adapter returns an explicit status.  Data is never silently replaced by
zeros and provider fields needed by DAP are preserved through normalization.
"""

from __future__ import print_function

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
import csv
import difflib
import gzip
import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from qe_pipeline import build_dap_output_contract, make_dap_item, stable_match_id, utc_now_iso


SOURCE_SUCCESS = "SUCCESS"
SOURCE_EMPTY = "EMPTY"
SOURCE_FAILED = "FAILED"
SOURCE_NOT_CONFIGURED = "NOT_CONFIGURED"
SOURCE_INVALID = "INVALID"


LEAGUE_NAMES = {
    "eng.1": "English Premier League",
    "eng.2": "English Championship",
    "esp.1": "Spanish LaLiga",
    "ita.1": "Italian Serie A",
    "ger.1": "German Bundesliga",
    "fra.1": "French Ligue 1",
    "ned.1": "Dutch Eredivisie",
    "por.1": "Portuguese Primeira Liga",
    "bel.1": "Belgian Pro League",
    "sco.1": "Scottish Premiership",
    "pol.1": "Polish Ekstraklasa",
    "bra.1": "Brazilian Serie A",
    "arg.1": "Argentine Liga Profesional",
    "mex.1": "Liga MX",
    "usa.1": "MLS",
    "uefa.champions": "UEFA Champions League",
    "uefa.europa": "UEFA Europa League",
    "conmebol.libertadores": "CONMEBOL Libertadores",
    "conmebol.sudamericana": "CONMEBOL Sudamericana",
}

DEFAULT_LEAGUES = list(LEAGUE_NAMES)

FOOTBALL_DATA_CODES = {
    "eng.1": "E0",
    "eng.2": "E1",
    "esp.1": "SP1",
    "ita.1": "I1",
    "ger.1": "D1",
    "fra.1": "F1",
    "ned.1": "N1",
    "por.1": "P1",
    "sco.1": "SC0",
    "bel.1": "B1",
}

UNDERSTAT_CODES = {
    "eng.1": "EPL",
    "esp.1": "La_liga",
    "ita.1": "Serie_A",
    "ger.1": "Bundesliga",
    "fra.1": "Ligue_1",
}

SOURCE_PRIORITY = {"A": 3, "B": 2, "C": 1, "D": 0}


def _safe_url(url):
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = []
    for key, value in query:
        if key.lower() in {"api_token", "token", "key", "api_key"}:
            value = "REDACTED"
        redacted.append((key, value))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted), parsed.fragment)
    )


def source_result(name, status, records=0, elapsed_ms=0, error=None, source_class="B", scope="", url=None):
    return {
        "source": name,
        "status": status,
        "records": int(records or 0),
        "elapsed_ms": int(elapsed_ms or 0),
        "error": str(error) if error else None,
        "class": source_class,
        "scope": scope,
        "url": _safe_url(url) if url else None,
        "checked_at": utc_now_iso(),
    }


class HttpClient(object):
    def __init__(self, default_timeout=12, ttl_seconds=300, max_cache_entries=512):
        self.default_timeout = default_timeout
        self.ttl_seconds = ttl_seconds
        self.max_cache_entries = max(1, int(max_cache_entries))
        self._cache = {}
        self._lock = threading.Lock()

    def _read(self, url, headers=None, timeout=None, ttl=None):
        timeout = timeout or self.default_timeout
        ttl = self.ttl_seconds if ttl is None else ttl
        cache_key = (url, tuple(sorted((headers or {}).items())))
        now = time.time()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and now - cached[0] <= ttl:
                return cached[1], None, 0
        started = time.monotonic()
        try:
            request_headers = {
                "User-Agent": "Mozilla/5.0 (Quantum Edge DAP)",
                "Accept": "*/*",
            }
            request_headers.update(headers or {})
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                if str(response.headers.get("Content-Encoding") or "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                with self._lock:
                    expired = [
                        key for key, item in self._cache.items()
                        if now - item[0] > self.ttl_seconds
                    ]
                    for key in expired:
                        self._cache.pop(key, None)
                    while len(self._cache) >= self.max_cache_entries:
                        oldest = min(self._cache, key=lambda key: self._cache[key][0])
                        self._cache.pop(oldest, None)
                    self._cache[cache_key] = (now, raw)
                return raw, None, int((time.monotonic() - started) * 1000)
        except urllib.error.HTTPError as exc:
            return None, "HTTP %s" % exc.code, int((time.monotonic() - started) * 1000)
        except Exception as exc:
            return None, str(exc), int((time.monotonic() - started) * 1000)

    def get_json(self, url, headers=None, timeout=None, ttl=None):
        raw, error, elapsed = self._read(url, headers=headers, timeout=timeout, ttl=ttl)
        if error:
            return None, error, elapsed
        try:
            return json.loads(raw.decode("utf-8", errors="strict")), None, elapsed
        except Exception as exc:
            return None, "INVALID JSON: %s" % exc, elapsed

    def get_text(self, url, headers=None, timeout=None, ttl=None):
        raw, error, elapsed = self._read(url, headers=headers, timeout=timeout, ttl=ttl)
        if error:
            return "", error, elapsed
        return raw.decode("utf-8", errors="replace"), None, elapsed


def normalize_team(value):
    value = str(value or "").lower()
    replacements = {
        "nott'm": "nottingham",
        "man utd": "manchester united",
        "spurs": "tottenham hotspur",
        "psg": "paris saint germain",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return "".join(ch for ch in value if ch.isalnum())


def teams_match(left, right):
    left, right = normalize_team(left), normalize_team(right)
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return True
    return difflib.SequenceMatcher(None, left, right).ratio() >= 0.78


def parse_iso(value):
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except Exception:
            dt = None
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    dt = datetime.strptime(raw, pattern)
                    break
                except Exception:
                    pass
            if dt is None:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_utc(value):
    dt = parse_iso(value)
    return dt.isoformat().replace("+00:00", "Z") if dt else ""


def date_string(value):
    dt = parse_iso(value)
    return dt.strftime("%Y-%m-%d") if dt else str(value or "")[:10]


def _season_start_year(value):
    dt = parse_iso(value) or datetime.now(timezone.utc)
    return dt.year if dt.month >= 6 else dt.year - 1


def _season_label(value):
    year = _season_start_year(value)
    return "%d-%d" % (year, year + 1)


def _football_data_season(value):
    year = _season_start_year(value)
    return "%02d%02d" % (year % 100, (year + 1) % 100)


def _fixture_key(record):
    kickoff = parse_iso(record.get("kickoff") or record.get("date"))
    stamp = kickoff.strftime("%Y%m%d%H%M") if kickoff else date_string(record.get("date"))
    return (normalize_team(record.get("home")), normalize_team(record.get("away")), stamp)


def _provider_meta(name, source_class, url):
    return {"source": name, "class": source_class, "url": _safe_url(url)}


def _add_record_evidence(record, provider, source_class, url):
    meta = _provider_meta(provider, source_class, url)
    record["_provider"] = meta
    evidence = record.setdefault("_field_evidence", {})
    for field in (
        "home",
        "away",
        "kickoff",
        "competition",
        "phase",
        "round",
        "status",
        "venue_name",
        "venue_city",
        "venue_country",
        "neutral",
    ):
        value = record.get(field)
        if value is not None and value != "":
            evidence.setdefault(field, []).append(
                {"source": provider, "class": source_class, "url": _safe_url(url), "value": value}
            )
    return record


def espn_fixtures(date_value, league_codes=None, client=None):
    client = client or HttpClient()
    league_codes = list(league_codes or DEFAULT_LEAGUES)
    compact = date_string(date_value).replace("-", "")

    def fetch_one(code):
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/%s/scoreboard?dates=%s" % (code, compact)
        data, error, elapsed = client.get_json(url, headers={"Accept": "application/json"}, timeout=12, ttl=180)
        if error:
            return [], source_result("ESPN:%s" % code, SOURCE_FAILED, elapsed_ms=elapsed, error=error, scope="fixtures", url=url)
        if not isinstance(data, dict):
            return [], source_result("ESPN:%s" % code, SOURCE_INVALID, elapsed_ms=elapsed, error="non-object payload", scope="fixtures", url=url)
        records = []
        for event in data.get("events") or []:
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors") or []
            home = next(
                ((item.get("team") or {}).get("displayName") for item in competitors if item.get("homeAway") == "home"),
                "",
            )
            away = next(
                ((item.get("team") or {}).get("displayName") for item in competitors if item.get("homeAway") == "away"),
                "",
            )
            if not home or not away:
                continue
            status_type = ((event.get("status") or {}).get("type") or {})
            status = status_type.get("name") or status_type.get("description") or ""
            if status in {"STATUS_FINAL", "STATUS_IN_PROGRESS", "STATUS_FULL_TIME"}:
                continue
            venue = competition.get("venue") or event.get("venue") or {}
            address = venue.get("address") or {}
            season = event.get("season") or {}
            phase = "Regular season" if code in LEAGUE_NAMES and "." in code and not code.startswith(("uefa", "conmebol")) else "Tournament phase"
            record = {
                "provider_id": "ESPN:%s" % event.get("id"),
                "home": home,
                "away": away,
                "kickoff": iso_utc(event.get("date")),
                "date": iso_utc(event.get("date")),
                "competition": LEAGUE_NAMES.get(code) or season.get("slug") or code,
                "phase": phase,
                "round": None,
                "status": status,
                "venue_name": venue.get("fullName"),
                "venue_city": address.get("city"),
                "venue_country": address.get("country"),
                "neutral": False if venue.get("fullName") and phase == "Regular season" else None,
                "league_code": code,
                "season": season.get("year"),
                "source": "ESPN:%s" % code,
            }
            records.append(_add_record_evidence(record, "ESPN", "B", url))
        status_name = SOURCE_SUCCESS if records else SOURCE_EMPTY
        return records, source_result("ESPN:%s" % code, status_name, len(records), elapsed, scope="fixtures", url=url)

    executor = ThreadPoolExecutor(max_workers=min(8, max(1, len(league_codes))))
    futures = [executor.submit(fetch_one, code) for code in league_codes]
    done, pending = wait(futures, timeout=35)
    records, results = [], []
    for future in done:
        try:
            rows, result = future.result()
        except Exception as exc:
            rows, result = [], source_result("ESPN", SOURCE_FAILED, error=exc, scope="fixtures")
        records.extend(rows)
        results.append(result)
    for future in pending:
        future.cancel()
        results.append(source_result("ESPN", SOURCE_FAILED, error="adapter deadline exceeded", scope="fixtures"))
    executor.shutdown(wait=False)
    return records, sorted(results, key=lambda item: item["source"])


def thesportsdb_daily(date_value, client=None):
    client = client or HttpClient()
    iso = date_string(date_value)
    url = "https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d=%s&s=Soccer" % urllib.parse.quote(iso)
    data, error, elapsed = client.get_json(url, headers={"Accept": "application/json"}, timeout=12, ttl=180)
    if error:
        return [], source_result("TheSportsDB", SOURCE_FAILED, elapsed_ms=elapsed, error=error, scope="fixtures", url=url)
    if not isinstance(data, dict):
        return [], source_result("TheSportsDB", SOURCE_INVALID, elapsed_ms=elapsed, error="non-object payload", scope="fixtures", url=url)
    records = []
    for event in data.get("events") or []:
        home = str(event.get("strHomeTeam") or "").strip()
        away = str(event.get("strAwayTeam") or "").strip()
        if not home or not away:
            continue
        record = {
            "provider_id": "TSDB:%s" % event.get("idEvent"),
            "home": home,
            "away": away,
            "kickoff": iso_utc(event.get("strTimestamp") or event.get("dateEvent")),
            "date": iso_utc(event.get("strTimestamp") or event.get("dateEvent")),
            "competition": event.get("strLeague"),
            "phase": "Regular season" if event.get("strLeague") else None,
            "round": event.get("intRound") or event.get("strRound"),
            "status": event.get("strStatus"),
            "venue_name": event.get("strVenue"),
            "venue_city": None,
            "venue_country": event.get("strCountry"),
            "neutral": None,
            "home_id": event.get("idHomeTeam"),
            "away_id": event.get("idAwayTeam"),
            "source": "TheSportsDB",
        }
        records.append(_add_record_evidence(record, "TheSportsDB", "B", url))
    status_name = SOURCE_SUCCESS if records else SOURCE_EMPTY
    return records, source_result("TheSportsDB", status_name, len(records), elapsed, scope="fixtures", url=url)


def api_football_daily(date_value, client=None):
    client = client or HttpClient()
    key = os.getenv("API_FOOTBALL_KEY", "").strip()
    if not key:
        return [], source_result("API-Football", SOURCE_NOT_CONFIGURED, error="API_FOOTBALL_KEY missing", scope="fixtures")
    iso = date_string(date_value)
    url = "https://v3.football.api-sports.io/fixtures?date=%s" % urllib.parse.quote(iso)
    data, error, elapsed = client.get_json(url, headers={"x-apisports-key": key, "Accept": "application/json"}, timeout=12, ttl=180)
    if error:
        return [], source_result("API-Football", SOURCE_FAILED, elapsed_ms=elapsed, error=error, scope="fixtures", url=url)
    response = (data or {}).get("response") if isinstance(data, dict) else None
    if not isinstance(response, list):
        return [], source_result("API-Football", SOURCE_INVALID, elapsed_ms=elapsed, error="missing response array", scope="fixtures", url=url)
    records = []
    for item in response:
        fixture = item.get("fixture") or {}
        teams = item.get("teams") or {}
        league = item.get("league") or {}
        home = (teams.get("home") or {}).get("name")
        away = (teams.get("away") or {}).get("name")
        if not home or not away:
            continue
        venue = fixture.get("venue") or {}
        status = fixture.get("status") or {}
        record = {
            "provider_id": "AF:%s" % fixture.get("id"),
            "home": home,
            "away": away,
            "kickoff": iso_utc(fixture.get("date")),
            "date": iso_utc(fixture.get("date")),
            "competition": league.get("name"),
            "phase": league.get("round") or "Competition phase",
            "round": league.get("round"),
            "status": status.get("long") or status.get("short"),
            "venue_name": venue.get("name"),
            "venue_city": venue.get("city"),
            "venue_country": league.get("country"),
            "neutral": None,
            "source": "API-Football",
        }
        records.append(_add_record_evidence(record, "API-Football", "B", url))
    status_name = SOURCE_SUCCESS if records else SOURCE_EMPTY
    return records, source_result("API-Football", status_name, len(records), elapsed, scope="fixtures", url=url)


def sportmonks_daily(date_value, client=None):
    client = client or HttpClient()
    token = os.getenv("SPORTMONKS_TOKEN", "").strip()
    if not token:
        return [], source_result("Sportmonks", SOURCE_NOT_CONFIGURED, error="SPORTMONKS_TOKEN missing", scope="fixtures")
    iso = date_string(date_value)
    url = "https://api.sportmonks.com/v3/football/fixtures/date/%s?api_token=%s&include=participants;venue;league" % (
        urllib.parse.quote(iso),
        urllib.parse.quote(token),
    )
    data, error, elapsed = client.get_json(url, headers={"Accept": "application/json"}, timeout=12, ttl=180)
    if error:
        return [], source_result("Sportmonks", SOURCE_FAILED, elapsed_ms=elapsed, error=error, scope="fixtures", url=url)
    payload = (data or {}).get("data") if isinstance(data, dict) else None
    if not isinstance(payload, list):
        return [], source_result("Sportmonks", SOURCE_INVALID, elapsed_ms=elapsed, error="missing data array", scope="fixtures", url=url)
    records = []
    for item in payload:
        participants = item.get("participants") or []
        home_item = next((p for p in participants if (p.get("meta") or {}).get("location") == "home"), None)
        away_item = next((p for p in participants if (p.get("meta") or {}).get("location") == "away"), None)
        if not home_item and participants:
            home_item = participants[0]
        if not away_item and len(participants) > 1:
            away_item = participants[-1]
        home = (home_item or {}).get("name")
        away = (away_item or {}).get("name")
        if not home or not away:
            continue
        venue = item.get("venue") or {}
        league = item.get("league") or {}
        record = {
            "provider_id": "SM:%s" % item.get("id"),
            "home": home,
            "away": away,
            "kickoff": iso_utc(item.get("starting_at")),
            "date": iso_utc(item.get("starting_at")),
            "competition": league.get("name"),
            "phase": item.get("round") or "Competition phase",
            "round": item.get("round"),
            "status": item.get("state_id"),
            "venue_name": venue.get("name"),
            "venue_city": venue.get("city_name"),
            "venue_country": venue.get("country_name"),
            "neutral": None,
            "source": "Sportmonks",
        }
        records.append(_add_record_evidence(record, "Sportmonks", "B", url))
    status_name = SOURCE_SUCCESS if records else SOURCE_EMPTY
    return records, source_result("Sportmonks", status_name, len(records), elapsed, scope="fixtures", url=url)


def _pl_headers():
    return {
        "Origin": "https://www.premierleague.com",
        "Referer": "https://www.premierleague.com/",
        "Accept": "application/json",
    }


def _premier_league_season_id(date_value, client):
    year = _season_start_year(date_value)
    url = "https://footballapi.pulselive.com/football/competitions/1/compseasons?page=0&pageSize=10"
    data, error, elapsed = client.get_json(url, headers=_pl_headers(), timeout=12, ttl=3600)
    if error or not isinstance(data, dict):
        return None, url, error or "invalid competition seasons payload", elapsed
    for item in data.get("content") or []:
        label = str(item.get("label") or "")
        if str(year) in label and str(year + 1) in label:
            try:
                return int(float(item.get("id"))), url, None, elapsed
            except Exception:
                pass
    return None, url, "season id not found", elapsed


def premierleague_official_daily(date_value, client=None):
    client = client or HttpClient()
    season_id, season_url, error, elapsed_1 = _premier_league_season_id(date_value, client)
    if error:
        return [], source_result("PremierLeague.com", SOURCE_FAILED, elapsed_ms=elapsed_1, error=error, source_class="A", scope="fixtures", url=season_url)
    url = (
        "https://footballapi.pulselive.com/football/fixtures?comp=1&compSeasons=%s"
        "&page=0&pageSize=500&sort=asc&altIds=true" % season_id
    )
    data, error, elapsed_2 = client.get_json(url, headers=_pl_headers(), timeout=15, ttl=180)
    elapsed = elapsed_1 + elapsed_2
    if error:
        return [], source_result("PremierLeague.com", SOURCE_FAILED, elapsed_ms=elapsed, error=error, source_class="A", scope="fixtures", url=url)
    content = (data or {}).get("content") if isinstance(data, dict) else None
    if not isinstance(content, list):
        return [], source_result("PremierLeague.com", SOURCE_INVALID, elapsed_ms=elapsed, error="missing content array", source_class="A", scope="fixtures", url=url)
    target_date = date_string(date_value)
    records = []
    for item in content:
        kickoff = item.get("kickoff") or {}
        millis = kickoff.get("millis")
        try:
            kickoff_iso = datetime.fromtimestamp(float(millis) / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            kickoff_iso = ""
        if date_string(kickoff_iso) != target_date:
            continue
        teams = item.get("teams") or []
        home = ((teams[0].get("team") or {}).get("name")) if teams else ""
        away = ((teams[1].get("team") or {}).get("name")) if len(teams) > 1 else ""
        if not home or not away:
            continue
        gameweek = item.get("gameweek") or {}
        comp_season = gameweek.get("compSeason") or {}
        competition = comp_season.get("competition") or {}
        ground = item.get("ground") or {}
        status_map = {"U": "SCHEDULED", "L": "IN_PROGRESS", "C": "COMPLETED"}
        record = {
            "provider_id": "PL:%s" % item.get("id"),
            "home": home,
            "away": away,
            "kickoff": kickoff_iso,
            "date": kickoff_iso,
            "competition": competition.get("description") or "Premier League",
            "phase": "Regular season",
            "round": "Gameweek %s" % gameweek.get("gameweek") if gameweek.get("gameweek") else None,
            "status": status_map.get(item.get("status"), item.get("status")),
            "venue_name": ground.get("name"),
            "venue_city": ground.get("city"),
            "venue_country": "England",
            "neutral": False,
            "league_code": "eng.1",
            "season_id": season_id,
            "source": "PremierLeague.com",
        }
        records.append(_add_record_evidence(record, "PremierLeague.com", "A", url))
    status_name = SOURCE_SUCCESS if records else SOURCE_EMPTY
    return records, source_result("PremierLeague.com", status_name, len(records), elapsed, source_class="A", scope="fixtures", url=url)


def _merge_records(records):
    merged = {}
    for record in records:
        key = _fixture_key(record)
        if not all(key[:2]):
            continue
        # Providers use different abbreviations (for example ``Nottm`` versus
        # ``Nottingham``).  A strict dictionary key left the same fixture as
        # several records and prevented cross-source confirmation in DAP.
        existing_key = next(
            (
                candidate
                for candidate in merged
                if candidate[2] == key[2]
                and teams_match(candidate[0], key[0])
                and teams_match(candidate[1], key[1])
            ),
            None,
        )
        if existing_key is not None:
            key = existing_key
        current = merged.get(key)
        if current is None:
            current = dict(record)
            current["_field_evidence"] = {
                name: list(values) for name, values in (record.get("_field_evidence") or {}).items()
            }
            current["providers"] = [record.get("_provider")]
            merged[key] = current
            continue
        current_priority = SOURCE_PRIORITY.get((current.get("_provider") or {}).get("class"), 0)
        new_priority = SOURCE_PRIORITY.get((record.get("_provider") or {}).get("class"), 0)
        higher_priority_value_used = False
        for field in (
            "provider_id",
            "home",
            "away",
            "kickoff",
            "date",
            "competition",
            "phase",
            "round",
            "status",
            "venue_name",
            "venue_city",
            "venue_country",
            "neutral",
            "league_code",
            "season",
            "season_id",
            "home_id",
            "away_id",
        ):
            value = record.get(field)
            if value is None or value == "":
                continue
            if current.get(field) in (None, "") or new_priority > current_priority:
                current[field] = value
                if new_priority > current_priority:
                    higher_priority_value_used = True
        if higher_priority_value_used:
            current["_provider"] = record.get("_provider")
        for field, values in (record.get("_field_evidence") or {}).items():
            current.setdefault("_field_evidence", {}).setdefault(field, []).extend(values)
        provider = record.get("_provider")
        if provider and provider not in current.setdefault("providers", []):
            current["providers"].append(provider)
    output = []
    for record in merged.values():
        record["match_id"] = stable_match_id(record)
        record["id"] = record["match_id"]
        record["source"] = ", ".join(sorted({p["source"] for p in record.get("providers") or [] if p}))
        output.append(record)
    output.sort(key=lambda item: parse_iso(item.get("kickoff")) or datetime.max.replace(tzinfo=timezone.utc))
    return output


def scan_fixtures(date_value, league_codes=None, client=None):
    """Run independent fixture adapters concurrently and return their real statuses."""

    client = client or HttpClient()
    league_codes = list(league_codes or DEFAULT_LEAGUES)
    tasks = [
        ("espn", lambda: espn_fixtures(date_value, league_codes, client)),
        ("tsdb", lambda: thesportsdb_daily(date_value, client)),
        ("api_football", lambda: api_football_daily(date_value, client)),
        ("sportmonks", lambda: sportmonks_daily(date_value, client)),
    ]
    if "eng.1" in league_codes:
        tasks.append(("premierleague", lambda: premierleague_official_daily(date_value, client)))
    executor = ThreadPoolExecutor(max_workers=len(tasks))
    futures = {executor.submit(task): name for name, task in tasks}
    done, pending = wait(list(futures), timeout=45)
    records, results = [], []
    for future in done:
        name = futures[future]
        try:
            rows, status = future.result()
            records.extend(rows)
            if isinstance(status, list):
                results.extend(status)
            else:
                results.append(status)
        except Exception as exc:
            results.append(source_result(name, SOURCE_FAILED, error=exc, scope="fixtures"))
    for future in pending:
        future.cancel()
        results.append(source_result(futures[future], SOURCE_FAILED, error="global source deadline exceeded", scope="fixtures"))
    executor.shutdown(wait=False)
    return _merge_records(records), sorted(results, key=lambda item: item["source"])


def thesportsdb_match_search(fixture, client=None):
    client = client or HttpClient()
    event_name = "%s_vs_%s" % (fixture.get("home") or "", fixture.get("away") or "")
    season = _season_label(fixture.get("kickoff") or fixture.get("date"))
    url = "https://www.thesportsdb.com/api/v1/json/3/searchevents.php?e=%s&s=%s" % (
        urllib.parse.quote(event_name.replace(" ", "_")),
        urllib.parse.quote(season),
    )
    data, error, elapsed = client.get_json(url, headers={"Accept": "application/json"}, timeout=12, ttl=180)
    if error:
        return [], source_result("TheSportsDB search", SOURCE_FAILED, elapsed_ms=elapsed, error=error, scope="match confirmation", url=url)
    events = (data or {}).get("event") if isinstance(data, dict) else None
    if events is None:
        events = []
    if not isinstance(events, list):
        return [], source_result("TheSportsDB search", SOURCE_INVALID, elapsed_ms=elapsed, error="event is not an array", scope="match confirmation", url=url)
    records = []
    for event in events:
        home = event.get("strHomeTeam")
        away = event.get("strAwayTeam")
        if not teams_match(home, fixture.get("home")) or not teams_match(away, fixture.get("away")):
            continue
        kickoff = iso_utc(event.get("strTimestamp") or (str(event.get("dateEvent") or "") + "T" + str(event.get("strTime") or "00:00:00")))
        if date_string(kickoff) != date_string(fixture.get("kickoff") or fixture.get("date")):
            continue
        record = {
            "provider_id": "TSDB:%s" % event.get("idEvent"),
            "home": home,
            "away": away,
            "kickoff": kickoff,
            "date": kickoff,
            "competition": event.get("strLeague"),
            "phase": "Regular season" if event.get("strLeague") else None,
            "round": event.get("strRound") or event.get("intRound"),
            "status": event.get("strStatus"),
            "venue_name": event.get("strVenue"),
            "venue_city": None,
            "venue_country": event.get("strCountry"),
            "neutral": None,
            "home_id": event.get("idHomeTeam"),
            "away_id": event.get("idAwayTeam"),
            "source": "TheSportsDB",
        }
        records.append(_add_record_evidence(record, "TheSportsDB", "B", url))
    status_name = SOURCE_SUCCESS if records else SOURCE_EMPTY
    return records, source_result("TheSportsDB search", status_name, len(records), elapsed, scope="match confirmation", url=url)


def premierleague_standings(fixture, client=None):
    client = client or HttpClient()
    if fixture.get("league_code") != "eng.1":
        return None, source_result("PremierLeague.com standings", SOURCE_EMPTY, scope="table", source_class="A")
    season_id = fixture.get("season_id")
    elapsed_total = 0
    if not season_id:
        season_id, season_url, error, elapsed = _premier_league_season_id(fixture.get("kickoff"), client)
        elapsed_total += elapsed
        if error:
            return None, source_result("PremierLeague.com standings", SOURCE_FAILED, elapsed_ms=elapsed_total, error=error, scope="table", source_class="A", url=season_url)
    url = "https://footballapi.pulselive.com/football/standings?comp=1&compSeasons=%s&page=0&pageSize=100&altIds=true" % season_id
    data, error, elapsed = client.get_json(url, headers=_pl_headers(), timeout=12, ttl=180)
    elapsed_total += elapsed
    if error:
        return None, source_result("PremierLeague.com standings", SOURCE_FAILED, elapsed_ms=elapsed_total, error=error, scope="table", source_class="A", url=url)
    try:
        entries = data["tables"][0]["entries"]
    except Exception:
        return None, source_result("PremierLeague.com standings", SOURCE_INVALID, elapsed_ms=elapsed_total, error="standings entries missing", scope="table", source_class="A", url=url)
    selected = []
    for entry in entries:
        team = (entry.get("team") or {}).get("name")
        if teams_match(team, fixture.get("home")) or teams_match(team, fixture.get("away")):
            selected.append(
                {
                    "team": team,
                    "position": entry.get("position"),
                    "overall": entry.get("overall") or {},
                }
            )
    if len(selected) != 2:
        return None, source_result("PremierLeague.com standings", SOURCE_EMPTY, len(selected), elapsed_total, scope="table", source_class="A", url=url)
    return {"provider": "PremierLeague.com", "class": "A", "season_id": season_id, "entries": selected, "url": _safe_url(url)}, source_result("PremierLeague.com standings", SOURCE_SUCCESS, len(selected), elapsed_total, scope="table", source_class="A", url=url)


def espn_standings(fixture, client=None):
    client = client or HttpClient()
    code = fixture.get("league_code")
    if not code:
        return None, source_result("ESPN standings", SOURCE_EMPTY, scope="table")
    year = _season_start_year(fixture.get("kickoff"))
    url = "https://site.api.espn.com/apis/v2/sports/soccer/%s/standings?season=%s" % (code, year)
    data, error, elapsed = client.get_json(url, headers={"Accept": "application/json"}, timeout=12, ttl=180)
    if error:
        return None, source_result("ESPN standings", SOURCE_FAILED, elapsed_ms=elapsed, error=error, scope="table", url=url)
    try:
        entries = data["children"][0]["standings"]["entries"]
    except Exception:
        return None, source_result("ESPN standings", SOURCE_INVALID, elapsed_ms=elapsed, error="standings entries missing", scope="table", url=url)
    selected = []
    for entry in entries:
        team = (entry.get("team") or {}).get("displayName")
        if teams_match(team, fixture.get("home")) or teams_match(team, fixture.get("away")):
            stats = {item.get("name"): item.get("value") for item in entry.get("stats") or []}
            selected.append({"team": team, "position": stats.get("rank"), "overall": stats})
    if len(selected) != 2:
        return None, source_result("ESPN standings", SOURCE_EMPTY, len(selected), elapsed, scope="table", url=url)
    return {"provider": "ESPN", "class": "B", "entries": selected, "url": _safe_url(url)}, source_result("ESPN standings", SOURCE_SUCCESS, len(selected), elapsed, scope="table", url=url)


def _parse_csv_date(value):
    for pattern in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value or "").strip(), pattern).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


def _row_side(row, team):
    if teams_match(row.get("HomeTeam"), team):
        return "home"
    if teams_match(row.get("AwayTeam"), team):
        return "away"
    return None


def _number(value, default=0.0):
    try:
        return float(str(value).replace(",", ".")) if value not in (None, "") else default
    except Exception:
        return default


def _team_summary(rows, team, limit=5):
    matches = [row for row in rows if _row_side(row, team) and row.get("FTHG") not in (None, "") and row.get("FTAG") not in (None, "")]
    matches.sort(key=lambda row: _parse_csv_date(row.get("Date")))
    matches = matches[-limit:]
    if not matches:
        return None
    points = shots = sot = corners = cards = gf = ga = 0.0
    for row in matches:
        side = _row_side(row, team)
        hg, ag = _number(row.get("FTHG")), _number(row.get("FTAG"))
        if side == "home":
            own, opp = hg, ag
            shots += _number(row.get("HS")); sot += _number(row.get("HST"))
            corners += _number(row.get("HC")); cards += _number(row.get("HY"))
        else:
            own, opp = ag, hg
            shots += _number(row.get("AS")); sot += _number(row.get("AST"))
            corners += _number(row.get("AC")); cards += _number(row.get("AY"))
        gf += own; ga += opp
        points += 3 if own > opp else 1 if own == opp else 0
    count = float(len(matches))
    return {
        "matches": int(count),
        "form": round(points / (count * 3) * 100, 1),
        "ppg": round(points / count, 3),
        "gd_per_match": round((gf - ga) / count, 3),
        "shots": round(shots / count, 1),
        "sot": round(sot / count, 1),
        "corners": round(corners / count, 1),
        "cards": round(cards / count, 1),
        "gf": round(gf / count, 2),
        "ga": round(ga / count, 2),
        "latest": matches[-1].get("Date"),
        "rows": matches,
    }


def football_data_stats(fixture, client=None):
    client = client or HttpClient()
    code = FOOTBALL_DATA_CODES.get(fixture.get("league_code"))
    if not code:
        return None, [source_result("Football-Data", SOURCE_EMPTY, error="league not supported", scope="historical statistics")]
    current = _football_data_season(fixture.get("kickoff"))
    start = int(current[:2])
    previous = "%02d%02d" % ((start - 1) % 100, start % 100)
    all_rows, results = [], []
    ranges = []

    def fetch_season(season):
        url = "https://www.football-data.co.uk/mmz4281/%s/%s.csv" % (season, code)
        text, error, elapsed = client.get_text(url, headers={"Accept": "text/csv"}, timeout=12, ttl=3600)
        if error:
            return season, [], source_result("Football-Data:%s" % season, SOURCE_FAILED, elapsed_ms=elapsed, error=error, scope="historical statistics", url=url)
        try:
            rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
        except Exception as exc:
            return season, [], source_result("Football-Data:%s" % season, SOURCE_INVALID, elapsed_ms=elapsed, error=exc, scope="historical statistics", url=url)
        cutoff = parse_iso(fixture.get("kickoff"))
        cutoff_day = cutoff.replace(hour=0, minute=0, second=0, microsecond=0) if cutoff else None
        completed = [
            row for row in rows
            if row.get("FTHG") not in (None, "")
            and row.get("FTAG") not in (None, "")
            # CSV has no kickoff time, so the whole target day is excluded to
            # prevent same-day result leakage in historical/prematch runs.
            and (not cutoff_day or _parse_csv_date(row.get("Date")) < cutoff_day)
        ]
        return season, completed, source_result("Football-Data:%s" % season, SOURCE_SUCCESS if completed else SOURCE_EMPTY, len(completed), elapsed, scope="historical statistics", url=url)

    executor = ThreadPoolExecutor(max_workers=2)
    season_outputs = [
        future.result()
        for future in [executor.submit(fetch_season, season) for season in (current, previous)]
    ]
    executor.shutdown(wait=True)
    for season, completed, result in season_outputs:
        all_rows.extend(completed)
        if completed:
            ranges.append(season)
        results.append(result)
    all_rows.sort(key=lambda row: _parse_csv_date(row.get("Date")))
    home_summary = _team_summary(all_rows, fixture.get("home"), 10)
    away_summary = _team_summary(all_rows, fixture.get("away"), 10)
    if not home_summary or not away_summary:
        return None, results
    h2h = [
        row for row in all_rows
        if (
            teams_match(row.get("HomeTeam"), fixture.get("home"))
            and teams_match(row.get("AwayTeam"), fixture.get("away"))
        ) or (
            teams_match(row.get("HomeTeam"), fixture.get("away"))
            and teams_match(row.get("AwayTeam"), fixture.get("home"))
        )
    ][-10:]
    current_rows = [row for row in all_rows if _parse_csv_date(row.get("Date")).year == _season_start_year(fixture.get("kickoff"))]
    freshness = 100 if len(current_rows) >= 10 else 80 if current_rows else 65
    return {
        "provider": "Football-Data",
        "class": "B",
        "seasons": ranges,
        "home": home_summary,
        "away": away_summary,
        "h2h": h2h,
        "freshness": freshness,
        "sample_uses_previous_season": len(current_rows) < 10,
    }, results


def understat_stats(fixture, client=None):
    client = client or HttpClient()
    league = UNDERSTAT_CODES.get(fixture.get("league_code"))
    if not league:
        return None, source_result("Understat", SOURCE_EMPTY, error="league not supported", scope="xG")
    season = _season_start_year(fixture.get("kickoff"))
    url = "https://understat.com/getLeagueData/%s/%s" % (league, season)
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://understat.com/league/%s/%s" % (league, season),
        "Accept": "application/json",
    }
    data, error, elapsed = client.get_json(url, headers=headers, timeout=12, ttl=600)
    if error:
        return None, source_result("Understat", SOURCE_FAILED, elapsed_ms=elapsed, error=error, scope="xG", url=url)
    teams = (data or {}).get("teams") if isinstance(data, dict) else None
    if isinstance(teams, dict):
        teams = list(teams.values())
    if not isinstance(teams, list):
        return None, source_result("Understat", SOURCE_INVALID, elapsed_ms=elapsed, error="teams missing", scope="xG", url=url)

    def selected(team_name):
        candidates = [team for team in teams if teams_match(team.get("title"), team_name)]
        if not candidates:
            return None
        history = candidates[0].get("history") or []
        cutoff = parse_iso(fixture.get("kickoff"))
        if cutoff:
            history = [
                row for row in history
                if parse_iso(row.get("date")) and parse_iso(row.get("date")) < cutoff
            ]
        history = history[-5:]
        if not history:
            return None
        return {
            "team": candidates[0].get("title"),
            "matches": len(history),
            "xg": round(sum(_number(row.get("xG")) for row in history) / len(history), 3),
            "xga": round(sum(_number(row.get("xGA")) for row in history) / len(history), 3),
            "latest": history[-1].get("date"),
            "history": history,
        }

    home, away = selected(fixture.get("home")), selected(fixture.get("away"))
    if not home or not away:
        return None, source_result("Understat", SOURCE_EMPTY, records=int(bool(home)) + int(bool(away)), elapsed_ms=elapsed, scope="xG", url=url)
    return {"provider": "Understat", "class": "B", "home": home, "away": away, "freshness": 100}, source_result("Understat", SOURCE_SUCCESS, home["matches"] + away["matches"], elapsed, scope="xG", url=url)


def _status_normalized(value):
    value = str(value or "").upper()
    if value in {"U", "NS", "SCHEDULED", "STATUS_SCHEDULED", "NOT STARTED"} or "SCHEDULE" in value:
        return "SCHEDULED"
    if value in {"L", "LIVE", "IN_PROGRESS", "STATUS_IN_PROGRESS"} or "PROGRESS" in value:
        return "IN_PROGRESS"
    if value in {"C", "FT", "COMPLETED", "STATUS_FINAL", "STATUS_FULL_TIME"} or "FINAL" in value:
        return "COMPLETED"
    return value or None


def _evidence_quality(evidence, chosen=None, normalizer=None):
    evidence = [item for item in evidence if item.get("value") not in (None, "")]
    if not evidence:
        return 0.0, "NONE"
    normalizer = normalizer or (lambda value: str(value).strip().lower())
    groups = {}
    for item in evidence:
        key = normalizer(item.get("value"))
        groups.setdefault(key, []).append(item)
    chosen_key = normalizer(chosen) if chosen not in (None, "") else next(iter(groups))
    supporting = groups.get(chosen_key) or []
    providers = {item.get("source") for item in supporting}
    has_official = any(item.get("class") == "A" for item in supporting)
    if len(providers) >= 2:
        quality = 1.0
    elif has_official:
        quality = 0.9
    else:
        quality = 0.75
    conflict = "NONE"
    if len(groups) > 1:
        conflict = "RESOLVED" if has_official else "UNRESOLVED"
    return quality, conflict


def _field_evidence(fixture, *fields):
    combined = []
    mapping = fixture.get("_field_evidence") or {}
    for field in fields:
        combined.extend(mapping.get(field) or [])
    return combined


def _merge_target_fixture(base, records):
    matches = []
    for record in records:
        if not teams_match(record.get("home"), base.get("home")):
            continue
        if not teams_match(record.get("away"), base.get("away")):
            continue
        if date_string(record.get("kickoff")) != date_string(base.get("kickoff") or base.get("date")):
            continue
        matches.append(record)
    # Once a provider confirms the requested identity, provider records own the
    # fixture facts. A date-only form candidate must not beat verified kickoff.
    candidates = matches if matches else [base]
    merged = _merge_records(candidates)
    if not merged:
        return dict(base)
    best = next(
        (item for item in merged if teams_match(item.get("home"), base.get("home")) and teams_match(item.get("away"), base.get("away"))),
        merged[0],
    )
    return best


def _role_assignment(fixture, table_context, football_stats):
    home, away = fixture.get("home"), fixture.get("away")
    trace = []
    source_ids = []
    entries = []
    if table_context:
        entries = table_context.get("entries") or []
        source_ids.append(table_context.get("provider"))
    if len(entries) == 2:
        by_team = {normalize_team(entry.get("team")): entry for entry in entries}
        home_entry = next((entry for key, entry in by_team.items() if teams_match(key, home)), None)
        away_entry = next((entry for key, entry in by_team.items() if teams_match(key, away)), None)
        if home_entry and away_entry:
            home_overall, away_overall = home_entry.get("overall") or {}, away_entry.get("overall") or {}
            home_played = _number(home_overall.get("played", home_overall.get("gamesPlayed")))
            away_played = _number(away_overall.get("played", away_overall.get("gamesPlayed")))
            if home_played >= 5 and away_played >= 5:
                home_points = _number(home_overall.get("points"))
                away_points = _number(away_overall.get("points"))
                home_ppg = home_points / home_played
                away_ppg = away_points / away_played
                trace.append("R2 PPG %.3f vs %.3f" % (home_ppg, away_ppg))
                if abs(home_ppg - away_ppg) >= 0.15:
                    favourite, underdog = (home, away) if home_ppg > away_ppg else (away, home)
                    return {"status": "RESOLVED", "favourite": favourite, "underdog": underdog, "basis": "R2_TABLE_PPG", "source_ids": source_ids, "values": {"home": home_ppg, "away": away_ppg}, "trace": trace}
            else:
                trace.append("R2 unavailable: fewer than 5 completed matches per side")
    if football_stats:
        h, a = football_stats.get("home") or {}, football_stats.get("away") or {}
        if h.get("matches") == 10 and a.get("matches") == 10:
            source_ids.append("Football-Data")
            h_ppg, a_ppg = _number(h.get("ppg")), _number(a.get("ppg"))
            trace.append("R4 PPG %.3f vs %.3f" % (h_ppg, a_ppg))
            if abs(h_ppg - a_ppg) >= 0.20:
                favourite, underdog = (home, away) if h_ppg > a_ppg else (away, home)
                return {"status": "RESOLVED", "favourite": favourite, "underdog": underdog, "basis": "R4_LAST10_PPG", "source_ids": sorted(set(source_ids)), "values": {"home": h_ppg, "away": a_ppg}, "trace": trace}
            h_gd, a_gd = _number(h.get("gd_per_match")), _number(a.get("gd_per_match"))
            trace.append("R4 GD/match %.3f vs %.3f" % (h_gd, a_gd))
            if abs(h_gd - a_gd) >= 0.25:
                favourite, underdog = (home, away) if h_gd > a_gd else (away, home)
                return {"status": "RESOLVED", "favourite": favourite, "underdog": underdog, "basis": "R4_LAST10_GD", "source_ids": sorted(set(source_ids)), "values": {"home": h_gd, "away": a_gd}, "trace": trace}
    if fixture.get("neutral") is False and fixture.get("venue_name"):
        trace.append("R5 classical home advantage")
        return {"status": "RESOLVED", "favourite": home, "underdog": away, "basis": "R5_HOME_ADVANTAGE", "source_ids": sorted(set(source_ids + ["DAP-D04"])), "values": {"home": "CLASSICAL", "away": "AWAY"}, "trace": trace}
    trace.append("R1-R5 unresolved")
    return {"status": "UNRESOLVED", "favourite": None, "underdog": None, "basis": None, "source_ids": sorted(set(source_ids)), "values": {}, "trace": trace}


def _stat_evidence(source, source_class="B"):
    return [{"source": source, "class": source_class, "value": "AVAILABLE"}]


def collect_dap_for_fixture(fixture, progress_callback=None, client=None):
    """Collect every critical DAP field before returning a closeable contract."""

    client = client or HttpClient()
    progress_callback = progress_callback or (lambda *args: None)
    fixture = dict(fixture)
    fixture["kickoff"] = iso_utc(fixture.get("kickoff") or fixture.get("date"))
    source_register = list(fixture.pop("_source_results", []) or [])

    progress_callback("DAP.SOURCES", 8, "RUNNING", "Potwierdzanie tożsamości meczu")
    target_date = fixture.get("kickoff") or fixture.get("date")
    target_sources = []
    source_tasks = []
    if fixture.get("league_code"):
        source_tasks.append(("ESPN confirmation", lambda: espn_fixtures(target_date, [fixture.get("league_code")], client)))
    source_tasks.append(("TheSportsDB search", lambda: thesportsdb_match_search(fixture, client)))
    if fixture.get("league_code") == "eng.1":
        source_tasks.append(("PremierLeague.com", lambda: premierleague_official_daily(target_date, client)))
    source_tasks.append(("API-Football", lambda: api_football_daily(target_date, client)))
    source_tasks.append(("Sportmonks", lambda: sportmonks_daily(target_date, client)))
    source_executor = ThreadPoolExecutor(max_workers=len(source_tasks))
    source_futures = {source_executor.submit(task): name for name, task in source_tasks}
    source_done, source_pending = wait(list(source_futures), timeout=35)
    for future in source_done:
        name = source_futures[future]
        try:
            rows, results = future.result()
            target_sources.extend(rows)
            source_register.extend(results if isinstance(results, list) else [results])
        except Exception as exc:
            source_register.append(source_result(name, SOURCE_FAILED, error=exc, scope="match confirmation"))
    for future in source_pending:
        future.cancel()
        source_register.append(source_result(source_futures[future], SOURCE_FAILED, error="adapter deadline exceeded", scope="match confirmation"))
    source_executor.shutdown(wait=False)
    fixture = _merge_target_fixture(fixture, target_sources)
    fixture["match_id"] = stable_match_id(fixture)
    progress_callback("DAP.SOURCES", 35, "COMPLETED", "Źródła terminarza zakończone")

    progress_callback("DAP.TABLE", 40, "RUNNING", "Pobieranie tabeli i kontekstu D09")
    table_executor = ThreadPoolExecutor(max_workers=2)
    pl_future = table_executor.submit(premierleague_standings, fixture, client)
    espn_future = table_executor.submit(espn_standings, fixture, client)
    pl_table, pl_result = pl_future.result()
    espn_table, espn_result = espn_future.result()
    table_executor.shutdown(wait=True)
    source_register.extend([pl_result, espn_result])
    table_context = pl_table or espn_table
    table_evidence = []
    for table in (pl_table, espn_table):
        if table:
            table_evidence.append({"source": table["provider"], "class": table["class"], "value": table.get("entries"), "url": table.get("url")})
    progress_callback("DAP.TABLE", 52, "COMPLETED" if table_context else "EMPTY", "Tabela zweryfikowana" if table_context else "Brak tabeli")

    progress_callback("DAP.STATS", 55, "RUNNING", "Pobieranie danych statystycznych")
    executor = ThreadPoolExecutor(max_workers=2)
    football_future = executor.submit(football_data_stats, fixture, client)
    understat_future = executor.submit(understat_stats, fixture, client)
    football_stats, football_results = football_future.result()
    understat, understat_result = understat_future.result()
    executor.shutdown(wait=True)
    source_register.extend(football_results)
    source_register.append(understat_result)
    progress_callback("DAP.STATS", 76, "COMPLETED", "Statystyki źródłowe zakończone")

    field_evidence = fixture.get("_field_evidence") or {}
    items = []

    pair_evidence = _field_evidence(fixture, "home", "away")
    home_quality, home_conflict = _evidence_quality(
        _field_evidence(fixture, "home"), fixture.get("home"), normalize_team
    )
    away_quality, away_conflict = _evidence_quality(
        _field_evidence(fixture, "away"), fixture.get("away"), normalize_team
    )
    pair_quality = min(home_quality, away_quality)
    pair_conflict = (
        "UNRESOLVED"
        if "UNRESOLVED" in (home_conflict, away_conflict)
        else "RESOLVED"
        if "RESOLVED" in (home_conflict, away_conflict)
        else "NONE"
    )
    items.append(make_dap_item("D01", "Oficjalna para HOME-AWAY", "CRITICAL", {"home": fixture.get("home"), "away": fixture.get("away")}, bool(fixture.get("home") and fixture.get("away")), evidence=pair_evidence, source_quality=pair_quality, freshness=100, conflict=pair_conflict))

    kickoff_evidence = _field_evidence(fixture, "kickoff")
    kickoff_quality, kickoff_conflict = _evidence_quality(kickoff_evidence, fixture.get("kickoff"), iso_utc)
    items.append(make_dap_item("D02", "Data, godzina i strefa", "CRITICAL", {"kickoff": fixture.get("kickoff"), "timezone": "UTC"}, bool(parse_iso(fixture.get("kickoff"))), evidence=kickoff_evidence, source_quality=kickoff_quality, freshness=100, conflict=kickoff_conflict, dynamic=True))

    comp_evidence = _field_evidence(fixture, "competition", "phase")
    comp_quality, comp_conflict = _evidence_quality(_field_evidence(fixture, "competition"), fixture.get("competition"))
    phase_quality, phase_conflict = _evidence_quality(_field_evidence(fixture, "phase"), fixture.get("phase"))
    items.append(make_dap_item("D03", "Rozgrywki i faza", "CRITICAL", {"competition": fixture.get("competition"), "phase": fixture.get("phase"), "round": fixture.get("round")}, bool(fixture.get("competition") and fixture.get("phase")), evidence=comp_evidence, source_quality=min(comp_quality, phase_quality) if comp_quality and phase_quality else max(comp_quality, phase_quality), freshness=100, conflict="UNRESOLVED" if "UNRESOLVED" in (comp_conflict, phase_conflict) else "RESOLVED" if "RESOLVED" in (comp_conflict, phase_conflict) else "NONE"))

    venue_evidence = _field_evidence(fixture, "venue_name", "venue_city", "venue_country", "neutral")
    venue_quality, venue_conflict = _evidence_quality(_field_evidence(fixture, "venue_name"), fixture.get("venue_name"))
    items.append(make_dap_item("D04", "Stadion i neutral venue", "CRITICAL", {"stadium": fixture.get("venue_name"), "city": fixture.get("venue_city"), "country": fixture.get("venue_country"), "neutral": fixture.get("neutral")}, bool(fixture.get("venue_name") and fixture.get("neutral") is not None), evidence=venue_evidence, source_quality=venue_quality, freshness=100, conflict=venue_conflict))

    status_evidence = _field_evidence(fixture, "status")
    normalized_status = _status_normalized(fixture.get("status"))
    status_quality, status_conflict = _evidence_quality(status_evidence, normalized_status, _status_normalized)
    items.append(make_dap_item("D-STATUS", "Oficjalny status meczu", "CRITICAL", normalized_status, bool(normalized_status), evidence=status_evidence, source_quality=status_quality, freshness=100, conflict=status_conflict, dynamic=True))

    table_quality, table_conflict = _evidence_quality(table_evidence, table_context.get("entries") if table_context else None, lambda value: canonical_table(value))
    table_applicable = str(fixture.get("phase") or "").lower() != "friendly"
    items.append(make_dap_item("D09", "Tabela / grupa / dwumecz", "CRITICAL", table_context, bool(table_context), evidence=table_evidence, source_quality=table_quality, freshness=100 if table_context else 0, conflict=table_conflict, applicable=table_applicable))

    character = "LEAGUE" if "league" in str(fixture.get("competition") or "").lower() or str(fixture.get("phase") or "").lower() == "regular season" else "TOURNAMENT"
    items.append(make_dap_item("D05", "Charakter meczu", "MANDATORY", character, bool(fixture.get("competition")), evidence=comp_evidence, source_quality=comp_quality, freshness=100))
    items.append(make_dap_item("D06", "Stawka meczu", "MANDATORY", None, False, reason="Brak źródłowego potwierdzenia szczególnej stawki"))
    items.append(make_dap_item("D07", "Czy remis jest korzystny", "MANDATORY", None, False, reason="Brak rozstrzygniętego kontekstu regulaminowego"))
    home_advantage = "CLASSICAL" if fixture.get("neutral") is False and fixture.get("venue_name") else None
    items.append(make_dap_item("D08", "Home advantage", "MANDATORY", home_advantage, bool(home_advantage), evidence=venue_evidence, source_quality=venue_quality, freshness=100))
    items.append(make_dap_item("D12", "Kluczowe absencje / dostępność", "MANDATORY", None, False, dynamic=True, reason="Brak zweryfikowanego źródła absencji"))

    stats_quality = 0.75 if football_stats else 0.0
    stats_freshness = football_stats.get("freshness", 0) if football_stats else 0
    items.append(make_dap_item("D-FORM", "Forma i split HOME/AWAY", "MANDATORY", {"home": (football_stats or {}).get("home"), "away": (football_stats or {}).get("away")}, bool(football_stats), evidence=_stat_evidence("Football-Data") if football_stats else [], source_quality=stats_quality, freshness=stats_freshness))
    h2h = (football_stats or {}).get("h2h") or []
    items.append(make_dap_item("D-H2H", "H2H", "MANDATORY", h2h, bool(h2h), evidence=_stat_evidence("Football-Data") if h2h else [], source_quality=stats_quality if h2h else 0, freshness=stats_freshness if h2h else 0))
    goal_data = {"home_gf": ((football_stats or {}).get("home") or {}).get("gf"), "home_ga": ((football_stats or {}).get("home") or {}).get("ga"), "away_gf": ((football_stats or {}).get("away") or {}).get("gf"), "away_ga": ((football_stats or {}).get("away") or {}).get("ga")}
    items.append(make_dap_item("D-GOALS", "Gole HOME/AWAY", "MANDATORY", goal_data, bool(football_stats), evidence=_stat_evidence("Football-Data") if football_stats else [], source_quality=stats_quality, freshness=stats_freshness))
    items.append(make_dap_item("D-XG", "xG / xGA", "MANDATORY", understat, bool(understat), evidence=_stat_evidence("Understat") if understat else [], source_quality=0.75 if understat else 0, freshness=(understat or {}).get("freshness", 0) if understat else 0))
    shot_data = {"home_shots": ((football_stats or {}).get("home") or {}).get("shots"), "home_sot": ((football_stats or {}).get("home") or {}).get("sot"), "away_shots": ((football_stats or {}).get("away") or {}).get("shots"), "away_sot": ((football_stats or {}).get("away") or {}).get("sot")}
    items.append(make_dap_item("D-SHOTS", "Strzały i SOT", "MANDATORY", shot_data, bool(football_stats), evidence=_stat_evidence("Football-Data") if football_stats else [], source_quality=stats_quality, freshness=stats_freshness))
    btts_data = None
    if football_stats:
        home_rows = (football_stats.get("home") or {}).get("rows") or []
        away_rows = (football_stats.get("away") or {}).get("rows") or []
        sample = home_rows + away_rows
        btts_data = {"sample": len(sample), "rate": round(sum(1 for row in sample if _number(row.get("FTHG")) > 0 and _number(row.get("FTAG")) > 0) / float(len(sample)), 3) if sample else None}
    items.append(make_dap_item("D-BTTS", "BTTS / clean sheets", "MANDATORY", btts_data, bool(btts_data), evidence=_stat_evidence("Football-Data") if btts_data else [], source_quality=stats_quality if btts_data else 0, freshness=stats_freshness if btts_data else 0))
    items.append(make_dap_item("D-TIMING", "Goal timing", "MANDATORY", None, False, reason="Football-Data CSV nie zwraca minut bramek"))

    integrity_issues = []
    if teams_match(fixture.get("home"), fixture.get("away")):
        integrity_issues.append({"severity": "CRITICAL", "code": "SAME_TEAM_BOTH_SIDES"})
    if not parse_iso(fixture.get("kickoff")):
        integrity_issues.append({"severity": "CRITICAL", "code": "INVALID_KICKOFF"})
    if normalized_status in {"IN_PROGRESS", "COMPLETED"}:
        integrity_issues.append({"severity": "CRITICAL", "code": "NOT_PREMATCH_STATUS"})
    if football_stats:
        for side in ("home", "away"):
            summary = football_stats.get(side) or {}
            if _number(summary.get("sot")) > _number(summary.get("shots")):
                integrity_issues.append({"severity": "CRITICAL", "code": "SOT_GT_SHOTS_%s" % side.upper()})

    warnings = []
    if any(result.get("status") in {SOURCE_FAILED, SOURCE_INVALID} for result in source_register):
        warnings.append("DAP-WF-05 SOURCE_PATH_DEVIATION")
    if football_stats and football_stats.get("sample_uses_previous_season"):
        warnings.append("DAP-WF-03 MIXED_CURRENT_PREVIOUS_SEASON_SAMPLE")
    if understat and min((understat.get("home") or {}).get("matches", 0), (understat.get("away") or {}).get("matches", 0)) < 5:
        warnings.append("DAP-WF-02 LOW_CURRENT_XG_SAMPLE")

    role = _role_assignment(fixture, table_context, football_stats)
    engine_input = {
        "home_team": fixture.get("home") or "",
        "away_team": fixture.get("away") or "",
        "city": fixture.get("venue_city") or "",
        "league": fixture.get("competition") or "",
        "xg_home": ((understat or {}).get("home") or {}).get("xg", 0),
        "xg_away": ((understat or {}).get("away") or {}).get("xg", 0),
        "xga_home": ((understat or {}).get("home") or {}).get("xga", 0),
        "xga_away": ((understat or {}).get("away") or {}).get("xga", 0),
        "xg_source": "Understat" if understat else "brak",
        "form_home": ((football_stats or {}).get("home") or {}).get("form", 0),
        "form_away": ((football_stats or {}).get("away") or {}).get("form", 0),
        "shots_home": ((football_stats or {}).get("home") or {}).get("shots", 0),
        "shots_away": ((football_stats or {}).get("away") or {}).get("shots", 0),
        "sot_home": ((football_stats or {}).get("home") or {}).get("sot", 0),
        "sot_away": ((football_stats or {}).get("away") or {}).get("sot", 0),
        "corners_home": ((football_stats or {}).get("home") or {}).get("corners", 0),
        "corners_away": ((football_stats or {}).get("away") or {}).get("corners", 0),
        "cards_home": ((football_stats or {}).get("home") or {}).get("cards", 0),
        "cards_away": ((football_stats or {}).get("away") or {}).get("cards", 0),
        "tempo": 62 if football_stats and (_number(((football_stats.get("home") or {}).get("shots"))) + _number(((football_stats.get("away") or {}).get("shots")))) >= 25 else 43 if football_stats else 0,
        "odds": 0,
        "odds_1": 0,
        "odds_x": 0,
        "odds_2": 0,
        "odds_source": "DISABLED_FOR_DECISION",
        "sources": ", ".join(sorted({result.get("source") for result in source_register if result.get("status") == SOURCE_SUCCESS})),
        "message": "Dane zamrożone w Output Contract DAP",
    }
    dynamic_refresh = {
        "fixture_status": "REFRESHED",
        "kickoff": "REFRESHED",
        "availability": "MISSING",
        "lineups": "NOT_ACTIVATED",
        "weather": "NOT_ACTIVATED",
        "external_market": "NOT_ACTIVATED",
    }
    progress_callback("DAP.CONTRACT", 85, "RUNNING", "Walidacja pozycji krytycznych i Output Contract")
    contract = build_dap_output_contract(
        fixture=fixture,
        items=items,
        source_register=source_register,
        role_assignment=role,
        engine_input=engine_input,
        warning_flags=warnings,
        integrity_issues=integrity_issues,
        dynamic_refresh_status=dynamic_refresh,
    )
    progress_callback("DAP.CONTRACT", 100, contract.get("status_dap"), contract.get("handover_status"))
    return contract


def canonical_table(value):
    if value is None:
        return ""
    if isinstance(value, dict) and "entries" in value:
        value = value.get("entries")
    if isinstance(value, list):
        normalized = []
        for entry in value:
            overall = entry.get("overall") or {}
            normalized.append(
                (
                    normalize_team(entry.get("team")),
                    int(_number(entry.get("position"))),
                    int(_number(overall.get("played", overall.get("gamesPlayed")))),
                    int(_number(overall.get("points"))),
                )
            )
        return json.dumps(sorted(normalized), separators=(",", ":"))
    return str(value)
