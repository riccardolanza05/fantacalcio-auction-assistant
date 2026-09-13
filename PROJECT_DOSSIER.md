# Fantacalcio Auction Assistant — Dossier di progetto / Project dossier

**Versione documento:** 1.0 — 13 settembre 2026
**Percorso del progetto sulla macchina dell'autore:** `C:\Users\<utente>\Desktop\Fantacalcio\`
**Stato:** funzionante e usato in asta reale; non ancora pubblicato.
**Destinazione:** questo file è la mappa completa del progetto, pensata per essere letta da un agente
che deve costruire una repository Git open source a partire dal materiale esistente.

Il documento è **bilingue**: la Parte I è in italiano, la Parte II è la traduzione integrale in inglese.
Le due parti contengono le stesse informazioni; se una diverge dall'altra, fa fede la Parte I.

> **Nota importante sul codice sorgente.** Tutti i file `.py` e `.js` del progetto hanno commenti,
> docstring e **nomi di variabili in italiano** (`prezzo_modello`, `fascia`, `correzione`, `scarsita`,
> `verdetto`, `livello_rimpiazzo`…). **Questo non va cambiato.** Non tradurre il codice, non rinominare
> le variabili, non riscrivere i commenti in inglese: il codice resta com'è. La documentazione (README,
> questo dossier, l'eventuale sito) è il livello in cui si fornisce l'inglese. Chi legge la repo troverà
> un glossario IT→EN alla fine di ciascuna parte.

> **Nota sullo stato di questo documento.** Questo dossier e' stato scritto
> come istruzioni per l'agente che ha costruito la repository che stai
> leggendo ora: e' un documento storico/di progettazione, non la
> descrizione dello stato attuale. Per lo stato aggiornato vedi
> [README.md](README.md) / [README.it.md](README.it.md) e
> [docs/](docs/). In particolare, rispetto a quanto scritto qui sotto:
> - i percorsi hard-coded (sezione 11.6) sono stati sostituiti con
>   argomenti da riga di comando in tutti gli script;
> - la password (sezione 12.2) e' stata rimossa dal codice: va impostata
>   con la variabile d'ambiente obbligatoria `ASTA_PASSWORD`;
> - `predizioni_2026_27_v2` e `probabili-formazioni-serie-a`, elencati
>   sotto come assenti (sezione 11), sono stati ritrovati sul disco
>   dell'autore;
> - lo script di training del modello ML e `Hreg.pkl`, anch'essi elencati
>   sotto come assenti, sono stati **recuperati dalla trascrizione della
>   sessione originale** (salvata in Basic Memory) e rieseguiti sui dati
>   reali per validarli: sono ora `pricing/model/train_model.py` e
>   `pricing/model/build_hreg.py`. La stessa trascrizione ha rivelato che
>   **SHAP non era mai stato implementato** (solo dichiarato come
>   intenzione), contrariamente a quanto affermato in questo documento;
> - la pipeline per costruire `voti_aggregato_v3.csv` dai voti grezzi
>   (scraper, parser, aggregatore, regole di punteggio) e' stata trovata
>   intatta in un'altra cartella dell'autore e recuperata in
>   `pricing/votes/`;
> - la struttura di cartelle e' quella descritta in sezione 12.1, con
>   `Modello_prezzi/` rinominato in `pricing/` (che ora include anche
>   `pricing/model/` e `pricing/votes/`) e gli script browser spostati in
>   `browser/`.
> Il resto del documento (metodologia, storia dello sviluppo, inventario)
> e' invariato ed e' la fonte di dettaglio piu' completa disponibile.

---

# PARTE I — ITALIANO

## 0. Come usare questo documento

Se sei un agente incaricato di creare la repository:

1. Leggi la sezione **10 (Inventario dei file)**: dice esattamente quale file serve, dove si trova e a cosa serve.
2. Leggi la sezione **11 (Cosa manca)**: alcuni artefatti citati dal codice **non sono sul disco** e la
   pipeline non è riproducibile end-to-end senza di essi. Vanno o ricostruiti o dichiarati come mancanti.
3. Leggi la sezione **12 (Preparare la repo)**: contiene la struttura di cartelle consigliata, il
   `.gitignore`, i segreti da rimuovere **prima** del primo commit e il problema di licenza dei dati.
4. Non toccare la lingua del codice (vedi nota in testa e sezione 13).

---

## 1. L'idea originale

Il fantacalcio all'italiana in modalità **Classic** si gioca con un'asta iniziale: ogni squadra ha un
budget fisso in crediti e compra i giocatori al rialzo, uno alla volta, finché tutti i ruoli sono coperti.
L'asta è il momento in cui si decide gran parte della stagione, ma si svolge in tempo reale, sotto pressione,
e le decisioni vengono prese "a sentimento" o guardando le liste di quotazioni ufficiali che tutti hanno.

L'idea di partenza era: **provare a vincere il fantacalcio con la matematica.** Più precisamente, rispondere
in modo quantitativo e verificabile a tre domande che in asta ci si pone di continuo:

1. **Quanto vale davvero questo giocatore**, in crediti, nella *mia* lega (non in astratto)?
2. **Al prezzo a cui sta andando adesso, conviene o no?** Cioè: è sopravvalutato o sottovalutato?
3. **Quanto sono disposto a spingermi**, considerando che le alternative si stanno esaurendo mentre l'asta
   procede?

Il progetto è quindi cresciuto in due metà complementari:

- una **pipeline statistica offline** che produce, prima dell'asta, una valutazione calibrata di ogni
  giocatore (prezzo atteso + intervallo di incertezza + verdetto);
- un **assistente live** che, durante l'asta, legge la pagina d'asta dal browser del PC e manda al telefono
  in tempo reale il prezzo consigliato aggiornato, i budget di tutti gli avversari e lo stato della propria rosa.

