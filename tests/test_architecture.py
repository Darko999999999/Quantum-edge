import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GlobalBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_source = (ROOT / "main.py").read_text(encoding="utf-8")
        cls.pipeline_source = (ROOT / "qe_pipeline.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.main_source)

    def function_calls(self):
        calls = {}
        for node in self.tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        names.append(child.func.id)
                    elif isinstance(child.func, ast.Attribute):
                        names.append(child.func.attr)
            calls[node.name] = names
        return calls

    def test_main_has_no_direct_final_analysis_insert(self):
        self.assertNotIn("INSERT INTO analyses", self.main_source)
        self.assertEqual(self.pipeline_source.count("INSERT INTO analyses"), 1)

    def test_model_has_one_authorized_caller(self):
        callers = [
            name for name, calls in self.function_calls().items() if "model" in calls
        ]
        self.assertEqual(callers, ["run_legacy_engine_from_contract"])

    def test_every_analysis_entry_uses_pipeline_runner(self):
        calls = self.function_calls()
        self.assertIn("run", calls["analyze"])
        self.assertIn("run", calls["persist_selected_matches"])
        self.assertNotIn("model", calls["analyze"])
        self.assertNotIn("model", calls["select_scan"])
        self.assertNotIn("persist_selected_matches", calls["select_scan"])

    def test_no_embedded_odds_key_or_fake_market_signal(self):
        self.assertNotIn("ODDS_API_KEY", self.main_source)
        self.assertNotIn("Steam detected", self.main_source)
        self.assertNotIn("No Trap", self.main_source)


if __name__ == "__main__":
    unittest.main()
