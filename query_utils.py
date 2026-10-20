"""Utility per generare ed eseguire query SQLite in sola lettura."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pandas as pd
from sqlalchemy import create_engine, event
from nomi import normalizza_nome


def _registra_funzione_normalizza(connessione, record) -> None:
    connessione.create_function("normalizza", 1, normalizza_nome, deterministic=True)


def crea_engine_sqlite(db_uri: str):
    """Crea un engine che espone la normalizzazione anche alla generazione SQL."""
    engine = create_engine(db_uri)
    event.listen(engine, "connect", _registra_funzione_normalizza)
    return engine


def pulisci_e_valida_sql(query: str) -> str:
    query = query.strip()
    if query.startswith("```sql"):
        query = query[6:].strip()
    elif query.startswith("```"):
        query = query[3:].strip()
    if query.endswith("```"):
        query = query[:-3].strip()

    if not query or query.lstrip().split(None, 1)[0].rstrip(";").upper() not in {"SELECT", "WITH"}:
        raise ValueError("Il modello non ha generato una query SELECT valida.")
    return query


@contextmanager
def apri_db_sola_lettura(db_path: Path) -> Iterator[sqlite3.Connection]:
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.create_function("normalizza", 1, normalizza_nome, deterministic=True)

    azioni_permesse = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        getattr(sqlite3, "SQLITE_RECURSIVE", -1),
    }

    def autorizza(azione, arg1, arg2, database, trigger):
        if azione == sqlite3.SQLITE_FUNCTION and (arg2 or arg1 or "").lower() == "load_extension":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK if azione in azioni_permesse else sqlite3.SQLITE_DENY

    conn.set_authorizer(autorizza)
    try:
        yield conn
    finally:
        conn.close()


def genera_ed_esegui_query(
    sql_chain, domanda: str, db_path: Path, max_tentativi: int = 3
) -> tuple[str, pd.DataFrame]:
    """Genera ed esegue SQL; in caso di errore SQLite chiede al modello una correzione."""
    richiesta_sql = domanda
    ultimo_errore = None
    ultima_query = None

    for tentativo in range(max_tentativi):
        ultima_query = pulisci_e_valida_sql(sql_chain.invoke({"question": richiesta_sql}))
        try:
            with apri_db_sola_lettura(db_path) as conn:
                risultati = pd.read_sql_query(ultima_query, conn)
            return ultima_query, risultati
        except (sqlite3.Error, pd.errors.DatabaseError) as errore:
            ultimo_errore = errore
            if tentativo == max_tentativi - 1:
                break
            richiesta_sql = (
                f"Domanda originale dell'utente: {domanda}\n"
                f"La query precedente non è stata eseguita. Query: {ultima_query}\n"
                f"Errore restituito da SQLite: {type(errore).__name__}: {errore}\n"
                "Correggi la query in base allo schema. Ricorda: stagione è in partite; "
                "marcatori va collegata a partite con marcatori.id_partita = partite.id_partita. "
                "Restituisci una sola query SELECT valida."
            )

    raise RuntimeError(
        f"La query non è stata corretta dopo {max_tentativi} tentativi. "
        f"Ultima SQL: {ultima_query}. "
        f"Ultimo errore SQLite: {type(ultimo_errore).__name__}: {ultimo_errore}"
    ) from ultimo_errore
