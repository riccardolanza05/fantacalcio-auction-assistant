"""
Server locale per l'asta live.
- /ws/extension  : lo script iniettato nel browser (PC) manda qui i dati estratti
- /ws/phone      : il telefono si collega qui e riceve lo stato aggiornato
- /              : pagina HTML mobile-friendly (static/phone.html)

Avvio:
    pip install -r requirements.txt
    python app.py
Poi sul telefono (stessa rete WiFi del PC): http://<IP_LOCALE_PC>:8000
Per trovare l'IP locale del PC: `ipconfig` (Windows, cerca "Indirizzo IPv4")
o `ifconfig` / `ip addr` (Mac/Linux).
"""
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import auth
from player_db import PlayerDB
from vorp_live import VorpLive
from live_state import LiveAuctionState
from simili import ProfiliSimili
from storico_prezzi import StoricoPrezzi

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("asta")

HERE = Path(__file__).parent
app = FastAPI()

# il server gira solo in locale sulla tua rete: CORS aperto e' innocuo qui
# e semplifica le chiamate dallo userscript
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# controllo esplicito all'avvio: se manca qualcosa lo dice subito e chiaro,
# invece di scoppiare solo quando il telefono si connette
for required in ["giocatori_2026_27.xlsx",
                  "static/phone.html", "static/login.html"]:
    if not (HERE / required).exists():
        raise FileNotFoundError(
            f"Manca il file '{required}' in {HERE}. "
            f"Controlla di avere copiato TUTTA la struttura di cartelle (incluso static/)."
        )

db = PlayerDB(str(HERE / "giocatori_2026_27.xlsx"))
# STRATO 4 del modello di prezzo: correzione VORP/scarsita' live.
# Sostituisce il vecchio tracker Bayesiano, che agiva su un fair value VORP
# puro e generava correzioni fuori scala.
vorp_live = VorpLive(list(db.by_id.values()))
log.info(f"Modello prezzi: {len(db.by_id)} giocatori, strato 4 (VORP live) attivo")

# --- prezzi delle aste passate ---
# Cerca i file d'asta in modo tollerante: maiuscole/minuscole indifferenti,
# accetta sia "Rose_lega-*" che "Rose lega*"/"rose_lega*", e guarda anche
# nella cartella superiore (capita di lasciarli accanto al progetto invece
# che dentro server/).
def _trova_file_aste() -> list[str]:
    trovati, visti = [], set()
    for cartella in (HERE, HERE.parent, HERE / "data"):
        if not cartella.is_dir():
            continue
        for f in sorted(cartella.iterdir()):
            if not f.is_file() or f.suffix.lower() != ".xlsx":
                continue
            nome = f.name.lower().replace(" ", "_")
            if nome.startswith("rose_lega") and f.resolve() not in visti:
                visti.add(f.resolve())
                trovati.append(str(f))
    return trovati

file_aste = _trova_file_aste()
storico = StoricoPrezzi(db, file_aste)

if not file_aste:
    log.warning("=" * 70)
    log.warning("NESSUN FILE D'ASTA TROVATO (Rose_lega-*.xlsx).")
    log.warning(f"Cercato in: {HERE} e {HERE.parent}")
    log.warning("Senza questo file OGNI giocatore risultera' 'non acquistato")
    log.warning("l'anno scorso'. Copia Rose_lega-abendosa.xlsx accanto ad app.py.")
    log.warning("=" * 70)
else:
    log.info(f"Storico aste: {storico.n_file} file caricati "
              f"({', '.join(os.path.basename(f) for f in file_aste)}), "
              f"{storico.n_record} acquisti, {storico.n_con_id} anche nel pool 2026-27")

# profili simili: usati solo quando un giocatore non era all'asta scorsa
simili = ProfiliSimili(str(HERE / "storico_asta_2025_26.xlsx"))
if simili.disponibile:
    log.info(f"Profili simili: {len(simili.righe)} giocatori storici con profilo completo")
else:
    log.warning("storico_asta_2025_26.xlsx assente: nessun confronto per analogia. "
                 "Generalo con: python build_storico_arricchito.py")

# elenco squadre presenti nello storico, per i menu della ricerca
SQUADRE_STORICO = sorted({v["squadra_reale"]
                           for voci in storico.per_cognome.values()
                           for v in voci})

