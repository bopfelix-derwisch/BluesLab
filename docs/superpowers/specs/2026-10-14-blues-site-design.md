# BluesLab-site — ontwerp (blues.felixisfelix.com)

**Datum:** 2026-10-14 · **Versie:** 2 (PDF-first; screenshot-invoer vervallen) · **Status:** ter review
**Stories:** BL-2 (site + PDF → speelschema per maat), BL-3 (solovoorbeeld op notenbalk),
BL-4 (oefeningen + coaching). De oude roadmap (play-along, mic, akkoord-mapping, sessielog) schuift op naar BL-5+.

## 1. Doel

Bob speelt in een jamband. Per nummer downloadt hij uit Chordify een **PDF met het volledige
akkoordenschema** (concert pitch, pianovoicing). Hij wil op **blues.felixisfelix.com** die PDF
uploaden en een **speelinstructie voor zijn blaasinstrument** terugkrijgen, in de **geschreven
notatie**: **Bes klarinet (Bb, +2)** (primair) of **alt sax (Eb, +9)**.

**Succes:** vóór de jam van volgende week heeft Bob voor elk nummer van de setlist een
correct getransponeerd speelschema per maat dat op een telefoon leesbaar is, en waar van
toepassing een uitgeschreven solovoorbeeld.

### Gezegd door Bob
- De PDF is de basis; het screenshot vervalt.
- De PDF is voor piano: "vertalen" naar sax/klarinet.
- (a) keuze sax of klarinet; (b) speelinstructie per maat, welke tonen in welke maat, volledig
  schema; (c) uitgeschreven solovoorbeeld waar dat van toepassing is, met oog voor
  toonsoortwisselingen binnen een nummer (voorbeeld *Californication*).
- Claude API voor het lezen en schrijven; hosting op orin3 + cloudflared; eigen wachtwoord.
- Gewenste onderdelen: speelschema, oefeningen, coaching-tekst, notenbalk.

### Aannames
- Persoonlijk gebruik (één gebruiker), mobiel als primair scherm.
- Nummers zijn niet allemaal blues; de instructie is generiek per deel en toonsoort.

## 2. Het Chordify-PDF-formaat (vastgesteld op `tests/fixtures/chordify-crazy.pdf`)

- Gegenereerd door **LilyPond**; één pagina, één notenbalk (vioolsleutel) met akkoorden in
  blokvorm (piano-voicing, geen melodie).
- Boven elke maat de **akkoordnamen** (soms 2 per maat); een **tempo** (`♩ = 103`),
  maatsoort (`C` = 4/4), **voortekening** (hier 5 mollen = D♭ / B♭m).
- **Maatnummer** aan het begin van elke regel (1, 10, 20, 29, 39, 49, 58, 67).
- Speciale symbolen: `sus4` als superscript, `N.C.` (geen akkoord), 3-noots en 4-noots akkoorden.
- **Geen** tekst, **geen** deelnamen (couplet/refrein/solo), **geen** herhalingstekens.
- `pdftotext` is onbruikbaar: ♭/♯-glyphs vallen weg ("B m") en maatstrepen zijn niet zichtbaar.
  → Claude leest de PDF **visueel** (document-input).

Het Chordify-formaat "akkoorden boven lyrics" kan afwijken; dat ondersteunen we pas als Bob
er een voorbeeld van aanlevert.

## 3. Aanpak: hybride

Claude **leest** (PDF), **structureert** (deelindeling, toonsoort per deel), **schrijft**
(solo als notenlijst, coaching, oefentekst). De deterministische engine in `core/` **rekent
en controleert**: akkoorden parsen, maattelling verifiëren, toonsoort per deel controleren,
transponeren, tonen per maat, solonoten valideren, ABC-notatie.

Regel: **alles wat op het scherm als noot staat, gaat door de engine.** Claude levert noten
alleen in concert pitch aan; de engine transponeert en markeert noten die niet bij het
akkoord of de toonladder van die maat passen.

## 4. Architectuur

```text
browser (mobiel) ──HTTPS──> Cloudflare tunnel (dashboard-managed)
                            blues.felixisfelix.com → http://localhost:8793
                                     │
                         FastAPI  app/  (blueslab.service, poort 8793)
                         ├─ auth (wachtwoord → sessiecookie)
                         ├─ api: setlists, songs, pdf-upload, content
                         ├─ app/claude.py  (Anthropic SDK, structured output)
                         └─ core/  (stdlib: theory.py, chords.py, analysis.py, abc.py)
                                     │
                         data/  (niet in git): blueslab.sqlite, uploads/
```

### Mappen
```text
core/theory.py    # BL-1, blijft stdlib-only; --selftest blijft groen
core/chords.py    # parse_chord, transpose_chord, chord_tones (geschreven)
core/analysis.py  # maattelling-check, deeldetectie (herhaling), toonsoort per deel, tonen per maat
core/abc.py       # ABC-export: toonladders, solo, akkoordtonen
app/main.py       # FastAPI, routes, statische web/
app/auth.py       # wachtwoordlogin, sessie, rate-limit
app/db.py         # SQLite (stdlib sqlite3)
app/claude.py     # 3 aanroepen (§6)
web/              # index.html, setlist.html, song.html, app.js, style.css, abcjs (vendored)
tests/            # pytest; fixtures/chordify-crazy.pdf
deploy/blueslab.service, .env.example, requirements.txt
```

