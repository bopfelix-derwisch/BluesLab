// BluesLab — gedeelde frontend-logica (BL-2). Vanilla JS, geen build-stap.
"use strict";

const INSTRUMENTEN = { bb: "Bes klarinet", eb: "Alt sax" };

function $(sel) { return document.querySelector(sel); }

function el(tag, attrs = {}, ...kinderen) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kinderen.flat()) {
    if (k !== null && k !== undefined) e.append(k instanceof Node ? k : String(k));
  }
  return e;
}

// "Bbm7/Eb" -> "B♭m7/E♭", "F#" -> "F♯" (alleen voortekens direct na een notenletter).
function mooi(naam) {
  if (!naam) return "";
  return naam.replace(/([A-G])b/g, "$1♭").replace(/([A-G])#/g, "$1♯");
}

function param(naam) { return new URLSearchParams(location.search).get(naam); }

// Per deel: start_maat van het eerste eerdere deel met precies dezelfde akkoorden, anders null.
function herhalingen(delen) {
  const vingerafdruk = d => d.maten.map(m => m.akkoorden.map(a => a.concert).join(" ")).join("|");
  const gezien = {};
  return delen.map(d => {
    const v = vingerafdruk(d);
    if (v in gezien) return gezien[v];
    gezien[v] = d.start_maat;
    return null;
  });
}

// Vorig en volgend nummer in de setlist-volgorde (ids), of null.
function buren(songs, id) {
  const i = songs.findIndex(s => s.id === id);
  if (i < 0) return { vorige: null, volgende: null };
  return { vorige: i > 0 ? songs[i - 1].id : null,
    volgende: i < songs.length - 1 ? songs[i + 1].id : null };
}

function instrument() {
  try { return localStorage.getItem("instrument") === "eb" ? "eb" : "bb"; }
  catch { return "bb"; }
}
function zetInstrument(i) {
  try { localStorage.setItem("instrument", i); } catch { /* privé-venster: negeren */ }
}

function toonFout(tekst) {
  const vak = $("#fout");
  if (!vak) { alert(tekst); return; }
  vak.textContent = tekst;
  vak.hidden = !tekst;
}

async function api(pad, opties = {}) {
  const init = { credentials: "same-origin", ...opties };
  if (opties.json !== undefined) {
    init.method = init.method || "POST";
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(opties.json);
  }
  const r = await fetch(pad, init);
  // Niet ingelogd: naar de loginpagina, behalve als we daar al zijn (anders herlaadlus).
  if (r.status === 401 && !pad.endsWith("/login") && document.body.dataset.pagina !== "index") {
    location.href = "index.html";
    throw new Error("Log eerst in.");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = data.detail;
    const tekst = Array.isArray(d) ? d.map(x => (typeof x === "string" ? x : x.msg)).join("\n")
      : (d || `Fout ${r.status}`);
    throw new Error(tekst);
  }
  return data;
}

function instrumentKnoppen(bijWissel) {
  const huidig = instrument();
  return el("div", { class: "wissel", role: "group", "aria-label": "Instrument" },
    Object.entries(INSTRUMENTEN).map(([code, label]) =>
      el("button", {
        type: "button", "aria-pressed": String(code === huidig),
        onclick: () => { zetInstrument(code); bijWissel(code); },
      }, label)));
}

// --- index.html: login + setlists -----------------------------------------
async function paginaIndex() {
  const login = $("#login"), lijst = $("#setlists");
  try {
    await api("/api/ik");
  } catch {
    // Het formulier post zelf naar /login (geen fetch: iOS Safari bewaarde die cookie niet).
    login.hidden = false;
    const fouten = { wachtwoord: "Onjuist wachtwoord.", limiet: "Te veel pogingen. Wacht een minuut." };
    if (fouten[param("fout")]) toonFout(fouten[param("fout")]);
    return;
  }
  lijst.hidden = false;
  $("#nieuwe-setlist").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const { id } = await api("/api/setlists", { json: { naam: $("#setlist-naam").value } });
      location.href = `setlist.html?id=${id}`;
    } catch (e) { toonFout(e.message); }
  });
  $("#uitloggen").addEventListener("click", async () => {
    await api("/api/logout", { method: "POST" });
    location.reload();
  });
  const sets = await api("/api/setlists");
  $("#setlist-lijst").replaceChildren(...sets.map(s =>
    el("li", {}, el("a", { href: `setlist.html?id=${s.id}` }, s.naam),
      el("span", { class: "klein" }, ` · ${s.aantal} nummers`))));
}

