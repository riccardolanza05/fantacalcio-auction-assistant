"""
Ricerca di profili di riferimento nell'asta della stagione precedente.

A cosa serve
------------
Se il Parma ha cambiato portiere titolare, quando viene astato il nuovo
arrivato lo storico non ha nulla da dire — e si perde l'informazione che
conta davvero: QUANTO COSTA QUELLO SLOT nella tua lega.

Viene usato SOLO quando il giocatore non e' presente nello storico: se c'e'
il prezzo reale, quello vince sempre.

Le due proposte
---------------
1) STESSO RUOLO + STESSA SQUADRA
   Chi occupava quel posto in quella squadra l'anno scorso. E' il
   riferimento migliore perche' cattura sia il livello del club sia il
   ruolo in rosa. Se in quella squadra e ruolo non fu comprato nessuno
   (tipico delle neopromosse) questa posizione resta vuota.

2) STESSO RUOLO + SQUADRA DIVERSA, quotazione e FVM simili
   Serve soprattutto quando la prima posizione e' vuota: cerca in tutta la
   lega chi, nello stesso ruolo, partiva da una valutazione di mercato
   paragonabile, e mostra quanto e' stato pagato. Il ruolo resta un filtro
   obbligatorio: un portiere non si confronta mai con un attaccante.

Quando la prima posizione e' vuota, la seconda ne propone due invece di
una, per dare comunque un intervallo di prezzo.
"""
import math
import os

import openpyxl

from common import team_to_abbr

# Ordinamento dei candidati della STESSA squadra: conta come giocavano
PESO_TITOLARITA = 0.60
PESO_FVM = 0.40

# Ordinamento dei candidati di ALTRA squadra: conta quanto valevano.
# La titolarita' entra solo con peso basso, come discriminante a parita'
# di valutazione, perche' il criterio richiesto e' la somiglianza di
# quotazione e FVM.
PESO_ALT_FVM = 0.45
PESO_ALT_QUOTAZIONE = 0.40
PESO_ALT_TITOLARITA = 0.15


def _somiglianza_fvm(a, b) -> float | None:
    """1.0 se identici, decresce col rapporto (non con la differenza assoluta:
    10 vs 20 e' una differenza enorme, 200 vs 210 no)."""
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if a <= 0 or b <= 0:
        return None
    return math.exp(-abs(math.log(a / b)))


def _somiglianza_titolarita(a, b) -> float | None:
    if a is None or b is None:
        return None
    return max(0.0, 1.0 - abs(float(a) - float(b)) / 100.0)


