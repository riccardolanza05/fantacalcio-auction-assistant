"""
STRATO 4 del modello di prezzo — correzione VORP/scarsita', da applicare
durante l'asta.

Sostituisce il vecchio tracker Bayesiano NIG, che agiva su un fair value
VORP puro e produceva correzioni enormi (moltiplicatori 6-10x sui giocatori
di coda). Qui l'ancora e' il `prezzo_modello`, gia' calibrato su FVM e
quote di reparto, e la correzione e' deliberatamente debole e limitata:

  - stesso tetto per ruolo dello strato 3 (P 6, D 12, C 20, A 30 crediti),
    e comunque mai oltre il 30% del prezzo base;
  - scalata dalla SCARSITA': finche' molti giocatori equivalenti sono
    ancora disponibili la correzione tende a zero, perche' non ha senso
    pagare un premio per qualcosa che si puo' ancora ottenere altrove;
  - satura dolcemente (tanh), cosi' un vantaggio enorme non produce una
    correzione enorme.

Il livello di rimpiazzo viene ricalcolato ad ogni acquisto: e' questo che
rende la correzione viva. A inizio asta il rimpiazzo di un attaccante e'
il 72esimo miglior attaccante; se ne vengono presi 60, diventa molto piu'
scarso e il vantaggio dei rimanenti cresce.

In piu' viene stimata una DERIVA DI MERCATO per ruolo: se la lega sta
pagando sistematicamente sopra il modello, il rapporto medio osservato
sposta le stime. Anche questa e' limitata (+-30%) e smorzata quando le
osservazioni sono poche, per non inseguire il rumore dei primi acquisti.
"""
import math

import numpy as np

# Squadre in lega: determina quanti slot da titolare esistono per ruolo, e
# quindi dove cade il livello di rimpiazzo. Va tenuto allineato a NSQ in
# modello_prezzo.py.
NSQ = 10
SLOT_TITOLARI = {"P": 3 * NSQ, "D": 8 * NSQ, "C": 8 * NSQ, "A": 6 * NSQ}
TETTO_CORREZIONE = {"P": 6, "D": 12, "C": 20, "A": 30}
TETTO_RELATIVO = 0.30

# Ordine di qualita' delle fasce: 0 = migliore.
ORDINE_FASCE = {"top": 0, "semitop": 1, "terza": 2, "quarta": 3, "minori": 4}
FASCE_ALTE = ("top", "semitop", "terza")

# Pesi della scarsita': quanto conta la COMPOSIZIONE di cio' che resta
# rispetto alla semplice quantita' consumata.
PESO_COMPOSIZIONE = 0.75
PESO_DEPLEZIONE = 0.25

# Deriva di mercato: quanto la lega paga sopra/sotto il modello.
DERIVA_MAX = 0.30
DERIVA_SMORZAMENTO = 5.0


