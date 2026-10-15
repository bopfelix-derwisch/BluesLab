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
