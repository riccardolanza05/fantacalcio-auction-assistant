#!/usr/bin/env python3
"""
MODELLO DI PREZZO — Lega Abendosa
=================================

Architettura a 4 strati, in ordine di autorita' decrescente.
Ogni strato puo' correggere il precedente solo entro limiti prefissati.

  STRATO 1 — ANCORA DI MERCATO (FVM)
      L'FVM di fantacalcio.it e' gia' calibrato su 12 squadre x 1000
      crediti: la somma sui 300 giocatori acquistati vale ~12.334.
      Fornisce la FORMA della curva dei prezzi, cioe' la struttura a
      fasce, che quindi non va reinventata.

  STRATO 2 — QUOTE PER REPARTO (10/20/30/40)
      L'FVM implica 5.7/20.1/34.8/39.4. Si riscala ciascun ruolo per
      centrare le quote volute. Questo e' cio' che rende la valutazione
      DIPENDENTE DAL RUOLO: lo stesso rendimento vale diversamente in
      porta e in attacco, perche' i due reparti competono per quote di
      budget diverse.

  STRATO 3 — CORREZIONE STATISTICA (modello di produzione)
      Confronto tra il percentile di produzione attesa e il percentile
      FVM, DENTRO il ruolo. Limitata da un tetto per ruolo:
      P 6, D 12, C 20, A 30 crediti al massimo, e comunque mai oltre
      il 30% del prezzo base. Sposta i prezzi, non li stravolge.

  STRATO 4 — VORP / MODIFICATORE (a valle, in asta)
      Correzione piu' debole di tutte, con lo stesso tetto dello
      strato 3 ma ulteriormente scalata dalla scarsita': finche' molti
      giocatori del reparto sono disponibili la correzione tende a
      zero, e cresce solo quando il reparto si svuota.

USO:
    python modello_prezzo.py
"""

import argparse

import numpy as np
import pandas as pd

# Percorsi di default: file nella cartella corrente. Sovrascrivibili da riga
# di comando, vedi `python modello_prezzo.py --help`.
IN_CSV = "predizioni_2026_27_v2.csv"
OUT_CSV = "prezzi_2026_27.csv"
HREG_PKL = "Hreg.pkl"

BUDGET_TOT = 12 * 1000
SLOT = {"P": 3 * 12, "D": 8 * 12, "C": 8 * 12, "A": 6 * 12}
QUOTE = {"P": 0.10, "D": 0.20, "C": 0.30, "A": 0.40}

# Fasce: numero di giocatori per fascia (punto medio degli intervalli indicati).
# La quinta fascia e' il resto: titolari di piccole e giocatori minori.
FASCE = {
    "P": [8, 5, 5, 5],
    "D": [11, 12, 15, 15],
    "C": [6, 12, 15, 15],
    "A": [6, 8, 12, 12],
}
NOMI_FASCE = ["top", "semitop", "terza", "quarta", "minori"]

# Tetto massimo (in crediti) della correzione statistica sui giocatori di
# prima fascia. Riflette il fatto che un errore di 5 crediti su un portiere
# e' grave quanto un errore di 30 su un attaccante.
TETTO_CORREZIONE = {"P": 6, "D": 12, "C": 20, "A": 30}
TETTO_RELATIVO = 0.30      # e comunque mai oltre il 30% del prezzo base

# STRATO 3b — REGRESSIONE ALLA MEDIA
# Quota di sovraperformance che l'anno seguente PERSISTE, stimata sullo
# storico 2015-16..2025-26 (n=2950, giocatori con almeno 10 presenze).
# Il portiere e' il caso estremo: una sua annata sopra il proprio livello
# non si ripete affatto. L'FVM non corregge questo effetto perche' riflette
# anche la popolarita' del momento; il modello di produzione si', ma il
# prezzo e' ancorato all'FVM, quindi la correzione va applicata qui.
COEF_PERSISTENZA = {"P": -0.08, "D": 0.705, "C": 0.904, "A": 0.810}
PESO_REGRESSIONE = 0.5     # quanto dello scarto corretto si traduce in prezzo

