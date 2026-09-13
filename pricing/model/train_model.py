#!/usr/bin/env python3
"""
Modello di produzione attesa — training + predizione per la stagione corrente.

Recuperato dalla trascrizione della sessione originale in cui e' stato
sviluppato (vedi docs/data-sources.md, "Come e' stato recuperato") e
validato: rieseguito sui dati reali riproduce lo stesso ordine di
grandezza dei risultati registrati in quella sessione (R^2 medio in
validazione temporale ~0.45-0.47, correzione conformal ~14 fantapunti).

Pipeline:
  1. Costruisce un pannello (giocatore, stagione) con feature laggate di
     un anno (_L1) e due anni (_L2) da `voti_aggregato_v3.csv` (prodotto da
     ../votes/aggrega_voti_v3.py) piu' Qt.I/FVM dalle Quotazioni storiche.
  2. Addestra un HistGradientBoostingRegressor sul target = fantapunti di
     stagione (fm_media * presenze).
  3. Addestra due modelli quantilici (10/90 percentile) e li calibra con
     CONFORMALIZED QUANTILE REGRESSION: la correzione (`Q`) e' la quantita'
     di cui allargare l'intervallo, stimata su una stagione di calibrazione
     mai vista in training, per ottenere una copertura empirica dell'80%
     invece di quella (piu' stretta) che il modello darebbe da solo.
  4. Applica la stessa predizione alla stagione corrente, con la
     titolarita' mappata sui quantili storici della metrica `tit_cont`
     (percentuale dalle probabili formazioni -> quantile corrispondente
     nella distribuzione storica dei titolari).

USO:
    python train_model.py \
        --voti-aggregato voti_aggregato_v3.csv \
        --statistiche-corrente Statistiche_Fantacalcio_Stagione_2026_27.xlsx \
        --quotazioni-corrente Quotazioni_Fantacalcio_Stagione_2026_27.xlsx \
        --quotazioni-storiche-glob "Quotazioni_Fantacalcio_Stagione_*.xlsx" \
        --out predizioni_2026_27_v2.csv
        [--probabili-json titolarita.json]   # opzionale, vedi sotto

Il file --probabili-json (opzionale) e' un JSON `{"pct": {"<Id>": <0-100>}}`
con la percentuale di probabile titolarita' per ciascun giocatore, per la
prossima giornata. Non e' incluso in questo repo (e' specifico della
settimana in cui viene generato): senza, la titolarita' futura e'
trattata come sconosciuta (pct=0 per tutti), che degrada solo quella
feature. Per costruirlo dalla pagina probabili-formazioni-serie-a, vedi
docs/data-sources.md — la struttura HTML del sito cambia nel tempo, quindi
il parser va ricalibrato quando serve (stesso principio dello scraper
dell'asta live in browser/).
"""
import argparse
import glob
import json
import re

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

FCOLS = ["presenze", "tasso_presenza", "quota_spezzoni", "gap_max", "partite_disponibili",
         "voto_medio_puro", "sd_voto", "fm_media", "sd_fm", "porte_inviolate",
         "tasso_porta_inviolata", "gol_tot", "Ass", "Amm", "rigori_calciati",
         "rigorista", "titolare_g1", "presenze_g1_3", "trasferito_in_corso",
         "n_squadre", "prod"]
ALPHA = 0.20  # intervallo all'80%


def _carica_quotazioni_storiche(pattern, stagione_corrente, sidx):
    qs = []
    for f in sorted(glob.glob(pattern)):
        m = re.search(r"(\d{4})_(\d{2})", f)
        if not m:
            continue
        s = f"{m.group(1)}-{m.group(2)}"
        if s == stagione_corrente:
            continue
        for sh in ("Tutti", "Ceduti"):
            try:
                df = pd.read_excel(f, sheet_name=sh, header=1)
                df["stagione"] = s
                qs.append(df[["Id", "stagione", "R", "Qt.I", "FVM"]])
            except ValueError:
                pass  # foglio assente in alcune stagioni: normale
    q = pd.concat(qs, ignore_index=True).drop_duplicates(["Id", "stagione"])
    q["si"] = q["stagione"].map(sidx)
    return q


