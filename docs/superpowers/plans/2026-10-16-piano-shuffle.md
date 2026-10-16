# Meespelen met piano en shuffle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De meespeel-begeleiding op de songpagina klinkt als een bluespiano in shuffle (echte pianosamples), met een zachte tik, en valt terug op de oude klank als de piano niet laadt.

**Architecture:** `speelplan` (puur, `web/speler.js`) krijgt een shuffle-stijl die dezelfde gebeurtenissen `{t, soort, midi, duur, maat}` maakt, zodat `Speler` en de cursor niet veranderen. Nieuw in `web/speler.js`: `laadPiano` (15 mp3-samples ophalen en decoderen), `pianoGeluid` (geluidsfunctie met dezelfde vorm als `speelGeluid`), `binnen` (tijdslimiet) en `Speler.ontgrendel()` (audio aanzetten binnen de tik). `web/app.js` laadt de piano bij de eerste ▶ en geeft `stijl: "shuffle"` mee.

**Tech Stack:** vanilla JS (geen build, node v12-compatibel: geen `?.`/`??`), Web Audio (`AudioBufferSourceNode`), ffmpeg + curl voor de samples, pytest + node voor de tests.

**Spec:** `docs/superpowers/specs/2026-10-16-piano-shuffle-design.md`

## Global Constraints

- Node op orin3 is **v12**: geen `?.` of `??` in `web/*.js`.
- Geen serverwijziging; samples in `web/piano/<midi>.mp3`, geserveerd door de bestaande StaticFiles.
- Samples: **Salamander Grand Piano (Alexander Holm, CC-BY 3.0)**, bron `https://tonejs.github.io/audio/salamander/`; naamsvermelding in de hulptekst en de README.
- `PIANO_NOTEN = [36, 39, 42, 45, 48, 51, 54, 57, 60, 63, 66, 69, 72, 75, 78]` (C2 t/m F♯5, elke kleine terts).
- Shuffle alleen bij 4 tellen; andere maatsoorten houden het rechte patroon.
- Tijdslimiet piano laden: **10 s**; daarna oude klank en melding "Piano niet geladen — eenvoudige klank."
- Bij elke wijziging aan `app.js`/`speler.js`: `?v=` verhogen (`app.js?v=7` in alle vier `web/*.html`, `speler.js?v=3` in `song.html`).
- UI-tekst Nederlands. Tests: `.venv/bin/python -m pytest -q` (suite nu 180 passed, 1 skipped).
- Commit-trailer:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_011HT47tgB5e8kbi5GEnQEKY
  ```

## Review Focus

1. **Volgorde van gebeurtenissen**: `Speler.vooruit` plant op volgorde en stopt bij de eerste toekomstige gebeurtenis; staat een gebeurtenis te vroeg in de lijst, dan valt er een gat. De shuffle moet op `t` gesorteerd blijven, ook bij drie akkoorden in een maat → test in Task 1.
2. **iOS-ontgrendeling**: het laden van de piano is async; zet de app de audio pas aan ná een `await`, dan blijft de iPad stil. `ontgrendel()` moet synchroon binnen de tik gebeuren → harness-test in Task 3 (`inKlik`).
3. **Dubbel tikken tijdens "Piano laden…"**: een tweede tik mag geen tweede laadpoging of dubbele start geven → harness-test in Task 3 (traag laden, twee tikken, één start).
4. **Pagina verborgen tijdens het laden** (Bob wisselt van app): na het laden niet alsnog starten → harness-test in Task 3.
5. **Laden mislukt**: spelen werkt met de oude klank, melding zichtbaar, en een volgende ▶ probeert niet opnieuw te laden (15 piano-fetches, niet 30) → harness-test in Task 3.

---

### Task 1: Shuffle-patroon in `speelplan`

**Files:**
- Modify: `web/speler.js` (`akkoordMidi`, `speelplan`, nieuwe helper `shuffleTel`)
- Test: `tests/test_speler.py`

**Interfaces:**
- Consumes: niets nieuws.
- Produces:
  - `akkoordMidi(tekst)` → bij een leesbaar akkoord `{nc: false, bas, akkoord, grond, kwint, slash}`; `grond` = `36 + pc` van de grondtoon, `kwint` = halve tonen van grondtoon tot kwint (7, 6 of 8), `slash` = boolean.
  - `speelplan(maten, {bpm, tellen = 4, start, eind, inteltel = tellen, stijl = "recht"})`; `stijl: "shuffle"` geldt alleen als `tellen === 4`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_speler.py`: vervang de body van `test_akkoord_midi` (die vergelijkt nu het hele object en breekt door de nieuwe velden) en voeg de nieuwe tests toe onder `test_speelplan_zonder_maten`:

```python
def test_akkoord_midi(tekst, bas, akkoord):
    r = js(f"akkoordMidi({json.dumps(tekst)})")
    assert {k: r[k] for k in ("nc", "bas", "akkoord")} == {"nc": False, "bas": bas, "akkoord": akkoord}


@pytest.mark.parametrize("tekst, grond, kwint, slash", [
    ("G7", 43, 7, False), ("Bdim", 47, 6, False), ("Caug", 36, 8, False),
    ("Gsus4", 43, 7, False), ("Bbm7/F", 46, 7, True)])
def test_akkoord_midi_grond_kwint_slash(tekst, grond, kwint, slash):
    r = js(f"akkoordMidi({json.dumps(tekst)})")
    assert (r["grond"], r["kwint"], r["slash"]) == (grond, kwint, slash)
```

En onder `test_speelplan_zonder_maten`:

```python
SHUF = {"bpm": 100, "inteltel": 0, "stijl": "shuffle"}  # tel 600 ms, korte achtste op 400 ms


def test_shuffle_een_akkoord_kwint_sext_septiem_sext():
    g, duur = plan(_maten("C"), SHUF)
    assert g == [
        [0, "tik", [], 1], [0, "bas", [36, 43], 1], [400, "bas", [36, 43], 1],
        [600, "tik", [], 1], [600, "bas", [36, 45], 1], [600, "akkoord", [60, 64, 67], 1],
        [1000, "bas", [36, 45], 1],
        [1200, "tik", [], 1], [1200, "bas", [36, 46], 1], [1600, "bas", [36, 46], 1],
        [1800, "tik", [], 1], [1800, "bas", [36, 45], 1], [1800, "akkoord", [60, 64, 67], 1],
        [2200, "bas", [36, 45], 1]]
    assert duur == 2400


def test_shuffle_twee_akkoorden_elk_kwint_sext():
    g, _ = plan(_maten("C G"), SHUF)
    assert [x[2] for x in g if x[1] == "bas"][::2] == [[36, 43], [36, 45], [43, 50], [43, 52]]
    assert [x[:3] for x in g if x[1] == "akkoord"] == [[600, "akkoord", [60, 64, 67]],
                                                       [1800, "akkoord", [55, 59, 62]]]


def test_shuffle_slash_alleen_basnoot():
    g, _ = plan(_maten("Bbm7/F"), SHUF)
    assert {tuple(x[2]) for x in g if x[1] == "bas"} == {(41,)}


def test_shuffle_dim_en_aug_alleen_eigen_kwint():
    g, _ = plan(_maten("Bdim", "Caug"), SHUF)
    assert {tuple(x[2]) for x in g if x[1] == "bas" and x[3] == 1} == {(47, 53)}
    assert {tuple(x[2]) for x in g if x[1] == "bas" and x[3] == 2} == {(36, 44)}


def test_shuffle_nc_alleen_tik():
    g, _ = plan(_maten("N.C.", ""), SHUF)
    assert {x[1] for x in g} == {"tik"}


def test_shuffle_niet_bij_drie_kwart():
    opties = {"bpm": 120, "tellen": 3}
    assert plan(_maten("C"), dict(opties, stijl="shuffle")) == plan(_maten("C"), opties)


def test_shuffle_gesorteerd_op_tijd_met_inteltel():
    # Speler.vooruit plant op volgorde: een gebeurtenis die te vroeg in de lijst staat geeft een gat.
    g, duur = plan(_maten("C F G", "Bbm7/F", "N.C.", "C"), {"bpm": 100, "stijl": "shuffle"})
    tijden = [x[0] for x in g]
    assert tijden == sorted(tijden)
    assert duur == 12000  # inteltel + 4 maten van 2,4 s
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_speler.py -q -k "akkoord_midi or shuffle"`
Expected: FAIL — `KeyError: 'grond'` en de shuffle-tests krijgen het rechte patroon (bv. `[36]` in plaats van `[36, 43]`). `test_shuffle_niet_bij_drie_kwart` slaagt al (dat is goed: het pint bestaand gedrag).

- [ ] **Step 3: Implement**

In `web/speler.js`, in `akkoordMidi`, vervang de `return`-regel door:

```js
  return { nc: false, bas: 36 + basPc, akkoord: stappen.map(s => laag + s),
    grond: 36 + grond[0], kwint: stappen[2], slash: slash >= 0 };
```

(`stappen[2]` is de kwint van elke drieklank: maj/min/sus 7, dim 6, aug 8; dim7 `[0, 3, 6, 9]` → 6.)

Boven `speelplan` toevoegen:

```js
// Shuffle-linkerhand: bovenop de grondtoon kwint, sext, kleine septiem, sext (+0, +2, +3, +2 op de kwint).
const SHUFFLE = [0, 2, 3, 2];

// Eén tel shuffle: linkerhand op de lange en de korte achtste, akkoord op tel 2 en 4.
// p = tel sinds het akkoord begon, b = tel in de maat. Op tijd gesorteerd.
function shuffleTel(a, t, tel, p, b, maat) {
  const links = a.slash ? [a.bas]
    : [a.grond, a.grond + a.kwint + (a.kwint === 7 ? SHUFFLE[p % 4] : 0)];
  const g = [{ t, soort: "bas", midi: links, duur: 0.9 * tel * 2 / 3, maat }];
  if (b % 2 === 1) g.push({ t, soort: "akkoord", midi: a.akkoord, duur: 0.25 * tel, maat });
  g.push({ t: t + tel * 2 / 3, soort: "bas", midi: links, duur: 0.9 * tel / 3, maat });
  return g;
}
```

Wijzig `speelplan`: commentaar, signatuur en de lus:

```js
// Schema-maten -> {gebeurtenissen: [{t, soort, midi, duur, maat}], duur} in seconden.
// start/eind: maatnummers (inclusief). inteltel: tikken vooraf (maat null).
// Recht: per tel een tik; bas op de eerste tel van elk akkoord (en op even tellen), anders het akkoord.
// Shuffle (alleen bij 4 tellen): tik per tel, linkerhand in zwingende achtsten, akkoord op 2 en 4.
function speelplan(maten, { bpm, tellen = 4, start = -Infinity, eind = Infinity, inteltel = tellen,
  stijl = "recht" }) {
  const tel = 60 / bpm;
  const shuffle = stijl === "shuffle" && tellen === 4;
```

en in de lus, direct na `const eerste = b === Math.ceil(k * tellen / n);`:

```js
      if (shuffle) {
        g.push(...shuffleTel(a, t, tel, b - Math.ceil(k * tellen / n), b, m.nr));
        continue;
      }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_speler.py -q`
Expected: alles PASS (ook de bestaande rechte-patroon-tests).

- [ ] **Step 5: Commit**

```bash
git add web/speler.js tests/test_speler.py
git commit -m "Meespelen: shuffle-patroon in speelplan (linkerhand kwint-sext-septiem, akkoord op 2 en 4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011HT47tgB5e8kbi5GEnQEKY"
```

---

### Task 2: Pianosamples, `laadPiano`, `pianoGeluid`, `binnen`, zachtere tik

**Files:**
- Create: `scripts/piano-samples.sh`, `web/piano/36.mp3` … `web/piano/78.mp3` (15 bestanden)
- Modify: `web/speler.js` (nieuwe functies na `speelGeluid`; `KLANK` en tik-volume in `speelGeluid`)
- Modify: `tests/web_eval.js` (beloftes afwachten)
- Test: `tests/test_speler.py`

**Interfaces:**
- Consumes: `speelGeluid(ctx, e, wanneer, uit)` (bestaand).
- Produces:
  - `PIANO_NOTEN` (array, zie Global Constraints).
  - `laadPiano(ctx, haal = fetch)` → `Promise<{[midi]: AudioBuffer}>`; haalt `piano/<midi>.mp3`; één fout (`!r.ok` of decodeerfout) → de hele belofte faalt met `Error("piano <midi>: <status>")`.
  - `pianoGeluid(buffers)` → `(ctx, e, wanneer, uit) => void`; `tik` gaat naar `speelGeluid`.
  - `binnen(belofte, ms)` → belofte die faalt met `Error("te traag")` na `ms`.

- [ ] **Step 1: Samples maken**

Maak `scripts/piano-samples.sh`:

```bash
#!/usr/bin/env bash
# Haalt de Salamander Grand Piano-samples (Alexander Holm, CC-BY 3.0) via Tone.js op
# en maakt ze klein voor web/piano/<midi>.mp3: mono, stilte vooraf eraf, 2 s met fade-out.
set -euo pipefail
cd "$(dirname "$0")/.."
BRON=https://tonejs.github.io/audio/salamander
NAMEN=(C2 Ds2 Fs2 A2 C3 Ds3 Fs3 A3 C4 Ds4 Fs4 A4 C5 Ds5 Fs5)  # MIDI 36, 39, ..., 78
WERK=$(mktemp -d)
trap 'rm -rf "$WERK"' EXIT
mkdir -p web/piano
midi=36
for n in "${NAMEN[@]}"; do
  curl -fsSL "$BRON/$n.mp3" -o "$WERK/$n.mp3"
  ffmpeg -loglevel error -y -i "$WERK/$n.mp3" -ac 1 \
    -af "silenceremove=start_periods=1:start_threshold=-50dB,atrim=0:2,afade=t=out:st=1.7:d=0.3" \
    -b:a 96k "web/piano/$midi.mp3"
  midi=$((midi + 3))
done
ls -l web/piano
```

