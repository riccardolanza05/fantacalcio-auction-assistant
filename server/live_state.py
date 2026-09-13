"""
Stato live dell'asta.

Due punti delicati risolti qui.

IDENTITA' DELLE SQUADRE
-----------------------
Il nome della rosa puo' cambiare durante l'asta ("Squadra Provvisoria" -> "Leonardo")
e l'ordine delle card puo' essere rimescolato. Usare il nome come chiave
creava una squadra doppia ad ogni rinomina, di cui solo una aggiornata.
L'identita' viene quindi risolta in tre passi:

  1. UID stabile: ogni rosa nel DOM ha un viewport con id univoco
     (roster-viewport-<uuid>), che non cambia ne' con la rinomina ne' col
     riordino. E' la chiave principale.
  2. Sovrapposizione della rosa: se l'UID non e' mai stato visto (succede
     se la pagina viene ricaricata e Angular rigenera gli id) ma i
     giocatori coincidono in larga parte con una squadra gia' nota, e' la
     stessa squadra.
  3. Nome: ultimo tentativo, per le squadre ancora senza giocatori.

RIPARTIZIONE DEL BUDGET DELLA PROPRIA SQUADRA
---------------------------------------------
Viene calcolata solo se tra le rose ne esiste una col nome configurato
(MIA_SQUADRA). Se non c'e', non viene esposto nulla: meglio niente che una
ripartizione riferita alla squadra sbagliata.
"""
import os
import time
from dataclasses import dataclass, field

from common import normalize_name
from player_db import PlayerDB

# Nome della tua squadra in lega, cosi' come compare nella pagina d'asta.
# Sovrascrivibile con la variabile d'ambiente MIA_SQUADRA senza toccare il
# codice (comodo se cloni il repo per un'altra lega).
MIA_SQUADRA = os.environ.get("MIA_SQUADRA", "NapoLanza")
BUDGET_INIZIALE = 1000
# quota minima di giocatori in comune per considerare due rose la stessa
# squadra quando l'UID non aiuta
SOGLIA_SOVRAPPOSIZIONE = 0.6


@dataclass
class TeamState:
    nome_squadra: str
    uid: str | None = None
    budget: float | None = None
    max_offerta: float | None = None
    counts: dict = field(default_factory=dict)
    # La rosa viene RICOSTRUITA da ogni snapshot, non accumulata: se un
    # giocatore viene tolto dalla rosa (assegnazione sbagliata, prezzo
    # errato) deve sparire anche dal calcolo della ripartizione.
    rosa: list = field(default_factory=list)        # {chiave, nome, ruolo, costo}
    rosa_keys: set = field(default_factory=set)
    costi_noti: dict = field(default_factory=dict)  # chiave -> costo dedotto
    nomi_precedenti: list = field(default_factory=list)

    def spesa_per_ruolo(self) -> dict:
        """Solo sui giocatori ATTUALMENTE in rosa."""
        out = {"P": 0, "D": 0, "C": 0, "A": 0}
        for p in self.rosa:
            r, c = p.get("ruolo"), p.get("costo")
            if r in out and c:
                out[r] += c
        return out

    def spesa_tracciata(self) -> int:
        return sum(p.get("costo") or 0 for p in self.rosa)


