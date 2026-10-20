"""Tests for SQL validation, player queries, coverage, and name normalization."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import text

from query_utils import (
    apri_db_sola_lettura,
    crea_engine_sqlite,
    genera_ed_esegui_query,
    pulisci_e_valida_sql,
)
from nomi import normalizza_nome
from query_templates import query_predefinita, riepilogo_copertura, stagione_non_coperta


class FakeChain:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.requests = []

    def invoke(self, values):
        self.requests.append(values["question"])
        return next(self.answers)


class QueryUtilsTests(unittest.TestCase):
    def setUp(self):
        workspace = Path(__file__).resolve().parent.parent
        self.temp_dir = tempfile.TemporaryDirectory(dir=workspace)
        self.db_path = Path(self.temp_dir.name) / "calcio.db"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE partite (
                    id_partita INTEGER PRIMARY KEY,
                    stagione TEXT,
                    giornata INTEGER,
                    data_partita TEXT,
                    squadra_casa TEXT,
                    squadra_trasferta TEXT
                );
                CREATE TABLE marcatori (
                    id_marcatore INTEGER PRIMARY KEY,
                    id_partita INTEGER,
                    calciatore TEXT,
                    tipo TEXT,
                    squadra TEXT,
                    id_giocatore TEXT,
                    minuto INTEGER,
                    FOREIGN KEY(id_partita) REFERENCES partite(id_partita)
                );
                CREATE TABLE giocatori (id_giocatore TEXT PRIMARY KEY, nome TEXT NOT NULL);
                CREATE TABLE alias_calciatori (
                    id_giocatore TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    alias_normalizzato TEXT NOT NULL,
                    PRIMARY KEY(id_giocatore, alias_normalizzato)
                );
                INSERT INTO giocatori VALUES ('yildiz-espn', 'Kenan Yildiz');
                INSERT INTO giocatori VALUES ('leao-espn', 'Rafael Leão');
                INSERT INTO alias_calciatori VALUES ('yildiz-espn', 'Kenan Yildiz', 'kenanyildiz');
                INSERT INTO alias_calciatori VALUES ('leao-espn', 'Rafael Leão', 'rafaelleao');
                INSERT INTO partite VALUES (3, '2023/2024', 17, '2023-12-23', 'Frosinone', 'Juventus');
                INSERT INTO partite VALUES (1, '2025/2026', 1, '2025-08-24', 'Juventus', 'Como');
                INSERT INTO partite VALUES (2, '2024/2025', 1, '2024-08-18', 'Juventus', 'Como');
                INSERT INTO marcatori VALUES (6, 3, 'Kenan Yildiz', 'Goal', 'Juventus', 'yildiz-espn', 12);
                INSERT INTO marcatori VALUES (1, 1, 'Kenan Yildiz', 'Goal', 'Juventus', 'yildiz-espn', 20);
                INSERT INTO marcatori VALUES (2, 1, 'Kenan Yildiz', 'Penalty - Scored', 'Juventus', 'yildiz-espn', 40);
                INSERT INTO marcatori VALUES (3, 1, 'Kenan Yildiz', 'Own Goal', 'Juventus', 'yildiz-espn', 60);
                INSERT INTO marcatori VALUES (4, 2, 'Kenan Yildiz', 'Goal', 'Juventus', 'yildiz-espn', 12);
                INSERT INTO marcatori VALUES (5, 1, 'Rafael Leão', 'Goal', 'Milan', 'leao-espn', 50);
                """
            )
        finally:
            conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_rejects_non_select_sql(self):
        with self.assertRaises(ValueError):
            pulisci_e_valida_sql("DELETE FROM marcatori")

    def test_read_only_connection_blocks_writes(self):
        with apri_db_sola_lettura(self.db_path) as conn:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE marcatori SET calciatore = 'altro'")

    def test_retries_invalid_season_query_and_counts_goal_types(self):
        bad_query = (
            "SELECT COUNT(*) FROM marcatori "
            "WHERE calciatore LIKE '%Yildiz%' AND stagione = '2025/2026'"
        )
        good_query = (
            "SELECT COUNT(*) FROM marcatori AS m "
            "JOIN partite AS p ON p.id_partita = m.id_partita "
            "WHERE m.calciatore LIKE '%Yildiz%' AND p.stagione = '2025/2026' "
            "AND (m.tipo LIKE 'Goal%' OR m.tipo = 'Penalty - Scored')"
        )
        chain = FakeChain([bad_query, good_query])

        query, results = genera_ed_esegui_query(
            chain, "Quanti gol ha fatto Yildiz nel 2025/26?", self.db_path
        )

        self.assertEqual(query, good_query)
        self.assertEqual(results.iloc[0, 0], 2)
        self.assertEqual(len(chain.requests), 2)
        self.assertIn("no such column: stagione", chain.requests[1])

    def test_season_is_on_matches_not_scorers(self):
        conn = sqlite3.connect(self.db_path)
        try:
            scorer_columns = {row[1] for row in conn.execute("PRAGMA table_info(marcatori)")}
            match_columns = {row[1] for row in conn.execute("PRAGMA table_info(partite)")}
        finally:
            conn.close()
        self.assertNotIn("stagione", scorer_columns)
        self.assertIn("stagione", match_columns)

    def test_normalizes_accents_case_punctuation_and_special_letters(self):
        self.assertEqual(normalizza_nome("Rafael Leão"), normalizza_nome("RAFAEL LEAO"))
        self.assertEqual(normalizza_nome("Yıldız"), normalizza_nome("Yildiz"))
        self.assertEqual(normalizza_nome("O’Connor-Sørloth"), normalizza_nome("oconnor sorloth"))

    def test_sqlite_function_is_available_on_both_connections(self):
        with apri_db_sola_lettura(self.db_path) as conn:
            result = conn.execute(
                "SELECT calciatore FROM marcatori "
                "WHERE normalizza(calciatore) LIKE '%' || normalizza(?) || '%'",
                ("RAFAEL LEAO",),
            ).fetchone()
        self.assertEqual(result[0], "Rafael Leão")

        engine = crea_engine_sqlite(f"sqlite:///{self.db_path.as_posix()}")
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT normalizza(:nome)"), {"nome": "Yıldız"}
                ).scalar_one()
            self.assertEqual(result, "yildiz")
        finally:
            engine.dispose()

    def test_predefined_player_query_resolves_alias_and_season(self):
        predefined = query_predefinita(
            "Quanti gol ha fatto YILDIZ nella stagione 2025/26?", self.db_path
        )
        self.assertIsNotNone(predefined)
        self.assertIsNone(predefined.messaggio)
        self.assertEqual(predefined.risultati.iloc[0]["gol"], 2)
        self.assertEqual(predefined.parametri, ("yildiz-espn", "2025/2026"))

    def test_predefined_first_scoring_match_resolves_short_alias_and_date(self):
        predefined = query_predefinita(
            "Qual è la prima partita in cui ha segnato Yildiz?", self.db_path
        )

        self.assertIsNotNone(predefined)
        self.assertIsNone(predefined.messaggio)
        self.assertEqual(predefined.parametri, ("yildiz-espn",))
        self.assertEqual(predefined.risultati.iloc[0]["data_partita"], "2023-12-23")
        self.assertEqual(predefined.risultati.iloc[0]["stagione"], "2023/2024")
        self.assertIn("ORDER BY p.data_partita ASC", predefined.sql)
        self.assertNotIn("alias_normalizzato =", predefined.sql)

    def test_first_scoring_match_accepts_player_before_verb(self):
        predefined = query_predefinita(
            "Qual è la prima partita in cui Yildiz ha segnato?", self.db_path
        )

        self.assertIsNotNone(predefined)
        self.assertIsNone(predefined.messaggio)
        self.assertEqual(predefined.risultati.iloc[0]["data_partita"], "2023-12-23")

    def test_coverage_reports_missing_or_partial_seasons(self):
        self.assertEqual(
            stagione_non_coperta("Gol di Yildiz nel 2026/27", self.db_path),
            "2026/2027",
        )
        self.assertEqual(
            stagione_non_coperta("Gol di Yildiz nel 2025/26", self.db_path),
            "2025/2026 (copertura parziale: 1/380 partite)",
        )
        seasons, missing_ids = riepilogo_copertura(self.db_path)
        self.assertEqual(len(seasons), 3)
        self.assertEqual(missing_ids, 0)

    def test_predefined_top_scorers_and_team_totals(self):
        scorers = query_predefinita("Classifica marcatori 2025/26", self.db_path)
        self.assertIsNotNone(scorers)
        self.assertEqual(scorers.risultati.iloc[0]["calciatore"], "Kenan Yildiz")
        self.assertEqual(scorers.risultati.iloc[0]["gol"], 2)

        teams = query_predefinita("Gol per squadra nella stagione 2025/26", self.db_path)
        self.assertIsNotNone(teams)
        self.assertEqual(teams.risultati.iloc[0]["squadra"], "Juventus")
        self.assertEqual(teams.risultati.iloc[0]["gol"], 2)


if __name__ == "__main__":
    unittest.main()
