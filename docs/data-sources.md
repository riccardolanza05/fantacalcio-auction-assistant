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
| `Quotazioni_Fantacalcio_Stagione_AAAA_AA.xlsx` | fantacalcio.it → Quotazioni | `pricing/model/train_model.py`, `server/build_storico_arricchito.py` |
| `Statistiche_Fantacalcio_Stagione_AAAA_AA.xlsx` | fantacalcio.it → Statistiche | `server/build_giocatori.py`, `server/build_storico_arricchito.py` |
| `voti_AAAA-AA_gNN.xlsx` (una per giornata) | fantacalcio.it → Voti (o scaricali con `pricing/votes/scraper_voti.py`) | `pricing/votes/` → `voti_aggregato_v3.csv` → `pricing/model/` |
| `probabili-formazioni-serie-a` (HTML) | https://www.fantacalcio.it/probabili-formazioni-serie-a — tasto destro → "Salva pagina", salvata **senza estensione** nella cartella `server/` | `server/build_giocatori.py` (infortuni e titolarita'), opzionalmente `pricing/model/train_model.py` (titolarita' futura, vedi sezione 3) |
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

## 3. La pipeline e' ora riproducibile end-to-end

Le prime versioni di questo repository segnalavano il modello ML di
produzione attesa e `Hreg.pkl` come pezzi mancanti. Non lo sono piu':
entrambi gli script che li generano sono stati **recuperati dalla
trascrizione della sessione originale** in cui il modello e' stato
sviluppato (salvata integralmente in Basic Memory, l'archivio di note
persistenti dell'autore) e sono ora in `pricing/model/`:

- `pricing/model/build_hreg.py` → produce `Hreg.pkl` (shrinkage gerarchico
  per la regressione alla media, strato 3b);
- `pricing/model/train_model.py` → addestra l'`HistGradientBoostingRegressor`
  con validazione temporale e regressione quantile conformalizzata, e
  produce le predizioni (`produzione_attesa`, `p10`, `p90`) che sono
  l'input di `pricing/modello_prezzo.py`.

Prima di includerli sono stati **rieseguiti sui dati reali** per
verificare che riproducessero i risultati del progetto originale, non solo
che avessero un aspetto plausibile:

| Numero verificato | Sessione originale | Rieseguito ora |
|---|---|---|
| Giocatori con storico in `Hreg.pkl` | 2274 | 2274 (identico) |
| Correzione conformal (fantapunti) | 13.8 | 13.8 (identico) |
| R² medio in validazione temporale | 0.467 (dossier) | ~0.45-0.47 |

Dettagli, uso e limiti residui in `pricing/model/README.md`. La pipeline
per costruire il loro input (`voti_aggregato_v3.csv`, dai voti
giornata-per-giornata) e' in `pricing/votes/` — anch'essa recuperata: gli
script (`scraper_voti.py`, `parse_voti.py`, `aggrega_voti_v3.py`,
`regole_lega.py`, ecc.) non erano nella cartella originale del progetto ma
sono stati ritrovati intatti in un'altra cartella della macchina
dell'autore.

**Quello che resta genuinamente assente:**

1. **Una titolarita' futura fresca** per `train_model.py`
   (`--probabili-json`): e' uno snapshot specifico della settimana in cui
   viene generato, non un artefatto statico. Senza, quella singola feature
   e' trattata come sconosciuta (pct=0) — il resto del modello funziona.
   Vedi `pricing/model/README.md` per come ricostruirlo dalla pagina
   probabili-formazioni-serie-a.
2. **SHAP non e' mai stato effettivamente implementato**, nonostante la
   documentazione precedente di questo progetto lo elencasse come fatto:
   nella trascrizione della sessione originale compare solo come intenzione
   dichiarata, mai come codice eseguito. Aggiungerlo e' immediato ma resta
   da fare.

Tutta la pipeline (`pricing/votes/`, `pricing/model/`,
`pricing/modello_prezzo.py`, `pricing/verdetto.py`,
`server/build_giocatori.py`, `server/build_storico_arricchito.py`) ha
percorsi di input/output parametrizzabili da riga di comando (vedi
`--help` su ciascuno script, o `examples/config.example.toml`).

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