class LiveAuctionState:
    def __init__(self, player_db: PlayerDB, vorp_live=None, storico=None,
                  simili=None, mia_squadra: str = MIA_SQUADRA):
        self.db = player_db
        self.vorp = vorp_live
        self.storico = storico
        self.simili = simili
        self.mia_squadra = mia_squadra
        self.teams: dict[str, TeamState] = {}   # chiave interna stabile
        self.current_player: dict | None = None
        self.assignment_log: list[dict] = []
        self.last_update_ts: float = 0.0

    # ------------------------------------------------------------------
    # giocatore in asta
    # ------------------------------------------------------------------
    def set_current_player(self, nome: str, squadra: str, ruolo: str,
                            fvm_live=None, player_id=None, nome_lista=None):
        rec, metodo = None, None
        if player_id is not None:
            rec = self.db.lookup_by_id(player_id)
            if rec:
                metodo = "id"
        if rec is None and nome_lista:
            rec = self.db.lookup(nome_lista, squadra)
            if rec:
                metodo = "nome_lista"
        if rec is None and nome:
            rec = self.db.lookup(nome, squadra)
            if rec:
                metodo = "nome_esteso"

        cp = {
            "nome": nome, "squadra": squadra, "ruolo": ruolo,
            "fvm_live": fvm_live, "player_id": player_id,
            "in_modello": rec is not None, "metodo_match": metodo,
        }

        if rec:
            cp.update({
                "nome": rec["nome"],
                "squadra": rec["squadra"],
                "ruolo": rec["ruolo"],
                "fascia": rec["fascia"],
                "fvm_mercato": rec["fvm_mercato"],
                "quotazione": rec["qti"],
                "pct_titolarita": rec["pct_titolarita"],
                "presenze_2025_26": rec["presenze_2025_26"],
                "fm_media_2025_26": rec["fm_media_2025_26"],
                "gol_2025_26": rec["gol_2025_26"],
                "assist_2025_26": rec["assist_2025_26"],
                "gol_subiti_2025_26": rec.get("gol_subiti_2025_26"),
                "clean_sheet_2025_26": rec.get("clean_sheet_2025_26"),
                "rigori_parati_2025_26": rec.get("rigori_parati_2025_26"),
                "prezzo_mercato": rec.get("prezzo_mercato"),
                "scarto_pct": rec.get("scarto_pct"),
                "verdetto": rec.get("verdetto"),
                "rif_verdetto": rec.get("rif_verdetto"),
                "infortunato": rec["infortunato"],
                "nota_infortunio": rec.get("nota_infortunio"),
                "p10": rec["p10"], "p90": rec["p90"],
            })
            if self.vorp is not None:
                cp.update(self.vorp.prezzo_consigliato(rec))
            else:
                cp["prezzo_modello"] = rec["prezzo_modello"]
                cp["prezzo_consigliato"] = rec["prezzo_modello"]

        # prezzo pagato nelle aste passate, cercato sempre (anche fuori pool)
        if self.storico is not None:
            cp["storico_asta"] = self.storico.get(
                player_id=(rec["id"] if rec else None),
                nome=(rec["nome"] if rec else nome),
                squadra=(rec["squadra"] if rec else squadra))
            if cp["storico_asta"] is None and nome:
                cp["storico_asta"] = self.storico.get(nome=nome, squadra=squadra)

        # riferimenti per analogia solo se manca il prezzo reale
        if self.simili is not None and cp.get("storico_asta") is None:
            trovati = self.simili.cerca(
                ruolo=(rec or {}).get("ruolo") or ruolo,
                squadra=(rec or {}).get("squadra") or squadra,
                fvm=(rec or {}).get("fvm_mercato") or fvm_live,
                pct_titolarita=(rec or {}).get("pct_titolarita"),
                quotazione=(rec or {}).get("qti"), n=2)
            if trovati:
                cp["profili_simili"] = trovati

        self.current_player = cp
        self.last_update_ts = time.time()
        return cp

    # ------------------------------------------------------------------
    # identita' delle squadre
    # ------------------------------------------------------------------
    def _risolvi_squadra(self, uid, nome_squadra, rosa_payload) -> TeamState:
        # 1) UID stabile
        if uid:
            for t in self.teams.values():
                if t.uid and t.uid == uid:
                    return t

        chiavi_nuove = {(normalize_name(p.get("nome", "")), p.get("squadra", ""))
                        for p in (rosa_payload or []) if p.get("nome")}

        # 2) sovrapposizione della rosa (pagina ricaricata, UID rigenerati)
        if chiavi_nuove:
            migliore, punteggio_migliore = None, 0.0
            for t in self.teams.values():
                if not t.rosa_keys:
                    continue
                comuni = len(chiavi_nuove & t.rosa_keys)
                punteggio = comuni / max(1, min(len(chiavi_nuove), len(t.rosa_keys)))
                if punteggio > punteggio_migliore:
                    migliore, punteggio_migliore = t, punteggio
            if migliore is not None and punteggio_migliore >= SOGLIA_SOVRAPPOSIZIONE:
                return migliore

        # 3) nome (squadre ancora vuote)
        for t in self.teams.values():
            if t.nome_squadra == nome_squadra:
                return t

        chiave = uid or f"nome:{nome_squadra}"
        nuova = TeamState(nome_squadra=nome_squadra, uid=uid)
        self.teams[chiave] = nuova
        return nuova

    # ------------------------------------------------------------------
    def apply_teams_snapshot(self, teams_payload: list[dict]) -> list[dict]:
        eventi = []
        for t in teams_payload:
            nome_sq = t.get("nome_squadra")
            if not nome_sq:
                continue
            uid = t.get("uid")
            rosa_payload = t.get("rosa") or []
            team = self._risolvi_squadra(uid, nome_sq, rosa_payload)
            prima_volta = team.budget is None and not team.counts

            if team.nome_squadra != nome_sq:
                team.nomi_precedenti.append(team.nome_squadra)
                team.nome_squadra = nome_sq
            if uid and not team.uid:
                team.uid = uid

            counts_new = t.get("counts") or {}
            counts_old = team.counts
            budget_prima, budget_dopo = team.budget, t.get("budget")
            tot_old, tot_new = counts_old.get("TOT"), counts_new.get("TOT")

            chiavi_ora = []
            per_chiave = {}
            for p in rosa_payload:
                if not p.get("nome"):
                    continue
                k = (normalize_name(p["nome"]), p.get("squadra", ""))
                chiavi_ora.append(k)
                per_chiave[k] = p
            insieme_ora = set(chiavi_ora)

            nuovi = [per_chiave[k] for k in chiavi_ora if k not in team.rosa_keys]
            rimossi = [k for k in team.rosa_keys if k not in insieme_ora]

            team.counts = counts_new or counts_old
            if budget_dopo is not None:
                team.budget = budget_dopo
            if t.get("max_offerta") is not None:
                team.max_offerta = t.get("max_offerta")

            # --- rimozioni: un giocatore tolto dalla rosa torna disponibile
            #     e il suo costo esce dalla ripartizione ---
            for k in rimossi:
                team.rosa_keys.discard(k)
                team.costi_noti.pop(k, None)
                rec = self.db.lookup(k[0], k[1])
                if rec and self.vorp is not None:
                    self.vorp.libera(rec["id"])
                eventi.append({
                    "tipo": "rimozione",
                    "squadra_fantacalcio": team.nome_squadra,
                    "nome": (rec or {}).get("nome") or k[0],
                    "ts": time.time(),
                })

            # --- costo dei nuovi arrivi, dal calo di budget ---
            delta_tot = (tot_new - tot_old) if (tot_old is not None and tot_new is not None) else None
            n_acquisti = delta_tot if delta_tot is not None else len(nuovi)
            costo_singolo = None
            if (budget_prima is not None and budget_dopo is not None
                    and len(nuovi) == 1 and not rimossi):
                d = budget_prima - budget_dopo
                if d > 0:
                    costo_singolo = d

            for p in nuovi:
                k = (normalize_name(p["nome"]), p.get("squadra", ""))
                team.rosa_keys.add(k)
                if costo_singolo is not None:
                    team.costi_noti[k] = costo_singolo

            # --- rosa corrente ricostruita dallo snapshot ---
            team.rosa = []
            for k in chiavi_ora:
                p = per_chiave[k]
                rec = self.db.lookup(p["nome"], p.get("squadra", ""))
                if rec and self.vorp is not None:
                    self.vorp.segna_preso(rec["id"])
                team.rosa.append({
                    "chiave": k,
                    "nome": (rec or {}).get("nome") or p["nome"],
                    "ruolo": (rec or {}).get("ruolo") or p.get("ruolo"),
                    "costo": team.costi_noti.get(k),
                })

            if prima_volta or not nuovi:
                continue

            for p in nuovi:
                eventi.append(self._registra(
                    team, p.get("nome"), p.get("squadra"), p.get("ruolo"),
                    costo_singolo, tot_new, "rosa"))

        self.last_update_ts = time.time()
        return eventi

    def _registra(self, team, nome, squadra_reale, ruolo, costo, tot, fonte,
                   player_id=None):
        rec = self.db.lookup_by_id(player_id) if player_id is not None else None
        if rec is None and nome:
            rec = self.db.lookup(nome, squadra_reale or "")

        ruolo_eff = (rec or {}).get("ruolo") or ruolo
        if rec and self.vorp is not None:
            self.vorp.segna_preso(rec["id"])
            if costo:
                self.vorp.osserva_prezzo(rec["ruolo"], costo, rec["prezzo_modello"])

        evento = {
            "tipo": "acquisto",
            "squadra_fantacalcio": team.nome_squadra,
            "nome": (rec or {}).get("nome") or nome or "sconosciuto",
            "squadra_reale": (rec or {}).get("squadra") or squadra_reale,
            "ruolo": ruolo_eff,
            "costo": costo,
            "prezzo_modello": (rec or {}).get("prezzo_modello"),
            "fonte": fonte,
            "in_modello": rec is not None,
            "n_giocatori_squadra": tot,
            "ts": time.time(),
        }
        self.assignment_log.append(evento)
        return evento

    # ------------------------------------------------------------------
    def _trova_mia_squadra(self) -> TeamState | None:
        """Cerca la propria rosa tra quelle viste, anche sotto un nome
        precedente (se e' stata rinominata dopo che l'avevamo agganciata)."""
        obiettivo = normalize_name(self.mia_squadra)
        for t in self.teams.values():
            if normalize_name(t.nome_squadra) == obiettivo:
                return t
            if any(normalize_name(n) == obiettivo for n in t.nomi_precedenti):
                return t
        return None

    def ripartizione_mia_squadra(self) -> dict | None:
        """Percentuale del budget iniziale spesa per reparto.
        Ritorna None se la propria squadra non e' tra quelle lette: meglio
        nulla che una ripartizione riferita alla squadra sbagliata."""
        team = self._trova_mia_squadra()
        if team is None:
            return None

        # tutto calcolato sulla ROSA ATTUALE letta dal sito: se un giocatore
        # viene tolto, i suoi crediti spariscono da qui al giro successivo
        spesa = team.spesa_per_ruolo()
        tracciata = team.spesa_tracciata()
        speso_reale = (BUDGET_INIZIALE - team.budget) if team.budget is not None else None
        # acquisti avvenuti prima che il server fosse avviato, o con costo non
        # deducibile: li teniamo separati invece di spalmarli a caso
        non_tracciato = None
        if speso_reale is not None:
            non_tracciato = max(0, round(speso_reale - tracciata))

        return {
            "nome_squadra": team.nome_squadra,
            "budget_residuo": team.budget,
            "max_offerta": team.max_offerta,
            "speso_totale": speso_reale,
            "per_ruolo": {r: {"crediti": spesa[r],
                               "pct": round(100.0 * spesa[r] / BUDGET_INIZIALE, 1)}
                           for r in ("P", "D", "C", "A")},
            "non_tracciato": non_tracciato,
            "counts": team.counts,
            "n_giocatori": len(team.rosa),
            "rosa": [{"nome": p["nome"], "ruolo": p["ruolo"], "costo": p["costo"]}
                      for p in team.rosa],
        }

    def teams_summary(self) -> list[dict]:
        return [{"nome_squadra": t.nome_squadra, "budget": t.budget,
                 "max_offerta": t.max_offerta,
                 "n_giocatori": (t.counts or {}).get("TOT", len(t.rosa)),
                 "counts": t.counts,
                 "mia": normalize_name(t.nome_squadra) == normalize_name(self.mia_squadra)}
                for t in sorted(self.teams.values(), key=lambda x: -(x.max_offerta or 0))]

    def full_state(self) -> dict:
        return {
            "current_player": self.current_player,
            "teams": self.teams_summary(),
            "mia_squadra": self.ripartizione_mia_squadra(),
            "ultima_assegnazione": self.assignment_log[-1] if self.assignment_log else None,
            "n_assegnazioni_totali": len(self.assignment_log),
            "last_update_ts": self.last_update_ts,
        }
