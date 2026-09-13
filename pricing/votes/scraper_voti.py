#!/usr/bin/env python3
"""
Scraper voti storici Fantacalcio.it (uso personale).

Scarica i file Excel dei voti giornata-per-giornata per le stagioni indicate,
usando lo stesso endpoint del bottone "Scarica" del sito.

USO:
    1) pip install requests beautifulsoup4
    2) esporta il cookie di sessione (vedi README)
    3) python scraper_voti.py

Caratteristiche:
  - ricava automaticamente l'ID interno di ogni stagione (non lo indovina)
  - riprende da dove si era interrotto (salta i file gia' scaricati)
  - rate limiting + backoff sugli errori: non martella il server
  - salva tutto in ./voti_raw/{stagione}/g{NN}.xlsx
"""

import os
import re
import sys
import time
import random
import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------------
# CONFIGURAZIONE
# ----------------------------------------------------------------------------

BASE = "https://www.fantacalcio.it"
OUTDIR = "voti_raw"

# Stagioni da scaricare (slug come compaiono nell'URL del sito)
STAGIONI = [
    "2015-16", "2016-17", "2017-18", "2018-19", "2019-20", "2020-21",
    "2021-22", "2022-23", "2023-24", "2024-25", "2025-26",
]

GIORNATE = range(1, 39)          # 1..38

# Pausa tra una richiesta e l'altra (secondi). NON abbassare sotto 1.5:
# un delay onesto e' cio' che distingue uno scraper civile da un attacco.
DELAY_MIN = 2.0
DELAY_MAX = 4.0

MAX_RETRY = 3                    # tentativi per singolo file
TIMEOUT = 30

# ----------------------------------------------------------------------------
# AUTENTICAZIONE
# ----------------------------------------------------------------------------
# Il cookie di sessione va preso dal TUO browser (vedi README) e messo
# nella variabile d'ambiente FC_COOKIE, oppure in un file cookie.txt.
#
# NOTA: il cookie e' equivalente a una sessione di login. Trattalo come una
# password: non committarlo su git, non condividerlo.

def leggi_cookie() -> str:
    raw = os.environ.get("FC_COOKIE", "").strip()
    if not raw and os.path.exists("cookie.txt"):
        # utf-8-sig rimuove automaticamente il BOM di PowerShell
        with open("cookie.txt", "r", encoding="utf-8-sig") as f:
            raw = f.read()
    if not raw:
        sys.exit(
            "ERRORE: cookie non trovato.\n"
            "Imposta FC_COOKIE oppure crea cookie.txt. Vedi README_scraper.md."
        )

    # Pulizia difensiva: BOM residui, newline da a capo automatici del terminale,
    # e qualunque carattere non rappresentabile in un header HTTP.
    c = raw.replace("\ufeff", "")
    c = "".join(c.split())          # rimuove \n \r \t e spazi accidentali
    c = c.encode("latin-1", "ignore").decode("latin-1")
    if not c:
        sys.exit("ERRORE: cookie vuoto dopo la pulizia. Rigeneralo.")
    return c


def crea_sessione(cookie: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        # User-Agent reale: identificarsi correttamente e' buona pratica
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0 Safari/537.36"),
        "Accept-Language": "it-IT,it;q=0.9",
        "Cookie": cookie,
    })
    return s


# ----------------------------------------------------------------------------
# SCOPERTA DEGLI ID STAGIONE
# ----------------------------------------------------------------------------
# L'endpoint Excel usa un ID numerico interno (es. 20 = 2025-26), NON lo slug.
# Invece di indovinarlo, lo leggiamo dal link "Scarica" presente nella pagina.

RE_EXCEL = re.compile(r"/api/v1/Excel/votes/(\d+)/(\d+)")


