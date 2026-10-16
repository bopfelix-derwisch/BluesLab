# BluesLab — meespelen met piano en shuffle

**Datum:** 2026-10-16 · **Status:** ontwerp, goedgekeurd in de chat (2026-10-16) · **Bouwt op:** oefenen (`2026-10-15-oefenen-design.md`)

## 1. Doel

De meespeel-begeleiding klinkt nu als piepjes (driehoeksgolven) in een recht patroon. Bob wil
"iets mooiers met piano-akkoorden". Gekozen in de chat:
- **echte pianoklank** (samples), op de eigen site;
- **shuffle-ritme** in plaats van recht;
- de **zachte tik blijft** op elke tel;
- een **melodielijn komt later** (buiten scope; de PDF heeft geen melodie).

**Succes:** op de iPad klinkt ▶ Speel als een bluespiano in shuffle, strak op tempo, met dezelfde
bediening als nu (startmaat, tempo, herhalen, Stop). Lukt het laden van de piano niet, dan werkt
het meespelen gewoon door met de oude klank.

## 2. Pianoklank

### Samples
- Bron: **Salamander Grand Piano** (Alexander Holm, **CC-BY 3.0**), de mp3's die Tone.js
  publiceert op `https://tonejs.github.io/audio/salamander/` (`C2.mp3`, `Ds2.mp3`, `Fs2.mp3`, …).
- **15 noten**, elke kleine terts van C2 (MIDI 36) t/m F♯5 (MIDI 78). Dat dekt de linkerhand
  (C2–A3) en de akkoorden (E3–F5); elke toon ligt hooguit anderhalve halve toon van een sample.
- Bewerkt met ffmpeg: mono, stilte aan het begin eraf, ingekort tot 2 s met een fade-out in de
  laatste 0,3 s, ~96 kbps. Samen rond 350 KB.
- In de repo: `web/piano/<midi>.mp3` (bv. `web/piano/36.mp3`), plus `scripts/piano-samples.sh`
  dat ze reproduceerbaar ophaalt en bewerkt. De server serveert ze al (StaticFiles op `web/`);
  geen serverwijziging. Ze vallen onder dezelfde 4 uur browsercache van Cloudflare.
