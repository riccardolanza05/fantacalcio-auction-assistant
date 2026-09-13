"""
Utility condivise: normalizzazione nomi giocatori e mapping squadre.
Serve per fare matching robusto tra file con formati leggermente diversi
(es. "Martinez L." in Quotazioni vs "Martinez L." in Rose_lega, ma anche
casi con accenti / abbreviazioni diverse).
"""
import re
import unicodedata

# Mapping nome-completo (come in Quotazioni/Statistiche) -> abbreviazione 3 lettere
# (come in Rose_lega / export FantaAsta Live)
TEAM_FULL_TO_ABBR = {
    "atalanta": "Ata", "bologna": "Bol", "cagliari": "Cag", "como": "Com",
    "cremonese": "Cre", "fiorentina": "Fio", "genoa": "Gen", "inter": "Int",
    "juventus": "Juv", "lazio": "Laz", "lecce": "Lec", "milan": "Mil",
    "napoli": "Nap", "parma": "Par", "pisa": "Pis", "roma": "Rom",
    "sassuolo": "Sas", "torino": "Tor", "udinese": "Udi", "verona": "Ver",
    # squadre di stagioni precedenti / retrocesse, aggiungere se servono
    "empoli": "Emp", "frosinone": "Fro", "salernitana": "Sal", "sampdoria": "Sam",
    "spezia": "Spe", "venezia": "Ven", "monza": "Mon",
}
TEAM_ABBR_SET = set(TEAM_FULL_TO_ABBR.values())


def team_to_abbr(team_name: str) -> str:
    """Converte un nome squadra (in qualsiasi formato) nella sigla a 3 lettere."""
    if not team_name:
        return ""
    t = team_name.strip()
    if t in TEAM_ABBR_SET:
        return t
    key = t.lower()
    return TEAM_FULL_TO_ABBR.get(key, t[:3].capitalize())


def normalize_name(name: str) -> str:
    """Normalizza un nome giocatore per matching: minuscolo, senza accenti,
    senza punteggiatura, spazi puliti."""
    if not name:
        return ""
    n = str(name).strip()
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode("ascii")
    n = n.lower()
    n = re.sub(r"[.\-']", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def build_match_key(name: str, team_abbr: str) -> str:
    return f"{normalize_name(name)}|{team_abbr}"
