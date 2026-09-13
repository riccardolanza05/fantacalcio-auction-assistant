# Fantacalcio Auction Assistant

*[Read this in English](README.md)*

Un sistema per **decidere quanto offrire durante l'asta del fantacalcio**
usando la matematica invece che il sentimento: prima dell'asta calcola un
prezzo calibrato per ogni giocatore (con un intervallo di incertezza),
durante l'asta legge in tempo reale la pagina d'asta dal browser e manda al
telefono il prezzo consigliato aggiornato, i budget di tutti gli avversari
e lo stato della propria rosa.

Nato per la Lega Abendosa (fantacalcio.it, modalita' Classic, 10 squadre),
usato in un'asta reale. Il codice — commenti, docstring, nomi di variabili
— e' **in italiano** e resta cosi' deliberatamente: e' un dominio
(*fantamedia*, *quotazione*, *titolarita'*, *fascia*) che non ha una
traduzione standard, e questo progetto e' nato per una lega italiana. Chi
legge in inglese trova un riassunto in [README.md](README.md), un
[glossario IT→EN](docs/glossary.md) e non deve toccare il codice per
usarlo. **Non aprire una pull request per tradurlo.**

## L'idea, in breve

Il fantacalcio all'italiana in modalita' Classic si gioca con un'asta
iniziale: ogni squadra ha un budget fisso in crediti e compra i giocatori
al rialzo, uno alla volta. L'asta decide gran parte della stagione ma si
svolge in tempo reale, sotto pressione, guardando le stesse liste di
quotazioni ufficiali che hanno tutti. Le domande che ci si pone di continuo
sono tre:

1. **Quanto vale davvero questo giocatore**, in crediti, nella *mia* lega?
2. **Al prezzo a cui sta andando adesso, conviene?**
3. **Quanto sono disposto a spingermi**, sapendo che le alternative si
   esauriscono mentre l'asta procede?

Il progetto risponde con due meta' complementari:

```
                    ┌──────────────────────────────────────────────┐
   DATI STORICI     │  PIPELINE OFFLINE (prima dell'asta)          │
   (fantacalcio.it) │                                              │
                     │  modello ML: produzione attesa (+ p10/p90)   │
                    │        ↓                                     │
                    │  pricing/modello_prezzo.py  (strati 1-2-3)   │
                    │        ↓  prezzi.csv                         │
                    │  pricing/verdetto.py  (sopra/sottovalutato)  │
                    │        ↓  verdetto.csv                       │
                    │  server/build_giocatori.py  (merge + infortuni) │
                    │        ↓                                     │
                    │     giocatori_AAAA_AA.xlsx  ◄── il database │
                    └──────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴──────────────────────────┐
                    │  ASSISTENTE LIVE (durante l'asta)            │
                    │                                              │
  pagina d'asta ──► browser/asta-live.user.js (Tampermonkey, PC)   │
  (HTTPS, Angular)  │  POST /ingest                                │
                    │        ↓                                     │
                    │  server/app.py (FastAPI, localhost:8000)     │
                    │   ├── player_db.py    lookup giocatore       │
                    │   ├── vorp_live.py    STRATO 4 (scarsita')   │
                    │   ├── live_state.py   stato asta e rose      │
                    │   ├── storico_prezzi.py  prezzi asta scorsa  │
                    │   └── simili.py       profili per analogia   │
                    │        ↓ WebSocket                           │
                    │  static/phone.html  ◄── telefono, stessa WiFi│
                    └──────────────────────────────────────────────┘
```

Il vincolo di progetto, ripetuto in ogni strato: **nessuno strato puo'
stravolgere il precedente.** Il mercato (l'FVM di fantacalcio.it) ha sempre
l'ultima parola sulla *forma* della curva dei prezzi; il modello statistico
sposta i prezzi, non li reinventa. Dettaglio completo in
[docs/methodology.md](docs/methodology.md).

## Come si e' arrivati qui (e perche')

Il progetto e' cresciuto per iterazioni, spesso in reazione a un
fallimento concreto piu' che per un piano iniziale. I due piu' istruttivi:

- **Il riferimento del verdetto conta piu' del modello.** La prima
  versione del verdetto (sopra/sottovalutato) confrontava ogni giocatore
  con un modello comportamentale addestrato su una sola asta reale.
  Risultato: verdetti completamente instabili (deviazione standard **≈
  241%**). Sostituendo il riferimento con l'FVM riscalato per quote di
  reparto — un numero molto piu' "banale" — la deviazione standard e'
  scesa a **≈ 10,9%**.
- **Un modello Bayesiano completo e' meglio offline che live.** Il primo
  correttore di scarsita' in tempo reale era un tracker Bayesiano
  Normal-Inverse-Gamma. Lavorando su un fair value VORP puro (non ancorato
  al mercato) produceva moltiplicatori 6-10× sui giocatori di coda — prezzi
  assurdi proprio dove l'asta e' piu' affollata. E' stato sostituito da un
  fattore di scarsita' piu' semplice basato su composizione/deplezione del
  pool ancora disponibile, che approssima uno shrinkage bayesiano empirico
  senza i suoi costi in latenza e osservazioni scarse.

Altre scelte notevoli, con la giustificazione empirica:

- **Gradient boosting, non rete neurale**, per il modello di produzione
  attesa: piu' performante su dati tabellari di questa dimensione.
- **Soglia del verdetto al 10%**, scelta su un backtest di 6 stagioni
  confrontando 5 soglie: e' quella con minore variabilita' del segnale tra
  stagioni, e copre l'83% dei giocatori.
- **Persistenza per ruolo nella regressione alla media**: il coefficiente
  dei portieri e' **negativo** (−0,08) — un'annata sopra il proprio livello
  storico, per un portiere, non si ripete affatto — mentre per gli
  attaccanti e' 0,81. E' il motivo per cui i tetti di correzione sui
  portieri sono cosi' bassi.

Il dettaglio di ogni fase, coi numeri, e' in
[docs/methodology.md](docs/methodology.md) e nel dossier di progetto
completo, [PROJECT_DOSSIER.md](PROJECT_DOSSIER.md).

## Risultati (backtest, 6 stagioni)

- Modello di produzione attesa: **R² ≈ 0,467** in validazione temporale;
  intervalli p10/p90 con copertura empirica **81,6%** (nominale 80%).
- Verdetto: i giocatori classificati sottovalutati hanno reso **1,86×**, i
  sopravvalutati **0,77×** la produzione realmente realizzata, in tutte le
  6 stagioni testate. Correlazione di rango (Spearman) tra 0,43 e 0,74 a
  seconda della stagione.

## Provarlo subito (dati sintetici, nessun account fantacalcio.it richiesto)

```bash
git clone <url-di-questo-repo>
cd fantacalcio-auction-assistant

# pipeline di pricing su 80 giocatori inventati
pip install -r requirements-pipeline.txt
python pricing/modello_prezzo.py --in-csv examples/sample_data/predizioni_esempio.csv --out-csv /tmp/prezzi.csv
python pricing/verdetto.py --in-csv /tmp/prezzi.csv --out-csv /tmp/verdetto.csv

# server (con lo stesso database sintetico gia' pronto)
pip install -r requirements.txt
cp examples/sample_data/giocatori_esempio.xlsx server/giocatori_2026_27.xlsx
cd server && ASTA_PASSWORD=demo python app.py   # poi apri http://localhost:8000
```

Per usarlo con la tua lega vera servono i tuoi file fantacalcio.it: vedi
[docs/data-sources.md](docs/data-sources.md) per dove trovarli e come sono
fatti, e [docs/operations.md](docs/operations.md) per la guida operativa
completa (calibrazione, Tampermonkey, troubleshooting).

## Stato onesto

La pipeline **e' riproducibile end-to-end** con i tuoi dati fantacalcio.it.
`pricing/model/train_model.py` e `pricing/model/build_hreg.py` — lo script
di training ML e il costruttore dello shrinkage gerarchico, che versioni
precedenti di questo repository segnalavano come assenti — sono stati
recuperati dalla trascrizione della sessione originale in cui sono stati
sviluppati e rieseguiti sui dati reali per verificare che riproducessero i
risultati documentati (vedi [docs/data-sources.md](docs/data-sources.md),
sezione 3, per i numeri esatti). `pricing/votes/` (anch'esso recuperato)
trasforma i voti grezzi giornata-per-giornata nel dataset aggregato che
questi due script usano.

Restano aperte due cose piu' piccole:

1. **Una titolarita' futura fresca** per `train_model.py` e' opzionale e
   specifica della settimana in cui viene generata, non un artefatto
   statico mancante — senza, quella singola feature resta "sconosciuta" e
   il resto del modello non ne risente. Vedi `pricing/model/README.md`.
2. **SHAP non e' mai stato effettivamente implementato** nel progetto
   originale, nonostante la documentazione precedente di questo repository
   lo indicasse come fatto: la trascrizione recuperata lo mostra solo come
   intenzione dichiarata, mai come codice eseguito.

Un disallineamento noto sul numero di squadre (10 vs 12) tra due parti
della pipeline di pricing resta documentato in
[docs/data-sources.md](docs/data-sources.md) e in
[PROJECT_DOSSIER.md](PROJECT_DOSSIER.md).

## Struttura del repository

```
pricing/
  modello_prezzo.py, verdetto.py   strati 1-3 del prezzo e verdetto
  model/                            training ML (HistGradientBoosting + conformal) e Hreg.pkl
  votes/                            scraping e aggregazione dei voti storici
server/     server FastAPI dell'assistente live + script di costruzione dati
browser/    userscript Tampermonkey e script da console per leggere l'asta
docs/       metodologia, fonti dei dati, glossario, guida operativa
tests/      smoke test di CI (dati sintetici) + script manuali di verifica
examples/   generatore di dati sintetici e file di configurazione di riferimento
```

## Licenza

Il codice e' MIT (vedi [LICENSE](LICENSE)). I dati ufficiali di
fantacalcio.it **non sono inclusi** e non sono coperti da questa licenza:
vedi [docs/data-sources.md](docs/data-sources.md) per come procurarteli.