def trova_id_stagione(sess: requests.Session, stagione: str) -> int | None:
    url = f"{BASE}/voti-fantacalcio-serie-a/{stagione}/1"
    try:
        r = sess.get(url, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  [!] impossibile aprire {url}: {e}")
        return None

    # 1) cerca nel link di download
    m = RE_EXCEL.search(r.text)
    if m:
        return int(m.group(1))

    # 2) fallback: cerca negli href della pagina
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        m = RE_EXCEL.search(a["href"])
        if m:
            return int(m.group(1))
    return None


# ----------------------------------------------------------------------------
# DOWNLOAD
# ----------------------------------------------------------------------------

def scarica_giornata(sess, id_stag: int, giornata: int, dest: str) -> str:
    """Ritorna: 'ok' | 'skip' | 'vuoto' | 'auth' | 'errore'"""
    if os.path.exists(dest) and os.path.getsize(dest) > 2000:
        return "skip"

    url = f"{BASE}/api/v1/Excel/votes/{id_stag}/{giornata}"

    for tentativo in range(1, MAX_RETRY + 1):
        try:
            r = sess.get(url, timeout=TIMEOUT)
        except requests.RequestException as e:
            print(f"      rete KO ({e}), retry {tentativo}/{MAX_RETRY}")
            time.sleep(5 * tentativo)
            continue

        if r.status_code in (401, 403):
            return "auth"

        if r.status_code == 429:            # rate limited: rallenta molto
            attesa = 30 * tentativo
            print(f"      429 rate limit, attendo {attesa}s")
            time.sleep(attesa)
            continue

        if r.status_code == 404:
            return "vuoto"

        if r.status_code != 200:
            print(f"      HTTP {r.status_code}, retry {tentativo}/{MAX_RETRY}")
            time.sleep(5 * tentativo)
            continue

        # Verifica che sia davvero un xlsx (PK = header ZIP) e non una
        # pagina di errore HTML travestita da 200.
        if not r.content.startswith(b"PK"):
            return "vuoto"

        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(r.content)
        return "ok"

    return "errore"


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main():
    cookie = leggi_cookie()
    sess = crea_sessione(cookie)

    print("=" * 70)
    print("SCRAPER VOTI FANTACALCIO — uso personale")
    print("=" * 70)

    # Fase 1: mappa stagione -> id interno
    print("\n[1/2] Individuazione ID stagione...")
    mappa = {}
    for st in STAGIONI:
        sid = trova_id_stagione(sess, st)
        if sid is None:
            print(f"  {st}: ID NON TROVATO — stagione saltata")
        else:
            print(f"  {st}: id={sid}")
            mappa[st] = sid
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    if not mappa:
        sys.exit("\nNessuna stagione risolta. Cookie scaduto o struttura del sito cambiata.")

    # Fase 2: download
    totale = len(mappa) * len(GIORNATE)
    print(f"\n[2/2] Download di ~{totale} file "
          f"(stima {totale * (DELAY_MIN + DELAY_MAX) / 2 / 60:.0f} minuti)\n")

    conta = {"ok": 0, "skip": 0, "vuoto": 0, "errore": 0}
    fatti = 0

    for st, sid in mappa.items():
        print(f"--- Stagione {st} (id {sid}) ---")
        for g in GIORNATE:
            dest = os.path.join(OUTDIR, st, f"g{g:02d}.xlsx")
            esito = scarica_giornata(sess, sid, g, dest)
            fatti += 1

            if esito == "auth":
                print("\n[STOP] Il server rifiuta le credenziali (401/403).")
                print("Il cookie e' scaduto: rifallo (vedi README) e rilancia.")
                print("I file gia' scaricati restano: lo script riprende da li'.")
                sys.exit(1)

            conta[esito] = conta.get(esito, 0) + 1
            simbolo = {"ok": ".", "skip": "-", "vuoto": "o", "errore": "X"}[esito]
            print(simbolo, end="", flush=True)
            if g % 38 == 0:
                print(f"   [{fatti}/{totale}]")

            if esito != "skip":
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        print()

    print("\n" + "=" * 70)
    print(f"FATTO — scaricati: {conta['ok']} | gia' presenti: {conta['skip']} | "
          f"vuoti/inesistenti: {conta['vuoto']} | errori: {conta['errore']}")
    print(f"File in ./{OUTDIR}/")
    print("Prossimo passo: python parse_voti.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
