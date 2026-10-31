# Stijlen per nummer met drums — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per nummer een begeleidingsstijl (Shuffle · Pop · Ballad · Funk) met piano én drums, bewaard op de server.

**Architecture:** Elke stijl is een tabel in `web/speler.js` (`STIJLEN`): één 4/4-maat in zestienden met regels voor linkerhand, rechterhand, kick, snare en hi-hat. `speelplan` zet de tabel per maat om in de bestaande gebeurtenissen `{t, soort, midi, duur, maat, sterkte}`; `maakGeluid({piano, drums})` speelt ze met samples. De server krijgt kolom `song.stijl` (met migratie) en `PUT /api/songs/{id}/stijl`; de songpagina toont stijlknoppen en laadt piano en drums los van elkaar.

**Tech Stack:** vanilla JS (node v12: geen `?.`/`??`), Web Audio, FastAPI + sqlite3 (stdlib), pytest + node-harness, ffmpeg/curl voor samples.

**Spec:** `docs/superpowers/specs/2026-10-16-stijlen-drums-design.md`

## Global Constraints

- Werk op branch **`stijlen-drums`** (van `main`); niet op `main` committen. `blueslab.service` draait vanuit deze working tree: statische bestanden zijn direct live, servercode pas na Bobs herstart.
- Node op orin3 is **v12**: geen `?.` of `??` in `web/*.js`.
- Stijlen: `shuffle | pop | ballad | funk`, alleen bij **4 tellen**; anders het rechte patroon met tik. Standaard **`shuffle`**.
- Met drums **geen tik tijdens het spelen**; het aftellen blijft `tik` met `maat: null` (klinkt als hi-hat als de drums geladen zijn).
- Drums: Google Chrome Labs `web-audio-samples`, `src/sounds/drum-samples/acoustic-kit/{kick,snare,hihat}.wav`, **Apache-2.0**; licentietekst mee in `web/drums/LICENSE-Apache-2.0.txt`.
- Tijdslimiet laden: 10 s per soort (piano, drums), onafhankelijk. Meldingen: "Piano niet geladen — eenvoudige klank." / "Drums niet geladen — met tik." / "Stijl niet bewaard."
- Versies: `speler.js?v=4` (song.html), `app.js?v=9` (alle vier `web/*.html`).
- Tests: `.venv/bin/python -m pytest -q` (nu 208 passed, 1 skipped).
- Commit-trailer:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_011HT47tgB5e8kbi5GEnQEKY
  ```

## Review Focus

1. **De live database** (`data/blueslab.sqlite`, met Bobs echte nummers) krijgt bij de herstart een `ALTER TABLE`: bestaande nummers moeten leesbaar blijven met stijl `shuffle`, en een tweede start mag niet falen → test met een database in het oude schema in Task 3, plus een reservekopie vóór de herstart.
2. **Shuffle-regressie**: de shuffle wordt een tabel; zonder drums moeten de gebeurtenissen exact gelijk blijven → de bestaande shuffle-tests blijven ongewijzigd (Task 1).
3. **Half geladen**: piano lukt en drums niet (of andersom) → elk speelt met wat er is, met de juiste melding → harness-tests in Task 4 en `maakGeluid`-tests in Task 2.
4. **Stijl kiezen tijdens "Laden…" of tijdens spelen**: tijdens het laden niet starten; tijdens het spelen opnieuw starten in de nieuwe stijl → harness-tests in Task 4.
5. **Oude server** (vóór Bobs herstart): het schema heeft geen `stijl` en `PUT …/stijl` faalt → app gebruikt Shuffle en meldt "Stijl niet bewaard." → harness-test in Task 4.

---

### Task 1: Stijltabellen en `speelplan`

**Files:**
- Modify: `web/speler.js` (`SHUFFLE` blijft; `shuffleTel` vervalt; nieuw `STIJLEN`, `posTel`, `linksTonen`, `rechtsTonen`, `stijlMaat`, `rechteMaat`; `speelplan` herschreven)
- Test: `tests/test_speler.py`

**Interfaces:**
- Consumes: `akkoordMidi` → `{nc, bas, akkoord, grond, kwint, slash}` (bestaand).
- Produces: `speelplan(maten, {bpm, tellen = 4, start, eind, inteltel = tellen, stijl = "recht", drums = false})` → `{gebeurtenissen, duur}`; gebeurtenis `{t, soort, midi, duur, maat, sterkte}` met `soort` ∈ `tik | bas | akkoord | kick | snare | hihat`; `STIJLEN` (object met sleutels `shuffle, pop, ballad, funk`).

- [ ] **Step 1: Write the failing tests**

Onderaan `tests/test_speler.py` (na de shuffle-tests, vóór `WEB = …` mag ook; plaats ze bij elkaar onder een kopje):

```python
# --- Stijlen met drums ----------------------------------------------------------

def _tijden(g, soort, maat=1):
    return [x[0] for x in g if x[1] == soort and x[3] == maat]


def _stijl(stijl, *maten, drums=True):
    return plan(_maten(*maten), {"bpm": 100, "inteltel": 0, "stijl": stijl, "drums": drums})[0]


def test_pop_patroon():
    g = _stijl("pop", "C")
    assert _tijden(g, "bas") == [0, 900, 1200]
    assert _tijden(g, "akkoord") == list(range(0, 2400, 300))
    assert (_tijden(g, "kick"), _tijden(g, "snare")) == ([0, 1200], [600, 1800])
    assert _tijden(g, "hihat") == list(range(0, 2400, 300))
    assert _tijden(g, "tik") == []  # met drums geen tik tijdens het spelen


def test_pop_twee_akkoorden_bas_op_8_is_tweede_akkoord():
    g = _stijl("pop", "C G")
    assert [x[2] for x in g if x[1] == "bas"] == [[36], [36], [43]]


def test_ballad_gebroken_akkoord_drie_en_vierklank():
    g = _stijl("ballad", "C", "C7")
    assert [x[2][0] for x in g if x[1] == "akkoord" and x[3] == 1] == [60, 64, 67, 72] * 2
    assert [x[2][0] for x in g if x[1] == "akkoord" and x[3] == 2] == [60, 64, 67, 70] * 2
    assert _tijden(g, "bas") == [0, 1200]
    assert (_tijden(g, "kick"), _tijden(g, "snare"), _tijden(g, "hihat")) == (
        [0], [1200], [0, 600, 1200, 1800])


def test_ballad_rechterhand_zacht():
    r = js("speelplan([{nr: 1, akkoorden: [{concert: 'C'}]}], {bpm: 100, inteltel: 0,"
           " stijl: 'ballad'}).gebeurtenissen.filter(e => e.soort === 'akkoord')[0].sterkte")
    assert r == 0.5


