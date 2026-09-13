"""
Costruisce `giocatori_2026_27.xlsx`, il database usato dal server durante
l'asta. Sostituisce il vecchio `fair_values_2026_27.xlsx`, che si basava sul
prezzo VORP puro.

Fonti unite:
  - prezzi_2026_27.csv          (nuovo modello a 4 strati: prezzo, fascia,
                                  base, correzione, produzione attesa, FVM,
                                  QtI, titolarita')
  - predizioni_2026_27_v2.xlsx  (giornate_perse_stimate -> flag infortunio,
                                  presenze e FM 2025-26)
  - Statistiche 2025-26         (gol e assist della scorsa stagione)

Da lanciare una volta sola quando aggiorni i dati; poi il server usa solo il
file prodotto.
"""
import os

import numpy as np
import openpyxl
import pandas as pd

from clean_sheet_2025_26 import CLEAN_SHEET_2025_26
from probabili import parse_infortunati
from common import normalize_name, team_to_abbr

# Soglia oltre la quale segnaliamo il giocatore come infortunato: il modello
# stima le giornate che saltera'. Sotto una giornata l'informazione non e'
# azionabile in asta e genererebbe solo rumore.
SOGLIA_INFORTUNIO = 1.0

# Fasce sulle quali si usa il verdetto "base" (riferimento del modello):
# sono quelle dove il budget e' reale e il confronto e' pulito. Sulle code
# vale di piu' il riferimento di lega, che riflette i prezzi realmente
# pagati quando conta riempire gli slot.
FASCE_VERDETTO_BASE = ("top", "semitop", "terza")

# Squadre in lega (allineato a NSQ in modello_prezzo.py)
NSQ = 10
BUDGET_LEGA = NSQ * 1000


def carica_statistiche(path: str) -> dict:
    """(nome_norm, abbr) -> {gol, assist, presenze, fm}"""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Tutti"]
    header = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
    i = {h: n for n, h in enumerate(header)}
    out = {}
    for row in ws.iter_rows(min_row=3, values_only=True):
        nome, squadra = row[i["Nome"]], row[i["Squadra"]]
        if not nome:
            continue
        # ATTENZIONE: nel file Statistiche il campo Gf comprende GIA' i gol
        # su rigore (a differenza del file voti per giornata, dove i rigori
        # sono separati). Sommare R+ qui li conterebbe due volte.
        out[(normalize_name(nome), team_to_abbr(squadra or ""))] = {
            "gol": row[i["Gf"]] or 0,
            "assist": row[i["Ass"]] or 0,
            "gol_subiti": row[i["Gs"]] or 0,
            "rigori_parati": row[i["Rp"]] or 0,
            "presenze": row[i["Pv"]] or 0,
            "fm": row[i["Fm"]],
        }
    return out


PARTICELLE = ("de", "van", "da", "di", "dos", "del", "der", "la", "den")


def _cognome(nome: str) -> str:
    """Estrae il cognome da entrambi i formati in cui compaiono i nomi.

      classifica clean sheet:  "J. Butez", "David de Gea", "Josep Martinez"
      file fantacalcio.it:     "Butez", "Martinez Jo.", "Pessina Mas."

    Il punto e' il segnale affidabile di iniziale: la lunghezza no, perche'
    ci sono cognomi corti ("Gea" in "de Gea" verrebbe scambiato per
    un'iniziale).
    """
    grezzo = str(nome).strip()
    token = [t for t in grezzo.replace("-", " ").split() if t]

    # 1) via le iniziali puntate, ovunque si trovino
    senza_iniziali = [t for t in token if not t.endswith(".")]
    if senza_iniziali and len(senza_iniziali) < len(token):
        token = senza_iniziali

    minuscoli = [t.lower().strip(".") for t in token]
    minuscoli = [t for t in minuscoli if t]
    if not minuscoli:
        return normalize_name(grezzo)

    # 2) cognome composto con particella: "David de Gea" -> "de gea"
    for i, t in enumerate(minuscoli):
        if t in PARTICELLE and i < len(minuscoli) - 1:
            return normalize_name(" ".join(minuscoli[i:]))

    # 3) "Josep Martinez" -> "martinez";  "Butez" -> "butez"
    return normalize_name(minuscoli[-1])


def carica_clean_sheet() -> dict:
    """cognome_normalizzato -> clean sheet. Il ruolo P fa gia' da filtro, quindi
    il cognome basta a identificare il portiere."""
    return {_cognome(nome): cs for nome, _abbr, cs in CLEAN_SHEET_2025_26}


def carica_predizioni(path: str) -> dict:
    """Id -> {giornate_perse, presenze, fm}"""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    header = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    i = {h: n for n, h in enumerate(header)}
    def num(v):
        """il campo arriva come testo ('0.0'): va convertito, non confrontato"""
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        pid = row[i["Id"]]
        if pid is None:
            continue
        out[int(pid)] = {
            "giornate_perse": num(row[i["giornate_perse_stimate"]]),
            "presenze": row[i["presenze_2025_26"]],
            "fm": row[i["fm_media_2025_26"]],
        }
    return out


