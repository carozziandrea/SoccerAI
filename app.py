"""Streamlit interface for asking natural-language questions about Serie A goals."""

from html import escape
from pathlib import Path

import streamlit as st
from ai_query import crea_llm_locale, crea_sistema_sql
from query_templates import query_predefinita, riepilogo_copertura, stagione_non_coperta
from query_utils import genera_ed_esegui_query
from risposte import formula_risposta


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "calcio.db"

st.set_page_config(page_title="SoccerAI · Almanacco dei gol", layout="wide")
st.markdown(
    """
    <style>
    :root { color-scheme: light; }
    .stApp { background: #f1ecdf; color: #20251f; }
    [data-testid="stHeader"] { background: #f1ecdf; }
    [data-testid="stMainBlockContainer"] {
        max-width: 1180px;
        padding: 2rem 2.5rem 5rem;
    }
    .brandbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: .8rem 0 .9rem;
        margin-bottom: 2.4rem;
        border-top: 2px solid #20251f;
        border-bottom: 1px solid #9d9789;
    }
    .brandname { color: #20251f; font-size: .78rem; font-weight: 800; letter-spacing: .14em; }
    .brandmeta { color: #5b5a50; font-size: .73rem; font-weight: 650; letter-spacing: .09em; text-transform: uppercase; }
    [data-testid="stHorizontalBlock"] { align-items: flex-start; gap: 3rem; }
    .hero-copy { max-width: 37rem; }
    h1 {
        color: #20251f !important;
        font-family: Georgia, "Palatino Linotype", "Times New Roman", serif !important;
        font-size: 3.7rem !important;
        font-weight: 500 !important;
        letter-spacing: -.045em !important;
        line-height: .99 !important;
        margin: 0 0 1rem !important;
    }
    .intro {
        max-width: 42ch;
        color: #53564e;
        font-size: 1.02rem;
        line-height: 1.65;
        margin: 0 0 2rem;
    }
    .coverage-strip {
        display: grid;
        grid-template-columns: 1fr 1fr;
        align-items: end;
        gap: .8rem 1.2rem;
        padding: 1.1rem 0 .9rem;
        margin: .3rem 0 0;
        border-top: 1px solid #9d9789;
        border-bottom: 1px solid #9d9789;
        color: #53564e;
        font-size: .78rem;
    }
    .coverage-strip strong { display: block; color: #20251f; font-size: 1.17rem; font-variant-numeric: tabular-nums; font-weight: 700; }
    .coverage-count { color: #53564e; text-align: left; font-variant-numeric: tabular-nums; }
    h2, h3 { color: #20251f !important; letter-spacing: -.025em; }
    h2 { font-family: Georgia, "Palatino Linotype", "Times New Roman", serif !important; font-size: 1.85rem !important; font-weight: 500 !important; }
    h3 { font-size: .78rem !important; font-weight: 750 !important; letter-spacing: .11em !important; text-transform: uppercase; }
    [data-testid="stForm"] {
        border-top: 2px solid #20251f;
        border-bottom: 1px solid #9d9789;
        background: #e8e2d5;
        padding: 1.3rem 1.35rem 1rem;
    }
    [data-testid="stTextInput"] label {
        color: #20251f !important;
        font-size: .78rem;
        font-weight: 750;
        letter-spacing: .08em;
        text-transform: uppercase;
        margin-bottom: .7rem;
    }
    [data-testid="stTextInput"] input {
        min-height: 3.25rem;
        border: 1px solid #77776d;
        border-radius: 2px;
        background: #f8f5ed;
        color: #20251f;
        font-size: 1rem;
    }
    [data-testid="stTextInput"] input::placeholder { color: #67675e; opacity: 1; }
    [data-testid="stTextInput"] input:focus {
        border-color: #9b3829;
        box-shadow: 0 0 0 2px rgb(155 56 41 / 18%);
    }
    [data-testid="stFormSubmitButton"] button {
        min-height: 2.9rem;
        border: 1px solid #9b3829;
        border-radius: 2px;
        background: #9b3829;
        color: #fffaf0;
        font-weight: 700;
        letter-spacing: .02em;
        transition: background-color 160ms ease, border-color 160ms ease;
    }
    [data-testid="stFormSubmitButton"] button:hover {
        border-color: #75271d;
        background: #75271d;
        color: #fffaf0;
    }
    [data-testid="stFormSubmitButton"] button:focus-visible {
        outline: 3px solid #20251f;
        outline-offset: 3px;
    }
    .examples { color: #53564e; font-size: .78rem; line-height: 1.75; margin: .8rem 0 1.6rem; }
    .answer-block {
        padding: 1.15rem 0 1.35rem;
        margin: .25rem 0 1.4rem;
        border-top: 2px solid #20251f;
        border-bottom: 1px solid #9d9789;
        color: #20251f;
        font-family: Georgia, "Palatino Linotype", "Times New Roman", serif;
        font-size: 1.55rem;
        line-height: 1.35;
        white-space: pre-wrap;
    }
    [data-testid="stDataFrame"] { border: 1px solid #9d9789; border-radius: 2px; overflow: hidden; }
    [data-testid="stExpander"] { border-color: #9d9789; border-radius: 2px; }
    [data-testid="stAlert"] { border-radius: 2px; }
    ::selection { background: #9b3829; color: #fffaf0; }
    @media (max-width: 640px) {
        [data-testid="stMainBlockContainer"] { padding: 1.1rem 1rem 3rem; }
        .brandbar { margin-bottom: 1.6rem; }
        .brandmeta { font-size: .62rem; text-align: right; }
        [data-testid="stHorizontalBlock"] { gap: 1.2rem; }
        h1 { font-size: 2.65rem !important; }
        .coverage-strip { grid-template-columns: 1fr 1fr; gap: .75rem; }
        [data-testid="stForm"] { padding: 1rem 1rem .8rem; }
        [data-testid="stFormSubmitButton"] button { width: 100%; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="brandbar"><span class="brandname">SOCCERAI</span>'
    '<span class="brandmeta">L’almanacco dei gol &nbsp; / &nbsp; Serie A</span></div>',
    unsafe_allow_html=True,
)


def crea_uri_sqlalchemy(db_path: Path) -> str:
    """Crea un URI SQLite assoluto, valido anche su Windows."""
    return f"sqlite:///{db_path.as_posix()}"


@st.cache_resource
def inizializza_sistema(db_uri: str):
    return crea_sistema_sql(db_uri)


if not DB_PATH.is_file():
    st.error(f"Database non trovato: {DB_PATH}")
    st.stop()

try:
    copertura, senza_id = riepilogo_copertura(DB_PATH)
    if not copertura:
        st.info("L'archivio non contiene stagioni consultabili.")
        st.stop()
    if copertura:
        prima = copertura[0][0]
        ultima = copertura[-1][0]
        partite_totali = sum(riga[1] for riga in copertura)
        gol_totali = sum(riga[2] for riga in copertura)
        col_intro, col_query = st.columns([1.1, .9], gap="large")
        with col_intro:
            st.title("Ogni gol, al suo posto.")
            st.markdown(
                '<p class="intro">Un archivio dei marcatori di Serie A, interrogabile in italiano. '
                'Dalla domanda ai dati, senza scrivere SQL.</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="coverage-strip" role="note">'
                f'<span><strong>{prima} – {ultima}</strong>Stagioni in archivio</span>'
                f'<span class="coverage-count"><strong>{partite_totali:,} · {gol_totali:,}</strong>'
                'Partite · eventi gol</span></div>'.replace(",", "."),
                unsafe_allow_html=True,
            )
        with col_query:
            with st.form("ricerca_marcatori", border=False):
                domanda = st.text_input(
                    "La tua domanda",
                    placeholder="Quanti gol ha fatto Leão nel 2025/26?",
                    key="domanda_marcatori",
                )
                inviata = st.form_submit_button("Cerca nell’archivio", type="primary")
                st.markdown(
                    '<p class="examples">Prova: “Gol di Yildiz nel 2025/26” · '
                    '“Classifica marcatori 2024/25” · “Gol per squadra”</p>',
                    unsafe_allow_html=True,
                )
        if senza_id:
            st.warning(
                f"{senza_id} eventi gol non hanno un ID giocatore: potrebbero non comparire "
                "nelle statistiche basate sull'anagrafica."
            )
except Exception as e:
    st.error("L'anagrafica dei calciatori non è ancora stata migrata.")
    st.code(f"Esegui: uv run python importa-marcatori.py --players-only\n{e}")
    st.stop()

if inviata and domanda.strip():
    stagione_non_disponibile = stagione_non_coperta(domanda, DB_PATH)
    if stagione_non_disponibile:
        st.info(
            f"Non posso rispondere con copertura completa per {stagione_non_disponibile}. "
            f"Il database contiene: {', '.join(riga[0] for riga in copertura)}."
        )
        st.stop()

    with st.spinner("Interrogo l'archivio Serie A…"):
        try:
            query_fissa = query_predefinita(domanda, DB_PATH)
            if query_fissa and query_fissa.messaggio:
                st.info(query_fissa.messaggio)
                st.stop()

            if query_fissa:
                query_sql = query_fissa.sql
                df_risultati = query_fissa.risultati
                llm = crea_llm_locale()
            else:
                sql_chain, llm = inizializza_sistema(crea_uri_sqlalchemy(DB_PATH))
                query_sql, df_risultati = genera_ed_esegui_query(sql_chain, domanda, DB_PATH)

            st.subheader("Risposta")
            try:
                risposta = formula_risposta(llm, domanda, df_risultati)
                st.markdown(
                    f'<div class="answer-block">{escape(risposta)}</div>',
                    unsafe_allow_html=True,
                )
            except Exception as e:
                st.info("Mostro i dati SQL; non sono riuscito a formulare una risposta testuale.")
                with st.expander("Dettaglio tecnico della risposta"):
                    st.code(f"{type(e).__name__}: {e}")

            if not df_risultati.empty:
                st.subheader("Dati restituiti dal database")
                st.dataframe(df_risultati, use_container_width=True, hide_index=True)
            else:
                st.info("La ricerca non ha prodotto risultati nel database.")

            with st.expander("Dettagli della query"):
                st.code(query_sql, language="sql")
                if query_fissa and query_fissa.parametri:
                    st.caption(f"Parametri SQL: {query_fissa.parametri}")
        except Exception as e:
            st.error("Non sono riuscito a elaborare la richiesta.")
            with st.expander("Dettaglio tecnico"):
                st.code(f"{type(e).__name__}: {e}")