class VorpLive:
    def __init__(self, giocatori: list[dict]):
        self.per_ruolo: dict[str, list[dict]] = {}
        for g in giocatori:
            if g.get("produzione_attesa") is None:
                continue
            self.per_ruolo.setdefault(g["ruolo"], []).append(g)
        for ruolo in self.per_ruolo:
            self.per_ruolo[ruolo].sort(key=lambda x: -x["produzione_attesa"])

        self.presi: set[int] = set()
        self.osservazioni: dict[str, list[float]] = {}
        # composizione iniziale del reparto, riferimento per la scarsita'
        self._iniziale = {r: self._conteggi(r, iniziale=True)
                          for r in self.per_ruolo}

    # ------------------------------------------------------------------
    def segna_preso(self, player_id):
        if player_id is not None:
            self.presi.add(int(player_id))

    def libera(self, player_id):
        """Un giocatore assegnato per errore e poi rimosso torna disponibile."""
        if player_id is not None:
            self.presi.discard(int(player_id))

    def osserva_prezzo(self, ruolo, prezzo_pagato, prezzo_modello):
        if not ruolo or not prezzo_pagato or not prezzo_modello:
            return
        if prezzo_pagato <= 0 or prezzo_modello <= 0:
            return
        self.osservazioni.setdefault(ruolo, []).append(
            math.log(prezzo_pagato / prezzo_modello))

    # ------------------------------------------------------------------
    def _conteggi(self, ruolo: str, iniziale: bool = False) -> dict:
        """Quanti giocatori restano per fascia, e quanti nel blocco alto."""
        out = {f: 0 for f in ORDINE_FASCE}
        for g in self.per_ruolo.get(ruolo, []):
            if not iniziale and int(g["id"]) in self.presi:
                continue
            f = g.get("fascia")
            if f in out:
                out[f] += 1
        out["_alte"] = sum(out[f] for f in FASCE_ALTE)
        return out

    def disponibili(self, ruolo: str) -> list[dict]:
        return [g for g in self.per_ruolo.get(ruolo, [])
                if int(g["id"]) not in self.presi]

    def livello_rimpiazzo(self, ruolo: str) -> float | None:
        disp = self.disponibili(ruolo)
        if not disp:
            return None
        slot_totali = SLOT_TITOLARI.get(ruolo, 0)
        presi_del_ruolo = sum(1 for g in self.per_ruolo.get(ruolo, [])
                              if int(g["id"]) in self.presi)
        slot_rimasti = max(0, slot_totali - presi_del_ruolo)
        if slot_rimasti == 0 or slot_rimasti >= len(disp):
            return disp[-1]["produzione_attesa"]
        return disp[slot_rimasti - 1]["produzione_attesa"]

    # ------------------------------------------------------------------
    def scarsita(self, ruolo: str, fascia: str) -> dict:
        """Quanto e' scarso, per QUESTO giocatore, il mercato delle
        alternative almeno equivalenti.

        Il VORP deve dire se esistono alternative valide. Contano due cose,
        e la prima pesa di piu':

        COMPOSIZIONE (peso 0.75) — che quota del blocco alto ancora libero
          e' fatta di giocatori almeno pari a lui. Se restano 10 attaccanti
          di fascia medio-alta e uno solo e' top, quel top non ha
          alternative: la sua quota e' 1/10. Se invece i top sono 5 su 10,
          di alternative ce ne sono, e il prezzo non deve salire.
          Il valore e' confrontato con la quota di INIZIO asta, altrimenti
          a mercato intatto risulterebbe gia' scarso: a inizio asta i top
          sono per costruzione una minoranza, ma non sono affatto scarsi.

        DEPLEZIONE (peso 0.25) — quanti giocatori di quel livello o
          superiore sono gia' stati presi in assoluto. Serve al caso
          "restano 5 top su 10": in proporzione ce ne sono tanti, ma il
          reparto si sta comunque svuotando e un piccolo premio e'
          giustificato.

        Le fasce basse ottengono un valore quasi nullo, perche' di
        alternative equivalenti ne restano sempre parecchie.
        """
        ora = self._conteggi(ruolo)
        inizio = self._iniziale.get(ruolo) or ora
        rango = ORDINE_FASCE.get(fascia)
        if rango is None:
            return {"scarsita": 0.0, "composizione": None, "deplezione": None,
                    "pari_o_meglio": None, "blocco_alto": ora.get("_alte", 0)}

        def pari_o_meglio(conteggi):
            return sum(conteggi[f] for f, r in ORDINE_FASCE.items() if r <= rango)

        pom_ora, pom_inizio = pari_o_meglio(ora), pari_o_meglio(inizio)

        # --- composizione, normalizzata sulla quota di inizio asta ---
        alte_ora, alte_inizio = ora.get("_alte", 0), inizio.get("_alte", 0)
        composizione = 0.0
        if fascia in FASCE_ALTE and alte_ora > 0 and alte_inizio > 0:
            quota_ora = min(pom_ora, alte_ora) / alte_ora
            quota_inizio = min(pom_inizio, alte_inizio) / alte_inizio
            if quota_inizio > 0:
                composizione = max(0.0, 1.0 - quota_ora / quota_inizio)

        # --- deplezione delle alternative di pari livello o superiore ---
        deplezione = 0.0
        if pom_inizio > 0:
            deplezione = max(0.0, 1.0 - pom_ora / pom_inizio)

        valore = PESO_COMPOSIZIONE * composizione + PESO_DEPLEZIONE * deplezione
        return {
            "scarsita": round(float(np.clip(valore, 0.0, 1.0)), 3),
            "composizione": round(composizione, 3),
            "deplezione": round(deplezione, 3),
            "pari_o_meglio": pom_ora,
            "blocco_alto": alte_ora,
        }

    def deriva(self, ruolo: str) -> float:
        """Fattore moltiplicativo che riflette quanto la lega sta pagando
        sopra il modello. Limitato e smorzato quando le osservazioni sono
        poche."""
        oss = self.osservazioni.get(ruolo, [])
        if not oss:
            return 1.0
        media = float(np.mean(oss))
        # smorzamento: con n osservazioni pesiamo n/(n+k)
        peso = len(oss) / (len(oss) + DERIVA_SMORZAMENTO)
        log_deriva = float(np.clip(media * peso,
                                    math.log(1 - DERIVA_MAX),
                                    math.log(1 + DERIVA_MAX)))
        return math.exp(log_deriva)

    # ------------------------------------------------------------------
    def correzione(self, prezzo_base: float, ruolo: str,
                    produzione_attesa: float, fascia: str) -> dict:
        """Correzione VORP live (strato 4), con i suoi due freni."""
        rimpiazzo = self.livello_rimpiazzo(ruolo)
        sc = self.scarsita(ruolo, fascia)
        if rimpiazzo is None or produzione_attesa is None:
            return {"correzione": 0.0, "vantaggio_vorp": None,
                    "rimpiazzo": None, **sc}

        vantaggio = produzione_attesa - rimpiazzo
        tetto = min(TETTO_CORREZIONE.get(ruolo, 10), prezzo_base * TETTO_RELATIVO)
        grezza = math.tanh(vantaggio / 50.0) * tetto
        corr = float(np.clip(grezza * sc["scarsita"], -tetto, tetto))
        return {"correzione": round(corr, 1),
                "vantaggio_vorp": round(vantaggio, 1),
                "rimpiazzo": round(rimpiazzo, 1), **sc}

    def prezzo_consigliato(self, giocatore: dict) -> dict:
        """Prezzo del modello + strato 4 + deriva di mercato."""
        base = giocatore.get("prezzo_modello")
        ruolo = giocatore.get("ruolo")
        if base is None or not ruolo:
            return {}
        c = self.correzione(base, ruolo, giocatore.get("produzione_attesa"),
                             giocatore.get("fascia"))
        d = self.deriva(ruolo)
        consigliato = max(1.0, (base + c["correzione"]) * d)
        return {
            "prezzo_modello": round(base, 1),
            "correzione_vorp": c["correzione"],
            "vantaggio_vorp": c["vantaggio_vorp"],
            "scarsita_reparto": c["scarsita"],
            "scarsita_composizione": c.get("composizione"),
            "scarsita_deplezione": c.get("deplezione"),
            "alternative_pari_o_meglio": c.get("pari_o_meglio"),
            "blocco_alto_disponibile": c.get("blocco_alto"),
            "deriva_mercato": round(d, 3),
            "prezzo_consigliato": round(consigliato, 1),
            "n_osservazioni_ruolo": len(self.osservazioni.get(ruolo, [])),
            "disponibili_ruolo": len(self.disponibili(ruolo)),
        }


