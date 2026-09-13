# Metodologia

Documento di dettaglio, in italiano (vedi la nota sulla lingua in
[README.it.md](../README.it.md)). Per l'introduzione generale al progetto e
per il riassunto in inglese vedi [README.md](../README.md) /
[README.it.md](../README.it.md); qui si entra nel merito di come funziona
il modello e perche' e' fatto cosi'.

## 1. Principio architetturale

Il sistema e' organizzato in **4 strati, in ordine di autorita'
decrescente**. Ogni strato puo' correggere il precedente solo entro limiti
prefissati — mai stravolgerlo. Il mercato (l'FVM di fantacalcio.it) ha
sempre l'ultima parola sulla *forma* della curva dei prezzi; il modello
statistico sposta i prezzi, non li reinventa. E' una scelta metodologica,
non una limitazione tecnica: e' il motivo per cui il sistema si comporta in
modo prevedibile anche quando il modello sbaglia.

```
STRATO 1  Ancora di mercato (FVM)              — la forma della curva
STRATO 2  Quote per reparto (10/20/30/40%)     — il livello per ruolo
STRATO 3  Correzione statistica (modello ML)   — sposta, con tetto
STRATO 4  VORP / scarsita' (live, in asta)     — la correzione piu' debole
```

Implementazione: `pricing/modello_prezzo.py` (strati 1-3) e
`server/vorp_live.py` (strato 4).

## 2. Contesto di lega usato per calibrare i numeri

| Parametro | Valore |
|---|---|
| Squadre | 10 (in precedenza 12 — vedi nota sul disallineamento sotto) |
| Budget per squadra | 1000 crediti |
| Budget di lega | 10.000 crediti |
| Rosa per squadra | 3 P / 8 D / 8 C / 6 A |
| Quote di budget per reparto | 10% P / 20% D / 30% C / 40% A |

Le quote di reparto erano il *prior* dell'autore, poi confermato
empiricamente sui prezzi realmente pagati in asta. E' il parametro che rende
la valutazione **dipendente dal ruolo**: lo stesso rendimento atteso vale
diversamente in porta e in attacco, perche' i reparti competono per fette di
budget diverse.

**Disallineamento noto**: `server/build_giocatori.py` e
`server/vorp_live.py` usano `NSQ = 10`; `pricing/modello_prezzo.py` e
`pricing/verdetto.py` hanno ancora cablata una lega da **12** squadre
(`BUDGET_TOT = 12*1000`, slot 36/96/96/72). Le quote di reparto sono
invarianti al numero di squadre, quindi la *forma* della curva resta valida
e il sistema e' usabile cosi' com'e'; ma prima di rigenerare i prezzi da
zero per una lega diversa conviene decidere se portare anche gli strati 1-3
al numero di squadre corretto (le costanti sono in cima a ciascun file).

## 3. Strato 1 — Ancora di mercato (FVM)

L'FVM di fantacalcio.it e' gia' calibrato sul mercato reale: contiene
informazione (aspettative estive, hype, notizie di mercato) che nessun
modello statistico possiede. Per questo fornisce la **forma** della curva
dei prezzi — la struttura a fasce — che il modello non reinventa.

## 4. Strato 2 — Quote per reparto (10/20/30/40)

L'FVM grezzo implica una ripartizione diversa da quella voluta (circa
5.7/20.1/34.8/39.4% invece di 10/20/30/40%). Si riscala l'FVM di ciascun
ruolo perche' la somma sui giocatori effettivamente acquistati centri la
quota voluta:

```
per ogni ruolo R:
    draftati = i primi SLOT[R] giocatori per FVM
    residuo  = BUDGET_TOT * QUOTA[R] − SLOT[R] * PREZZO_MIN
    k        = residuo / somma_FVM(draftati)
    base_i   = PREZZO_MIN + FVM_i * k          (PREZZO_MIN = 1 credito)
```

**Fasce.** Dentro ciascun ruolo i giocatori sono ordinati per FVM e divisi
in cinque fasce (`top, semitop, terza, quarta, minori`):

| Ruolo | top | semitop | terza | quarta | minori |
|---|---|---|---|---|---|
| P | 8 | 5 | 5 | 5 | resto |
| D | 11 | 12 | 15 | 15 | resto |
| C | 6 | 12 | 15 | 15 | resto |
| A | 6 | 8 | 12 | 12 | resto |

Nella coda l'FVM non discrimina (nella stagione osservata tutti i portieri
oltre il 24° avevano FVM = 1): l'ordinamento usa quindi una chiave composta,
rango FVM come criterio primario (peso 1000) piu' rango della produzione
attesa come spareggio.

## 5. Strato 3 — Correzione statistica

