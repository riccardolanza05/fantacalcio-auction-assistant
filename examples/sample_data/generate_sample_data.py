#!/usr/bin/env python3
"""
Genera dati SINTETICI (giocatori inventati, nessun dato fantacalcio.it) per
provare la pipeline e far partire il server senza possedere i file ufficiali
della lega. Vedi docs/data-sources.md per i dati veri.

Uso (dalla cartella examples/sample_data/):
    python generate_sample_data.py

Produce in questa stessa cartella:
    predizioni_esempio.csv   input della pipeline di pricing (pricing/)
    giocatori_esempio.xlsx   database pronto per il server (server/)

Per provare il server con questi dati:
    cp giocatori_esempio.xlsx ../../server/giocatori_2026_27.xlsx
"""
import os
import sys
import random

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PRICING_DIR = os.path.join(HERE, "..", "..", "pricing")
sys.path.insert(0, PRICING_DIR)

import modello_prezzo  # noqa: E402
import verdetto  # noqa: E402

random.seed(42)
np.random.seed(42)

SQUADRE = ["Inter", "Milan", "Napoli", "Juventus", "Roma", "Fiorentina",
           "Atalanta", "Bologna", "Torino", "Genoa"]
N_PER_RUOLO = {"P": 12, "D": 24, "C": 24, "A": 20}

righe = []
pid = 1000
for ruolo, n in N_PER_RUOLO.items():
    # FVM generati come una coda esponenziale, poi ordinati in modo
    # decrescente: cosi' il migliore del ruolo e' sempre il piu' caro,
    # come nella distribuzione reale delle quotazioni.
    fvm_base = {"P": 15, "D": 15, "C": 20, "A": 30}[ruolo]
    fvm_ruolo = sorted((int(v) + 1 for v in np.random.exponential(fvm_base, n)),
                        reverse=True)
    for i in range(n):
        fvm = max(1, fvm_ruolo[i])
        qti = max(1, int(fvm * random.uniform(0.7, 1.0)))
        pct_tit = round(random.uniform(40, 95), 0)
        produzione = round(fvm * random.uniform(0.6, 1.3) + random.gauss(0, 5), 1)
        spread = round(abs(produzione) * 0.18 + 8, 1)
        righe.append({
            "Id": pid,
            "Nome": f"Giocatore{ruolo}{i+1:02d}",
            "Squadra": SQUADRE[(pid + i) % len(SQUADRE)],
            "Ruolo": ruolo,
            "QtI": qti,
            "FVM": fvm,
            "pct_titolarita": pct_tit,
            "tit_cont": round(pct_tit / 100, 1),
            "giornate_perse_stimate": round(random.uniform(0, 3), 1) if random.random() < 0.15 else 0.0,
            "produzione_attesa": max(0.0, produzione),
            "p10": max(0.0, produzione - spread),
            "p90": produzione + spread,
            "presenze_2025_26": random.randint(0, 38),
            "fm_media_2025_26": round(random.uniform(5.5, 7.5), 1),
            "gap_percentile": round(random.uniform(-0.2, 0.2), 2),
        })
        pid += 1

predizioni = pd.DataFrame(righe)
pred_path = os.path.join(HERE, "predizioni_esempio.csv")
predizioni.to_csv(pred_path, index=False)
print(f"Scritto {pred_path}: {len(predizioni)} giocatori sintetici")

# Esegue la STESSA pipeline usata sui dati veri: strati 1-3 (modello_prezzo)
# poi il verdetto, cosi' il file di esempio e' generato con la logica reale
# e non con numeri a caso.
prezzi_path = os.path.join(HERE, "prezzi_esempio.csv")
verdetto_path = os.path.join(HERE, "verdetto_esempio.csv")
modello_prezzo.main(in_csv=pred_path, out_csv=prezzi_path,
                     hreg_pkl=os.path.join(HERE, "Hreg_inesistente.pkl"))
verdetto.main(in_csv=prezzi_path, out_csv=verdetto_path)

prezzi = pd.read_csv(prezzi_path)
verd = pd.read_csv(verdetto_path)[["Id", "verdetto"]]
df = prezzi.merge(verd, on="Id", how="left")

# Schema minimo richiesto da server/player_db.py, con qualche colonna di
# demo per gol/assist/presenze/infortuni (anch'esse inventate).
out = pd.DataFrame({
    "Id": df["Id"],
    "Nome": df["Nome"],
    "Squadra": df["Squadra"],
    "Ruolo": df["Ruolo"],
    "fascia": df["fascia"],
    "pct_titolarita": df["pct_titolarita"],
    "FVM": df["FVM"],
    "QtI": df["QtI"],
    "produzione_attesa": df["produzione_attesa"],
    "p10": df["p10"],
    "p90": df["p90"],
    "prezzo_base": df["base"],
    "correzione": df["correzione"],
    "prezzo_modello": df["prezzo"],
    "prezzo_mercato": df["FVM"],
    "scarto_pct": (100 * (df["prezzo"] - df["FVM"]) / df["FVM"]).round(1),
    "verdetto": df["verdetto"],
    "rif_verdetto": "modello",
    "gol_2025_26": np.where(df["Ruolo"] == "A", np.random.randint(0, 20, len(df)), 0),
    "gol_subiti_2025_26": np.where(df["Ruolo"] == "P", np.random.randint(10, 50, len(df)), None),
    "clean_sheet_2025_26": np.where(df["Ruolo"] == "P", np.random.randint(0, 15, len(df)), None),
    "rigori_parati_2025_26": np.where(df["Ruolo"] == "P", np.random.randint(0, 3, len(df)), None),
    "assist_2025_26": np.random.randint(0, 10, len(df)),
    "presenze_2025_26": np.random.randint(0, 38, len(df)),
    "fm_media_2025_26": np.round(np.random.uniform(5.5, 7.5, len(df)), 1),
    "nota_infortunio": None,
    "infortunato": False,
})

xlsx_path = os.path.join(HERE, "giocatori_esempio.xlsx")
out.to_excel(xlsx_path, sheet_name="giocatori_esempio", index=False)
print(f"Scritto {xlsx_path}: {len(out)} giocatori sintetici")