Il vincolo di progetto, ribadito ovunque nel codice, è: **nessuno strato deve poter stravolgere il precedente.**
Il mercato (l'FVM di fantacalcio.it) ha sempre l'ultima parola sulla *forma* della curva dei prezzi; il modello
statistico può spostare i prezzi, non reinventarli. Questa è una scelta metodologica, non una limitazione
tecnica, ed è la ragione per cui il sistema si comporta in modo prevedibile anche quando il modello sbaglia.

---

## 2. Il contesto: la lega

| Parametro | Valore |
|---|---|
| Nome lega | Lega Abendosa (fantacalcio.it) |
| Squadra dell'autore | NapoLanza |
| Numero squadre | 10 (in precedenza 12) |
| Budget per squadra | 1000 crediti |
| Budget complessivo lega | 10.000 crediti |
| Modalità | Classic |
| Rosa per squadra | 3 P / 8 D / 8 C / 6 A (25 giocatori) |
| Slot totali in lega | 30 P / 80 D / 80 C / 60 A (250) |
| Piattaforma d'asta | FantaAsta Live (`fanta-asta-live.fantacalcio.it`), servita in HTTPS |

Il passaggio da 12 a 10 squadre è rilevante: parte del codice è ancora tarata su 12 (vedi sezione 11).

**Quote di budget per reparto.** Il modello impone che la spesa complessiva della lega si ripartisca
**10% portieri / 20% difensori / 30% centrocampisti / 40% attaccanti**. Questa ripartizione era il *prior*
dell'autore ed è stata poi confermata empiricamente sui prezzi realmente pagati. È il parametro più
importante del sistema, perché è ciò che rende la valutazione **dipendente dal ruolo**: lo stesso rendimento
atteso vale diversamente in porta e in attacco, perché i reparti competono per fette di budget diverse.

---

## 3. Le due metà del sistema

```
                    ┌──────────────────────────────────────────────┐
   DATI STORICI     │  PIPELINE OFFLINE (prima dell'asta)          │
   2015-16 → 2026-27│                                              │
   Statistiche      │  modello ML produzione attesa (+ p10/p90)    │
   Quotazioni       │        ↓                                     │
   Voti per giornata│  modello_prezzo.py   (strati 1-2-3)          │
                    │        ↓  prezzi_2026_27.csv                 │
                    │  verdetto.py         (sopra/sottovalutato)   │
                    │        ↓  verdetto_2026_27.csv               │
                    │  build_giocatori.py  (merge + infortuni)     │
                    │        ↓                                     │
                    │     giocatori_2026_27.xlsx  ◄── il database  │
                    └──────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴──────────────────────────┐
                    │  ASSISTENTE LIVE (durante l'asta)            │
                    │                                              │
  pagina d'asta ──► asta-live.user.js (Tampermonkey, sul PC)       │
  (HTTPS, Angular)  │  POST /ingest                                │
                    │        ↓                                     │
                    │  app.py (FastAPI, localhost:8000)            │
                    │   ├── player_db.py    lookup giocatore       │
                    │   ├── vorp_live.py    STRATO 4 (scarsità)    │
                    │   ├── live_state.py   stato asta e rose      │
                    │   ├── storico_prezzi.py  prezzi asta 2025-26 │
                    │   └── simili.py       profili per analogia   │
                    │        ↓ WebSocket                           │
                    │  static/phone.html  ◄── telefono, stessa WiFi│
                    └──────────────────────────────────────────────┘
```

---

## 4. Storia dello sviluppo, fase per fase

Questa sezione è importante perché **molte scelte del progetto sono reazioni a un fallimento concreto**.
Chi legge la repo deve capire perché una soluzione apparentemente più elegante è stata scartata.

### Fase 1 — Costruzione del panel storico
Raccolta dei file ufficiali di fantacalcio.it: `Statistiche` e `Quotazioni` per 12 stagioni (2015-16 → 2026-27),
più i **voti giornata per giornata** per 11 stagioni (2015-16 → 2025-26, 38 giornate ciascuna = 418 file).
I dati vengono uniti in un pannello longitudinale giocatore × stagione, chiave di join l'`Id` fantacalcio.it.

Problemi risolti in questa fase (tutti verificati sui dati, non ipotizzati):
- i file dei **voti** usano `Cod.` come identificativo, non `Id`;
- un **asterisco** accanto al voto indica *voto d'ufficio* (spezzone irrilevante) e **non conta come presenza**:
  la regola è stata validata al 99,4% di accuratezza contro le presenze ufficiali;
- gli **allenatori** (ruolo `ALL`) compaiono nei file dei voti e vanno filtrati;
- l'API delle giornate restituisce **401 a richieste esterne** anche con cookie validi, quindi lo scarico
  si è dovuto fare con un downloader JavaScript eseguito nel browser;
- i file generati via PowerShell contengono **BOM**: richiedono `utf-8-sig` più sanitizzazione latin-1;
- il campo `Gf` delle `Statistiche` **comprende già i gol su rigore** (a differenza dei file voti dove i
  rigori sono separati): sommare `R+` li contava due volte. Bug trovato e corretto.

### Fase 2 — Modello di produzione attesa
Modello supervisionato che stima, per ogni giocatore, la **produzione attesa della stagione** in fantapunti.

- Algoritmo: **HistGradientBoostingRegressor** (gradient boosting su istogrammi, scikit-learn).
- Validazione: **cross-validation temporale** (ogni stagione predetta usando solo il proprio passato).
- Performance: **R² ≈ 0,467** in validazione temporale.
- Intervalli: **regressione quantile conformalizzata** per p10/p90, con **copertura empirica 81,6%** su dati
  mai visti (nominale 80%). Gli intervalli sono quindi *calibrati*, non decorativi: è ciò che permette di
  parlare di verdetti "robusti" (sezione 7).
- Interpretabilità: **valori SHAP**.
- Scelta metodologica: gradient boosting batte le reti neurali su dati tabellari di questa dimensione.
  Questa non è un'opinione di comodo, è il motivo esplicito per cui non è stata usata una rete.
- **Titolarità**: la percentuale di titolarità dalle probabili formazioni viene mappata sui tassi di
  presenza storici, per convertire una stima qualitativa ("è il titolare") in un moltiplicatore di minuti.

### Fase 3 — Dal rendimento al prezzo: il modello a 4 strati
È il cuore concettuale del progetto (dettaglio completo in sezione 6). L'intuizione: *non si deve costruire
il prezzo da zero*. L'FVM (Fantamedia Valore di Mercato) di fantacalcio.it è già calibrato sul mercato reale
e contiene informazione che nessun modello statistico ha (aspettative, mercato estivo, hype). Quindi l'FVM
fornisce la **forma** della curva; il modello corregge **il livello**, dentro limiti fissati a priori.

### Fase 4 — Regressione alla media
Aggiunta di uno strato (3b) che penalizza chi nell'ultima stagione ha fatto meglio del proprio livello storico.
I **coefficienti di persistenza** sono stati stimati sullo storico 2015-16 → 2025-26 (n = 2950 giocatori con
almeno 10 presenze) e sono fortemente dipendenti dal ruolo:

| Ruolo | Coefficiente di persistenza |
|---|---|
| P (portieri) | **−0,08** |
| D (difensori) | 0,705 |
| C (centrocampisti) | 0,904 |
| A (attaccanti) | 0,810 |

Il portiere è il caso estremo: una sua annata sopra il proprio livello **non si ripete affatto** (coefficiente
negativo). È uno dei risultati empirici più utili del progetto, e giustifica da solo il tetto di correzione
bassissimo imposto ai portieri.

### Fase 5 — Il verdetto
Sistema che classifica ogni giocatore come *sottovalutato / in linea / sopravvalutato* (sezione 7).
Qui c'è stato **il fallimento più istruttivo del progetto**: la prima versione usava come riferimento un
modello comportamentale addestrato su **una sola asta reale**. Risultato: verdetti completamente instabili,
**deviazione standard ≈ 241%**. Sostituendo il riferimento con l'FVM riscalato per quote di reparto
(strati 1+2) la deviazione standard è scesa a **≈ 10,9%**. Lezione: *il riferimento conta più del modello*.

Successivamente il verdetto è diventato **doppio**, perché le due domande sono diverse a seconda della fascia:
- `verdetto_base` — confronto col riferimento del modello, usato su **top, semitop, terza fascia**, dove il
  budget c'è davvero e il confronto è pulito;
- `verdetto_lega` — confronto con quanto la lega paga davvero, usato su **quarta fascia e minori**, dove il
  prezzo è guidato dall'obbligo di riempire gli slot più che dal valore.

### Fase 6 — L'assistente live e il tracker Bayesiano (poi rimosso)
Prima versione dello strato 4: un **tracker Bayesiano Normal-Inverse-Gamma** che aggiornava le stime a ogni
acquisto osservato. Fallimento: lavorando su un fair value **VORP puro** (non ancorato all'FVM) produceva
moltiplicatori 6-10× sui giocatori di coda, cioè prezzi assurdi proprio dove l'asta è più affollata.
Sostituito dall'approccio a **composizione/scarsità** descritto in sezione 8.

Conclusione metodologica registrata nel progetto: un modello **gerarchico bayesiano completo è più adatto
offline** che live. Le ragioni concrete sono la latenza e la scarsità di osservazioni per sottogruppo durante
un'asta; live funzionano meglio fattori di correzione per ruolo/fascia aggiornati incrementalmente, che
approssimano uno shrinkage bayesiano empirico.

### Fase 7 — Integrazione col browser e debugging del DOM
Numerosi problemi risolti, ciascuno con una soluzione precisa (dettagli in sezione 9):
- **WebSocket bloccata**: la pagina d'asta è HTTPS, `ws://localhost` è contenuto misto; il costruttore
  `WebSocket` lancia un'eccezione **sincrona** che uccide l'intero script prima ancora dell'overlay.
  Soluzione: `GM_xmlhttpRequest` (contesto privilegiato dell'estensione) verso `POST /ingest`.
- **Identità delle squadre**: rinominare una rosa creava una squadra fantasma. Soluzione: UUID stabile del
  viewport DOM, con fallback su sovrapposizione rosa ≥60% e poi sul nome.
- **Rilevamento acquisti**: attribuire l'acquisto al "giocatore in vetrina" falliva perché tra l'assegnazione
  e la lettura successiva la vetrina si svuota. Soluzione: confronto delle **righe rosa** tra snapshot.
- **Budget accumulato invece che ricostruito**: un giocatore rimosso lasciava i crediti spesi per sempre.
  Soluzione: la rosa viene **ricostruita da ogni snapshot**, non accumulata.
- **Parser infortuni**: un unico regex sull'intera pagina appaiava il nome di una voce con la descrizione
  della successiva. Soluzione: isolare prima il singolo `<li>`.
- **Omonimi**: il match per cognome segnalava infortunati sbagliati (due Pessina, due Martinez). Soluzione:
  il fallback per cognome si applica **solo quando il cognome è univoco nel pool**.

---

## 5. I dati

### 5.1 Fonti
Tutti i dati grezzi provengono da **fantacalcio.it** (sezione statistiche/quotazioni ufficiali) e dalla pagina
pubblica delle **probabili formazioni**. I prezzi d'asta storici provengono dall'export della propria lega.

### 5.2 File presenti sul disco

| Cartella | Contenuto | Quantità |
|---|---|---|
| `Dati/Quotazioni/` | `Quotazioni_Fantacalcio_Stagione_YYYY_YY.xlsx` | 12 file (2015-16 → 2026-27) |
| `Dati/Statistiche/` | `Statistiche_Fantacalcio_Stagione_YYYY_YY.xlsx` | 12 file (2015-16 → 2026-27) |
| `Dati/Voti/` | `voti_YYYY-YY_gNN.xlsx` | 418 file (11 stagioni × 38 giornate) |

**Colonne rilevanti nelle Quotazioni**: `Id`, `Nome`, `Squadra`, `R` (ruolo), `Qt.A` (quotazione attuale),
`Qt.I` (quotazione iniziale), `FVM`. L'header è sulla **riga 2**, i dati dalla **riga 3**, foglio `Tutti`.

**Colonne rilevanti nelle Statistiche**: `Nome`, `Squadra`, `Pv` (presenze), `Fm` (fantamedia), `Gf` (gol
fatti, **rigori inclusi**), `Gs` (gol subiti), `Rp` (rigori parati), `Ass` (assist). Stessa struttura di header.

**File dei voti**: identificativo `Cod.`, asterisco = voto d'ufficio (non presenza), righe con ruolo `ALL` da filtrare.

### 5.3 Dati che NON stanno nei file ufficiali e vanno forniti a parte
- **Clean sheet dei portieri**: i file `Statistiche` riportano i gol subiti ma non le partite senza subire.
  Il dato è stato inserito a mano in `server/clean_sheet_2025_26.py` come lista di tuple
  `(nome, sigla squadra, clean sheet)`. I portieri non in lista hanno 0 clean sheet **solo se hanno giocato**:
  chi non ha presenze ha valore `None`, che è diverso da "zero clean sheet in 38 partite".
- **Infortuni e titolarità**: si ricavano dalla pagina `probabili-formazioni-serie-a` salvata come HTML e
  messa in `server/`. Va risalvata prima di ogni aggiornamento.

### 5.4 Artefatti derivati

| File | Prodotto da | Contenuto |
|---|---|---|
| `Modello_prezzi/prezzi_2026_27.csv` | `modello_prezzo.py` | 501 righe — prezzo per strati 1-3 |
| `Modello_prezzi/verdetto_2026_27.csv` | `verdetto.py` (versione successiva a quella su disco) | 501 righe — verdetto |
| `server/giocatori_2026_27.xlsx` | `build_giocatori.py` | **517 giocatori** — il database che usa il server |
| `server/storico_asta_2025_26.xlsx` | `build_storico_arricchito.py` | 268 acquisti arricchiti con profilo |
| `server/Rose_lega-abendosa.xlsx` | export della lega | 268 acquisti dell'asta 2025-26 con prezzo pagato |

**Attenzione (verificato):** i due CSV in `Modello_prezzi/` sono di una **generazione precedente** rispetto a
`giocatori_2026_27.xlsx`. Il CSV ha 501 giocatori, l'xlsx ne ha 517; 275 FVM su 484 in comune sono diversi;
402 prezzi su 484 sono diversi. Inoltre il CSV ha un verdetto **singolo**, mentre `build_giocatori.py` si
aspetta le colonne del verdetto **doppio** (`verdetto_base`/`verdetto_lega`), che infatti sono presenti
nell'xlsx. Conclusione: l'xlsx è stato costruito da versioni più recenti dei CSV, **non salvate sul disco**.

### 5.5 Composizione del database finale (`giocatori_2026_27.xlsx`, verificata)
- 517 giocatori: 62 P, 184 D, 184 C, 87 A
- verdetti: 220 SOTTOVALUTATO, 170 SOPRAVVALUTATO, 127 in linea
- riferimento usato: 115 "modello" (fasce alte), 402 "lega" (code)
- 40 giocatori segnalati come infortunati
- 34 colonne, fra cui: `Id, Nome, Squadra, Ruolo, fascia, FVM, QtI, pct_titolarita, produzione_attesa,
  p10, p90, prezzo_base, correzione, prezzo_modello, prezzo_mercato, scarto_pct, verdetto, rif_verdetto,
  verdetto_base, scarto_base_pct, verdetto_lega, scarto_lega_pct, div_modello, div_regressione,
  correzione_fm, gol_2025_26, assist_2025_26, gol_subiti_2025_26, rigori_parati_2025_26,
  clean_sheet_2025_26, presenze_2025_26, fm_media_2025_26, infortunato, nota_infortunio`

---

## 6. Il modello di prezzo a 4 strati

Implementazione: `Modello_prezzi/modello_prezzo.py` (strati 1-3) e `server/vorp_live.py` (strato 4).
Gli strati sono in **ordine di autorità decrescente**: ognuno può correggere il precedente solo entro limiti
prefissati. È il principio architetturale del progetto.

### Strato 1 — Ancora di mercato (FVM)
L'FVM di fantacalcio.it è già calibrato: la somma sui giocatori effettivamente acquistati vale circa 12.334
crediti su una lega da 12 × 1000. L'FVM fornisce la **forma** della curva dei prezzi — cioè la struttura a
fasce — che quindi non va reinventata.

### Strato 2 — Quote per reparto (10/20/30/40)
L'FVM grezzo implica una ripartizione **5,7 / 20,1 / 34,8 / 39,4 %** fra P/D/C/A. Si riscala l'FVM di ciascun
ruolo perché la somma sugli slot realmente acquistati centri la quota voluta:

```
per ogni ruolo R:
    draftati   = i primi SLOT[R] giocatori per FVM
    residuo    = BUDGET_TOT * QUOTA[R] − SLOT[R] * PREZZO_MIN
    k          = residuo / somma_FVM(draftati)
    base_i     = PREZZO_MIN + FVM_i * k          (PREZZO_MIN = 1 credito)
```

Questo è ciò che rende la valutazione **dipendente dal ruolo**.

**Fasce.** Dentro ciascun ruolo i giocatori sono ordinati per FVM e divisi in cinque fasce
(`top, semitop, terza, quarta, minori`), con numerosità:

| Ruolo | top | semitop | terza | quarta | minori |
|---|---|---|---|---|---|
| P | 8 | 5 | 5 | 5 | resto |
| D | 11 | 12 | 15 | 15 | resto |
| C | 6 | 12 | 15 | 15 | resto |
| A | 6 | 8 | 12 | 12 | resto |

Dettaglio non ovvio: nella coda l'FVM **non discrimina** (nel 2025-26 tutti i portieri dal 24° in giù avevano
FVM = 1), quindi l'ordinamento usa una **chiave composta**: rango FVM come criterio primario × 1000, più il
rango della produzione attesa come spareggio.

### Strato 3 — Correzione statistica
Due componenti, entrambe dentro lo stesso tetto.

**3a — divergenza modello/mercato.** Si confronta il *percentile* di produzione attesa con il *percentile*
FVM, **dentro il ruolo**: `div_modello = pct_modello − pct_mercato`. Usare i percentili anziché i valori
assoluti rende il confronto immune alle scale diverse di ruoli e stagioni.

**3b — regressione alla media.** Lo scarto di fantamedia rispetto al livello storico del giocatore viene
standardizzato per ruolo, troncato a ±2 deviazioni standard e pesato:

```
div_regressione = clip(correzione_fm / sd_ruolo, −2, +2) * 0.25 * PESO_REGRESSIONE   (PESO_REGRESSIONE = 0.5)
```

La `correzione_fm` viene da un file `Hreg.pkl` (shrinkage gerarchico: `fm_storica`, `fm_shrunk`, `fm_L1`,
`n_stagioni`). Se il file manca, lo strato 3b si disattiva silenziosamente e vale 0.

**Doppio tetto.** La correzione totale è limitata da un tetto **assoluto per ruolo** e da un tetto **relativo**:

```
tetto      = min( TETTO_CORREZIONE[ruolo] , base * 0.30 )
correzione = clip( divergenza * 2.0 * tetto , −tetto , +tetto )
prezzo     = base + correzione
```

| Ruolo | Tetto assoluto |
|---|---|
| P | 6 crediti |
| D | 12 crediti |
| C | 20 crediti |
| A | 30 crediti |

La logica del tetto: un errore di 5 crediti su un portiere è grave quanto un errore di 30 su un attaccante.

**Normalizzazione iterativa.** I giocatori di quinta fascia hanno un tetto di prezzo calibrato sul
**90° percentile dei prezzi realmente pagati** nell'asta di agosto 2025 (fasce assegnate per `Qt.I`, immune
al calo di quotazione durante la stagione): **P 5, D 22, C 22, A 23 crediti**. Il clip dei minori sottrae
budget, che va riassorbito dalle fasce superiori, il che può richiedere un nuovo clip: la funzione
`normalizza()` itera fino a 30 volte, uscendo quando lo scarto dalle quote scende sotto 1 credito.
Nota antiretorica registrata nel codice: la regola "i minori costano 1-5 crediti" **vale solo per i portieri**;
negli altri reparti la coda è molto più cara.

**Controllo di continuità.** Una funzione dedicata verifica che non ci siano salti tra fasce contigue:
l'ultimo `top` deve costare quanto il primo `semitop`. Le fasce descrivono **come si compongono le rose**,
non scalini di prezzo. Il risultato registrato è che la continuità esiste: non c'è omogeneità di prezzo
*dentro* la fascia, ma continuità *tra* fasce adiacenti.

### Strato 4 — VORP/scarsità live
Vedi sezione 8. È la correzione più debole della catena, per costruzione.

---

## 7. Il verdetto di valutazione

Implementazione: `Modello_prezzi/verdetto.py` (versione su disco) e colonne `verdetto*` in
`giocatori_2026_27.xlsx` (versione più recente, a doppio riferimento).

**Domanda:** questo giocatore, al prezzo a cui sta andando, conviene?

Il metodo evita due trappole esplicitamente dichiarate nel codice:

1. **Non si confrontano crediti fra ruoli diversi.** Un attaccante da 100 crediti e un portiere da 100 non
   sono paragonabili. Il confronto è **sempre dentro il ruolo**.
2. **Non si usa solo la stima puntuale.** Il modello ha intervalli conformi calibrati: il verdetto è
   dichiarato **robusto** solo se regge anche usando l'estremo sfavorevole dell'intervallo.

**Metrica: rendimento per credito**, normalizzato sulla mediana del proprio ruolo calcolata **solo sui
giocatori che verranno effettivamente acquistati** (i primi `SLOT[R]` per prezzo):

```
indice      = (produzione_attesa / prezzo) / mediana_ruolo
indice_p10  = (p10 / prezzo) / mediana_ruolo
indice_p90  = (p90 / prezzo) / mediana_ruolo
```

**Soglie:** `indice ≥ 1,15` → sottovalutato; `indice ≤ 0,85` → sopravvalutato; in mezzo → valutato correttamente.
Il verdetto diventa "robusto" se `indice_p10 ≥ 1` (sottovalutato anche nello scenario sfavorevole) oppure
`indice_p90 ≤ 1` (sopravvalutato anche in quello favorevole).

Vengono anche calcolati il **prezzo di indifferenza** (il prezzo al quale il giocatore renderebbe esattamente
come la mediana del ruolo) e il **margine** = prezzo di indifferenza − prezzo. È il numero più operativo di
tutti: dice di quanti crediti puoi salire restando in vantaggio.

### Calibrazione della soglia (backtest)
Backtest su **6 stagioni** (2019-20 → 2024-25), ciascuna predetta usando **solo il proprio passato**.
Testate le soglie di scarto 10 / 15 / 20 / 25 / 30%:

- la separazione tra sottovalutati e sopravvalutati cresce **quasi linearmente** con la soglia
  (da 2,40× a 3,06×): **non esiste un taglio "naturale"**, è un compromesso tra separazione e copertura;
- si è scelto **10%** perché è la soglia con minore variabilità del segnale fra stagioni
  (dev. std del rapporto **0,52**, contro 0,60 al 15% e fino a 0,75 al 30%) e perché copre **l'83%** dei
  giocatori contro il 51-73% delle soglie più alte, lasciando senza verdetto il minor numero possibile di casi.

**Risultato del backtest a quella soglia:** i giocatori classificati sottovalutati hanno prodotto **1,86×**
e i sopravvalutati **0,77×** la produzione poi realmente realizzata, **in tutte e 6 le stagioni testate**.
La correlazione di rango (Spearman) fra prezzo del modello e resa effettiva varia fra **0,43 e 0,74** a
seconda della stagione.

### Doppio riferimento
Nella versione finale (quella dentro `giocatori_2026_27.xlsx`) il verdetto è calcolato due volte:

| Fascia | Riferimento usato | Perché |
|---|---|---|
| top, semitop, terza | `verdetto_base` / `scarto_base_pct` | il budget c'è davvero, il confronto col riferimento del modello è pulito |
| quarta, minori | `verdetto_lega` / `scarto_lega_pct` | coglie la dinamica di fine asta sulle code, dove il prezzo lo fa l'obbligo di riempire gli slot |

Il database traccia quale riferimento è stato usato (`rif_verdetto` = `modello` | `lega`), e il telefono lo
mostra, perché è un'informazione che serve a sapere **quanto fidarsi del numero**.

Avvertenza registrata: sulle code gli scarti percentuali diventano enormi (+280%, +560%) perché si dividono
per prezzi di pochi crediti. Su un giocatore da 3 crediti un +500% vale 15 crediti: non è un affare da
rincorrere. Per questo su quelle fasce conta più il verdetto che la percentuale.

---

## 8. Strato 4: la correzione di scarsità live

Implementazione: `server/vorp_live.py`, classe `VorpLive`.

**Domanda a cui risponde il VORP:** *esistono ancora alternative valide per questo giocatore?*
La risposta non dipende da quanti giocatori restano in assoluto, ma da **come è composto ciò che resta**.

### Livello di rimpiazzo
Ricalcolato a ogni acquisto: è la produzione attesa del giocatore che occuperebbe l'**ultimo slot da titolare
ancora libero** del ruolo. A inizio asta il rimpiazzo di un attaccante è il 60° miglior attaccante
(6 × 10 squadre); man mano che gli attaccanti vengono presi, il rimpiazzo peggiora e il vantaggio dei
rimanenti cresce. `vantaggio_vorp = produzione_attesa − livello_rimpiazzo`.

### Scarsità: due componenti
**Composizione (peso 0,75)** — quale quota del blocco alto ancora libero (top + semitop + terza) è fatta di
giocatori **almeno pari** a lui. Se restano 10 attaccanti di fascia medio-alta e uno solo è top, quel top non
ha alternative. Se i top sono 5 su 10, di alternative ce ne sono e il prezzo non deve salire. Il valore è
**normalizzato sulla quota di inizio asta**: senza questa normalizzazione i top risulterebbero scarsi già a
mercato intatto, visto che sono per costruzione una minoranza.

```
composizione = max(0, 1 − quota_ora / quota_inizio)
```

**Deplezione (peso 0,25)** — quanti giocatori di livello pari o superiore sono già stati presi in assoluto.
Serve al caso "restano 5 top su 10": in proporzione ce ne sono ancora tanti, ma il reparto si sta svuotando
e un piccolo premio è giustificato.

```
scarsita = 0.75 * composizione + 0.25 * deplezione        (poi troncata in [0, 1])
```

### Correzione finale
```
tetto      = min( TETTO_CORREZIONE[ruolo] , prezzo_base * 0.30 )     # stessi tetti dello strato 3
grezza     = tanh( vantaggio_vorp / 50 ) * tetto                      # satura dolcemente
correzione = clip( grezza * scarsita , −tetto , +tetto )
```

Tre freni deliberati: il tetto per ruolo, la saturazione `tanh` (un vantaggio enorme **non** produce una
correzione enorme) e il fattore scarsità (finché ci sono alternative, la correzione tende a zero).

**Comportamento verificato sugli attaccanti** (dal test riproducibile in fondo a `vorp_live.py`):

| Scenario | top | semitop | terza |
|---|---|---|---|
| inizio asta (6/8/12 liberi) | +0,0 | +0,0 | +0,0 |
| restano 1 top, 2 semitop, 7 terza | **+17,2** | +14,5 | +2,6 |
| restano 5 top e 5 semitop | +1,1 | +2,0 | — |

### Deriva di mercato
Se la lega sta pagando sistematicamente sopra il modello, la stima si sposta. Si accumulano i
**log-rapporti** `log(prezzo_pagato / prezzo_modello)` per ruolo; la media viene smorzata con peso
`n / (n + 5)` e troncata a **±30%**:

```
deriva = exp( clip( media_log * n/(n+5) , log(0.7) , log(1.3) ) )
prezzo_consigliato = max(1, (prezzo_modello + correzione_strato4) * deriva)
```

Lo smorzamento evita di inseguire il rumore dei primi acquisti; il tetto evita che un'asta anomala travolga
il modello.

Nota di correttezza: un'assegnazione il cui costo **non è deducibile con certezza** (due acquisti nello stesso
intervallo di polling) viene mostrata sul telefono ma **non** passata al motore, per non inquinarlo con un
prezzo indovinato. Un giocatore rimosso per errore torna disponibile nel calcolo della scarsità (`libera()`).

