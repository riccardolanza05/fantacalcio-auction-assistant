# Scraper voti storici — istruzioni

Scarica e consolida i voti giornata-per-giornata di fantacalcio.it in un
unico file (`voti_aggregato_v3.csv`), l'input di
[`../model/train_model.py`](../model/train_model.py) e
[`../model/build_hreg.py`](../model/build_hreg.py).

## 1. Prerequisiti

```bash
pip install requests beautifulsoup4 pandas openpyxl
```

## 2. Ottenere il cookie di sessione

L'endpoint Excel dei voti funziona solo da loggati e rifiuta le richieste
esterne anche con credenziali corrette a volte (dipende dal cookie), quindi
serve il cookie della **tua** sessione. Passaggi (Chrome/Edge/Firefox sono
equivalenti):

1. Apri il browser e **fai login** su `fantacalcio.it`.
2. Vai su una pagina voti qualsiasi, es.
   `https://www.fantacalcio.it/voti-fantacalcio-serie-a/2025-26/4`
3. Premi **F12** → scheda **Network** (Rete).
4. Ricarica la pagina (F5).
5. Nella lista, clicca la **prima richiesta** (quella del documento HTML).
6. Sezione **Request Headers** → trova la riga `Cookie:`.
7. Copia **tutto** il valore dopo `Cookie: ` (è lungo, spesso centinaia di caratteri).

Poi, in questa cartella:

```bash
# macOS / Linux
echo 'INCOLLA_QUI_IL_COOKIE' > cookie.txt

# Windows PowerShell
'INCOLLA_QUI_IL_COOKIE' | Out-File -Encoding utf8 cookie.txt
```

In alternativa via variabile d'ambiente:

```bash
export FC_COOKIE='INCOLLA_QUI_IL_COOKIE'     # macOS/Linux
$env:FC_COOKIE='INCOLLA_QUI_IL_COOKIE'       # Windows PowerShell
```

> **Il cookie equivale a una sessione di login attiva.** Non metterlo su
> GitHub, non condividerlo (`cookie.txt` è nel `.gitignore` del repo). Se
> sbagli, fai logout/login sul sito: il vecchio cookie decade. Scade da
> solo dopo un po': se lo script si ferma con `[STOP] credenziali
> rifiutate`, rifai questi passaggi e rilancia — riprende da dove si era
> interrotto.

Verifica rapida che il cookie funzioni: `python test_auth.py`.

## 3. Lanciare il download

```bash
python scraper_voti.py
```

- **Fase 1**: risolve l'ID interno di ogni stagione leggendolo dal sito
  (non lo tira a indovinare). ~1 minuto.
- **Fase 2**: scarica ~418 file (11 stagioni × 38 giornate). Con il delay
  impostato (2-4s), sono circa 20-30 minuti. Lascialo girare: puoi
  interromperlo (Ctrl+C) e rilanciarlo quando vuoi, riprende da dove era.

I file finiscono in `voti_raw/{stagione}/g{NN}.xlsx`.

Se preferisci scaricarli manualmente dal browser invece che via cookie
(es. `voti_STAGIONE_gNN.xlsx` finiti nella cartella Downloads), usa
`riordina_download.py` per rimetterli nella struttura che
`parse_voti.py` si aspetta.

## 4. Consolidare

```bash
python parse_voti.py      # -> voti_panel.csv, voti_panel_report.txt
python valida_voti.py [cartella_con_i_file_Statistiche]   # verifica di coerenza
python aggrega_voti_v3.py # -> voti_aggregato_v3.csv (richiede regole_lega.py)
```

`aggrega_voti_v3.py` applica le regole di punteggio della tua lega
(`regole_lega.py`: gol con rigori inclusi, rigore sbagliato -2, porta
inviolata +1 solo portiere, modificatore difesa a fasce) e produce
`voti_aggregato_v3.csv`: una riga per (stagione, giocatore), con
fantamedia, deviazione standard del voto, titolarità storica e le altre
feature che il modello ML usa. `regole_lega.py` gira anche da solo come
autotest (`python regole_lega.py`).

## Comportamento civile dello scraper

- Delay 2-4s randomizzato tra le richieste, con backoff progressivo sugli
  errori e attesa lunga in caso di HTTP 429.
- Ripresa incrementale: non riscarica ciò che ha già.
- User-Agent reale, nessun tentativo di mascheramento.

È un download una-tantum di dati che il sito già espone dal bottone
"Scarica" del tuo account, per uso personale. Non redistribuire i dati
grezzi e non alzare la frequenza.

## Se qualcosa non funziona

| Sintomo | Causa probabile | Rimedio |
|---|---|---|
| `ERRORE: cookie non trovato` | manca `cookie.txt` / `FC_COOKIE` | rifai la sezione 2 |
| `[STOP] credenziali rifiutate` | cookie scaduto | rifai la sezione 2, rilancia |
| `ID NON TROVATO` per tutte le stagioni | non sei loggato, o il sito è cambiato | verifica il login |
| tanti `o` (vuoti) | endpoint diverso per le stagioni vecchie | normale sulle prime stagioni |
| `X` sparsi | rete instabile | rilancia: riprende e completa i buchi |
