"""Create a small, deterministic SQLite database for question evaluations."""

import sqlite3
from contextlib import closing
from pathlib import Path

from database import prepare_database
from nomi import normalizza_nome


def crea_database_valutazione(db_path: Path) -> None:
    """Create synthetic players, matches, and scoring events for offline evaluation."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        prepare_database(conn)
        giocatori = [
            ("yildiz-espn", "Kenan Yildiz"),
            ("leao-espn", "Rafael Leão"),
            ("alex-sandro", "Alex Sandro"),
            ("alexis-saelemaekers", "Alexis Saelemaekers"),
        ]
        conn.executemany("INSERT INTO giocatori VALUES (?, ?)", giocatori)
        conn.executemany(
            "INSERT INTO alias_calciatori VALUES (?, ?, ?)",
            [(player_id, name, normalizza_nome(name)) for player_id, name in giocatori],
        )
        conn.executemany(
            "INSERT INTO partite "
            "(id_partita, stagione, giornata, data_partita, squadra_casa, squadra_trasferta) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "2023/2024", 17, "2023-12-23", "Frosinone", "Juventus"),
                (2, "2024/2025", 1, "2024-08-18", "Juventus", "Como"),
                (3, "2025/2026", 1, "2025-08-24", "Juventus", "Como"),
            ],
        )
        conn.executemany(
            "INSERT INTO marcatori "
            "(id_marcatore, id_partita, calciatore, tipo, squadra, id_giocatore, minuto) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, 1, "Kenan Yildiz", "Goal", "Juventus", "yildiz-espn", 12),
                (2, 2, "Kenan Yildiz", "Goal", "Juventus", "yildiz-espn", 12),
                (3, 3, "Kenan Yildiz", "Goal", "Juventus", "yildiz-espn", 20),
                (4, 3, "Kenan Yildiz", "Penalty - Scored", "Juventus", "yildiz-espn", 40),
                (5, 3, "Kenan Yildiz", "Own Goal", "Juventus", "yildiz-espn", 60),
                (6, 3, "Rafael Leão", "Goal", "Milan", "leao-espn", 50),
            ],
        )
        conn.commit()
