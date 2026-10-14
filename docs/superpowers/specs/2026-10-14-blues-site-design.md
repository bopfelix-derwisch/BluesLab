# BluesLab-site — ontwerp (blues.felixisfelix.com)

**Datum:** 2026-10-14 · **Status:** ontwerp goedgekeurd in chat, spec ter review
**Stories:** BL-2 (site + setlist + spiekbriefje), BL-3 (Chordify-PDF), BL-4 (oefeningen, coaching, notenbalk).
De oude roadmap (play-along, mic, akkoord-mapping, sessielog) schuift één plek op (BL-5+).

## 1. Doel

Bob speelt in een jamband en krijgt de setlist uit een akkoorden-app (Chordify) als lijst
nummers met de eerste ~4 akkoorden. Hij wil op **blues.felixisfelix.com** een screenshot
van die setlist uploaden en per nummer instructie voor **live spelen** en **oefeningen**
krijgen, in de **geschreven notatie** van zijn instrument: **Bes klarinet (Bb, +2)**
(primair) of **alt sax (Eb, +9)**.

**Succes:** vóór de jam van volgende week staat de setlist "Next week" (7 nummers) op de
site en heeft elk nummer een correct getransponeerd spiekbriefje dat op een telefoon leesbaar is.

### Gezegd door Bob
- Screenshot van de setlist als invoer; alt sax en Bes klarinet.
- Claude API leest het screenshot.
- Per nummer optioneel de **volledige Chordify-PDF** (akkoorden in concert pitch, niet getransponeerd) uploaden.
- Hosting op orin3 via cloudflared; afscherming met een **eigen wachtwoord**.
- Per nummer: spiekbriefje live, oefeningen, coaching-tekst (Claude), notenbalk.

### Aannames
- Het screenshot toont slechts ~4 akkoorden per nummer; de toonsoort wordt afgeleid en is door Bob te corrigeren.
- Niet elk nummer is een blues (bijv. *Californication*, *Crazy*); instructie is generiek per toonsoort/progressie, niet alleen 12-maats.
- Persoonlijk gebruik (één gebruiker), mobiel als primair scherm.

## 2. Aanpak: hybride

Claude **leest** (screenshot, PDF) en **schrijft** (coaching, oefentekst). De deterministische
engine in `core/` **rekent**: akkoorden parsen, transponeren, toonladders, akkoordtonen, ABC-notatie.
Claude krijgt de getransponeerde noten als invoer en mag geen eigen noten introduceren;
alle noten op het scherm komen uit de engine.

Afgewezen: alles via Claude (transpositiefouten), geen generatieve AI (geen coaching per stijl).

## 3. Architectuur

```text
browser (mobiel) ──HTTPS──> Cloudflare tunnel (dashboard-managed)
                            blues.felixisfelix.com → http://localhost:8793
                                     │
                         FastAPI  app/  (blueslab.service, poort 8793)
                         ├─ auth (wachtwoord → sessiecookie)
                         ├─ api: setlists, songs, uploads, content
                         ├─ app/claude.py  (Anthropic SDK, structured output)
                         └─ core/  (stdlib: theory.py, chords.py, abc.py)
                                     │
                         data/  (niet in git): blueslab.sqlite, uploads/
```

### Mappen
```text
core/theory.py   # BL-1, blijft stdlib-only; --selftest blijft groen
core/chords.py   # NIEUW: parse_chord, transpose_chord, guess_key, scale_for_key
core/abc.py      # NIEUW: ABC-export van toonladders/akkoordtonen/licks
app/main.py      # FastAPI-app, routes, statische web/
app/auth.py      # wachtwoordlogin, sessie, rate-limit
app/db.py        # SQLite (stdlib sqlite3), schema + queries
app/claude.py    # 3 aanroepen (zie §5)
web/             # index.html, setlist.html, song.html, app.js, style.css, abcjs (vendored)
tests/           # pytest
deploy/blueslab.service, .env.example
```

`core/` blijft vrij van externe dependencies. `app/` gebruikt `fastapi`, `uvicorn`,
`python-multipart`, `anthropic` in een venv (`.venv/`, `requirements.txt`).

