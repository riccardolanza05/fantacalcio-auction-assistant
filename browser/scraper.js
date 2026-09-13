/**
 * SCRAPER — da eseguire DOPO aver girato inspector.js e (idealmente) dopo
 * aver riempito CONFIG.SELECTORS con i selettori esatti trovati insieme.
 * Finche' CONFIG.SELECTORS resta vuoto, usa euristiche generiche (testo
 * "BUDGET"/"MAX", sigle squadra reali) che dovrebbero funzionare ma sono
 * meno precise. Non clicca ne' modifica nulla sulla pagina: legge soltanto.
 *
 * Uso:
 *  1. Apri https://fanta-asta-live.fantacalcio.it/#/main, entra nell'asta.
 *  2. Avvia il server locale sul PC (vedi README).
 *  3. F12 -> Console -> incolla questo intero script -> invio.
 *  4. In basso a destra compare un overlay con lo stato della connessione
 *     e cosa sta leggendo, per verificare a colpo d'occhio che funzioni.
 *
 * In alternativa, per non doverlo re-incollare ogni volta: salvalo come
 * script utente in Tampermonkey con @match https://fanta-asta-live.fantacalcio.it/*
 */
(function () {
  "use strict";

  const CONFIG = {
    SERVER_WS_URL: "ws://localhost:8000/ws/extension",
    // il server richiede autenticazione (ASTA_PASSWORD sul server): la
    // password viene inviata come primo messaggio subito dopo l'apertura
    // della connessione
    PASSWORD: "INSERISCI_LA_TUA_PASSWORD",
    POLL_INTERVAL_MS: 2000,
    DEBUG: true,
    // Se conosci i selettori esatti (da inspector.js + calibrazione), riempili
    // qui: hanno SEMPRE la precedenza sulle euristiche generiche sotto.
    SELECTORS: {
      // --- GIOCATORE IN ASTA: selettori REALI, ricavati dal DOM della pagina ---
      currentPlayerCard: "ui-player-showcase",
      currentPlayerName: ".player-name",
      currentPlayerTeam: ".player-team",
      currentPlayerImg: "img.player-image",           // src contiene l'id: /card/2764.png
      currentPlayerRole: "ui-player-roles[data-game='1'] ui-role span.role",
      // --- BARRA SQUADRE: selettori REALI dal DOM ---
      // Nota: le rose usano virtual scroll (i giocatori esistono nel DOM solo
      // se visibili) e le card fuori dallo scroll orizzontale non sono
      // renderizzate affatto. Per questo NON leggiamo le liste dei giocatori:
      // usiamo budget + contatori per ruolo, che sono sempre presenti su
      // ogni card renderizzata e bastano a ricostruire le assegnazioni.
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

  // mappa data-label dei ruoli (classic) -> lettera usata nei nostri file
  const ROLE_MAP = { gk: "P", def: "D", mid: "C", atk: "A",
                      p: "P", d: "D", c: "C", a: "A" };

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

  // ---------- overlay di debug ----------
  let overlay;
  let overlayHidden = false;
  function ensureOverlay() {
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.style.cssText = `position:fixed;bottom:8px;right:8px;z-index:999999;
      background:#14101fcc;color:#f1eefc;font:11px monospace;padding:8px 10px;
      border-radius:8px;max-width:280px;line-height:1.5;pointer-events:none;`;
    document.body.appendChild(overlay);
    return overlay;
  }
  // Ctrl+Shift+A per nascondere/mostrare l'overlay (leggilo quando ti serve,
  // toglilo di torno mentre segui l'asta)
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.shiftKey && e.key.toUpperCase() === "A") {
      overlayHidden = !overlayHidden;
      ensureOverlay().style.display = overlayHidden ? "none" : "block";
    }
  });
  function updateOverlay(status, player, teams) {
    if (!CONFIG.DEBUG || overlayHidden) return;
    ensureOverlay();
    overlay.innerHTML = `<b>Asta Live scraper</b><br>
      server: ${status}<br>
      giocatore: ${player ? (player.nome || "?") + " " + (player.ruolo || "") : "-"}<br>
      id letto: ${player ? (player.player_id ?? "NESSUNO") : "-"} | lista: ${player ? (player.nome_lista || "-") : "-"}<br>
      squadre lette: ${teams.length}<br>
      ${teams[0] ? `es. ${teams[0].nome_squadra}: budget ${teams[0].budget}, max ${teams[0].max_offerta}, rosa ${teams[0].rosa.length}` : ""}<br>
      <span style="opacity:.6">Ctrl+Shift+A per nascondere</span>`;
  }

  // ---------- websocket ----------
  let ws, wsStatus = "connessione...";
  function connect() {
    // La pagina e' in HTTPS: verso ws://localhost il browser puo' bloccare
    // per "contenuto misto" e il costruttore lancia un'eccezione SINCRONA.
    // Senza try/catch qui, l'intero script si interromperebbe e non
    // comparirebbe nemmeno l'overlay.
    try {
      ws = new WebSocket(CONFIG.SERVER_WS_URL);
    } catch (err) {
      wsStatus = "BLOCCATO dal browser (contenuto misto): usa Tampermonkey";
      console.error("[asta-scraper] WebSocket bloccata:", err);
      return;
    }
    ws.onopen = () => {
      wsStatus = "autenticazione...";
      ws.send(JSON.stringify({ type: "auth", password: CONFIG.PASSWORD }));
    };
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === "auth_ok") {
          wsStatus = "connesso";
          console.log("[asta-scraper] autenticato");
        } else if (m.type === "auth_error") {
          wsStatus = "PASSWORD ERRATA";
          console.error("[asta-scraper] password rifiutata dal server");
        }
      } catch (e) { /* messaggi non JSON: ignora */ }
    };
    ws.onclose = () => { wsStatus = "disconnesso, riprovo..."; setTimeout(connect, 2000); };
    ws.onerror = () => ws.close();
  }
  connect();

  function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }

  // ---------- loop principale ----------
  let lastPlayerKey = null;
  function tick() {
    const player = extractCurrentPlayer();
    const teams = extractTeamsSnapshot();

    if (player && (player.nome || player.player_id !== null)) {
      const key = (player.player_id ?? "") + "|" + (player.nome || "");
      if (key !== lastPlayerKey) {
        lastPlayerKey = key;
        send({ type: "player_on_auction", ...player });
        if (CONFIG.DEBUG) console.log("[asta-scraper] nuovo giocatore in asta:", player);
      }
    }

    if (teams.length) {
      send({ type: "teams_snapshot", teams });
    }

    updateOverlay(wsStatus, player, teams);
  }

  setInterval(tick, CONFIG.POLL_INTERVAL_MS);
  tick();
  console.log("[asta-scraper] avviato. Overlay in basso a destra per verificare la lettura.");
})();