def test_funk_patroon():
    g = _stijl("funk", "C")
    assert [(x[0], x[2]) for x in g if x[1] == "bas"] == [
        (0, [36]), (450, [36]), (900, [48]), (1200, [36]), (1650, [43]), (2100, [48])]
    assert _tijden(g, "akkoord") == [750, 1050, 1950, 2250]
    assert (_tijden(g, "kick"), _tijden(g, "snare")) == ([0, 900], [600, 1800])
    assert _tijden(g, "hihat") == list(range(0, 2400, 150))


def test_shuffle_met_drums_zwingende_hihat():
    g = _stijl("shuffle", "C")
    assert _tijden(g, "hihat") == [0, 400, 600, 1000, 1200, 1600, 1800, 2200]
    assert (_tijden(g, "kick"), _tijden(g, "snare"), _tijden(g, "tik")) == ([0, 1200], [600, 1800], [])


def test_stijl_slash_akkoord_bas_is_slashnoot():
    assert {tuple(x[2]) for x in _stijl("pop", "Bbm7/F") if x[1] == "bas"} == {(41,)}


def test_stijl_nc_met_drums_alleen_hihat_zonder_drums_tik():
    met = _stijl("pop", "N.C.")
    assert {x[1] for x in met} == {"hihat"} and _tijden(met, "hihat") == [0, 600, 1200, 1800]
    zonder = _stijl("pop", "N.C.", drums=False)
    assert {x[1] for x in zonder} == {"tik"} and _tijden(zonder, "tik") == [0, 600, 1200, 1800]


def test_stijl_zonder_drums_tik_en_geen_drums():
    g = _stijl("funk", "C", drums=False)
    assert _tijden(g, "tik") == [0, 600, 1200, 1800]
    assert not [x for x in g if x[1] in ("kick", "snare", "hihat")]


def test_drums_aftellen_blijft_tik():
    g, _ = plan(_maten("C"), {"bpm": 100, "stijl": "pop", "drums": True})
    assert [x for x in g if x[1] == "tik"] == [[t, "tik", [], None] for t in (0, 600, 1200, 1800)]


def test_stijl_niet_bij_drie_kwart():
    opties = {"bpm": 120, "tellen": 3}
    assert plan(_maten("C"), dict(opties, stijl="pop", drums=True)) == plan(_maten("C"), opties)


@pytest.mark.parametrize("stijl", ["shuffle", "pop", "ballad", "funk"])
@pytest.mark.parametrize("drums", [True, False])
def test_stijl_gesorteerd_op_tijd(stijl, drums):
    g, _ = plan(_maten("C F G", "Bbm7/F", "N.C.", "C"), {"bpm": 100, "stijl": stijl, "drums": drums})
    tijden = [x[0] for x in g]
    assert tijden == sorted(tijden)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_speler.py -q -k "pop or ballad or funk or drums or stijl"`
Expected: FAIL — onbekende stijlen geven het rechte patroon (bv. `bas`-tijden `[0, 1200]`, geen `hihat`). `test_stijl_niet_bij_drie_kwart` en een deel van `test_stijl_gesorteerd_op_tijd` slagen al (pinnen bestaand gedrag).

- [ ] **Step 3: Implement**

In `web/speler.js`: vervang het blok van `// Eén tel shuffle: …` t/m het einde van `speelplan` (dus `shuffleTel` en `speelplan`; `SHUFFLE` en het commentaar erboven blijven) door:

```js
// Stijlen: één 4/4-maat in zestienden (positie 0-15). Piano: [positie, rol, duur in tellen, sterkte];
// drums: [positie, sterkte]. Rollen links: R grondtoon, 5 kwint, 8 octaaf, S shuffle-tweeklank;
// rechts: A heel akkoord, B0-B3 één toon van het gebroken akkoord. Swing: positie 4b+2 op b + 2/3.
const ACHTSTEN = [0, 2, 4, 6, 8, 10, 12, 14];
const ZESTIENDEN = [...Array(16).keys()];
const STIJLEN = {
  shuffle: { swing: true,
    links: ACHTSTEN.map(p => [p, "S", p % 4 ? 0.3 : 0.6, 1]),
    rechts: [[4, "A", 0.25, 1], [12, "A", 0.25, 1]],
    kick: [[0, 1], [8, 1]], snare: [[4, 1], [12, 1]], hihat: ACHTSTEN.map(p => [p, 1]) },
  pop: { swing: false,
    links: [[0, "R", 1.4, 1], [6, "R", 0.45, 1], [8, "R", 1.8, 1]],
    rechts: ACHTSTEN.map(p => [p, "A", 0.4, 0.6]),
    kick: [[0, 1], [8, 1]], snare: [[4, 1], [12, 1]], hihat: ACHTSTEN.map(p => [p, 1]) },
  ballad: { swing: false,
    links: [[0, "R", 1.9, 1], [8, "R", 1.9, 1]],
    rechts: ACHTSTEN.map((p, i) => [p, `B${i % 4}`, 0.9, 0.5]),
    kick: [[0, 0.6]], snare: [[8, 0.6]], hihat: [0, 4, 8, 12].map(p => [p, 0.5]) },
  funk: { swing: false,
    links: [[0, "R", 0.45, 1], [3, "R", 0.2, 1], [6, "8", 0.2, 1], [8, "R", 0.45, 1],
      [11, "5", 0.2, 1], [14, "8", 0.2, 1]],
    rechts: [5, 7, 13, 15].map(p => [p, "A", 0.15, 0.7]),
    kick: [[0, 1], [6, 1]], snare: [[4, 1], [12, 1]], hihat: ZESTIENDEN.map(p => [p, p % 2 ? 0.4 : 0.7]) },
};
const DRUMS = ["kick", "snare", "hihat"];
const DRUM_DUUR = 0.5;  // seconden; de sample klinkt zelf uit

// Positie (zestienden) -> tellen sinds het begin van de maat.
const posTel = (p, swing) => Math.floor(p / 4) + (swing ? (p % 4 ? 2 / 3 : 0) : (p % 4) / 4);

// Linkerhand-rol -> MIDI-tonen. p = tellen sinds het akkoord begon. Slash: de slash-noot is de grondtoon.
function linksTonen(a, rol, p) {
  const g = a.slash ? a.bas : a.grond;
  if (rol === "S") return a.slash ? [a.bas] : [g, g + a.kwint + (a.kwint === 7 ? SHUFFLE[p % 4] : 0)];
  if (rol === "5") return [g + a.kwint];
  if (rol === "8") return [g + 12];
  return [g];
}

// Rechterhand-rol -> MIDI-tonen: A = heel akkoord, Bi = toon i van [akkoord..., grondtoon + 12].
function rechtsTonen(a, rol) {
  return rol === "A" ? a.akkoord : [a.akkoord.concat([a.akkoord[0] + 12])[Number(rol.slice(1))]];
}

// Eén maat in een tabelstijl. Zonder drums een tik per tel; met drums de drumregels.
// Geen speelbaar akkoord (N.C., leeg, onleesbaar): geen piano, met drums alleen hi-hat op de tellen.
function stijlMaat(pat, akk, begin, tel, maat, drums) {
  const n = akk.length;
  const g = [];
  const op = (p, soort, midi, duur, sterkte) =>
    g.push({ t: begin + posTel(p, pat.swing) * tel, soort, midi, duur, maat, sterkte });
  for (let p = 0; p < 16; p++) {
    const b = Math.floor(p / 4);
    const k = Math.floor(b * n / 4);
    const a = n ? akk[k] : null;
    if (!drums && p % 4 === 0) op(p, "tik", [], TIK_DUUR, 1);
    if (!a || a.nc) {
      if (drums && p % 4 === 0) op(p, "hihat", [], DRUM_DUUR, 0.7);
      continue;
    }
    const sinds = b - Math.ceil(k * 4 / n);
    for (const [q, rol, duur, s] of pat.links) if (q === p) op(p, "bas", linksTonen(a, rol, sinds), duur * tel, s);
    for (const [q, rol, duur, s] of pat.rechts) if (q === p) op(p, "akkoord", rechtsTonen(a, rol), duur * tel, s);
    if (drums) for (const soort of DRUMS) for (const [q, s] of pat[soort]) if (q === p) op(p, soort, [], DRUM_DUUR, s);
  }
  return g;
}

// Eén maat recht (elke maatsoort): tik per tel; bas op de eerste tel van elk akkoord (en op even
// tellen), anders het akkoord.
function rechteMaat(akk, tellen, begin, tel, maat) {
  const n = akk.length;
  const g = [];
  for (let b = 0; b < tellen; b++) {
    const t = begin + b * tel;
    g.push({ t, soort: "tik", midi: [], duur: TIK_DUUR, maat });
    if (!n) continue;
    const k = Math.floor(b * n / tellen);
    const a = akk[k];
    if (!a || a.nc) continue;
    const eerste = b === Math.ceil(k * tellen / n);
    if (eerste || (tellen % 2 === 0 && b % 2 === 0)) {
      g.push({ t, soort: "bas", midi: [a.bas], duur: 0.9 * tel, maat });
    } else {
      g.push({ t, soort: "akkoord", midi: a.akkoord, duur: 0.5 * tel, maat });
    }
  }
  return g;
}

// Schema-maten -> {gebeurtenissen: [{t, soort, midi, duur, maat, sterkte}], duur} in seconden.
// start/eind: maatnummers (inclusief). inteltel: tikken vooraf (maat null).
// stijl: recht of een sleutel uit STIJLEN (die alleen bij 4 tellen; anders recht).
// drums: drumregels i.p.v. de tik tijdens het spelen (alleen in een tabelstijl).
function speelplan(maten, { bpm, tellen = 4, start = -Infinity, eind = Infinity, inteltel = tellen,
  stijl = "recht", drums = false }) {
  const tel = 60 / bpm;
  const pat = tellen === 4 ? STIJLEN[stijl] : undefined;
  const g = [];
  for (let i = 0; i < inteltel; i++) g.push({ t: i * tel, soort: "tik", midi: [], duur: TIK_DUUR, maat: null });
  const gekozen = maten.filter(m => m.nr >= start && m.nr <= eind);
  gekozen.forEach((m, mi) => {
    const begin = (inteltel + mi * tellen) * tel;
    const akk = m.akkoorden.map(a => akkoordMidi(a.concert));
    g.push(...(pat ? stijlMaat(pat, akk, begin, tel, m.nr, drums) : rechteMaat(akk, tellen, begin, tel, m.nr)));
  });
  return { gebeurtenissen: g, duur: (inteltel + gekozen.length * tellen) * tel };
}
```

Let op: `STIJLEN` gebruikt `SHUFFLE` niet, `linksTonen` wel; `SHUFFLE` moet boven `linksTonen` staan (dat doet hij). `TIK_DUUR` staat al boven dit blok.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_speler.py -q`
Expected: alles PASS — ook de bestaande shuffle-tests (`test_shuffle_*`) en rechte-patroon-tests, ongewijzigd.

- [ ] **Step 5: Commit**

```bash
git add web/speler.js tests/test_speler.py
git commit -m "Stijlen: shuffle, pop, ballad en funk als tabel in speelplan, met drumregels

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011HT47tgB5e8kbi5GEnQEKY"
```

---

### Task 2: Drumsamples, `laadSamples`, `maakGeluid`

**Files:**
- Create: `scripts/drum-samples.sh`, `web/drums/{kick,snare,hihat}.mp3`, `web/drums/LICENSE-Apache-2.0.txt`
- Modify: `web/speler.js` (`speelGeluid` met `sterkte`; `laadPiano` via `laadSamples`; `pianoGeluid` via `maakGeluid`)
- Test: `tests/test_speler.py`

**Interfaces:**
- Consumes: gebeurtenissen uit Task 1 (`soort` incl. `kick/snare/hihat`, optioneel `sterkte`).
- Produces:
  - `laadSamples(ctx, paden, haal = fetch)` → `Promise<{sleutel: AudioBuffer}>`; fout → `Error("<pad>: <status>")`.
  - `laadPiano(ctx, haal)` en `laadDrums(ctx, haal)` (= `laadSamples` met `PIANO_PADEN` / `DRUM_PADEN`).
  - `maakGeluid({piano = null, drums = null})` → `(ctx, e, wanneer, uit) => void`.
  - `pianoGeluid(buffers)` = `maakGeluid({piano: buffers})` (blijft bestaan).

- [ ] **Step 1: Samples maken**

Maak `scripts/drum-samples.sh`:

```bash
#!/usr/bin/env bash
# Haalt het akoestische drumstel uit Google Chrome Labs web-audio-samples (Apache-2.0) op
# en maakt het klein voor web/drums/<naam>.mp3: mono, stilte vooraf eraf, max 1 s met fade-out.
set -euo pipefail
cd "$(dirname "$0")/.."
BRON=https://raw.githubusercontent.com/GoogleChromeLabs/web-audio-samples/main
WERK=$(mktemp -d)
trap 'rm -rf "$WERK"' EXIT
mkdir -p web/drums
for n in kick snare hihat; do
  curl -fsSL "$BRON/src/sounds/drum-samples/acoustic-kit/$n.wav" -o "$WERK/$n.wav"
  ffmpeg -loglevel error -y -i "$WERK/$n.wav" -ac 1 -map_metadata -1 \
    -af "silenceremove=start_periods=1:start_threshold=-50dB,atrim=0:1,afade=t=out:st=0.8:d=0.2" \
    -b:a 96k "web/drums/$n.mp3"
