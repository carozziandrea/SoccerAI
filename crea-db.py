"""Create the empty SQLite database schema required by SoccerAI."""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from database import prepare_database


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).resolve().parent / "calcio.db",
        help="Percorso del database SQLite",
    )
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(args.db)) as conn:
        prepare_database(conn)
        conn.commit()
    print(f"Schema SoccerAI pronto: {args.db.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
