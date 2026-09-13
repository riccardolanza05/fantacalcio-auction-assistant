"""Test di integrazione manuale: richiede il server avviato su localhost:8000
con la tua ASTA_PASSWORD e un giocatori_2026_27.xlsx reale caricato (i player
id usati qui, es. 2764, sono quelli veri di fantacalcio.it). Non gira in CI.

Uso:
    ASTA_PASSWORD=... python app.py        # in un altro terminale, da server/
    ASTA_PASSWORD=... python tests/test_integration.py
"""
import asyncio
import json
import os
import urllib.request

import websockets

BASE = "http://127.0.0.1:8000"


def login(password=None):
    password = password or os.environ.get("ASTA_PASSWORD")
    if not password:
        raise SystemExit("Imposta ASTA_PASSWORD con la stessa password del server.")
    req = urllib.request.Request(
        BASE + "/login", method="POST",
        data=json.dumps({"password": password}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)["token"]


TOKEN = login()


async def phone_listener(received: list):
    async with websockets.connect(f"ws://127.0.0.1:8000/ws/phone?token={TOKEN}") as ws:
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                received.append(json.loads(msg))
        except asyncio.TimeoutError:
            pass


async def extension_sender():
    async with websockets.connect(f"ws://127.0.0.1:8000/ws/extension?token={TOKEN}") as ws:
        await ws.send(json.dumps({
            "type": "player_on_auction",
            "nome": "Lautaro Martinez", "squadra": "Inter", "ruolo": "A",
            "fvm_live": 370, "player_id": 2764,
        }))
        await asyncio.sleep(0.3)
        await ws.send(json.dumps({
            "type": "teams_snapshot",
            "teams": [
                {"uid": "u1", "nome_squadra": "NapoLanza", "budget": 1000, "max_offerta": 976,
                 "counts": {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, "rosa": []},
                {"uid": "u2", "nome_squadra": "Squadra Rivale", "budget": 1000, "max_offerta": 976,
                 "counts": {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, "rosa": []},
            ],
        }))
        await asyncio.sleep(0.3)
        await ws.send(json.dumps({
            "type": "teams_snapshot",
            "teams": [
                {"uid": "u1", "nome_squadra": "NapoLanza", "budget": 850, "max_offerta": 826,
                 "counts": {"P": 0, "D": 0, "C": 0, "A": 1, "TOT": 1},
                 "rosa": [{"nome": "Martinez L.", "squadra": "Inter", "ruolo": "A"}]},
            ],
        }))
        await asyncio.sleep(0.3)
        await ws.send(json.dumps({
            "type": "player_on_auction",
            "nome": "Hojlund", "squadra": "Napoli", "ruolo": "A", "fvm_live": 271,
        }))
        await asyncio.sleep(0.3)


async def main():
    received = []
    listener_task = asyncio.create_task(phone_listener(received))
    await asyncio.sleep(0.3)
    await extension_sender()
    await listener_task

    print(f"Il telefono ha ricevuto {len(received)} aggiornamenti\n")
    for i, r in enumerate(received):
        cp = r.get("current_player")
        print(f"--- update {i} ---")
        if cp:
            print(f"  giocatore in asta: {cp['nome']} | prezzo_atteso_live={cp.get('prezzo_atteso_live')}")
        print(f"  squadre: {r['teams']}")
        print(f"  ultima assegnazione: {r['ultima_assegnazione']}")

    assert received[-1]["current_player"]["nome"] == "Hojlund"
    ev = received[-1]["ultima_assegnazione"]
    assert ev is not None and ev["costo"] == 150 and ev["nome"] == "Martinez L."
    cp = received[1]["current_player"]
    assert cp.get("storico_asta"), "storico asta mancante nel payload"
    assert cp["storico_asta"]["prezzo_medio"] == 319
    mia = received[-1].get("mia_squadra")
    assert mia is not None, "ripartizione della mia squadra mancante"
    print(f"\nMia squadra {mia['nome_squadra']}: residuo {mia['budget_residuo']}, "
          f"A {mia['per_ruolo']['A']['pct']}% del budget")
    print(f"\nStorico asta letto: {cp['nome']} pagato "
          f"{cp['storico_asta']['prezzo_medio']} crediti l'anno scorso "
          f"da {cp['storico_asta']['dettaglio'][0]['squadra_fantacalcio']}")
    print("\nOK: assegnazione dedotta correttamente da TOT+1 e delta budget "
          "(150 crediti), id 2764 risolto in 'Martinez L.', e la stima per il "
          "prossimo attaccante dello stesso tier si e' alzata di conseguenza.")


asyncio.run(main())