// --- setlist.html -----------------------------------------------------------
async function paginaSetlist() {
  const id = param("id");
  let setlist;

  async function laad() {
    setlist = await api(`/api/setlists/${id}`);
    $("#titel").textContent = setlist.naam;
    document.title = `${setlist.naam} · BluesLab`;
    teken();
  }

  function teken() {
    const inst = instrument();
    $("#instrument").replaceChildren(instrumentKnoppen(teken));
    $("#songs").replaceChildren(...setlist.songs.map((s, i) => {
      const doel = s.status === "gecontroleerd" ? `song.html?id=${s.id}` : `controle.html?id=${s.id}`;
      return el("li", { class: "song" },
        el("a", { href: doel }, el("strong", {}, s.titel), " ",
          el("span", { class: "klein" }, s.artiest)),
        el("span", { class: "sleutel" }, mooi(s.sleutels[inst]) || "?"),
        s.status !== "gecontroleerd" ? el("span", { class: "badge" }, "controleren") : null,
        el("span", { class: "acties" },
          el("button", { type: "button", "aria-label": "Omhoog", disabled: i === 0,
            onclick: () => verplaats(i, -1) }, "▲"),
          el("button", { type: "button", "aria-label": "Omlaag",
            disabled: i === setlist.songs.length - 1, onclick: () => verplaats(i, 1) }, "▼"),
          el("button", { type: "button", "aria-label": "Verwijderen",
            onclick: () => verwijder(s) }, "✕")));
    }));
  }

  async function verplaats(i, stap) {
    const ids = setlist.songs.map(s => s.id);
    [ids[i], ids[i + stap]] = [ids[i + stap], ids[i]];
    try {
      await api(`/api/setlists/${id}/volgorde`, { method: "PUT", json: { song_ids: ids } });
      await laad();
    } catch (e) { toonFout(e.message); }
  }

  async function verwijder(s) {
    if (!confirm(`"${s.titel}" verwijderen?`)) return;
    try { await api(`/api/songs/${s.id}`, { method: "DELETE" }); await laad(); }
    catch (e) { toonFout(e.message); }
  }

  $("#pdfs").addEventListener("change", async (ev) => {
    const bestanden = [...ev.target.files];
    const status = $("#upload-status");
    toonFout("");
    for (const [n, f] of bestanden.entries()) {
      status.textContent = `PDF ${n + 1} van ${bestanden.length} lezen: ${f.name} (duurt ± een minuut)…`;
      const fd = new FormData();
      fd.append("bestand", f);
      try {
        await api(`/api/setlists/${id}/songs`, { method: "POST", body: fd });
      } catch (e) {
        toonFout(`${f.name}: ${e.message}`);
      }
      await laad();
    }
    status.textContent = "";
    ev.target.value = "";
  });

  await laad();
}

