// Laadt web/speler.js + web/app.js in een vm (zonder DOM-start) en print JSON.stringify(<expressie>),
// na afwachten als het een belofte is (een afgewezen belofte wordt {fout: <melding>}).
// Gebruik: node tests/web_eval.js '<expressie>'
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ctx = { console, URLSearchParams, setTimeout, clearTimeout, setInterval, clearInterval,
  document: { addEventListener() {} } };
vm.createContext(ctx);
for (const f of ["speler.js", "app.js"]) {
  vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "web", f), "utf8"), ctx);
}
Promise.resolve(vm.runInContext(process.argv[2], ctx)).then(
  r => console.log(JSON.stringify(r)),
  e => console.log(JSON.stringify({ fout: String(e && e.message || e) })));