---

## 9. Architettura software

### 9.1 Server — `server/app.py` (FastAPI, `0.0.0.0:8000`)

| Endpoint | Metodo | Funzione |
|---|---|---|
| `/login` | POST | scambia la password con un token di sessione |
| `/auth/check` | GET | verifica validità token |
| `/ingest` | POST | ingresso dati dallo userscript Tampermonkey (autenticato) |
| `/` | GET | serve `static/phone.html` |
| `/login` | GET | serve `static/login.html` |
| `/storico/cerca` | GET | ricerca nell'asta precedente per nome/squadra/ruolo |
| `/diag` | GET | diagnostica del matching giocatore |
| `/diag/storico` | GET | diagnostica dei prezzi storici |
| `/ws/phone` | WS | canale verso il telefono (token in query string) |
| `/ws/extension` | WS | canale per lo scraper da console (auth come primo messaggio) |

All'avvio il server verifica esplicitamente la presenza dei file necessari e fallisce con un messaggio
leggibile invece di esplodere alla prima connessione. Cerca i file d'asta in modo tollerante (maiuscole,
spazi al posto degli underscore, cartella superiore, `server/data/`), purché il nome inizi per `rose_lega`.

### 9.2 Moduli

| Modulo | Responsabilità |
|---|---|
| `player_db.py` | indice dei 517 giocatori; lookup per **id** (esatto) o per nome, con tre strategie a cascata |
| `vorp_live.py` | strato 4: livello di rimpiazzo, scarsità, deriva di mercato |
| `live_state.py` | stato dell'asta: identità squadre, rose, budget, ripartizione della propria rosa |
| `storico_prezzi.py` | prezzi pagati nelle aste passate, indicizzati **fuori** dal pool del modello |
| `simili.py` | riferimenti per analogia quando il prezzo storico non esiste |
| `probabili.py` | parser HTML per infortuni e titolarità |
| `parse_rose_lega.py` | parser dei file `Rose_lega-*.xlsx` (blocchi di 2 squadre affiancate) |
| `common.py` | normalizzazione nomi e mapping squadra → sigla a 3 lettere |
| `auth.py` | password + token di sessione in memoria |
| `build_giocatori.py` | costruisce `giocatori_2026_27.xlsx` (da lanciare quando aggiorni i dati) |
| `build_storico_arricchito.py` | costruisce `storico_asta_2025_26.xlsx` |
| `clean_sheet_2025_26.py` | tabella clean sheet inserita a mano |