Due componenti, entrambe dentro lo stesso tetto.

**3a — divergenza modello/mercato.** Si confronta il *percentile* di
produzione attesa col *percentile* FVM, dentro il ruolo:
`div_modello = pct_modello − pct_mercato`. I percentili (non i valori
assoluti) rendono il confronto immune alle scale diverse di ruoli e
stagioni.

**3b — regressione alla media.** Penalizza chi nell'ultima stagione ha
fatto meglio del proprio livello storico. I coefficienti di persistenza
sono stati stimati sullo storico multi-stagione (n=2950 giocatori con
almeno 10 presenze) e dipendono fortemente dal ruolo:

| Ruolo | Coefficiente di persistenza |
|---|---|
| P (portieri) | **−0,08** |
| D (difensori) | 0,705 |
| C (centrocampisti) | 0,904 |
| A (attaccanti) | 0,810 |

Il portiere e' il caso estremo: una sua annata sopra il proprio livello
**non si ripete affatto** (coefficiente negativo). Giustifica da solo il
tetto di correzione molto basso imposto ai portieri (vedi sotto). L'FVM non
corregge questo effetto perche' riflette anche la popolarita' del momento;
il modello di produzione si', ma il prezzo e' ancorato all'FVM, quindi la
correzione va applicata a valle:

```
div_regressione = clip(correzione_fm / sd_ruolo, −2, +2) * 0.25 * PESO_REGRESSIONE
                                                            (PESO_REGRESSIONE = 0.5)
```

La `correzione_fm` viene da uno shrinkage gerarchico (`Hreg.pkl`, generato
da `pricing/model/build_hreg.py`, vedi `docs/data-sources.md`); se il file
manca, lo strato 3b si disattiva silenziosamente e vale 0.

**Doppio tetto.** La correzione totale e' limitata da un tetto assoluto per
ruolo e da un tetto relativo:

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

La logica: un errore di 5 crediti su un portiere e' grave quanto un errore
di 30 su un attaccante, perche' i reparti competono per quote di budget
diverse.

**Normalizzazione iterativa.** I giocatori di quinta fascia hanno un tetto
di prezzo calibrato sul 90° percentile dei prezzi realmente pagati
(P 5, D 22, C 22, A 23 crediti). Il clip dei minori sottrae budget, che va
riassorbito dalle fasce superiori — il che puo' richiedere un nuovo clip:
`normalizza()` itera fino a 30 volte, uscendo quando lo scarto dalle quote
scende sotto 1 credito. La regola "i minori costano 1-5 crediti" vale
**solo per i portieri**; negli altri reparti la coda e' molto piu' cara.

**Controllo di continuita'.** Una funzione dedicata verifica che non ci
siano salti tra fasce contigue: l'ultimo `top` deve costare quanto il primo
`semitop`. Le fasce descrivono come si compongono le rose, non scalini di
prezzo — non c'e' omogeneita' *dentro* la fascia, ma continuita' *tra*
fasce adiacenti.

## 6. Il verdetto di valutazione

Implementazione: `pricing/verdetto.py`.

**Domanda:** questo giocatore, al prezzo a cui sta andando, conviene?

Due trappole evitate esplicitamente:

1. **Non si confrontano crediti fra ruoli diversi.** Un attaccante da 100
   crediti e un portiere da 100 non sono paragonabili: il confronto e'
   sempre dentro il ruolo.
2. **Non si usa solo la stima puntuale.** Gli intervalli conformi sono
   calibrati (copertura empirica verificata 81,6% su dato mai visto): il
   verdetto e' dichiarato **robusto** solo se regge anche usando l'estremo
   sfavorevole dell'intervallo.

**Metrica: rendimento per credito**, normalizzato sulla mediana del proprio
ruolo calcolata solo sui giocatori che verranno effettivamente acquistati:

```
indice      = (produzione_attesa / prezzo) / mediana_ruolo
indice_p10  = (p10 / prezzo) / mediana_ruolo
indice_p90  = (p90 / prezzo) / mediana_ruolo
```

Soglie: `indice ≥ 1,15` → sottovalutato; `indice ≤ 0,85` → sopravvalutato;
in mezzo → valutato correttamente. "Robusto" se `indice_p10 ≥ 1` (regge
anche nello scenario sfavorevole) oppure `indice_p90 ≤ 1` (sopravvalutato
anche in quello favorevole).

Si calcola anche il **prezzo di indifferenza** (al quale il giocatore
renderebbe come la mediana del ruolo) e il **margine** = prezzo di
indifferenza − prezzo: quanti crediti puoi salire restando in vantaggio.

### Calibrazione della soglia (backtest)

