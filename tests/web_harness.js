// Draait web/app.js in een nep-browser (vm) en print wat er gebeurde als JSON.
// Gebruik: node tests/web_harness.js <pagina> <http-status voor elke API-aanroep>
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const [pagina, ikStatus] = [process.argv[2], Number(process.argv[3])];
const navigaties = [];
const elementen = {};
const nepElement = (sel) => elementen[sel] || (elementen[sel] = {
  hidden: true, value: "", textContent: "",
  addEventListener() {}, replaceChildren() {}, append() {},
});
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
    search: "",
    get href() { return "https://blues.example/index.html"; },
    set href(v) { navigaties.push(v); },
    reload() { navigaties.push("reload"); },
  },
  // Elke API-aanroep krijgt dezelfde status (niet ingelogd = overal 401).
  fetch: async () => ({
    status: ikStatus,
    ok: ikStatus < 400,
    json: async () => (ikStatus < 400 ? [] : { detail: "Log eerst in." }),
  }),
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "web", "app.js"), "utf8"), ctx);
luisteraars.DOMContentLoaded();
setTimeout(() => {
  console.log(JSON.stringify({ navigaties, login_zichtbaar: !nepElement("#login").hidden }));
}, 50);
