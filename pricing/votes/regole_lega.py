#!/usr/bin/env python3
"""
REGOLE DI PUNTEGGIO — Lega Abendosa (Classic, 12 squadre, 1000 crediti)

Tre livelli, tenuti deliberatamente separati:

  LIVELLO 1 — punteggio individuale per partita
              Separabile: dipende solo dal giocatore. Va nel modello ML.

  LIVELLO 2 — modificatore difesa
              NON separabile: dipende dalla composizione del reparto
              schierato. Non e' un attributo del giocatore, quindi non
              entra come feature: si calcola a valle, sulla rosa.

  LIVELLO 3 — conversione punti -> gol (soglia 6)
              Serve per simulare i risultati, NON per valutare i
              giocatori: per il VORP la valuta corretta sono i fantapunti.

Lanciando questo file si esegue l'autotest:  python regole_lega.py
"""

import numpy as np

# ---------------------------------------------------------------------------
# CONFIGURAZIONE
# ---------------------------------------------------------------------------

REGOLE = {
    # bonus/malus individuali
    "gol": 3.0,              # ogni gol, rigori inclusi
    "assist": 1.0,           # assist di ogni tipo
    "rigore_sbagliato": -2.0,
    "rigore_parato": 3.0,
    "autogol": -2.0,
    "ammonizione": -0.5,
    "espulsione": -1.0,
    "porta_inviolata": 1.0,  # partita senza gol subiti
    "gol_subito": -1.0,      # per ogni gol subito

    # A chi si applicano i malus/bonus di reparto.
    # ASSUNZIONE DA CONFERMARE: nel Classic standard 'gol subito' e
    # 'porta inviolata' valgono per il solo portiere. Se nella tua lega
    # valgono anche per i difensori, aggiungi "D" a queste liste.
    "ruoli_gol_subito": ("P",),
    "ruoli_porta_inviolata": ("P",),

    # modificatore difesa
    "mod_min_difensori": 4,      # si applica schierando almeno 4 difensori
    "mod_n_difensori": 3,        # calcolato sui migliori 3 a voto
    "mod_include_portiere": True,
    # (soglia_inclusa, bonus) in ordine crescente
    "mod_fasce": ((6.0, 1.0), (6.5, 3.0), (7.0, 6.0)),

    # conversione punti -> gol
    "soglia_gol": 6.0,
    "punti_primo_gol": 66.0,     # 66 punti = 1 gol, poi ogni 6

    # struttura della lega
    "n_squadre": 12,
    "budget": 1000,
    "rosa": {"P": 3, "D": 8, "C": 8, "A": 6},
    "titolari_max": {"P": 1, "D": 5, "C": 5, "A": 3},   # dai moduli concessi
    "titolari_min": {"P": 1, "D": 3, "C": 3, "A": 1},
}


# ---------------------------------------------------------------------------
# LIVELLO 1 — punteggio individuale
# ---------------------------------------------------------------------------

def punteggio_partita(voto, ruolo, gf=0, rf=0, ass=0, rs=0, rp=0,
                      au=0, amm=0, esp=0, gs=0, regole=REGOLE):
    """Fantapunti di UN giocatore in UNA partita.

    ATTENZIONE sui gol: nei file dei voti la colonna 'Gf' NON include i
    rigori, contati a parte in 'Rf'. Verificato: Statistiche.Gf = Gf + Rf
    nel 99.95% dei casi. Poiche' la regola premia i gol "di tutti i tipi",
    qui si sommano entrambi. Ignorare Rf sottostima i rigoristi di 3 punti
    per rigore.

    Ritorna None se il giocatore non ha voto (non conta come presenza).
    """
    if voto is None:
        return None

    r = regole
    p = float(voto)
    p += r["gol"] * (gf + rf)          # gol su azione + su rigore
    p += r["assist"] * ass
    p += r["rigore_sbagliato"] * rs
    p += r["rigore_parato"] * rp
    p += r["autogol"] * au
    p += r["ammonizione"] * amm
    p += r["espulsione"] * esp

    if ruolo in r["ruoli_gol_subito"]:
        p += r["gol_subito"] * gs
    if ruolo in r["ruoli_porta_inviolata"] and gs == 0:
        p += r["porta_inviolata"]

    return p