Backtest su 6 stagioni, ciascuna predetta usando solo il proprio passato.
Testate le soglie di scarto 10/15/20/25/30%: la separazione tra
sottovalutati e sopravvalutati cresce quasi linearmente con la soglia (da
2,40× a 3,06×) — non esiste un taglio "naturale", e' un compromesso tra
separazione e copertura. Si e' scelto **10%** perche' e' la soglia con
minore variabilita' del segnale fra stagioni (dev. std del rapporto 0,52,
contro 0,60 al 15% e fino a 0,75 al 30%) e copre l'83% dei giocatori contro
il 51-73% delle soglie piu' alte.

**Risultato del backtest a quella soglia:** i sottovalutati hanno prodotto
**1,86×** e i sopravvalutati **0,77×** la produzione poi realmente
realizzata, in tutte e 6 le stagioni testate. La correlazione di rango
(Spearman) fra prezzo del modello e resa effettiva varia fra 0,43 e 0,74 a
seconda della stagione.

### Doppio riferimento

Nella versione finale il verdetto e' calcolato due volte:

| Fascia | Riferimento | Perche' |
|---|---|---|
| top, semitop, terza | `verdetto_base` / `scarto_base_pct` | il budget c'e' davvero, il confronto col riferimento del modello e' pulito |
| quarta, minori | `verdetto_lega` / `scarto_lega_pct` | coglie la dinamica di fine asta sulle code, dove il prezzo lo fa l'obbligo di riempire gli slot |

Il database traccia quale riferimento e' stato usato (`rif_verdetto`), ed e'
mostrato all'utente: e' un'informazione che serve a sapere quanto fidarsi
del numero. Sulle code gli scarti percentuali diventano enormi (+280%,
+560%) perche' si dividono per prezzi di pochi crediti — su un giocatore da
3 crediti un +500% vale 15 crediti, non e' un affare da rincorrere. Per
questo su quelle fasce conta piu' il verdetto che la percentuale.

### Il fallimento che ha portato a questo disegno

La prima versione del verdetto usava come riferimento un modello
comportamentale addestrato su **una sola asta reale**. Risultato: verdetti
completamente instabili, deviazione standard **≈ 241%**. Sostituendo il
riferimento con l'FVM riscalato per quote di reparto (strati 1+2) la
deviazione standard e' scesa a **≈ 10,9%**. Lezione registrata nel
progetto: *il riferimento conta piu' del modello*.

## 7. Strato 4 — Correzione di scarsita' live

Implementazione: `server/vorp_live.py`, classe `VorpLive`.

**Domanda a cui risponde:** esistono ancora alternative valide per questo
giocatore? La risposta non dipende da quanti giocatori restano in assoluto,
ma da come e' composto cio' che resta.

**Livello di rimpiazzo.** Ricalcolato a ogni acquisto: la produzione attesa
del giocatore che occuperebbe l'ultimo slot da titolare ancora libero del
ruolo. `vantaggio_vorp = produzione_attesa − livello_rimpiazzo`.

**Scarsita', due componenti:**

- **Composizione (peso 0,75)** — quale quota del blocco alto ancora libero
  (top+semitop+terza) e' fatta di giocatori almeno pari a lui.
  Normalizzata sulla quota di inizio asta (senza normalizzazione i top
  risulterebbero scarsi gia' a mercato intatto, essendo per costruzione una
  minoranza):
  ```
  composizione = max(0, 1 − quota_ora / quota_inizio)
  ```
- **Deplezione (peso 0,25)** — quanti giocatori di livello pari o
  superiore sono gia' stati presi in assoluto. Copre il caso "restano 5 top
  su 10": proporzionalmente ce ne sono ancora tanti, ma il reparto si sta
  svuotando e un piccolo premio e' giustificato.

```
scarsita = 0.75 * composizione + 0.25 * deplezione       (poi troncata in [0,1])
```

**Correzione finale:**

```
tetto      = min( TETTO_CORREZIONE[ruolo] , prezzo_base * 0.30 )   # stessi tetti dello strato 3
grezza     = tanh( vantaggio_vorp / 50 ) * tetto                    # satura dolcemente
correzione = clip( grezza * scarsita , −tetto , +tetto )
```