// --- controle.html ----------------------------------------------------------
async function paginaControle() {
  const id = param("id");
  const song = await api(`/api/songs/${id}`);
  document.title = `Controle: ${song.titel} · BluesLab`;
  $("#titel-veld").value = song.titel;
  $("#artiest-veld").value = song.artiest;
  $("#tempo-veld").value = song.tempo == null ? "" : song.tempo;
  $("#voortekening-veld").value = song.voortekening;
  if (song.onparseerbaar.length) {
    $("#waarschuwing").hidden = false;
    $("#waarschuwing").textContent = "Onbekende akkoorden: " +
      song.onparseerbaar.map(o => `maat ${o.maat}: ${o.akkoord}`).join(", ");
  }

  const regels = song.regels.map(r => ({ start_maat: r.start_maat, maten: r.maten.map(m => m.join(" ")) }));
  const delen = song.delen.map(d => ({ ...d }));

  function tekenRegels() {
    $("#regels").replaceChildren(...regels.map((r, ri) => {
      const volgende = regels[ri + 1];
      const verwacht = volgende ? volgende.start_maat - r.start_maat : null;
      const fout = verwacht !== null && verwacht !== r.maten.length;
      return el("div", { class: fout ? "regel fout" : "regel" },
        el("div", { class: "regelkop" }, `Maat ${r.start_maat}`,
          fout ? el("span", { class: "klein" },
            ` · ${r.maten.length} maten, ${verwacht} verwacht`) : null),
        el("div", { class: "maten" },
          r.maten.map((m, mi) => el("input", {
            class: "maat", value: m, "aria-label": `Regel ${r.start_maat}, maat ${mi + 1}`,
            oninput: (ev) => { r.maten[mi] = ev.target.value; },
          })),
          el("button", { type: "button", "aria-label": "Maat toevoegen",
            onclick: () => { r.maten.push(""); tekenRegels(); } }, "+"),
          el("button", { type: "button", "aria-label": "Laatste maat weghalen",
            disabled: r.maten.length === 0,
            onclick: () => { r.maten.pop(); tekenRegels(); } }, "−")));
    }));
  }

  function tekenDelen() {
    $("#delen").replaceChildren(...delen.map((d, di) => el("div", { class: d.afwijking ? "deel fout" : "deel" },
      el("input", { value: d.naam, "aria-label": "Naam", oninput: (e) => { d.naam = e.target.value; } }),
      el("input", { type: "number", value: d.start_maat, "aria-label": "Van maat",
        oninput: (e) => { d.start_maat = Number(e.target.value); } }),
      el("input", { type: "number", value: d.eind_maat, "aria-label": "Tot en met maat",
        oninput: (e) => { d.eind_maat = Number(e.target.value); } }),
      el("input", { value: d.concert_key, "aria-label": "Toonsoort (concert)",
        oninput: (e) => { d.concert_key = e.target.value; d.key_source = "handmatig"; } }),
      el("label", {}, el("input", { type: "checkbox", checked: d.solo_geschikt,
        onchange: (e) => { d.solo_geschikt = e.target.checked; } }), " solo"),
      el("button", { type: "button", "aria-label": "Deel verwijderen",
        onclick: () => { delen.splice(di, 1); tekenDelen(); } }, "✕"),
      d.afwijking ? el("div", { class: "klein" },
        `Engine denkt ${mooi(d.engine_key)}, Claude ${mooi(d.concert_key)}. Kies zelf.`) : null,
      d.reden ? el("div", { class: "klein" }, d.reden) : null)));
  }

  $("#deel-toevoegen").addEventListener("click", () => {
    const laatste = delen[delen.length - 1];
    delen.push({ naam: "Couplet", start_maat: laatste ? laatste.eind_maat + 1 : 1,
      eind_maat: laatste ? laatste.eind_maat + 1 : 1,
      concert_key: laatste ? laatste.concert_key : "", key_source: "handmatig",
      solo_geschikt: false, reden: "" });
    tekenDelen();
  });

  $("#opslaan").addEventListener("click", async () => {
    toonFout("");
    const body = {
      titel: $("#titel-veld").value,
      artiest: $("#artiest-veld").value,
      tempo: $("#tempo-veld").value === "" ? null : Number($("#tempo-veld").value),
      voortekening: Number($("#voortekening-veld").value || 0),
      regels: regels.map(r => ({ start_maat: r.start_maat,
        maten: r.maten.map(m => m.split(/\s+/).filter(Boolean)) })),
      delen: delen.map(({ naam, start_maat, eind_maat, concert_key, key_source, solo_geschikt, reden }) =>
        ({ naam, start_maat, eind_maat, concert_key, key_source, solo_geschikt, reden })),
    };
    try {
      await api(`/api/songs/${id}`, { method: "PUT", json: body });
      location.href = `song.html?id=${id}`;
    } catch (e) { toonFout(e.message); }
  });

  tekenRegels();
  tekenDelen();
}

// --- song.html: oefenen (fragment + meespelen) --------------------------------
// iTunes-zoekresultaten -> de gekozen preview (index loopt rond), of null.
// Precies de titel gaat voor, dan "begint met de titel": iTunes zet soms een
// ander nummer of een akoestische versie bovenaan.
function kiesFragment(resultaten, index, titel = "") {
  const t = titel.trim().toLowerCase();
  const past = r => {
    const naam = String(r.trackName || "").toLowerCase();
    return naam === t ? 0 : naam.startsWith(t) ? 1 : 2;
  };
  const met = (resultaten || []).filter(r => r.previewUrl)
    .map((r, i) => [past(r), i, r]).sort((x, y) => x[0] - y[0] || x[1] - y[1])
    .map(x => x[2]).slice(0, 5);
  if (!met.length) return null;
  const i = ((index % met.length) + met.length) % met.length;
  return { url: met[i].previewUrl, track: met[i].trackName, artiest: met[i].artistName,
    index: i, aantal: met.length };
}

