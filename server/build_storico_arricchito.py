"""
Costruisce `storico_asta_2025_26.xlsx`: i prezzi dell'asta 2025-26 arricchiti
con il profilo di ciascun giocatore (ruolo, squadra, FVM pre-asta, presenze
e quindi titolarita' effettiva).

Serve alla ricerca dei "profili simili": quando un giocatore non era all'asta
dell'anno scorso, vogliamo poter rispondere alla domanda "quanto e' costato
l'anno scorso un giocatore con lo stesso ruolo, nella stessa squadra e con
titolarita'/quotazione paragonabili?".

Da lanciare una volta sola; poi il server usa solo il file prodotto.
"""
import os
import openpyxl

from common import normalize_name, team_to_abbr
from parse_rose_lega import parse_rose_lega

GIORNATE = 38


def carica_quotazioni(path: str) -> dict:
    """(nome_norm, abbr) -> {fvm, qta, ruolo, squadra}"""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Tutti"]
    header = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
    idx = {h: i for i, h in enumerate(header)}
    out = {}
    for row in ws.iter_rows(min_row=3, values_only=True):
        nome = row[idx["Nome"]]
        if not nome:
            continue
        squadra = row[idx["Squadra"]] or ""
        abbr = team_to_abbr(squadra)
        out[(normalize_name(nome), abbr)] = {
            "fvm": row[idx["FVM"]],
            "qta": row[idx.get("Qt.A", idx["FVM"])],
            "ruolo": row[idx["R"]],
            "squadra": squadra,
        }
    return out


def carica_statistiche(path: str) -> dict:
    """(nome_norm, abbr) -> {presenze, fm}"""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Tutti"]
    header = [c.value for c in next(ws.iter_rows(min_row=2, max_row=2))]
    idx = {h: i for i, h in enumerate(header)}
    out = {}
    for row in ws.iter_rows(min_row=3, values_only=True):
        nome = row[idx["Nome"]]
        if not nome:
            continue
        squadra = row[idx["Squadra"]] or ""
        out[(normalize_name(nome), team_to_abbr(squadra))] = {
            "presenze": row[idx["Pv"]] or 0,
            "fm": row[idx["Fm"]],
        }
    return out


def costruisci(rose_path, quotazioni_path, statistiche_path, out_path):
    quot = carica_quotazioni(quotazioni_path)
    stat = carica_statistiche(statistiche_path)
    rose = parse_rose_lega(rose_path)

    righe, senza_profilo = [], 0
    for r in rose:
        chiave = (normalize_name(r["calciatore"]), r["squadra_reale"])
        q = quot.get(chiave)
        s = stat.get(chiave)
        if q is None:
            # fallback su nome, se univoco (cambio squadra a mercato aperto)
            cands = [v for k, v in quot.items() if k[0] == chiave[0]]
            q = cands[0] if len(cands) == 1 else None
        if s is None:
            cands = [v for k, v in stat.items() if k[0] == chiave[0]]
            s = cands[0] if len(cands) == 1 else None
        if q is None and s is None:
            senza_profilo += 1

        presenze = (s or {}).get("presenze") or 0
        righe.append({
            "Nome": r["calciatore"],
            "SquadraAbbr": r["squadra_reale"],
            "Squadra": (q or {}).get("squadra") or "",
            "Ruolo": r["ruolo"] or (q or {}).get("ruolo") or "",
            "Costo": r["costo"],
            "SquadraFantacalcio": r["squadra_fantacalcio"],
            "FVM": (q or {}).get("fvm"),
            "QtA": (q or {}).get("qta"),
            "Presenze": presenze,
            "TitolaritaPct": round(100.0 * presenze / GIORNATE, 1),
            "FMmedia": (s or {}).get("fm"),
        })

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "asta_2025_26"
    cols = list(righe[0].keys())
    ws.append(cols)
    for riga in righe:
        ws.append([riga[c] for c in cols])
    from openpyxl.styles import Font
    for cell in ws[1]:
        cell.font = Font(name="Arial", bold=True)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Arial")
    larghezze = {"A": 20, "B": 13, "C": 13, "D": 7, "E": 8, "F": 30,
                  "G": 8, "H": 8, "I": 10, "J": 15, "K": 10}
    for col, w in larghezze.items():
        ws.column_dimensions[col].width = w
    wb.save(out_path)

    print(f"Scritto {out_path}: {len(righe)} acquisti")
    print(f"  senza profilo (ne' quotazione ne' statistiche): {senza_profilo}")
    con_fvm = sum(1 for r in righe if r["FVM"])
    print(f"  con FVM: {con_fvm} | con presenze > 0: {sum(1 for r in righe if r['Presenze'])}")


if __name__ == "__main__":
    import argparse

    HERE = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Costruisce storico_asta_2025_26.xlsx dai prezzi pagati in lega.")
    ap.add_argument("--rose", required=True,
                     help="export Rose_lega-<tuasigla>.xlsx della tua lega (dato privato, non nel repo)")
    ap.add_argument("--quotazioni", default=os.path.join(HERE, "Quotazioni_Fantacalcio_Stagione_2025_26.xlsx"),
                     help="quotazioni ufficiali fantacalcio.it della stagione conclusa")
    ap.add_argument("--statistiche", default=os.path.join(HERE, "Statistiche_Fantacalcio_Stagione_2025_26.xlsx"),
                     help="statistiche ufficiali fantacalcio.it della stagione conclusa")
    ap.add_argument("--out", default=os.path.join(HERE, "storico_asta_2025_26.xlsx"),
                     help="file d'uscita, usato dal server per i riferimenti storici")
    args = ap.parse_args()
    costruisci(args.rose, args.quotazioni, args.statistiche, args.out)