Tre freni deliberati: il tetto per ruolo, la saturazione `tanh` (un
vantaggio enorme non produce una correzione enorme), e il fattore scarsita'
(finche' ci sono alternative, la correzione tende a zero).

**Comportamento verificato sugli attaccanti** (test riproducibile in fondo
a `server/vorp_live.py`):

| Scenario | top | semitop | terza |
|---|---|---|---|
| inizio asta (6/8/12 liberi) | +0,0 | +0,0 | +0,0 |
| restano 1 top, 2 semitop, 7 terza | **+17,2** | +14,5 | +2,6 |
| restano 5 top e 5 semitop | +1,1 | +2,0 | — |

**Deriva di mercato.** Se la lega sta pagando sistematicamente sopra il
modello, la stima si sposta: si accumulano i log-rapporti
`log(prezzo_pagato / prezzo_modello)` per ruolo, la media viene smorzata
con peso `n/(n+5)` e troncata a ±30%:

```
deriva = exp( clip( media_log * n/(n+5) , log(0.7) , log(1.3) ) )
prezzo_consigliato = max(1, (prezzo_modello + correzione_strato4) * deriva)
```

Lo smorzamento evita di inseguire il rumore dei primi acquisti; il tetto
evita che un'asta anomala travolga il modello.

### Il tentativo scartato: tracker Bayesiano completo

La prima versione dello strato 4 era un tracker Bayesiano
Normal-Inverse-Gamma che aggiornava le stime a ogni acquisto osservato.
Fallimento: lavorando su un fair value VORP puro (non ancorato all'FVM)
produceva moltiplicatori 6-10× sui giocatori di coda — prezzi assurdi
proprio dove l'asta e' piu' affollata. Sostituito dall'approccio a
composizione/scarsita' sopra descritto.

Conclusione metodologica registrata nel progetto: un modello gerarchico
bayesiano completo e' piu' adatto **offline** che live. Le ragioni concrete
sono la latenza e la scarsita' di osservazioni per sottogruppo durante
un'asta; live funzionano meglio fattori di correzione per ruolo/fascia
aggiornati incrementalmente, che approssimano uno shrinkage bayesiano
empirico.

## 8. Il modello di produzione attesa (a monte della pipeline)

Implementazione: `pricing/model/train_model.py` (training + predizione) e
`pricing/model/build_hreg.py` (shrinkage per lo strato 3b). Recuperati
dalla trascrizione della sessione originale in cui sono stati sviluppati e
rieseguiti sui dati reali per verificarne la fedelta' (dettagli in
`docs/data-sources.md`, sezione 3).

- Algoritmo: `HistGradientBoostingRegressor` (gradient boosting su
  istogrammi, scikit-learn). Scelta motivata: il gradient boosting batte le
  reti neurali su dati tabellari di questa dimensione — non e' un'opinione
  di comodo, e' il motivo esplicito per cui non e' stata usata una rete.
- Validazione: cross-validation **temporale** (ogni stagione predetta
  usando solo il proprio passato). Performance: R² ≈ 0,467.
- Intervalli: regressione quantile conformalizzata per p10/p90, con
  copertura empirica **81,6%** su dati mai visti (nominale 80%) — sono
  calibrati, non decorativi.
- Interpretabilita': valori SHAP **previsti ma non implementati** — nella
  trascrizione della sessione originale compare solo come intenzione
  dichiarata, mai come codice effettivamente eseguito (vedi
  `pricing/model/README.md`).
- Titolarita': la percentuale dalle probabili formazioni viene mappata sui
  tassi di presenza storici, per convertire una stima qualitativa ("e' il
  titolare") in un moltiplicatore di minuti.

## 9. Fasi dello sviluppo e problemi risolti nell'integrazione col browser

Per il dettaglio completo (matching dei nomi, rilevamento acquisti,
identita' delle rose, parser degli infortuni) vedi i docstring dei moduli
in `server/` — sono scritti apposta per essere la documentazione di
riferimento di ciascun problema, con la soluzione e il perche'. In sintesi,
i problemi piu' istruttivi:

- **WebSocket bloccata**: la pagina d'asta e' HTTPS, `ws://localhost` e'
  contenuto misto e Chrome lo blocca con un'eccezione sincrona che uccide
  lo script prima ancora dell'overlay. Soluzione: `GM_xmlhttpRequest`
  (contesto privilegiato dell'estensione) verso `POST /ingest`
  (`browser/asta-live.user.js`).
- **Identita' delle squadre**: rinominare una rosa creava una squadra
  fantasma. Soluzione: UID stabile del viewport DOM, poi sovrapposizione
  rosa ≥60%, poi nome (`server/live_state.py`).
- **Rilevamento acquisti**: il "giocatore in vetrina" non basta, perche' la
  vetrina si svuota tra un'assegnazione e la lettura successiva. Soluzione:
  confronto delle righe rosa tra snapshot.
- **Budget ricostruito, non accumulato**: un giocatore rimosso dalla rosa
  deve sparire anche dal calcolo della ripartizione.
- **Omonimi**: il fallback per cognome (due Pessina, due Martinez) si
  applica solo quando il cognome e' univoco nel pool.