## 4. Datamodel (SQLite)

| Tabel | Velden |
|-------|--------|
| `setlist` | id, naam, created_at |
| `screenshot` | id, setlist_id, pad |
| `song` | id, setlist_id, positie, titel, artiest, chords_preview (JSON-lijst, concert), concert_key (bijv. `Gm`, `Bb`), key_source (`gok`/`pdf`/`handmatig`), progression (JSON, maten × akkoorden, concert; leeg tot PDF), pdf_path |
| `content` | id, song_id, instrument (`bb`/`eb`), soort (`coaching`/`oefeningen`), tekst (markdown), model, input_hash, created_at |

`content` is een cache: alleen opnieuw genereren als Bob op "opnieuw" drukt of als de
`input_hash` (toonsoort + progressie + instrument) verandert.

Toonsoort wordt opgeslagen als grondtoon + mineur/majeur. De bestaande `parse_key` in
`theory.py` dekt alleen grondtonen; `chords.py` voegt de mode toe.

## 5. Claude-aanroepen

Model: `claude-sonnet-5-5`. Key uit `.env` (`ANTHROPIC_API_KEY`), voorlopig
`DERWISCH_ANTHROPIC_API_KEY` uit labs-secrets; Bob kan later een eigen `BLUESLAB_ANTHROPIC_API_KEY` aanmaken.

1. **Screenshot → setlist** (BL-2). Invoer: 1..n afbeeldingen. Uitvoer (JSON-schema):
   `{nummers: [{titel, artiest, akkoorden: [str], toonsoort_gok: str}]}`.
   Overlap tussen screenshots (zelfde nummer op beide schermen) wordt ontdubbeld op titel+artiest.
   Titels worden opgeschoond ("(Official Music Video)", "[HD UPGRADE]" eraf).
2. **PDF → progressie** (BL-3). Invoer: Chordify-PDF als document. Uitvoer:
   `{toonsoort: str, maten: [[str]], secties: [{naam, start_maat}]?}`.
3. **Coaching / oefeningen** (BL-4). Invoer: titel, artiest, instrument, en de **door de
   engine berekende** geschreven toonsoort, akkoorden, toonladders en akkoordtonen. Uitvoer: markdown
   in het Nederlands. Prompt verbiedt het noemen van noten die niet in de invoer staan.

Akkoord-strings uit Claude gaan altijd door `parse_chord`; wat niet parset wordt
gemarkeerd, niet weggegooid.

## 6. Engine-uitbreiding (`core/chords.py`, `core/abc.py`)

- `parse_chord("B♭m7/F")` → `{root_pc, kwaliteit, extensies, bas_pc}`; accepteert `♭ ♯ b #`,
  `m min - maj7 M7 7 sus2 sus4 dim ° aug + 6 9 add9`, slash-bas. Onbekend → `ValueError`.
- `transpose_chord(chord, voice)` → geschreven akkoordnaam, spelling volgens de
  geschreven toonsoort (hergebruik `spell_note` / `FLAT_KEYS` uit `theory.py`).
