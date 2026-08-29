from copy import deepcopy
import os
import sqlite3
import tempfile
import unittest

from qe_pipeline import (
    PipelineRepository,
    PipelineRunner,
    PipelineState,
    PipelineViolation,
    build_dap_output_contract,
    make_dap_item,
    verify_contract,
)


FIXTURE = {
    "home": "Liverpool",
    "away": "Nottingham Forest",
    "kickoff": "2026-08-29T11:30:00Z",
    "competition": "Premier League",
    "phase": "Regular season",
    "league_code": "eng.1",
    "status": "SCHEDULED",
    "venue_name": "Anfield",
    "neutral": False,
}


def contract(missing_critical=False, missing_mandatory=False):
    critical = ["D01", "D02", "D03", "D04", "D-STATUS", "D09"]
    items = []
    for item_id in critical:
        available = not (missing_critical and item_id == "D09")
        items.append(
            make_dap_item(
                item_id,
                item_id,
                "CRITICAL",
                value="confirmed" if available else None,
                available=available,
                evidence=[{"source": "Official", "class": "A", "value": "confirmed"}]
                if available
                else [],
                source_quality=0.9 if available else 0,
                freshness=100 if available else 0,
            )
        )
    items.append(
        make_dap_item(
            "D05",
            "Match character",
            "MANDATORY",
            value=None if missing_mandatory else "LEAGUE",
            available=not missing_mandatory,
            evidence=[] if missing_mandatory else [{"source": "Official", "class": "A", "value": "LEAGUE"}],
            source_quality=0 if missing_mandatory else 0.9,
            freshness=0 if missing_mandatory else 100,
        )
    )
    return build_dap_output_contract(
        fixture=FIXTURE,
        items=items,
        source_register=[{"source": "Official", "status": "SUCCESS"}],
        role_assignment={
            "status": "RESOLVED",
            "favourite": "Liverpool",
            "underdog": "Nottingham Forest",
            "basis": "R5_HOME_ADVANTAGE",
            "source_ids": ["DAP-D04"],
            "values": {"home": "CLASSICAL", "away": "AWAY"},
            "trace": ["R5 classical home advantage"],
        },
        engine_input={"home_team": "Liverpool", "away_team": "Nottingham Forest"},
    )


def engine_result():
    return {
        "pick": "1X",
        "prob": 62,
        "fair": 1.61,
        "bookmaker_odds": 0,
        "edge": 0,
        "rating": "BRAK DANYCH RYNKOWYCH",
        "control": "1:0",
        "value": "2:1",
        "chaos": "2:2",
    }


class PipelineContractTests(unittest.TestCase):
    def test_missing_critical_data_stops_handover(self):
        output = contract(missing_critical=True)
        self.assertEqual(output["status_dap"], "FAIL")
        self.assertEqual(output["handover_status"], "STOP")
        self.assertFalse(verify_contract(output))

    def test_missing_mandatory_data_can_be_limited_but_ready(self):
        output = contract(missing_mandatory=True)
        self.assertEqual(output["status_dap"], "LIMITED")
        self.assertEqual(output["handover_status"], "READY FOR ENGINE 1")
        self.assertTrue(verify_contract(output))

    def test_contract_tampering_is_rejected(self):
        output = contract()
        output["immutable_facts_package"]["engine_input"]["home_team"] = "Tampered"
        with self.assertRaises(PipelineViolation):
            verify_contract(output)


class PipelineRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp.name, "pipeline.sqlite")
        self.repository = PipelineRepository(self.db_path)

    def tearDown(self):
        self.temp.cleanup()

    def count_analyses(self):
        con = sqlite3.connect(self.db_path)
        count = con.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        con.close()
        return count

    def test_blocked_dap_never_starts_engine_or_saves_result(self):
        calls = []

        def collector(_fixture, _progress):
            return contract(missing_critical=True)

        def engine(_contract, _progress):
            calls.append("engine")
            return engine_result()

        run = PipelineRunner(self.repository, collector, engine).run(FIXTURE)
        self.assertEqual(run["state"], PipelineState.DAP_BLOCKED.value)
        self.assertEqual(calls, [])
        self.assertEqual(self.count_analyses(), 0)
        self.assertFalse(any(event["stage"] == "ENGINES" for event in run["events"]))

    def test_ready_dap_runs_engine_then_saves_once(self):
        calls = []

        def collector(_fixture, progress):
            progress("DAP.TEST", 50, "RUNNING", "test")
            return contract()

        def engine(_contract, progress):
            calls.append("engine")
            progress("ENGINE.LEGACY", 50, "RUNNING", "test")
            return engine_result()

        run = PipelineRunner(self.repository, collector, engine).run(FIXTURE)
        self.assertEqual(run["state"], PipelineState.COMPLETED.value)
        self.assertEqual(calls, ["engine"])
        self.assertEqual(self.count_analyses(), 1)
        stages = [event["stage"] for event in run["events"]]
        self.assertLess(stages.index("DAP"), stages.index("ENGINES"))
        self.assertLess(stages.index("ENGINES"), stages.index("PERSISTENCE"))

        analysis_id = self.repository.finalize_analysis(
            run["run_id"], FIXTURE, run["dap_contract"], run["engine_result"]
        )
        self.assertEqual(analysis_id, run["analysis_id"])
        self.assertEqual(self.count_analyses(), 1)

    def test_engine_failure_never_saves_partial_result(self):
        def collector(_fixture, _progress):
            return contract()

        def engine(_contract, _progress):
            raise RuntimeError("engine failed")

        run = PipelineRunner(self.repository, collector, engine).run(FIXTURE)
        self.assertEqual(run["state"], PipelineState.FAILED.value)
        self.assertEqual(self.count_analyses(), 0)

    def test_repository_rejects_direct_save_before_ready_to_save(self):
        output = contract()
        run_id = self.repository.create_run(FIXTURE)
        with self.assertRaises(PipelineViolation):
            self.repository.finalize_analysis(run_id, FIXTURE, output, engine_result())
        self.assertEqual(self.count_analyses(), 0)

    def test_repository_rejects_state_machine_jump(self):
        run_id = self.repository.create_run(FIXTURE)
        with self.assertRaises(PipelineViolation):
            self.repository.update_run(run_id, PipelineState.ENGINES_RUNNING.value)
        self.assertEqual(
            self.repository.get_run(run_id)["state"], PipelineState.CREATED.value
        )


if __name__ == "__main__":
    unittest.main()
