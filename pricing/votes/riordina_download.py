#!/usr/bin/env python3
"""
Riordina i file scaricati dal browser (download_voti_browser.js)
nella struttura che parse_voti.py si aspetta.

Da:   voti_2015-16_g01.xlsx        (tutti insieme, in Download)
A:    voti_raw/2015-16/g01.xlsx

USO:
    python riordina_download.py "C:/Users/<utente>/Downloads"

Se non passi il percorso, cerca nella cartella Download di default.
"""

import os
import re
import shutil
import sys

DEST = "voti_raw"
PATTERN = re.compile(r"^voti_(\d{4}-\d{2})_g(\d{2})\.xlsx$", re.IGNORECASE)


def cartella_download() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    return os.path.join(os.path.expanduser("~"), "Downloads")


def main():
    src = cartella_download()
    if not os.path.isdir(src):
        sys.exit(f"Cartella non trovata: {src}\n"
                 f"Passala come argomento: python riordina_download.py \"C:/percorso\"")

    print(f"Cerco in: {src}")

    spostati, saltati, duplicati = 0, 0, 0

    for nome in sorted(os.listdir(src)):
        m = PATTERN.match(nome)
        if not m:
            continue

        # Chrome rinomina i doppioni in "voti_..._g01 (1).xlsx": il pattern
        # non li cattura, quindi vengono ignorati di proposito.
        stagione, giornata = m.group(1), m.group(2)
        percorso_src = os.path.join(src, nome)

        if os.path.getsize(percorso_src) < 2000:
            print(f"  salto (troppo piccolo, probabile errore): {nome}")
            saltati += 1
            continue

        dest_dir = os.path.join(DEST, stagione)
        os.makedirs(dest_dir, exist_ok=True)
        percorso_dest = os.path.join(dest_dir, f"g{giornata}.xlsx")

        if os.path.exists(percorso_dest):
            duplicati += 1
            continue

        shutil.copy2(percorso_src, percorso_dest)
        spostati += 1

    print(f"\nCopiati: {spostati} | gia' presenti: {duplicati} | saltati: {saltati}")

    if spostati or duplicati:
        print("\nCopertura per stagione:")
        for st in sorted(os.listdir(DEST)):
            d = os.path.join(DEST, st)
            if os.path.isdir(d):
                n = len([f for f in os.listdir(d) if f.endswith(".xlsx")])
                stato = "OK" if n == 38 else f"mancano {38 - n}"
                print(f"  {st}: {n}/38 giornate  [{stato}]")
        print("\nProssimo passo: python parse_voti.py")
    else:
        print("\nNessun file trovato col pattern 'voti_STAGIONE_gNN.xlsx'.")
        print("Verifica che lo script JS sia arrivato a scaricare qualcosa.")


if __name__ == "__main__":
    main()