Run: `chmod +x scripts/piano-samples.sh && scripts/piano-samples.sh`
Expected: 15 bestanden `36.mp3` … `78.mp3`, elk ongeveer 15–30 KB.

Run: `for f in web/piano/*.mp3; do ffprobe -v error -show_entries format=duration -of csv=p=0 "$f"; done | sort -u | head`
Expected: elke duur ≈ 2,0 s (bv. `2.000000` of `2.0xx`).

- [ ] **Step 2: Write the failing tests**

Eerst `tests/web_eval.js`: laat de laatste regel beloftes afwachten (bestaande tests geven gewone waarden en blijven werken):

```js
Promise.resolve(vm.runInContext(process.argv[2], ctx)).then(
  r => console.log(JSON.stringify(r)),
  e => console.log(JSON.stringify({ fout: String(e && e.message || e) })));
```

(vervangt `console.log(JSON.stringify(vm.runInContext(process.argv[2], ctx)));`; werk ook het kopcommentaar bij: "print JSON.stringify(<expressie>), na afwachten als het een belofte is").

Dan in `tests/test_speler.py`, onderaan:

```python
WEB = Path(__file__).parent.parent / "web"


def test_pianosamples_aanwezig_en_klein():
    noten = js("PIANO_NOTEN")
    assert noten == list(range(36, 79, 3))
    for m in noten:
        f = WEB / "piano" / f"{m}.mp3"
        assert f.is_file(), f
        assert 5_000 < f.stat().st_size < 60_000, f


NEP_PIANO = ("(() => { const bronnen = []; const tonen = [];"
             " const param = () => ({setValueAtTime() {}, linearRampToValueAtTime() {},"
             " exponentialRampToValueAtTime() {}});"
             " const knoop = x => Object.assign({connect: y => y}, x);"
             " const ctx = {createGain: () => knoop({gain: param()}),"
             " createBufferSource: () => { const b = knoop({playbackRate: {}, start() {}, stop() {}});"
             " bronnen.push(b); return b; },"
             " createOscillator: () => { const o = knoop({frequency: {}, start() {}, stop() {}});"
             " tonen.push(o); return o; }};"
             " const buffers = {}; PIANO_NOTEN.forEach(m => { buffers[m] = 'buf' + m; });")


def test_piano_geluid_dichtstbijzijnde_sample_en_toonhoogte():
    r = js(NEP_PIANO + " const g = pianoGeluid(buffers);"
           " g(ctx, {soort: 'akkoord', midi: [37, 30, 80], duur: 0.5, maat: 1}, 1, {});"
           " g(ctx, {soort: 'tik', midi: [], duur: 0.03, maat: 1}, 1, {});"
           " return {bronnen: bronnen.map(b => [b.buffer, Math.round(b.playbackRate.value * 10000) / 10000]),"
           " tonen: tonen.length}; })()")
    assert r["bronnen"] == [["buf36", 1.0595], ["buf36", 0.7071], ["buf78", 1.1225]]
    assert r["tonen"] == 1  # de tik blijft de synth


LAAD = ("(() => { const gevraagd = []; const ctx = {decodeAudioData: d => Promise.resolve('dec:' + d)};"
        " const haal = url => { gevraagd.push(url); const ok = url !== FOUT;"
        " return Promise.resolve({ok, status: ok ? 200 : 404, arrayBuffer: () => Promise.resolve(url)}); };")


def test_laad_piano_haalt_alle_samples():
    r = js("const FOUT = null;" + LAAD + " return laadPiano(ctx, haal).then(b =>"
           " ({gevraagd, b36: b[36], n: Object.keys(b).length})); })()")
    assert r["gevraagd"] == [f"piano/{m}.mp3" for m in range(36, 79, 3)]
    assert (r["b36"], r["n"]) == ("dec:piano/36.mp3", 15)


def test_laad_piano_een_fout_is_alles_fout():
    r = js("const FOUT = 'piano/51.mp3';" + LAAD + " return laadPiano(ctx, haal); })()")
    assert r == {"fout": "piano 51: 404"}


def test_binnen_tijdslimiet():
    assert js("binnen(new Promise(() => {}), 10)") == {"fout": "te traag"}
    assert js("binnen(Promise.resolve(5), 5000)") == 5  # en de wekker houdt node niet open


def test_tik_tijdens_spelen_zachter_dan_inteltel():
    r = js("(() => { const pieken = []; const knoop = x => Object.assign({connect: y => y}, x);"
           " const ctx = {createOscillator: () => knoop({frequency: {}, start() {}, stop() {}}),"
           " createGain: () => knoop({gain: {setValueAtTime() {}, exponentialRampToValueAtTime() {},"
           " linearRampToValueAtTime(v) { pieken.push(v); }}})};"
           " speelGeluid(ctx, {soort: 'tik', midi: [], duur: 0.03, maat: null}, 0, {});"
           " speelGeluid(ctx, {soort: 'tik', midi: [], duur: 0.03, maat: 1}, 0, {});"
           " return pieken; })()")
    assert r[0] > r[1] > 0
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_speler.py -q -k "piano or binnen or tik_tijdens"`
Expected: FAIL — `PIANO_NOTEN is not defined` / `pianoGeluid is not defined` / `binnen is not defined` (node-fout → `CalledProcessError`), en de tik-test faalt op `r[0] > r[1]` (beide 0.04).