def costruisci(prezzi_csv, verdetto_csv, predizioni_xlsx, statistiche_xlsx,
                probabili_html, out_xlsx):
    df = pd.read_csv(prezzi_csv)

    # --- verdetto di valutazione ---
    # Il file ne contiene DUE, che rispondono a domande diverse:
    #   verdetto_base  confronta col riferimento del modello. E' pulito e
    #                  affidabile dove il budget c'e' davvero, cioe' sulle
    #                  fasce alte (top, semitop, terza).
    #   verdetto_lega  confronta con quanto la lega paga davvero. Coglie
    #                  meglio la dinamica di fine asta sulle code, dove i
    #                  prezzi sono guidati dall'obbligo di riempire gli slot
    #                  piu' che dal valore.
    # Si sceglie il riferimento in base alla fascia, e si tiene traccia di
    # quale e' stato usato: e' un'informazione che serve per sapere quanto
    # fidarsi del numero.
    verd = pd.read_csv(verdetto_csv)[
        ["Id", "rif_base", "scarto_base_pct", "verdetto_base",
         "rif_lega", "scarto_lega_pct", "verdetto_lega"]]
    df = df.merge(verd, on="Id", how="left")

    alte = df["fascia"].isin(FASCE_VERDETTO_BASE)
    df["verdetto"] = df["verdetto_lega"].where(~alte, df["verdetto_base"])
    df["scarto_pct"] = df["scarto_lega_pct"].where(~alte, df["scarto_base_pct"])
    df["prezzo_mercato"] = df["rif_lega"].where(~alte, df["rif_base"])
    df["rif_verdetto"] = np.where(alte, "modello", "lega")

    pred = carica_predizioni(predizioni_xlsx)
    stat = carica_statistiche(statistiche_xlsx)
    clean_sheet = carica_clean_sheet()

    # infortuni: la dicitura arriva dalla pagina delle probabili formazioni
    # ("out contro Venezia", "rientro da inizio ottobre") e viene riportata
    # tale e quale, senza reinterpretarla
    infortuni = parse_infortunati(probabili_html)
    inf_per_cognome = {_cognome(n): (n, d) for n, d in infortuni.items()}
    inf_usati = set()
    # Il match per cognome va usato solo quando NON e' ambiguo: nel pool ci
    # sono omonimi (due Pessina, due Martinez) e attribuire a entrambi
    # l'infortunio di uno solo e' peggio che non segnalarlo affatto.
    from collections import Counter
    cognomi_pool = Counter(_cognome(str(n)) for n in df["Nome"])

    righe = []
    n_stat = 0
    cs_usati = set()
    for _, r in df.iterrows():
        pid = int(r["Id"])
        p = pred.get(pid, {})
        chiave = (normalize_name(r["Nome"]), team_to_abbr(str(r["Squadra"])))
        s = stat.get(chiave)
        if s is None:
            # il giocatore puo' aver cambiato squadra: ripiega sul nome
            cands = [v for k, v in stat.items() if k[0] == chiave[0]]
            s = cands[0] if len(cands) == 1 else {}
        if s:
            n_stat += 1

        cog_g = _cognome(str(r["Nome"]))
        voce_inf = infortuni.get(str(r["Nome"]))
        if voce_inf is None and cog_g in inf_per_cognome and cognomi_pool[cog_g] == 1:
            voce_inf = inf_per_cognome[cog_g][1]
        if voce_inf:
            inf_usati.add(cog_g)
        infortunato = bool(voce_inf)

        # Clean sheet: solo per i portieri. Chi non e' in classifica ne ha 0,
        # ma solo se ha davvero giocato: per chi non ha presenze il dato non
        # esiste e vale None (diverso da "zero clean sheet in 38 partite").
        cs = None
        if r["Ruolo"] == "P":
            cog = _cognome(str(r["Nome"]))
            if cog in clean_sheet:
                cs = clean_sheet[cog]
                cs_usati.add(cog)
            elif (s or {}).get("presenze"):
                cs = 0

        righe.append({
            "Id": pid,
            "Nome": r["Nome"],
            "Squadra": r["Squadra"],
            "Ruolo": r["Ruolo"],
            "fascia": r["fascia"],
            "FVM": r["FVM"],
            "QtI": r["QtI"],
            "pct_titolarita": r["pct_titolarita"],
            "produzione_attesa": r["produzione_attesa"],
            "p10": r["p10"],
            "p90": r["p90"],
            "prezzo_base": r["base"],
            "correzione": r["correzione"],
            "prezzo_modello": r["prezzo"],
            "prezzo_mercato": r.get("prezzo_mercato"),
            "scarto_pct": r.get("scarto_pct"),
            "verdetto": r.get("verdetto"),
            "rif_verdetto": r.get("rif_verdetto"),
            "verdetto_base": r.get("verdetto_base"),
            "scarto_base_pct": r.get("scarto_base_pct"),
            "verdetto_lega": r.get("verdetto_lega"),
            "scarto_lega_pct": r.get("scarto_lega_pct"),
            "div_modello": r.get("div_modello"),
            "div_regressione": r.get("div_regressione"),
            "correzione_fm": r.get("correzione_fm"),
            "gol_2025_26": (s or {}).get("gol"),
            "assist_2025_26": (s or {}).get("assist"),
            "gol_subiti_2025_26": (s or {}).get("gol_subiti"),
            "rigori_parati_2025_26": (s or {}).get("rigori_parati"),
            "clean_sheet_2025_26": cs,
            "presenze_2025_26": p.get("presenze", (s or {}).get("presenze")),
            "fm_media_2025_26": p.get("fm", (s or {}).get("fm")),
            "infortunato": infortunato,
            "nota_infortunio": voce_inf,
        })

    out = pd.DataFrame(righe).sort_values(["Ruolo", "prezzo_modello"],
                                           ascending=[True, False])
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as w:
        out.to_excel(w, sheet_name="giocatori_2026_27", index=False)
        ws = w.sheets["giocatori_2026_27"]
        from openpyxl.styles import Font
        for cell in ws[1]:
            cell.font = Font(name="Arial", bold=True)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = Font(name="Arial")
        for n_col in range(1, ws.max_column + 1):
            lettera = openpyxl.utils.get_column_letter(n_col)
            intestazione = ws.cell(row=1, column=n_col).value or ""
            ws.column_dimensions[lettera].width = max(9, min(22, len(str(intestazione)) + 3))

    print(f"Scritto {out_xlsx}: {len(out)} giocatori")
    print(f"  con statistiche 2025-26: {n_stat}")
    print(f"  infortunati segnalati: {int(out['infortunato'].sum())} "
          f"su {len(infortuni)} presenti nelle probabili")
    persi = set(inf_per_cognome) - inf_usati
    if persi:
        print(f"  non agganciati (fuori dal pool): "
              f"{sorted(inf_per_cognome[c][0] for c in persi)}")
    print(f"  con gol valorizzati: {out['gol_2025_26'].notna().sum()}")
    portieri = out[out.Ruolo == "P"]
    print(f"  portieri: {len(portieri)}, con clean sheet: "
          f"{portieri['clean_sheet_2025_26'].notna().sum()}")
    print(f"  con verdetto: {out['verdetto'].notna().sum()}")
    print(pd.crosstab(out["verdetto"], out["rif_verdetto"]).to_string())
    non_usati = set(clean_sheet) - cs_usati
    if non_usati:
        print(f"  ATTENZIONE - portieri in classifica clean sheet non trovati "
              f"nel pool 2026-27: {sorted(non_usati)}")
    print("\nprezzo modello per ruolo (somma sui titolari attesi):")
    for R, slot in [("P", 3 * NSQ), ("D", 8 * NSQ), ("C", 8 * NSQ), ("A", 6 * NSQ)]:
        g = out[out.Ruolo == R].nlargest(slot, "prezzo_modello")
        print(f"  {R}: {g['prezzo_modello'].sum():7.0f} crediti "
              f"({100*g['prezzo_modello'].sum()/BUDGET_LEGA:4.1f}%)  max {g['prezzo_modello'].max():.0f}")


