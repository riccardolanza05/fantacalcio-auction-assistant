#!/usr/bin/env python3
"""
VERDETTO DI VALUTAZIONE
=======================

Risponde a: questo giocatore e' sopravvalutato, sottovalutato o corretto?

Il metodo evita due trappole:

  1. Confrontare crediti tra ruoli diversi non ha senso. Un attaccante da
     100 crediti e uno da 100 in porta non sono paragonabili. Il confronto
     si fa quindi SEMPRE dentro il ruolo.

  2. Un verdetto basato solo sulla stima puntuale ignora l'incertezza.
     Il modello ha un intervallo conformo calibrato (copertura verificata
     0.816 su dato mai visto): il verdetto e' ROBUSTO solo se regge anche
     usando l'estremo sfavorevole dell'intervallo.

Metrica: RENDIMENTO PER CREDITO, cioe' produzione attesa diviso prezzo,
normalizzato sulla mediana del proprio ruolo tra i giocatori che verranno
effettivamente acquistati.

    indice = (produzione / prezzo) / (mediana del ruolo)

    indice > 1  -> rende piu' della media del suo ruolo a parita' di spesa
    indice < 1  -> rende meno

Il verdetto e' "robusto" quando anche calcolando con p10 (scenario
sfavorevole) l'indice resta sopra 1, oppure quando anche con p90
(scenario favorevole) resta sotto 1.

USO:
    python verdetto.py
"""

import argparse

import numpy as np
import pandas as pd

# Percorsi di default: file nella cartella corrente. Sovrascrivibili da riga
# di comando, vedi `python verdetto.py --help`.
IN_CSV = "prezzi_2026_27.csv"
OUT_CSV = "verdetto_2026_27.csv"
SLOT = {"P": 36, "D": 96, "C": 96, "A": 72}

SOGLIA_ALTA = 1.15    # oltre: conviene
SOGLIA_BASSA = 0.85   # sotto: non conviene

# Backtest su 6 stagioni (2019-20..2024-25, ciascuna con solo il proprio
# passato). Testate le soglie 10/15/20/25/30%: la separazione tra
# sottovalutati e sopravvalutati cresce in modo pressoche' lineare con la
# soglia (da 2.40x a 3.06x), quindi non esiste un taglio "naturale" -
# e' un compromesso tra separazione e copertura. Si sceglie 10% perche':
#   - e' la soglia con minore variabilita' del segnale tra le stagioni
#     (dev.std del rapporto 0.52, contro 0.60 a 15% fino a 0.75 a 30%);
#   - copre l'83% dei giocatori contro il 51-73% delle soglie piu' alte,
#     lasciando "in linea" (cioe' senza verdetto) il minor numero possibile
#     di casi.
# A questa soglia, nel backtest: sottovalutati 1.86x, sopravvalutati 0.77x
# la produzione poi realmente realizzata, in tutte le 6 stagioni testate.
SOGLIA_SCARTO_PCT = 10.0


def main(in_csv=IN_CSV, out_csv=OUT_CSV):
    df = pd.read_csv(in_csv)
    df["prezzo"] = df["prezzo"].clip(lower=1)

    # mediana di riferimento: solo i giocatori che verranno comprati
    rif = {}
    for R, n in SLOT.items():
        g = df[df["Ruolo"] == R].nlargest(n, "prezzo")
        rif[R] = (g["produzione_attesa"] / g["prezzo"]).median()
    df["rif_ruolo"] = df["Ruolo"].map(rif)

    df["indice"] = (df["produzione_attesa"] / df["prezzo"]) / df["rif_ruolo"]
    df["indice_p10"] = (df["p10"] / df["prezzo"]) / df["rif_ruolo"]
    df["indice_p90"] = (df["p90"] / df["prezzo"]) / df["rif_ruolo"]

    # prezzo al quale il giocatore renderebbe esattamente come la mediana
    df["prezzo_indifferenza"] = (df["produzione_attesa"] / df["rif_ruolo"]).round(0)
    df["margine"] = (df["prezzo_indifferenza"] - df["prezzo"]).round(0)

    def verdetto(r):
        if r["indice"] >= SOGLIA_ALTA:
            return "sottovalutato robusto" if r["indice_p10"] >= 1.0 else "sottovalutato"
        if r["indice"] <= SOGLIA_BASSA:
            return "sopravvalutato robusto" if r["indice_p90"] <= 1.0 else "sopravvalutato"
        return "valutato correttamente"

    df["verdetto"] = df.apply(verdetto, axis=1)

    print("=== DISTRIBUZIONE DEI VERDETTI (sui giocatori acquistabili) ===")
    acq = pd.concat([df[df["Ruolo"] == R].nlargest(n, "prezzo")
                     for R, n in SLOT.items()])
    t = pd.crosstab(acq["verdetto"], acq["Ruolo"])
    print(t.to_string())

    print("\n=== rendimento per credito di riferimento (mediana per ruolo) ===")
    for R in "PDCA":
        print(f"  {R}: {rif[R]:.2f} fantapunti per credito")

    print("\n=== I MIGLIORI AFFARI (sottovalutati robusti, prezzo >= 5) ===")
    best = acq[(acq["verdetto"] == "sottovalutato robusto") & (acq["prezzo"] >= 5)]
    print(best.nlargest(12, "margine")[
        ["Nome", "Squadra", "Ruolo", "fascia", "prezzo",
         "prezzo_indifferenza", "margine", "produzione_attesa", "indice"]
    ].round(2).to_string(index=False))

    print("\n=== DA EVITARE (sopravvalutati robusti) ===")
    worst = acq[acq["verdetto"] == "sopravvalutato robusto"]
    print(worst.nsmallest(12, "margine")[
        ["Nome", "Squadra", "Ruolo", "fascia", "prezzo",
         "prezzo_indifferenza", "margine", "produzione_attesa", "indice"]
    ].round(2).to_string(index=False))

    cols = ["Id", "Nome", "Squadra", "Ruolo", "fascia", "FVM", "prezzo",
            "produzione_attesa", "p10", "p90", "prezzo_indifferenza",
            "margine", "indice", "indice_p10", "indice_p90", "verdetto"]
    df[cols].sort_values(["Ruolo", "prezzo"], ascending=[True, False]) \
            .round(2).to_csv(out_csv, index=False)
    print(f"\n-> {out_csv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Verdetto di valutazione sui prezzi calcolati.")
    ap.add_argument("--in-csv", default=IN_CSV,
                     help=f"prezzi calcolati da modello_prezzo.py (default: {IN_CSV})")
    ap.add_argument("--out-csv", default=OUT_CSV,
                     help=f"verdetti, in uscita (default: {OUT_CSV})")
    args = ap.parse_args()
    main(in_csv=args.in_csv, out_csv=args.out_csv)
