"""
Prezzi d'asta delle stagioni precedenti (file Rose_lega-*.xlsx).

IMPORTANTE — perche' l'indice NON passa dal pool 2026-27:
la prima versione agganciava i prezzi storici all'id del giocatore nel pool
del modello. Risultato: chi era all'asta l'anno scorso ma non compare nelle
Quotazioni 2026-27 (perche' ceduto, o perche' la lista non e' ancora
aggiornata) non poteva MAI mostrare il proprio prezzo e veniva segnalato
come "non presente", pur essendo nel file. Ora l'indice e' costruito
direttamente sui nomi del file d'asta, indipendentemente dal pool.

Chiavi di ricerca, dalla piu' precisa alla piu' larga:
  1. id del pool (se il giocatore e' anche nel modello)
  2. nome normalizzato + sigla squadra
  3. cognome + sigla squadra   (gestisce "Moise Kean" -> "Kean")
  4. cognome da solo, se non ambiguo (giocatore che ha cambiato squadra)
"""
import os
import statistics

from common import normalize_name, team_to_abbr
from parse_rose_lega import parse_rose_lega


def _cognome(nome: str) -> str:
    """'Martinez L.' -> 'martinez';  'Moise Kean' -> 'kean';  'Kean' -> 'kean'"""
    n = normalize_name(nome)
    parts = n.split()
    if not parts:
        return ""
    if len(parts) >= 2 and len(parts[-1]) <= 2:
        return " ".join(parts[:-1])      # forma dei file: cognome + iniziale
    if len(parts) >= 2:
        return parts[-1]                  # forma estesa della card d'asta
    return parts[0]


class StoricoPrezzi:
    def __init__(self, player_db, percorsi: list[str]):
        self.per_id: dict[int, dict] = {}
        self.per_nome_squadra: dict[str, dict] = {}
        self.per_cognome_squadra: dict[str, dict] = {}
        self.per_cognome: dict[str, list[dict]] = {}
        self.n_file = 0
        self.n_record = 0
        self.n_con_id = 0
        for path in percorsi:
            if os.path.exists(path):
                self._carica(player_db, path)
                self.n_file += 1

    @staticmethod
    def _voce(contenitore, chiave):
        return contenitore.setdefault(chiave, {"prezzi": [], "dettaglio": [], "nome": None})

    def _carica(self, player_db, path: str):
        etichetta = os.path.splitext(os.path.basename(path))[0]
        for r in parse_rose_lega(path):
            self.n_record += 1
            nome, squadra = r["calciatore"], r["squadra_reale"]
            abbr = team_to_abbr(squadra)
            osservazione = {
                "costo": r["costo"],
                "squadra_fantacalcio": r["squadra_fantacalcio"],
                "squadra_reale": squadra,
                "fonte": etichetta,
            }

            chiavi = [
                (self.per_nome_squadra, f"{normalize_name(nome)}|{abbr}"),
                (self.per_cognome_squadra, f"{_cognome(nome)}|{abbr}"),
            ]
            # l'id si aggiunge solo se il giocatore e' anche nel pool attuale,
            # ma NON e' piu' un requisito per essere ritrovato
            rec = player_db.lookup(nome, squadra) if player_db else None
            if rec and rec.get("id") is not None:
                self.n_con_id += 1
                chiavi.append((self.per_id, int(rec["id"])))

            for contenitore, chiave in chiavi:
                voce = self._voce(contenitore, chiave)
                voce["prezzi"].append(r["costo"])
                voce["dettaglio"].append(osservazione)
                voce["nome"] = voce["nome"] or nome

            cog = _cognome(nome)
            if cog:
                self.per_cognome.setdefault(cog, []).append(
                    {"nome": nome, "abbr": abbr, "ruolo": r.get("ruolo"),
                     **osservazione})

    @staticmethod
    def _formatta(voce, extra=None) -> dict:
        prezzi = voce["prezzi"]
        out = {
            "prezzo_medio": round(statistics.mean(prezzi), 1),
            "prezzo_min": min(prezzi),
            "prezzo_max": max(prezzi),
            "n": len(prezzi),
            "nome_storico": voce.get("nome"),
            "dettaglio": voce["dettaglio"],
        }
        if extra:
            out.update(extra)
        return out

    def cerca_libera(self, testo: str = "", squadra: str = "", ruolo: str = "",
                      limite: int = 60) -> list[dict]:
        """Ricerca nello storico per nome parziale e/o squadra e/o ruolo.

        Lavora sulle righe grezze dei file d'asta, quindi trova anche i
        giocatori che oggi non sono piu' in Serie A. I risultati sono
        ordinati per prezzo decrescente: in asta interessa prima "quanto si
        e' speso", non l'ordine alfabetico.
        """
        q = normalize_name(testo) if testo else ""
        abbr = team_to_abbr(squadra) if squadra else ""
        ruolo = (ruolo or "").upper().strip()

        risultati = []
        for voci in self.per_cognome.values():
            for v in voci:
                if q and q not in normalize_name(v["nome"]):
                    continue
                if abbr and v["abbr"] != abbr:
                    continue
                if ruolo and v.get("ruolo") != ruolo:
                    continue
                risultati.append({
                    "nome": v["nome"],
                    "squadra": v["squadra_reale"],
                    "ruolo": v.get("ruolo"),
                    "costo": v["costo"],
                    "squadra_fantacalcio": v["squadra_fantacalcio"],
                    "fonte": v["fonte"],
                })
        risultati.sort(key=lambda x: -x["costo"])
        return risultati[:limite]

    def get(self, player_id=None, nome: str = "", squadra: str = "") -> dict | None:
        """Prezzo storico per id oppure per nome + squadra.
        Funziona anche per giocatori fuori dal pool del modello."""
        if player_id is not None:
            try:
                voce = self.per_id.get(int(player_id))
            except (TypeError, ValueError):
                voce = None
            if voce:
                return self._formatta(voce)

        if not nome:
            return None
        abbr = team_to_abbr(squadra) if squadra else ""

        if abbr:
            voce = self.per_nome_squadra.get(f"{normalize_name(nome)}|{abbr}")
            if voce:
                return self._formatta(voce)
            voce = self.per_cognome_squadra.get(f"{_cognome(nome)}|{abbr}")
            if voce:
                return self._formatta(voce)

        # cognome da solo: accettato solo se non ambiguo. Serve per chi ha
        # cambiato squadra tra le due stagioni.
        cand = self.per_cognome.get(_cognome(nome), [])
        if cand and len({c["nome"] for c in cand}) == 1:
            prezzi = [c["costo"] for c in cand]
            return {
                "prezzo_medio": round(statistics.mean(prezzi), 1),
                "prezzo_min": min(prezzi),
                "prezzo_max": max(prezzi),
                "n": len(prezzi),
                "nome_storico": cand[0]["nome"],
                "squadra_diversa": bool(abbr) and cand[0]["abbr"] != abbr,
                "squadra_storica": cand[0]["squadra_reale"],
                "dettaglio": [{"costo": c["costo"],
                                "squadra_fantacalcio": c["squadra_fantacalcio"],
                                "squadra_reale": c["squadra_reale"],
                                "fonte": c["fonte"]} for c in cand],
            }
        return None


