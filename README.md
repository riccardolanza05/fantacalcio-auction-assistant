# Fantacalcio Auction Assistant

*[Leggi questo in italiano](README.it.md)*

A system for deciding how much to bid in a fantasy-football auction using
math instead of gut feeling. Before the auction it computes a calibrated
price for every player (with an uncertainty range); during the auction it
reads the live auction page from the browser and pushes the current
recommended bid, every opponent's remaining budget, and your own roster
breakdown to your phone in real time.

Built for **Fantacalcio** — the Italian fantasy-football format played
through a live auction — for the author's own 10-team league, and used in
a real auction. **The source code is written in Italian** (comments,
docstrings, variable names) and stays that way on purpose: the domain has
terms (*fantamedia*, *quotazione*, *titolarità*, *fascia*) with no standard
English translation, and the project was built for an Italian league. This
README, [docs/methodology.md](docs/methodology.md) and the
[IT→EN glossary](docs/glossary.md) are enough to understand and run it
without reading Italian code. The fuller native documentation — including
the complete evolution log and file inventory — lives in
[README.it.md](README.it.md) and [PROJECT_DOSSIER.md](PROJECT_DOSSIER.md).
**Please don't open a pull request to translate the code.**

## The idea, in plain terms

Italian fantasy football in "Classic" mode is played through an initial
auction: each team has a fixed budget in credits and buys players in
ascending bids, one at a time, until every roster slot is filled. The
auction largely decides the season, yet it happens in real time, under
pressure, with everyone reading the same official price list. Three
questions keep coming up:

1. **What is this player actually worth**, in credits, in *my* league?
2. **At the price it's going for right now, is it a good deal?**
3. **How far should I push**, given that alternatives are being depleted
   as the auction proceeds?

The project answers with two complementary halves:

```
                    ┌──────────────────────────────────────────────┐
   HISTORICAL DATA  │  OFFLINE PIPELINE (before the auction)       │
   (fantacalcio.it) │                                              │
                     │  ML model: expected production (+ p10/p90)   │
                    │        ↓                                     │
                    │  pricing/modello_prezzo.py  (layers 1-2-3)   │
                    │        ↓  prices.csv                         │
                    │  pricing/verdetto.py  (over/undervalued)     │
                    │        ↓  verdict.csv                        │
                    │  server/build_giocatori.py  (merge + injuries) │
                    │        ↓                                     │
                    │     giocatori_YYYY_YY.xlsx  ◄── the database │
                    └──────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴──────────────────────────┐
                    │  LIVE ASSISTANT (during the auction)         │
                    │                                              │
  auction page   ──► browser/asta-live.user.js (Tampermonkey, PC)  │
  (HTTPS, Angular)  │  POST /ingest                                │
                    │        ↓                                     │
                    │  server/app.py (FastAPI, localhost:8000)     │
                    │   ├── player_db.py    player lookup          │
                    │   ├── vorp_live.py    LAYER 4 (scarcity)     │
                    │   ├── live_state.py   auction & roster state │
                    │   ├── storico_prezzi.py  last season's prices│
                    │   └── simili.py       lookalike references  │
                    │        ↓ WebSocket                           │
                    │  static/phone.html  ◄── phone, same WiFi     │
                    └──────────────────────────────────────────────┘
```

