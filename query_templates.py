"""Query parametrizzate per le domande statistiche ricorrenti."""

from dataclasses import dataclass
import re
import sqlite3
from pathlib import Path

import pandas as pd

from nomi import normalizza_nome
from query_utils import apri_db_sola_lettura


@dataclass
class QueryPredefinita:
    sql: str
    risultati: pd.DataFrame | None = None
    messaggio: str | None = None
    parametri: tuple[object, ...] = ()


SEASON_RE = re.compile(r"(?<!\d)(20\d{2}|\d{2})\s*/\s*(20\d{2}|\d{2})(?!\d)")
PLAYER_PATTERNS = (
    re.compile(
        r"\b(?:ha\s+fatto|ha\s+segnato|ha\s+realizzato|gol\s+di|reti\s+di)\s+"
        r"(?P<name>.+?)(?=\s+(?:nella\s+stagione|in\s+stagione|nella|nel|nell[ae]|"
        r"del|della|in(?:\s+serie\s+a)?|per\s+la\s+stagione)\b|[?!.;,]|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:in\s+cui|quando)\s+(?P<name>.+?)\s+"
        r"(?:ha\s+segnato|ha\s+realizzato|ha\s+fatto\s+gol)"
        r"(?=\s*[?!.;,]|$)",
        re.IGNORECASE,
    ),
)
FIRST_GOAL_RE = re.compile(
    r"\bprima\s+partita\b|\bprimo\s+(?:gol|goal)\b|\bprima\s+rete\b|"
    r"\bper\s+la\s+prima\s+volta\b",
    re.IGNORECASE,
)
GOAL_TYPES = "(m.tipo LIKE 'Goal%' OR m.tipo = 'Penalty - Scored')"


def normalizza_stagione(testo: str) -> str:
    match = SEASON_RE.search(testo)
    if not match:
        return ""
    start, end = match.groups()
    start_year = int(start) if len(start) == 4 else 2000 + int(start)
    end_year = int(end) if len(end) == 4 else 2000 + int(end)
    return f"{start_year}/{end_year}"


def stagione_non_coperta(domanda: str, db_path: Path) -> str | None:
    stagione = normalizza_stagione(domanda)
    if not stagione:
        return None
    with apri_db_sola_lettura(db_path) as conn:
        partite = conn.execute(
            "SELECT COUNT(*) FROM partite WHERE stagione = ?", (stagione,)
        ).fetchone()[0]
    if not partite:
        return stagione
    if partite != 380:
        return f"{stagione} (copertura parziale: {partite}/380 partite)"
    return None


def riepilogo_copertura(db_path: Path) -> tuple[list[tuple[str, int, int]], int]:
    with apri_db_sola_lettura(db_path) as conn:
        stagioni = conn.execute(
            "SELECT p.stagione, COUNT(DISTINCT p.id_partita), COUNT(m.id_marcatore) "
            "FROM partite p LEFT JOIN marcatori m ON m.id_partita = p.id_partita "
            "GROUP BY p.stagione ORDER BY p.stagione"
        ).fetchall()
        senza_id = conn.execute(
            "SELECT COUNT(*) FROM marcatori WHERE id_giocatore IS NULL"
        ).fetchone()[0]
    return [(str(s), int(partite), int(gol)) for s, partite, gol in stagioni], int(senza_id)


def _nome_calciatore(domanda: str) -> str | None:
    for pattern in PLAYER_PATTERNS:
        match = pattern.search(domanda)
        if match:
            nome = match.group("name").strip(" \t\r\n'\"“”‘’")
            nome = SEASON_RE.sub("", nome).strip()
            if nome:
                return nome
    return None


def _risolvi_giocatore(conn: sqlite3.Connection, nome: str) -> tuple[str, str] | None:
    chiave = normalizza_nome(nome)
    if len(chiave) < 3:
        return None
    righe = conn.execute(
        "SELECT DISTINCT g.id_giocatore, g.nome "
        "FROM alias_calciatori a JOIN giocatori g ON g.id_giocatore = a.id_giocatore "
        "WHERE a.alias_normalizzato = ? OR instr(a.alias_normalizzato, ?) > 0 "
        "ORDER BY g.nome LIMIT 8",
        (chiave, chiave),
    ).fetchall()
    if len(righe) == 1:
        return str(righe[0][0]), str(righe[0][1])
    if len(righe) > 1:
        candidati = ", ".join(str(riga[1]) for riga in righe)
        raise ValueError(f"Nome ambiguo: {candidati}. Inserisci nome e cognome.")
    return None