PREZZO_MIN = 1
# Tetto della quinta fascia, calibrato sui prezzi realmente pagati nell'asta
# di agosto 2025 (fasce assegnate per Qt.I, immune al calo di stagione):
# e' il 90esimo percentile osservato. La regola "i minori costano 1-5" vale
# solo per i portieri; negli altri reparti la coda e' molto piu' cara.
PREZZO_MAX_MINORI = {"P": 5, "D": 22, "C": 22, "A": 23}


# ---------------------------------------------------------------------------

def assegna_fasce(df):
    """Ordina per FVM dentro il ruolo e assegna la fascia."""
    df = df.copy()
    # Ordinamento per FVM, ma nella coda l'FVM non discrimina (nel 2025-26
    # tutti i portieri dal 24esimo in giu' avevano FVM = 1). Si usa quindi
    # una chiave composta: FVM come criterio primario e produzione attesa
    # come spareggio, che invece separa i giocatori di quinta fascia.
    df["_chiave"] = (df["FVM"].rank(ascending=False, method="average") * 1000
                     + df["produzione_attesa"].rank(ascending=False,
                                                    method="average"))
    df["rank_ruolo"] = df.groupby("Ruolo")["_chiave"].rank(ascending=True,
                                                           method="first")
    def fascia(row):
        limiti = np.cumsum(FASCE[row["Ruolo"]])
        r = row["rank_ruolo"]
        for i, lim in enumerate(limiti):
            if r <= lim:
                return NOMI_FASCE[i]
        return NOMI_FASCE[-1]
    df["fascia"] = df.apply(fascia, axis=1)
    return df


def prezzo_base(df):
    """STRATO 1+2: forma dall'FVM, livello dalle quote per reparto.

    Si riscala l'FVM di ciascun ruolo in modo che la somma sui giocatori
    effettivamente acquistati centri la quota di budget voluta.
    """
    df = df.copy()
    df["base"] = np.nan

    for R, quota in QUOTE.items():
        m = df["Ruolo"] == R
        g = df.loc[m].sort_values("FVM", ascending=False)
        draftati = g.index[: SLOT[R]]          # i soli che verranno comprati

        budget_ruolo = BUDGET_TOT * quota
        # ogni slot costa almeno 1 credito: il resto si distribuisce sull'FVM
        residuo = budget_ruolo - SLOT[R] * PREZZO_MIN
        somma_fvm = df.loc[draftati, "FVM"].sum()
        k = residuo / somma_fvm if somma_fvm > 0 else 0.0
        df.loc[m, "base"] = PREZZO_MIN + df.loc[m, "FVM"] * k

    return df


def correzione_statistica(df):
    """STRATO 3: scostamento tra opinione del modello e mercato, limitato.

    Due componenti, entrambe dentro lo stesso tetto:
      3a  divergenza tra percentile di produzione attesa e percentile FVM;
      3b  regressione alla media: penalizza chi nell'ultima stagione ha
          fatto meglio del proprio livello storico, con intensita' diversa
          per ruolo.
    """
    df = df.copy()
    df["pct_modello"] = df.groupby("Ruolo")["produzione_attesa"].rank(pct=True)
    df["pct_mercato"] = df.groupby("Ruolo")["FVM"].rank(pct=True)
    df["div_modello"] = df["pct_modello"] - df["pct_mercato"]

    # 3b: scarto di fantamedia riportato su scala percentile del ruolo
    if "correzione_fm" in df.columns:
        sd = df.groupby("Ruolo")["correzione_fm"].transform(
            lambda s: s.std() if s.std() and s.std() > 0 else 1.0)
        df["div_regressione"] = (df["correzione_fm"].fillna(0) / sd
                                 ).clip(-2, 2) * 0.25 * PESO_REGRESSIONE
    else:
        df["div_regressione"] = 0.0

    df["divergenza"] = df["div_modello"] + df["div_regressione"]

    # la correzione e' proporzionale alla divergenza, con doppio tetto
    tetto_abs = df["Ruolo"].map(TETTO_CORREZIONE)
    tetto = np.minimum(tetto_abs, df["base"] * TETTO_RELATIVO)
    df["correzione"] = np.clip(df["divergenza"] * 2.0 * tetto, -tetto, tetto)
    df["prezzo"] = df["base"] + df["correzione"]
    return df