Run ook: `.venv/bin/python -m pytest tests/test_speler.py tests/test_web.py -q`
Expected: de bestaande tests blijven PASS met de nieuwe `web_eval.js`.

- [ ] **Step 4: Implement**

In `web/speler.js`: vervang de `KLANK`-regel en de eerste regel van `speelGeluid`:

```js
const KLANK = { bas: ["triangle", 0.35], akkoord: ["triangle", 0.1], tik: ["square", 0.03] };
const INTELTIK = 0.06;  // de tikken vooraf iets harder dan de zachte tik tijdens het spelen
```

```js
function speelGeluid(ctx, e, wanneer, uit) {
  const vorm = KLANK[e.soort][0];
  const sterkte = e.soort === "tik" && e.maat === null ? INTELTIK : KLANK[e.soort][1];
```

(de rest van `speelGeluid` blijft gelijk; werk het commentaar erboven bij: "inteltikken klinken hoger en harder").

Direct na `speelGeluid` toevoegen:

```js
// Salamander Grand Piano (Alexander Holm, CC-BY 3.0): web/piano/<midi>.mp3, elke kleine terts.
const PIANO_NOTEN = [36, 39, 42, 45, 48, 51, 54, 57, 60, 63, 66, 69, 72, 75, 78];
const PIANO_STERKTE = { bas: 0.5, akkoord: 0.3 };
const LOSLATEN = 0.08;  // seconden: de toon dempt als een loslatende toets

// Haalt en decodeert alle samples; één fout = alles fout (geen halve piano).
function laadPiano(ctx, haal = fetch) {
  return Promise.all(PIANO_NOTEN.map(m => haal(`piano/${m}.mp3`)
    .then(r => { if (!r.ok) throw new Error(`piano ${m}: ${r.status}`); return r.arrayBuffer(); })
    .then(data => ctx.decodeAudioData(data))
    .then(buf => [m, buf])))
    .then(paren => Object.fromEntries(paren));
}

// Faalt met "te traag" als `belofte` niet binnen `ms` klaar is.
function binnen(belofte, ms) {
  let wekker;
  const teLaat = new Promise((_, nee) => { wekker = setTimeout(() => nee(new Error("te traag")), ms); });
  return Promise.race([belofte, teLaat]).finally(() => clearTimeout(wekker));
}

const dichtsteSample = m => PIANO_NOTEN.reduce((b, s) => (Math.abs(s - m) < Math.abs(b - m) ? s : b));

// Geluidsfunctie zoals speelGeluid, maar met pianosamples; de tik blijft de synth.
function pianoGeluid(buffers) {
  return (ctx, e, wanneer, uit) => {
    if (e.soort === "tik") { speelGeluid(ctx, e, wanneer, uit); return; }
    const sterkte = PIANO_STERKTE[e.soort];
    const los = wanneer + e.duur;
    for (const m of e.midi) {
      const s = dichtsteSample(m);
      const bron = ctx.createBufferSource();
      bron.buffer = buffers[s];
      bron.playbackRate.value = Math.pow(2, (m - s) / 12);
      const vol = ctx.createGain();
      vol.gain.setValueAtTime(sterkte, wanneer);
      vol.gain.setValueAtTime(sterkte, los);
      vol.gain.linearRampToValueAtTime(0.0001, los + LOSLATEN);
      bron.connect(vol).connect(uit);
      bron.start(wanneer);
      bron.stop(los + LOSLATEN + 0.02);
    }
  };
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_speler.py tests/test_web.py -q`
Expected: alles PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/piano-samples.sh web/piano tests/web_eval.js web/speler.js tests/test_speler.py
git commit -m "Meespelen: pianosamples (Salamander, CC-BY) met laadPiano en pianoGeluid; zachtere tik

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011HT47tgB5e8kbi5GEnQEKY"
```

---

### Task 3: Piano laden bij de eerste ▶, shuffle aan, naamsvermelding, docs

**Files:**
- Modify: `web/speler.js` (`Speler.ontgrendel`, `start` gebruikt die)
- Modify: `web/app.js` (`paginaSong`: `piano`-stand, `speelKnop`, `speel` met shuffle, `tekenSpeler`)
- Modify: `web/song.html` (hulptekst met naamsvermelding; `speler.js?v=3`, `app.js?v=7`), `web/index.html`, `web/setlist.html`, `web/controle.html` (`app.js?v=7`)
- Modify: `tests/web_harness.js`, `tests/test_web.py`, `tests/test_speler.py`
- Modify: `README.md`, `CLAUDE.md`, spec-status in `docs/superpowers/specs/2026-10-16-piano-shuffle-design.md`

**Interfaces:**
- Consumes: `speelplan(…, {stijl})` (Task 1); `laadPiano(ctx)`, `pianoGeluid(buffers)`, `binnen(belofte, ms)` (Task 2).
- Produces: `Speler.ontgrendel()` → de `AudioContext` (maakt hem één keer aan, hervat hem, zet `navigator.audioSession.type = "playback"`).

- [ ] **Step 1: Harness uitbreiden**

In `tests/web_harness.js`:

1. Bovenaan, na `const fetches = [];`, toevoegen:

```js
const wacht = ms => new Promise(r => setTimeout(r, ms));
// BLUESLAB_PIANO: ok (standaard) | fout (404) | traag (30 ms) | hangt (nooit klaar).
const pianoStand = process.env.BLUESLAB_PIANO || "ok";
const pianoAntwoord = async () => {
  if (pianoStand === "hangt") return new Promise(() => {});
  if (pianoStand === "traag") await wacht(30);
  const ok = pianoStand !== "fout";
  return { ok, status: ok ? 200 : 404, arrayBuffer: async () => new ArrayBuffer(8) };
};
```

en verwijder de latere regel `const wacht = ms => new Promise(r => setTimeout(r, ms));` (anders dubbel gedeclareerd).

2. `document` krijgt `visibilityState: process.env.BLUESLAB_VERBORGEN === "1" ? "hidden" : "visible",`.

3. `fetch` wordt:

```js
  fetch: async (pad) => {
    fetches.push(pad);
    if (pad.startsWith("piano/")) return pianoAntwoord();
    return { status: ikStatus, ok: ikStatus < 400,
      json: async () => (ikStatus < 400 ? antwoordVoor(pad) : { detail: "Log eerst in." }) };
  },