- `guess_key(chords)` → meest waarschijnlijke toonsoort (eerste akkoord + diatonische fit-score).
- `scale_for_key(key)` → majeur/natuurlijk mineur, pentatonisch, blues; per voice gespeld.
- `chord_tones(chord, voice)` → grondtoon, terts, kwint, (septiem), geschreven.
- `abc.py`: toonladder / akkoordtonen / korte lick → ABC-string met geschreven sleutel
  (`K:`); octaaf binnen een comfortabel register (klarinet en sax: rond c'–c'').

Enharmonische spelling blijft MVP-pragmatisch (BL-1 §5).

## 7. Schermen (web/)

1. **Login**: één wachtwoordveld.
2. **Setlists**: lijst + "Nieuwe setlist" (naam + 1..n screenshots uploaden).
3. **Controle** na het uitlezen: tabel met titel, artiest, akkoorden, toonsoort; alles te bewerken,
   rijen te verwijderen en te verplaatsen; pas na "Opslaan" in de database.
4. **Setlist**: nummers op volgorde met geschreven toonsoort voor het gekozen instrument.
5. **Nummer**: wisselknop **Bes klarinet / Alt sax** (keuze onthouden in localStorage, standaard Bes), dan:
   - **Spiekbriefje live** (BL-2): concert- en geschreven toonsoort, akkoorden geschreven,
     "speel hierover"-toonladder, veilige noten (akkoordtonen van I/IV/V of i/iv/v).
   - **Volledige progressie** (BL-3): PDF uploaden, dan alle maten geschreven in een raster.
   - **Oefeningen** + **Coaching** (BL-4): Claude-tekst met knop "opnieuw".
   - **Notenbalk** (BL-4): abcjs rendert ABC van toonladder, akkoordtonen en licks.

Mobile-first, grote letters op het spiekbriefje, licht/donker volgens het systeem.

## 8. Beveiliging

- Wachtwoord als hash (`hashlib.scrypt`) in `.env`; sessie = ondertekende cookie
  (`HttpOnly`, `Secure`, `SameSite=Lax`, 30 dagen).
- Login rate-limit: maximaal 5 pogingen per minuut per IP (`CF-Connecting-IP`).
- Claude-endpoints: maximaal 30 aanroepen per uur (budgetbescherming), in memory.
- Uploads: alleen png/jpg/heic/webp (screenshots) en pdf; maximaal 10 MB; opgeslagen onder een uuid-naam.
- `.env` en `data/` in `.gitignore`. Geen key in logs.

## 9. Fouten

- Claude-fout of time-out: duidelijke NL-melding + "opnieuw"; geen half-opgeslagen setlist.
- Onparseerbaar akkoord: gemarkeerd (⚠) in het spiekbriefje, de rest blijft werken.
- Onzekere toonsoort: label "gok", bewerkbaar.

## 10. Testen

- `pytest` voor `core/chords.py` en `core/abc.py`: parsen (♭/♯, slash, sus, dim), transpositie
  Bb/Eb tegen bekende voorbeelden (concert Gm → klarinet Am, alt sax Em; concert B♭m → klarinet Cm, alt sax Gm), `guess_key`
  op de 7 nummers uit het voorbeeld.
- API-tests met `TestClient` en een gemockte `app/claude.py`.
- Eén handmatige smoketest tegen de echte API met Bobs twee screenshots (fixture in `tests/fixtures/`).
- `python3 core/theory.py --selftest` blijft groen.
- Live-check: `curl` via `https://blues.felixisfelix.com` na de tunnelconfiguratie.

## 11. Deploy

- `deploy/blueslab.service` (user `bob`, `WorkingDirectory=/home/bob/BluesLab`,
  `uvicorn app.main:app --host 127.0.0.1 --port 8793`).
- cloudflared: **Public Hostname** `blues.felixisfelix.com` → `http://localhost:8793` toevoegen in
  het Zero Trust-dashboard (handmatige stap voor Bob; de tunnel is dashboard-managed).
- DNS: felixisfelix.com staat al bij Cloudflare (NS garret/bingo.ns.cloudflare.com, gecontroleerd
  2026-10-14). Bij het toevoegen van de Public Hostname maakt Cloudflare de CNAME zelf aan.
- orin3-window `blueslab` en `ORIN3_SYSTEEM.md` / inventaris bijwerken met poort 8793.

## 12. Opleveringen

| Story | Inhoud | Bruikbaar als |
|-------|--------|---------------|
| BL-2 | backend, login, screenshot → setlist, controlescherm, spiekbriefje, deploy | voorbereiding jam met de 4 preview-akkoorden |
| BL-3 | PDF-upload → volledige progressie, geschreven raster, toonsoort uit PDF | volledige akkoordenkaart per nummer |
| BL-4 | oefeningen, coaching (Claude), notenbalk (abcjs) | oefenen thuis |

## 13. Buiten scope

Audio/play-along, microfoon/transcriptie, meerdere gebruikers, delen met bandleden,
Chordify-API/scraping (alleen screenshot + PDF als invoer).