def normalizza(df, n_iter=30):
    """Riporta le somme sulle quote rispettando il tetto della quinta fascia.

    Va fatto iterativamente: clipare i minori a 5 crediti sottrae budget, che
    deve essere riassorbito dalle fasce superiori, il che puo' richiedere un
    nuovo clip. Poche iterazioni bastano a convergere.
    """
    df = df.copy()
    minori = df["fascia"] == "minori"

    tetto_minori = df["Ruolo"].map(PREZZO_MAX_MINORI)

    for _ in range(n_iter):
        df.loc[minori, "prezzo"] = np.minimum(df.loc[minori, "prezzo"],
                                              tetto_minori[minori])
        df.loc[minori, "prezzo"] = df.loc[minori, "prezzo"].clip(lower=PREZZO_MIN)
        df["prezzo"] = df["prezzo"].clip(lower=PREZZO_MIN)

        scarto_max = 0.0
        for R, quota in QUOTE.items():
            m = df["Ruolo"] == R
            g = df.loc[m].sort_values("prezzo", ascending=False)
            draftati = g.index[: SLOT[R]]
            obiettivo = BUDGET_TOT * quota
            attuale = df.loc[draftati, "prezzo"].sum()
            scarto_max = max(scarto_max, abs(attuale - obiettivo))

            # il budget mancante va redistribuito solo su chi non e' al tetto
            liberi = df.index[m & ~minori]
            residuo_liberi = (df.loc[liberi, "prezzo"] - PREZZO_MIN).clip(lower=0)
            bloccati = df.loc[[i for i in draftati if i not in set(liberi)],
                              "prezzo"].sum()
            da_coprire = obiettivo - bloccati - len(
                [i for i in draftati if i in set(liberi)]) * PREZZO_MIN
            somma_res = residuo_liberi.loc[
                [i for i in draftati if i in set(liberi)]].sum()
            if somma_res > 0 and da_coprire > 0:
                k = da_coprire / somma_res
                df.loc[liberi, "prezzo"] = PREZZO_MIN + residuo_liberi * k

        if scarto_max < 1.0:
            break

    df.loc[minori, "prezzo"] = np.minimum(df.loc[minori, "prezzo"],
                                          tetto_minori[minori])
    df["prezzo"] = df["prezzo"].clip(lower=PREZZO_MIN)
    return df


def continuita(df):
    """Verifica che non ci siano salti tra fasce contigue.

    Le fasce descrivono come si compongono le rose, non scalini di prezzo:
    l'ultimo 'top' deve costare quanto il primo 'semitop'.
    """
    righe = []
    for R in "PDCA":
        g = df[df["Ruolo"] == R].sort_values("prezzo", ascending=False)
        for i in range(len(NOMI_FASCE) - 1):
            a = g[g["fascia"] == NOMI_FASCE[i]]["prezzo"]
            b = g[g["fascia"] == NOMI_FASCE[i + 1]]["prezzo"]
            if len(a) and len(b):
                righe.append({"Ruolo": R,
                              "confine": f"{NOMI_FASCE[i]}|{NOMI_FASCE[i+1]}",
                              "ultimo": round(a.min(), 1),
                              "primo": round(b.max(), 1),
                              "salto": round(a.min() - b.max(), 1)})
    return pd.DataFrame(righe)


# ---------------------------------------------------------------------------
# STRATO 4 — da usare durante l'asta
# ---------------------------------------------------------------------------

def correzione_vorp(prezzo_base_giocatore, ruolo, fascia, vantaggio_vorp,
                    quota_reparto_rimanente):
    """Correzione live, la piu' debole della catena.

    vantaggio_vorp: scostamento (in fantapunti) rispetto al replacement
                    corrente, gia' comprensivo del modificatore difesa.
    quota_reparto_rimanente: frazione di giocatori di quella fascia ancora
                    disponibili (1.0 a inizio asta, 0.0 a reparto esaurito).

    Due freni:
      - lo stesso tetto per ruolo dello strato 3;
      - la scarsita': con molti giocatori ancora disponibili la correzione
        e' quasi nulla, perche' un'alternativa equivalente e' ancora a
        portata di mano e non ha senso pagare un premio.
    """
    tetto = min(TETTO_CORREZIONE[ruolo], prezzo_base_giocatore * TETTO_RELATIVO)
    scarsita = 1.0 - float(np.clip(quota_reparto_rimanente, 0.0, 1.0))
    grezza = np.tanh(vantaggio_vorp / 50.0) * tetto      # satura dolcemente
    return float(np.clip(grezza * scarsita, -tetto, tetto))