```

4. Het audio-blok: `starts` telt nu keren spelen (het hoofdvolume dat aan de luidspreker hangt), `resumes` de hervat-aanroepen:

```js
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
```

5. In de actielus het aantal `resumes` binnen de klik zelf (synchroon) bijhouden — iOS staat audio alleen daar toe:

```js
const inKlik = [];  // resume-aanroepen synchroon binnen elke klik
```

(boven de `(async () => {`), en in de lus `doel._on.click();` vervangen door:

```js
    const voor = resumes;
    doel._on.click();
    inKlik.push(resumes - voor);
```

6. De uitvoer krijgt erbij: `resumes, inKlik, hulp: nepElement("#hulp").textContent, speelknop: speelknop()`, met boven de `console.log`:

```js
  const knop = gemaakt.filter(e => e.className === "speelknop").pop();
  const speelknop = () => (knop ? { tekst: knop._tekst, uit: "disabled" in knop._attrs } : null);
```

Werk het kopcommentaar van de harness bij met de nieuwe omgevingsvariabelen (`BLUESLAB_PIANO`, `BLUESLAB_VERBORGEN`).

Run: `.venv/bin/python -m pytest tests/test_web.py -q`
Expected: alles PASS (de bestaande `starts`-tests tellen nu het aantal starts in plaats van resumes; vóór de app-wijziging zijn die gelijk).

- [ ] **Step 2: Write the failing tests**

In `tests/test_speler.py`, na `test_speler_stop_meldt_een_keer`:

```python
def test_ontgrendel_maakt_context_een_keer_en_hervat():
    r = js("(() => { let gemaakt = 0, hervat = 0; const ctx = {resume() { hervat += 1; }};"
           " const s = new Speler({maakContext: () => { gemaakt += 1; return ctx; }});"
           " const a = s.ontgrendel(); s.ontgrendel(); return {zelfde: a === ctx, gemaakt, hervat}; })()")
    assert r == {"zelfde": True, "gemaakt": 1, "hervat": 2}
```

In `tests/test_web.py`: `draai` krijgt een `env`-parameter en `_speel` geeft die door:

```python
def draai(pagina, ik_status, zoek="", fixtures=None, audio=False, acties=(), env=None):
    env = dict(os.environ, BLUESLAB_FIXTURES=json.dumps(fixtures or {}),
               BLUESLAB_AUDIO="1" if audio else "0", BLUESLAB_ACTIES=json.dumps(list(acties)),
               **(env or {}))
```

```python
def _speel(*acties, **env):
    return draai("song", 200, "?id=1", {"/api/songs/": SCHEMA, "/api/setlists/": SETLIST},
                 audio=True, acties=acties, env=env)
```

En onderaan:

```python
# --- Meespelen met piano --------------------------------------------------------

def _piano_fetches(r):
    return [f for f in r["fetches"] if f.startswith("piano/")]


def test_eerste_speel_laadt_piano_en_start():
    r = _speel("tekst=▶ Speel")
    assert len(_piano_fetches(r)) == 15
    assert r["starts"] == 1
    assert r["speelknop"] == {"tekst": "■ Stop", "uit": False}
    assert r["hulp"] == ""


def test_audio_ontgrendeld_binnen_de_tik():
    # iOS: audio mag alleen synchroon binnen de tik aan, niet pas na het laden.
    assert _speel("tekst=▶ Speel", BLUESLAB_PIANO="hangt")["inKlik"] == [1]


def test_tijdens_laden_knop_uit_en_geen_start():
    r = _speel("tekst=▶ Speel", BLUESLAB_PIANO="hangt")
    assert r["speelknop"] == {"tekst": "Piano laden…", "uit": True}
    assert r["starts"] == 0


def test_dubbel_tikken_tijdens_laden_een_keer_laden_en_starten():
    r = _speel("tekst=▶ Speel", "tekst=▶ Speel", BLUESLAB_PIANO="traag")
    assert len(_piano_fetches(r)) == 15
    assert r["starts"] == 1


def test_piano_mislukt_speelt_eenvoudige_klank_en_meldt():
    r = _speel("tekst=▶ Speel", BLUESLAB_PIANO="fout")
    assert r["starts"] == 1
    assert "Piano niet geladen" in r["hulp"]


def test_piano_mislukt_niet_opnieuw_laden():
    r = _speel("tekst=▶ Speel", "tekst=■ Stop", "tekst=▶ Speel", BLUESLAB_PIANO="fout")
    assert len(_piano_fetches(r)) == 15
    assert r["starts"] == 2


def test_pagina_verborgen_tijdens_laden_niet_starten():
    r = _speel("tekst=▶ Speel", BLUESLAB_VERBORGEN="1")
    assert r["starts"] == 0
    assert r["speelknop"]["tekst"] == "▶ Speel"


def test_hulptekst_noemt_salamander_piano():
    html = (Path(__file__).parent.parent / "web" / "song.html").read_text()
    assert "Salamander Grand Piano" in html and "CC-BY 3.0" in html
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_speler.py tests/test_web.py -q -k "ontgrendel or piano or laden or verborgen or salamander or ontgrendeld"`
Expected: FAIL — `s.ontgrendel is not a function`; geen `piano/`-fetches; `speelknop` toont nooit "Piano laden…"; hulptekst zonder Salamander. (`test_pagina_verborgen_tijdens_laden_niet_starten` faalt op `starts == 1`.)

- [ ] **Step 4: Implement `Speler.ontgrendel`**

In `web/speler.js`, in `class Speler`, vóór `start(`:

```js
  // iOS: audio mag alleen binnen een tik aan. Roep dit aan vóór elke await.
  ontgrendel() {
    // Afspelen als media: anders dempt de stille modus van iPad/iPhone de begeleiding.
    if (typeof navigator !== "undefined" && navigator.audioSession) navigator.audioSession.type = "playback";
    if (!this.ctx) this.ctx = this.maakContext();
    if (this.ctx.resume) this.ctx.resume();
    return this.ctx;
  }
```

en in `start` de drie regels (audioSession-commentaar + `if (typeof navigator …`, `if (!this.ctx) …`, `if (this.ctx.resume) …`) vervangen door:

```js
    this.ontgrendel();
```

- [ ] **Step 5: Implement de app-kant**

In `web/app.js`, in `paginaSong`, na `const speler = …`:

```js
  // Piano: één laadpoging per pagina (nieuw → laden → klaar of mislukt).
  let piano = "nieuw";

  async function speelKnop() {
    if (speler.speelt) { speler.stop(); return; }
    if (piano === "laden") return;
    const ctx = speler.ontgrendel();  // binnen de tik, vóór de await (iOS)
    if (piano === "nieuw") {
      piano = "laden";
      tekenSpeler();
      try {
        speler.geluid = pianoGeluid(await binnen(laadPiano(ctx), 10000));
        piano = "klaar";
      } catch (e) {
        piano = "mislukt";
        $("#hulp").textContent = "Piano niet geladen — eenvoudige klank. Tik op een maat om daar te beginnen.";
      }
      if (document.visibilityState === "hidden") { tekenSpeler(); return; }
    }
    speel();
  }
```

In `speel()` beide `speelplan`-aanroepen `stijl: "shuffle"` meegeven:

```js
    speler.start(speelplan(maten, { bpm, tellen, start: b.start, eind: b.eind, stijl: "shuffle" }),
      oefen.herhaal ? speelplan(maten, { bpm, tellen, start: b.lusStart, eind: b.eind, inteltel: 0,
        stijl: "shuffle" }) : null);
```

In `tekenSpeler()` de speelknop:

```js
      el("button", { class: "speelknop", disabled: piano === "laden", onclick: speelKnop },
        piano === "laden" ? "Piano laden…" : speler.speelt ? "■ Stop" : "▶ Speel"),
```

- [ ] **Step 6: Hulptekst en versies**

`web/song.html`, regel met `id="hulp"`:

```html
    <p id="hulp" class="klein" hidden>Tik op een maat om daar te beginnen. Hoor je niets? Zet het geluid aan. Piano: Salamander Grand Piano (Alexander Holm, CC-BY 3.0).</p>
```

Versies: `speler.js?v=2` → `speler.js?v=3` in `web/song.html`; `app.js?v=6` → `app.js?v=7` in alle vier `web/*.html`:

Run: `sed -i 's/speler\.js?v=2/speler.js?v=3/' web/song.html && sed -i 's/app\.js?v=6/app.js?v=7/' web/*.html && grep -n "v=" web/*.html`
Expected: `speler.js?v=3` in song.html, `app.js?v=7` in alle vier, `style.css?v=5` ongewijzigd.

- [ ] **Step 7: Run de hele suite**

Run: `.venv/bin/python -m pytest -q`
Expected: alles PASS (180 + de nieuwe tests uit Task 1–3 passed, 1 skipped).

- [ ] **Step 8: Live controleren**

Run: `curl -sI https://blues.felixisfelix.com/piano/36.mp3 | grep -iE "^(HTTP|content-type)"`
Expected: `HTTP/2 200` en `content-type: audio/mpeg` (StaticFiles serveert nieuwe bestanden zonder herstart).

Run: `curl -s https://blues.felixisfelix.com/song.html | grep -o 'speler.js?v=[0-9]*\|app.js?v=[0-9]*\|Salamander'`
Expected: `speler.js?v=3`, `app.js?v=7`, `Salamander`.

- [ ] **Step 9: Docs**

`README.md`: onder het oefenen-stuk een regel:

```markdown
- De begeleiding speelt een shuffle op piano: samples van de **Salamander Grand Piano** (Alexander Holm, CC-BY 3.0), via Tone.js, verkleind met `scripts/piano-samples.sh` naar `web/piano/`. Lukt het laden niet, dan klinkt een eenvoudige synth.
```

`CLAUDE.md`, onder de story "Oefenen per nummer", een nieuwe story:

```markdown
- **Meespelen met piano en shuffle**: spec `docs/superpowers/specs/2026-10-16-piano-shuffle-design.md`,
  plan `docs/superpowers/plans/2026-10-16-piano-shuffle.md`. Salamander-samples in `web/piano/`
  (opnieuw maken: `scripts/piano-samples.sh`), geladen bij de eerste ▶. *Status: gebouwd (2026-10-16), branch `bl-2-site`.*
```

en bij de valkuilen:

```markdown
- iOS zet audio alleen aan binnen een tik: `speler.ontgrendel()` vóór elke `await` (het laden van de piano is async).
```

Spec-status: in `docs/superpowers/specs/2026-10-16-piano-shuffle-design.md` "**Status:** ontwerp, goedgekeurd in de chat (2026-10-16)" → "**Status:** gebouwd (2026-10-16)".

- [ ] **Step 10: Commit**

```bash
git add web/speler.js web/app.js web/*.html tests/web_harness.js tests/test_web.py tests/test_speler.py \
  README.md CLAUDE.md docs/superpowers/specs/2026-10-16-piano-shuffle-design.md
git commit -m "Meespelen: piano laden bij de eerste ▶, shuffle aan, naamsvermelding Salamander

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011HT47tgB5e8kbi5GEnQEKY"
```