if __name__ == "__main__":
    import argparse

    HERE = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Costruisce giocatori_2026_27.xlsx dai file intermedi.")
    ap.add_argument("--prezzi-csv", default=os.path.join(HERE, "..", "pricing", "prezzi_2026_27.csv"),
                     help="uscita di pricing/modello_prezzo.py")
    ap.add_argument("--verdetto-csv", default=os.path.join(HERE, "..", "pricing", "verdetto_2026_27.csv"),
                     help="uscita di pricing/verdetto.py")
    ap.add_argument("--predizioni", default=os.path.join(HERE, "predizioni_2026_27_v2.xlsx"),
                     help="uscita del modello ML (vedi docs/data-sources.md: manca in questo repo)")
    ap.add_argument("--statistiche", default=os.path.join(HERE, "Statistiche_Fantacalcio_Stagione_2025_26.xlsx"),
                     help="file ufficiale fantacalcio.it della stagione conclusa")
    ap.add_argument("--probabili", default=os.path.join(HERE, "probabili-formazioni-serie-a"),
                     help="pagina probabili-formazioni-serie-a salvata come HTML")
    ap.add_argument("--out", default=os.path.join(HERE, "giocatori_2026_27.xlsx"),
                     help="database d'uscita, usato dal server")
    args = ap.parse_args()
    costruisci(
        args.prezzi_csv,
        args.verdetto_csv,
        args.predizioni,
        args.statistiche,
        args.probabili,
        args.out,
    )
