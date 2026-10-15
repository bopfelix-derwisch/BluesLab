// BluesLab — meespeel-begeleiding (oefenen). Vanilla JS, geen build-stap.
// Puur deel (akkoordMidi, tellenUit, speelplan) wordt met node getest;
// Speler en speelGeluid praten met Web Audio.
"use strict";

const NOOT_PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const VOORTEKEN = { "♭": -1, b: -1, "♯": 1, "#": 1 };
// Gespiegeld aan core/chords.py (TRIADS, EXTENSIONS, DIM7), alleen de halve tonen.
const DRIEKLANK = { maj: [0, 4, 7], min: [0, 3, 7], dim: [0, 3, 6], aug: [0, 4, 8],
  sus2: [0, 2, 7], sus4: [0, 5, 7] };
const EXTENSIE = { "": [], "7": [10], maj7: [11], "6": [9], "9": [10, 14], add9: [14] };
const NC_TEKSTEN = ["N.C.", "N.C", "NC"];

const eersteVan = (s, paren) => paren.find(([t]) => s.startsWith(t));

// "Bbm7" -> [pc, "m7"], of null zonder grondtoon.
function leesNoot(s) {
  if (!s || !(s[0] in NOOT_PC)) return null;
  let pc = NOOT_PC[s[0]];
  let rest = s.slice(1);
  if (rest && rest[0] in VOORTEKEN) { pc += VOORTEKEN[rest[0]]; rest = rest.slice(1); }
  return [(pc + 12) % 12, rest];
}

// Achtervoegsel -> [kwaliteit, extensie], of null bij iets onbekends (zoals core/chords.py).
function leesAchtervoegsel(s) {
  let kwaliteit = "maj";
  const k = eersteVan(s, [["min", "min"], ["dim", "dim"], ["aug", "aug"],
    ["°", "dim"], ["+", "aug"], ["-", "min"]]);
  if (k) { kwaliteit = k[1]; s = s.slice(k[0].length); }
  else if (s.startsWith("m") && !s.startsWith("maj")) { kwaliteit = "min"; s = s.slice(1); }
  let extensie = "";
  const e = eersteVan(s, [["maj7", "maj7"], ["M7", "maj7"], ["add9", "add9"],
    ["7", "7"], ["6", "6"], ["9", "9"]]);
  if (e) { extensie = e[1]; s = s.slice(e[0].length); }
  const sus = eersteVan(s, [["sus2", "sus2"], ["sus4", "sus4"], ["sus", "sus4"]]);
  if (sus) {
    if (kwaliteit !== "maj") return null;
    kwaliteit = sus[1];
    s = s.slice(sus[0].length);
  }
  return s ? null : [kwaliteit, extensie];
}

// Concert-akkoordnaam -> {nc: false, bas, akkoord} in MIDI; {nc: true} bij N.C.; null als onleesbaar.
function akkoordMidi(tekst) {
  const t = String(tekst || "").trim();
  if (NC_TEKSTEN.includes(t.replace(/ /g, "").toUpperCase())) return { nc: true };
  const slash = t.indexOf("/");
  const grond = leesNoot(slash < 0 ? t : t.slice(0, slash));
  const soort = grond && leesAchtervoegsel(grond[1]);
  if (!soort) return null;
  let basPc = grond[0];
  if (slash >= 0) {
    const b = leesNoot(t.slice(slash + 1));
    if (!b || b[1]) return null;
    basPc = b[0];
  }
  const [kwaliteit, extensie] = soort;
  const stappen = kwaliteit === "dim" && extensie === "7" ? [0, 3, 6, 9]
    : DRIEKLANK[kwaliteit].concat(EXTENSIE[extensie]);
  const laag = 52 + ((grond[0] - 4 + 12) % 12);  // grondtoon tussen E3 (52) en E♭4 (63)
  return { nc: false, bas: 36 + basPc, akkoord: stappen.map(s => laag + s) };
}

// "3/4" -> 3; leeg of onzin -> 4.
function tellenUit(maatsoort) {
  const n = parseInt(String(maatsoort || "").split("/")[0], 10);
  return n >= 1 && n <= 12 ? n : 4;
}

const TIK_DUUR = 0.03;

