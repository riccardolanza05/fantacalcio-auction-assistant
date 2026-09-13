// ==UserScript==
// @name         Asta Live - Copilota Fantacalcio
// @namespace    https://fanta-asta-live.fantacalcio.it/
// @version      2.0
// @description  Legge il giocatore in asta e i budget delle squadre da FantaAstaLive e li invia al server locale, che li inoltra al telefono.
// @author       -
// @match        https://fanta-asta-live.fantacalcio.it/*
// @grant        GM_xmlhttpRequest
// @connect      localhost
// @connect      127.0.0.1
// @run-at       document-idle
// ==/UserScript==

/*
 * PERCHE' HTTP E NON WEBSOCKET
 * La pagina d'asta e' servita in HTTPS. Aprire una WebSocket verso
 * ws://localhost:8000 e' "contenuto misto": Chrome lo blocca e il
 * costruttore WebSocket lancia un'eccezione SINCRONA, che interrompe
 * l'intero script prima ancora che compaia l'overlay.
 * GM_xmlhttpRequest gira invece nel contesto privilegiato dell'estensione,
 * quindi non e' soggetto ne' a mixed content ne' a CORS: mandiamo i dati
 * al server con POST /ingest. Il telefono continua a usare WebSocket, che
 * per lui funziona (si collega in http://).
 *
 * L'overlay in basso a destra si nasconde/mostra con Ctrl+Shift+A.
 */
