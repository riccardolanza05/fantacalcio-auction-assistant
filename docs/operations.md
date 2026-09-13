# Guida operativa — far girare l'assistente live

Documento di dettaglio, in italiano. Presuppone PC e telefono sulla
**stessa rete WiFi**. Per l'idea generale vedi [README.it.md](../README.it.md);
per come funziona il modello vedi [methodology.md](methodology.md).

## 1. Setup (una volta sola)

```bash
cd server
pip install -r ../requirements.txt
ASTA_PASSWORD="una-password-tua" python app.py
```

Dovresti vedere `Uvicorn running on http://0.0.0.0:8000`.

`requirements.txt` copre il solo server d'asta. Per rigenerare i dati
(`build_giocatori.py`, `build_storico_arricchito.py`) serve in piu'
`requirements-pipeline.txt` (pandas, numpy, openpyxl).

Il server **non si avvia** senza `ASTA_PASSWORD` impostata (vedi
`server/auth.py`): e' l'unica autenticazione, e senza non c'e' un default
da scoprire in giro.

Trova l'IP locale del PC:
- Windows: `ipconfig` → cerca "Indirizzo IPv4" (es. `192.168.1.23`)
- Mac: `ipconfig getifaddr en0`
- Linux: `ip addr` o `hostname -I`

## 2. Calibrazione dei selettori DOM

I selettori in `browser/scraper.js` e `browser/asta-live.user.js` sono
quelli osservati sul DOM reale di FantaAsta Live al momento in cui questo
progetto e' stato scritto. Se l'interfaccia cambia, vanno ricalibrati:

- giocatore in asta: `ui-player-showcase`, con `.player-name`,
  `.player-team`, ruolo da
  `ui-player-roles[data-game='1'] ui-role span.role` (data-label
  gk/def/mid/atk), FVM da `ui-player-row.selected .stats`
- **id giocatore**: estratto dall'URL della card immagine
  (`.../campioncini/21/card/2764.png` → id 2764). E' il match ESATTO col
  database: la card mostra "Lautaro Martinez" mentre i file usano
  "Martinez L.", quindi il match per nome fallirebbe proprio sui big.
- squadre: `ui-rosters-grid nz-card.team-card`, nome da
  `ui-team-card .team-name span`, contatori ruolo da
  `ui-roles-info header ui-chip`, BUDGET/MAX da
  `ui-roles-info footer ui-chip`

`browser/inspector2.js` serve a ricalibrare i selettori se in futuro
FantaAsta Live cambia grafica.

## 3. Durante l'asta

### Opzione A — Tampermonkey (consigliata)

1. Installa l'estensione **Tampermonkey** dal Chrome Web Store.
2. Icona Tampermonkey → **Crea un nuovo script**.
3. Cancella tutto il contenuto dell'editor.
4. Apri `browser/asta-live.user.js`, imposta `CONFIG.PASSWORD` sulla stessa
   password che hai messo in `ASTA_PASSWORD`, copia **tutto**, incolla
   nell'editor.
5. **Ctrl+S** per salvare.
6. Apri (o ricarica) `https://fanta-asta-live.fantacalcio.it/#/main`.

Alla prima esecuzione Tampermonkey chiede il permesso di contattare
`localhost`: **concedilo** (scegli "Sempre consenti" per non ripetere).

### Opzione B — Console (per prove rapide)

F12 → Console → incolla `browser/scraper.js` (con `CONFIG.PASSWORD`
impostata) → invio. Va rifatto ad ogni ricarica della pagina.

Anche questa via e' autenticata: lo script manda la password come primo
messaggio sulla WebSocket. Se vedi `403 / token non valido` nel log del
server, controlla che `CONFIG.PASSWORD` coincida con `ASTA_PASSWORD`.

### Poi, in entrambi i casi

1. Sul PC: `ASTA_PASSWORD="..." python app.py` (dalla cartella `server/`).
2. Sul telefono, stessa WiFi: apri `http://<IP_DEL_PC>:8000`. Chiede la
   password: la digiti una volta sola, il token resta salvato sul telefono
   finche' il server non viene riavviato.
3. Controlla l'overlay: deve dire `server: connesso` e
   `squadre lette: <numero squadre della tua lega>`.

## 4. Se non compare NIENTE (nessun overlay in basso a destra)

Procedi in ordine.

