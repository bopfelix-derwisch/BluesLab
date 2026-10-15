// Draait web/app.js in een nep-browser (vm) en print wat er gebeurde als JSON.
// Gebruik: node tests/web_harness.js <pagina> <http-status voor elke API-aanroep>
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const [pagina, ikStatus, zoek] = [process.argv[2], Number(process.argv[3]), process.argv[4] || ""];
const navigaties = [];
const elementen = {};
const luisterNaar = [];
let nullKinderen = 0;  // "selector:event" voor elke addEventListener op een element
const nepElement = (sel) => elementen[sel] || (elementen[sel] = {
  hidden: true, value: "", textContent: "",
  addEventListener(t) { luisterNaar.push(`${String(sel)}:${t}`); },
  // null/undefined als kind wordt in een echte browser de tekst "null": tellen.
  replaceChildren(...k) { nullKinderen += k.filter(x => x == null).length; },
  append(...k) { nullKinderen += k.filter(x => x == null).length; },
  setAttribute() {},
});
// Optioneel: BLUESLAB_FIXTURES = JSON {padprefix: antwoord} voor geslaagde API-aanroepen.
const fixtures = JSON.parse(process.env.BLUESLAB_FIXTURES || "{}");
const antwoordVoor = (pad) => {
  const sleutel = Object.keys(fixtures).find(k => pad.startsWith(k));
  return sleutel ? fixtures[sleutel] : [];
};
let wakelock = 0;
const luisteraars = {};
const ctx = {
  console, URLSearchParams, Node: function Node() {},
  localStorage: { getItem: () => null, setItem() {} },
  document: {
    body: { dataset: { pagina } },
    querySelector: nepElement,
    createElement: () => nepElement(Symbol("el")),
    addEventListener: (t, f) => { luisteraars[t] = f; },
  },
  location: {
    search: zoek,
    get href() { return "https://blues.example/index.html"; },
    set href(v) { navigaties.push(v); },
    reload() { navigaties.push("reload"); },
  },
  // Elke API-aanroep krijgt dezelfde status (niet ingelogd = overal 401).
  fetch: async (pad) => ({
    status: ikStatus,
    ok: ikStatus < 400,
    json: async () => (ikStatus < 400 ? antwoordVoor(pad) : { detail: "Log eerst in." }),
  }),
  navigator: { wakeLock: { request: async () => { wakelock += 1; return { addEventListener() {} }; } } },
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "web", "app.js"), "utf8"), ctx);
luisteraars.DOMContentLoaded();
setTimeout(() => {
  console.log(JSON.stringify({ navigaties, login_zichtbaar: !nepElement("#login").hidden,
    fout: nepElement("#fout").textContent, luisterNaar, wakelock, nullKinderen }));
}, 50);
