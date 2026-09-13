#!/usr/bin/env python3
"""
Costruisce `Hreg.pkl`: lo shrinkage gerarchico per la regressione alla media
(strato 3b di modello_prezzo.py).

Per ogni giocatore stima, dalla sua storia fino alla stagione precedente:
  fm_storica    media pesata (decadimento esponenziale + presenze) delle
                fantamedie di carriera
  fm_shrunk     fm_storica ridotta verso la media di ruolo, pesata sulle
                presenze in carriera (shrinkage empirico-bayesiano: chi ha
                pochi dati si ancora di piu' alla media del ruolo)
  correzione_fm quanto la fantamedia dell'ultima stagione (fm_L1) si
                discosta da fm_shrunk una volta applicato il coefficiente
                di persistenza per ruolo (vedi COEF sotto) — è negativa per
                chi ha sovraperformato il proprio livello storico.

I coefficienti di persistenza per ruolo (P: -0.08, D: 0.705, C: 0.904,
A: 0.810) sono stati stimati sullo storico 2015-16..2025-26 (n=2950
giocatori con almeno 10 presenze): quanta parte di uno scostamento di +1.0
dal livello storico resta l'anno successivo. Il portiere e' il caso
estremo: un'annata sopra il proprio livello non si ripete affatto.

Recuperato dalla trascrizione della sessione originale (vedi
docs/data-sources.md, "Come e' stato recuperato"), e validato: rieseguito
sui dati reali produce esattamente gli stessi numeri registrati in
quella sessione (2274 giocatori con storico, media/min/max di
correzione_fm per ruolo identici).

USO:
    python build_hreg.py --voti-aggregato voti_aggregato_v3.csv --out Hreg.pkl
"""
import argparse

import numpy as np
import pandas as pd

DECAY = 0.65   # decadimento annuo del peso delle stagioni piu' vecchie
K = 25         # forza dello shrinkage verso la media di ruolo (in "presenze equivalenti")
COEF = {"P": -0.08, "D": 0.705, "C": 0.904, "A": 0.810}


def main(voti_aggregato_csv, out_pkl):
    v = pd.read_csv(voti_aggregato_csv)
    v = v[v["Ruolo"].isin(["P", "D", "C", "A"])].copy()
    seasons = sorted(set(v["stagione"]) | {"2026-27"})
    sidx = {s: i for i, s in enumerate(seasons)}
    v["si"] = v["stagione"].map(sidx)
    si_corrente = sidx["2026-27"]
    mu = v.groupby(["si", "Ruolo"])["fm_media"].mean().rename("mu_ruolo").reset_index()

    out = []
    for idg, g in v.sort_values("si").groupby("Id"):
        past = g[g["si"] < si_corrente]
        if len(past) == 0:
            continue
        eta = si_corrente - past["si"].values
        w = DECAY ** (eta - 1) * past["presenze"].values
        if w.sum() == 0:
            w = np.ones(len(past))
        out.append({
            "Id": idg, "n_stagioni": len(past),
            "presenze_carriera": past["presenze"].sum(),
            "fm_storica": np.average(past["fm_media"].values, weights=w),
            "fm_L1": (past[past["si"] == si_corrente - 1]["fm_media"].values[0]
                      if (past["si"] == si_corrente - 1).any() else np.nan),
            "Ruolo": past["Ruolo"].iloc[-1],
        })
    H = pd.DataFrame(out)
    H = H.merge(mu[mu["si"] == si_corrente - 1][["Ruolo", "mu_ruolo"]], on="Ruolo", how="left")
    n = H["presenze_carriera"]
    H["fm_shrunk"] = (n * H["fm_storica"] + K * H["mu_ruolo"]) / (n + K)
    H["over_fm"] = H["fm_L1"] - H["fm_shrunk"]
    H["coef"] = H["Ruolo"].map(COEF)
    H["fm_corretta"] = H["fm_shrunk"] + H["coef"] * H["over_fm"].fillna(0)
    H["correzione_fm"] = H["fm_corretta"] - H["fm_L1"]
    H.to_pickle(out_pkl)

    print(f"giocatori con storico: {len(H)}")
    print(H.groupby("Ruolo")["correzione_fm"].agg(media="mean", min="min", max="max").round(3).to_string())
    print(f"\n-> {out_pkl}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voti-aggregato", default="voti_aggregato_v3.csv",
                     help="output di ../votes/aggrega_voti_v3.py (default: %(default)s)")
    ap.add_argument("--out", default="Hreg.pkl",
                     help="file d'uscita, usato da pricing/modello_prezzo.py (default: %(default)s)")
    args = ap.parse_args()
    main(args.voti_aggregato, args.out)