`core/` blijft stdlib-only. `app/` gebruikt `fastapi`, `uvicorn`, `python-multipart`,
`anthropic` in `.venv/`.

## 5. Datamodel (SQLite)

| Tabel | Velden |
|-------|--------|
| `setlist` | id, naam (bijv. "Next week"), created_at |
| `song` | id, setlist_id, positie, titel, artiest, pdf_path, tempo, maatsoort, voortekening, status (`gelezen`/`gecontroleerd`) |
| `bar` | song_id, nr (1-based), akkoorden (JSON, concert, 1..n per maat, met tel-positie), flag (onparseerbaar/telling) |
| `section` | song_id, naam (Intro/Couplet/Refrein/Brug/Solo/Outro), start_bar, end_bar, concert_key, key_source (`claude`/`engine`/`handmatig`), solo_geschikt (bool) |
| `content` | song_id, instrument (`bb`/`eb`), soort (`solo`/`oefeningen`/`coaching`), data (JSON/markdown), model, input_hash, created_at |

`content` is cache: alleen opnieuw genereren bij "opnieuw" of als `input_hash`
(maten + delen + instrument) verandert.

## 6. Claude-aanroepen

Model: `claude-sonnet-5-5`. Key uit `.env` (`ANTHROPIC_API_KEY`); voorlopig de waarde van
`DERWISCH_ANTHROPIC_API_KEY` uit labs-secrets, later eventueel een eigen `BLUESLAB_ANTHROPIC_API_KEY`.

1. **PDF → maten** (BL-2). Invoer: PDF als document. Uitvoer (JSON-schema):
   `{titel, artiest, tempo, maatsoort, voortekening, regels: [{start_maat, maten: [[akkoord,…]]}]}`.
   Titel opgeschoond ("(Official Music Video)" eraf).
2. **Structuur** (BL-2). Invoer: titel/artiest + de gecontroleerde maatlijst (concert).
   Uitvoer: `{delen: [{naam, start_maat, eind_maat, toonsoort, solo_geschikt, reden}]}`.
   Claude mag zijn kennis van het nummer gebruiken (bijv. waar de gitaarsolo zit), maar
   de engine controleert dat de delen aansluiten en elke maat dekken.
3. **Solo + coaching + oefeningen** (BL-3/BL-4). Invoer: per deel de door de engine
   berekende geschreven akkoorden, toonladder en doeltonen, plus het instrument.
   - Solo: notenlijst **in concert pitch** per maat: `[{maat, noten: [{toon: "A4", duur: "8"}]}]`.
     De engine valideert, transponeert en rendert.
   - Coaching/oefeningen: markdown in het Nederlands; verwijst alleen naar noten uit de invoer.

Elke akkoord-string uit Claude gaat door `parse_chord`; wat niet parset wordt gemarkeerd, niet weggegooid.

## 7. Engine (`core/`)

- **`chords.py`**
  - `parse_chord("B♭m7/F")` → `{root_pc, kwaliteit, extensies, bas_pc}`; accepteert
    `♭ ♯ b #`, `m min - maj7 M7 7 sus2 sus4 dim ° aug + 6 9 add9`, slash-bas, `N.C.`.
  - `transpose_chord(chord, voice)` → geschreven akkoordnaam (spelling volgens de
    geschreven toonsoort; hergebruikt `spell_note`/`FLAT_KEYS` uit `theory.py`).
  - `chord_tones(chord, voice)` → grondtoon, terts, kwint, (septiem), geschreven.
- **`analysis.py`**
  - `check_bar_count(regels)` → per regel: verwacht = volgende `start_maat` − deze; afwijking = flag.
  - `detect_sections(maten)` → kandidaat-delen op basis van herhaalde akkoordpatronen
    (2/4/8 maten). Dient als controle en fallback voor Claude-aanroep 2.
  - `key_for_section(maten, voortekening)` → toonsoort per deel op diatonische fit, met
    de voortekening als prior. Wijkt die af van Claude, dan wordt het deel gemarkeerd.
    Zo komen **toonsoortwisselingen binnen een nummer** (Californication) aan het licht.
  - `bar_guide(bar, section_key, voice)` → per maat: geschreven akkoord, akkoordtonen,
    **doeltoon** (terts/septiem, met stemvoering naar de volgende maat) en de toonladder van het deel.
  - `validate_solo(solo, maten, delen)` → per noot: akkoordtoon / toonladdertoon / vreemd (gemarkeerd).
- **`abc.py`**: toonladder / akkoordtonen / solo → ABC met geschreven `K:` en `Q:` (tempo);
  register rond c'–c'' (comfortabel voor klarinet en alt sax).

Enharmonische spelling blijft MVP-pragmatisch (BL-1 §5).

## 8. Schermen (web/)

