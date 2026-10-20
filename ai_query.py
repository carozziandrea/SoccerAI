"""Build the local language-model chain that generates read-only SQLite queries."""

from langchain_classic.chains import create_sql_query_chain
from langchain_community.llms import Ollama
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import PromptTemplate

from query_utils import crea_engine_sqlite


SQL_PROMPT = (
    "Sei un esperto SQL. Data una domanda, restituisci ESCLUSIVAMENTE una query SQLite di sola lettura. "
    "Non aggiungere spiegazioni o Markdown. Genera una sola istruzione SQL eseguibile senza "
    "parametri esterni: non usare placeholder come ? o :nome. Aggiungi filtri giocatore solo "
    "se la domanda nomina esplicitamente un giocatore. Se non è nominato un giocatore, non "
    "usare giocatori, alias_calciatori, id_giocatore o calciatore nella query.\n"
    "Limita i risultati a massimo {top_k} righe quando ha senso.\n\n"
    "Schema del database:\n{table_info}\n\n"
    "Regole del database: usa alias_calciatori solo quando la domanda contiene un nome di giocatore. "
    "Stagione è una colonna di partite, non di marcatori. Per filtrare per stagione "
    "o giornata collega marcatori a partite con marcatori.id_partita = partite.id_partita. Le stagioni "
    "sono memorizzate come YYYY/YYYY, anche quando l'utente scrive 2025/26. Usa normalizza() per i nomi. "
    "Per il giocatore collega marcatori.id_giocatore a giocatori.id_giocatore; usa alias_calciatori "
    "per i nomi alternativi ed EXISTS per evitare doppioni; confronta i nomi grezzi con "
    "normalizza(marcatori.calciatore) = alias_calciatori.alias_normalizzato. Per contare le reti attribuite al "
    "giocatore includi Goal% e Penalty - Scored ed escludi Own Goal. Se l'utente chiede "
    "esplicitamente autogol o tutti gli eventi, includi invece anche Own Goal e gli altri tipi "
    "pertinenti. Se la domanda chiede un conteggio raggruppato per tipo, restituisci tutti i "
    "valori presenti in tipo: non aggiungere filtri su tipo. Usa solo SELECT.\n\n"
    "Domanda: {input}\nSQL Query:"
)


def crea_sistema_sql(
    db_uri: str,
    model_name: str = "llama3",
    include_engine: bool = False,
):
    """Create the same local SQL chain used by the app and evaluation runner."""
    engine = crea_engine_sqlite(db_uri)
    database = SQLDatabase(engine)
    llm = crea_llm_locale(model_name)
    prompt = PromptTemplate.from_template(SQL_PROMPT)
    sql_chain = create_sql_query_chain(llm, database, prompt=prompt)
    if include_engine:
        return sql_chain, llm, engine
    return sql_chain, llm


def crea_llm_locale(model_name: str = "llama3"):
    """Create the deterministic local Ollama model used for answer generation."""
    return Ollama(model=model_name, temperature=0)
