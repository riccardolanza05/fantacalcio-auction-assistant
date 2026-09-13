# Modello di produzione attesa

```bash
pip install -r ../../requirements-pipeline.txt

# 1. shrinkage gerarchico per la regressione alla media (strato 3b)
python build_hreg.py \
    --voti-aggregato ../votes/voti_aggregato_v3.csv \
    --out Hreg.pkl

# 2. training + predizione per la stagione corrente
python train_model.py \
    --voti-aggregato ../votes/voti_aggregato_v3.csv \
    --quotazioni-corrente <path>/Quotazioni_Fantacalcio_Stagione_2026_27.xlsx \
    --quotazioni-storiche-glob "<path>/Quotazioni_Fantacalcio_Stagione_*.xlsx" \
    --out predizioni_2026_27_v2.csv

# 3. da qui in poi, la pipeline documentata nel README principale
cp Hreg.pkl ../
python ../modello_prezzo.py --in-csv predizioni_2026_27_v2.csv --out-csv prezzi.csv --hreg ../Hreg.pkl
```

`voti_aggregato_v3.csv` si costruisce con la pipeline in
[`../votes/`](../votes/README.md), a partire dai voti giornata-per-giornata
scaricati da fantacalcio.it.

## Origine di questi due script

Non erano tra i file del progetto su disco (vedi
`docs/data-sources.md`): sono stati recuperati dalla trascrizione della
sessione originale in cui il modello e' stato sviluppato, salvata
integralmente in Basic Memory. Sono stati **rieseguiti sui dati reali** per
verificarne la fedeltà prima di includerli qui:

- `build_hreg.py` riproduce **esattamente** i numeri registrati nella
  sessione originale (2274 giocatori con storico, stessa media/min/max di
  `correzione_fm` per ruolo).
- `train_model.py` riproduce la stessa correzione conformal (13.8
  fantapunti) e un R² medio in validazione temporale (~0.45-0.47) coerente
  col numero documentato altrove nel progetto (0.467).

## Cosa manca ancora

`train_model.py --probabili-json` e' opzionale e non incluso: e' uno
snapshot delle percentuali di probabile titolarità per la prossima
giornata, specifico della settimana in cui viene generato (non un dato
statico riusabile). Senza, la titolarità futura e' trattata come
sconosciuta (pct=0), che degrada solo quella singola feature — il resto
del modello funziona comunque. Per costruirlo dalla pagina
`probabili-formazioni-serie-a`, vedi `docs/data-sources.md`: la struttura
HTML del sito cambia nel tempo, quindi il parser va ricalibrato quando
serve (stesso principio dello scraper dell'asta live in `browser/`).

Non e' invece stato ritrovato ne' ricostruito l'uso di **SHAP** per
l'interpretabilità: nella trascrizione della sessione originale compare
solo come intenzione dichiarata ("gradient boosting con SHAP resta la
scelta giusta"), mai come codice effettivamente eseguito. La
documentazione precedente di questo progetto lo elencava come già fatto:
non lo era. Aggiungerlo e' immediato (`shap.TreeExplainer(mod)` sul
modello di `train_model.py`) ma resta da fare.
