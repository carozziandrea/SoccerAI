"""Test the curated AI evaluation dataset and its deterministic grading."""

import json
import tempfile
import unittest
from pathlib import Path

from evals.fixture import crea_database_valutazione
from evals.runner import carica_casi, esegui_valutazioni, riepiloga, valuta_caso


class FakeSqlChain:
    def __init__(self, sql: str):
        self.sql = sql

    def invoke(self, _: dict[str, str]) -> str:
        return self.sql


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1]
        )
        self.db_path = Path(self.temp_dir.name) / "evaluation.sqlite"
        crea_database_valutazione(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_offline_regression_cases_pass_against_synthetic_database(self):
        results = esegui_valutazioni(self.db_path)

        self.assertEqual(len(results), 9)
        self.assertTrue(all(item["passed"] for item in results), results)
        self.assertNotIn("generated_sql", riepiloga(results)["by_category"])

    def test_sql_chain_case_grades_actual_database_rows(self):
        case = next(case for case in carica_casi() if case["route"] == "sql_chain")
        chain = FakeSqlChain(
            "SELECT m.tipo, COUNT(*) AS conteggio FROM marcatori m "
            "JOIN partite p ON p.id_partita = m.id_partita "
            "WHERE p.stagione = '2025/2026' GROUP BY m.tipo"
        )

        result = valuta_caso(case, self.db_path, sql_chain=chain)

        self.assertTrue(result["passed"], result)

    def test_sql_chain_case_rejects_non_read_only_generated_query(self):
        case = next(case for case in carica_casi() if case["route"] == "sql_chain")
        result = valuta_caso(case, self.db_path, sql_chain=FakeSqlChain("DELETE FROM marcatori"))

        self.assertFalse(result["passed"])
        self.assertIn("SELECT", result["error"])

    def test_dataset_rejects_duplicate_case_ids(self):
        duplicate_case = {"id": "same", "category": "x", "route": "coverage", "question": "x"}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary_dir:
            cases_path = Path(temporary_dir) / "cases.jsonl"
            cases_path.write_text(
                json.dumps(duplicate_case) + "\n" + json.dumps(duplicate_case) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "id duplicato"):
                carica_casi(cases_path)

    def test_dataset_rejects_missing_required_fields(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary_dir:
            cases_path = Path(temporary_dir) / "cases.jsonl"
            cases_path.write_text('{"id":"incomplete"}\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "campi obbligatori mancanti"):
                carica_casi(cases_path)


if __name__ == "__main__":
    unittest.main()
