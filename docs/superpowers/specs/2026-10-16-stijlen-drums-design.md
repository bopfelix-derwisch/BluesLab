# BluesLab — stijlen per nummer met drums (shuffle, pop, ballad, funk)

**Datum:** 2026-10-16 · **Status:** gebouwd (2026-10-16) · **Bouwt op:** piano + shuffle (`2026-10-16-piano-shuffle-design.md`)

## 1. Doel

De setlist heeft naast blues ook **pop/rock (vlot)**, **ballads** en **soul/funk**. De
piano-shuffle past daar niet bij. Gekozen in de chat:
- een **stijl per nummer**: Shuffle · Pop · Ballad · Funk, te kiezen in de speelbalk;
- **drums** erbij (bassdrum, snare, hi-hat, echte samples), meteen;
- de keuze **per nummer op de server** bewaard (iPhone en iPad zien hetzelfde); nieuwe
  nummers beginnen op Shuffle;
- **met drums verdwijnt de tik** tijdens het spelen; het aftellen blijft (vier tikken op de hi-hat);
- elke stijl is een **kleine tabel** (patroon in zestienden), niet een eigen stuk code.

**Succes:** Bob kiest per nummer een stijl, en ▶ Speel klinkt als een eenvoudige band in die
stijl (piano + drums), strak op tempo, met dezelfde bediening (startmaat, tempo, herhalen,
Stop). Laden de drums niet, dan speelt de piano met de tik; laadt de piano niet, dan de synth.

## 2. Drumsamples

- Bron: **Google Chrome Labs `web-audio-samples`** (Apache-2.0),
  `src/sounds/drum-samples/acoustic-kit/{kick,snare,hihat}.wav`
  (raw via `https://raw.githubusercontent.com/GoogleChromeLabs/web-audio-samples/main/…`).
- Met ffmpeg naar `web/drums/{kick,snare,hihat}.mp3`: mono, stilte vooraf eraf, maximaal 1 s,
  fade-out, ~96 kbps (samen rond 30 KB). Script `scripts/drum-samples.sh`, net als
  `scripts/piano-samples.sh`; het zet ook de Apache-2.0-licentietekst in
  `web/drums/LICENSE-Apache-2.0.txt`.
- Naamsvermelding: hulptekst ("Drums: Google Chrome Labs web-audio-samples, Apache-2.0") en
  README.

## 3. Stijlen als tabel (`web/speler.js`)

### Gebeurtenissen
Ongewijzigde vorm `{t, soort, midi, duur, maat}`, met één optioneel veld **`sterkte`**
(vermenigvuldiger, standaard 1). Nieuwe soorten: `"kick"`, `"snare"`, `"hihat"` (`midi: []`).
`"bas"` = linkerhand, `"akkoord"` = rechterhand, `"tik"` blijft.

### Tabel per stijl
```js
STIJLEN = {
  shuffle: { swing: true, links: [...], rechts: [...], kick: [...], snare: [...], hihat: [...] },
  pop: {...}, ballad: {...}, funk: {...},
}
```
- Een regel is `[positie, rol, duur, sterkte]` voor piano en `[positie, sterkte]` voor drums.
  **Positie** in zestienden binnen een 4/4-maat (0–15); **duur** in tellen.
- **Swing** (shuffle): alleen even posities; positie `4b + 2` klinkt op `b + 2/3` tel.
- Het **akkoord op een positie** is dat van de tel `floor(positie / 4)` (zoals nu: elk akkoord in
  een maat krijgt een gelijk deel van de tellen). `p` = tellen sinds dat akkoord begon.
- **Rollen linkerhand** (`soort: "bas"`): `R` grondtoon, `5` kwint, `8` octaaf (grondtoon + 12),
  `S` shuffle-tweeklank (grondtoon + kwint/sext/septiem/sext naar `p % 4`, zoals nu; geen reine
  kwint → steeds grondtoon + eigen kwint). Grondtoon = `36 + pc`. Bij een **slash-akkoord** is de
  grondtoon de slash-noot en speelt `S` alleen die noot.
- **Rollen rechterhand** (`soort: "akkoord"`): `A` het hele akkoord (ligging van nu);
  `B0`…`B3` één toon uit `[akkoord…, akkoord[0] + 12]` (gebroken akkoord; bij een vierklank is
  `B3` de vierde toon).
- **Volgorde**: per positie eerst de tik (alleen tijdens het aftellen of zonder drums), dan
  linkerhand, rechterhand, kick, snare, hi-hat; de lijst blijft op `t` gesorteerd.

### De vier patronen
| Stijl | Linkerhand | Rechterhand | Kick | Snare | Hi-hat |
|---|---|---|---|---|---|
| **shuffle** (swing) | `S` op elke achtste, lang 0,6 / kort 0,3 tel | `A` op 4 en 12, 0,25 tel | 0, 8 | 4, 12 | elke achtste (zwingend) |
| **pop** | `R` op 0 (1,4 tel), 6 (0,45), 8 (1,8) | `A` op elke achtste, 0,4 tel, sterkte 0,6 | 0, 8 | 4, 12 | elke achtste |
| **ballad** | `R` op 0 en 8, 1,9 tel | `B0 B1 B2 B3` herhaald op de achtsten, 0,9 tel, sterkte 0,5 | 0 (0,6) | 8 (0,6) | 0, 4, 8, 12 (0,5) |
| **funk** | `R` 0 (0,45), `R` 3 (0,2), `8` 6 (0,2), `R` 8 (0,45), `5` 11 (0,2), `8` 14 (0,2) | `A` op 5, 7, 13, 15, 0,15 tel, sterkte 0,7 | 0, 6 | 4, 12 | elke zestiende (0,4; op de achtsten 0,7) |