# ---------------------------------------------------------------------------
# LIVELLO 2 — modificatore difesa
# ---------------------------------------------------------------------------

def modificatore_difesa(voti_difensori, voto_portiere, regole=REGOLE):
    """Modificatore di UNA giornata.

    Si calcola sul VOTO PURO (senza bonus/malus), sui migliori 3 difensori
    a voto piu' il portiere: media dei 4 valori, poi si applica la fascia.
    Ritorna 0 se sono schierati meno di 4 difensori.
    """
    r = regole
    vd = [v for v in voti_difensori if v is not None]
    if len(vd) < r["mod_min_difensori"]:
        return 0.0
    if voto_portiere is None:
        return 0.0

    migliori = sorted(vd, reverse=True)[: r["mod_n_difensori"]]
    valori = migliori + ([voto_portiere] if r["mod_include_portiere"] else [])
    media = sum(valori) / len(valori)

    bonus = 0.0
    for soglia, b in r["mod_fasce"]:
        if media >= soglia:
            bonus = b
    return bonus


def modificatore_atteso(medie_difensori, media_portiere, sd_difensori=None,
                        sd_portiere=0.6, n_sim=100_000, regole=REGOLE, seed=0):
    """Modificatore atteso PER PARTITA, dato il reparto che possiedi.

    Non basta applicare la fascia alla media dei voti medi: la selezione
    dei "migliori 3" e' non lineare, quindi la varianza conta. Simulare e'
    l'unico modo corretto.

    Effetto contro-intuitivo che ne emerge: piu' varianza = modificatore
    piu' alto, perche' si prendono i migliori 3 e si scarta il resto.
    """
    rng = np.random.default_rng(seed)
    md = np.asarray(medie_difensori, dtype=float)
    if md.size < regole["mod_min_difensori"]:
        return 0.0
    sd = (np.full(md.size, 0.6) if sd_difensori is None
          else np.asarray(sd_difensori, dtype=float))

    v_dif = rng.normal(md, sd, size=(n_sim, md.size))
    v_por = rng.normal(media_portiere, sd_portiere, size=n_sim)

    migliori = np.sort(v_dif, axis=1)[:, -regole["mod_n_difensori"]:]
    media = (migliori.sum(axis=1) + v_por) / (regole["mod_n_difensori"] + 1)

    soglie = np.array([s for s, _ in regole["mod_fasce"]])
    bonus = np.array([b for _, b in regole["mod_fasce"]])
    idx = np.searchsorted(soglie, media, side="right") - 1
    out = np.where(idx >= 0, bonus[np.clip(idx, 0, None)], 0.0)
    return float(out.mean())


def valore_marginale_difensore(medie_reparto, media_portiere, media_nuovo,
                               sd_reparto=None, sd_nuovo=0.6,
                               n_partite=38, regole=REGOLE):
    """Punti a stagione guadagnati aggiungendo UN difensore al reparto.

    E' il valore che il VORP additivo non cattura: dipende da chi hai
    gia'. Va ricalcolato durante l'asta man mano che compri difensori.
    """
    sd_rep = ([0.6] * len(medie_reparto) if sd_reparto is None
              else list(sd_reparto))
    prima = modificatore_atteso(medie_reparto, media_portiere,
                                sd_rep, regole=regole)
    dopo = modificatore_atteso(list(medie_reparto) + [media_nuovo],
                               media_portiere, sd_rep + [sd_nuovo],
                               regole=regole)
    return (dopo - prima) * n_partite


# ---------------------------------------------------------------------------
# LIVELLO 3 — punti -> gol
# ---------------------------------------------------------------------------

