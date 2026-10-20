"""Run curated question cases and grade structured database outcomes."""

import json
from pathlib import Path
from typing import Any

from query_templates import query_predefinita, stagione_non_coperta
from query_utils import genera_ed_esegui_query


CASES_PATH = Path(__file__).with_name("cases.jsonl")


def carica_casi(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    """Load and validate one JSON object per line from the versioned eval dataset."""
    casi = []
    ids = set()
    for numero_riga, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        caso = json.loads(line)
        richiesti = {"id", "category", "route", "question"}
        mancanti = richiesti - caso.keys()
        if mancanti:
            raise ValueError(f"{path}:{numero_riga}: campi obbligatori mancanti: {sorted(mancanti)}")
        if caso["id"] in ids:
            raise ValueError(f"{path}:{numero_riga}: id duplicato: {caso['id']}")
        ids.add(caso["id"])
        casi.append(caso)
    return casi


def _righe_normalizzate(righe: list[dict[str, Any]]) -> list[str]:
    return sorted(json.dumps(riga, ensure_ascii=False, sort_keys=True) for riga in righe)


def valuta_caso(
    caso: dict[str, Any],
    db_path: Path,
    sql_chain=None,
) -> dict[str, Any]:
    """Evaluate one case using exact data checks rather than judging free-form prose."""
    route = caso["route"]
    dettaglio: dict[str, Any] = {"id": caso["id"], "category": caso["category"], "route": route}
    try:
        if route == "coverage":
            actual = stagione_non_coperta(caso["question"], db_path)
            passed = actual == caso["expected_coverage"]
            dettaglio.update(expected=caso["expected_coverage"], actual=actual)
        elif route in {"template", "template_message"}:
            result = query_predefinita(caso["question"], db_path)
            if result is None:
                raise AssertionError("Nessun template selezionato")
            if route == "template_message":
                actual = result.messaggio or ""
                passed = caso["expected_message_contains"] in actual
                dettaglio.update(expected=caso["expected_message_contains"], actual=actual)
            else:
                actual_rows = result.risultati.to_dict(orient="records")
                expected_rows = caso["expected_rows"]
                passed = _righe_normalizzate(actual_rows) == _righe_normalizzate(expected_rows)
                if "expected_params" in caso:
                    passed = passed and list(result.parametri) == caso["expected_params"]
                dettaglio.update(expected_rows=expected_rows, actual_rows=actual_rows)
                if "expected_params" in caso:
                    dettaglio["expected_params"] = caso["expected_params"]
                    dettaglio["actual_params"] = list(result.parametri)
        elif route == "sql_chain":
            if sql_chain is None:
                raise ValueError("Questo caso richiede --include-llm e un Ollama attivo")
            query, risultati = genera_ed_esegui_query(sql_chain, caso["question"], db_path)
            columns = caso["expected_columns"]
            actual_rows = risultati[columns].to_dict(orient="records")
            expected_rows = caso["expected_rows"]
            passed = _righe_normalizzate(actual_rows) == _righe_normalizzate(expected_rows)
            dettaglio.update(
                expected_rows=expected_rows,
                actual_rows=actual_rows,
                columns=columns,
                sql=query,
            )
        else:
            raise ValueError(f"Route non supportata nel caso {caso['id']}: {route}")
        dettaglio["passed"] = bool(passed)
    except Exception as errore:
        dettaglio.update(passed=False, error=f"{type(errore).__name__}: {errore}")
    return dettaglio


def esegui_valutazioni(
    db_path: Path,
    sql_chain=None,
    include_llm: bool = False,
    cases_path: Path = CASES_PATH,
) -> list[dict[str, Any]]:
    """Evaluate all offline cases and optionally the local-model SQL-generation cases."""
    risultati = []
    for caso in carica_casi(cases_path):
        if caso["route"] == "sql_chain" and not include_llm:
            continue
        risultati.append(valuta_caso(caso, db_path, sql_chain=sql_chain))
    return risultati


def riepiloga(risultati: list[dict[str, Any]]) -> dict[str, Any]:
    """Return pass rates overall and by capability category."""
    categorie = {}
    for category in sorted({item["category"] for item in risultati}):
        group = [item for item in risultati if item["category"] == category]
        passed = sum(item["passed"] for item in group)
        categorie[category] = {"passed": passed, "total": len(group)}
    passed = sum(item["passed"] for item in risultati)
    return {"passed": passed, "total": len(risultati), "by_category": categorie}