(function () {
  "use strict";

  const CONFIG = {
    SERVER_URL: "http://localhost:8000",
    // stessa password che usi sul telefono (ASTA_PASSWORD sul server);
    // lo script fa il login da solo
    PASSWORD: "INSERISCI_LA_TUA_PASSWORD",
    POLL_INTERVAL_MS: 2000,
    DEBUG: true,
    SELECTORS: {
      currentPlayerCard: "ui-player-showcase",
      currentPlayerName: ".player-name",
      currentPlayerTeam: ".player-team",
      currentPlayerImg: "img.player-image",
      currentPlayerRole: "ui-player-roles[data-game='1'] ui-role span.role",
      teamCard: "ui-rosters-grid nz-card.team-card",
      teamName: "ui-team-card .team-name span",
      roleChips: "ui-roles-info header ui-chip",
      footerChips: "ui-roles-info footer ui-chip .inner",
      rosterViewport: "ui-roster cdk-virtual-scroll-viewport",
      rosterRow: "ui-roster ui-player-row",
      rosterName: ".player-name",
      rosterTeam: ".player-team",
      rosterRole: "ui-role span.role",
    },
  };

  const ROLE_MAP = { gk: "P", def: "D", mid: "C", atk: "A",
                      p: "P", d: "D", c: "C", a: "A" };

  // ---------- OVERLAY: creato per PRIMO, cosi' se qualcosa fallisce dopo
  // ---------- lo vedi comunque e sai che lo script e' partito ----------
  let overlay = null, overlayHidden = false;
  function ensureOverlay() {
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.id = "asta-live-overlay";
    overlay.style.cssText = "position:fixed;bottom:8px;right:8px;z-index:2147483647;" +
      "background:rgba(20,16,31,.92);color:#f1eefc;font:11px/1.5 monospace;" +
      "padding:8px 10px;border-radius:8px;max-width:300px;pointer-events:none;" +
      "border:1px solid rgba(124,92,255,.5);";
    overlay.textContent = "Asta Live: avvio...";
    (document.body || document.documentElement).appendChild(overlay);
    return overlay;
  }
  function setOverlay(html) {
    if (!CONFIG.DEBUG || overlayHidden) return;
    ensureOverlay().innerHTML = html;
  }
  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey && e.shiftKey && String(e.key).toUpperCase() === "A") {
      overlayHidden = !overlayHidden;
      ensureOverlay().style.display = overlayHidden ? "none" : "block";
    }
  });

  ensureOverlay();
  console.log("[asta-live] script avviato");

  const TEAM_ABBR = ["Ata","Bol","Cag","Com","Cre","Fio","Gen","Int","Juv","Laz",
                      "Lec","Mil","Nap","Par","Pis","Rom","Sas","Tor","Udi","Ver"];
  const ABBR_RE = new RegExp("^(" + TEAM_ABBR.join("|") + ")$");

  // ---------- utils ----------
  function ownText(el) {
    return Array.from(el.childNodes)
      .filter(n => n.nodeType === Node.TEXT_NODE)
      .map(n => n.textContent.trim()).join(" ").trim();
  }

  function firstNumberIn(text) {
    const m = (text || "").match(/-?\d+([.,]\d+)?/);
    return m ? parseFloat(m[0].replace(",", ".")) : null;
  }

  // Nelle chip il testo e' del tipo "BUDGET 956" / "MAX 932" / "TOT 0":
  // serve l'ULTIMO numero, non il primo (il primo puo' finire dentro
  // l'etichetta o dentro un badge nascosto).
  function lastNumberIn(text) {
    const m = (text || "").match(/(-?\d+)(?!.*\d)/s);
    return m ? parseInt(m[1], 10) : null;
  }

  function findLabelNodes(labelUpper) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const out = [];
    while (walker.nextNode()) {
      const t = walker.currentNode.textContent.trim();
      if (t.toUpperCase() === labelUpper) out.push(walker.currentNode);
    }
    return out;
  }

  // ---------- estrazione squadre (budget / max / contatori ruolo) ----------
  // Usa i selettori reali del DOM. Non legge le liste dei giocatori in rosa:
  // sono in virtual scroll (presenti solo se visibili) e quindi inaffidabili.
  // I contatori per ruolo + TOT sono invece sempre renderizzati e bastano a
  // capire CHI ha comprato COSA (il chi/cosa lo sappiamo dal giocatore in asta).
  function extractTeamsSnapshot() {
    const S = CONFIG.SELECTORS;
    const cards = document.querySelectorAll(S.teamCard);
    const out = [];
    for (const card of cards) {
      const nome_squadra = card.querySelector(S.teamName)?.textContent.trim() || null;
      if (!nome_squadra) continue;

      const counts = {};
      card.querySelectorAll(S.roleChips).forEach(chip => {
        const inner = chip.querySelector(".inner");
        if (!inner) return;
        const roleSpan = inner.querySelector("ui-role span.role");
        const n = lastNumberIn(inner.textContent);
        if (roleSpan) {
          const r = ROLE_MAP[roleSpan.getAttribute("data-label")];
          if (r) counts[r] = n;
        } else if (/TOT/.test(inner.textContent)) {
          counts.TOT = n;
        }
      });

      let budget = null, max_offerta = null;
      card.querySelectorAll(S.footerChips).forEach(inner => {
        const t = inner.textContent;
        if (/BUDGET/.test(t)) budget = lastNumberIn(t);
        else if (/MAX/.test(t)) max_offerta = lastNumberIn(t);
      });

      // Righe rosa: quando visibili dicono ESATTAMENTE chi e' stato
      // comprato, senza dover indovinare dal giocatore in vetrina (che al
      // momento della lettura puo' essere gia' cambiato o vuoto).
      // Sono in virtual scroll, quindi possono mancare: in quel caso il
      // server ripiega sui contatori.
      const rosa = [];
      card.querySelectorAll(S.rosterRow).forEach(r => {
        const n = r.querySelector(S.rosterName)?.textContent.trim();
        if (!n) return;
        const roleSpan = r.querySelector(S.rosterRole);
        rosa.push({
          nome: n,
          squadra: r.querySelector(S.rosterTeam)?.textContent.trim() || "",
          ruolo: roleSpan ? (ROLE_MAP[roleSpan.getAttribute("data-label")] || null) : null,
        });
      });

      // UID stabile della rosa: l'id del viewport contiene un uuid che NON
      // cambia se la squadra viene rinominata o se le card vengono
      // riordinate. Senza, una rinomina creerebbe una seconda squadra
      // fantasma sul telefono.
      let uid = null;
      const vp = card.querySelector(S.rosterViewport);
      if (vp && vp.id) {
        const m = vp.id.match(/roster-viewport-(.+)$/);
        uid = m ? m[1] : vp.id;
      }

      out.push({ uid, nome_squadra, budget, max_offerta, counts, rosa });
    }
    return out;
  }

  // ---------- estrazione giocatore in asta ----------
  function extractCurrentPlayer() {
    const S = CONFIG.SELECTORS;
    const card = document.querySelector(S.currentPlayerCard);
    if (!card) return null;

    const nome = card.querySelector(S.currentPlayerName)?.textContent.trim() || null;
    const squadra = card.querySelector(S.currentPlayerTeam)?.textContent.trim() || null;

    // --- id fantacalcio.it: chiave di match ESATTA col database ---
    // La card mostra il nome esteso ("Moise Kean") mentre i file usano la
    // forma abbreviata ("Kean"): l'id evita del tutto il problema.
    // Provo piu' fonti perche' durante l'animazione di cambio card la prima
    // immagine puo' essere ancora quella del giocatore precedente.
    let player_id = null;
    const imgs = card.querySelectorAll("img.player-image");
    // l'ultima immagine e' la "card-front", quella effettivamente mostrata
    for (let i = imgs.length - 1; i >= 0 && player_id === null; i--) {
      const src = imgs[i].getAttribute("src") || imgs[i].src || "";
      const m = src.match(/\/card\/(\d+)\.png/);
      if (m) player_id = parseInt(m[1], 10);
    }

    // ruolo classic dal data-label dello span
    let ruolo = null;
    const roleSpan = card.querySelector(S.currentPlayerRole);
    if (roleSpan) ruolo = ROLE_MAP[roleSpan.getAttribute("data-label")] || null;

    // FVM e nome in forma abbreviata dalla riga selezionata nella lista laterale
    // (quando c'e', e' gia' nel formato dei file: "Kean", "Martinez L.")
    let fvm_live = null, nome_lista = null;
    const selRow = document.querySelector("ui-player-row.selected");
    if (selRow) {
      fvm_live = lastNumberIn(selRow.querySelector(".stats")?.textContent);
      nome_lista = selRow.querySelector(".player-name")?.textContent.trim() || null;
    }

    // Quando nessun giocatore e' in asta la vetrina resta montata ma vuota e
    // i campi contengono segnaposto ("-"): niente da inviare, altrimenti il
    // telefono mostrerebbe un giocatore inesistente.
    const nomeValido = nome && nome !== "-" && nome.length > 1;
    if (!nomeValido && player_id === null) return null;
    return { nome: nomeValido ? nome : null, nome_lista, squadra, ruolo, fvm_live, player_id };
  }

  // ---------- invio al server via GM_xmlhttpRequest ----------
  let serverStatus = "login in corso...";
  let lastError = "";
  let token = null;

  // Il server richiede autenticazione: prima cosa scambiamo la password con
  // un token di sessione, poi ogni POST lo porta nell'header.
  function login(callback) {
    try {
      GM_xmlhttpRequest({
        method: "POST",
        url: CONFIG.SERVER_URL + "/login",
        headers: { "Content-Type": "application/json" },
        data: JSON.stringify({ password: CONFIG.PASSWORD }),
        timeout: 4000,
        onload: function (res) {
          if (res.status === 200) {
            try {
              token = JSON.parse(res.responseText).token;
              serverStatus = "connesso";
              lastError = "";
              if (callback) callback();
            } catch (e) { serverStatus = "risposta login illeggibile"; }
          } else if (res.status === 401) {
            serverStatus = "password errata";
            lastError = "correggi PASSWORD nello script";
          } else {
            serverStatus = "login fallito (HTTP " + res.status + ")";
          }
        },
        onerror: function () {
          serverStatus = "server non raggiungibile";
          lastError = "avvia app.py sul PC";
        },
        ontimeout: function () { serverStatus = "timeout al login"; },
      });
    } catch (err) {
      serverStatus = "GM_xmlhttpRequest non disponibile";
      lastError = String(err).slice(0, 80);
      console.error("[asta-live]", err);
    }
  }

  function send(obj) {
    if (!token) { login(); return; }   // riprovera' al tick successivo
    try {
      GM_xmlhttpRequest({
        method: "POST",
        url: CONFIG.SERVER_URL + "/ingest",
        headers: { "Content-Type": "application/json", "X-Auth-Token": token },
        data: JSON.stringify(obj),
        timeout: 4000,
        onload: function (res) {
          if (res.status === 200) {
            serverStatus = "connesso";
          } else if (res.status === 401) {
            // server riavviato: i token vengono azzerati, rifacciamo login
            token = null;
            serverStatus = "riautenticazione...";
            login();
          } else {
            serverStatus = "errore HTTP " + res.status;
            lastError = String(res.responseText || "").slice(0, 80);
          }
        },
        onerror: function () {
          serverStatus = "server non raggiungibile";
          lastError = "avvia app.py sul PC";
        },
        ontimeout: function () { serverStatus = "timeout"; },
      });
    } catch (err) {
      serverStatus = "GM_xmlhttpRequest non disponibile";
      lastError = String(err).slice(0, 80);
      console.error("[asta-live]", err);
    }
  }

  // ---------- loop principale ----------
  let lastPlayerKey = null;

  function tick() {
    let player = null, teams = [];
    try {
      player = extractCurrentPlayer();
    } catch (err) {
      lastError = "estrazione giocatore: " + String(err).slice(0, 60);
      console.error("[asta-live] extractCurrentPlayer", err);
    }
    try {
      teams = extractTeamsSnapshot();
    } catch (err) {
      lastError = "estrazione squadre: " + String(err).slice(0, 60);
      console.error("[asta-live] extractTeamsSnapshot", err);
    }

    if (player && (player.nome || player.player_id !== null)) {
      const key = (player.player_id != null ? player.player_id : "") + "|" + (player.nome || "");
      if (key !== lastPlayerKey) {
        lastPlayerKey = key;
        send(Object.assign({ type: "player_on_auction" }, player));
        console.log("[asta-live] nuovo giocatore in asta:", player);
      }
    }
    if (teams.length) send({ type: "teams_snapshot", teams: teams });

    setOverlay(
      "<b>Asta Live</b><br>" +
      "server: " + serverStatus + "<br>" +
      "giocatore: " + (player ? (player.nome || "?") + " " + (player.ruolo || "") : "-") + "<br>" +
      "id letto: " + (player ? (player.player_id != null ? player.player_id : "NESSUNO") : "-") +
      " | lista: " + (player ? (player.nome_lista || "-") : "-") + "<br>" +
      "squadre lette: " + teams.length + "<br>" +
      (teams[0] ? ("es. " + teams[0].nome_squadra + ": budget " + teams[0].budget +
                    ", max " + teams[0].max_offerta + ", tot " + (teams[0].counts || {}).TOT + "<br>") : "") +
      (lastError ? "<span style='color:#ff8f8f'>" + lastError + "</span><br>" : "") +
      "<span style='opacity:.6'>Ctrl+Shift+A per nascondere</span>"
    );
  }

  login(tick);
  setInterval(tick, CONFIG.POLL_INTERVAL_MS);
})();