The design rule, enforced at every layer: **no layer may overturn the
previous one.** The market (fantacalcio.it's FVM market-value index)
always has the final say on the *shape* of the price curve; the
statistical model shifts prices, it doesn't reinvent them. Full detail in
[docs/methodology.md](docs/methodology.md).

## How it evolved, and why

The project grew iteratively, often in reaction to a concrete failure
rather than a plan drawn up in advance. The two most instructive turns:

- **The verdict's reference matters more than the model itself.** The
  first version of the over/undervalued verdict compared each player
  against a behavioral model trained on a single real auction. Result:
  completely unstable verdicts (standard deviation **≈ 241%**). Replacing
  that reference with the market-value index rescaled by role-based budget
  quotas — a far more "boring" number — brought the standard deviation
  down to **≈ 10.9%**.
- **A full Bayesian model works better offline than live.** The first
  live scarcity corrector was a Bayesian Normal-Inverse-Gamma tracker.
  Working from a pure VORP fair value (not anchored to the market) it
  produced 6-10× multipliers on bottom-tier players — absurd prices
  exactly where the auction gets most crowded. It was replaced by a
  simpler scarcity factor based on the composition/depletion of the
  remaining player pool, which approximates empirical Bayesian shrinkage
  without the latency and sparse-observation costs of the full model.

Other notable, empirically-justified choices:

- **Gradient boosting, not a neural network**, for the expected-production
  model: it outperforms neural nets on tabular data of this size.
- **A 10% verdict threshold**, chosen from a 6-season backtest comparing 5
  candidate thresholds: it's the one with the least variability across
  seasons, and covers 83% of players.
- **Role-dependent persistence in the mean-reversion correction**: the
  goalkeeper coefficient is **negative** (−0.08) — a goalkeeper's
  above-average season simply doesn't repeat — versus 0.81 for forwards.
  This is why the correction caps on goalkeepers are so low.

Every phase, with the numbers behind it, is documented in
[docs/methodology.md](docs/methodology.md) and in the full project
dossier, [PROJECT_DOSSIER.md](PROJECT_DOSSIER.md).

## Results (6-season backtest)

- Expected-production model: **R² ≈ 0.467** under temporal
  cross-validation; p10/p90 intervals with **81.6%** empirical coverage
  (nominal 80%).
- Verdict: players flagged undervalued returned **1.86×**, and overvalued
  players **0.77×**, the production actually realized — across all 6
  tested seasons. Rank correlation (Spearman) between 0.43 and 0.74
  depending on the season.

## Try it now (synthetic data, no fantacalcio.it account needed)

```bash
git clone <this-repo-url>
cd fantacalcio-auction-assistant

# pricing pipeline on 80 made-up players
pip install -r requirements-pipeline.txt
python pricing/modello_prezzo.py --in-csv examples/sample_data/predizioni_esempio.csv --out-csv /tmp/prezzi.csv
python pricing/verdetto.py --in-csv /tmp/prezzi.csv --out-csv /tmp/verdetto.csv

# server (with the same ready-made synthetic database)
pip install -r requirements.txt
cp examples/sample_data/giocatori_esempio.xlsx server/giocatori_2026_27.xlsx
cd server && ASTA_PASSWORD=demo python app.py   # then open http://localhost:8000
```

To use it with your own league you need your own fantacalcio.it exports:
see [docs/data-sources.md](docs/data-sources.md) for where to find them and
how they're shaped, and [docs/operations.md](docs/operations.md) (Italian)
for the full operational guide (DOM calibration, Tampermonkey setup,
troubleshooting).

## Honest status

The pipeline **is** reproducible end-to-end from your own fantacalcio.it
data. `pricing/model/train_model.py` and `pricing/model/build_hreg.py` —
the ML training script and the hierarchical-shrinkage builder that earlier
versions of this repository listed as missing — have been recovered from
the transcript of the original development session and re-run against
real data to confirm they reproduce the documented results (see
[docs/data-sources.md](docs/data-sources.md), section 3, for the exact
numbers). `pricing/votes/` (also recovered) turns the raw per-matchday vote
files into the aggregated dataset those two scripts need.

Two smaller things remain open:

1. **A fresh starter-likelihood snapshot** for `train_model.py` is
   optional and week-specific, not a static missing artifact — without it
   that one feature defaults to "unknown" and the rest of the model is
   unaffected. See `pricing/model/README.md`.
2. **SHAP was never actually implemented** in the original project,
   despite earlier documentation here claiming it was — the recovered
   transcript shows it only as a stated intention, never as executed code.

A known mismatch between two parts of the pricing pipeline over the
league's team count (10 vs. 12) is also documented in
[docs/data-sources.md](docs/data-sources.md) and in
[PROJECT_DOSSIER.md](PROJECT_DOSSIER.md).

## Repository layout

```
pricing/
  modello_prezzo.py, verdetto.py   price layers 1-3 and the verdict
  model/                            ML training (HistGradientBoosting + conformal) and Hreg.pkl
  votes/                            scraping and aggregating historical votes
server/     the live assistant's FastAPI server + data-building scripts
browser/    the Tampermonkey userscript and console script that read the auction page
docs/       methodology, data sources, glossary, operational guide (mostly Italian)
tests/      CI smoke test (synthetic data) + manual verification scripts
examples/   synthetic-data generator and a reference configuration file
```

## License

The code is MIT (see [LICENSE](LICENSE)). Official fantacalcio.it data is
**not included** and is not covered by this license — see
[docs/data-sources.md](docs/data-sources.md) for how to obtain it yourself.
