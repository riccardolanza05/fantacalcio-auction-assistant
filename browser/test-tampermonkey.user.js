// ==UserScript==
// @name         TEST Tampermonkey
// @namespace    https://fanta-asta-live.fantacalcio.it/
// @version      1.0
// @description  Script di prova: verifica solo se Tampermonkey esegue gli script su questa pagina.
// @match        https://fanta-asta-live.fantacalcio.it/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

/*
 * A COSA SERVE
 * Non fa niente di utile: disegna solo una banda verde in alto.
 *   - Se la banda COMPARE -> Tampermonkey funziona, il problema e' nello
 *     script principale (o nei permessi verso localhost).
 *   - Se la banda NON compare -> Tampermonkey non sta eseguendo nulla su
 *     questa pagina. Nel 90% dei casi manca la "Modalita' sviluppatore" in
 *     chrome://extensions (vedi README).
 */
(function () {
  "use strict";
  var d = document.createElement("div");
  d.textContent = "TAMPERMONKEY FUNZIONA — ora puoi togliere questo script di prova";
  d.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:2147483647;" +
    "background:#23c48a;color:#08160f;font:bold 14px sans-serif;" +
    "padding:10px;text-align:center;";
  (document.body || document.documentElement).appendChild(d);
  console.log("[TEST] Tampermonkey esegue gli script su questa pagina");
})();