class ProfiliSimili:
    def __init__(self, path_storico_arricchito: str):
        self.righe: list[dict] = []
        self.disponibile = False
        if not os.path.exists(path_storico_arricchito):
            return
        wb = openpyxl.load_workbook(path_storico_arricchito, data_only=True)
        ws = wb["asta_2025_26"]
        header = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        for row in ws.iter_rows(min_row=2, values_only=True):
            d = dict(zip(header, row))
            if not d.get("Nome"):
                continue
            self.righe.append(d)
        self.disponibile = bool(self.righe)

    def _punteggio_stessa_squadra(self, r, fvm, pct_titolarita):
        componenti, pesi, spiegazioni = [], [], []
        s_tit = _somiglianza_titolarita(pct_titolarita, r.get("TitolaritaPct"))
        if s_tit is not None:
            componenti.append(s_tit); pesi.append(PESO_TITOLARITA)
            if s_tit > 0.85:
                spiegazioni.append("titolarita' simile")
        s_fvm = _somiglianza_fvm(fvm, r.get("FVM"))
        if s_fvm is not None:
            componenti.append(s_fvm); pesi.append(PESO_FVM)
            if s_fvm > 0.8:
                spiegazioni.append("quotazione simile")
        punteggio = (sum(c * p for c, p in zip(componenti, pesi)) / sum(pesi)
                      if pesi else 0.0)
        return punteggio, spiegazioni

    def _punteggio_altra_squadra(self, r, fvm, quotazione, pct_titolarita):
        componenti, pesi, spiegazioni = [], [], []
        s_fvm = _somiglianza_fvm(fvm, r.get("FVM"))
        if s_fvm is not None:
            componenti.append(s_fvm); pesi.append(PESO_ALT_FVM)
            if s_fvm > 0.8:
                spiegazioni.append("FVM simile")
        s_qta = _somiglianza_fvm(quotazione, r.get("QtA"))
        if s_qta is not None:
            componenti.append(s_qta); pesi.append(PESO_ALT_QUOTAZIONE)
            if s_qta > 0.85:
                spiegazioni.append("quotazione simile")
        s_tit = _somiglianza_titolarita(pct_titolarita, r.get("TitolaritaPct"))
        if s_tit is not None:
            componenti.append(s_tit); pesi.append(PESO_ALT_TITOLARITA)
        if not pesi:
            return None, []
        return sum(c * p for c, p in zip(componenti, pesi)) / sum(pesi), spiegazioni

    @staticmethod
    def _formatta(r, punteggio, spiegazioni, stessa_squadra):
        return {
            "nome": r["Nome"],
            "squadra": r.get("Squadra") or r.get("SquadraAbbr"),
            "ruolo": r.get("Ruolo"),
            "costo": r.get("Costo"),
            "fvm": r.get("FVM"),
            "quotazione": r.get("QtA"),
            "titolarita_pct": r.get("TitolaritaPct"),
            "presenze": r.get("Presenze"),
            "squadra_fantacalcio": r.get("SquadraFantacalcio"),
            "somiglianza": round(punteggio, 3),
            "stessa_squadra": stessa_squadra,
            "perche": spiegazioni,
        }

    def cerca(self, ruolo: str, squadra: str = "", fvm=None,
              pct_titolarita=None, quotazione=None, n: int = 2) -> list[dict]:
        """Fino a n riferimenti dall'asta scorsa.

        Primo: stesso ruolo E stessa squadra.
        Secondo: stesso ruolo, squadra diversa, quotazione/FVM simili.
        Se il primo non esiste, il secondo criterio ne propone due.
        """
        if not self.disponibile or not ruolo:
            return []
        abbr = team_to_abbr(squadra) if squadra else ""

        stessa, altre = [], []
        for r in self.righe:
            if r.get("Ruolo") != ruolo:      # il ruolo e' sempre obbligatorio
                continue
            if abbr and r.get("SquadraAbbr") == abbr:
                p, sp = self._punteggio_stessa_squadra(r, fvm, pct_titolarita)
                stessa.append((p, sp, r))
            else:
                p, sp = self._punteggio_altra_squadra(r, fvm, quotazione, pct_titolarita)
                if p is not None:
                    altre.append((p, sp, r))

        stessa.sort(key=lambda x: -x[0])
        altre.sort(key=lambda x: -x[0])

        risultati = []
        if stessa:
            p, sp, r = stessa[0]
            risultati.append(self._formatta(r, p, sp, True))

        # se manca il riferimento di squadra, ne mostriamo due "per valore"
        quanti_altri = n - len(risultati) if risultati else min(n, 2)
        for p, sp, r in altre[:max(0, quanti_altri)]:
            risultati.append(self._formatta(r, p, sp, False))

        return risultati[:n]


if __name__ == "__main__":
    HERE = os.path.dirname(os.path.abspath(__file__))
    ps = ProfiliSimili(os.path.join(HERE, "storico_asta_2025_26.xlsx"))
    print(f"Profili storici caricati: {len(ps.righe)}\n")

    prove = [
        ("Nuovo portiere titolare del Parma",  "P", "Parma",     12, 85, 12),
        ("Portiere del Pisa",                   "P", "Pisa",      10, 80, 11),
        ("Portiere della Cremonese (neopr.)",   "P", "Cremonese", 10, 80, 11),
        ("Attaccante top della Cremonese",      "A", "Cremonese", 90, 85, 20),
        ("Difensore titolare dell'Inter",       "D", "Inter",     40, 85, 15),
    ]
    for etichetta, ruolo, squadra, fvm, tit, qt in prove:
        print(f"{etichetta}  (ruolo {ruolo}, FVM {fvm}, quotazione {qt}, tit {tit}%)")
        ris = ps.cerca(ruolo, squadra, fvm=fvm, pct_titolarita=tit, quotazione=qt)
        if not ris:
            print("   nessun riferimento\n"); continue
        for x in ris:
            tag = "STESSA SQUADRA" if x["stessa_squadra"] else "altra squadra"
            perche = ", ".join(x["perche"]) or "stesso ruolo"
            print(f"   [{tag:14s}] {x['nome']:16s} {str(x['squadra'])[:11]:11s} "
                  f"FVM {str(x['fvm']):>4s} Qt {str(x['quotazione']):>3s} "
                  f"tit {x['titolarita_pct']:>5}% -> {x['costo']:>3} cr  [{perche}]")
        print()