### 9.3 Il problema del matching dei nomi (e come è risolto)
La card della pagina d'asta mostra il **nome esteso** ("Lautaro Martinez", "Moise Kean"), mentre i file
fantacalcio.it usano la forma **abbreviata** ("Martinez L.", "Kean"). Un confronto testuale diretto
fallirebbe **proprio sui giocatori più importanti**. Soluzione, in ordine di affidabilità:

1. **Id numerico** estratto dall'URL dell'immagine della card (`.../card/2764.png` → id 2764). Match esatto.
2. **Nome abbreviato** letto dalla lista laterale (già nel formato dei file).
3. **Nome esteso** risolto per cognome + iniziale, che distingue correttamente anche i due Martinez dell'Inter.

Lo stesso problema si presenta nel parsing dei cognomi composti (`"David de Gea"`, `"Martinez Jo."`): il
segnale affidabile di iniziale è **il punto**, non la lunghezza — altrimenti "Gea" verrebbe scambiato per
un'iniziale. C'è una lista esplicita di particelle (`de, van, da, di, dos, del, der, la, den`).

### 9.4 Rilevamento degli acquisti
Tre segnali letti dalla pagina, in ordine di affidabilità:
1. **Righe rosa** (`ui-roster ui-player-row`): confrontando la rosa con l'ultima lettura si sa esattamente
   chi è stato comprato. Via principale.
2. **Contatori per ruolo e TOT**: sempre renderizzati, dicono quanti acquisti sono avvenuti anche quando le
   righe non sono visibili (virtual scroll).
3. **Giocatore in vetrina**: solo come ripiego.

Il **costo** si deduce dal calo del budget fra due snapshot. Se nello stesso intervallo la squadra ha preso
più di un giocatore, il costo del singolo non è ricavabile: l'evento compare comunque sul telefono ma non
viene passato al motore. Il primo snapshot di ogni squadra fa solo da riferimento e non genera eventi,
altrimenti all'avvio verrebbero "riscoperti" tutti i giocatori già in rosa.

### 9.5 Identità delle rose
Risolta in tre passi: **UID stabile** del viewport DOM (`roster-viewport-<uuid>`, invariante a rinomina e
riordino) → **sovrapposizione della rosa ≥ 60%** (se la pagina è stata ricaricata e Angular ha rigenerato gli
id) → **nome** (ultimo tentativo, per rose ancora vuote). I nomi precedenti vengono ricordati, così la propria
squadra resta agganciata anche dopo una rinomina.

### 9.6 Telefono
`static/phone.html` è una pagina mobile-first che si collega via WebSocket e mostra: giocatore in asta con
prezzo consigliato e intervallo, banda verde/grigia/rossa del verdetto con lo scarto percentuale e il
riferimento usato, budget e massima offerta di ogni squadra, ultima assegnazione, ripartizione per reparto
della propria rosa (porta arancione, difesa verde, centrocampo azzurro, attacco rosso) e una sezione
richiudibile di ricerca nell'asta dell'anno scorso (digitazione ritardata di 250 ms).

### 9.7 Sicurezza (stato attuale, onesto)
Password unica (`ASTA_PASSWORD`, default hard-coded), confronto a tempo costante, token `secrets.token_urlsafe(32)`
in memoria che si azzerano al riavvio. Il traffico viaggia in **HTTP in chiaro sulla rete locale**: protegge
dalla curiosità di chi è sulla stessa WiFi, non da un attacco vero. Adeguato per un'asta tra amici; da non
riutilizzare altrove. **Prima della pubblicazione la password va rimossa dal codice** (sezione 12).

---

## 10. Inventario completo dei file

Percorso base: `C:\Users\<utente>\Desktop\Fantacalcio\`

### `Modello_prezzi/` — pipeline di pricing offline
| File | Pubblicare? | Note |
|---|---|---|
| `modello_prezzo.py` | **Sì** | strati 1-3. Path di input/output **hard-coded** su `/mnt/user-data/outputs/`: vanno parametrizzati |
| `verdetto.py` | **Sì, con avvertenza** | versione **precedente** a quella che ha generato il verdetto doppio |
| `prezzi_2026_27.csv` | Opzionale | artefatto derivato, generazione vecchia (501 righe) |
| `verdetto_2026_27.csv` | Opzionale | artefatto derivato, generazione vecchia, verdetto singolo |

### `server/` — assistente live
| File | Pubblicare? | Note |
|---|---|---|
| `app.py` | **Sì** | server FastAPI |
| `auth.py` | **Sì, dopo bonifica** | contiene la password di default in chiaro |
| `common.py` | **Sì** | utility di normalizzazione |
| `player_db.py` | **Sì** | indice giocatori e matching |
| `vorp_live.py` | **Sì** | strato 4 |
| `live_state.py` | **Sì, dopo bonifica** | contiene `MIA_SQUADRA = "NapoLanza"`, da rendere configurabile |
| `storico_prezzi.py` | **Sì** | prezzi storici |
| `simili.py` | **Sì** | profili per analogia |
| `probabili.py` | **Sì** | parser infortuni/titolarità |
| `parse_rose_lega.py` | **Sì** | parser rose di lega |
| `build_giocatori.py` | **Sì** | path hard-coded nel `__main__`, da parametrizzare |
| `build_storico_arricchito.py` | **Sì** | idem |
| `clean_sheet_2025_26.py` | **Sì** | dato inserito a mano |
| `asta-live.user.js` | **Sì, dopo bonifica** | userscript Tampermonkey; contiene la password |
| `scraper.js` | **Sì, dopo bonifica** | variante da console (WebSocket); contiene la password |
| `test-tampermonkey.user.js` | **Sì** | script di diagnosi |
| `inspector2.js` | **Sì** | utility per ricalibrare i selettori DOM |
| `test_integration.py` | **Sì** | test |
| `test_squadre.py` | **Sì** | test |
| `requirements.txt` | **Sì, da correggere** | **manca `pandas`**, richiesto da `build_giocatori.py` |
| `README.md` | **Sì** | guida operativa in italiano (aggiornata il 13/09/2026) |
| `static/phone.html` | **Sì** | UI del telefono |
| `static/login.html` | **Sì** | schermata di login |
| `giocatori_2026_27.xlsx` | **Valutare** | dato derivato da fantacalcio.it, vedi sezione 12.4 |
| `storico_asta_2025_26.xlsx` | **No / anonimizzare** | contiene i nomi delle squadre della lega |
| `Rose_lega-abendosa.xlsx` | **No / anonimizzare** | dati della lega privata (nomi squadre degli amici) |
| `pagina_asta.html` | **No** | dump HTML della pagina d'asta (330 KB), serviva per la calibrazione |
| `__pycache__/` | **No** | artefatto, va in `.gitignore` |

### `Dati/` — dati grezzi
| Cartella | Pubblicare? | Note |
|---|---|---|
| `Quotazioni/` (12 file) | **Valutare** | dati ufficiali fantacalcio.it, vedi 12.4 |
| `Statistiche/` (12 file) | **Valutare** | idem |
| `Voti/` (418 file) | **Valutare** | idem |

---

## 11. Cosa manca per la riproducibilità (stato aperto)

Questa è la sezione più importante per chi costruisce la repo: **la pipeline oggi non è riproducibile
end-to-end** con il solo materiale presente sul disco.

1. **Script di training del modello ML — RECUPERATO.** Non era tra i file
   del progetto su disco, ma il codice completo (HistGradientBoostingRegressor,
   cross-validation temporale, regressione quantile conformalizzata) è stato
   ritrovato nella trascrizione della sessione originale (salvata in Basic
   Memory) ed è ora in `pricing/model/train_model.py` e
   `pricing/model/build_hreg.py`, rieseguiti sui dati reali e validati contro
   i numeri della sessione originale (vedi `docs/data-sources.md`). SHAP non
   risulta invece mai eseguito nella trascrizione, solo dichiarato come
   intenzione: non era implementato, contrariamente a quanto affermato più
   sotto in questo stesso documento.
2. **`predizioni_2026_27_v2.csv` / `.xlsx` — RITROVATO.** Non era nella
   cartella del progetto ma nella cartella Downloads della partizione
   Windows (`predizioni_2026_27_v2_1.csv`, 517 righe, la generazione piu'
   recente). È l'input di `modello_prezzo.py` e di `build_giocatori.py`
   (giornate perse stimate, presenze e fantamedia 2025-26); non è incluso
   in questa repo pubblica (dato derivato da fantacalcio.it) ma esiste sul
   disco dell'autore.
3. **`Hreg.pkl` — RECUPERATO.** Contiene lo shrinkage gerarchico (`fm_storica`, `fm_shrunk`, `fm_L1`,
   `correzione_fm`, `n_stagioni`) che alimenta lo strato 3b. Lo script che lo costruisce è stato
   ritrovato nella trascrizione della sessione originale ed è ora `pricing/model/build_hreg.py`,
   rieseguito sui dati reali e validato (stessi identici numeri della sessione originale — vedi
   `docs/data-sources.md`). Se non lo generi, `modello_prezzo.py` funziona comunque: la
   regressione alla media si disattiva da sola.
   **Bug correlato trovato e corretto in questa repo**: quando il file manca,
   `modello_prezzo.py` andava comunque in errore perché il selettore finale
   delle colonne d'uscita referenziava sempre `n_stagioni`/`fm_L1`/
   `fm_storica`/`fm_shrunk` anche se non erano mai stati creati — non solo
   un file mancante, ma un crash. Corretto impostando quelle colonne a `NaN`
   nel ramo che gestisce l'assenza di `Hreg.pkl`.
4. **`probabili-formazioni-serie-a` (HTML) — RITROVATO.** Non era nella
   cartella del progetto ma in `Downloads/Varie/` sulla partizione Windows
   (717 KB, salvata il 17/08/2026). Non è incluso in questa repo pubblica
   (contenuto di terzi, fantacalcio.it) ma esiste sul disco dell'autore.
5. **CSV intermedi di ultima generazione — ASSENTI.** Quelli su disco sono più vecchi dell'xlsx finale
   (sezione 5.4). Le versioni che hanno prodotto `giocatori_2026_27.xlsx` vivevano in una sandbox temporanea.
6. **Path hard-coded.** `modello_prezzo.py`, `verdetto.py`, `build_giocatori.py`, `build_storico_arricchito.py`
   e `parse_rose_lega.py` contengono percorsi assoluti tipo `/mnt/user-data/outputs/...`, `/mnt/user-data/uploads/...`
   e `/mnt/project/...`: sono residui dell'ambiente in cui gli script sono stati eseguiti. Vanno sostituiti
   con argomenti da riga di comando o un file di configurazione.
7. **`requirements.txt` incompleto.** Copre il server ma non la pipeline: manca `pandas` (e servirà
   `scikit-learn` quando il training verrà reintegrato). `scipy` è elencato ma non risulta importato dal server.
8. **Disallineamento sul numero di squadre.** `build_giocatori.py` e `vorp_live.py` usano `NSQ = 10`;
   `modello_prezzo.py` e `verdetto.py` hanno ancora cablata una lega da **12** squadre
   (`BUDGET_TOT = 12*1000`, `SLOT = 36/96/96/72`). Le quote di reparto (10/20/30/40%) sono invarianti, quindi
   la forma della curva regge e il sistema è usabile così com'è; ma prima di rigenerare i prezzi da zero va
   deciso se portare anche gli strati 1-3 a 10 squadre. Il README ora lo segnala esplicitamente.
9. **Nessun controllo di versione.** La cartella non è un repository Git: non esiste storia dei cambiamenti.
10. **Clean sheet solo per il 2025-26**, inseriti a mano: per la stagione successiva la tabella va rifatta.

---

## 12. Preparare la repository open source

### 12.1 Struttura consigliata
```
fantacalcio-auction-assistant/
├── README.md                  # inglese, con link al README italiano
├── README.it.md               # l'attuale server/README.md, ampliato
├── PROJECT_DOSSIER.md         # questo documento
├── LICENSE                    # es. MIT per il codice
├── .gitignore
├── requirements.txt           # server
├── requirements-pipeline.txt  # pandas, scikit-learn, ecc.
├── docs/
│   ├── methodology.md         # sezioni 6-8 di questo dossier
│   ├── data-sources.md        # sezione 5, con le gotchas
│   └── glossary.md            # glossario IT→EN
├── pricing/                   # ex Modello_prezzi/
│   ├── modello_prezzo.py
│   └── verdetto.py
├── server/
│   ├── app.py, auth.py, common.py, player_db.py, vorp_live.py,
│   ├── live_state.py, storico_prezzi.py, simili.py, probabili.py,
│   ├── parse_rose_lega.py, build_giocatori.py,
│   ├── build_storico_arricchito.py, clean_sheet_2025_26.py
│   └── static/{phone.html,login.html}
├── browser/
│   ├── asta-live.user.js
│   ├── scraper.js
│   ├── test-tampermonkey.user.js
│   └── inspector2.js
├── tests/
│   ├── test_integration.py
│   └── test_squadre.py
└── examples/
    └── config.example.toml    # percorsi dati, nome squadra, numero squadre
