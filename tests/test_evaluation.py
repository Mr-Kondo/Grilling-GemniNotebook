import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("evaluate", Path(__file__).resolve().parents[1] / "scripts/evaluate_knowledge.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


class EvaluationTests(unittest.TestCase):
    def test_citation_requires_exact_nonempty_original(self):
        corpus = {"a": "original quote"}
        good = {"source": "a", "quote": "original"}
        self.assertTrue(evaluation.citation_valid(good, "a", corpus))
        for source, quote in (("b", "original"), ("a", ""), ("a", "invented")):
            self.assertFalse(evaluation.citation_valid({"source": source, "quote": quote}, "a", corpus))

    def test_malformed_response_stops_without_repair(self):
        for response in ('```json\n{}\n```', '{}', '[]', '{"answer":1}'):
            with self.assertRaises((ValueError, TypeError)):
                evaluation.parse_answer(response)

    def test_preparation_freezes_identical_sources_and_condition_order(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pilot"
            evaluation.prepare(path)
            import json
            manifest = json.loads((path / "manifest.json").read_text())
            self.assertEqual([r["id"] for r in manifest["runs"]],
                             ["T1-A", "T1-B", "T2-B", "T2-A", "T3-A", "T3-B", "T4-B", "T4-A"])
            for task, _, _ in evaluation.TASKS:
                a = (path / f"{task}-A.prompt.md").read_text()
                b = (path / f"{task}-B.prompt.md").read_text()
                self.assertTrue(b.startswith(a))
                self.assertNotIn("--- knowledge/", a)
            with self.assertRaises(FileExistsError):
                evaluation.prepare(path)

    def test_output_must_stay_under_feedback(self):
        with self.assertRaises(ValueError):
            evaluation.output_dir(evaluation.ROOT / "outside")

    def test_started_run_cannot_launch_again(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pilot"
            evaluation.prepare(path)
            (path / "started").touch()
            with patch.object(evaluation.subprocess, "run") as model:
                with self.assertRaises(FileExistsError):
                    evaluation.run(path)
                model.assert_not_called()

    def test_changed_prompt_stops_before_any_model_call(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pilot"
            evaluation.prepare(path)
            (path / "T1-A.prompt.md").write_text("changed")
            with patch.object(evaluation.subprocess, "run") as model:
                with self.assertRaises(ValueError):
                    evaluation.run(path)
                model.assert_not_called()

    def test_changed_corpus_stops_before_any_model_call(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pilot"
            evaluation.prepare(path)
            (path / "corpus.json").write_text('{}')
            with patch.object(evaluation.subprocess, "run") as model:
                with self.assertRaisesRegex(ValueError, "Corpus changed"):
                    evaluation.run(path)
                model.assert_not_called()
