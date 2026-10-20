"""Importa i marcatori della Serie A 2021/22–2025/26 dal feed pubblico ESPN.

Il feed ESPN non è un'API documentata ufficialmente e può cambiare struttura.
I JSON scaricati sono messi in cache per non ripetere le richieste.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from database import prepare_database
from nomi import normalizza_nome


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "calcio.db"
CACHE_DIR = ROOT / ".cache" / "espn-serie-a"
API_ROOT = "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1"
SEASONS = tuple(range(2021, 2026))
USER_AGENT = "SoccerAI/1.0 (local football statistics importer)"


def fetch_json(url: str, cache_file: Path, pause: float) -> dict:
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            with urlopen(request, timeout=30) as response:
                payload = response.read()
            data = json.loads(payload.decode("utf-8"))
            cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            time.sleep(pause)
            return data
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if isinstance(exc, HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(min(2**attempt, 20))
    raise RuntimeError(f"Richiesta ESPN fallita ({url}): {last_error}") from last_error


def season_calendar(year: int, pause: float) -> list[str]:
    start = f"{year}0701"
    url = f"{API_ROOT}/scoreboard?{urlencode({'dates': start})}"
    data = fetch_json(url, CACHE_DIR / str(year) / f"calendar-{start}.json", pause)
    league = (data.get("leagues") or [{}])[0]
    dates = league.get("calendar") or []
    if not dates:
        raise RuntimeError(
            f"ESPN non ha restituito il calendario della stagione {year}/{year + 1}. "
            "Il feed potrebbe non offrire più questo storico."
        )
    normalized = set()
    for value in dates:
        try:
            normalized.add(datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y%m%d"))
        except ValueError:
            continue
    return sorted(normalized)


def get_schedule(year: int, pause: float) -> list[dict]:
    events: dict[str, dict] = {}
    for game_date in season_calendar(year, pause):
        url = f"{API_ROOT}/scoreboard?{urlencode({'dates': game_date})}"
        data = fetch_json(url, CACHE_DIR / str(year) / f"scoreboard-{game_date}.json", pause)
        for event in data.get("events", []):
            competition = (event.get("competitions") or [{}])[0]
            status = competition.get("status", {}).get("type", {})
            if not status.get("completed", False):
                continue
            competitors = competition.get("competitors", [])
            home = next((t for t in competitors if t.get("homeAway") == "home"), None)
            away = next((t for t in competitors if t.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            events[event["id"]] = {
                "id": str(event["id"]),
                "date": event.get("date", "")[:10],
                "home": home.get("team", {}).get("displayName", "").strip(),
                "away": away.get("team", {}).get("displayName", "").strip(),
                "home_team_id": str(home.get("team", {}).get("id", "")),
                "away_team_id": str(away.get("team", {}).get("id", "")),
                "home_goals": int(home.get("score") or 0),
                "away_goals": int(away.get("score") or 0),
            }

    suffix = f"{year}-{str(year + 1)[-2:]}"
    filename = f"{suffix}_1-seriea-full.json" if year == 2025 else f"{suffix}_1-seriea.json"
    rounds_url = f"https://openfootball.github.io/italy/{filename}"
    round_data = fetch_json(rounds_url, CACHE_DIR / str(year) / f"openfootball-{filename}", pause)
    round_by_fixture: dict[tuple[str, str, str], int] = {}
    for fixture in round_data.get("matches", []):
        match = re.search(r"\d+", fixture.get("round", ""))
        if not match:
            continue
        key = (
            fixture.get("date", ""),
            normalize_team(fixture.get("team1", "")),
            normalize_team(fixture.get("team2", "")),
        )
        round_by_fixture[key] = int(match.group())

    matched = []
    unmatched = []
    for event in events.values():
        key = (event["date"], normalize_team(event["home"]), normalize_team(event["away"]))
        round_number = round_by_fixture.get(key)
        if round_number is None:
            unmatched.append(event)
            continue
        event["round"] = round_number
        matched.append(event)

    if len(matched) != len(round_by_fixture):
        raise RuntimeError(
            f"Calendari non allineati per {year}/{year + 1}: "
            f"ESPN={len(events)}, fixture OpenFootball={len(round_by_fixture)}, "
            f"abbinati={len(matched)}, non abbinati ESPN={len(unmatched)}. "
            "Importazione annullata; verificare la cache e la copertura delle fonti."
        )
    return matched


def normalize_team(name: str) -> str:
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold()
    tokens = re.findall(r"[a-z0-9]+", value)
    tokens = [
        token for token in tokens
        if token not in {"fc", "acf", "ss", "ssc", "as", "us", "ac", "bc", "cfc", "uc", "sc", "calcio", "1907", "1909", "1913", "1919"}
    ]
    value = "".join(tokens)
    aliases = {
        "internazionalemilano": "inter",
        "internazionale": "inter",
        "milan": "milan",
        "fiorentina": "fiorentina",
        "napoli": "napoli",
        "roma": "roma",
        "hellasverona": "hellasverona",
        "sassuolo": "sassuolo",
    }
    return aliases.get(value, value)


def event_team_name(event: dict) -> str:
    team = event.get("team") or {}
    return (team.get("displayName") or team.get("name") or "").strip()


def extract_goals(summary: dict) -> list[dict]:
    goals = []
    for event in summary.get("keyEvents", []):
        if not event.get("scoringPlay") or event.get("shootout"):
            continue
        participants = event.get("participants") or []
        scorer = ""
        player_id = ""
        for participant in participants:
            athlete = participant.get("athlete") or {}
            scorer = (athlete.get("displayName") or athlete.get("fullName") or "").strip()
            player_id = str(athlete.get("id") or "")
            if scorer:
                break
        clock = (event.get("clock") or {}).get("displayValue", "")
        minute_match = re.search(r"\d+", clock)
        goals.append(
            {
                "scorer": scorer,
                "player_id": player_id,
                "team": event_team_name(event),
                "team_id": str((event.get("team") or {}).get("id", "")),
                "minute": int(minute_match.group()) if minute_match else None,
                "type": (event.get("type") or {}).get("text", "Gol"),
                "raw": event.get("text", ""),
            }
        )
    return goals


def backfill_player_ids(conn: sqlite3.Connection, cache_dir: Path) -> tuple[int, int]:
    """Collega gli eventi gol già importati agli ID atleta ESPN presenti nella cache."""
    updated = 0
    without_id = 0
    for summary_path in cache_dir.rglob("summary-*.json"):
        game_id = summary_path.stem.removeprefix("summary-")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        for goal_index, goal in enumerate(extract_goals(summary), start=1):
            player_id = goal.get("player_id")
            scorer = goal.get("scorer")
            if not player_id or not scorer:
                without_id += 1
                continue
            scorer_id = f"{game_id}:{goal_index}"
            exists = conn.execute(
                "SELECT 1 FROM marcatori WHERE espn_id = ?", (scorer_id,)
            ).fetchone()
            if not exists:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO giocatori (id_giocatore, nome) VALUES (?, ?)",
                (player_id, scorer),
            )
            conn.execute(
                "INSERT OR IGNORE INTO alias_calciatori "
                "(id_giocatore, alias, alias_normalizzato) VALUES (?, ?, ?)",
                (player_id, scorer, normalizza_nome(scorer)),
            )
            conn.execute(
                "UPDATE marcatori SET id_giocatore = ? WHERE espn_id = ?",
                (player_id, scorer_id),
            )
            updated += 1
    return updated, without_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Percorso del file SQLite")
    parser.add_argument("--pause", type=float, default=0.2, help="Pausa fra richieste (secondi)")
    parser.add_argument("--workers", type=int, default=4, help="Richieste simultanee per i riepiloghi")
    parser.add_argument("--refresh", action="store_true", help="Riscarica i JSON anche se sono in cache")
    parser.add_argument(
        "--players-only",
        action="store_true",
        help="Migra gli ID giocatore e gli alias dai JSON già presenti in cache, senza richieste di rete",
    )
    args = parser.parse_args()
    global CACHE_DIR
    if args.players_only and args.refresh:
        parser.error("--players-only non può essere usato insieme a --refresh")
    if args.refresh:
        shutil.rmtree(CACHE_DIR, ignore_errors=True)

    if args.players_only:
        db_path = args.db.resolve()
        if not db_path.exists():
            raise FileNotFoundError(f"Database non trovato: {db_path}")
        backup_path = db_path.with_name(f"{db_path.stem}.prima-anagrafica{db_path.suffix}")
        if not backup_path.exists():
            shutil.copy2(db_path, backup_path)
            print(f"Backup creato: {backup_path}")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("BEGIN IMMEDIATE")
            prepare_database(conn)
            updated, without_id = backfill_player_ids(conn, CACHE_DIR)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        print(f"Eventi collegati a un ID ESPN: {updated}")
        print(f"Eventi in cache senza ID atleta: {without_id}")
        return 0

    schedule_by_season: dict[int, list[dict]] = {}
    for year in SEASONS:
        schedule = get_schedule(year, args.pause)
        if len(schedule) < 300:
            raise RuntimeError(
                f"Solo {len(schedule)} partite completate per {year}/{year + 1}; "
                "importazione annullata per evitare un DB incompleto."
            )
        schedule_by_season[year] = schedule
        print(f"{year}/{year + 1}: trovate {len(schedule)} partite concluse")

    imports: dict[int, list[tuple[dict, list[dict]]]] = {}
    for year, games in schedule_by_season.items():
        def load_game(game: dict) -> tuple[dict, list[dict]]:
            query = urlencode({"event": game["id"]})
            url = f"{API_ROOT}/summary?{query}"
            summary = fetch_json(url, CACHE_DIR / str(year) / f"summary-{game['id']}.json", args.pause)
            goals = extract_goals(summary)
            expected = game["home_goals"] + game["away_goals"]
            if len(goals) != expected or any(not goal["scorer"] for goal in goals):
                raise RuntimeError(
                    f"Controllo fallito per {game['date']} {game['home']}–{game['away']}: "
                    f"risultato {expected} gol, eventi con autore {len(goals)}. "
                    "DB non modificato; i dati scaricati restano in cache."
                )
            for goal in goals:
                if goal["team_id"] == game["home_team_id"]:
                    goal["team"] = game["home"]
                elif goal["team_id"] == game["away_team_id"]:
                    goal["team"] = game["away"]
                elif goal["team"] not in (game["home"], game["away"]):
                    raise RuntimeError(
                        f"Squadra del marcatore inattesa ({goal['team']}) in "
                        f"{game['home']}–{game['away']}; DB non modificato."
                    )
            return game, goals

        imports[year] = []
        season_goal_count = 0
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = [pool.submit(load_game, game) for game in games]
            for index, future in enumerate(as_completed(futures), start=1):
                game, goals = future.result()
                imports[year].append((game, goals))
                season_goal_count += len(goals)
                if index % 50 == 0 or index == len(games):
                    print(f"  {index}/{len(games)} partite analizzate")
        print(f"  {season_goal_count} gol verificati")

    db_path = args.db.resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Database non trovato: {db_path}")
    backup_path = db_path.with_name(f"{db_path.stem}.prima-importazione{db_path.suffix}")
    if not backup_path.exists():
        shutil.copy2(db_path, backup_path)
        print(f"Backup creato: {backup_path}")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        prepare_database(conn)
        season_names = [f"{year}/{year + 1}" for year in SEASONS]
        placeholders = ",".join("?" for _ in season_names)
        conn.execute(
            f"DELETE FROM marcatori WHERE id_partita IN "
            f"(SELECT id_partita FROM partite WHERE stagione IN ({placeholders}))",
            season_names,
        )
        conn.execute(f"DELETE FROM partite WHERE stagione IN ({placeholders})", season_names)

        for year, matches in imports.items():
            season = f"{year}/{year + 1}"
            for game, goals in matches:
                cursor = conn.execute(
                    "INSERT INTO partite "
                    "(giornata, squadra_casa, squadra_trasferta, stagione, data_partita, espn_id) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (game["round"], game["home"], game["away"], season, game["date"], game["id"]),
                )
                match_id = cursor.lastrowid
                for goal in goals:
                    player_id = goal.get("player_id")
                    scorer = goal["scorer"]
                    if player_id:
                        conn.execute(
                            "INSERT OR IGNORE INTO giocatori (id_giocatore, nome) VALUES (?, ?)",
                            (player_id, scorer),
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO alias_calciatori "
                            "(id_giocatore, alias, alias_normalizzato) VALUES (?, ?, ?)",
                            (player_id, scorer, normalizza_nome(scorer)),
                        )
                conn.executemany(
                    "INSERT INTO marcatori "
                    "(id_partita, calciatore, minuto, squadra, tipo, espn_id, id_giocatore) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        (match_id, goal["scorer"], goal["minute"], goal["team"], goal["type"],
                         f"{game['id']}:{goal_index}", goal.get("player_id") or None)
                        for goal_index, goal in enumerate(goals, start=1)
                    ],
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("Importazione completata.")
    print(f"Database aggiornato: {db_path}")
    print("Stagioni: 2021/2022–2025/2026")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        raise SystemExit(1)