def _estrai_nome_top(domanda: str) -> str | None:
    return _nome_calciatore(domanda)


def query_predefinita(domanda: str, db_path: Path) -> QueryPredefinita | None:
    testo = domanda.casefold()
    stagione = normalizza_stagione(domanda)

    if FIRST_GOAL_RE.search(testo):
        nome = _estrai_nome_top(domanda)
        if nome:
            sql = (
                "SELECT g.nome AS calciatore, p.data_partita, p.stagione, p.giornata, "
                "p.squadra_casa, p.squadra_trasferta, m.minuto, m.tipo "
                "FROM marcatori m "
                "JOIN giocatori g ON g.id_giocatore = m.id_giocatore "
                "JOIN partite p ON p.id_partita = m.id_partita "
                "WHERE m.id_giocatore = ? AND " + GOAL_TYPES + " "
                "ORDER BY p.data_partita ASC, p.id_partita ASC, m.minuto ASC LIMIT 1"
            )
            with apri_db_sola_lettura(db_path) as conn:
                try:
                    giocatore = _risolvi_giocatore(conn, nome)
                except ValueError as errore:
                    return QueryPredefinita("", messaggio=str(errore))
                if not giocatore:
                    return QueryPredefinita(
                        "",
                        messaggio=(
                            f"Non trovo '{nome}' nell'anagrafica dei marcatori coperta dal database. "
                            "Prova con nome e cognome o con un altro alias."
                        ),
                    )
                parametri = (giocatore[0],)
                df = pd.read_sql_query(sql, conn, params=parametri)
            return QueryPredefinita(sql, df, parametri=parametri)

    if re.search(r"\b(?:gol|reti)\b", testo):
        nome = _estrai_nome_top(domanda)
        if nome:
            sql = (
                "SELECT COUNT(*) AS gol FROM marcatori m "
                "JOIN partite p ON p.id_partita = m.id_partita "
                "WHERE m.id_giocatore = ? AND " + GOAL_TYPES
            )
            parametri: list[object] = []
            with apri_db_sola_lettura(db_path) as conn:
                try:
                    giocatore = _risolvi_giocatore(conn, nome)
                except ValueError as errore:
                    return QueryPredefinita("", messaggio=str(errore))
                if not giocatore:
                    return QueryPredefinita(
                        "",
                        messaggio=(
                            f"Non trovo '{nome}' nell'anagrafica dei marcatori coperta dal database. "
                            "Prova con nome e cognome o con un altro alias."
                        ),
                    )
                parametri.append(giocatore[0])
                if stagione:
                    sql += " AND p.stagione = ?"
                    parametri.append(stagione)
                df = pd.read_sql_query(sql, conn, params=parametri)
            return QueryPredefinita(sql, df, parametri=tuple(parametri))

    if re.search(r"classifica\s+(?:dei\s+)?marcator|capocannonier|chi\s+ha\s+segnato\s+pi[uù]", testo):
        sql = (
            "SELECT g.nome AS calciatore, COUNT(*) AS gol FROM marcatori m "
            "JOIN giocatori g ON g.id_giocatore = m.id_giocatore "
            "JOIN partite p ON p.id_partita = m.id_partita WHERE " + GOAL_TYPES
        )
        params: list[object] = []
        if stagione:
            sql += " AND p.stagione = ?"
            params.append(stagione)
        sql += " GROUP BY g.id_giocatore, g.nome ORDER BY gol DESC, g.nome LIMIT 10"
        with apri_db_sola_lettura(db_path) as conn:
            return QueryPredefinita(
                sql, pd.read_sql_query(sql, conn, params=params), parametri=tuple(params)
            )

    if re.search(r"(?:gol|reti)\s+(?:per|di ogni)\s+squadra|squadre.*(?:gol|segnat)", testo):
        sql = (
            "SELECT m.squadra, COUNT(*) AS gol FROM marcatori m "
            "JOIN partite p ON p.id_partita = m.id_partita WHERE " + GOAL_TYPES
        )
        params = []
        if stagione:
            sql += " AND p.stagione = ?"
            params.append(stagione)
        sql += " GROUP BY m.squadra ORDER BY gol DESC, m.squadra"
        with apri_db_sola_lettura(db_path) as conn:
            return QueryPredefinita(
                sql, pd.read_sql_query(sql, conn, params=params), parametri=tuple(params)
            )

    return None
