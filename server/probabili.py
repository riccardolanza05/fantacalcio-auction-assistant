"""
Estrae dal file HTML delle probabili formazioni di fantacalcio.it:
  - gli infortunati, con la dicitura del sito ("distorsione alla caviglia,
    out contro Venezia" / "... out fino al 15 settembre");
  - la percentuale di titolarita' di ciascun giocatore.

Il file va scaricato dalla pagina https://www.fantacalcio.it/probabili-formazioni-serie-a
(tasto destro -> Salva pagina) e messo nella cartella server/ col nome
`probabili-formazioni-serie-a`. Il parser e' tollerante: se il file manca,
il resto del sistema continua a funzionare senza dati di infortunio.
"""
import html as _html
import os
import re

TAG = re.compile(r"<[^>]+>")


def _testo(frammento: str) -> str:
    t = TAG.sub(" ", frammento)
    t = _html.unescape(t)      # &#x27; -> '  ,  &#xE8; -> e' accentata
    return re.sub(r"\s+", " ", t).strip()


def parse_infortunati(path: str) -> dict:
    """nome_giocatore -> dicitura del sito sull'indisponibilita'."""
    if not os.path.exists(path):
        return {}
    html = open(path, encoding="utf-8", errors="replace").read()

    out = {}
    # Ogni infortunato e' un <li> dentro <ul class="injured-list">.
    # Va isolato PRIMA il singolo <li>: cercando nome e descrizione con un
    # unico regex sull'intera pagina, il nome di una voce finisce appaiato
    # alla descrizione di quella successiva.
    for lista in re.findall(r'<ul class="injured-list">(.*?)</ul>', html, re.S):
        for li in re.findall(r"<li>(.*?)</li>", lista, re.S):
            m_nome = re.search(r'class="player-name[^"]*"[^>]*>.*?<span>(.*?)</span>',
                                li, re.S)
            m_desc = re.search(r'<p class="description">(.*?)</p>', li, re.S)
            if not (m_nome and m_desc):
                continue
            nome = _testo(m_nome.group(1))
            descrizione = _testo(m_desc.group(1))
            if nome and descrizione:
                out[nome] = descrizione
    return out


def parse_titolarita(path: str) -> dict:
    """(nome, sigla_squadra) -> percentuale di titolarita'."""
    if not os.path.exists(path):
        return {}
    html = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    # il valore compare come attributo/percentuale accanto al nome nella
    # griglia dei probabili titolari
    for m in re.finditer(
            r'<span[^>]*class="[^"]*player-name[^"]*"[^>]*>(.*?)</span>.*?'
            r'(\d{1,3})%', html, re.S):
        nome = _testo(m.group(1))
        if nome and len(nome) < 40:
            out.setdefault(nome, int(m.group(2)))
    return out


if __name__ == "__main__":
    HERE = os.path.dirname(os.path.abspath(__file__))
    for cartella in (HERE, os.getcwd()):
        p = os.path.join(cartella, "probabili-formazioni-serie-a")
        if os.path.exists(p):
            inf = parse_infortunati(p)
            print(f"{p}: {len(inf)} infortunati")
            for n, d in list(inf.items())[:12]:
                print(f"  {n:22s} {d}")
            break
    else:
        print("file delle probabili formazioni non trovato")
