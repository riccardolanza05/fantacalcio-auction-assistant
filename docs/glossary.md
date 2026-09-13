# Glossario IT → EN

Il codice, i nomi di colonna e la documentazione di dettaglio di questo
progetto sono in italiano (vedi la nota in [README.it.md](../README.it.md)).
Questa tabella traduce i termini di dominio del fantacalcio per chi legge
in inglese e vuole seguire `docs/methodology.md` o il codice sorgente.

| Italiano | English | Significato / meaning |
|---|---|---|
| fantacalcio | Italian fantasy football | gioco basato sui voti dei giornalisti sportivi / a fantasy game scored on journalist-assigned match ratings |
| asta | auction | l'asta iniziale in cui si comprano i giocatori / the initial auction where players are bought |
| crediti | credits | valuta dell'asta, 1000 per squadra in questa lega / the auction currency, 1000 per team in this league |
| rosa | roster / squad | l'insieme dei giocatori di una squadra / a team's set of players |
| ruolo (P/D/C/A) | role (GK/DEF/MID/FWD) | portiere, difensore, centrocampista, attaccante |
| fascia | tier | livello di qualita' dentro il ruolo (top/semitop/terza/quarta/minori) |
| quotazione (Qt.A / Qt.I) | listing price (current / initial) | il prezzo ufficiale di listino di fantacalcio.it |
| FVM | market value index | l'indice di valore di mercato di fantacalcio.it, usato come ancora del modello |
| fantamedia (Fm) | fantasy average | la media dei fantapunti del giocatore |
| titolarita' | starter likelihood | probabilita'/percentuale di essere titolare |
| produzione attesa | expected production | i fantapunti stagionali attesi, stimati dal modello ML |
| prezzo base | base price | il prezzo dopo gli strati 1-2 (ancora di mercato + quote per reparto) |
| correzione | correction | lo scostamento applicato dagli strati 3 e 4 |
| prezzo modello | model price | il prezzo finale offline (strati 1-3) |
| prezzo consigliato | recommended bid | prezzo modello + strato 4 (live) + deriva di mercato |
| verdetto | verdict | sottovalutato / in linea / sopravvalutato |
| scarto | gap | la differenza percentuale fra prezzo modello e riferimento |
| scarsita' | scarcity | quanto sono esaurite le alternative equivalenti in un dato momento dell'asta |
| deplezione | depletion | la quota di giocatori pari o superiori gia' acquistati |
| livello di rimpiazzo | replacement level | la produzione attesa dell'ultimo slot da titolare ancora libero (concetto VORP) |
| deriva di mercato | market drift | quanto la lega sta pagando sopra o sotto il modello |
| voto d'ufficio | administrative rating | un voto assegnato d'ufficio, non conta come presenza |
| clean sheet | clean sheet | partita senza gol subiti (portieri) |
| giornata | matchday | un turno di campionato |
| probabili formazioni | predicted line-ups | la pagina con i titolari probabili e gli infortuni |