function fragmentZoekUrl(titel, artiest) {
  const term = encodeURIComponent(`${titel} ${artiest || ""}`.trim());
  return `https://itunes.apple.com/search?term=${term}&entity=song&country=NL&limit=10`;
}

// Welke maten de begeleiding speelt: vanaf de startmaat tot het eind, of (herhaal)
// tot het eind van het deel van de startmaat, waarna dat hele deel herhaalt.
function speelBereik(delen, start, herhaal) {
  if (!delen.length) return { start: 1, eind: 0, lusStart: 1 };
  const s = start === null ? delen[0].start_maat : start;
  const d = herhaal && delen.find(x => s >= x.start_maat && s <= x.eind_maat);
  if (d) return { start: s, eind: d.eind_maat, lusStart: d.start_maat };
  return { start: s, eind: delen[delen.length - 1].eind_maat, lusStart: s };
}

// --- song.html: speelschema ---------------------------------------------------
// Scherm aan houden tijdens het spelen (Safari 16.4+); stil negeren waar het niet kan.
function houdSchermAan() {
  if (typeof navigator === "undefined" || !navigator.wakeLock) return;
  const vraag = () => navigator.wakeLock.request("screen").catch(() => {});
  vraag();
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") vraag();
  });
}

async function zetNavigatie(setlistId, id) {
  $("#terug").href = `setlist.html?id=${setlistId}`;
  const sl = await api(`/api/setlists/${setlistId}`);
  const b = buren(sl.songs, id);
  for (const [sel, sid] of [["#vorige", b.vorige], ["#volgende", b.volgende]]) {
    const a = $(sel);
    a.hidden = sid === null;
    if (sid !== null) a.href = `song.html?id=${sid}`;
  }
}

function maatRaster(maten, opTik) {
  return el("div", { class: "maatraster" }, maten.map(m => el("div",
    { class: "maatvak", "data-nr": m.nr, onclick: () => opTik(m.nr) },
    el("span", { class: "nr" }, m.nr),
    el("div", { class: "akkoord" }, m.akkoorden.map(a =>
      a.fout ? el("span", { class: "fout", title: a.fout }, `⚠ ${a.concert}`) : mooi(a.geschreven))
      .flatMap((x, i) => (i ? [" ", x] : [x]))),
    el("div", { class: "tonen" }, m.akkoorden.filter(a => !a.fout)
      .map(a => a.tonen.map(mooi).join(" ")).join(" | ")),
    m.doeltoon ? el("div", { class: "doel" }, `→ ${mooi(m.doeltoon)}`) : null)));
}

// Cursor op het klinkende maatvak (null = weg); een ingeklapte herhaling gaat open.
function zetCursor(nr) {
  const oud = $(".maatvak.speelt");
  if (oud) oud.classList.remove("speelt");
  if (nr === null) return;
  const vak = $(`.maatvak[data-nr="${nr}"]`);
  if (!vak) return;
  const dicht = vak.closest("details");
  if (dicht) dicht.open = true;
  vak.classList.add("speelt");
  vak.scrollIntoView({ block: "center", behavior: "smooth" });
}

let fragmentAudio = null;

