# BluesLab — oefenen per nummer: fragment + meespeel-begeleiding

**Datum:** 2026-10-15 · **Status:** gebouwd (2026-10-15) · **Bouwt op:** BL-2 (speelschema, iPad-weergave)

## 1. Doel

Bob oefent thuis op de iPad (staand) de nummers van de setlist voor de jam. Per nummer wil hij:
1. **horen hoe het nummer klinkt**: een kort fragment van de echte opname;
2. **meespelen**: een eenvoudige begeleiding uit de akkoorden, op tempo, met een cursor die
   over het maatraster loopt, zodat hij zijn doeltonen en akkoordtonen kan oefenen.

**Gezegd door Bob:** "een clipje laten horen van ieder nummer"; iPad in de sessies, staand.
**Aannames:** oefenen gebeurt thuis (niet live op de jam); de begeleiding hoeft niet mooi te
klinken, wel strak op tempo; geen extra hardware.

**Succes:** op de songpagina kan Bob met één tik het fragment horen, en met één tik vanaf
een gekozen maat meespelen, op een lager tempo als hij wil, en een deel laten herhalen.

## 2. Fragment (30 seconden, officieel)

- Bron: **iTunes Search API** (`itunes.apple.com/search`, `entity=song`, `country=NL`),
  vanuit de browser (CORS staat open, gecontroleerd 2026-10-15). Geen server-wijziging.
- Zoekterm: `titel + artiest`. Het eerste resultaat wordt gekozen; de knop toont
  "▶ Fragment — <track> · <artiest>" zodat Bob ziet of het de goede versie is.
- **"Ander fragment"** loopt door de volgende resultaten (max. 5); de keuze wordt per nummer
  bewaard in `localStorage` (alleen voor die iPad, in try/catch).
- Afspelen met een gewoon `<audio>`-element (preview-URL van Apple's CDN). Niets gevonden →
  "Geen fragment gevonden."
- Juridisch: het fragment komt van Apple's eigen servers, zoals in elke muziek-app; wij
  slaan geen audio op.

## 3. Meespeel-begeleiding

### Aanpak (gekozen: A)
- **A. Eigen mini-synth in Web Audio** (oscillatoren: bas + akkoord + tik). Geen
  afhankelijkheden, klein, werkt offline. Klinkt als een eenvoudige oefen-app. **Aanbevolen.**
- B. Tone.js + piano-samples: mooier geluid, maar MB's aan samples en een externe library.
- C. Op de server met fluidsynth naar MP3 renderen: zwaar, en de cursor loopt lastig synchroon.

A kan later naar B zonder dat de rest verandert: het geluid zit achter één functie.

### Wat je hoort (concert pitch — de band speelt concert)
- Per tel van een 4/4-maat: **bas** (grondtoon of slash-bas) op tel 1 en 3, **akkoord** kort
  op tel 2 en 4, zachte **tik** op elke tel. Twee akkoorden in een maat: elk een halve maat.
- `N.C.` en lege maten: alleen de tik. Onparseerbaar akkoord: alleen de tik.
- Eén **inteltmaat** (4 tikken) vóór de start.
- Andere maatsoorten dan 4/4: tellen volgens de teller (3/4 → 3 tellen); bas op 1, akkoord op
  de overige tellen.

### Bediening (in de vaste balk, onder de instrumentkeuze)
- **▶ Speel / ■ Stop**. Start vanaf de **aangetikte maat** (tik op een maatvak = startpunt,
  gemarkeerd), anders vanaf maat 1.
- **Tempo**: 50 %, 75 %, 100 % van het tempo uit de PDF (zonder tempo: 100 bpm).
- **🔁 Herhaal dit deel**: lust het deel van de startmaat tot het gestopt wordt.
- Tijdens het spelen: het **huidige maatvak licht op** en scrollt in beeld.
- Het scherm blijft al aan (Wake Lock).

### Opbouw
- `web/speler.js` (nieuw, vanilla JS, geen build):
  - `speelplan(maten, {bpm, tellen, start, eind, inteltel})` → **pure functie**: lijst
    gebeurtenissen `{t, soort: "bas"|"akkoord"|"tik", midi: [..], duur, maat}` in seconden.
    Gebruikt de concert-akkoorden uit het schema-antwoord (`akkoorden[].concert` →
    toonhoogtes via een kleine akkoord-naar-MIDI-functie in JS, gespiegeld aan
    `core/chords.py`: grondtoon, kwaliteit, septiem, slash-bas).
  - `Speler` → plant het speelplan in Web Audio (`AudioContext.currentTime` als klok,
    vooruit-plannen per ~100 ms) en roept `opMaat(nr)` aan voor de cursor.
- `web/app.js`: knoppen, startmaat kiezen, cursor tekenen.
- Server: **geen wijziging** (het schema-antwoord bevat al tempo, maatsoort en de
  concert-akkoorden per maat).

### iPad-valkuilen
- Web Audio start pas na een tik (iOS-regel): de ▶-knop maakt de `AudioContext` aan/hervat hem.
- Een iPhone met de stil-schakelaar aan speelt Web Audio niet af; de iPad heeft geen
  schakelaar. Melding in de hulptekst: "Hoor je niets? Zet het geluid aan."
- Vergrendelt het scherm of wisselt Bob van app: begeleiding stopt (geen achtergrondaudio).

## 4. Fouten
- iTunes onbereikbaar → "Fragment niet beschikbaar"; de rest werkt door.
- Geen Web Audio → speelknop verborgen.

## 5. Testen
- Node-tests (via `tests/web_eval.js`) voor `speelplan`: tijden op 100 bpm, inteltmaat,
  halve maten bij twee akkoorden, N.C. alleen tik, slash-bas, 3/4, tempo 50 %, start/eind.
- Node-test voor akkoord → MIDI tegen een paar gevallen uit `tests/test_chords.py`
  (Bbm7/F, Gsus4, N.C.).
- Node-test voor de fragmentkeuze (`kiesFragment(resultaten, index)`), zonder netwerk.
- Handmatig op de iPad: fragment speelt; begeleiding hoorbaar en strak; cursor loopt mee.

## 6. Buiten scope (later)
Mooier geluid (samples), drums/shuffle-patronen, live meeluisteren met de microfoon,
feedback na de repetitie (eigen ontwerp), fragment op de setlist-pagina.