def main(in_csv=IN_CSV, out_csv=OUT_CSV, hreg_pkl=HREG_PKL):
    df = pd.read_csv(in_csv)
    try:
        H = pd.read_pickle(hreg_pkl)
        df = df.merge(H[["Id", "fm_storica", "fm_shrunk", "fm_L1",
                         "correzione_fm", "n_stagioni"]], on="Id", how="left")
    except FileNotFoundError:
        print(f"[!] {hreg_pkl} assente: regressione alla media non applicata")
        df["correzione_fm"] = 0.0
        for col in ("n_stagioni", "fm_L1", "fm_storica", "fm_shrunk"):
            df[col] = np.nan
    df = assegna_fasce(df)
    df = prezzo_base(df)
    df = correzione_statistica(df)
    df = normalizza(df)

    print("=== QUOTE DI BUDGET OTTENUTE ===")
    tot = 0
    for R in "PDCA":
        g = df[df["Ruolo"] == R].nlargest(SLOT[R], "prezzo")
        s = g["prezzo"].sum()
        tot += s
        print(f"  {R}: {s:7.0f} crediti  ({100*s/BUDGET_TOT:4.1f}%  "
              f"obiettivo {100*QUOTE[R]:.0f}%)   prezzo max {g['prezzo'].max():.0f}")
    print(f"  totale: {tot:.0f} / {BUDGET_TOT}")

    print("\n=== PREZZO MEDIO PER FASCIA ===")
    piv = df.pivot_table(index="fascia", columns="Ruolo", values="prezzo",
                         aggfunc="mean").reindex(NOMI_FASCE)
    print(piv.round(1).to_string())

    print("\n=== CONTINUITA' TRA FASCE (salto = ultimo della fascia - primo della successiva) ===")
    print(continuita(df).to_string(index=False))

    print("\n=== EFFETTO DELLA CORREZIONE STATISTICA ===")
    print(df.groupby("Ruolo")["correzione"].agg(
        media_assoluta=lambda s: s.abs().mean(),
        massima=lambda s: s.abs().max()).round(1).to_string())

    out = df[["Id", "Nome", "Squadra", "Ruolo", "fascia", "FVM", "QtI",
              "produzione_attesa", "p10", "p90", "pct_titolarita",
              "n_stagioni", "fm_L1", "fm_storica", "fm_shrunk", "correzione_fm",
              "base", "div_modello", "div_regressione", "correzione",
              "prezzo"]].copy()
    out = out.sort_values(["Ruolo", "prezzo"], ascending=[True, False]).round(1)
    out.to_csv(out_csv, index=False)
    print(f"\n-> {out_csv}")

    print("\n=== TOP 6 PER RUOLO ===")
    for R in "PDCA":
        print(f"\n--- {R} ---")
        print(out[out["Ruolo"] == R].head(6)[
            ["Nome", "Squadra", "fascia", "FVM", "base", "correzione", "prezzo"]
        ].to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Strati 1-3 del modello di prezzo.")
    ap.add_argument("--in-csv", default=IN_CSV,
                     help=f"predizioni del modello ML (default: {IN_CSV})")
    ap.add_argument("--out-csv", default=OUT_CSV,
                     help=f"prezzi calcolati, in uscita (default: {OUT_CSV})")
    ap.add_argument("--hreg", default=HREG_PKL,
                     help=f"shrinkage gerarchico per lo strato 3b, opzionale (default: {HREG_PKL})")
    args = ap.parse_args()
    main(in_csv=args.in_csv, out_csv=args.out_csv, hreg_pkl=args.hreg)