// Schema-maten -> {gebeurtenissen: [{t, soort, midi, duur, maat}], duur} in seconden.
// start/eind: maatnummers (inclusief). inteltel: tikken vooraf (maat null).
// Per tel een tik; bas op de eerste tel van elk akkoord (en op even tellen), anders het akkoord.
function speelplan(maten, { bpm, tellen = 4, start = -Infinity, eind = Infinity, inteltel = tellen }) {
  const tel = 60 / bpm;
  const g = [];
  for (let i = 0; i < inteltel; i++) g.push({ t: i * tel, soort: "tik", midi: [], duur: TIK_DUUR, maat: null });
  const gekozen = maten.filter(m => m.nr >= start && m.nr <= eind);
  gekozen.forEach((m, mi) => {
    const begin = (inteltel + mi * tellen) * tel;
    const akk = m.akkoorden.map(a => akkoordMidi(a.concert));
    const n = akk.length;
    for (let b = 0; b < tellen; b++) {
      const t = begin + b * tel;
      g.push({ t, soort: "tik", midi: [], duur: TIK_DUUR, maat: m.nr });
      if (!n) continue;
      const k = Math.floor(b * n / tellen);
      const a = akk[k];
      if (!a || a.nc) continue;
      const eerste = b === Math.ceil(k * tellen / n);
      if (eerste || (tellen % 2 === 0 && b % 2 === 0)) {
        g.push({ t, soort: "bas", midi: [a.bas], duur: 0.9 * tel, maat: m.nr });
      } else {
        g.push({ t, soort: "akkoord", midi: a.akkoord, duur: 0.5 * tel, maat: m.nr });
      }
    }
  });
  return { gebeurtenissen: g, duur: (inteltel + gekozen.length * tellen) * tel };
}

const VOORUIT = 0.12;  // seconden vooruit plannen
const KLOK_MS = 25;

function kanSpelen() {
  return typeof AudioContext !== "undefined" || typeof webkitAudioContext !== "undefined";
}

function nieuweContext() {
  return typeof AudioContext !== "undefined" ? new AudioContext() : new webkitAudioContext();
}

const hz = midi => 440 * Math.pow(2, (midi - 69) / 12);
const KLANK = { bas: ["triangle", 0.35], akkoord: ["triangle", 0.1], tik: ["square", 0.04] };

// Eén gebeurtenis als korte toon(en) met een envelop; inteltikken klinken hoger.
function speelGeluid(ctx, e, wanneer) {
  const [vorm, sterkte] = KLANK[e.soort];
  const tonen = e.soort === "tik" ? [e.maat === null ? 96 : 84] : e.midi;
  for (const m of tonen) {
    const osc = ctx.createOscillator();
    const vol = ctx.createGain();
    osc.type = vorm;
    osc.frequency.value = hz(m);
    vol.gain.setValueAtTime(0.0001, wanneer);
    vol.gain.linearRampToValueAtTime(sterkte, wanneer + 0.005);
    vol.gain.exponentialRampToValueAtTime(0.0001, wanneer + e.duur);
    osc.connect(vol).connect(ctx.destination);
    osc.start(wanneer);
    osc.stop(wanneer + e.duur + 0.02);
  }
}

// Speelt een speelplan op de AudioContext-klok; `herhaal` volgt daarna eindeloos.
class Speler {
  constructor({ maakContext = nieuweContext, geluid = speelGeluid,
    opMaat = () => {}, opKlaar = () => {} } = {}) {
    Object.assign(this, { maakContext, geluid, opMaat, opKlaar });
    this.ctx = null;
    this.speelt = false;
    this.klok = null;
    this.wekkers = [];
  }

  start(plan, herhaal = null) {
    this.stop();
    if (!this.ctx) this.ctx = this.maakContext();
    if (this.ctx.resume) this.ctx.resume();  // iOS: mag alleen binnen een tik
    this.plan = plan;
    this.herhaal = herhaal && herhaal.duur > 0 ? herhaal : null;
    this.i = 0;
    this.laatsteMaat = undefined;
    this.t0 = this.ctx.currentTime + 0.1;
    this.speelt = true;
    this.klok = setInterval(() => this.vooruit(this.ctx.currentTime + VOORUIT), KLOK_MS);
    this.vooruit(this.ctx.currentTime + VOORUIT);
  }

  // Plant alle gebeurtenissen die vóór `tot` (contextklok) beginnen.
  vooruit(tot) {
    while (this.speelt) {
      if (this.i >= this.plan.gebeurtenissen.length) {
        if (!this.herhaal) { this.einde(); return; }
        this.t0 += this.plan.duur;
        this.plan = this.herhaal;
        this.i = 0;
        continue;
      }
      const e = this.plan.gebeurtenissen[this.i];
      const wanneer = this.t0 + e.t;
      if (wanneer >= tot) return;
      this.geluid(this.ctx, e, wanneer);
      if (e.maat !== this.laatsteMaat) {
        this.laatsteMaat = e.maat;
        this.wek(wanneer, () => this.opMaat(e.maat));
      }
      this.i++;
    }
  }

  einde() {  // alles gepland: na de laatste tel netjes stoppen
    clearInterval(this.klok);
    this.klok = null;
    this.wek(this.t0 + this.plan.duur, () => this.stop());
  }

  wek(wanneer, f) {
    this.wekkers.push(setTimeout(f, Math.max(0, (wanneer - this.ctx.currentTime) * 1000)));
  }

  stop() {
    const speelde = this.speelt;
    this.speelt = false;
    clearInterval(this.klok);
    this.klok = null;
    this.wekkers.forEach(w => clearTimeout(w));
    this.wekkers = [];
    if (speelde) { this.opMaat(null); this.opKlaar(); }
  }
}