if __name__ == "__main__":
    import os
    from player_db import PlayerDB

    HERE = os.path.dirname(os.path.abspath(__file__))
    db = PlayerDB(os.path.join(HERE, "giocatori_2026_27.xlsx"))
    tutti = list(db.by_id.values())

    def scenario(titolo, tenere: dict):
        """tenere: quanti giocatori lasciare liberi per fascia (ruolo A)."""
        vl = VorpLive(tutti)
        per_fascia = {}
        for g in vl.per_ruolo["A"]:
            per_fascia.setdefault(g.get("fascia"), []).append(g)
        for fascia, lista in per_fascia.items():
            quanti = tenere.get(fascia, 0)
            for g in lista[quanti:]:
                vl.segna_preso(g["id"])
        print(f"\n{titolo}")
        print(f"  {'fascia':9s} {'liberi':>6s} {'scars.':>7s} {'compos.':>8s} "
              f"{'deplez.':>8s} {'corr.':>7s}")
        for fascia in ("top", "semitop", "terza"):
            lista = [g for g in per_fascia.get(fascia, [])
                     if int(g["id"]) not in vl.presi]
            if not lista:
                continue
            g = lista[0]
            r = vl.prezzo_consigliato(g)
            print(f"  {fascia:9s} {len(lista):6d} {r['scarsita_reparto']:7.3f} "
                  f"{r['scarsita_composizione']:8.3f} {r['scarsita_deplezione']:8.3f} "
                  f"{r['correzione_vorp']:+7.1f}")

    print("=" * 62)
    print("SCARSITA' PER COMPOSIZIONE DEL BLOCCO ALTO (attaccanti)")
    print("=" * 62)
    scenario("A) inizio asta: nessuno preso -> nessuna correzione attesa",
             {"top": 6, "semitop": 8, "terza": 12, "quarta": 12, "minori": 99})
    scenario("B) restano 1 top, 2 semitop, 7 terza (il top non ha alternative)",
             {"top": 1, "semitop": 2, "terza": 7})
    scenario("C) restano 5 top e 5 semitop (di alternative ce ne sono ancora)",
             {"top": 5, "semitop": 5, "terza": 0})
