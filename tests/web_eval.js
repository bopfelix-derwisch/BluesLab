// Laadt web/app.js in een vm (zonder DOM-start) en print JSON.stringify(<expressie>).
// Gebruik: node tests/web_eval.js '<expressie>'
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ctx = { console, URLSearchParams, document: { addEventListener() {} } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "web", "app.js"), "utf8"), ctx);
console.log(JSON.stringify(vm.runInContext(process.argv[2], ctx)));
