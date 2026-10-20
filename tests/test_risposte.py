"""Tests for deterministic and model-assisted answer formatting."""

import unittest

import pandas as pd

from risposte import formula_risposta


class FakeLLM:
    def __init__(self, answer="Rafael Leão ha segnato 3 gol."):
        self.answer = answer
        self.prompt = None

    def invoke(self, prompt):
        self.prompt = prompt
        return self.answer


class AnswerFormattingTests(unittest.TestCase):
    def test_empty_results_have_clear_answer(self):
        answer = formula_risposta(None, "Gol di Yildiz?", pd.DataFrame())
        self.assertEqual(answer, "Non sono stati trovati risultati nel database.")

    def test_numeric_count_is_formatted_without_llm(self):
        answer = formula_risposta(None, "Quanti gol?", pd.DataFrame({"gol": [3]}))
        self.assertEqual(answer, "Il risultato è 3 gol.")

    def test_first_goal_answer_includes_match_date_and_round(self):
        data = pd.DataFrame([{
            "calciatore": "Kenan Yildiz",
            "data_partita": "2023-12-23",
            "stagione": "2023/2024",
            "giornata": 17,
            "squadra_casa": "Frosinone",
            "squadra_trasferta": "Juventus",
            "minuto": 12,
        }])
        answer = formula_risposta(None, "Prima partita di Yildiz", data)
        self.assertEqual(
            answer,
            "Kenan Yildiz ha segnato per la prima volta in Serie A in "
            "Frosinone-Juventus, il 23/12/2023 (17ª giornata della stagione "
            "2023/2024; gol al 12º).",
        )

    def test_tabular_summary_is_grounded_in_sql_rows(self):
        llm = FakeLLM()
        data = pd.DataFrame([{"calciatore": "Rafael Leão", "gol": 3}])
        answer = formula_risposta(llm, "Riassumi", data)
        self.assertEqual(answer, "Rafael Leão ha segnato 3 gol.")
        self.assertIn('"calciatore":"Rafael Leão"', llm.prompt)
        self.assertIn('"gol":3', llm.prompt)


if __name__ == "__main__":
    unittest.main()