**Passo 1 — Tampermonkey esegue qualcosa?** Installa
`browser/test-tampermonkey.user.js` e ricarica la pagina d'asta: disegna
solo una banda verde in alto, per verificare che l'estensione stia
eseguendo script.
- Banda assente → passo 2. Banda presente → passo 3.

**Passo 2 — Modalita' sviluppatore di Chrome.** Dalle versioni recenti
(Manifest V3) Chrome non permette a Tampermonkey di eseguire userscript
finche' non abiliti la modalita' sviluppatore. E' silenzioso: nessun
errore, semplicemente non parte niente. E' di gran lunga la causa piu'
comune di "installato ma non succede nulla".
1. Apri `chrome://extensions`
2. Attiva **Modalita' sviluppatore**
3. Ricarica la pagina d'asta

(Su alcune versioni la voce si chiama "Consenti script utente", dentro i
dettagli dell'estensione Tampermonkey.)

**Passo 3 — Lo script principale e' attivo sulla pagina?** L'icona di
Tampermonkey deve mostrare il badge **1**. Se mostra 0, controlla
l'interruttore dello script e che tu sia davvero su
`fanta-asta-live.fantacalcio.it`.

**Passo 4 — Permesso verso localhost.** Se l'hai negato, lo script parte ma
non riesce a parlare col server ("server non raggiungibile"). Elimina lo
script da Tampermonkey e reinstallalo per farti richiedere di nuovo il
permesso.

**Passo 5 — Console.** F12 → Console. All'avvio lo script scrive
`[asta-live] script avviato`. Riga assente → torna al passo 2.

**Alternativa immediata**: `browser/scraper.js` in console (F12) fa le
stesse letture senza Tampermonkey, ma va reincollato a ogni ricarica e
parla col server via WebSocket, che su HTTPS puo' essere bloccata come
contenuto misto — se succede, l'unica via che funziona davvero e' lo
userscript Tampermonkey (`GM_xmlhttpRequest`).

## 5. Se un giocatore risulta "non presente nel pool"

Il pool contiene tutti i giocatori del tuo `server/giocatori_2026_27.xlsx`
(517 nella lega originale), quindi un "non trovato" e' quasi sempre un
problema di lettura, non di dati mancanti:

1. Guarda l'**overlay**: la riga `id letto:` deve mostrare un numero. Se
   dice `NESSUNO`, l'immagine della card non e' stata letta e il sistema
   ripiega sul nome.
2. Guarda il **log del server**: per ogni giocatore stampa con quale
   metodo e' stato risolto (`id`, `nome_lista`, `nome_esteso`) oppure un
   warning con i dati grezzi ricevuti se non lo trova.
3. Prova il **diagnostico**: `http://localhost:8000/diag?id=2097` oppure
   `http://localhost:8000/diag?nome=Moise Kean&squadra=Fiorentina`.

Il match e' tentato in tre modi, in ordine: id numerico dalla card immagine
(esatto), nome abbreviato dalla lista laterale, nome esteso della card
risolto per cognome + iniziale — quest'ultimo distingue correttamente anche
gli omonimi (es. due giocatori con lo stesso cognome in squadre diverse).

## 6. Password

Il server ascolta su `0.0.0.0` per farsi raggiungere dal telefono, quindi
senza password chiunque sulla tua WiFi potrebbe aprire la pagina e vedere
le tue stime.

- **Impostarla**: `ASTA_PASSWORD="una-password-tua" python app.py`
  (obbligatoria, il server non si avvia senza).
- **Telefono**: alla prima apertura compare la schermata di login.
- **Userscript**: fa il login da solo — la password sta in
  `CONFIG.PASSWORD` in cima a `browser/asta-live.user.js`: deve coincidere
  con `ASTA_PASSWORD`.

I token si azzerano ad ogni riavvio del server: telefono e userscript se ne
accorgono e rifanno il login da soli.

Un limite da conoscere: il traffico viaggia in HTTP in chiaro sulla rete
locale. Protegge dalla curiosita' di chi e' sulla stessa WiFi, non da un
attacco vero — adeguato per un'asta tra amici, non riusare questa password
altrove.

## 7. Prezzi dell'asta dell'anno scorso

### Il file deve stare accanto ad `app.py`

Copia il tuo export `Rose_lega-<tuasigla>.xlsx` nella cartella `server/`,
accanto ad `app.py`. Senza quel file ogni giocatore risultera' "non
acquistato l'anno scorso". La ricerca del file e' tollerante
(maiuscole/minuscole, spazi al posto degli underscore, cartella superiore o
`server/data/`), ma il nome deve iniziare per `rose_lega`.

All'avvio il server lo dice chiaramente nel log (quanti file, quanti
acquisti, quanti in comune col pool corrente); un blocco di WARNING con
"NESSUN FILE D'ASTA TROVATO" significa che il file non e' dove serve.