// Fragment van de echte opname (iTunes, 30 s); de keuze wordt per nummer onthouden.
async function toonFragment(s, bijAfspelen) {
  const vak = $("#fragment");
  let resultaten;
  try {
    const r = await fetch(fragmentZoekUrl(s.titel, s.artiest));
    if (!r.ok) throw new Error(String(r.status));
    resultaten = (await r.json()).results;
  } catch {
    vak.replaceChildren(el("span", { class: "klein" }, "Fragment niet beschikbaar."));
    return;
  }
  const sleutel = `fragment-${s.id}`;
  let index = 0;
  try { index = Number(localStorage.getItem(sleutel)) || 0; } catch { /* geen opslag */ }
  const audio = el("audio", { preload: "none" });
  fragmentAudio = audio;
  let knop = null;
  let label = () => "";
  for (const t of ["play", "pause", "ended"]) {
    audio.addEventListener(t, () => { if (knop) knop.textContent = label(t === "play"); });
  }
  function teken() {
    const f = kiesFragment(resultaten, index, s.titel);
    if (!f) { vak.replaceChildren(el("span", { class: "klein" }, "Geen fragment gevonden.")); return; }
    audio.src = f.url;
    label = speelt => `${speelt ? "❚❚" : "▶"} Fragment — ${f.track} · ${f.artiest}`;
    knop = el("button", { class: "fragmentknop", onclick: () => {
      if (audio.paused) { bijAfspelen(); audio.play().catch(() => {}); } else audio.pause();
    } }, label(false));
    vak.replaceChildren(...[knop, f.aantal > 1 ? el("button", { class: "stil", onclick: () => {
      audio.pause();
      index = f.index + 1;
      try { localStorage.setItem(sleutel, String(index)); } catch { /* geen opslag */ }
      teken();
    } }, "Ander fragment") : null].filter(Boolean));
  }
  teken();
}