def punti_a_gol(punti_totali, regole=REGOLE):
    """Gol segnati dalla formazione, data la somma dei fantapunti."""
    r = regole
    if punti_totali < r["punti_primo_gol"]:
        return 0
    return int(1 + (punti_totali - r["punti_primo_gol"]) // r["soglia_gol"])


# ---------------------------------------------------------------------------
# AUTOTEST
# ---------------------------------------------------------------------------

def _autotest():
    ok = 0
    fail = 0

    def check(nome, atteso, ottenuto, tol=1e-9):
        nonlocal ok, fail
        if abs(atteso - ottenuto) < tol:
            print(f"  OK   {nome}: {ottenuto}")
            ok += 1
        else:
            print(f"  FAIL {nome}: atteso {atteso}, ottenuto {ottenuto}")
            fail += 1

    print("LIVELLO 1 — punteggio individuale")
    # attaccante: voto 6.5, 1 gol su azione, 1 su rigore, 1 assist, 1 amm
    check("attaccante 6.5 + 2 gol + assist - amm",
          6.5 + 3 + 3 + 1 - 0.5,
          punteggio_partita(6.5, "A", gf=1, rf=1, ass=1, amm=1))
    # portiere clean sheet
    check("portiere 6.0, 0 gol subiti (porta inviolata)",
          6.0 + 1.0, punteggio_partita(6.0, "P", gs=0))
    # portiere 2 gol subiti, 1 rigore parato
    check("portiere 6.0, 2 gol subiti, 1 rig. parato",
          6.0 - 2 + 3, punteggio_partita(6.0, "P", gs=2, rp=1))
    # difensore: non prende malus gol subiti (assunzione)
    check("difensore 6.0 con gs=2 (malus non applicato)",
          6.0, punteggio_partita(6.0, "D", gs=2))
    # rigore sbagliato
    check("rigore sbagliato",
          6.0 - 2, punteggio_partita(6.0, "A", rs=1))
    # senza voto
    print(f"  OK   senza voto -> {punteggio_partita(None, 'C')}")

    print("\nLIVELLO 2 — modificatore, fasce")
    check("media 5.9 -> 0", 0.0, modificatore_difesa([5.9, 5.9, 5.9, 5.9], 5.9))
    check("media 5.99 -> 0", 0.0, modificatore_difesa([6.0, 6.0, 6.0, 6.0], 5.96))
    check("media 6.0  -> +1", 1.0, modificatore_difesa([6.0, 6.0, 6.0, 5.0], 6.0))
    check("media 6.5  -> +3", 3.0, modificatore_difesa([6.5, 6.5, 6.5, 5.0], 6.5))
    check("media 7.0  -> +6", 6.0, modificatore_difesa([7.0, 7.0, 7.0, 5.0], 7.0))
    check("solo 3 difensori -> 0", 0.0, modificatore_difesa([7.0, 7.0, 7.0], 7.0))
    # verifica che prenda i MIGLIORI 3 e non tutti
    check("migliori 3 di 5 (scarta i due peggiori)", 3.0,
          modificatore_difesa([6.5, 6.5, 6.5, 4.0, 4.0], 6.5))

    print("\nLIVELLO 3 — punti -> gol")
    check("65 punti -> 0 gol", 0, punti_a_gol(65))
    check("66 punti -> 1 gol", 1, punti_a_gol(66))
    check("72 punti -> 2 gol", 2, punti_a_gol(72))

    print("\nMODIFICATORE ATTESO (simulazione)")
    for nome, md, mp in [
        ("reparto medio", [6.1, 6.0, 6.0, 5.9], 6.0),
        ("reparto buono", [6.3, 6.2, 6.1, 6.0], 6.2),
    ]:
        m = modificatore_atteso(md, mp)
        print(f"  {nome}: {m:+.2f}/partita  ({m*38:+.0f} punti/stagione)")

    print("\nVALORE MARGINALE 5° difensore (reparto buono, nuovo a 6.1)")
    vm = valore_marginale_difensore([6.3, 6.2, 6.1, 6.0], 6.2, 6.1)
    print(f"  {vm:+.1f} punti/stagione")

    print(f"\n=== {ok} test superati, {fail} falliti ===")
    return fail == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _autotest() else 1)
