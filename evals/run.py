"""Command-line entry point for the SoccerAI regression evaluations."""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from ai_query import crea_sistema_sql
from evals.fixture import crea_database_valutazione
from evals.runner import esegui_valutazioni, riepiloga


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run SoccerAI question-answer evaluations.")
    parser.add_argument(
        "--include-llm",
        action="store_true",
        help="Include SQL generation with the configured local Ollama model.",
    )
    parser.add_argument("--model", default="llama3", help="Local Ollama model name.")
    parser.add_argument("--json-output", type=Path, help="Write the full evaluation report to this path.")
    return parser


def _mostra_risultati(risultati: list[dict[str, Any]], riepilogo: dict[str, Any]) -> None:
    for item in risultati:
        stato = "PASS" if item["passed"] else "FAIL"
        print(f"{stato} [{item['category']}] {item['id']}")
        if not item["passed"]:
            print(f"  {item.get('error') or 'Risultato diverso da quello atteso'}")
            if "sql" in item:
                print(f"  SQL: {item['sql']}")
    print(f"\nTotale: {riepilogo['passed']}/{riepilogo['total']} casi superati")
    for category, scores in riepilogo["by_category"].items():
        print(f"  {category}: {scores['passed']}/{scores['total']}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    with tempfile.TemporaryDirectory(
        prefix=".soccerai-eval-", dir=Path(__file__).resolve().parents[1]
    ) as temporary_dir:
        db_path = Path(temporary_dir) / "evaluation.sqlite"
        crea_database_valutazione(db_path)
        sql_chain = None
        engine = None
        if args.include_llm:
            db_uri = f"sqlite:///{db_path.as_posix()}"
            sql_chain, _, engine = crea_sistema_sql(
                db_uri, model_name=args.model, include_engine=True
            )
        try:
            risultati = esegui_valutazioni(
                db_path,
                sql_chain=sql_chain,
                include_llm=args.include_llm,
            )
        finally:
            if engine is not None:
                engine.dispose()
    riepilogo = riepiloga(risultati)
    _mostra_risultati(risultati, riepilogo)
    report = {
        "model": args.model if args.include_llm else None,
        "temperature": 0 if args.include_llm else None,
        "llm_included": args.include_llm,
        "summary": riepilogo,
        "cases": risultati,
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Report JSON: {args.json_output}")
    return int(riepilogo["passed"] != riepilogo["total"])


if __name__ == "__main__":
    sys.exit(main())