if __name__ == "__main__":
    from player_db import PlayerDB
    HERE = os.path.dirname(os.path.abspath(__file__))
    db = PlayerDB(os.path.join(HERE, "giocatori_2026_27.xlsx"))
    files = [os.path.join(HERE, f) for f in sorted(os.listdir(HERE))
             if f.startswith("Rose_lega-") and f.endswith(".xlsx")]
    st = StoricoPrezzi(db, files)
    print(f"File: {st.n_file} | record letti: {st.n_record} | anche nel pool: {st.n_con_id}")

    print("\n-- nel pool, ricerca per id --")
    for pid in (2097, 2764, 4312):
        rec = db.lookup_by_id(pid)
        r = st.get(player_id=pid)
        print(f"  {rec['nome']:16s} -> {r['prezzo_medio'] if r else 'MANCA'}")

    print("\n-- FUORI dal pool: prima invisibili, ora ritrovati --")
    for nome, sq in [("Vlahovic", "Juventus"), ("Dusan Vlahovic", "Juventus"),
                      ("Lukaku", "Napoli"), ("Acerbi", "Inter"),
                      ("Castellanos", "Lazio"), ("Angelino", "Roma")]:
        r = st.get(nome=nome, squadra=sq)
        det = f"{r['prezzo_medio']} cr ({r['dettaglio'][0]['squadra_fantacalcio']})" if r else "non trovato"
        print(f"  {nome:18s} {sq:12s} -> {det}")

    print("\n-- copertura del file d'asta --")
    rose = parse_rose_lega(files[0])
    ok = sum(1 for r in rose if st.get(nome=r["calciatore"], squadra=r["squadra_reale"]))
    print(f"  {ok}/{len(rose)} giocatori dell'asta scorsa sono ritrovabili")
