// Draait web/app.js in een nep-browser (vm) en print wat er gebeurde als JSON.
// Gebruik: node tests/web_harness.js <pagina> <http-status voor elke API-aanroep>
// Omgeving: BLUESLAB_FIXTURES, BLUESLAB_AUDIO, BLUESLAB_ACTIES (zie verderop),
// BLUESLAB_PIANO (ok | fout | traag | hangt) en BLUESLAB_VERBORGEN=1 (pagina niet zichtbaar).
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const [pagina, ikStatus, zoek] = [process.argv[2], Number(process.argv[3]), process.argv[4] || ""];
const navigaties = [];
const elementen = {};
const luisterNaar = [];
let nullKinderen = 0;  // "selector:event" voor elke addEventListener op een element
let maatvakken = 0;   // elementen met data-nr (aan te tikken maatvakken)
const fetches = [];
const wacht = ms => new Promise(r => setTimeout(r, ms));
// BLUESLAB_PIANO: ok (standaard) | fout (404) | traag (30 ms) | hangt (nooit klaar).
const pianoStand = process.env.BLUESLAB_PIANO || "ok";
const pianoAntwoord = async () => {
  if (pianoStand === "hangt") return new Promise(() => {});
  if (pianoStand === "traag") await wacht(30);
  const ok = pianoStand !== "fout";
  return { ok, status: ok ? 200 : 404, arrayBuffer: async () => new ArrayBuffer(8) };
};
const gemaakt = [];   // elementen uit createElement, voor BLUESLAB_ACTIES
const nepElement = (sel) => elementen[sel] || (elementen[sel] = {
  hidden: true, value: "", textContent: "", _attrs: {}, _on: {}, _tekst: "",
  addEventListener(t, f) { luisterNaar.push(`${String(sel)}:${t}`); this._on[t] = f; },
  // null/undefined als kind wordt in een echte browser de tekst "null": tellen.
  replaceChildren(...k) { nullKinderen += k.filter(x => x == null).length; },
  append(...k) {
    nullKinderen += k.filter(x => x == null).length;
    this._tekst += k.filter(x => typeof x === "string").join("");
  },
  setAttribute(k, v) { this._attrs[k] = v; if (k === "data-nr") maatvakken += 1; },
  classList: { add() {}, remove() {} },
  closest() { return null; },
  pause() {},
  play: async () => {},
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
  setTimeout, clearTimeout, setInterval, clearInterval,
  localStorage: { getItem: () => null, setItem() {} },
  document: {
    body: { dataset: { pagina } },
    visibilityState: process.env.BLUESLAB_VERBORGEN === "1" ? "hidden" : "visible",
    querySelector: nepElement,
    createElement: () => { const e = nepElement(Symbol("el")); gemaakt.push(e); return e; },
    addEventListener: (t, f) => { luisteraars[t] = f; },
  },
  location: {
    search: zoek,
    get href() { return "https://blues.example/index.html"; },
    set href(v) { navigaties.push(v); },
    reload() { navigaties.push("reload"); },
  },
  // Elke API-aanroep krijgt dezelfde status (niet ingelogd = overal 401).
  fetch: async (pad) => {
    fetches.push(pad);
    if (pad.startsWith("piano/")) return pianoAntwoord();
    return { status: ikStatus, ok: ikStatus < 400,
      json: async () => (ikStatus < 400 ? antwoordVoor(pad) : { detail: "Log eerst in." }) };
  },
  navigator: { audioSession: { type: "auto" }, wakeLock: { request: async () => { wakelock += 1; return { addEventListener() {} }; } } },
};
// BLUESLAB_AUDIO=1: de browser heeft Web Audio (nep: er klinkt niets).
// starts = keren gestart (hoofdvolume aan de luidspreker), resumes = AudioContext.resume-aanroepen.
let starts = 0;
let resumes = 0;
const luidspreker = {};
const nepParam = () => ({ setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {},
  cancelScheduledValues() {} });
const nepKnoop = extra => Object.assign({ connect: x => { if (x === luidspreker) starts += 1; return x; },
  disconnect() {} }, extra);
if (process.env.BLUESLAB_AUDIO === "1") {
  ctx.AudioContext = function AudioContext() {
    return { currentTime: 0, destination: luidspreker, resume: async () => { resumes += 1; },
      decodeAudioData: async () => ({}),
      createGain: () => nepKnoop({ gain: nepParam() }),
      createBufferSource: () => nepKnoop({ playbackRate: {}, start() {}, stop() {} }),
      createOscillator: () => nepKnoop({ frequency: {}, start() {}, stop() {} }) };
  };
}
vm.createContext(ctx);
for (const f of ["speler.js", "app.js"]) {
  vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "web", f), "utf8"), ctx);
}
luisteraars.DOMContentLoaded();
// Optioneel: BLUESLAB_ACTIES = JSON ["data-nr=3", "tekst=▶ Speel", ...]: klik na het laden
// op het laatst gemaakte element met dat attribuut of die tekst.
const acties = JSON.parse(process.env.BLUESLAB_ACTIES || "[]");
const inKlik = [];  // resume-aanroepen synchroon binnen elke klik
(async () => {
  await wacht(50);
  for (const a of acties) {
    const [k, v] = a.split("=");
    const doel = gemaakt.filter(e => (k === "tekst" ? e._tekst === v : String(e._attrs[k]) === v)).pop();
    if (!doel || !doel._on.click) throw new Error(`niets om te klikken: ${a}`);
    const voor = resumes;
    doel._on.click();
    inKlik.push(resumes - voor);
    await wacht(20);
  }
  await wacht(30);
  const knop = gemaakt.filter(e => e.className === "speelknop").pop();
  const speelknop = () => (knop ? { tekst: knop._tekst, uit: "disabled" in knop._attrs } : null);
  console.log(JSON.stringify({ navigaties, login_zichtbaar: !nepElement("#login").hidden,
    fout: nepElement("#fout").textContent, luisterNaar, wakelock, nullKinderen,
    speler_zichtbaar: !nepElement("#speler").hidden, maatvakken, fetches, starts,
    audiosessie: ctx.navigator.audioSession.type, resumes, inKlik,
    hulp: nepElement("#hulp").textContent, speelknop: speelknop() }));
  process.exit(0);  // een spelende Speler houdt anders de klok (setInterval) open
})();
