# Da dove vengono i dati, e cosa manca

Questo repository **non contiene i dati ufficiali di fantacalcio.it**, per due
motivi: non e' chiaro se la loro ridistribuzione sia consentita dai termini
d'uso del sito, e in ogni caso i file cambiano ogni stagione. Quello che
trovi qui e' il codice che li elabora, piu' una piccola cartella di dati
**sintetici** (`examples/sample_data/`) che ti permette di far girare la
pipeline e il server senza possedere nulla di reale.

Se vuoi ricostruire la pipeline con i tuoi dati veri, questa pagina elenca
esattamente quali file servono, dove si scaricano e le trappole che sono
state trovate lavorandoci (utili anche se stai adattando il progetto a una
lega diversa).

## 1. File richiesti e dove trovarli

Tutti da **fantacalcio.it**, sezione statistiche/quotazioni ufficiali
(richiede un abbonamento a pagamento per gli export completi):

| File | Dove | Usato da |
|---|---|---|
| `Quotazioni_Fantacalcio_Stagione_AAAA_AA.xlsx` | fantacalcio.it → Quotazioni | `pricing/` (indirettamente, via le predizioni), `server/build_storico_arricchito.py` |
| `Statistiche_Fantacalcio_Stagione_AAAA_AA.xlsx` | fantacalcio.it → Statistiche | `server/build_giocatori.py`, `server/build_storico_arricchito.py` |
| `voti_AAAA-AA_gNN.xlsx` (una per giornata) | fantacalcio.it → Voti | il modello ML di produzione attesa (script assente, vedi sotto) |
| `probabili-formazioni-serie-a` (HTML) | https://www.fantacalcio.it/probabili-formazioni-serie-a — tasto destro → "Salva pagina", salvata **senza estensione** nella cartella `server/` | `server/build_giocatori.py` (infortuni e titolarita') |
| `Rose_lega-<tuasigla>.xlsx` | export della TUA lega su fantacalcio.it/FantaAsta Live | `server/build_storico_arricchito.py`, e va copiato accanto ad `app.py` per la ricerca "asta dell'anno scorso" |

Per un'asta live serve anche l'accesso alla piattaforma **FantaAsta Live**
(`fanta-asta-live.fantacalcio.it`), che e' quella che lo userscript in
`browser/` legge.

## 2. Le trappole nei dati (verificate, non ipotizzate)

Chi riscrive la pipeline da zero su questi file incontrera' gli stessi
problemi risolti qui:

- **Header sulla riga 2**: nei file Quotazioni e Statistiche l'intestazione
  vera sta sulla riga 2 (la riga 1 e' un titolo), i dati partono dalla riga
  3, foglio `Tutti`.
- **`Cod.` non `Id`**: i file dei voti giornata-per-giornata usano `Cod.`
  come identificativo del giocatore, non `Id` come Quotazioni/Statistiche.
- **Asterisco = non presenza**: un asterisco accanto al voto in un file
  giornata significa *voto d'ufficio* (il giocatore e' entrato per uno
  spezzone irrilevante) e **non va contato come presenza**. Verificato al
  99,4% di accuratezza contro le presenze ufficiali.
- **Riga `ALL`**: i file dei voti includono anche l'allenatore con ruolo
  `ALL`: va filtrato.
- **`Gf` include gia' i rigori**: nel file Statistiche il campo `Gf` (gol
  fatti) comprende gia' i gol su rigore, a differenza dei file voti dove i
  rigori segnati sono separati. Sommarli di nuovo li conta due volte — un
  bug reale trovato e corretto durante lo sviluppo.
- **BOM e codifica**: i file scaricati/generati via PowerShell hanno un BOM
  e vanno letti con `utf-8-sig`, con una sanitizzazione ulteriore per
  caratteri latin-1 residui.
- **API delle giornate bloccata**: l'endpoint che serve i voti giornata per
  giornata risponde 401 alle richieste esterne anche con cookie di sessione
  validi; lo scarico va fatto con uno script eseguito nel browser, loggato.
- **Cognomi abbreviati**: i file usano "Martinez L.", non "Lautaro
  Martinez"; il match nome-per-nome fallisce proprio sui giocatori piu'
  importanti. Vedi `server/player_db.py` e `server/common.py` per la
  strategia di matching (id numerico → nome abbreviato → cognome+iniziale).

## 3. Cosa manca per una pipeline riproducibile end-to-end

Con SOLO il codice di questo repository e i file elencati sopra, la
pipeline **non gira interamente da zero**. Mancano due pezzi:

1. **Lo script di training del modello ML.** Il codice che addestra
   l'`HistGradientBoostingRegressor`, fa la cross-validation temporale,
   calcola gli intervalli p10/p90 con regressione quantile conformalizzata e
   produce SHAP non e' incluso in questo repository. Il suo output atteso
   (un CSV/XLSX con colonne `Id, Nome, Squadra, Ruolo, QtI, FVM,
   pct_titolarita, produzione_attesa, p10, p90, presenze_2025_26,
   fm_media_2025_26, ...`, vedi `examples/sample_data/predizioni_esempio.csv`
   per lo schema esatto) e' l'input di `pricing/modello_prezzo.py`.
   **Se hai questo script, forniscilo**: e' il pezzo che chiude la pipeline.
2. **`Hreg.pkl`** — lo shrinkage gerarchico bayesiano (`fm_storica`,
   `fm_shrunk`, `fm_L1`, `correzione_fm`, `n_stagioni`) che alimenta lo
   strato 3b (regressione alla media, sezione 4 di `docs/methodology.md`).
   Senza questo file `pricing/modello_prezzo.py` funziona comunque — la
   correzione 3b si disattiva silenziosamente e vale 0 — ma non e'
   l'output completo del progetto originale.

Tutto il resto della pipeline (`pricing/modello_prezzo.py`,
`pricing/verdetto.py`, `server/build_giocatori.py`,
`server/build_storico_arricchito.py`) e' incluso e funzionante, e i loro
percorsi di input/output sono parametrizzabili da riga di comando (vedi
`--help` su ciascuno, o `examples/config.example.toml`).

## 4. Dati sintetici per provare il sistema subito

`examples/sample_data/generate_sample_data.py` genera 80 giocatori
**completamente inventati** (nessun nome, statistica o quotazione reale) ed
esegue su di loro la pipeline vera (`pricing/modello_prezzo.py` +
`pricing/verdetto.py`), producendo:

- `predizioni_esempio.csv` — input di esempio per la pipeline di pricing;
- `giocatori_esempio.xlsx` — database pronto nello schema che
  `server/player_db.py` si aspetta.

Per provare il server senza dati reali:

```bash
python examples/sample_data/generate_sample_data.py   # rigenera i file, opzionale: sono gia' inclusi
cp examples/sample_data/giocatori_esempio.xlsx server/giocatori_2026_27.xlsx
cd server && ASTA_PASSWORD=demo python app.py
```

I numeri che ne escono non sono realistici (la lega sintetica ha 80
giocatori invece di ~500), ma bastano a vedere il meccanismo: fasce, quote
di reparto, verdetti, e le pagine `static/phone.html` / `static/login.html`
che si aprono su `http://localhost:8000`.

## 5. Licenza dei dati

Il **codice** di questo repository e' MIT (vedi `LICENSE`). I **dati**
scaricati da fantacalcio.it non sono coperti da questa licenza e non sono
inclusi: ricostruiscili con le istruzioni sopra. `examples/sample_data/` e'
tutto sintetico ed e' quindi coperto anch'esso da MIT.
