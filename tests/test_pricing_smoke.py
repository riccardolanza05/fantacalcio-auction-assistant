"""Smoke test end-to-end della pipeline di pricing sui dati sintetici in
examples/sample_data/. Gira in CI: non richiede dati fantacalcio.it reali.

Verifica che pricing/modello_prezzo.py e pricing/verdetto.py, invocati come
farebbe un utente da riga di comando, producano un prezzo per ogni
giocatore e un verdetto tra i valori attesi.
"""
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = REPO_ROOT / "examples" / "sample_data"
PRICING_DIR = REPO_ROOT / "pricing"

VERDETTI_ATTESI = {
    "sottovalutato", "sottovalutato robusto",
    "sopravvalutato", "sopravvalutato robusto",
    "valutato correttamente",
}


def test_pipeline_end_to_end(tmp_path):
    predizioni = SAMPLE_DIR / "predizioni_esempio.csv"
    assert predizioni.exists(), (
        "manca examples/sample_data/predizioni_esempio.csv: rigeneralo con "
        "python examples/sample_data/generate_sample_data.py"
    )

    prezzi_csv = tmp_path / "prezzi.csv"
    verdetto_csv = tmp_path / "verdetto.csv"

    subprocess.run(
        [sys.executable, str(PRICING_DIR / "modello_prezzo.py"),
         "--in-csv", str(predizioni), "--out-csv", str(prezzi_csv)],
        check=True, cwd=PRICING_DIR,
    )
    assert prezzi_csv.exists()
    prezzi = pd.read_csv(prezzi_csv)
    assert len(prezzi) > 0
    assert (prezzi["prezzo"] > 0).all(), "ogni giocatore deve avere un prezzo positivo"

    subprocess.run(
        [sys.executable, str(PRICING_DIR / "verdetto.py"),
         "--in-csv", str(prezzi_csv), "--out-csv", str(verdetto_csv)],
        check=True, cwd=PRICING_DIR,
    )
    assert verdetto_csv.exists()
    verdetti = pd.read_csv(verdetto_csv)
    assert len(verdetti) == len(prezzi)
    assert set(verdetti["verdetto"].unique()) <= VERDETTI_ATTESI

    # quote di reparto: la somma sui titolari attesi deve rispettare 10/20/30/40
    quote_attese = {"P": 0.10, "D": 0.20, "C": 0.30, "A": 0.40}
    slot = {"P": 36, "D": 96, "C": 96, "A": 72}
    budget_tot = 12 * 1000
    for ruolo, quota in quote_attese.items():
        g = prezzi[prezzi["Ruolo"] == ruolo].nlargest(slot[ruolo], "prezzo")
        pct = g["prezzo"].sum() / budget_tot
        assert abs(pct - quota) < 0.01, f"quota {ruolo}: {pct:.3f} atteso {quota}"
