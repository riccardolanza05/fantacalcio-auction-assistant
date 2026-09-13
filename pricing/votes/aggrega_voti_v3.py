#!/usr/bin/env python3
"""
Aggregatore v3 — riassunto per (stagione, giocatore) con le REGOLE DELLA
TUA LEGA, calcolato da voti_panel.csv.

Cosa aggiunge rispetto alla v2:
  - fantamedia calcolata con regole_lega.py (rigori contati, rigore
    sbagliato -2, porta inviolata +1, gol subito solo al portiere)
  - Gs totali e porte_inviolate (mancavano: senza queste il portiere
    era sistematicamente sottovalutato)
  - sd_voto: deviazione standard del voto puro. Serve al modificatore
    difesa, dove la varianza conta piu' della media
  - voto_medio_puro: media del voto SENZA bonus/malus, che e' la
    grandezza su cui si calcola il modificatore
  - titolare_g1 e presenze_g1_3: proxy storico della titolarita' a inizio
    stagione, cosi' le probabili formazioni diventano usabili come feature
  - rigorista: rigori calciati, per identificare i tiratori designati

Richiede regole_lega.py nella stessa cartella.

USO:
    python aggrega_voti_v3.py

Output:
    voti_aggregato_v3.csv
"""

import csv
import math
import os
import sys
from collections import defaultdict

try:
    from regole_lega import punteggio_partita, REGOLE
except ImportError:
    sys.exit("Serve regole_lega.py nella stessa cartella.")

CSV_IN = "voti_panel.csv"
CSV_OUT = "voti_aggregato_v3.csv"
FONTE = "Fantacalcio"
N_GIORNATE = 38
SOGLIA_GIRONE = 19

CAMPI = [
    "stagione", "Id", "Nome", "Ruolo",
    "squadra_prima", "squadra_ultima", "n_squadre", "trasferito_in_corso",
    "prima_g", "ultima_g", "partite_disponibili",
    "presenze", "voti_ufficio", "comparse",
    "tasso_presenza", "quota_spezzoni", "tipo_disponibilita", "gap_max",
    "titolare_g1", "presenze_g1_3",
    "voto_medio_puro", "sd_voto",          # per il modificatore difesa
    "fm_media", "sd_fm", "fantapunti_tot", # con le regole della lega
    "porte_inviolate", "tasso_porta_inviolata",
    "Gs", "gol_tot", "Gf_azione", "Rf", "Rs", "rigori_calciati", "rigorista",
    "Ass", "Amm", "Esp", "Au", "Rp",
]


def dev_std(valori):
    n = len(valori)
    if n < 2:
        return ""
    media = sum(valori) / n
    var = sum((v - media) ** 2 for v in valori) / (n - 1)
    return round(math.sqrt(var), 4)


def gap_massimo(giornate, prima, ultima):
    if not giornate:
        return ultima - prima + 1
    g = sorted(giornate)
    peggiore = g[0] - prima
    for a, b in zip(g, g[1:]):
        peggiore = max(peggiore, b - a - 1)
    return max(peggiore, ultima - g[-1])