```

Nota: se sposti gli userscript in `browser/`, **aggiorna i riferimenti nel README**, che ora puntano a `server/`.

### 12.2 Segreti e dati personali da rimuovere PRIMA del primo commit

**[FATTO in questa repo]** La password originale e' stata rimossa da
`server/auth.py` (ora richiede `ASTA_PASSWORD`, obbligatoria, nessun
default nel codice), da `browser/asta-live.user.js` e `browser/scraper.js`
(sostituita con il segnaposto `"INSERISCI_LA_TUA_PASSWORD"`), e da tutte le
occorrenze nella documentazione operativa.

1. **Password** in `server/auth.py`, `server/asta-live.user.js`
   (CONFIG.PASSWORD), `server/scraper.js` (CONFIG.PASSWORD) e citata più
   volte nel `README.md`. Sostituire con variabile d'ambiente obbligatoria
   e, negli userscript, con un segnaposto `"INSERISCI_LA_TUA_PASSWORD"`.
2. **`MIA_SQUADRA = "NapoLanza"`** in `server/live_state.py` → parametro di configurazione.
3. **Nomi delle squadre della lega** dentro `Rose_lega-abendosa.xlsx` e `storico_asta_2025_26.xlsx`:
   sono nomi scelti da persone reali. O si escludono, o si anonimizzano (`Squadra 1`, `Squadra 2`, …).
   Servirebbe comunque un file di esempio per far girare il codice: creane uno **sintetico**.
4. **`pagina_asta.html`**: dump completo della pagina d'asta, può contenere nomi squadra e stato della lega.
   Non pubblicare.

### 12.3 `.gitignore` minimo
```
__pycache__/
*.pyc
.venv/
*.pkl
probabili-formazioni-serie-a
Rose_lega-*.xlsx
pagina_asta.html
```

### 12.4 Licenza e ridistribuzione dei dati — da decidere consapevolmente
Il **codice** può essere rilasciato liberamente (MIT/Apache-2.0). I **dati** sono un'altra questione:
i file `Statistiche_*`, `Quotazioni_*` e i voti giornata per giornata sono prodotti da **fantacalcio.it** e la
loro ridistribuzione potrebbe non essere consentita. Raccomandazione prudente:

- **non** committare i file xlsx di fantacalcio.it nella repo;
- documentare in `docs/data-sources.md` esattamente **quali file servono, dove si scaricano e come si
  chiamano**, in modo che chiunque possa ricostruirsi il dataset;
- fornire un piccolo **dataset sintetico** (10-20 giocatori inventati) che permetta di far girare i test e di
  vedere il sistema funzionare senza dati altrui;
- se vuoi pubblicare comunque gli artefatti derivati (`giocatori_2026_27.xlsx`), verifica prima i termini d'uso
  del sito: è un file derivato ma contiene colonne che vengono direttamente da loro (`FVM`, `QtI`).

Nota non giuridica ma pratica: questa scelta non è solo formale, è quella che rende la repo utilizzabile
anche in leghe diverse dalla tua, perché costringe a documentare il formato dei dati invece di assumerlo.

### 12.5 Priorità di lavoro suggerite per l'agente
1. Bonifica dei segreti (12.2) — **bloccante**, va fatta prima di qualunque commit.
2. Parametrizzazione dei path hard-coded (11.6) — senza questa la repo non gira su nessuna macchina.
3. `requirements` corretti e separati (11.7).
4. README in inglese + traduzione/adattamento di questo dossier in `docs/`.
5. Dataset di esempio sintetico + test che girino in CI.
6. Ricostruzione dello script di training ML (11.1) — è il pezzo mancante più sostanzioso.
7. Decisione sul numero di squadre (11.8) e allineamento di `modello_prezzo.py`/`verdetto.py`.

---

## 13. Nota sulla lingua del codice (da riportare nel README della repo)

Il progetto è scritto da un madrelingua italiano per una lega italiana, in un dominio — il fantacalcio — i cui
termini **non hanno una traduzione standard** in inglese (*fantamedia*, *quotazione*, *titolarità*, *fascia*,
*FVM*). Di conseguenza:

- commenti, docstring e nomi di variabili sono **in italiano** e **restano in italiano**;
- non tradurre il codice, non rinominare identificatori, non riscrivere i commenti;
- la comprensibilità per un pubblico internazionale è garantita dalla **documentazione bilingue** e dal
  glossario qui sotto.

Questa è una scelta deliberata. Va dichiarata apertamente nel README della repo, così che un contributore
esterno sappia cosa aspettarsi invece di aprire una pull request per "internazionalizzare" il codice.

---

## 14. Glossario IT → EN

| Italiano | Inglese | Significato |
|---|---|---|
| fantacalcio | Italian fantasy football | gioco basato sui voti dei giornalisti sportivi |
| asta | auction | asta iniziale in cui si comprano i giocatori |
| crediti | credits | valuta dell'asta (1000 per squadra) |
| rosa | roster / squad | insieme dei giocatori di una squadra |
| ruolo (P/D/C/A) | role (GK/DEF/MID/FWD) | portiere, difensore, centrocampista, attaccante |
| fascia | tier | livello di qualità dentro il ruolo (top/semitop/terza/quarta/minori) |
| quotazione (Qt.A / Qt.I) | listing price (current / initial) | prezzo ufficiale di listino |
| FVM | market value index | indice di valore di mercato di fantacalcio.it |
| fantamedia (Fm) | fantasy average | media dei fantavoti del giocatore |
| titolarità | starter likelihood | probabilità/percentuale di essere titolare |
| produzione attesa | expected production | fantapunti stagionali attesi |
| prezzo base | base price | prezzo dopo strati 1-2 |
| correzione | correction | scostamento applicato dagli strati 3 e 4 |
| prezzo modello | model price | prezzo finale offline (strati 1-3) |
| prezzo consigliato | recommended bid | prezzo modello + strato 4 + deriva |
| verdetto | verdict | sottovalutato / in linea / sopravvalutato |
| scarto | gap | differenza fra prezzo modello e riferimento |
| scarsità | scarcity | quanto sono esaurite le alternative equivalenti |
| deplezione | depletion | quota di giocatori pari o superiori già acquistati |
| livello di rimpiazzo | replacement level | produzione dell'ultimo slot da titolare libero |
| deriva di mercato | market drift | quanto la lega paga sopra/sotto il modello |
| voto d'ufficio | administrative rating | voto assegnato d'ufficio, non conta come presenza |
| clean sheet | clean sheet | partita senza gol subiti (portieri) |
| giornata | matchday | turno di campionato |
| probabili formazioni | predicted line-ups | pagina con titolari probabili e infortuni |

---
---

# PART II — ENGLISH

> **Important note about the source code.** Every `.py` and `.js` file in this project has comments,
> docstrings and **variable names in Italian** (`prezzo_modello`, `fascia`, `correzione`, `scarsita`,
> `verdetto`, `livello_rimpiazzo`…). **This must not be changed.** Do not translate the code, do not rename
> identifiers, do not rewrite comments in English. English is provided at the documentation layer only
> (this dossier, the repo README). A glossary is at the end of each part.

## 0. How to use this document

If you are an agent tasked with creating the repository:

1. Read section **10 (File inventory)**: it states exactly which file is needed, where it lives, what it does.
2. Read section **11 (What is missing)**: several artifacts referenced by the code are **not on disk**, and
   the pipeline is not reproducible end-to-end without them. They must be rebuilt or declared missing.
3. Read section **12 (Preparing the repo)**: folder layout, `.gitignore`, secrets to strip **before** the
   first commit, and the data-licensing problem.
4. Do not change the language of the code (see the note above and section 13).

---

## 1. The original idea

Italian fantasy football in **Classic** mode is played through an initial auction: each team has a fixed
budget in credits and buys players in ascending bids, one at a time, until every role slot is filled. The
auction largely decides the season, yet it happens in real time, under pressure, with decisions made by feel
or by reading the same official listing everybody else has.

The founding idea was: **try to win fantasy football with mathematics.** Concretely, answer three questions
that keep coming up during an auction, in a quantitative and verifiable way:

1. **What is this player actually worth**, in credits, in *my* league (not in the abstract)?
2. **At the price it is going for right now, is it a good deal?** That is: overvalued or undervalued?
3. **How far should I push**, given that alternatives are being depleted as the auction proceeds?

The project therefore grew into two complementary halves:

- an **offline statistical pipeline** producing, before the auction, a calibrated valuation of every player
  (expected price + uncertainty interval + verdict);
- a **live assistant** that, during the auction, reads the auction page in the PC browser and pushes to the
  phone in real time the updated recommended bid, every opponent's budget, and the state of one's own roster.

The design constraint, repeated throughout the code, is: **no layer may overturn the previous one.**
The market (fantacalcio.it's FVM) always has the last word on the *shape* of the price curve; the statistical
model may shift prices, not reinvent them. This is a methodological choice, not a technical limitation, and
it is why the system behaves predictably even when the model is wrong.

---

## 2. League context

| Parameter | Value |
|---|---|
| League name | Lega Abendosa (fantacalcio.it) |
| Author's team | NapoLanza |
| Number of teams | 10 (previously 12) |
| Budget per team | 1000 credits |
| League-wide budget | 10,000 credits |
| Mode | Classic |
| Roster per team | 3 GK / 8 DEF / 8 MID / 6 FWD (25 players) |
| League-wide slots | 30 / 80 / 80 / 60 (250) |
| Auction platform | FantaAsta Live (`fanta-asta-live.fantacalcio.it`), served over HTTPS |

The move from 12 to 10 teams matters: part of the code is still calibrated on 12 (see section 11).

**Budget quotas per role.** The model forces league-wide spending to split
**10% goalkeepers / 20% defenders / 30% midfielders / 40% forwards**. This was the author's prior and was
later confirmed empirically against prices actually paid. It is the single most important parameter, because
it is what makes valuation **role-dependent**: the same expected output is worth different amounts in goal and
up front, because roles compete for different slices of the budget.

---

## 3. The two halves of the system

See the diagram in Part I, section 3 (identical for both languages).

Offline: historical data → ML expected-production model (+ p10/p90) → `modello_prezzo.py` (layers 1-2-3) →
`prezzi_2026_27.csv` → `verdetto.py` → `verdetto_2026_27.csv` → `build_giocatori.py` →
**`giocatori_2026_27.xlsx`** (the database the server consumes).

Live: auction page → `asta-live.user.js` (Tampermonkey) → `POST /ingest` → `app.py` (FastAPI, localhost:8000)
with `player_db` / `vorp_live` / `live_state` / `storico_prezzi` / `simili` → WebSocket → `static/phone.html`.

---

## 4. Development history, phase by phase

This section matters because **many project choices are reactions to a concrete failure**. Anyone reading the
repo needs to understand why a seemingly more elegant solution was discarded.

### Phase 1 — Building the historical panel
Collected official fantacalcio.it files: `Statistiche` and `Quotazioni` for 12 seasons (2015-16 → 2026-27),
plus **per-matchday ratings** for 11 seasons (2015-16 → 2025-26, 38 matchdays each = 418 files), merged into a
longitudinal player × season panel joined on the fantacalcio.it `Id`.

Problems solved in this phase (all verified against data, not assumed):
- the **ratings** files use `Cod.` as the identifier, not `Id`;
- an **asterisk** next to a rating marks an *administrative rating* (irrelevant cameo) and **does not count as
  an appearance**: validated at 99.4% accuracy against official appearance counts;
- **head coaches** (role `ALL`) appear in the ratings data and must be filtered out;
- the matchday API returns **401 to external requests** even with valid cookies, so downloading had to be done
  with a JavaScript downloader running inside the browser;
- PowerShell-generated files contain a **BOM**: they need `utf-8-sig` plus latin-1 sanitisation;
- the `Gf` column in `Statistiche` **already includes penalty goals** (unlike the per-matchday files, where
  penalties are separate): adding `R+` double-counted them. Bug found and fixed.

### Phase 2 — Expected-production model
A supervised model estimating each player's **expected seasonal production** in fantasy points.

- Algorithm: **HistGradientBoostingRegressor** (histogram gradient boosting, scikit-learn).
- Validation: **temporal cross-validation** (each season predicted using only its own past).
- Performance: **R² ≈ 0.467** under temporal validation.
- Intervals: **conformalized quantile regression** for p10/p90, with **81.6% empirical coverage** on unseen
  data (80% nominal). The intervals are therefore *calibrated*, not decorative — which is what makes "robust"
  verdicts meaningful (section 7).
- Interpretability: **SHAP values**.
- Methodological choice: gradient boosting beats neural networks on tabular data of this size. This is the
  explicit stated reason no network was used.
- **Starter likelihood**: the starting percentage from predicted line-ups is mapped onto historical appearance
  rates, converting a qualitative signal ("he's the starter") into a minutes multiplier.

### Phase 3 — From output to price: the 4-layer model
The conceptual core (full detail in section 6). The insight: *do not build the price from scratch*.
Fantacalcio.it's FVM (market value index) is already calibrated on the real market and carries information no
statistical model has (expectations, summer transfers, hype). So FVM supplies the **shape** of the curve; the
model corrects the **level**, within limits fixed in advance.

### Phase 4 — Mean reversion
Added a layer (3b) penalising players who last season outperformed their own historical level.
**Persistence coefficients** were estimated on 2015-16 → 2025-26 (n = 2950 players with at least 10
appearances) and are strongly role-dependent:

| Role | Persistence coefficient |
|---|---|
| GK | **−0.08** |
| DEF | 0.705 |
| MID | 0.904 |
| FWD | 0.810 |

Goalkeepers are the extreme case: an above-level season **does not repeat at all** (negative coefficient).
This is one of the most useful empirical results in the project and on its own justifies the very low
correction cap imposed on goalkeepers.

### Phase 5 — The verdict
A system classifying each player as *undervalued / fair / overvalued* (section 7). This produced **the most
instructive failure of the project**: the first version used, as its reference, a behavioural model trained on
**a single real auction**. Result: wildly unstable verdicts, **standard deviation ≈ 241%**. Replacing the
reference with FVM rescaled by role quotas (layers 1+2) dropped it to **≈ 10.9%**. Lesson: *the reference
matters more than the model*.

Later the verdict became **dual**, because the question differs by tier:
- `verdetto_base` — compared against the model reference, used for **top, semitop, terza**, where the budget
  genuinely exists and the comparison is clean;
- `verdetto_lega` — compared against what the league actually pays, used for **quarta and minori**, where
  price is driven by the obligation to fill slots rather than by value.

### Phase 6 — The live assistant and the Bayesian tracker (later removed)
First version of layer 4: a **Normal-Inverse-Gamma Bayesian tracker** updating estimates on each observed
purchase. It failed: working from a **pure VORP** fair value (not FVM-anchored) it produced 6-10× multipliers
on tail players — absurd prices exactly where the auction is most crowded. Replaced by the
**composition/scarcity** approach in section 8.

Methodological conclusion recorded in the project: a **full hierarchical Bayesian model fits better offline**
than live. The concrete reasons are latency and sparse per-subgroup observations during an auction; live,
incrementally updated role/tier correction factors work better and approximate empirical Bayesian shrinkage.

### Phase 7 — Browser integration and DOM debugging
Many problems solved, each with a precise fix (details in section 9):
- **WebSocket blocked**: the auction page is HTTPS, `ws://localhost` is mixed content; the `WebSocket`
  constructor throws a **synchronous** exception that kills the whole script before the overlay even appears.
  Fix: `GM_xmlhttpRequest` (privileged extension context) posting to `/ingest`.