- Naamsvermelding (verplicht onder CC-BY): in de hulptekst op de songpagina ("Piano: Salamander
  Grand Piano, Alexander Holm, CC-BY 3.0") en in de README.

### Afspelen (`web/speler.js`)
- `PIANO_NOTEN = [36, 39, …, 78]`.
- `laadPiano(ctx, haal = fetch)` → Promise van `{midi: AudioBuffer}`: haalt alle 15 bestanden en
  decodeert ze met `ctx.decodeAudioData`. Faalt er één, dan faalt het geheel (geen halve piano).
- `pianoGeluid(buffers)` → een functie met dezelfde vorm als `speelGeluid(ctx, e, wanneer, uit)`,
  zodat `Speler` niet verandert:
  - `tik` → doorgeven aan `speelGeluid` (synth-tik zoals nu);
  - elke toon in `e.midi`: dichtstbijzijnde sample `s`, `AudioBufferSourceNode` met
    `playbackRate = 2^((m − s)/12)`;
  - volume per toon: linkerhand ~0,5, rechterhand ~0,3 (af te stemmen op het gehoor); de toon
    klinkt tot `wanneer + duur` en dempt dan in 80 ms (als een loslatende toets).

### Laden (`web/app.js`)
- Eerste tik op ▶ op de pagina:
  1. **binnen de tik** de audio ontgrendelen (iOS-regel): nieuwe methode `Speler.ontgrendel()`
     maakt de `AudioContext` aan, hervat hem en zet `navigator.audioSession.type = "playback"`.
     `start()` gebruikt dezelfde methode;
  2. knop toont **"Piano laden…"** (niet klikbaar);
  3. `laadPiano` met een tijdslimiet van 10 s;
  4. gelukt → `speler.geluid = pianoGeluid(buffers)`; mislukt → oude klank houden en in de
     hulpregel "Piano niet geladen — eenvoudige klank." tonen;
  5. daarna `speel()` zoals nu, maar alleen als de pagina nog zichtbaar is.
- Daarna (zelfde pagina) wordt niet opnieuw geladen, ook niet na een mislukte poging.

## 3. Shuffle-patroon (`speelplan`)

- Nieuwe optie: `speelplan(maten, {…, stijl = "recht"})`. De app geeft `stijl: "shuffle"` mee.
  Shuffle geldt **alleen bij 4 tellen**; bij andere maatsoorten blijft het rechte patroon van nu.
- Elke tel krijgt twee **zwingende achtsten**: op `t` (lang, 2/3 tel) en op `t + 2/3 tel`
  (kort, 1/3 tel). Duur van de tonen: 0,9 × hun deel van de tel.
- **Linkerhand** (`soort: "bas"`, twee tonen tegelijk), op beide achtsten van elke tel.
  Per positie `p` binnen het akkoord (tel 0, 1, 2, … sinds het akkoord begon):
  `[grondtoon + kwint, grondtoon + sext, grondtoon + kleine septiem, grondtoon + sext][p % 4]`.
  - Grondtoon: `36 + pc` van de grondtoon (C2–B2). Sext = kwint + 2, septiem = kwint + 3.
  - Twee akkoorden in een maat: elk een halve maat → kwint, sext.
  - Geen reine kwint (dim, aug): steeds grondtoon + de eigen kwint van het akkoord.
  - Slash-akkoord (Bbm7/F): alleen de basnoot (`36 + pc` van de slash-noot), op dezelfde
    achtsten.
- **Rechterhand** (`soort: "akkoord"`): het akkoord (de ligging van nu, E3–E♭4 grondtoon) kort
  (0,25 tel) op **tel 2 en 4** (index 1 en 3), met het akkoord dat op die tel klinkt.
- **Tik** (`soort: "tik"`) op elke tel, zacht; de inteltel-tikken blijven hoger en iets harder.
- N.C., lege maat of onleesbaar akkoord: alleen de tik.
- De vorm van de gebeurtenissen blijft `{t, soort, midi, duur, maat}`; `Speler` en de cursor
  veranderen niet.
- `akkoordMidi` geeft daarvoor ook `grond` (MIDI `36 + pc` van de grondtoon), `kwint` (halve
  tonen: 7, 6 of 8) en `slash` (true/false) terug.

## 4. Fouten
- Piano laden mislukt of duurt langer dan 10 s → oude klank, melding in de hulpregel; spelen werkt.
- Geen Web Audio → speelknop verborgen (zoals nu).
- Pagina verborgen tijdens het laden → niet starten.

## 5. Testen
- `speelplan` met `stijl: "shuffle"` op 100 bpm: tijden van de achtsten na de inteltmaat (+0, +0,4, +0,6, +1,0 s …),
  het patroon kwint-sext-septiem-sext, twee akkoorden per maat (kwint, sext), slash-akkoord
  (één toon), dim (alleen kwint), N.C. (alleen tik), rechterhand op index 1 en 3, 3/4 blijft
  recht, `stijl` weglaten geeft het oude patroon (bestaande tests blijven groen).
- `akkoordMidi`: `grond`, `kwint`, `slash` voor G7, Bdim, Bbm7/F.
- `pianoGeluid` met een nep-context: dichtstbijzijnde sample en `playbackRate` (bv. MIDI 37 →
  sample 36, rate 2^(1/12)); tik gaat naar de synth.
- `laadPiano` met een nep-`haal`: 15 bestanden opgevraagd; één mislukt → Promise faalt.
- Harness (`tests/web_harness.js`): eerste ▶ toont "Piano laden…" en start daarna; mislukt laden
  → speelt met de oude klank en toont de melding.
- Handmatig op de iPad: klinkt het als piano, zwingt het, is het strak, is de balans goed.

## 6. Buiten scope (later)
Melodielijn (eigen ontwerp: uploaden van MIDI/MusicXML of transcriptie), drums, walking bass,
recht/shuffle per nummer kiezen, samples op meerdere sterktes.