state = LiveAuctionState(db, vorp_live=vorp_live, storico=storico, simili=simili)

phone_clients: set[WebSocket] = set()


async def broadcast_to_phones():
    if not phone_clients:
        return
    payload = json.dumps(state.full_state(), default=str)
    dead = []
    for ws in phone_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        phone_clients.discard(ws)


def _richiedi_auth(request: Request):
    token = (request.headers.get("X-Auth-Token")
             or request.query_params.get("token"))
    if not auth.token_valido(token):
        raise HTTPException(status_code=401, detail="Token mancante o non valido")


@app.post("/login")
async def login(body: dict):
    """Scambia la password con un token di sessione."""
    if not auth.verifica_password(body.get("password", "")):
        log.warning("Tentativo di login con password errata")
        raise HTTPException(status_code=401, detail="Password errata")
    token = auth.nuovo_token()
    log.info("Login riuscito, nuovo token emesso")
    return {"token": token}


@app.get("/auth/check")
async def auth_check(request: Request):
    token = request.headers.get("X-Auth-Token") or request.query_params.get("token")
    return {"valido": auth.token_valido(token)}


@app.post("/ingest")
async def ingest(msg: dict, request: Request):
    _richiedi_auth(request)
    """Ingresso HTTP per lo userscript Tampermonkey.

    La pagina d'asta e' in HTTPS: aprire una WebSocket verso ws://localhost
    viene bloccato dal browser come contenuto misto (e il costruttore lancia
    un'eccezione sincrona che ammazza lo script). GM_xmlhttpRequest gira nel
    contesto privilegiato dell'estensione e non ha questo problema, quindi
    lo userscript manda qui i dati via POST. Il canale verso il telefono
    resta WebSocket, che funziona perche' il telefono si collega in http://.
    """
    await handle_message(msg)
    await broadcast_to_phones()
    return {"ok": True, "in_modello": (state.current_player or {}).get("in_modello")}


@app.get("/")
async def index():
    # la pagina si serve sempre: e' lei a chiedere la password e a tenere il
    # token; i dati veri passano solo da endpoint autenticati
    return FileResponse(str(HERE / "static" / "phone.html"))


@app.get("/login")
async def login_page():
    return FileResponse(str(HERE / "static" / "login.html"))


@app.get("/storico/cerca")
async def storico_cerca(request: Request, nome: str = "", squadra: str = "",
                         ruolo: str = ""):
    """Ricerca nell'asta precedente per nome parziale, squadra e/o ruolo.
    Alimenta la sezione di ricerca della pagina sul telefono."""
    _richiedi_auth(request)
    risultati = storico.cerca_libera(testo=nome, squadra=squadra, ruolo=ruolo)
    return {"n": len(risultati), "risultati": risultati,
            "squadre": SQUADRE_STORICO}


@app.get("/diag/storico")
async def diag_storico(request: Request, nome: str = "", squadra: str = "", id: int | None = None):
    """Verifica dei prezzi storici:
       http://localhost:8000/diag/storico                      -> stato generale
       http://localhost:8000/diag/storico?nome=Kean&squadra=Fiorentina
    """
    _richiedi_auth(request)
    info = {
        "file_caricati": storico.n_file,
        "nomi_file": [os.path.basename(f) for f in file_aste],
        "acquisti_totali": storico.n_record,
        "anche_nel_pool_2026_27": storico.n_con_id,
        "cartelle_cercate": [str(HERE), str(HERE.parent)],
    }
    if not file_aste:
        info["PROBLEMA"] = ("Nessun file Rose_lega-*.xlsx trovato: tutti i giocatori "
                            "risulteranno 'non acquistato l'anno scorso'. "
                            "Copia il file accanto ad app.py e riavvia il server.")
    if nome or id is not None:
        info["ricerca"] = {"nome": nome, "squadra": squadra, "id": id}
        info["risultato"] = storico.get(player_id=id, nome=nome, squadra=squadra)
    return info