- **Team identity**: renaming a roster created a phantom team. Fix: stable DOM viewport UUID, falling back to
  ≥60% roster overlap and then to name matching.
- **Purchase detection**: attributing a purchase to the "showcased player" failed because between assignment
  and the next read the showcase empties. Fix: diffing **roster rows** between snapshots.
- **Budget accumulated instead of rebuilt**: a removed player left his credits spent forever. Fix: the roster
  is **rebuilt from each snapshot**, never accumulated.
- **Injury parser**: a single regex over the whole page paired one entry's name with the next entry's
  description. Fix: isolate the individual `<li>` first.
- **Namesakes**: surname matching flagged the wrong injured players (two Pessina, two Martinez). Fix: the
  surname fallback applies **only when the surname is unambiguous in the pool**.

---

## 5. The data

### 5.1 Sources
All raw data comes from **fantacalcio.it** (official statistics/listings) and its public **predicted line-ups**
page. Historical auction prices come from the league's own export.

### 5.2 Files on disk

| Folder | Contents | Count |
|---|---|---|
| `Dati/Quotazioni/` | `Quotazioni_Fantacalcio_Stagione_YYYY_YY.xlsx` | 12 files (2015-16 → 2026-27) |
| `Dati/Statistiche/` | `Statistiche_Fantacalcio_Stagione_YYYY_YY.xlsx` | 12 files (2015-16 → 2026-27) |
| `Dati/Voti/` | `voti_YYYY-YY_gNN.xlsx` | 418 files (11 seasons × 38 matchdays) |

**Relevant columns in Quotazioni**: `Id`, `Nome`, `Squadra`, `R` (role), `Qt.A` (current listing), `Qt.I`
(initial listing), `FVM`. Header on **row 2**, data from **row 3**, sheet `Tutti`.

**Relevant columns in Statistiche**: `Nome`, `Squadra`, `Pv` (appearances), `Fm` (fantasy average),
`Gf` (goals scored, **penalties included**), `Gs` (goals conceded), `Rp` (penalties saved), `Ass` (assists).

**Ratings files**: identifier `Cod.`, asterisk = administrative rating (not an appearance), rows with role
`ALL` must be filtered.

### 5.3 Data NOT present in the official files, supplied separately
- **Goalkeeper clean sheets**: the `Statistiche` files report goals conceded but not shutouts. The data was
  entered manually in `server/clean_sheet_2025_26.py` as `(name, team abbreviation, clean sheets)` tuples.
  Keepers not listed have 0 clean sheets **only if they actually played**: those with no appearances get
  `None`, which is different from "zero clean sheets in 38 games".
- **Injuries and starter likelihood**: extracted from the `probabili-formazioni-serie-a` page saved as HTML
  into `server/`. It must be re-saved before each refresh.

### 5.4 Derived artifacts

| File | Produced by | Contents |
|---|---|---|
| `Modello_prezzi/prezzi_2026_27.csv` | `modello_prezzo.py` | 501 rows — layer 1-3 prices |
| `Modello_prezzi/verdetto_2026_27.csv` | `verdetto.py` (a later version than the one on disk) | 501 rows — verdicts |
| `server/giocatori_2026_27.xlsx` | `build_giocatori.py` | **517 players** — the database the server uses |
| `server/storico_asta_2025_26.xlsx` | `build_storico_arricchito.py` | 268 purchases enriched with profiles |
| `server/Rose_lega-abendosa.xlsx` | league export | 268 purchases from the 2025-26 auction with prices paid |

**Warning (verified):** the two CSVs in `Modello_prezzi/` are an **earlier generation** than
`giocatori_2026_27.xlsx`. The CSV has 501 players, the xlsx 517; 275 of 484 shared FVM values differ; 402 of
484 prices differ. The CSV also carries a **single** verdict, whereas `build_giocatori.py` expects the
**dual** verdict columns (`verdetto_base`/`verdetto_lega`), which are indeed present in the xlsx. Conclusion:
the xlsx was built from newer CSVs that were **never saved to disk**.

### 5.5 Final database composition (`giocatori_2026_27.xlsx`, verified)
- 517 players: 62 GK, 184 DEF, 184 MID, 87 FWD
- verdicts: 220 undervalued, 170 overvalued, 127 fair
- reference used: 115 "model" (high tiers), 402 "league" (tails)
- 40 players flagged as injured
- 34 columns (list in Part I, section 5.5)

---

## 6. The 4-layer pricing model

Implemented in `Modello_prezzi/modello_prezzo.py` (layers 1-3) and `server/vorp_live.py` (layer 4).
Layers are ordered by **decreasing authority**: each may correct the previous one only within preset limits.
That is the architectural principle of the project.

### Layer 1 — Market anchor (FVM)
Fantacalcio.it's FVM is already calibrated: summed over players actually bought it totals roughly 12,334
credits for a 12 × 1000 league. FVM supplies the **shape** of the price curve — the tier structure — which
therefore should not be reinvented.

### Layer 2 — Role quotas (10/20/30/40)
Raw FVM implies a **5.7 / 20.1 / 34.8 / 39.4 %** split across GK/DEF/MID/FWD. Each role's FVM is rescaled so
that the sum over actually-drafted slots hits the intended quota:

```
for each role R:
    drafted  = top SLOT[R] players by FVM
    residual = TOTAL_BUDGET * QUOTA[R] − SLOT[R] * MIN_PRICE
    k        = residual / sum_FVM(drafted)
    base_i   = MIN_PRICE + FVM_i * k          (MIN_PRICE = 1 credit)
```

This is what makes valuation **role-dependent**.

**Tiers.** Within each role players are sorted by FVM and split into five tiers
(`top, semitop, terza, quarta, minori`), with sizes:

| Role | top | semitop | terza | quarta | minori |
|---|---|---|---|---|---|
| GK | 8 | 5 | 5 | 5 | rest |
| DEF | 11 | 12 | 15 | 15 | rest |
| MID | 6 | 12 | 15 | 15 | rest |
| FWD | 6 | 8 | 12 | 12 | rest |

Non-obvious detail: in the tail FVM **does not discriminate** (in 2025-26 every goalkeeper from 24th down had
FVM = 1), so sorting uses a **composite key**: FVM rank as primary criterion × 1000 plus expected-production
rank as tie-breaker.

### Layer 3 — Statistical correction
Two components, both inside the same cap.

**3a — model/market divergence.** The *percentile* of expected production is compared against the *percentile*
of FVM, **within the role**: `div_modello = pct_model − pct_market`. Percentiles rather than raw values make
the comparison immune to differing scales across roles and seasons.

**3b — mean reversion.** The player's fantasy-average gap versus his own historical level is standardised per
role, clipped at ±2 standard deviations and weighted:

```
div_regressione = clip(correzione_fm / sd_role, −2, +2) * 0.25 * REGRESSION_WEIGHT   (REGRESSION_WEIGHT = 0.5)
```

`correzione_fm` comes from an `Hreg.pkl` file (hierarchical shrinkage: `fm_storica`, `fm_shrunk`, `fm_L1`,
`n_stagioni`). If the file is missing, layer 3b silently disables itself and evaluates to 0.

**Double cap.** The total correction is limited by an **absolute per-role** cap and a **relative** one:

```
cap        = min( ROLE_CAP[role] , base * 0.30 )
correction = clip( divergence * 2.0 * cap , −cap , +cap )
price      = base + correction
```

| Role | Absolute cap |
|---|---|
| GK | 6 credits |
| DEF | 12 credits |
| MID | 20 credits |
| FWD | 30 credits |

The rationale: a 5-credit error on a goalkeeper is as serious as a 30-credit error on a forward.

**Iterative normalisation.** Fifth-tier players have a price ceiling calibrated on the **90th percentile of
prices actually paid** in the August 2025 auction (tiers assigned by `Qt.I`, immune to in-season listing
decay): **GK 5, DEF 22, MID 22, FWD 23 credits**. Clipping the tail removes budget that must be reabsorbed by
higher tiers, which can require another clip: `normalizza()` iterates up to 30 times, exiting when the gap
from target quotas falls below 1 credit. A myth-busting note recorded in the code: the rule "tail players cost
1-5 credits" **holds only for goalkeepers**; in the other roles the tail is far more expensive.

**Continuity check.** A dedicated function verifies there are no jumps between adjacent tiers: the last `top`
must cost what the first `semitop` costs. Tiers describe **how rosters are composed**, not price steps. The
recorded result is that continuity holds: there is no price homogeneity *within* a tier, but continuity
*between* adjacent tiers.

### Layer 4 — Live VORP/scarcity
See section 8. By construction, the weakest correction in the chain.

---

## 7. The valuation verdict

Implemented in `Modello_prezzi/verdetto.py` (the on-disk version) and in the `verdetto*` columns of
`giocatori_2026_27.xlsx` (the newer, dual-reference version).

**Question:** at the price it is going for, is this player worth it?

The method avoids two traps explicitly stated in the code:

1. **Never compare credits across roles.** A 100-credit forward and a 100-credit goalkeeper are not
   comparable. Comparison is **always within the role**.
2. **Never use the point estimate alone.** The model has calibrated conformal intervals: a verdict is declared
   **robust** only if it survives the unfavourable end of the interval.

**Metric: return per credit**, normalised by the role median computed **only over players who will actually be
bought** (the top `SLOT[R]` by price):

```
index      = (expected_production / price) / role_median
index_p10  = (p10 / price) / role_median
index_p90  = (p90 / price) / role_median
```

**Thresholds:** `index ≥ 1.15` → undervalued; `index ≤ 0.85` → overvalued; in between → fairly valued.
The verdict becomes "robust" if `index_p10 ≥ 1` (undervalued even in the unfavourable scenario) or
`index_p90 ≤ 1` (overvalued even in the favourable one).

Also computed: the **indifference price** (the price at which the player would return exactly the role median)
and the **margin** = indifference price − price. This is the most actionable number of all: it says how many
credits you can still bid while staying ahead.

### Threshold calibration (backtest)
Backtest over **6 seasons** (2019-20 → 2024-25), each predicted using **only its own past**. Gap thresholds of
10 / 15 / 20 / 25 / 30% were tested:

- separation between undervalued and overvalued grows **almost linearly** with the threshold (from 2.40× to
  3.06×): there is **no "natural" cut-off**, it is a trade-off between separation and coverage;
- **10%** was chosen because it has the lowest signal variability across seasons (ratio std. dev. **0.52**,
  versus 0.60 at 15% and up to 0.75 at 30%) and because it covers **83%** of players versus 51-73% for higher
  thresholds, leaving the fewest possible cases without a verdict.

**Backtest result at that threshold:** players classified as undervalued produced **1.86×** and overvalued
ones **0.77×** the production actually realised, **in all 6 seasons tested**. Rank correlation (Spearman)
between model price and realised output ranges between **0.43 and 0.74** depending on the season.

### Dual reference
In the final version (the one inside `giocatori_2026_27.xlsx`) the verdict is computed twice:

| Tier | Reference used | Why |
|---|---|---|
| top, semitop, terza | `verdetto_base` / `scarto_base_pct` | the budget genuinely exists; comparison against the model reference is clean |
| quarta, minori | `verdetto_lega` / `scarto_lega_pct` | captures end-of-auction dynamics in the tail, where price is set by the need to fill slots |

The database records which reference was used (`rif_verdetto` = `modello` | `lega`), and the phone displays
it, because that tells you **how much to trust the number**.

Recorded caveat: in the tail, percentage gaps become enormous (+280%, +560%) because they divide by prices of
a few credits. On a 3-credit player, +500% is 15 credits — not a bargain worth chasing. Hence in those tiers
the verdict matters more than the percentage.

---

## 8. Layer 4: the live scarcity correction

Implemented in `server/vorp_live.py`, class `VorpLive`.

**The question VORP must answer:** *are there still valid alternatives to this player?*
The answer does not depend on how many players remain in absolute terms, but on **how what remains is composed**.

### Replacement level
Recomputed on every purchase: the expected production of the player who would occupy the **last starter slot
still open** in that role. At the start of the auction a forward's replacement is the 60th-best forward
(6 × 10 teams); as forwards get bought, replacement worsens and the remaining players' advantage grows.
`vorp_advantage = expected_production − replacement_level`.

### Scarcity: two components
**Composition (weight 0.75)** — what share of the still-free high block (top + semitop + terza) consists of
players **at least as good** as him. If 10 mid-high forwards remain and only one is top, that top player has
no alternatives. If 5 of 10 are top, alternatives exist and the price should not rise. The value is
**normalised against the start-of-auction share**: without that normalisation top players would look scarce
with the market untouched, since by construction they are a minority.

```
composition = max(0, 1 − share_now / share_at_start)
```

**Depletion (weight 0.25)** — how many players of equal or higher tier have been taken in absolute terms.
It covers the "5 of 10 top remain" case: proportionally there are still many, but the role is emptying out and
a small premium is justified.

```
scarcity = 0.75 * composition + 0.25 * depletion        (then clipped to [0, 1])
```

### Final correction
```
cap        = min( ROLE_CAP[role] , base_price * 0.30 )     # same caps as layer 3
raw        = tanh( vorp_advantage / 50 ) * cap             # saturates smoothly
correction = clip( raw * scarcity , −cap , +cap )
```

Three deliberate brakes: the per-role cap, `tanh` saturation (a huge advantage does **not** produce a huge
correction) and the scarcity factor (while alternatives exist, the correction tends to zero).

**Verified behaviour on forwards** (from the reproducible scenario at the bottom of `vorp_live.py`):

| Scenario | top | semitop | terza |
|---|---|---|---|
| auction start (6/8/12 free) | +0.0 | +0.0 | +0.0 |
| 1 top, 2 semitop, 7 terza left | **+17.2** | +14.5 | +2.6 |
| 5 top and 5 semitop left | +1.1 | +2.0 | — |

### Market drift
If the league is systematically paying above the model, estimates shift. Per-role **log ratios**
`log(price_paid / model_price)` are accumulated; the mean is damped by weight `n / (n + 5)` and clipped at
**±30%**:

```
drift          = exp( clip( mean_log * n/(n+5) , log(0.7) , log(1.3) ) )
recommended    = max(1, (model_price + layer4_correction) * drift)
```

Damping avoids chasing the noise of the first few purchases; the cap prevents one anomalous auction from
overwhelming the model.

Correctness note: an assignment whose cost **cannot be deduced with certainty** (two purchases within the same
polling interval) is shown on the phone but **not** fed to the engine, so as not to pollute it with a guessed
price. A player removed by mistake becomes available again in the scarcity computation (`libera()`).

---

## 9. Software architecture

### 9.1 Server — `server/app.py` (FastAPI, `0.0.0.0:8000`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/login` | POST | exchanges the password for a session token |
| `/auth/check` | GET | token validity check |
| `/ingest` | POST | data intake from the Tampermonkey userscript (authenticated) |
| `/` | GET | serves `static/phone.html` |
| `/login` | GET | serves `static/login.html` |
| `/storico/cerca` | GET | search last year's auction by name/team/role |
| `/diag` | GET | player-matching diagnostics |
| `/diag/storico` | GET | historical-price diagnostics |
| `/ws/phone` | WS | channel to the phone (token in query string) |
| `/ws/extension` | WS | channel for the console scraper (auth as first message) |

At startup the server explicitly checks that required files exist and fails with a readable message instead of
blowing up on the first connection. It looks for auction files leniently (case, spaces instead of underscores,
parent folder, `server/data/`), as long as the name starts with `rose_lega`.

### 9.2 Modules

| Module | Responsibility |
|---|---|
| `player_db.py` | index of the 517 players; lookup by **id** (exact) or by name, with three cascading strategies |
| `vorp_live.py` | layer 4: replacement level, scarcity, market drift |
| `live_state.py` | auction state: team identity, rosters, budgets, own-roster breakdown |
| `storico_prezzi.py` | prices paid in past auctions, indexed **outside** the model pool |
| `simili.py` | analogy-based references when no historical price exists |
| `probabili.py` | HTML parser for injuries and starter likelihood |
| `parse_rose_lega.py` | parser for `Rose_lega-*.xlsx` files (blocks of two side-by-side teams) |
| `common.py` | name normalisation and team → 3-letter abbreviation mapping |
| `auth.py` | password + in-memory session tokens |
| `build_giocatori.py` | builds `giocatori_2026_27.xlsx` (run when refreshing data) |
| `build_storico_arricchito.py` | builds `storico_asta_2025_26.xlsx` |
| `clean_sheet_2025_26.py` | manually entered clean-sheet table |

### 9.3 The name-matching problem (and how it is solved)
The auction card shows the **full name** ("Lautaro Martinez", "Moise Kean"), while fantacalcio.it files use the
**abbreviated** form ("Martinez L.", "Kean"). A direct string comparison would fail **precisely on the most
important players**. Solution, in order of reliability:

1. **Numeric id** extracted from the card image URL (`.../card/2764.png` → id 2764). Exact match.
2. **Abbreviated name** read from the side list (already in file format).
3. **Full name** resolved by surname + initial, which also correctly separates Inter's two Martinez.

The same problem appears when parsing compound surnames (`"David de Gea"`, `"Martinez Jo."`): the reliable
signal for an initial is **the dot**, not length — otherwise "Gea" would be mistaken for an initial. There is
an explicit particle list (`de, van, da, di, dos, del, der, la, den`).

### 9.4 Purchase detection
Three page signals, in order of reliability:
1. **Roster rows** (`ui-roster ui-player-row`): diffing the roster against the last read tells you exactly who
   was bought. The primary path.
2. **Per-role and TOT counters**: always rendered, they report how many purchases happened even when rows are
   not visible (virtual scroll).
3. **Showcased player**: fallback only.

**Cost** is deduced from the budget drop between snapshots. If a team bought more than one player within the
same interval, the individual cost is not recoverable: the event still shows on the phone but is not fed to
the engine. Each team's first snapshot serves only as a baseline and generates no events, otherwise every
player already on a roster would be "rediscovered" at startup.

### 9.5 Roster identity
Resolved in three steps: **stable UID** of the DOM viewport (`roster-viewport-<uuid>`, invariant to renaming
and reordering) → **roster overlap ≥ 60%** (when the page was reloaded and Angular regenerated the ids) →
**name** (last resort, for still-empty rosters). Previous names are remembered, so your own team stays
attached even after a rename.

### 9.6 Phone
`static/phone.html` is a mobile-first page connecting over WebSocket, showing: the player on auction with
recommended price and interval, a green/grey/red verdict band with percentage gap and which reference was
used, every team's budget and maximum bid, the last assignment, your own roster's per-role budget breakdown
(GK orange, DEF green, MID blue, FWD red), and a collapsible search over last year's auction (250 ms debounce).

### 9.7 Security (honest current state)
Single password (`ASTA_PASSWORD`, hard-coded default), constant-time comparison, in-memory
`secrets.token_urlsafe(32)` tokens cleared on restart. Traffic travels as **plain HTTP over the local
network**: it protects against the curiosity of others on the same WiFi, not against a real attack. Adequate
for an auction among friends; do not reuse elsewhere. **The password must be removed from the code before
publication** (section 12).

---

## 10. Full file inventory

Base path: `C:\Users\<utente>\Desktop\Fantacalcio\` — see the tables in Part I, section 10, which apply verbatim.
Summary of the publication decisions:

- **Publish as-is:** all server and pricing Python modules, the tests, `static/*.html`, `inspector2.js`,
  `test-tampermonkey.user.js`, `README.md`.
- **Publish after sanitising:** `auth.py` (password), `live_state.py` (`MIA_SQUADRA`), `asta-live.user.js` and
  `scraper.js` (password).
- **Fix before publishing:** `requirements.txt` (**`pandas` is missing**, required by `build_giocatori.py`).
- **Do not publish / anonymise:** `Rose_lega-abendosa.xlsx`, `storico_asta_2025_26.xlsx` (real people's team
  names), `pagina_asta.html` (330 KB DOM dump), `__pycache__/`.
- **Decide deliberately:** `Dati/**` and `giocatori_2026_27.xlsx` (fantacalcio.it data — see 12.4).

---

## 11. What is missing for reproducibility (open state)

The most important section for whoever builds the repo: **the pipeline is currently not reproducible
end-to-end** from the material on disk alone.

1. **ML training script — RECOVERED.** It wasn't among the project's files
   on disk, but the complete code (HistGradientBoostingRegressor, temporal
   cross-validation, conformalized quantile regression) was found in the
   transcript of the original session (saved in Basic Memory) and now lives
   in `pricing/model/train_model.py` and `pricing/model/build_hreg.py`,
   re-run against real data and validated against the original session's
   numbers (see `docs/data-sources.md`). SHAP, on the other hand, never
   appears as executed code in the transcript, only as a stated intention:
   it was not implemented, contrary to what this same document claims
   further below.
2. **`predizioni_2026_27_v2.csv` / `.xlsx` — FOUND.** It wasn't in the
   project folder but in the Downloads folder on the Windows partition
   (`predizioni_2026_27_v2_1.csv`, 517 rows, the most recent generation).
   Input to `modello_prezzo.py` and `build_giocatori.py` (estimated
   matchdays missed, 2025-26 appearances and fantasy average); not shipped
   in this public repo (a fantacalcio.it-derived dataset) but exists on the
   author's disk.
3. **`Hreg.pkl` — RECOVERED.** Holds the hierarchical shrinkage (`fm_storica`, `fm_shrunk`, `fm_L1`,
   `correzione_fm`, `n_stagioni`) feeding layer 3b. The script that builds it was found in the
   transcript of the original session and now lives at `pricing/model/build_hreg.py`, re-run
   against real data and validated (identical numbers to the original session — see
   `docs/data-sources.md`). If you don't generate it, `modello_prezzo.py` still works: mean
   reversion just switches itself off.
   **Related bug found and fixed in this repo**: when the file is absent,
   `modello_prezzo.py` used to crash anyway, because the final output
   column selector always referenced `n_stagioni`/`fm_L1`/`fm_storica`/
   `fm_shrunk` even when they had never been created — not just a missing
   file, but a crash. Fixed by setting those columns to `NaN` in the
   branch that handles a missing `Hreg.pkl`.
4. **`probabili-formazioni-serie-a` (HTML) — FOUND.** It wasn't in the
   project folder but in a `Downloads` subfolder on the Windows partition
   (717 KB, saved on 2026-08-17). Not shipped in this public repo
   (third-party fantacalcio.it content) but exists on the author's disk.
5. **Latest-generation intermediate CSVs — MISSING.** The ones on disk are older than the final xlsx
   (section 5.4). The versions that produced `giocatori_2026_27.xlsx` lived in a temporary sandbox.
6. **Hard-coded paths.** `modello_prezzo.py`, `verdetto.py`, `build_giocatori.py`,
   `build_storico_arricchito.py` and `parse_rose_lega.py` contain absolute paths such as
   `/mnt/user-data/outputs/...`, `/mnt/user-data/uploads/...` and `/mnt/project/...` — leftovers from the
   environment where the scripts were run. Replace with CLI arguments or a config file.
7. **Incomplete `requirements.txt`.** It covers the server but not the pipeline: `pandas` is missing (and
   `scikit-learn` will be needed once training is reintegrated). `scipy` is listed but not imported by the server.
8. **Team-count mismatch.** `build_giocatori.py` and `vorp_live.py` use `NSQ = 10`; `modello_prezzo.py` and
   `verdetto.py` still hard-code a **12-team** league (`BUDGET_TOT = 12*1000`, `SLOT = 36/96/96/72`). Role
   quotas (10/20/30/40%) are invariant, so the curve's shape holds and the system is usable as-is; but before
   regenerating prices from scratch, decide whether to bring layers 1-3 to 10 teams as well. The README now
   flags this explicitly.
9. **No version control.** The folder is not a Git repository: there is no change history.
10. **Clean sheets only for 2025-26**, manually entered: the table must be redone for the next season.

---

## 12. Preparing the open-source repository

### 12.1 Suggested layout
See the tree in Part I, section 12.1. Note: if you move the userscripts into `browser/`, **update the README
references**, which currently point at `server/`.

### 12.2 Secrets and personal data to strip BEFORE the first commit

**[DONE in this repo]** The original password has been removed from
`server/auth.py` (now requires `ASTA_PASSWORD`, mandatory, no default in
the code), from `browser/asta-live.user.js` and `browser/scraper.js`
(replaced with the `"INSERISCI_LA_TUA_PASSWORD"` placeholder), and from
every occurrence in the operational docs.

1. **Password** in `server/auth.py`, `server/asta-live.user.js`
   (CONFIG.PASSWORD), `server/scraper.js` (CONFIG.PASSWORD), and mentioned
   several times in `README.md`. Replace with a mandatory environment
   variable and, in the userscripts, a `"YOUR_PASSWORD_HERE"` placeholder.
2. **`MIA_SQUADRA = "NapoLanza"`** in `server/live_state.py` → configuration parameter.
3. **League team names** inside `Rose_lega-abendosa.xlsx` and `storico_asta_2025_26.xlsx`: these were chosen
   by real people. Either exclude them or anonymise (`Team 1`, `Team 2`, …). A sample file is still needed to
   run the code: create a **synthetic** one.
4. **`pagina_asta.html`**: a full dump of the auction page; may contain team names and league state. Do not publish.

### 12.3 Minimal `.gitignore`
```
__pycache__/
*.pyc
.venv/
*.pkl
probabili-formazioni-serie-a
Rose_lega-*.xlsx
pagina_asta.html
```

### 12.4 Licensing and data redistribution — decide deliberately
The **code** can be released freely (MIT/Apache-2.0). The **data** is a separate matter: the `Statistiche_*`,
`Quotazioni_*` and per-matchday ratings files are produced by **fantacalcio.it** and redistributing them may
not be permitted. Prudent recommendation:

- do **not** commit fantacalcio.it xlsx files to the repo;
- document in `docs/data-sources.md` exactly **which files are needed, where to download them and how they
  are named**, so anyone can rebuild the dataset;
- ship a small **synthetic dataset** (10-20 invented players) so tests run and the system can be seen working
  without anyone else's data;
- if you still want to publish derived artifacts (`giocatori_2026_27.xlsx`), check the site's terms first:
  it is derived, but it carries columns that come straight from them (`FVM`, `QtI`).

A practical rather than legal note: this choice is not merely formal — it is what makes the repo usable in
leagues other than yours, because it forces the data format to be documented instead of assumed.

### 12.5 Suggested work order for the agent
1. Strip secrets (12.2) — **blocking**, before any commit.
2. Parameterise hard-coded paths (11.6) — without this the repo runs on no machine.
3. Correct and split the `requirements` files (11.7).
4. English README + adaptation of this dossier into `docs/`.
5. Synthetic sample dataset + tests running in CI.
6. Rebuild the ML training script (11.1) — the largest missing piece.
7. Decide on the team count (11.8) and align `modello_prezzo.py` / `verdetto.py`.

---

## 13. Note on the language of the code (to be carried into the repo README)

The project was written by a native Italian speaker for an Italian league, in a domain — *fantacalcio* — whose
terms **have no standard English translation** (*fantamedia*, *quotazione*, *titolarità*, *fascia*, *FVM*).
Consequently:

- comments, docstrings and variable names are **in Italian** and **stay in Italian**;
- do not translate the code, do not rename identifiers, do not rewrite comments;
- accessibility for an international audience is provided by the **bilingual documentation** and the glossary.

This is a deliberate choice. State it openly in the repo README, so an outside contributor knows what to
expect instead of opening a pull request to "internationalise" the code.

---

## 14. Glossary EN ← IT

See the table in Part I, section 14 — it is already bilingual and applies to both parts.

---

*Documento generato il 13 settembre 2026 ispezionando direttamente i file del progetto su
`C:\Users\<utente>\Desktop\Fantacalcio\`. Tutte le cifre riportate come "verificate" sono state ricalcolate dai
file stessi; le informazioni sul modello ML (R², copertura, SHAP) provengono dalla documentazione di progetto
perché il codice di training non è presente sul disco.*

*Document generated on 13 September 2026 by directly inspecting the project files at
`C:\Users\<utente>\Desktop\Fantacalcio\`. Every figure marked "verified" was recomputed from those files;
information about the ML model (R², coverage, SHAP) comes from project documentation because the training code
is not present on disk.*
