/**
 * INSPECTOR 2 — "punta e clicca", molto piu' affidabile del primo perche'
 * non cerca alla cieca: tu selezioni esattamente l'elemento giusto con
 * l'ispettore di Chrome, lo script legge SOLO quello.
 *
 * PROCEDURA (da rifare per ciascuna voce, richiede ~1 minuto ciascuna):
 *
 *  1. Sulla pagina dell'asta, con almeno una colonna squadra visibile a
 *     schermo, tasto destro sul TESTO "BUDGET" (o sul numero accanto) ->
 *     "Ispeziona". Si apre F12 con quell'elemento gia' selezionato/blu.
 *  2. Vai sul tab "Console" (senza deselezionare l'elemento).
 *  3. Incolla questo intero file UNA VOLTA SOLA (basta la prima volta,
 *     resta disponibile per i pick successivi).
 *  4. Scrivi in console: astaPick("budget")   e premi invio.
 *  5. Ripeti dal punto 1 per: il NUMERO del budget, la scritta "MAX", il
 *     numero del max, il NOME SQUADRA fantacalcio (es. "NapoLanza"), UNA
 *     riga giocatore nella rosa (es. "Meret"), la sigla squadra reale
 *     accanto al giocatore (es. "Nap"). Ogni volta: ispeziona -> torna in
 *     console -> astaPick("<etichetta a piacere>").
 *  6. Alla fine scrivi:  astaReport()   e mandami TUTTO l'output.
 */
window.astaPicks = window.astaPicks || {};

window.astaPick = function (label) {
  const el = $0; // ultimo elemento selezionato nel pannello Elements
  if (!el) {
    console.warn("Nessun elemento selezionato: fai tasto destro -> Ispeziona su qualcosa prima.");
    return;
  }
  function path(node, maxDepth = 6) {
    const parts = [];
    let cur = node;
    for (let i = 0; i < maxDepth && cur && cur !== document.body; i++) {
      const cls = (cur.className && typeof cur.className === "string")
        ? "." + cur.className.trim().split(/\s+/).slice(0, 3).join(".")
        : "";
      parts.unshift(cur.tagName.toLowerCase() + cls);
      cur = cur.parentElement;
    }
    return parts.join(" > ");
  }
  window.astaPicks[label] = {
    ownText: Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(" ").trim(),
    innerText: (el.innerText || "").slice(0, 150),
    tag: el.tagName.toLowerCase(),
    className: el.className || null,
    path: path(el),
    outerHTMLPreview: el.outerHTML.slice(0, 300),
  };
  console.log(`%c[astaPick] salvato "${label}"`, "color:#23c48a;font-weight:bold", window.astaPicks[label]);
};

window.astaReport = function () {
  console.log("%c=== ASTA PICKS REPORT (copia tutto da qui in giu') ===", "color:#7c5cff;font-weight:bold");
  console.log(JSON.stringify(window.astaPicks, null, 2));
  console.log("%c=== FINE REPORT ===", "color:#7c5cff;font-weight:bold");
};

console.log("%cInspector 2 pronto.", "color:#7c5cff;font-weight:bold",
  "\nTasto destro su un elemento -> Ispeziona -> torna qui -> astaPick(\"nome_a_piacere\")." +
  "\nQuando hai fatto tutti i pick: astaReport()");
