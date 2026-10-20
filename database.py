"""Shared SQLite schema creation and migration helpers."""

import sqlite3


def prepare_database(conn: sqlite3.Connection) -> None:
    """Create the application schema and add columns missing from older databases."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS partite (
            id_partita INTEGER PRIMARY KEY AUTOINCREMENT,
            giornata INTEGER,
            squadra_casa TEXT,
            squadra_trasferta TEXT,
            stagione TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS marcatori (
            id_marcatore INTEGER PRIMARY KEY AUTOINCREMENT,
            id_partita INTEGER,
            calciatore TEXT,
            minuto INTEGER,
            FOREIGN KEY(id_partita) REFERENCES partite(id_partita)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS giocatori (
            id_giocatore TEXT PRIMARY KEY,
            nome TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS alias_calciatori (
            id_giocatore TEXT NOT NULL REFERENCES giocatori(id_giocatore),
            alias TEXT NOT NULL,
            alias_normalizzato TEXT NOT NULL,
            PRIMARY KEY (id_giocatore, alias_normalizzato)
        )"""
    )
    match_columns = {row[1] for row in conn.execute("PRAGMA table_info(partite)")}
    for name, sql_type in (("data_partita", "TEXT"), ("espn_id", "TEXT")):
        if name not in match_columns:
            conn.execute(f"ALTER TABLE partite ADD COLUMN {name} {sql_type}")
    goal_columns = {row[1] for row in conn.execute("PRAGMA table_info(marcatori)")}
    for name, sql_type in (
        ("squadra", "TEXT"),
        ("tipo", "TEXT"),
        ("espn_id", "TEXT"),
        ("id_giocatore", "TEXT"),
    ):
        if name not in goal_columns:
            conn.execute(f"ALTER TABLE marcatori ADD COLUMN {name} {sql_type}")