### Verifica

- `http://localhost:8000/diag/storico` → quanti file e quanti acquisti
- `http://localhost:8000/diag/storico?nome=Kean&squadra=Fiorentina` → il
  prezzo di quel giocatore

### Rigenerare i dati

```bash
python server/build_storico_arricchito.py \
    --rose server/Rose_lega-<tuasigla>.xlsx \
    --quotazioni <path>/Quotazioni_Fantacalcio_Stagione_AAAA_AA.xlsx \
    --statistiche <path>/Statistiche_Fantacalcio_Stagione_AAAA_AA.xlsx \
    --out server/storico_asta_AAAA_AA.xlsx
```

## 8. Riferimenti dall'asta scorsa (quando manca il prezzo reale)

Se una squadra ha cambiato titolare in un ruolo, per il nuovo arrivato lo
storico non ha nulla da dire. Il telefono mostra allora fino a due
riferimenti:

1. **Stesso ruolo e stessa squadra** — chi occupava quel posto l'anno
   scorso: cattura sia il livello del club sia il ruolo in rosa.
2. **Stesso ruolo, squadra diversa, quotazione e FVM simili** — chi, in
   tutta la lega, partiva da una valutazione di mercato paragonabile.

Il ruolo e' sempre un filtro obbligatorio. Se in quella squadra e ruolo
l'anno scorso non fu comprato nessuno (tipico delle neopromosse), il
secondo criterio propone due candidati invece di uno, per avere comunque un
intervallo. Scatta **solo** se il giocatore non era all'asta dell'anno
scorso: un dato esatto non viene mai sostituito da una stima per analogia.

| posizione | criteri | pesi |
|---|---|---|
| stessa squadra | titolarita', FVM | 0.60 / 0.40 |
| altra squadra | FVM, quotazione, titolarita' | 0.45 / 0.40 / 0.15 |

## 9. Come rileva chi ha comprato, cosa e a quanto

Tre segnali, in ordine di affidabilita':

1. **Righe rosa** (`ui-roster ui-player-row`) — confrontando la rosa con
   l'ultima lettura si sa esattamente chi e' stato comprato. Via
   principale.
2. **Contatori per ruolo e TOT** — sempre presenti, dicono quanti acquisti
   sono avvenuti anche quando le righe non sono visibili (virtual scroll).
3. **Giocatore in vetrina** — solo come ripiego.

Il costo si deduce dal calo del budget. Se nello stesso intervallo la
squadra ha preso piu' di un giocatore, il costo del singolo non e'
ricavabile: l'evento compare sul telefono ma non viene passato al motore.
Il primo snapshot di ogni squadra fa solo da riferimento e non genera
eventi.

## 10. Infortuni

I dati arrivano da `probabili-formazioni-serie-a` (la pagina
`https://www.fantacalcio.it/probabili-formazioni-serie-a` salvata come
HTML) messa nella cartella `server/`. Per aggiornarli prima di ogni
giornata: risalva la pagina e rilancia `build_giocatori.py`.

## 11. La tua squadra

Il server cerca tra le rose quella con il nome in `MIA_SQUADRA`
(`server/live_state.py`, sovrascrivibile con la variabile d'ambiente
`MIA_SQUADRA` senza toccare il codice) e mostra la percentuale del budget
spesa per reparto. Se quella rosa non e' tra quelle lette, non viene
mostrato nulla — meglio niente che una ripartizione riferita alla squadra
sbagliata.

## 12. Limiti noti

- Se due assegnazioni avvengono nello stesso intervallo di polling (2s), il
  costo della seconda non e' deducibile con certezza. Puoi abbassare
  `POLL_INTERVAL_MS` a 1000 se la tua asta e' molto veloce.
- Il rilevamento richiede che la card della squadra sia visibile almeno una
  volta prima e una volta dopo l'acquisto.
- Se FantaAsta Live cambia interfaccia, lo scraper puo' smettere di
  funzionare: l'overlay lo segnala subito (squadre lette: 0).
- Un giocatore fuori dal pool del modello mostra solo l'FVM letto dal vivo.
- L'overlay si nasconde/mostra con **Ctrl+Shift+A**.
