"""Test manuale (script, non pytest) dei due comportamenti piu' delicati:
identita' stabile delle rose e ripartizione del budget della propria
squadra. Richiede un server/giocatori_2026_27.xlsx reale (non incluso nel
repo, vedi docs/data-sources.md): senza, PlayerDB non trova il file.

Uso:
    python tests/test_squadre.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(HERE, "..", "server")
sys.path.insert(0, SERVER_DIR)

from player_db import PlayerDB
from vorp_live import VorpLive
from live_state import LiveAuctionState

db = PlayerDB(os.path.join(SERVER_DIR, "giocatori_2026_27.xlsx"))


def nuovo_stato():
    return LiveAuctionState(db, vorp_live=VorpLive(list(db.by_id.values())))


def snap(uid, nome, budget, counts, rosa):
    return {"uid": uid, "nome_squadra": nome, "budget": budget,
            "max_offerta": budget - 23, "counts": counts, "rosa": rosa}


print("=" * 68)
print("1) RINOMINA DELLA ROSA (Squadra Provvisoria -> Nome Definitivo)")
print("=" * 68)
st = nuovo_stato()
st.apply_teams_snapshot([snap("uid-A", "Squadra Provvisoria", 1000,
                               {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, [])])
st.apply_teams_snapshot([snap("uid-A", "Squadra Provvisoria", 900,
                               {"P": 0, "D": 0, "C": 0, "A": 1, "TOT": 1},
                               [{"nome": "Kean", "squadra": "Fiorentina", "ruolo": "A"}])])
st.apply_teams_snapshot([snap("uid-A", "Nome Definitivo", 800,
                               {"P": 0, "D": 1, "C": 0, "A": 1, "TOT": 2},
                               [{"nome": "Kean", "squadra": "Fiorentina", "ruolo": "A"},
                                {"nome": "Bastoni", "squadra": "Inter", "ruolo": "D"}])])
print(f"   rose totali: {len(st.teams)} (atteso 1, non 2)")
for t in st.teams_summary():
    print(f"   {t['nome_squadra']:12s} budget {t['budget']} giocatori {t['n_giocatori']}")

print()
print("=" * 68)
print("2) RIORDINO DELLE CARD (NapoLanza e Squadra Avversaria si scambiano)")
print("=" * 68)
st = nuovo_stato()
st.apply_teams_snapshot([
    snap("uid-1", "NapoLanza", 1000, {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, []),
    snap("uid-2", "Squadra Avversaria", 1000, {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, []),
])
# stesso snapshot ma con le squadre in ordine invertito
st.apply_teams_snapshot([
    snap("uid-2", "Squadra Avversaria", 950, {"P": 0, "D": 0, "C": 0, "A": 1, "TOT": 1},
         [{"nome": "Kean", "squadra": "Fiorentina", "ruolo": "A"}]),
    snap("uid-1", "NapoLanza", 1000, {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, []),
])
print(f"   rose totali: {len(st.teams)} (atteso 2)")
for t in st.teams_summary():
    print(f"   {t['nome_squadra']:16s} budget {t['budget']} giocatori {t['n_giocatori']}")

print()
print("=" * 68)
print("3) UID RIGENERATI (pagina ricaricata): riaggancio dalla rosa")
print("=" * 68)
st = nuovo_stato()
rosa = [{"nome": "Kean", "squadra": "Fiorentina", "ruolo": "A"},
        {"nome": "Bastoni", "squadra": "Inter", "ruolo": "D"},
        {"nome": "Svilar", "squadra": "Roma", "ruolo": "P"}]
st.apply_teams_snapshot([snap("uid-vecchio", "NapoLanza", 700,
                               {"P": 1, "D": 1, "C": 0, "A": 1, "TOT": 3}, rosa)])
st.apply_teams_snapshot([snap("uid-NUOVO", "NapoLanza", 700,
                               {"P": 1, "D": 1, "C": 0, "A": 1, "TOT": 3}, rosa)])
print(f"   rose totali: {len(st.teams)} (atteso 1: riconosciuta dalla rosa)")

print()
print("=" * 68)
print("4) RIPARTIZIONE DEL BUDGET — la mia squadra c'e'")
print("=" * 68)
st = nuovo_stato()
st.apply_teams_snapshot([snap("u1", "NapoLanza", 1000,
                               {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, [])])
acquisti = [("Svilar", "Roma", "P", 1, 940, {"P": 1, "TOT": 1}),
            ("Bastoni", "Inter", "D", 2, 850, {"P": 1, "D": 1, "TOT": 2}),
            ("Kean", "Fiorentina", "A", 3, 620, {"P": 1, "D": 1, "A": 1, "TOT": 3})]
rosa_prog = []
for nome, sq, ruolo, n, budget, counts in acquisti:
    rosa_prog = rosa_prog + [{"nome": nome, "squadra": sq, "ruolo": ruolo}]
    c = {"P": 0, "D": 0, "C": 0, "A": 0}
    c.update(counts)
    st.apply_teams_snapshot([snap("u1", "NapoLanza", budget, c, list(rosa_prog))])

rip = st.ripartizione_mia_squadra()
print(f"   squadra: {rip['nome_squadra']} | residuo {rip['budget_residuo']} | "
      f"speso {rip['speso_totale']}")
for r in ("P", "D", "C", "A"):
    d = rip["per_ruolo"][r]
    print(f"     {r}: {d['crediti']:4d} crediti = {d['pct']:5.1f}% del budget")
print(f"   non tracciato: {rip['non_tracciato']}")

print()
print("=" * 68)
print("5) LA MIA SQUADRA NON C'E' -> nessuna ripartizione")
print("=" * 68)
st = nuovo_stato()
st.apply_teams_snapshot([snap("x", "Squadra Avversaria", 1000,
                               {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, [])])
print(f"   ripartizione: {st.ripartizione_mia_squadra()} (atteso None)")

print()
print("=" * 68)
print("6) LA MIA SQUADRA VIENE RINOMINATA -> resta agganciata")
print("=" * 68)
st = nuovo_stato()
st.apply_teams_snapshot([snap("u9", "NapoLanza", 1000,
                               {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, [])])
st.apply_teams_snapshot([snap("u9", "NapoLanza Reloaded", 900,
                               {"P": 0, "D": 0, "C": 0, "A": 1, "TOT": 1},
                               [{"nome": "Kean", "squadra": "Fiorentina", "ruolo": "A"}])])
rip = st.ripartizione_mia_squadra()
print(f"   trovata come: {rip['nome_squadra'] if rip else None} "
      f"(agganciata dal nome precedente)")


print()
print("=" * 68)
print("7) GIOCATORE TOLTO DALLA MIA ROSA (assegnazione sbagliata)")
print("=" * 68)
st = nuovo_stato()
st.apply_teams_snapshot([snap("u1", "NapoLanza", 1000,
                               {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, [])])
st.apply_teams_snapshot([snap("u1", "NapoLanza", 800,
                               {"P": 0, "D": 0, "C": 0, "A": 1, "TOT": 1},
                               [{"nome": "Kean", "squadra": "Fiorentina", "ruolo": "A"}])])
r = st.ripartizione_mia_squadra()
print(f"   dopo l'acquisto: A = {r['per_ruolo']['A']['pct']}% "
      f"({r['per_ruolo']['A']['crediti']} cr), rosa {r['n_giocatori']}")

# il giocatore viene tolto e il budget ripristinato
ev = st.apply_teams_snapshot([snap("u1", "NapoLanza", 1000,
                                    {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, [])])
r = st.ripartizione_mia_squadra()
print(f"   dopo la rimozione: A = {r['per_ruolo']['A']['pct']}% "
      f"({r['per_ruolo']['A']['crediti']} cr), rosa {r['n_giocatori']}")
print(f"   eventi: {[e.get('tipo') for e in ev]}")

# riassegnato a un'altra squadra a prezzo corretto
st.apply_teams_snapshot([snap("u2", "Squadra Avversaria", 1000,
                               {"P": 0, "D": 0, "C": 0, "A": 0, "TOT": 0}, [])])
st.apply_teams_snapshot([snap("u2", "Squadra Avversaria", 850,
                               {"P": 0, "D": 0, "C": 0, "A": 1, "TOT": 1},
                               [{"nome": "Kean", "squadra": "Fiorentina", "ruolo": "A"}])])
r = st.ripartizione_mia_squadra()
print(f"   dopo riassegnazione alla Squadra Avversaria: mia A = {r['per_ruolo']['A']['pct']}% "
      f"(atteso 0.0)")
