# SoccerAI

## ENG

SoccerAI is a local Serie A goal archive. Ask football statistics questions in Italian and inspect the SQL and rows behind each answer. Common questions use deterministic, parameterized templates; less common questions can use a local language model to generate SQLite queries.

### Highlights

- **Auditable answers:** the interface displays the SQL query and database rows behind a response.
- **Read-only execution:** SQLite denies write operations, and invalid generated queries can be retried using database errors as feedback.
- **Reliable common queries:** templates cover player goal totals, first Serie A goal, scorer rankings, and team totals.
- **Robust player lookup:** normalization handles accents, case, punctuation, and selected transliterations; IDs and aliases resolve names such as “Yildiz”.
- **Data quality checks:** imports compare ESPN match scores against extracted scoring events and map fixtures to OpenFootball rounds before replacing season data.
- **Reproducible local development:** dependencies are locked with `uv`; offline tests use temporary SQLite databases and need neither network access nor Ollama.

### Stack

Python 3.13, Streamlit, SQLite, pandas, SQLAlchemy, LangChain, and Ollama with Llama 3.

### Setup

Install [Python 3.13](https://www.python.org/) and [uv](https://docs.astral.sh/uv/), then run from the project directory:

```powershell
uv sync
uv run python crea-db.py
uv run python importa-marcatori.py
```

The importer downloads the five seasons configured in the project (2021/22 through 2025/26). It uses ESPN's public, undocumented feed for match and goal events and OpenFootball calendars for round numbers. Downloads are cached in `.cache/espn-serie-a`; reruns reuse the cache. Pass `--refresh` to download again. A local backup is created before an existing database is changed. Source validation happens before the database transaction.

The database and downloaded source data are generated locally and excluded from Git. Importing requires internet access. Data availability and third-party feed formats may change; check source terms before redistributing downloaded data.

### Run the app

Install [Ollama](https://ollama.com/), start its local service, and download the model:

```powershell
ollama pull llama3
uv run streamlit run app.py
```

The app opens in your browser. Common questions use tested SQL templates; other questions use the local model to generate a read-only SQLite query. No account or API key is needed for local operation. Template-based questions can still work when the model service is unavailable.

Example questions:

- `Quanti gol ha fatto Leao nel 2025/26?`
- `Qual è la prima partita in cui ha segnato Yildiz?`
- `Classifica marcatori 2024/25`
- `Gol per squadra nel 2025/26`

### Database and coverage

`calcio.db` is created locally by `crea-db.py` and filled by `importa-marcatori.py`; it is not included in this repository. Seasons are stored in `partite.stagione`. Scorer events link to matches through `marcatori.id_partita`; player IDs and aliases are stored in `giocatori` and `alias_calciatori`. For an existing database with ESPN summaries in cache, `uv run python importa-marcatori.py --players-only` fills player IDs and aliases without network requests.

The app reports the seasons and match counts in the local database. A season is considered complete at 380 matches. ESPN does not document a stable API, so source changes or fixture mismatches can prevent imports. The app does not provide live data.

### Tests

Run the offline test suite:

```powershell
uv run python -m unittest discover -s tests -v
```

Tests cover the SQLite schema and migration, read-only SQL safeguards, query correction, season filtering, name aliases and special characters, first-goal match selection, goal totals, team totals, scorer rankings, and answer formatting. They make no external API calls and do not need a running Ollama service.

### Project status

SoccerAI is an experimental proof of concept for a portfolio, not a production service. The local database must be imported before the app can display archive coverage. The importer depends on third-party feeds whose formats and availability can change. The project code is released under the MIT License; the license provides the software “as is” without warranty.

---

## ITA

SoccerAI è un archivio locale dei gol della Serie A. Permette di fare domande statistiche in italiano e controllare la query SQL e le righe alla base di ogni risposta. Le domande comuni usano template deterministici e parametrizzati; per le altre, un modello locale può generare query SQLite.

### Punti di forza

- **Risposte verificabili:** l'interfaccia mostra la query SQL e i dati alla base della risposta.
- **Esecuzione in sola lettura:** SQLite blocca le scritture e le query generate non valide possono essere corrette usando gli errori del database.
- **Domande comuni affidabili:** i template coprono totali per calciatore, prima rete in Serie A, classifiche marcatori e gol per squadra.
- **Ricerca robusta dei giocatori:** la normalizzazione gestisce accenti, maiuscole, punteggiatura e alcune traslitterazioni; ID e alias aiutano a riconoscere nomi come “Yildiz”.
- **Controlli sulla qualità dei dati:** prima di sostituire una stagione, l'importatore confronta i punteggi ESPN con gli eventi gol e abbina le partite ai turni OpenFootball.
- **Sviluppo locale riproducibile:** le dipendenze sono bloccate con `uv`; i test offline usano database SQLite temporanei e non richiedono rete né Ollama.

### Stack

Python 3.13, Streamlit, SQLite, pandas, SQLAlchemy, LangChain e Ollama con Llama 3.

### Installazione

Installa [Python 3.13](https://www.python.org/) e [uv](https://docs.astral.sh/uv/), poi esegui questi comandi dalla cartella del progetto:

```powershell
uv sync
uv run python crea-db.py
uv run python importa-marcatori.py
```

L'importatore scarica le cinque stagioni configurate nel progetto (dal 2021/22 al 2025/26). Usa il feed pubblico non documentato di ESPN per partite ed eventi gol e i calendari OpenFootball per i numeri di giornata. I download sono salvati in `.cache/espn-serie-a` e riutilizzati alle esecuzioni successive. Aggiungi `--refresh` per scaricarli di nuovo. Prima di modificare un database esistente, viene creata una copia locale. I controlli sulle fonti avvengono prima della transazione sul database.

Il database e i dati scaricati sono generati localmente ed esclusi da Git. L'importazione richiede internet. Disponibilità e formato dei feed esterni possono cambiare; verifica le condizioni delle fonti prima di ridistribuire i dati.

### Avvio dell'app

Installa [Ollama](https://ollama.com/), avvia il servizio locale e scarica il modello:

```powershell
ollama pull llama3
uv run streamlit run app.py
```

L'app si apre nel browser. Le domande comuni usano template SQL verificati; per le altre il modello locale genera query SQLite di sola lettura. Per l'esecuzione locale non servono account o chiavi API. Le query basate su template possono funzionare anche se Ollama non è disponibile.

Esempi:

- `Quanti gol ha fatto Leao nel 2025/26?`
- `Qual è la prima partita in cui ha segnato Yildiz?`
- `Classifica marcatori 2024/25`
- `Gol per squadra nel 2025/26`

### Database e copertura

`calcio.db` viene creato localmente da `crea-db.py` e popolato da `importa-marcatori.py`; non è incluso nel repository. Le stagioni sono salvate in `partite.stagione`. Gli eventi gol si collegano alle partite tramite `marcatori.id_partita`; gli ID e gli alias dei giocatori sono in `giocatori` e `alias_calciatori`. Se esiste già un database con riepiloghi ESPN in cache, `uv run python importa-marcatori.py --players-only` completa ID e alias senza richieste di rete.

L'app mostra stagioni e numero di partite presenti nel database locale. Una stagione è considerata completa con 380 partite. ESPN non documenta un'API stabile: modifiche alla fonte o calendari non corrispondenti possono impedire l'importazione. L'app non fornisce dati in tempo reale.

### Test

Esegui la suite offline:

```powershell
uv run python -m unittest discover -s tests -v
```

I test verificano schema e migrazione SQLite, protezione in sola lettura, correzione delle query, filtri stagione, alias e caratteri speciali, prima partita con gol, totali, classifiche e formattazione delle risposte. Non chiamano API esterne e non richiedono Ollama.

### Stato del progetto

SoccerAI è un proof of concept sperimentale per portfolio e non un servizio destinato alla produzione. Il database locale va importato prima che l'app possa mostrare la copertura dell'archivio. L'importatore dipende da feed di terze parti che possono cambiare formato o diventare indisponibili. Il codice del progetto è distribuito con licenza MIT, che fornisce il software “così com'è” e senza garanzie.