@app.get("/diag")
async def diag(request: Request, nome: str = "", squadra: str = "", id: int | None = None):
    _richiedi_auth(request)
    """Diagnostica rapida del matching, da browser:
       http://localhost:8000/diag?nome=Moise Kean&squadra=Fiorentina
       http://localhost:8000/diag?id=2097
    Utile per capire se un giocatore non viene trovato per un problema di
    nome o perche' non e' proprio nel pool."""
    rec = db.lookup_by_id(id) if id is not None else None
    metodo = "id" if rec else None
    if rec is None and nome:
        rec = db.lookup(nome, squadra)
        metodo = "nome" if rec else None
    return {
        "richiesta": {"nome": nome, "squadra": squadra, "id": id},
        "trovato": rec is not None,
        "metodo": metodo,
        "record": rec,
        "giocatori_nel_pool": len(db.by_id),
    }


async def handle_message(msg: dict):
    """Logica comune ai due canali di ingresso (WebSocket e POST /ingest)."""
    mtype = msg.get("type")
    if mtype == "player_on_auction":
        cp = state.set_current_player(
            nome=msg.get("nome", ""), squadra=msg.get("squadra", ""),
            ruolo=msg.get("ruolo", ""), fvm_live=msg.get("fvm_live"),
            player_id=msg.get("player_id"), nome_lista=msg.get("nome_lista"),
        )
        if cp["in_modello"]:
            log.info(f"Giocatore in asta: {msg.get('nome')} -> {cp['nome']} "
                      f"(match via {cp['metodo_match']}, prezzo atteso "
                      f"{cp.get('prezzo_atteso_live')})")
        else:
            log.warning(f"NON TROVATO nel modello: nome='{msg.get('nome')}' "
                         f"nome_lista='{msg.get('nome_lista')}' "
                         f"squadra='{msg.get('squadra')}' id={msg.get('player_id')}")

    elif mtype == "teams_snapshot":
        eventi = state.apply_teams_snapshot(msg.get("teams", []))
        for ev in eventi:
            if ev.get("tipo") == "rimozione":
                # succede quando un'assegnazione viene annullata: il
                # giocatore torna disponibile e i suoi crediti escono dalla
                # ripartizione della squadra
                log.info(f"Rimosso: {ev['nome']} da {ev['squadra_fantacalcio']}")
            else:
                log.info(f"Assegnato: {ev.get('nome')} -> "
                          f"{ev.get('squadra_fantacalcio')} per {ev.get('costo')} "
                          f"(in_modello={ev.get('in_modello')})")
    else:
        log.warning(f"Tipo messaggio sconosciuto: {mtype}")


@app.websocket("/ws/phone")
async def ws_phone(ws: WebSocket):
    token = ws.query_params.get("token")
    if not auth.token_valido(token):
        await ws.close(code=4401)
        log.warning("Connessione telefono rifiutata: token non valido")
        return
    await ws.accept()
    phone_clients.add(ws)
    log.info(f"Telefono connesso ({len(phone_clients)} totali)")
    try:
        await ws.send_text(json.dumps(state.full_state(), default=str))
        while True:
            await ws.receive_text()  # non ci aspettiamo messaggi dal telefono, solo keep-alive
    except WebSocketDisconnect:
        phone_clients.discard(ws)
        log.info(f"Telefono disconnesso ({len(phone_clients)} rimasti)")


@app.websocket("/ws/extension")
async def ws_extension(ws: WebSocket):
    """Canale per lo scraper da console (`extension/scraper.js`).

    Autenticazione: o `?token=...` gia' valido nella query string, oppure il
    PRIMO messaggio deve essere {"type":"auth","password":"..."}. La seconda
    via evita allo script in pagina di dover fare una chiamata HTTP separata
    per il login.
    Lo userscript Tampermonkey non passa di qui: usa POST /ingest.
    """
    await ws.accept()
    autenticato = auth.token_valido(ws.query_params.get("token"))
    if autenticato:
        log.info("Estensione browser connessa (token in query)")

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                log.warning(f"Messaggio non-JSON ignorato: {raw[:200]}")
                continue

            if not autenticato:
                if msg.get("type") == "auth" and auth.verifica_password(msg.get("password", "")):
                    autenticato = True
                    log.info("Estensione browser autenticata")
                    await ws.send_text(json.dumps({"type": "auth_ok"}))
                else:
                    log.warning("Estensione: password errata o messaggio prima dell'auth")
                    await ws.send_text(json.dumps({"type": "auth_error"}))
                    await ws.close(code=4401)
                    return
                continue

            await handle_message(msg)
            await broadcast_to_phones()
    except WebSocketDisconnect:
        log.info("Estensione browser disconnessa")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