done
curl -fsSL "$BRON/LICENSE" -o web/drums/LICENSE-Apache-2.0.txt
ls -l web/drums
```

Run: `chmod +x scripts/drum-samples.sh && scripts/drum-samples.sh`
Expected: `kick.mp3`, `snare.mp3`, `hihat.mp3` (elk ~3–15 KB) en `LICENSE-Apache-2.0.txt`.

Run: `for f in web/drums/*.mp3; do ffprobe -v error -show_entries format=duration -of csv=p=0 "$f"; ffmpeg -hide_banner -i "$f" -af volumedetect -f null - 2>&1 | grep -o "max_volume: [-0-9.]* dB"; done; head -3 web/drums/LICENSE-Apache-2.0.txt`
Expected: elke duur ≤ ~1,05 s; max_volume niet lager dan ~−30 dB (dus geen stilte); licentiekop "Apache License".

- [ ] **Step 2: Write the failing tests**

In `tests/test_speler.py`: pas de verwachting van `test_laad_piano_een_fout_is_alles_fout` aan (de foutmelding noemt nu het pad):

```python
def test_laad_piano_een_fout_is_alles_fout():
    r = js("const FOUT = 'piano/51.mp3';" + LAAD + " return laadPiano(ctx, haal); })()")
    assert r == {"fout": "piano/51.mp3: 404"}
```

En onderaan:

```python
def test_drumsamples_aanwezig_en_licentie():
    for n in ("kick", "snare", "hihat"):
        f = WEB / "drums" / f"{n}.mp3"
        assert f.is_file(), f
        assert 1_000 < f.stat().st_size < 30_000, f
    assert "Apache License" in (WEB / "drums" / "LICENSE-Apache-2.0.txt").read_text()


def test_laad_drums_haalt_drie_samples():
    r = js("const FOUT = null;" + LAAD + " return laadDrums(ctx, haal).then(b =>"
           " ({gevraagd, sleutels: Object.keys(b).sort(), kick: b.kick})); })()")
    assert r["gevraagd"] == ["drums/kick.mp3", "drums/snare.mp3", "drums/hihat.mp3"]
    assert r["sleutels"] == ["hihat", "kick", "snare"]
    assert r["kick"] == "dec:drums/kick.mp3"


NEP_GELUID = ("(() => { const bronnen = []; let oscs = 0;"
              " const param = log => ({setValueAtTime(v) { log.push(v); }, linearRampToValueAtTime() {},"
              " exponentialRampToValueAtTime() {}});"
              " const knoop = x => Object.assign({connect: y => y}, x); let laatsteGain = [];"
              " const ctx = {createGain: () => { laatsteGain = []; return knoop({gain: param(laatsteGain)}); },"
              " createBufferSource: () => { const b = knoop({playbackRate: {}, start() {}, stop() {}});"
              " bronnen.push(b); return b; },"
              " createOscillator: () => { oscs += 1; return knoop({frequency: {}, start() {}, stop() {}}); }};"
              " const DR = {kick: 'K', snare: 'S', hihat: 'H'};")


def test_maak_geluid_drums_met_sterkte():
    r = js(NEP_GELUID + " const g = maakGeluid({drums: DR});"
           " g(ctx, {soort: 'kick', midi: [], duur: 0.5, maat: 1, sterkte: 0.5}, 1, {});"
           " return {buf: bronnen.map(b => b.buffer), gain: laatsteGain[0], oscs}; })()")
    assert r == {"buf": ["K"], "gain": 0.45, "oscs": 0}


def test_maak_geluid_inteltik_wordt_hihat_met_drums():
    r = js(NEP_GELUID + " const g = maakGeluid({drums: DR});"
           " g(ctx, {soort: 'tik', midi: [], duur: 0.03, maat: null}, 1, {});"
           " g(ctx, {soort: 'tik', midi: [], duur: 0.03, maat: 1}, 1, {});"
           " return {buf: bronnen.map(b => b.buffer), oscs}; })()")
    assert r == {"buf": ["H"], "oscs": 1}  # alleen de inteltik wordt hi-hat


def test_maak_geluid_zonder_piano_synth_en_zonder_drums_stil():
    r = js(NEP_GELUID + " maakGeluid({drums: DR})(ctx, {soort: 'bas', midi: [36, 43], duur: 0.5, maat: 1}, 1, {});"
           " const synth = oscs;"
           " maakGeluid({})(ctx, {soort: 'snare', midi: [], duur: 0.5, maat: 1}, 1, {});"
           " return {synth, bronnen: bronnen.length, oscs}; })()")
    assert r == {"synth": 2, "bronnen": 0, "oscs": 2}


def test_synth_volgt_sterkte():
    r = js("(() => { const pieken = []; const knoop = x => Object.assign({connect: y => y}, x);"
           " const ctx = {createOscillator: () => knoop({frequency: {}, start() {}, stop() {}}),"
           " createGain: () => knoop({gain: {setValueAtTime() {}, exponentialRampToValueAtTime() {},"
           " linearRampToValueAtTime(v) { pieken.push(v); }}})};"
           " speelGeluid(ctx, {soort: 'akkoord', midi: [60], duur: 0.3, maat: 1}, 0, {});"
           " speelGeluid(ctx, {soort: 'akkoord', midi: [60], duur: 0.3, maat: 1, sterkte: 0.5}, 0, {});"
           " return pieken; })()")
    assert r[1] == r[0] / 2
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_speler.py -q -k "laad or drums or maak_geluid or synth_volgt"`
Expected: FAIL — `laadDrums is not defined`, `maakGeluid is not defined`, foutmelding nog `piano 51: 404`, `r[1] == r[0]` (sterkte genegeerd). `test_drumsamples_aanwezig_en_licentie` slaagt (samples uit Step 1).

- [ ] **Step 4: Implement**

In `web/speler.js`, in `speelGeluid`: de `sterkte`-regel wordt

```js
  const sterkte = (e.soort === "tik" && e.maat === null ? INTELTIK : KLANK[e.soort][1])
    * (e.sterkte === undefined ? 1 : e.sterkte);
```

Vervang `laadPiano`, `dichtsteSample` blijft, en `pianoGeluid` (het blok van `// Haalt en decodeert alle samples` t/m het einde van `pianoGeluid`, maar **`binnen` blijft staan**) door:

```js
const PIANO_PADEN = Object.fromEntries(PIANO_NOTEN.map(m => [m, `piano/${m}.mp3`]));
// Akoestisch drumstel uit Google Chrome Labs web-audio-samples (Apache-2.0): web/drums/<naam>.mp3.
const DRUM_PADEN = { kick: "drums/kick.mp3", snare: "drums/snare.mp3", hihat: "drums/hihat.mp3" };
const DRUMSTERKTE = { kick: 0.9, snare: 0.6, hihat: 0.25 };
const INTEL_HIHAT = 0.5;

// {sleutel: pad} -> {sleutel: AudioBuffer}; één fout = alles fout (geen half drumstel of halve piano).
function laadSamples(ctx, paden, haal = fetch) {
  return Promise.all(Object.entries(paden).map(([sleutel, pad]) => haal(pad)
    .then(r => { if (!r.ok) throw new Error(`${pad}: ${r.status}`); return r.arrayBuffer(); })
    .then(data => ctx.decodeAudioData(data))
    .then(buf => [sleutel, buf])))
    .then(paren => Object.fromEntries(paren));
}
const laadPiano = (ctx, haal) => laadSamples(ctx, PIANO_PADEN, haal);
const laadDrums = (ctx, haal) => laadSamples(ctx, DRUM_PADEN, haal);
```

(`binnen` en `dichtsteSample` blijven waar ze staan.) Daarna, op de plek van het oude `pianoGeluid`:

```js
function speelBuffer(ctx, buffer, rate, sterkte, wanneer, los, uit) {
  const bron = ctx.createBufferSource();
  bron.buffer = buffer;
  bron.playbackRate.value = rate;
  const vol = ctx.createGain();
  vol.gain.setValueAtTime(sterkte, wanneer);
  if (los !== null) {
    vol.gain.setValueAtTime(sterkte, los);
    vol.gain.linearRampToValueAtTime(0.0001, los + LOSLATEN);
  }
  bron.connect(vol).connect(uit);
  bron.start(wanneer);
  if (los !== null) bron.stop(los + LOSLATEN + 0.02);
}

// Geluidsfunctie voor de Speler. piano/drums: buffers of null. Zonder piano speelt de synth;
// zonder drums klinken drumgebeurtenissen niet en blijft de tik de synth.
function maakGeluid({ piano = null, drums = null } = {}) {
  return (ctx, e, wanneer, uit) => {
    const s = e.sterkte === undefined ? 1 : e.sterkte;
    if (e.soort === "tik") {
      if (drums && e.maat === null) speelBuffer(ctx, drums.hihat, 1, INTEL_HIHAT, wanneer, null, uit);
      else speelGeluid(ctx, e, wanneer, uit);
      return;
    }
    if (e.soort in DRUMSTERKTE) {
      if (drums) speelBuffer(ctx, drums[e.soort], 1, DRUMSTERKTE[e.soort] * s, wanneer, null, uit);
      return;
    }
    if (!piano) { speelGeluid(ctx, e, wanneer, uit); return; }
    for (const m of e.midi) {
      const sample = dichtsteSample(m);
      speelBuffer(ctx, piano[sample], Math.pow(2, (m - sample) / 12), PIANO_STERKTE[e.soort] * s,
        wanneer, wanneer + e.duur, uit);
    }
  };
}

const pianoGeluid = buffers => maakGeluid({ piano: buffers });
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_speler.py tests/test_web.py -q`
Expected: alles PASS (ook `test_piano_geluid_dichtstbijzijnde_sample_en_toonhoogte` en de harness-tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/drum-samples.sh web/drums web/speler.js tests/test_speler.py
git commit -m "Stijlen: drumsamples (Chrome Labs, Apache-2.0), laadSamples en maakGeluid

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011HT47tgB5e8kbi5GEnQEKY"
```

---

### Task 3: Stijl per nummer op de server

**Files:**
- Modify: `app/db.py` (`SCHEMA`, `verbind`, nieuw `zet_stijl`)
- Modify: `app/main.py` (model `Stijl`, route `PUT /api/songs/{song_id}/stijl`, `stijl` in het schema-antwoord)
- Test: `tests/test_db.py`, `tests/test_api.py`

**Interfaces:**
- Produces: `db.zet_stijl(conn, song_id: int, stijl: str) -> bool`; `GET /api/songs/{id}/schema` → `"stijl": str`; `PUT /api/songs/{id}/stijl` body `{"stijl": "shuffle"|"pop"|"ballad"|"funk"}` → `{"ok": true}` | 404 | 422 | 401.

- [ ] **Step 1: Write the failing tests**

`tests/test_db.py`, onderaan:

```python
OUD_SONG = """CREATE TABLE song (
    id INTEGER PRIMARY KEY, setlist_id INTEGER NOT NULL, positie INTEGER NOT NULL,
    titel TEXT NOT NULL, artiest TEXT NOT NULL DEFAULT '', pdf_path TEXT NOT NULL, tempo INTEGER,
    maatsoort TEXT NOT NULL DEFAULT '4/4', voortekening INTEGER NOT NULL DEFAULT 0,
    regelstarts TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'gelezen')"""


def test_migratie_voegt_stijl_toe_aan_oude_database(tmp_path):
    import sqlite3
    pad = str(tmp_path / "oud.sqlite")
    oud = sqlite3.connect(pad)
    oud.execute("CREATE TABLE setlist (id INTEGER PRIMARY KEY, naam TEXT NOT NULL,"
                " created_at TEXT NOT NULL DEFAULT (datetime('now')))")
    oud.execute(OUD_SONG)
    oud.execute("INSERT INTO setlist (id, naam) VALUES (1, 'Next week')")
    oud.execute("INSERT INTO song (id, setlist_id, positie, titel, pdf_path, tempo)"
                " VALUES (1, 1, 1, 'Spooky', '/x.pdf', 107)")
    oud.commit()
    oud.close()
    c = db.verbind(pad)
    s = db.song(c, 1)
    assert (s["titel"], s["tempo"], s["stijl"]) == ("Spooky", 107, "shuffle")
    c.close()
    db.verbind(pad).close()  # tweede start: kolom bestaat al, geen fout


def test_zet_stijl(conn):
    sl = db.maak_setlist(conn, "Next week")
    sid = db.maak_song(conn, sl, "/x.pdf", KOP, REGELS, DELEN)
    assert db.song(conn, sid)["stijl"] == "shuffle"
    assert db.zet_stijl(conn, sid, "funk") is True
    assert db.song(conn, sid)["stijl"] == "funk"
    assert db.zet_stijl(conn, 999, "pop") is False
```

`tests/test_api.py`, onderaan:

```python
def test_stijl_per_nummer(maak):
    c = _login(maak())
    sid = _upload(c, _setlist(c)).json()["id"]
    assert c.get(f"/api/songs/{sid}/schema").json()["stijl"] == "shuffle"
    assert c.put(f"/api/songs/{sid}/stijl", json={"stijl": "pop"}).json() == {"ok": True}
    assert c.get(f"/api/songs/{sid}/schema").json()["stijl"] == "pop"
    assert c.put(f"/api/songs/{sid}/stijl", json={"stijl": "jazz"}).status_code == 422
    assert c.put("/api/songs/999/stijl", json={"stijl": "pop"}).status_code == 404


def test_stijl_zonder_login_401(maak):
    assert maak().put("/api/songs/1/stijl", json={"stijl": "pop"}).status_code == 401


def test_controleren_laat_stijl_staan(maak):
    c = _login(maak())
    sid = _upload(c, _setlist(c)).json()["id"]
    c.put(f"/api/songs/{sid}/stijl", json={"stijl": "ballad"})
    s = c.get(f"/api/songs/{sid}").json()
    body = {"titel": "Crazy", "artiest": "Lost Frequencies", "tempo": 103, "voortekening": -5,
            "regels": s["regels"],
            "delen": [{"naam": "Couplet", "start_maat": 1, "eind_maat": 8, "concert_key": "Bbm",
                       "key_source": "claude", "solo_geschikt": True}]}
    assert c.put(f"/api/songs/{sid}", json=body).status_code == 200
    assert c.get(f"/api/songs/{sid}/schema").json()["stijl"] == "ballad"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_db.py tests/test_api.py -q -k "stijl"`
Expected: FAIL — `KeyError: 'stijl'`, `AttributeError: module 'app.db' has no attribute 'zet_stijl'`, PUT geeft 404/405. `test_stijl_zonder_login_401` slaagt mogelijk al (de login-middleware weigert alles onder `/api/`) — dat pint het gedrag.

- [ ] **Step 3: Implement**

`app/db.py`, in `SCHEMA` bij `song`, na de `status`-regel (let op de komma):

```sql
    status TEXT NOT NULL DEFAULT 'gelezen',
    stijl TEXT NOT NULL DEFAULT 'shuffle'
```

In `verbind`, na `conn.executescript(SCHEMA)`:

```python
    # Oudere database: kolom stijl bestond nog niet (CREATE TABLE IF NOT EXISTS voegt hem niet toe).
    if "stijl" not in {r["name"] for r in conn.execute("PRAGMA table_info(song)")}:
        with conn:
            conn.execute("ALTER TABLE song ADD COLUMN stijl TEXT NOT NULL DEFAULT 'shuffle'")
```

Na `def song(...)` (of bij de andere song-functies):

```python
def zet_stijl(conn, song_id: int, stijl: str) -> bool:
    """Begeleidingsstijl van een nummer; False als het nummer niet bestaat."""
    with conn:
        return conn.execute("UPDATE song SET stijl = ? WHERE id = ?", (stijl, song_id)).rowcount > 0
```

`app/main.py`: bij de andere modellen:

```python
class Stijl(BaseModel):
    stijl: Literal["shuffle", "pop", "ballad", "funk"]
```

na de route `verwijder` (vóór `@api.get("/songs/{song_id}/schema")`):

```python
    @api.put("/songs/{song_id}/stijl")
    def zet_stijl(song_id: int, body: Stijl, conn=Depends(conn_dep)):
        if not db.zet_stijl(conn, song_id, body.stijl):
            raise HTTPException(404, "Nummer niet gevonden.")
        return {"ok": True}
```

en in het schema-antwoord, na `"maatsoort": s["maatsoort"], …`-regel: voeg `"stijl": s["stijl"],` toe (bv. direct na `"instrument": instrument,`).

(`Literal` is in `app/main.py` al geïmporteerd voor de `instrument`-parameter; controleer met `grep -n "Literal" app/main.py`.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: alles PASS.

- [ ] **Step 5: Reservekopie live database en commit**

Run: `cp -p data/blueslab.sqlite data/blueslab.sqlite.voor-stijl-2026-10-16 && ls -l data/`
Expected: de kopie staat naast het origineel (`data/` staat buiten git).

```bash
git add app/db.py app/main.py tests/test_db.py tests/test_api.py
git commit -m "Stijlen: stijl per nummer in de database (met migratie) en PUT /api/songs/{id}/stijl

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011HT47tgB5e8kbi5GEnQEKY"
```

---

### Task 4: Stijlknoppen, piano en drums laden, docs

**Files:**
- Modify: `web/app.js` (`paginaSong`), `web/song.html` (hulptekst, versies), `web/index.html`, `web/setlist.html`, `web/controle.html` (versies)
- Modify: `tests/web_harness.js`, `tests/test_web.py`
- Modify: `README.md`, `CLAUDE.md`, spec-status

**Interfaces:**
- Consumes: `speelplan(…, {stijl, drums})` (Task 1); `laadPiano`, `laadDrums`, `maakGeluid`, `binnen` (Task 2); schema `stijl` en `PUT /api/songs/{id}/stijl` (Task 3).

- [ ] **Step 1: Harness uitbreiden**

In `tests/web_harness.js`:

1. Kopcommentaar: voeg `BLUESLAB_DRUMS (ok | fout)` en `BLUESLAB_PUT_STATUS` toe.
2. Na de `pianoAntwoord`-definitie:

```js
const drumsAntwoord = async () => {
  const ok = (process.env.BLUESLAB_DRUMS || "ok") !== "fout";
  return { ok, status: ok ? 200 : 404, arrayBuffer: async () => new ArrayBuffer(8) };
};
const puts = [];   // [pad, body] van elke PUT
```

3. `fetch` wordt (tweede parameter `init`):

```js
  fetch: async (pad, init) => {
    fetches.push(pad);
    if (pad.startsWith("piano/")) return pianoAntwoord();
    if (pad.startsWith("drums/")) return drumsAntwoord();
    let status = ikStatus;
    if (init && init.method === "PUT") {
      puts.push([pad, init.body]);
      status = Number(process.env.BLUESLAB_PUT_STATUS || ikStatus);
    }
    return { status, ok: status < 400,
      json: async () => (status < 400 ? antwoordVoor(pad) : { detail: "Log eerst in." }) };
  },
```

4. Na het laden van de scripts (na de `for (const f of ["speler.js", "app.js"])`-lus) `speelplan` aftappen:

```js
const plannen = [];  // opties van elke speelplan-aanroep door de app
const echtPlan = ctx.speelplan;
ctx.speelplan = (maten, opties) => { plannen.push(opties); return echtPlan(maten, opties); };
```

5. Uitvoer erbij: `puts, plannen, knoppen: [...new Set(gemaakt.filter(e => e._on.click).map(e => e._tekst))]`.

Run: `.venv/bin/python -m pytest tests/test_web.py -q`
Expected: alles PASS (de app laadt nog geen drums; niets veranderd in het gedrag).

- [ ] **Step 2: Write the failing tests**

In `tests/test_web.py`: in de bestaande test `test_tijdens_laden_knop_uit_en_geen_start` wordt de verwachte knoptekst `"Laden…"`:

```python
    assert r["speelknop"] == {"tekst": "Laden…", "uit": True}
```

En onderaan:

```python
# --- Stijlen met drums ----------------------------------------------------------

def _drum_fetches(r):
    return [f for f in r["fetches"] if f.startswith("drums/")]


def test_stijlknoppen_bij_vier_kwart():
    assert {"Shuffle", "Pop", "Ballad", "Funk"} <= set(_speel()["knoppen"])


def test_geen_stijlknoppen_bij_drie_kwart():
    schema = dict(SCHEMA, maatsoort="3/4")
    r = draai("song", 200, "?id=1", {"/api/songs/": schema, "/api/setlists/": SETLIST}, audio=True)
    assert "Pop" not in r["knoppen"]
    assert r["nullKinderen"] == 0


def test_tik_op_pop_bewaart_stijl():
    r = _speel("tekst=Pop")
    assert r["puts"] == [["/api/songs/1/stijl", '{"stijl":"pop"}']]
    assert r["hulp"] == ""


def test_stijl_bewaren_mislukt_meldt():
    r = _speel("tekst=Pop", BLUESLAB_PUT_STATUS="404")  # oude server zonder de route
    assert "Stijl niet bewaard" in r["hulp"]


def test_speel_geeft_stijl_en_drums_door():
    r = _speel("tekst=▶ Speel")
    assert len(_piano_fetches(r)) == 15 and len(_drum_fetches(r)) == 3
    assert (r["plannen"][0]["stijl"], r["plannen"][0]["drums"]) == ("shuffle", True)  # schema zonder stijl


def test_stijl_uit_schema():
    schema = dict(SCHEMA, stijl="funk")
    r = draai("song", 200, "?id=1", {"/api/songs/": schema, "/api/setlists/": SETLIST},
              audio=True, acties=["tekst=▶ Speel"])
    assert r["plannen"][0]["stijl"] == "funk"


def test_stijl_wisselen_tijdens_spelen_herstart():
    r = _speel("tekst=▶ Speel", "tekst=Pop")
    assert r["starts"] == 2
    assert r["plannen"][-1]["stijl"] == "pop"


def test_stijl_kiezen_tijdens_laden_start_niet():
    r = _speel("tekst=▶ Speel", "tekst=Pop", BLUESLAB_PIANO="hangt")
    assert r["starts"] == 0


def test_drums_mislukt_met_tik_en_melding():
    r = _speel("tekst=▶ Speel", BLUESLAB_DRUMS="fout")
    assert r["starts"] == 1
    assert r["plannen"][0]["drums"] is False
    assert "Drums niet geladen" in r["hulp"] and "Piano" not in r["hulp"]


def test_piano_mislukt_drums_wel():
    r = _speel("tekst=▶ Speel", BLUESLAB_PIANO="fout")
    assert r["plannen"][0]["drums"] is True
    assert "Piano niet geladen" in r["hulp"] and "Drums" not in r["hulp"]


def test_hulptekst_noemt_drums():
    html = (Path(__file__).parent.parent / "web" / "song.html").read_text()
    assert "Google Chrome Labs" in html and "Apache-2.0" in html
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_web.py -q`
Expected: FAIL — geen stijlknoppen, geen `drums/`-fetches, `plannen[0]` zonder `stijl`/`drums`, knoptekst nog "Piano laden…", hulptekst zonder drums. (`test_stijl_kiezen_tijdens_laden_start_niet` faalt omdat "Pop" nog niet bestaat: "niets om te klikken".)

- [ ] **Step 4: Implement**

In `web/app.js`:

1. Boven `async function paginaSong()`:

```js
const STIJL_NAMEN = [["shuffle", "Shuffle"], ["pop", "Pop"], ["ballad", "Ballad"], ["funk", "Funk"]];
```

2. In `paginaSong` het piano-blok vervangen. Oud:

```js
  // Piano: één laadpoging per pagina (nieuw → laden → klaar of mislukt).
  let piano = "nieuw";
```

Nieuw:

```js
  // Samples: één laadpoging per pagina (nieuw → laden → klaar); piano en drums los van elkaar.
  let laden = "nieuw";
  let drumsGeladen = false;
  let stijl = "shuffle";
```

3. `speelKnop` wordt:

```js
  async function speelKnop() {
    if (speler.speelt) { speler.stop(); return; }
    if (laden === "laden") return;
    const ctx = speler.ontgrendel();  // binnen de tik, vóór de await (iOS)
    if (laden === "nieuw") {
      laden = "laden";
      wegTijdensLaden = false;
      tekenSpeler();
      const [piano, drums] = await Promise.all([
        binnen(laadPiano(ctx), 10000).catch(() => null),
        binnen(laadDrums(ctx), 10000).catch(() => null)]);
      laden = "klaar";
      drumsGeladen = Boolean(drums);
      speler.geluid = maakGeluid({ piano, drums });
      const meldingen = [piano ? "" : "Piano niet geladen — eenvoudige klank.",
        drums ? "" : "Drums niet geladen — met tik."].filter(Boolean);
      if (meldingen.length) $("#hulp").textContent = `${meldingen.join(" ")} Tik op een maat om daar te beginnen.`;
      if (wegTijdensLaden || document.visibilityState === "hidden") { tekenSpeler(); return; }
    }
    speel();
  }

  function kiesStijl(k) {
    wijzig(() => { stijl = k; });
    api(`/api/songs/${id}/stijl`, { method: "PUT", json: { stijl: k } }).catch(() => {
      $("#hulp").textContent = "Stijl niet bewaard. Tik op een maat om daar te beginnen.";
    });
  }
```

4. In `speel()` beide `speelplan`-aanroepen: `stijl: "shuffle"` → `stijl, drums: drumsGeladen`:

```js
    speler.start(speelplan(maten, { bpm, tellen, start: b.start, eind: b.eind, stijl, drums: drumsGeladen }),
      oefen.herhaal ? speelplan(maten, { bpm, tellen, start: b.lusStart, eind: b.eind, inteltel: 0,
        stijl, drums: drumsGeladen }) : null);
```

5. `tekenSpeler()` wordt:

```js
  function tekenSpeler() {
    const vanaf = speelBereik(schema.delen, oefen.start, false).start;
    $("#speler").replaceChildren(...[
      el("button", { class: "speelknop", disabled: laden === "laden", onclick: speelKnop },
        laden === "laden" ? "Laden…" : speler.speelt ? "■ Stop" : "▶ Speel"),
      el("span", { class: "klein" }, `vanaf maat ${vanaf}`),
      el("div", { class: "wissel tempo" }, [50, 75, 100].map(p => el("button",
        { "aria-pressed": String(p === oefen.tempo), onclick: () => wijzig(() => { oefen.tempo = p; }) },
        `${p}%`))),
      tellenUit(schema.maatsoort) === 4 ? el("div", { class: "wissel stijl" }, STIJL_NAMEN.map(([k, naam]) =>
        el("button", { "aria-pressed": String(k === stijl), onclick: () => kiesStijl(k) }, naam))) : null,
      el("button", { class: "stil herhaal", "aria-pressed": String(oefen.herhaal),
        onclick: () => wijzig(() => { oefen.herhaal = !oefen.herhaal; }) },
        oefen.herhaal ? "🔁 Herhaal dit deel: aan" : "🔁 Herhaal dit deel"),
    ].filter(Boolean));  // replaceChildren maakt van null de tekst "null"
  }
```

6. In de `visibilitychange`-handler: `if (piano === "laden") wegTijdensLaden = true;` → `if (laden === "laden") wegTijdensLaden = true;`.

7. In `laad(inst)`, binnen `if (eersteKeer) {`, direct na `eersteKeer = false;`:

```js
      if (STIJL_NAMEN.some(([k]) => k === s.stijl)) stijl = s.stijl;  // oude server: geen stijl → shuffle
```

Controleer: `grep -n 'piano ===\|piano = "' web/app.js` geeft niets meer (de oude standvariabele is weg).

- [ ] **Step 5: Hulptekst en versies**

`web/song.html`, de hulpregel wordt:

```html
    <p id="hulp" class="klein" hidden>Tik op een maat om daar te beginnen. Hoor je niets? Zet het geluid aan. Piano: Salamander Grand Piano (Alexander Holm, CC-BY 3.0). Drums: Google Chrome Labs web-audio-samples (Apache-2.0).</p>
```

Run: `sed -i 's/speler\.js?v=3/speler.js?v=4/' web/song.html && sed -i 's/app\.js?v=8/app.js?v=9/' web/*.html && grep -n "v=" web/*.html`
Expected: `speler.js?v=4` in song.html, `app.js?v=9` in alle vier.

- [ ] **Step 6: Run de hele suite**

Run: `.venv/bin/python -m pytest -q`
Expected: alles PASS, 1 skipped.

- [ ] **Step 7: Live controleren (statisch) en geluidsvoorbeelden**

Run: `curl -sI https://blues.felixisfelix.com/drums/kick.mp3 | grep -iE "^(HTTP|content-type)"; curl -s https://blues.felixisfelix.com/song.html | grep -o 'speler.js?v=[0-9]*\|app.js?v=[0-9]*'`
Expected: `HTTP/2 200`, `audio/mpeg`, `speler.js?v=4`, `app.js?v=9`.

Render per stijl 4 maten met de echte code in headless chromium (zelfde aanpak als bij de piano-shuffle: probe-pagina in de scratchpad met symlinks naar `web/speler.js`, `web/piano`, `web/drums`, een traag plaatje dat het load-event openhoudt, `OfflineAudioContext`, `maakGeluid({piano, drums})`, WAV → mp3). Maten: pop `C G Am F`, ballad `C Am F G`, funk `Am7 D7 Am7 D7`, shuffle `G7 C7 G7 D7`; tempo pop 110, ballad 70, funk 100, shuffle 107.
Expected: vier mp3's, piek niet boven −1 dB (geen oversturing). Stuur ze Bob na de eindreview.

- [ ] **Step 8: Docs**

`README.md`, in de alinea over oefenen: vervang de zin over de shuffle door

```markdown
**▶ Speel** speelt uit de concert-akkoorden een begeleiding in de stijl van het nummer
(**Shuffle · Pop · Ballad · Funk**, per nummer bewaard) met piano en drums.
```

en voeg na de Salamander-zin toe:

```markdown
Drums: het akoestische drumstel uit Google Chrome Labs `web-audio-samples` (Apache-2.0, licentie in
`web/drums/`), verkleind met `scripts/drum-samples.sh`. Lukken de drums niet, dan klinkt een tik.
```

`CLAUDE.md`, na de story "Meespelen met piano en shuffle":

```markdown
- **Stijlen per nummer met drums** (Shuffle · Pop · Ballad · Funk): spec
  `docs/superpowers/specs/2026-10-16-stijlen-drums-design.md`, plan `docs/superpowers/plans/2026-10-16-stijlen-drums.md`.
  Patronen = tabellen `STIJLEN` in `web/speler.js`; stijl per nummer in `song.stijl` (`PUT /api/songs/{id}/stijl`).
  *Status: gebouwd (2026-10-16), branch `stijlen-drums`.*
```

Spec-status: "**Status:** ontwerp, goedgekeurd in de chat (2026-10-16)" → "**Status:** gebouwd (2026-10-16)".

- [ ] **Step 9: Commit**

```bash
git add web/app.js web/*.html tests/web_harness.js tests/test_web.py README.md CLAUDE.md \
  docs/superpowers/specs/2026-10-16-stijlen-drums-design.md
git commit -m "Stijlen: stijlknoppen per nummer, piano en drums los laden, naamsvermelding drums

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011HT47tgB5e8kbi5GEnQEKY"
```

Na de merge/push (Bobs keuze): Bob herstart de dienst (`sudo systemctl restart blueslab.service`, in zijn SSH-app); daarna `curl -s https://blues.felixisfelix.com/api/songs/1/schema` geeft 401 (login), en in de journal staat geen migratiefout: `journalctl -u blueslab.service -n 20 --no-pager`.