def main(voti_aggregato_csv, quotazioni_corrente_xlsx, quotazioni_storiche_glob,
         out_csv, probabili_json=None, stagione_corrente="2026-27"):
    v = pd.read_csv(voti_aggregato_csv)
    v = v[v["Ruolo"].isin(["P", "D", "C", "A"])].copy()
    v["prod"] = v["fm_media"] * v["presenze"]
    seasons = sorted(set(v["stagione"]) | {stagione_corrente})
    sidx = {s: i for i, s in enumerate(seasons)}
    v["si"] = v["stagione"].map(sidx)
    si_corrente = sidx[stagione_corrente]
    v["tit_cont"] = v["presenze_g1_3"] / 3.0

    if probabili_json:
        with open(probabili_json) as f:
            pct_by_id = {int(k): p for k, p in json.load(f)["pct"].items()}
    else:
        print("[!] --probabili-json non fornito: titolarita' futura sconosciuta (pct=0 per tutti)")
        pct_by_id = {}

    q26 = pd.read_excel(quotazioni_corrente_xlsx, sheet_name="Tutti", header=1)
    print(f"quotazioni {stagione_corrente}: {len(q26)} giocatori")

    q = _carica_quotazioni_storiche(quotazioni_storiche_glob, stagione_corrente, sidx)
    q26b = q26[["Id", "R", "Qt.I", "FVM"]].copy()
    q26b["stagione"] = stagione_corrente
    q26b["si"] = si_corrente
    q = pd.concat([q, q26b], ignore_index=True).drop_duplicates(["Id", "si"])

    def lag(k):
        d = v[["Id", "si"] + FCOLS].copy()
        d["si"] = d["si"] + k
        d.columns = ["Id", "si"] + [f"{c}_L{k}" for c in FCOLS]
        return d

    tgt = v[["Id", "si", "prod", "Ruolo"]].rename(columns={"prod": "y"})
    m = tgt.merge(lag(1), on=["Id", "si"], how="left").merge(lag(2), on=["Id", "si"], how="left")
    m = m.merge(q[["Id", "si", "Qt.I", "FVM"]], on=["Id", "si"], how="left")
    m["R_code"] = m["Ruolo"].map({"P": 0, "D": 1, "C": 2, "A": 3})
    m = m.merge(v[["Id", "si", "tit_cont"]].rename(columns={"tit_cont": "tit_cont_now"}),
                on=["Id", "si"], how="left")
    d = m[m["presenze_L1"].notna() & m["y"].notna()].copy()
    feat = [c for c in d.columns if c.endswith(("_L1", "_L2"))] + ["Qt.I", "FVM", "R_code", "tit_cont_now"]

    X = q26[["Id", "Nome", "Squadra", "R", "Qt.I", "FVM"]].copy()
    X["si"] = si_corrente
    X = X.merge(lag(1), on=["Id", "si"], how="left").merge(lag(2), on=["Id", "si"], how="left")
    X["R_code"] = X["R"].map({"P": 0, "D": 1, "C": 2, "A": 3})
    X["pct"] = X["Id"].map(pct_by_id).fillna(0)
    storico = d["tit_cont_now"].dropna().values
    X["tit_cont_now"] = np.quantile(storico, np.clip(X["pct"].rank(pct=True), 0, 1))

    mod = HistGradientBoostingRegressor(max_iter=500, learning_rate=0.05, max_depth=6,
          min_samples_leaf=20, l2_regularization=1.0, random_state=0).fit(d[feat], d["y"])
    X["produzione_attesa"] = np.clip(mod.predict(X[feat]), 0, None)

    tr, cal = d[d["si"] < si_corrente - 1], d[d["si"] == si_corrente - 1]

    def qm(qq):
        return HistGradientBoostingRegressor(loss="quantile", quantile=qq, max_iter=400,
               learning_rate=0.06, max_depth=6, min_samples_leaf=20,
               l2_regularization=1.0, random_state=0).fit(tr[feat], tr["y"])

    lo, hi = qm(ALPHA / 2), qm(1 - ALPHA / 2)
    E = np.maximum(lo.predict(cal[feat]) - cal["y"].values, cal["y"].values - hi.predict(cal[feat]))
    n = len(E)
    Q = np.sort(E)[min(int(np.ceil((n + 1) * (1 - ALPHA))), n) - 1]
    X["p10"] = np.minimum(np.clip(lo.predict(X[feat]) - Q, 0, None), X["produzione_attesa"])
    X["p90"] = np.maximum(hi.predict(X[feat]) + Q, X["produzione_attesa"])
    print(f"correzione conformal: {Q:.1f} fantapunti")

    out = X[["Id", "Nome", "Squadra", "R", "Qt.I", "FVM", "pct",
              "produzione_attesa", "p10", "p90", "presenze_L1", "fm_media_L1"]].rename(columns={
        "R": "Ruolo", "Qt.I": "QtI", "pct": "pct_titolarita",
        "presenze_L1": "presenze_2025_26", "fm_media_L1": "fm_media_2025_26",
    }).round(1)
    out = out.sort_values(["Ruolo", "produzione_attesa"], ascending=[True, False])
    out.to_csv(out_csv, index=False)
    print(f"predizioni scritte: {len(out)}")
    print(f"-> {out_csv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voti-aggregato", required=True, help="output di ../votes/aggrega_voti_v3.py")
    ap.add_argument("--quotazioni-corrente", required=True, help="Quotazioni_Fantacalcio_Stagione_<corrente>.xlsx")
    ap.add_argument("--quotazioni-storiche-glob", required=True,
                     help='pattern glob per le Quotazioni delle stagioni passate, es. "Quotazioni_Fantacalcio_Stagione_*.xlsx"')
    ap.add_argument("--out", default="predizioni.csv", help="CSV d'uscita, input di modello_prezzo.py")
    ap.add_argument("--probabili-json", default=None,
                     help='JSON {"pct": {"<Id>": <0-100>}} con la titolarita\' attesa (opzionale, vedi docstring)')
    ap.add_argument("--stagione-corrente", default="2026-27")
    args = ap.parse_args()
    main(args.voti_aggregato, args.quotazioni_corrente, args.quotazioni_storiche_glob,
         args.out, args.probabili_json, args.stagione_corrente)
