"""Tests for the SQLite schema used by imports and application queries."""

import sqlite3
import unittest
from contextlib import closing

from database import prepare_database


class DatabaseSchemaTests(unittest.TestCase):
    def test_new_database_contains_all_application_tables_and_columns(self):
        with closing(sqlite3.connect(":memory:")) as conn:
            prepare_database(conn)
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            self.assertTrue({"partite", "marcatori", "giocatori", "alias_calciatori"} <= tables)
            match_columns = {row[1] for row in conn.execute("PRAGMA table_info(partite)")}
            scorer_columns = {row[1] for row in conn.execute("PRAGMA table_info(marcatori)")}
            self.assertTrue({"stagione", "data_partita", "espn_id"} <= match_columns)
            self.assertTrue({"tipo", "squadra", "id_giocatore", "espn_id"} <= scorer_columns)

    def test_migration_is_repeatable(self):
        with closing(sqlite3.connect(":memory:")) as conn:
            prepare_database(conn)
            prepare_database(conn)
            columns = [row[1] for row in conn.execute("PRAGMA table_info(marcatori)")]
            self.assertEqual(len(columns), len(set(columns)))

    def test_migration_adds_columns_to_legacy_schema(self):
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.executescript(
                "CREATE TABLE partite (id_partita INTEGER PRIMARY KEY, giornata INTEGER, "
                "squadra_casa TEXT, squadra_trasferta TEXT, stagione TEXT);"
                "CREATE TABLE marcatori (id_marcatore INTEGER PRIMARY KEY, id_partita INTEGER, "
                "calciatore TEXT, minuto INTEGER);"
            )
            prepare_database(conn)
            match_columns = {row[1] for row in conn.execute("PRAGMA table_info(partite)")}
            scorer_columns = {row[1] for row in conn.execute("PRAGMA table_info(marcatori)")}
            self.assertTrue({"data_partita", "espn_id"} <= match_columns)
            self.assertTrue({"calciatore", "minuto", "squadra", "tipo", "id_giocatore"} <= scorer_columns)


if __name__ == "__main__":
    unittest.main()
