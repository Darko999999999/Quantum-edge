"""Global DAP -> engines -> persistence orchestration for Quantum Edge.

This module is deliberately independent from FastAPI and from external data
providers.  It owns the state machine and is the only place allowed to commit a
final analysis.  Provider-specific collection lives in ``qe_sources.py``.
"""

from __future__ import print_function

from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import sqlite3
import uuid


MODEL_VERSION = "MASTER-v11.3-PR17.2"
DAP_VERSION = "DAP-v11.0"
EPL_WEIGHTS_VERSION = "W10.3.0"
ROLE_ALGORITHM_VERSION = "ROLE-P11.0.2"


class PipelineState(str, Enum):
    CREATED = "CREATED"
    DAP_RUNNING = "DAP_RUNNING"
    DAP_BLOCKED = "DAP_BLOCKED"
    READY_FOR_ENGINE_1 = "READY_FOR_ENGINE_1"
    ENGINES_RUNNING = "ENGINES_RUNNING"
    READY_TO_SAVE = "READY_TO_SAVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DapGate(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    LIMITED = "LIMITED"
    FAIL = "FAIL"


class PipelineViolation(RuntimeError):
    """Raised when a caller attempts to bypass the global pipeline contract."""


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_default(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    raise TypeError("Object is not JSON serializable: %r" % (value,))


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def payload_hash(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def stable_match_id(fixture):
    raw = "|".join(
        [
            str(fixture.get("home") or "").strip().lower(),
            str(fixture.get("away") or "").strip().lower(),
            str(fixture.get("kickoff") or fixture.get("date") or "").strip(),
            str(fixture.get("competition") or fixture.get("league_code") or "").strip().lower(),
        ]
    )
    return "QE-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()


def make_dap_item(
    item_id,
    label,
    classification,
    value=None,
    available=False,
    active=True,
    evidence=None,
    source_quality=0.0,
    freshness=0.0,
    conflict="NONE",
    dynamic=False,
    applicable=True,
    reason=None,
):
    weights = {"CRITICAL": 5, "MANDATORY": 3, "CONDITIONAL": 1}
    classification = str(classification or "").upper()
    if classification not in weights:
        raise ValueError("Unknown DAP classification: %s" % classification)
    if not applicable:
        active = False
    return {
        "id": item_id,
        "label": label,
        "classification": classification,
        "weight": weights[classification],
        "active": bool(active),
        "applicable": bool(applicable),
        "available": bool(available),
        "value": value,
        "evidence": list(evidence or []),
        "source_quality": max(0.0, min(1.0, float(source_quality or 0.0))),
        "freshness": max(0.0, min(100.0, float(freshness or 0.0))),
        "conflict": str(conflict or "NONE").upper(),
        "dynamic": bool(dynamic),
        "reason": reason,
    }


def _round_metric(value):
    return round(max(0.0, min(100.0, float(value))), 2)


def _required_contract_fields_present(contract):
    required = [
        "match_id",
        "input_snapshot_id",
        "data_cutoff_timestamp",
        "model_version",
        "dap_version_id",
        "output_contract_version_id",
        "status_dap",
        "dc",
        "sc",
        "df",
        "di",
        "fdc",
        "data_integrity_check",
        "warning_flags",
        "immutable_facts_package",
        "source_register",
        "data_collection_log_id",
        "dynamic_refresh_status",
        "handover_status",
        "decision_trace_id",
        "prematch_role_favourite",
        "prematch_role_underdog",
        "role_status",
        "role_basis",
        "role_source_ids",
        "role_tie_break_trace",
        "role_algorithm_version",
    ]
    missing = []
    for key in required:
        if key not in contract or contract.get(key) is None:
            missing.append(key)
    return missing


def build_dap_output_contract(
    fixture,
    items,
    source_register,
    role_assignment,
    engine_input,
    warning_flags=None,
    integrity_issues=None,
    dynamic_refresh_status=None,
    collected_at=None,
):
    """Build and close the immutable DAP Output Contract.

    Gate priority follows MASTER v11.3: critical facts and integrity first,
    followed by mandatory coverage and the calculated quality metrics.
    """

    collected_at = collected_at or utc_now_iso()
    warning_flags = list(warning_flags or [])
    integrity_issues = list(integrity_issues or [])
    dynamic_refresh_status = dynamic_refresh_status or {}
    active_items = [item for item in items if item.get("active")]
    if not active_items:
        raise ValueError("DAP cannot close without active data items")

    denominator = float(sum(item["weight"] for item in active_items))
    dc = 100.0 * sum(
        item["weight"] * (1.0 if item.get("available") else 0.0)
        for item in active_items
    ) / denominator
    sc = 100.0 * sum(
        item["weight"] * float(item.get("source_quality") or 0.0)
        for item in active_items
    ) / denominator
    df = sum(
        item["weight"] * float(item.get("freshness") or 0.0)
        for item in active_items
    ) / denominator

    critical_conflicts = [
        item["id"]
        for item in active_items
        if item["classification"] == "CRITICAL"
        and item.get("conflict") == "UNRESOLVED"
    ]
    resolved_conflicts = [
        item["id"]
        for item in active_items
        if item.get("conflict") == "RESOLVED"
    ]
    minor_conflicts = [
        item["id"]
        for item in active_items
        if item.get("conflict") == "MINOR"
    ]
    di = 100.0
    di -= 40.0 * len(critical_conflicts)
    di -= 20.0 * len(resolved_conflicts)
    di -= 5.0 * len(minor_conflicts)
    for issue in integrity_issues:
        severity = str(issue.get("severity") or "MAJOR").upper()
        di -= 40.0 if severity == "CRITICAL" else 20.0 if severity == "MAJOR" else 5.0
    di = max(0.0, di)

    dc, sc, df, di = map(_round_metric, (dc, sc, df, di))
    fdc = _round_metric(0.40 * dc + 0.30 * sc + 0.20 * df + 0.10 * di)

    missing_critical = [
        item["id"]
        for item in active_items
        if item["classification"] == "CRITICAL" and not item.get("available")
    ]
    missing_mandatory = [
        item["id"]
        for item in active_items
        if item["classification"] == "MANDATORY" and not item.get("available")
    ]
    stale_dynamic = [
        item["id"]
        for item in active_items
        if item.get("dynamic") and item.get("available") and item.get("freshness", 0) < 50
    ]
    role_status = str(role_assignment.get("status") or "UNRESOLVED").upper()

    if critical_conflicts or missing_critical:
        warning_flags.append("DAP-WF-01 CRITICAL_DATA_CONFLICT_OR_MISSING")
    if missing_mandatory:
        warning_flags.append("DAP-WF-02 MISSING_MANDATORY_DATA")
    if stale_dynamic:
        warning_flags.append("DAP-WF-03 STALE_DYNAMIC_DATA")
    if any(item.get("source_quality") == 0.5 for item in active_items if item.get("available")):
        warning_flags.append("DAP-WF-04 PROXY_USED")
    if integrity_issues:
        warning_flags.append("DAP-WF-06 INTEGRITY_CHECK_FAILED")
    if role_status != "RESOLVED":
        warning_flags.append("DAP-WF-10 PREMATCH_ROLE_UNRESOLVED")

    critical_integrity_failure = any(
        str(issue.get("severity") or "").upper() == "CRITICAL"
        for issue in integrity_issues
    )
    if (
        missing_critical
        or critical_conflicts
        or critical_integrity_failure
        or role_status != "RESOLVED"
        or fdc < 70
    ):
        gate = DapGate.FAIL
    elif missing_mandatory or fdc < 85:
        gate = DapGate.LIMITED
    elif fdc < 95 or warning_flags:
        gate = DapGate.WARNING
    else:
        gate = DapGate.PASS

    warning_flags = sorted(set(warning_flags)) or ["NONE"]
    match_id = fixture.get("match_id") or stable_match_id(fixture)
    input_snapshot_id = "SNAP-" + uuid.uuid4().hex.upper()
    output_contract_version_id = "DAP-OC-" + uuid.uuid4().hex.upper()
    data_collection_log_id = "DCL-" + uuid.uuid4().hex.upper()
    decision_trace_id = "TRACE-" + uuid.uuid4().hex.upper()
    handover = "READY FOR ENGINE 1" if gate != DapGate.FAIL else "STOP"

    facts_by_id = {
        item["id"]: {
            "label": item["label"],
            "value": item.get("value"),
            "classification": item["classification"],
            "available": item.get("available"),
            "evidence": item.get("evidence") or [],
        }
        for item in active_items
    }
    immutable_facts = {
        "fixture": deepcopy(fixture),
        "items": facts_by_id,
        "engine_input": deepcopy(engine_input or {}),
    }
    contract = {
        "match_id": match_id,
        "input_snapshot_id": input_snapshot_id,
        "data_cutoff_timestamp": collected_at,
        "timezone": "UTC",
        "model_version": MODEL_VERSION,
        "dap_version_id": DAP_VERSION,
        "output_contract_version_id": output_contract_version_id,
        "epl_weights_version": EPL_WEIGHTS_VERSION,
        "status_dap": gate.value,
        "dc": dc,
        "sc": sc,
        "df": df,
        "di": di,
        "fdc": fdc,
        "data_integrity_check": "FAIL" if critical_integrity_failure else "WARNING" if integrity_issues else "PASS",
        "integrity_issues": integrity_issues,
        "warning_flags": warning_flags,
        "missing_critical": missing_critical,
        "missing_mandatory": missing_mandatory,
        "immutable_facts_package": immutable_facts,
        "source_register": deepcopy(source_register or []),
        "data_collection_log_id": data_collection_log_id,
        "active_conditional_data": [
            item["id"]
            for item in active_items
            if item["classification"] == "CONDITIONAL"
        ],
        "missing_data_proxy": [
            item["id"] for item in active_items if not item.get("available")
        ],
        "source_priority_exceptions": [],
        "dynamic_refresh_status": deepcopy(dynamic_refresh_status),
        "operational_certification_status": "TECHNICAL PRODUCTION",
        "formal_evidence_status": "NOT PREDICTIVELY CERTIFIED",
        "handover_status": handover,
        "decision_trace_id": decision_trace_id,
        "prematch_role_favourite": role_assignment.get("favourite"),
        "prematch_role_underdog": role_assignment.get("underdog"),
        "role_status": role_status,
        "role_basis": role_assignment.get("basis"),
        "role_source_ids": list(role_assignment.get("source_ids") or []),
        "role_values_home_away": deepcopy(role_assignment.get("values") or {}),
        "role_tie_break_trace": list(role_assignment.get("trace") or []),
        "role_algorithm_version": ROLE_ALGORITHM_VERSION,
        "dap_items": deepcopy(active_items),
    }

    missing_contract_fields = _required_contract_fields_present(contract)
    if missing_contract_fields:
        contract["status_dap"] = DapGate.FAIL.value
        contract["handover_status"] = "STOP"
        contract["warning_flags"] = sorted(
            set(contract["warning_flags"] + ["DAP-WF-09 GOVERNANCE_TRACE_MISSING"])
        )
        contract["contract_missing_fields"] = missing_contract_fields
    else:
        contract["contract_missing_fields"] = []

    contract["contract_hash"] = payload_hash(contract)
    return contract


def verify_contract(contract):
    if not isinstance(contract, dict):
        raise PipelineViolation("DAP collector did not return an Output Contract")
    expected = contract.get("contract_hash")
    unsigned = deepcopy(contract)
    unsigned.pop("contract_hash", None)
    actual = payload_hash(unsigned)
    if not expected or expected != actual:
        raise PipelineViolation("DAP Output Contract hash mismatch")
    missing = _required_contract_fields_present(contract)
    if missing:
        raise PipelineViolation("Incomplete DAP Output Contract: %s" % ", ".join(missing))
    ready = (
        contract.get("status_dap") in {"PASS", "WARNING", "LIMITED"}
        and contract.get("handover_status") == "READY FOR ENGINE 1"
        and not contract.get("missing_critical")
    )
    return ready


class PipelineRepository(object):
    """SQLite audit store and the sole final-analysis commit boundary."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.ensure_schema()

    def _connect(self):
        con = sqlite3.connect(self.db_path, timeout=20)
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=20000")
        return con

    def ensure_schema(self):
        con = self._connect()
        cur = con.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS analyses ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, home_team TEXT, "
            "away_team TEXT, pick TEXT, probability REAL, fair_odds REAL, "
            "bookmaker_odds REAL, value_edge REAL, exact_score TEXT, rating TEXT)"
        )
        columns = {row[1] for row in cur.execute("PRAGMA table_info(analyses)")}
        for name, col_type in [
            ("run_id", "TEXT"),
            ("match_id", "TEXT"),
            ("dap_gate", "TEXT"),
            ("completed_at", "TEXT"),
        ]:
            if name not in columns:
                cur.execute("ALTER TABLE analyses ADD COLUMN %s %s" % (name, col_type))
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_analyses_run_id "
            "ON analyses(run_id) WHERE run_id IS NOT NULL"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS analysis_runs ("
            "run_id TEXT PRIMARY KEY, match_id TEXT NOT NULL, state TEXT NOT NULL, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, dap_gate TEXT, "
            "handover_status TEXT, dap_contract_json TEXT, engine_result_json TEXT, "
            "error TEXT, analysis_id INTEGER, "
            "FOREIGN KEY(analysis_id) REFERENCES analyses(id))"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS analysis_events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, seq INTEGER NOT NULL, "
            "stage TEXT NOT NULL, progress REAL NOT NULL, status TEXT NOT NULL, "
            "message TEXT, created_at TEXT NOT NULL, "
            "UNIQUE(run_id, seq), FOREIGN KEY(run_id) REFERENCES analysis_runs(run_id))"
        )
        con.commit()
        con.close()

    def create_run(self, fixture):
        run_id = "RUN-" + uuid.uuid4().hex.upper()
        match_id = fixture.get("match_id") or stable_match_id(fixture)
        now = utc_now_iso()
        con = self._connect()
        con.execute(
            "INSERT INTO analysis_runs "
            "(run_id,match_id,state,created_at,updated_at) VALUES (?,?,?,?,?)",
            (run_id, match_id, PipelineState.CREATED.value, now, now),
        )
        con.commit()
        con.close()
        return run_id

    def record_event(self, run_id, stage, progress, status, message=""):
        now = utc_now_iso()
        con = self._connect()
        cur = con.cursor()
        seq = cur.execute(
            "SELECT COALESCE(MAX(seq),0)+1 FROM analysis_events WHERE run_id=?",
            (run_id,),
        ).fetchone()[0]
        cur.execute(
            "INSERT INTO analysis_events "
            "(run_id,seq,stage,progress,status,message,created_at) VALUES (?,?,?,?,?,?,?)",
            (run_id, seq, stage, float(progress), status, message, now),
        )
        con.commit()
        con.close()

    def update_run(self, run_id, state, contract=None, result=None, error=None):
        now = utc_now_iso()
        gate = contract.get("status_dap") if contract else None
        handover = contract.get("handover_status") if contract else None
        con = self._connect()
        allowed = {
            PipelineState.CREATED.value: {PipelineState.DAP_RUNNING.value, PipelineState.FAILED.value},
            PipelineState.DAP_RUNNING.value: {
                PipelineState.DAP_BLOCKED.value,
                PipelineState.READY_FOR_ENGINE_1.value,
                PipelineState.FAILED.value,
            },
            PipelineState.READY_FOR_ENGINE_1.value: {
                PipelineState.ENGINES_RUNNING.value,
                PipelineState.FAILED.value,
            },
            PipelineState.ENGINES_RUNNING.value: {
                PipelineState.READY_TO_SAVE.value,
                PipelineState.FAILED.value,
            },
            PipelineState.READY_TO_SAVE.value: {PipelineState.FAILED.value},
            PipelineState.DAP_BLOCKED.value: {PipelineState.FAILED.value},
            PipelineState.COMPLETED.value: set(),
            PipelineState.FAILED.value: set(),
        }
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT state FROM analysis_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if not row:
                raise PipelineViolation("Unknown analysis run")
            current = row[0]
            if state != current and state not in allowed.get(current, set()):
                raise PipelineViolation(
                    "Illegal pipeline transition %s -> %s" % (current, state)
                )
            con.execute(
                "UPDATE analysis_runs SET state=?,updated_at=?,match_id=COALESCE(?,match_id),dap_gate=COALESCE(?,dap_gate),"
                "handover_status=COALESCE(?,handover_status),"
                "dap_contract_json=COALESCE(?,dap_contract_json),"
                "engine_result_json=COALESCE(?,engine_result_json),error=? WHERE run_id=?",
                (
                    state,
                    now,
                    contract.get("match_id") if contract else None,
                    gate,
                    handover,
                    canonical_json(contract) if contract is not None else None,
                    canonical_json(result) if result is not None else None,
                    error,
                    run_id,
                ),
            )
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def finalize_analysis(self, run_id, fixture, contract, result):
        """Commit one final result only from READY_TO_SAVE, atomically and idempotently."""

        if not verify_contract(contract):
            raise PipelineViolation("Final save blocked: DAP is not READY FOR ENGINE 1")
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT state,analysis_id,dap_contract_json,engine_result_json "
                "FROM analysis_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if not row:
                raise PipelineViolation("Unknown analysis run")
            if row[1] is not None:
                con.commit()
                return row[1]
            if row[0] != PipelineState.READY_TO_SAVE.value:
                raise PipelineViolation(
                    "Final save blocked in state %s; expected READY_TO_SAVE" % row[0]
                )
            if not row[2] or canonical_json(json.loads(row[2])) != canonical_json(contract):
                raise PipelineViolation("Final save blocked: contract differs from READY_TO_SAVE snapshot")
            if not row[3] or canonical_json(json.loads(row[3])) != canonical_json(result):
                raise PipelineViolation("Final save blocked: engine result differs from READY_TO_SAVE snapshot")
            now = utc_now_iso()
            cur = con.cursor()
            cur.execute(
                "INSERT INTO analyses "
                "(created_at,home_team,away_team,pick,probability,fair_odds,bookmaker_odds,"
                "value_edge,exact_score,rating,run_id,match_id,dap_gate,completed_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    fixture.get("kickoff") or fixture.get("date") or now,
                    fixture.get("home") or "",
                    fixture.get("away") or "",
                    result.get("pick") or "",
                    float(result.get("prob") or 0),
                    float(result.get("fair") or 0),
                    float(result.get("bookmaker_odds") or 0),
                    float(result.get("edge") or 0),
                    result.get("control") or "",
                    result.get("rating") or "",
                    run_id,
                    contract.get("match_id"),
                    contract.get("status_dap"),
                    now,
                ),
            )
            analysis_id = cur.lastrowid
            cur.execute(
                "UPDATE analysis_runs SET state=?,updated_at=?,analysis_id=?,"
                "engine_result_json=?,error=NULL WHERE run_id=?",
                (
                    PipelineState.COMPLETED.value,
                    now,
                    analysis_id,
                    canonical_json(result),
                    run_id,
                ),
            )
            seq = cur.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM analysis_events WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
            cur.execute(
                "INSERT INTO analysis_events "
                "(run_id,seq,stage,progress,status,message,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    run_id,
                    seq,
                    "PERSISTENCE",
                    100.0,
                    "COMPLETED",
                    "Wynik zapisany po ukończeniu DAP i silników",
                    now,
                ),
            )
            con.commit()
            return analysis_id
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def get_run(self, run_id):
        con = self._connect()
        con.row_factory = sqlite3.Row
        run = con.execute(
            "SELECT * FROM analysis_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        events = con.execute(
            "SELECT seq,stage,progress,status,message,created_at "
            "FROM analysis_events WHERE run_id=? ORDER BY seq",
            (run_id,),
        ).fetchall()
        con.close()
        if not run:
            return None
        data = dict(run)
        for key in ("dap_contract_json", "engine_result_json"):
            raw = data.pop(key, None)
            data[key[:-5]] = json.loads(raw) if raw else None
        data["events"] = [dict(row) for row in events]
        return data


class PipelineRunner(object):
    """The only authorized execution path from DAP collection to final save."""

    def __init__(self, repository, dap_collector, engine_runner):
        self.repository = repository
        self.dap_collector = dap_collector
        self.engine_runner = engine_runner

    def _event(self, run_id, stage, progress, status, message=""):
        self.repository.record_event(run_id, stage, progress, status, message)

    @staticmethod
    def _validate_engine_result(result):
        required = {
            "pick",
            "prob",
            "fair",
            "edge",
            "rating",
            "control",
            "value",
            "chaos",
        }
        if not isinstance(result, dict):
            raise PipelineViolation("Engine runner returned a non-object result")
        missing = sorted(required.difference(result))
        if missing:
            raise PipelineViolation("Incomplete engine result: %s" % ", ".join(missing))

    def run(self, fixture):
        fixture = deepcopy(fixture)
        fixture["match_id"] = fixture.get("match_id") or stable_match_id(fixture)
        run_id = self.repository.create_run(fixture)
        contract = None
        result = None
        try:
            self.repository.update_run(run_id, PipelineState.DAP_RUNNING.value)
            self._event(run_id, "DAP", 0, "RUNNING", "Rozpoczęto kompletowanie DAP")

            def dap_progress(stage, progress, status, message=""):
                self._event(run_id, stage, progress, status, message)

            contract = self.dap_collector(fixture, dap_progress)
            ready = verify_contract(contract)
            self.repository.update_run(
                run_id,
                PipelineState.READY_FOR_ENGINE_1.value if ready else PipelineState.DAP_BLOCKED.value,
                contract=contract,
            )
            self._event(
                run_id,
                "DAP",
                100,
                contract.get("status_dap"),
                contract.get("handover_status"),
            )
            if not ready:
                return self.repository.get_run(run_id)

            self.repository.update_run(
                run_id, PipelineState.ENGINES_RUNNING.value, contract=contract
            )
            self._event(
                run_id,
                "ENGINES",
                0,
                "RUNNING",
                "DAP zamknięty; uruchomiono silniki",
            )
            frozen_for_engine = json.loads(canonical_json(contract))
            result = self.engine_runner(frozen_for_engine, lambda *args: self._event(run_id, *args))
            self._validate_engine_result(result)
            verify_contract(contract)
            self._event(run_id, "ENGINES", 100, "COMPLETED", "Silniki zakończone")

            self.repository.update_run(
                run_id,
                PipelineState.READY_TO_SAVE.value,
                contract=contract,
                result=result,
            )
            self._event(
                run_id,
                "PERSISTENCE",
                0,
                "RUNNING",
                "Wynik gotowy do zapisu transakcyjnego",
            )
            self.repository.finalize_analysis(run_id, fixture, contract, result)
            return self.repository.get_run(run_id)
        except Exception as exc:
            self.repository.update_run(
                run_id,
                PipelineState.FAILED.value,
                contract=contract,
                result=result,
                error="%s: %s" % (exc.__class__.__name__, exc),
            )
            self._event(run_id, "PIPELINE", 100, "FAILED", str(exc))
            return self.repository.get_run(run_id)