def main():
    if not os.path.exists(CSV_IN):
        sys.exit(f"{CSV_IN} assente. Lancia prima parse_voti_v2.py")

    agg = defaultdict(lambda: {
        "nome": "", "ruolo": "", "prima": 99, "ultima": 0,
        "comparse": 0, "ast": 0,
        "voti_puri": [], "fm": [], "g_presenza": set(), "squadre": [],
        "clean": 0, "g13": 0,
        "Gs": 0, "Gf": 0, "Rf": 0, "Rs": 0, "Ass": 0,
        "Amm": 0, "Esp": 0, "Au": 0, "Rp": 0,
    })

    letti = 0
    with open(CSV_IN, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["fonte"] != FONTE:
                continue
            letti += 1

            k = (r["stagione"], int(r["Id"]))
            d = agg[k]
            ruolo = (r["Ruolo"] or "").strip()
            d["nome"] = r["Nome"] or d["nome"]
            d["ruolo"] = ruolo or d["ruolo"]

            g = int(r["giornata"])
            d["prima"] = min(d["prima"], g)
            d["ultima"] = max(d["ultima"], g)
            d["comparse"] += 1
            d["squadre"].append((g, r["Squadra"]))

            def n(c):
                try:
                    return int(r[c] or 0)
                except ValueError:
                    return 0

            gf, rf, rs, rp = n("Gf"), n("Rf"), n("Rs"), n("Rp")
            au, amm, esp, ass_, gs = n("Au"), n("Amm"), n("Esp"), n("Ass"), n("Gs")

            for campo, val in (("Gf", gf), ("Rf", rf), ("Rs", rs), ("Rp", rp),
                               ("Au", au), ("Amm", amm), ("Esp", esp),
                               ("Ass", ass_), ("Gs", gs)):
                d[campo] += val

            asterisco = r["voto_ufficio"] == "1"
            sv = r["senza_voto"] == "1"
            voto = None
            if r["Voto"] not in ("", None):
                try:
                    voto = float(r["Voto"])
                except ValueError:
                    voto = None

            if asterisco:
                d["ast"] += 1
                continue
            if voto is None or sv:
                continue

            # --- presenza valida ---
            d["g_presenza"].add(g)
            d["voti_puri"].append(voto)
            if g <= 3:
                d["g13"] += 1

            fp = punteggio_partita(voto, ruolo, gf=gf, rf=rf, ass=ass_,
                                   rs=rs, rp=rp, au=au, amm=amm, esp=esp, gs=gs)
            d["fm"].append(fp)

            if ruolo in REGOLE["ruoli_porta_inviolata"] and gs == 0:
                d["clean"] += 1

    if not agg:
        sys.exit(f"Nessuna riga con fonte '{FONTE}'")

    print(f"Righe lette ({FONTE}): {letti}")
    print(f"Coppie (stagione, giocatore): {len(agg)}")

    righe = []
    for (stagione, idg), d in sorted(agg.items()):
        prima, ultima = d["prima"], d["ultima"]
        disp = ultima - prima + 1
        pres = len(d["voti_puri"])

        seq = sorted(d["squadre"])
        squadre = {s for _, s in seq if s}

        if prima >= SOGLIA_GIRONE and ultima >= N_GIORNATE - 2:
            tipo = "arrivo_tardivo"
        elif ultima <= SOGLIA_GIRONE and prima <= 3:
            tipo = "uscita_anticipata"
        elif prima <= 3 and ultima >= N_GIORNATE - 2:
            tipo = "intera_stagione"
        else:
            tipo = "parziale"

        rig = d["Rf"] + d["Rs"]

        righe.append({
            "stagione": stagione, "Id": idg,
            "Nome": d["nome"], "Ruolo": d["ruolo"],
            "squadra_prima": seq[0][1] if seq else "",
            "squadra_ultima": seq[-1][1] if seq else "",
            "n_squadre": len(squadre),
            "trasferito_in_corso": int(len(squadre) > 1),
            "prima_g": prima, "ultima_g": ultima, "partite_disponibili": disp,
            "presenze": pres, "voti_ufficio": d["ast"], "comparse": d["comparse"],
            "tasso_presenza": round(pres / disp, 4) if disp else 0,
            "quota_spezzoni": round(d["ast"] / d["comparse"], 4) if d["comparse"] else 0,
            "tipo_disponibilita": tipo,
            "gap_max": gap_massimo(d["g_presenza"], prima, ultima),
            "titolare_g1": int(1 in d["g_presenza"]),
            "presenze_g1_3": d["g13"],
            "voto_medio_puro": round(sum(d["voti_puri"]) / pres, 4) if pres else "",
            "sd_voto": dev_std(d["voti_puri"]),
            "fm_media": round(sum(d["fm"]) / pres, 4) if pres else "",
            "sd_fm": dev_std(d["fm"]),
            "fantapunti_tot": round(sum(d["fm"]), 2) if pres else 0,
            "porte_inviolate": d["clean"],
            "tasso_porta_inviolata": round(d["clean"] / pres, 4) if pres else "",
            "Gs": d["Gs"],
            "gol_tot": d["Gf"] + d["Rf"],
            "Gf_azione": d["Gf"], "Rf": d["Rf"], "Rs": d["Rs"],
            "rigori_calciati": rig, "rigorista": int(rig >= 3),
            "Ass": d["Ass"], "Amm": d["Amm"], "Esp": d["Esp"],
            "Au": d["Au"], "Rp": d["Rp"],
        })

    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPI)
        w.writeheader()
        w.writerows(righe)

    # ---- riepilogo di controllo ----
    def media(campo, filtro=None):
        vals = [r[campo] for r in righe
                if r[campo] not in ("", None) and (filtro is None or filtro(r))]
        return sum(vals) / len(vals) if vals else 0

    print("\nControlli:")
    print(f"  fm_media complessiva          {media('fm_media'):.3f}")
    for ruolo in ("P", "D", "C", "A"):
        f = lambda r, ru=ruolo: r["Ruolo"] == ru
        print(f"  fm_media {ruolo}                    {media('fm_media', f):.3f}"
              f"   voto_puro {media('voto_medio_puro', f):.3f}"
              f"   sd_voto {media('sd_voto', f):.3f}")
    fp = lambda r: r["Ruolo"] == "P" and r["presenze"] >= 10
    print(f"\n  portieri (>=10 pres.): tasso porta inviolata "
          f"{media('tasso_porta_inviolata', fp):.3f}")
    rigoristi = sum(r["rigorista"] for r in righe)
    print(f"  rigoristi (>=3 rigori calciati): {rigoristi}")
    tit = sum(r["titolare_g1"] for r in righe)
    print(f"  titolari alla giornata 1: {tit} ({100*tit/len(righe):.1f}%)")
    print(f"\n-> {CSV_OUT}  ({len(righe)} righe)")
    print("Caricalo in chat.")


if __name__ == "__main__":
    main()