1. **Login**: één wachtwoordveld.
2. **Setlists**: lijst; nieuwe setlist = naam.
3. **Setlist**: nummers op volgorde (slepen), knop "PDF toevoegen" (meerdere tegelijk mogelijk);
   per nummer geschreven grondtoonsoort voor het gekozen instrument.
4. **Controle** na het lezen van de PDF: maten in een raster per regel (concert), gemarkeerde
   regels/akkoorden in het rood, alles bewerkbaar; daaronder de voorgestelde delen met toonsoort
   (bewerkbaar). Pas na "Opslaan" krijgt het nummer de status `gecontroleerd`.
5. **Nummer**: wisselknop **Bes klarinet / Alt sax** bovenaan (keuze in localStorage, standaard Bes), dan:
   - **Kop**: titel, tempo, concert- en geschreven toonsoort.
   - **Speelschema per maat** (BL-2): per deel een kopregel (naam, maten, toonsoort geschreven,
     toonladder), daaronder een raster: maatnr · geschreven akkoord · akkoordtonen · doeltoon.
     Toonsoortwissels krijgen een opvallende markering.
   - **Solovoorbeeld** (BL-3): per deel met `solo_geschikt` een notenbalk (abcjs), afwijkende
     noten gemarkeerd; knop "nieuwe solo".
   - **Oefeningen** + **Coaching** (BL-4): Claude-tekst met knop "opnieuw".

Mobile-first, groot lettertype in het speelschema, licht/donker volgens het systeem.

## 9. Beveiliging

- Wachtwoord als `hashlib.scrypt`-hash in `.env`; sessie = ondertekende cookie
  (`HttpOnly`, `Secure`, `SameSite=Lax`, 30 dagen).
- Login rate-limit: maximaal 5 pogingen per minuut per IP (`CF-Connecting-IP`).
- Claude-endpoints: maximaal 30 aanroepen per uur, in memory (budgetbescherming).
- Uploads: alleen PDF (magic bytes `%PDF`), maximaal 10 MB, opgeslagen onder een uuid-naam.
- `.env` en `data/` in `.gitignore`; geen key in logs.

## 10. Fouten

- Claude-fout of time-out: NL-melding + "opnieuw"; geen half-opgeslagen nummer.
- Maattelling klopt niet: regel gemarkeerd op het controlescherm; opslaan kan wel (Bob beslist).
- Onparseerbaar akkoord: ⚠ in het schema; de rest blijft werken.
- Toonsoort Claude ≠ engine: deel gemarkeerd, Bob kiest.

## 11. Testen

- `pytest` voor `core/`:
  - `parse_chord`/`transpose_chord`: ♭/♯, slash, sus4, N.C.; concert B♭m → klarinet Cm,
    alt sax Gm; concert Gm → klarinet Am, alt sax Em.
  - `check_bar_count` op de regelstarts van de fixture (1, 10, 20, 29, 39, 49, 58, 67).
  - `key_for_section`: Crazy → B♭m (heel nummer); een Californication-achtige reeks
    (couplet Am–F, refrein C–G–D–Am–F) → twee delen met verschillende toonsoort.
  - `validate_solo` en ABC-export (geschreven `K:` klopt per instrument).
- API-tests met `TestClient` en een gemockte `app/claude.py`.
- Smoketest tegen de echte API met `tests/fixtures/chordify-crazy.pdf`: titel "Crazy",
  tempo 103, voortekening 5 mollen, eerste akkoord B♭m, regelstarts 1/10/20/29/39/49/58/67
  zonder telfout. De resulterende maatlijst wordt na handmatige controle als
  golden-fixture vastgelegd.
- `python3 core/theory.py --selftest` blijft groen.
- Live-check: `curl` via `https://blues.felixisfelix.com` na de tunnelconfiguratie.

## 12. Deploy

- `deploy/blueslab.service` (user `bob`, `WorkingDirectory=/home/bob/BluesLab`,
  `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8793`).
- cloudflared: **Public Hostname** `blues.felixisfelix.com` → `http://localhost:8793` toevoegen in
  het Zero Trust-dashboard (handmatige stap voor Bob; de tunnel is dashboard-managed).
- DNS: felixisfelix.com staat al bij Cloudflare (NS garret/bingo.ns.cloudflare.com, gecontroleerd
  2026-10-14); Cloudflare maakt de CNAME zelf aan bij het toevoegen van de Public Hostname.
- orin3-window `blueslab`, `ORIN3_SYSTEEM.md` en de inventaris bijwerken met poort 8793.

## 13. Opleveringen

| Story | Inhoud | Bruikbaar als |
|-------|--------|---------------|
| BL-2 | backend, login, setlists, PDF → maten → controle, delen + toonsoort per deel, speelschema per maat (Bb/Eb), deploy | spiekbriefje voor de jam |
| BL-3 | solovoorbeeld per geschikt deel, gevalideerd en op de notenbalk (abcjs) | soleren oefenen |
| BL-4 | oefeningen + coaching (Claude) | thuis oefenen |

## 14. Buiten scope

Screenshot-invoer, het Chordify-formaat "akkoorden boven lyrics" (tot er een voorbeeld is),
audio/play-along, microfoon/transcriptie, meerdere gebruikers, delen met bandleden,
Chordify-API/scraping.