async function paginaSong() {
  const id = Number(param("id"));
  $("#naar-controle").href = `controle.html?id=${id}`;
  houdSchermAan();
  let eersteKeer = true;
  let schema = null;
  const oefen = { start: null, tempo: 100, herhaal: false };
  const speler = kanSpelen() ? new Speler({ opMaat: zetCursor, opKlaar: () => tekenSpeler() }) : null;
  // Piano: één laadpoging per pagina (nieuw → laden → klaar of mislukt).
  let piano = "nieuw";
  // Weg geweest tijdens het laden: daarna niet alsnog starten. iOS bevriest JS op de
  // achtergrond, dus het laden is vaak pas klaar als de pagina alweer zichtbaar is.
  let wegTijdensLaden = false;

  function markeerStart() {
    const oud = $(".maatvak.start");
    if (oud) oud.classList.remove("start");
    const vak = oefen.start === null ? null : $(`.maatvak[data-nr="${oefen.start}"]`);
    if (vak) vak.classList.add("start");
  }

  // Tik op een maat = startpunt; nog eens tikken = weer vanaf het begin.
  // Speelt de begeleiding al, dan begint hij meteen daar.
  function kiesStart(nr) {
    oefen.start = oefen.start === nr ? null : nr;
    markeerStart();
    if (speler) wijzig(() => {});
  }

  async function speelKnop() {
    if (speler.speelt) { speler.stop(); return; }
    if (piano === "laden") return;
    const ctx = speler.ontgrendel();  // binnen de tik, vóór de await (iOS)
    if (piano === "nieuw") {
      piano = "laden";
      wegTijdensLaden = false;
      tekenSpeler();
      try {
        speler.geluid = pianoGeluid(await binnen(laadPiano(ctx), 10000));
        piano = "klaar";
      } catch (e) {
        piano = "mislukt";
        $("#hulp").textContent = "Piano niet geladen — eenvoudige klank. Tik op een maat om daar te beginnen.";
      }
      if (wegTijdensLaden || document.visibilityState === "hidden") { tekenSpeler(); return; }
    }
    speel();
  }

  function speel() {
    if (fragmentAudio) fragmentAudio.pause();
    const maten = schema.delen.flatMap(d => d.maten);
    const tellen = tellenUit(schema.maatsoort);
    const bpm = (schema.tempo || 100) * oefen.tempo / 100;
    const b = speelBereik(schema.delen, oefen.start, oefen.herhaal);
    speler.start(speelplan(maten, { bpm, tellen, start: b.start, eind: b.eind, stijl: "shuffle" }),
      oefen.herhaal ? speelplan(maten, { bpm, tellen, start: b.lusStart, eind: b.eind, inteltel: 0,
        stijl: "shuffle" }) : null);
    tekenSpeler();
  }

  // Instelling wijzigen; speelt de begeleiding al, dan opnieuw starten.
  function wijzig(f) {
    f();
    if (speler.speelt) speel(); else tekenSpeler();
  }

  function tekenSpeler() {
    const vanaf = speelBereik(schema.delen, oefen.start, false).start;
    $("#speler").replaceChildren(
      el("button", { class: "speelknop", disabled: piano === "laden", onclick: speelKnop },
        piano === "laden" ? "Piano laden…" : speler.speelt ? "■ Stop" : "▶ Speel"),
      el("span", { class: "klein" }, `vanaf maat ${vanaf}`),
      el("div", { class: "wissel tempo" }, [50, 75, 100].map(p => el("button",
        { "aria-pressed": String(p === oefen.tempo), onclick: () => wijzig(() => { oefen.tempo = p; }) },
        `${p}%`))),
      el("button", { class: "stil herhaal", "aria-pressed": String(oefen.herhaal),
        onclick: () => wijzig(() => { oefen.herhaal = !oefen.herhaal; }) },
        oefen.herhaal ? "🔁 Herhaal dit deel: aan" : "🔁 Herhaal dit deel"));
  }

  async function laad(inst) {
    const s = await api(`/api/songs/${id}/schema?instrument=${inst}`);
    schema = s;
    document.title = `${s.titel} · BluesLab`;
    if (eersteKeer) {
      eersteKeer = false;
      zetNavigatie(s.setlist_id, id).catch(() => { /* navigatie is bijzaak */ });
      toonFragment(s, () => { if (speler) speler.stop(); });
      if (speler) {
        $("#speler").hidden = false;
        $("#hulp").hidden = false;
        document.addEventListener("visibilitychange", () => {
          if (document.visibilityState !== "hidden") return;
          speler.stop();
          if (piano === "laden") wegTijdensLaden = true;
        });
      }
    }
    $("#balk-titel").textContent = s.titel;
    $("#instrument").replaceChildren(instrumentKnoppen(laad));
    $("#kop").replaceChildren(...[
      el("h1", {}, s.titel), el("div", { class: "klein" }, s.artiest),
      el("div", { class: "kopinfo" },
        s.tempo ? el("span", {}, `♩ = ${s.tempo}`) : null,
        el("span", {}, `concert ${mooi(s.concert_key)}`),
        el("span", { class: "sleutel" }, `${INSTRUMENTEN[inst]}: ${mooi(s.geschreven_key)}`)),
      s.status !== "gecontroleerd" ? el("div", { class: "badge" }, "Nog niet gecontroleerd") : null,
    ].filter(Boolean));  // replaceChildren maakt van null de tekst "null"

    const herh = herhalingen(s.delen);
    $("#sprong").replaceChildren(...s.delen.map((d, i) =>
      el("a", { class: "chip", href: `#deel-${i}` }, `${d.naam} ${d.start_maat}`)));
    $("#schema").replaceChildren(...s.delen.map((d, i) => {
      const titel = [el("span", { class: "deelnaam" }, d.naam), " ",
        el("span", { class: "klein" }, `maat ${d.start_maat}–${d.eind_maat}`)];
      const inhoud = [
        d.wissel ? el("div", { class: "wisselmelding" }, `Toonsoortwissel → ${mooi(d.geschreven_key)}`) : null,
        el("div", { class: "klein" }, `Toonsoort ${mooi(d.geschreven_key)} · ladder `,
          el("span", { class: "ladder" }, d.toonladder.map(mooi).join(" "))),
        maatRaster(d.maten, kiesStart)];
      const klasse = d.wissel ? "deel wissel-deel" : "deel";
      // Herhaling zonder toonsoortwissel: ingeklapt, met een tik open te klappen.
      if (herh[i] !== null && !d.wissel) {
        return el("details", { class: klasse, id: `deel-${i}` },
          el("summary", {}, ...titel, el("span", { class: "klein" },
            ` — zoals ${s.delen.find(x => x.start_maat === herh[i]).naam} (maat ${herh[i]})`)),
          ...inhoud);
      }
      return el("section", { class: klasse, id: `deel-${i}` }, el("h2", {}, ...titel), ...inhoud);
    }));
    markeerStart();
    if (speler) tekenSpeler();
  }

  await laad(instrument());
}

document.addEventListener("DOMContentLoaded", () => {
  const paginas = { index: paginaIndex, setlist: paginaSetlist, controle: paginaControle, song: paginaSong };
  const pagina = paginas[document.body.dataset.pagina];
  if (pagina) pagina().catch(e => toonFout(e.message));
});