De shuffle uit de vorige stap wordt zo een tabel; zonder drums geeft hij **exact dezelfde
gebeurtenissen** als nu (de bestaande shuffle-tests blijven ongewijzigd groen).

### `speelplan`
`speelplan(maten, {bpm, tellen = 4, start, eind, inteltel = tellen, stijl = "recht", drums = false})`
- `stijl` ∈ `recht | shuffle | pop | ballad | funk`. De vier tabelstijlen gelden **alleen bij 4
  tellen**; anders het rechte patroon van nu (bas/akkoord + tik).
- `drums: false` → tik op elke tel (zoals nu), geen drumgebeurtenissen.
- `drums: true` → **geen tik tijdens het spelen**, wel de drumregels; het aftellen blijft
  `tik`-gebeurtenissen met `maat: null`.
- **N.C., lege of onleesbare maat**: geen piano; met drums alleen de hi-hat op de tellen, zonder
  drums de tik (zoals nu).

### Geluid
- `laadSamples(ctx, paden, haal = fetch)` → `{sleutel: AudioBuffer}`; `laadPiano` wordt
  `laadSamples` met de 15 pianonoten. Drums: `{kick, snare, hihat}` uit `drums/<naam>.mp3`.
- `maakGeluid({piano, drums})` (elk een buffer-object of `null`) → geluidsfunctie:
  - `bas`/`akkoord`: piano-samples, of de synth als `piano` ontbreekt; volume × `sterkte`;
  - `kick`/`snare`/`hihat`: drumsample, volume `DRUMSTERKTE[soort] × sterkte`;
  - `tik` met `maat: null` en drums geladen → hi-hat; anders de synth-tik zoals nu.

## 4. Opslag per nummer (server)

- Kolom `song.stijl TEXT NOT NULL DEFAULT 'shuffle'`. Bestaande database: `verbind()` voegt de
  kolom toe als hij ontbreekt (`PRAGMA table_info` → `ALTER TABLE song ADD COLUMN …`).
- `GET /api/songs/{id}/schema` geeft `"stijl"` mee.
- Nieuw: `PUT /api/songs/{id}/stijl` met `{"stijl": "shuffle"|"pop"|"ballad"|"funk"}` → `{"ok": true}`;
  onbekende stijl → 422; onbekend nummer → 404. Achter de login zoals de rest van `/api/`.
- Het controleren van een nummer (`PUT /api/songs/{id}`) laat de stijl ongemoeid.
- Na de wijziging moet **Bob de dienst één keer herstarten** (`sudo systemctl restart blueslab.service`).

## 5. Bediening (`web/app.js`)

- In de speelbalk een rij knoppen **Shuffle · Pop · Ballad · Funk** (zoals de tempoknoppen,
  `aria-pressed`). Alleen bij 4 tellen; anders verborgen.
- Tik → stijl direct gebruiken (speelt hij, dan opnieuw starten via `wijzig`) en
  `PUT …/stijl` op de achtergrond. Mislukt het bewaren → hulpregel "Stijl niet bewaard." (de
  keuze blijft voor deze pagina gelden).
- Zonder `stijl` in het schema-antwoord (oude server) → Shuffle.
- Laden bij de eerste ▶: piano en drums **tegelijk en onafhankelijk**, elk met de 10 s-limiet;
  de knop toont "Laden…". Melding bij een mislukking: "Piano niet geladen — eenvoudige klank."
  en/of "Drums niet geladen — met tik.". Daarna geen nieuwe laadpoging op deze pagina.
- `speel()` geeft `stijl` en `drums: <drums geladen>` aan `speelplan`.

## 6. Fouten
- Drums laden mislukt → piano + tik (zoals nu). Piano mislukt → synth (+ drums als die er zijn).
- Opslaan stijl mislukt → melding, spelen werkt.
- Andere maatsoort dan 4/4 → geen stijlknoppen, rechte patroon, met tik.

## 7. Testen
- `speelplan` per stijl (100 bpm, `inteltel: 0`): posities en tijden van linkerhand, rechterhand en
  drums in één maat; pop met twee akkoorden (de bas op positie 8 is het tweede akkoord); ballad
  `B0`–`B3` voor een drie- en een vierklank; funk-rollen `8` en `5`; slash-akkoord; N.C. met en
  zonder drums; `drums: true` → geen tik tijdens het spelen, wel het aftellen; 3/4 → recht;
  gesorteerd op `t` voor elke stijl.
- Bestaande shuffle-tests ongewijzigd groen (`drums: false`).
- `maakGeluid`: drums → juiste buffer en sterkte; inteltik → hi-hat als er drums zijn; zonder
  piano → synth.
- Server: migratie op een oude database (kolom ontbreekt → wordt toegevoegd, standaard
  `shuffle`); `PUT …/stijl` (ok, 422, 404, zonder login 401); schema bevat `stijl`; controleren
  laat de stijl staan.
- Harness: stijlknoppen zichtbaar bij 4/4 en niet bij 3/4; tik op Pop → `PUT …/stijl` met
  `pop`; drums mislukt → melding en `speelplan` zonder drums; beide geladen → 18 fetches.
- Handmatig op de iPad: klinkt elke stijl als die stijl, balans piano/drums.

## 8. Buiten scope (later)
Fills en variatie per deel (refrein drukker), 12/8 en 3/4-stijlen, latin/bossa, stijl raden bij
het importeren, melodielijn, eigen stijlen samenstellen.
