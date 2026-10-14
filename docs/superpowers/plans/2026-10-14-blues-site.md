# BL-2 — BluesLab-site: PDF → speelschema per maat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bob uploadt op blues.felixisfelix.com een Chordify-PDF en krijgt, na een controlescherm, per maat een correct getransponeerd speelschema voor Bes klarinet of alt sax op zijn telefoon.

**Architecture:** Een stdlib-engine in `core/` (akkoorden parsen/transponeren, maattelling, delen, toonsoort per deel, speelschema) doet al het rekenwerk. `app/` is een FastAPI-app die de engine, SQLite en twee Claude-aanroepen aan elkaar knoopt (PDF → maten, maten → delen). `web/` is vanilla HTML/JS zonder build-stap. Hij draait op orin3 als systemd-dienst achter de bestaande cloudflared-tunnel.

**Tech Stack:** Python 3.10 · stdlib (`core/`, `sqlite3`, `hashlib.scrypt`, `hmac`) · FastAPI 0.143 / Starlette 1.7 / uvicorn · python-multipart · anthropic SDK 1.14 (structured outputs via `output_config`) · pytest + httpx (TestClient) · vanilla JS.

**Spec:** `docs/superpowers/specs/2026-10-14-blues-site-design.md` (v2). Lees die naast dit plan.

**Geverifieerd:** alle code in dit plan is vooraf als prototype gedraaid op orin3: 100 tests groen, `core/theory.py --selftest` groen, de server serveert alle pagina's en `node --check web/app.js` slaagt. Alleen de live-aanroep naar Claude (Task 8) is nog niet gedraaid.

## Afwijkingen van de spec (bewust; laat Bob ze bij review bevestigen)

1. **Poort 8796 in plaats van 8793.** Poort 8793 is bezet door `atelier-portaal.service` (leeratelier), en 8794 en 8795 zijn ook in gebruik. 8796 is vrij (gecontroleerd met `ss -ltnp` op 2026-10-14). `CLAUDE.md` wordt bijgewerkt.
2. **Eigen API-key-naam `BLUESLAB_ANTHROPIC_API_KEY`, nu al.** De labs-secrets-kluis rendert sleutels onder hun eigen naam. Daarom krijgt BluesLab een eigen kluis-secret (zelfde waarde als `DERWISCH_ANTHROPIC_API_KEY`) en een eigen profiel `blueslab` → `/home/bob/BluesLab/.env.secrets`.
3. **Geen tel-positie per akkoord.** De Claude-uitvoer uit spec §6 bevat geen tel-posities. `bar.akkoorden` is daarom een lijst akkoordnamen in volgorde.
4. **`bar.flag` wordt niet opgeslagen maar berekend** bij elke `GET /api/songs/{id}` (`telling`, `onparseerbaar`). Zo kan een flag nooit verouderen na een bewerking.
5. **`song.regelstarts` (JSON) + `bar.regel`** bewaren de regelindeling van de PDF, nodig voor het controlescherm en de maattelling.
6. **Tabel `content` pas in BL-3.** Die wordt pas gebruikt door de solo, coaching en oefeningen.
7. **Herordenen met ▲▼-knoppen in plaats van slepen.** Dat werkt betrouwbaar op touch zonder bibliotheek.
8. **Wachtwoord-hash-formaat `scrypt:<salt>:<hash>`** (`:` in plaats van `$`), zodat shell en systemd niets expanderen.

## Global Constraints

- `core/` blijft **stdlib-only**; `python3 core/theory.py --selftest` blijft groen.
- Interne representatie: **altijd concert pitch**. Weergave: geschreven = klinkend + offset. **Bb-klarinet `+2` (grote secunde, +1 letter), Eb-altsax `+9` (grote sext, +5 letters).** Nooit het teken omdraaien.
- Instrumentcodes in de API en de frontend: `bb` → voice `bb_clarinet`, `eb` → voice `eb_alto_sax`. Standaard is `bb`.
- Alle gebruikersteksten en foutmeldingen zijn **Nederlands**.
- Model: **`claude-sonnet-5-5`**; structured output via `output_config={"format": {"type": "json_schema", ...}}`.
- Poort **8796**, bind **127.0.0.1**; publiek via cloudflared `blues.felixisfelix.com` → `http://localhost:8796`.
- Uploads: alleen PDF (magic bytes `%PDF`), maximaal **10 MB**, opgeslagen onder een uuid-naam in `data/uploads/`.
- Login maximaal **5 pogingen per minuut per IP** (`CF-Connecting-IP`). Claude maximaal **30 aanroepen per uur** (in memory).
- Cookie: `HttpOnly`, `Secure`, `SameSite=Lax`, **30 dagen**.
- `.env`, `.env.secrets` en `data/` horen niet in git. Nooit een key in logs, in de transcript of in een commit.
- Enharmonische spelling blijft MVP-pragmatisch (BL-1 §5).
- Commit-trailer: `Co-Authored-By: Claude <model> <noreply@anthropic.com>` met het model dat de commit maakt. **Committen mag zelfstandig, pushen nooit.**

## Review Focus

De vijf randgevallen die het meest waarschijnlijk misgaan bij echt gebruik. Elk heeft een test in de genoemde task.

1. **Claude levert delen met een gat of overlap.** Verwacht: de engine valt terug op `detect_sections` en het nummer heeft toch een dekkend schema → `test_upload_structuur_met_gat_valt_terug` (Task 7).
2. **Een deel met alleen `N.C.` of lege maten** (intro of stilte). Verwacht: geen crash; toonsoort = majeur van de voortekening, bron `engine`; doeltoon leeg → `test_engine_key_deel_zonder_akkoorden`, `test_upload_deel_met_alleen_nc` (Task 7).
3. **Bob typt `B♭m`, spaties of lege velden op het controlescherm.** Verwacht: unicode-♭ wordt geaccepteerd, de toonsoort wordt genormaliseerd naar `Bbm` en lege akkoordvelden verdwijnen → `test_upload_en_controle_flow`, `test_controle_bewaart_telfout_wel` (Task 7), `test_unicode_akkoorden_bewaard` (Task 4).
4. **Claude geeft een toonsoort die niet parset** (bijv. `"B flat minor"`). Verwacht: de engine-toonsoort met bron `engine`, niet weggooien → `test_upload_claude_toonsoort_onleesbaar` (Task 7).
5. **De server start zonder `BLUESLAB_SECRET` of wachtwoord-hash.** Verwacht: hij weigert te starten. Elke cookie accepteren mag niet → `test_ontbrekende_instellingen` (Task 7), `test_sessie_vervalst` (Task 3).

---

## Bestandsstructuur

| Bestand | Verantwoordelijkheid |
|---|---|
| `core/__init__.py` | maakt `core` importeerbaar (leeg) |
| `core/chords.py` | akkoordnaam ↔ dict, letter-gebaseerd transponeren, akkoordtonen, gidstonen |
| `core/analysis.py` | maattelling, delen (detectie + controle), toonsoort per deel, speelschema per maat |
| `app/__init__.py` | leeg |
| `app/auth.py` | scrypt-wachtwoord, HMAC-sessiecookie, `RateLimiter`, CLI voor de hash |
| `app/db.py` | SQLite-schema + CRUD (setlist, song, bar, section) |
| `app/claude.py` | twee Claude-aanroepen met JSON-schema, `ClaudeFout` met NL-melding |
| `app/main.py` | FastAPI-factory `maak_app()`: login, API, upload-flow, statische `web/` |
| `web/index.html`, `setlist.html`, `controle.html`, `song.html` | vier schermen (spec §8) |
| `web/app.js`, `web/style.css` | gedeelde logica per pagina, mobile-first licht/donker |
| `tests/test_*.py` | pytest; `test_live.py` alleen met `BLUESLAB_LIVE=1` |
| `deploy/blueslab.service` | systemd-unit |
| `pytest.ini`, `requirements.txt`, `requirements-dev.txt`, `.env.example` | tooling |

---

### Task 1: Projectopzet + `core/chords.py`

**Files:**
- Create: `core/__init__.py`, `core/chords.py`, `pytest.ini`, `requirements.txt`, `requirements-dev.txt`, `tests/test_chords.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `core.theory.LETTERS`, `LETTER_PC`, `VOICES`, `spell_note(pc, letter_idx, prefer_flats) -> str` (BL-1, bestaat al).
- Produces:
  - `parse_chord(text: str) -> dict`: `{"nc": False, "root_pc", "root_letter", "kwaliteit" ∈ {maj,min,dim,aug,sus2,sus4}, "extensie" ∈ {"",7,maj7,6,9,add9}, "bas_pc", "bas_letter", "tekst"}` of `{"nc": True, "tekst"}`; `ValueError` (NL) als het niet parset.
  - `transpose_chord(chord: dict, voice: str) -> str`: ASCII-naam (`"Bbm7/F"`), `"N.C."` voor geen akkoord.
  - `transpose_note(pc, letter, voice) -> (pc, letter)`, `note_name(pc, letter) -> str`.
  - `chord_pcs(chord) -> list[int]` (concert), `chord_tones(chord, voice) -> list[str]` (geschreven).
  - `guide_tones(chord) -> list[int]` (concert-pc's: terts of sus-toon, plus septiem/sext), `guide_tone_name(pc, chord, voice) -> str`.
  - Voices: `"concert"`, `"bb_clarinet"`, `"eb_alto_sax"`.

- [ ] **Step 1: Tooling en venv**

`.gitignore`: voeg onderaan toe:

```text
data/
.env
.env.secrets
```

`pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

`requirements.txt`:

```text
fastapi>=0.115
uvicorn>=0.30
python-multipart>=0.0.9
anthropic>=1.14
```

`requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8
httpx>=0.27
```

`core/__init__.py`: leeg bestand.

Run:

```bash
cd /home/bob/BluesLab && python3 -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt && .venv/bin/python -m pytest --version
```

Expected: `pytest 9.x`.

- [ ] **Step 2: Write the failing test** — `tests/test_chords.py`:

```python
@@FILE tests/test_chords.py@@
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_chords.py -q`
Expected: FAIL / collection error `ModuleNotFoundError: No module named 'core.chords'`

- [ ] **Step 4: Write the implementation** — `core/chords.py`:

```python
@@FILE core/chords.py@@
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_chords.py -q && python3 core/theory.py --selftest`
Expected: alle tests PASS; `✅ selftest OK`.

- [ ] **Step 6: Commit**

```bash
git add .gitignore pytest.ini requirements.txt requirements-dev.txt core/__init__.py core/chords.py tests/test_chords.py
git commit -m "BL-2: core/chords — akkoorden parsen, transponeren, akkoordtonen" -m "Co-Authored-By: Claude <model> <noreply@anthropic.com>"
```

---

### Task 2: `core/analysis.py` — maattelling, delen, toonsoort, speelschema

**Files:**
- Create: `core/analysis.py`, `tests/test_analysis.py`

**Interfaces:**
- Consumes (Task 1): `parse_chord`, `transpose_chord`, `transpose_note`, `note_name`, `chord_pcs`, `chord_tones`, `guide_tones`, `guide_tone_name`.
- Produces:
  - Regels: `[{"start_maat": int, "maten": [[str, ...], ...]}]`; maten: `list[list[str]]` (concert).
  - `check_bar_count(regels) -> [{"start_maat", "verwacht": int|None, "gevonden", "ok"}]`
  - `flatten(regels) -> list[list[str]]`
  - `detect_sections(maten, blok=4) -> [{"naam": "Deel A", "start_maat", "eind_maat"}]`
  - `check_sections(delen, aantal_maten) -> list[str]` (NL-problemen, `[]` = goed; delen hebben minstens `naam`, `start_maat`, `eind_maat`)
  - Toonsoort-dict: `{"naam": "Bbm", "tonic_pc": 10, "mode": "maj"|"min"}`
  - `key_dict(tonic_pc, mode, voortekening=0) -> dict`, `parse_key(naam) -> dict` (ValueError), `same_key(a, b) -> bool`
  - `key_for_section(maten, voortekening=0) -> dict` (ValueError als er geen akkoorden zijn); voortekening = aantal kruizen, negatief = mollen
  - `written_key_name(key, voice) -> str`, `scale_names(key, voice) -> list[str]`
  - `bar_guide(nr, maat, voice, vorige_doel_pc=None) -> {"nr", "akkoorden": [{"concert", "geschreven", "tonen", "fout"}], "doeltoon", "doel_pc"}`
  - `speelschema(maten, delen, voice) -> [{"naam", "start_maat", "eind_maat", "concert_key", "geschreven_key", "toonladder", "wissel", "maten": [bar_guide…]}]`; delen hebben `concert_key` (naam-string).

Toonsoort-algoritme (spec §7): score per kandidaat (12 majeur + 12 natuurlijk mineur) = Σ diatonische fit per akkoord `(in − 2·uit)/n` + 2.0 per tonica-akkoord + 1.5 als het eerste akkoord de tonica is + 1.0 voor het laatste + 1.0 als de voortekening bij de toonsoort hoort. Crazy (B♭m–G♭–D♭–A♭, 5 mollen) → B♭m. Californication-achtig couplet (Am–F) → Am, refrein (C–G–D–Am–F) → C.

- [ ] **Step 1: Write the failing test** — `tests/test_analysis.py`:

```python
@@FILE tests/test_analysis.py@@
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_analysis.py -q`
Expected: FAIL met `ModuleNotFoundError: No module named 'core.analysis'`

- [ ] **Step 3: Write the implementation** — `core/analysis.py`:

```python
@@FILE core/analysis.py@@
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ -q && python3 core/theory.py --selftest`
Expected: alle tests PASS; selftest OK.

- [ ] **Step 5: Commit**

```bash
git add core/analysis.py tests/test_analysis.py
git commit -m "BL-2: core/analysis — maattelling, delen, toonsoort per deel, speelschema" -m "Co-Authored-By: Claude <model> <noreply@anthropic.com>"
```

---

### Task 3: `app/auth.py` — wachtwoord, sessie, rate-limit

**Files:**
- Create: `app/__init__.py` (leeg), `app/auth.py`, `tests/test_auth.py`

**Interfaces:**
- Produces:
  - `maak_hash(wachtwoord, salt=None) -> "scrypt:<salt-hex>:<hash-hex>"`, `controleer_wachtwoord(wachtwoord, opgeslagen) -> bool`
  - `maak_sessie(secret, nu=None) -> str`, `sessie_geldig(cookie, secret, nu=None) -> bool`
  - `COOKIE = "blueslab_sessie"`, `SESSIE_DUUR = 30 dagen` (seconden)
  - `RateLimiter(maximum, venster).toegestaan(sleutel, nu=None, aantal=1) -> bool`
  - CLI: `.venv/bin/python -m app.auth` vraagt het wachtwoord twee keer en print `BLUESLAB_PASSWORD_HASH=…`

- [ ] **Step 1: Write the failing test** — `tests/test_auth.py`:

```python
@@FILE tests/test_auth.py@@
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_auth.py -q`
Expected: FAIL met `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write the implementation** — `app/__init__.py` leeg, `app/auth.py`:

```python
@@FILE app/auth.py@@
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_auth.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py app/auth.py tests/test_auth.py
git commit -m "BL-2: app/auth — scrypt-wachtwoord, HMAC-sessie, rate-limiter" -m "Co-Authored-By: Claude <model> <noreply@anthropic.com>"
```

---

### Task 4: `app/db.py` — SQLite-opslag

**Files:**
- Create: `app/db.py`, `tests/test_db.py`

**Interfaces:**
- Produces (alle functies krijgen een `sqlite3.Connection` als eerste argument):
  - `verbind(pad) -> Connection` (maakt het schema aan, `row_factory = Row`, foreign keys aan)
  - `maak_setlist(conn, naam) -> int`, `setlists(conn) -> [{"id","naam","created_at","aantal"}]` (nieuwste eerst), `setlist(conn, id) -> dict|None`
  - `maak_song(conn, setlist_id, pdf_path, kop, regels, delen) -> int`. Hier is `kop = {titel, artiest, tempo, maatsoort, voortekening}` en `delen = [{naam, start_maat, eind_maat, concert_key, key_source, solo_geschikt, reden}]`. Status wordt `gelezen`, alles in één transactie.
  - `werk_song_bij(conn, song_id, kop, regels, delen)` → status `gecontroleerd`
  - `song(conn, id) -> dict|None` met `regels` en `delen` (zelfde vorm als hierboven) plus kolommen `id, setlist_id, positie, titel, artiest, pdf_path, tempo, maatsoort, voortekening, status`
  - `songs(conn, setlist_id) -> [{"id","positie","titel","artiest","tempo","status","concert_key"}]` (concert_key = eerste deel)
  - `herorden(conn, setlist_id, song_ids)`, `verwijder_song(conn, id) -> pdf_path|None`

- [ ] **Step 1: Write the failing test** — `tests/test_db.py`:

```python
@@FILE tests/test_db.py@@
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_db.py -q`
Expected: FAIL met `ImportError: cannot import name 'db' from 'app'`

- [ ] **Step 3: Write the implementation** — `app/db.py`:

```python
@@FILE app/db.py@@
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_db.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/db.py tests/test_db.py
git commit -m "BL-2: app/db — SQLite voor setlists, nummers, maten en delen" -m "Co-Authored-By: Claude <model> <noreply@anthropic.com>"
```

---

### Task 5: `app/claude.py` — PDF → maten, maten → delen

**Files:**
- Create: `app/claude.py`, `tests/test_claude.py`

**Interfaces:**
- Produces:
  - `MODEL = "claude-sonnet-5-5"`, `DEEL_NAMEN = ["Intro","Couplet","Refrein","Brug","Solo","Outro"]`
  - `class ClaudeFout(Exception)`: `str(exc)` is een NL-melding voor de gebruiker
  - `lees_pdf(pdf: bytes, client=None) -> {titel, artiest, tempo: int|None, maatsoort, voortekening: int, regels: [{start_maat, maten}]}`. De titel is opgeschoond; `ClaudeFout` bij een API-fout, time-out, refusal, max_tokens of als er geen regels zijn.
  - `structuur(titel, artiest, voortekening, maten, client=None) -> [{naam, start_maat, eind_maat, toonsoort, solo_geschikt, reden}]`
  - `schoon_titel(titel) -> str`
  - `client` is te injecteren voor tests; zonder client wordt een `anthropic.Anthropic(api_key=os.environ["BLUESLAB_ANTHROPIC_API_KEY"], timeout=180, max_retries=2)` gemaakt.

- [ ] **Step 1: Write the failing test** — `tests/test_claude.py`:

```python
@@FILE tests/test_claude.py@@
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_claude.py -q`
Expected: FAIL met `ImportError: cannot import name 'claude' from 'app'`

- [ ] **Step 3: Write the implementation** — `app/claude.py`:

```python
@@FILE app/claude.py@@
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_claude.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/claude.py tests/test_claude.py
git commit -m "BL-2: app/claude — PDF lezen en delen bepalen met structured output" -m "Co-Authored-By: Claude <model> <noreply@anthropic.com>"
```

---

### Task 6: Secrets klaarzetten (vóór de API en de live-test)

Dit is geen code; het is nodig voor Task 7 (handmatige start) en Task 8 (live-test). **Toon nooit een waarde**: niet in de output, niet in de transcript, niet in een commit.

**Files:**
- Create: `.env.example` (gecommit), `.env.secrets` (niet gecommit, gerenderd door labs-secrets)
- Modify: `/home/bob/labs-mcp/scripts/seed_profiles.py` (ander repo; commit daar apart)

- [ ] **Step 1: `.env.example`**

```text
# BluesLab — kopieer naar .env.secrets en vul in (of render met labs-secrets: profiel "blueslab").
# Wachtwoord-hash maken: .venv/bin/python -m app.auth
BLUESLAB_ANTHROPIC_API_KEY=
BLUESLAB_PASSWORD_HASH=
BLUESLAB_SECRET=
# Optioneel; standaard /home/bob/BluesLab/data
# BLUESLAB_DATA=
```

- [ ] **Step 2: Secrets in de kluis (zonder ze te tonen)**

```bash
cd ~/labs-mcp
L="env PYTHONPATH=$HOME/labs-mcp python3 -m labsctl.cli"
$L set BLUESLAB_ANTHROPIC_API_KEY "$($L get DERWISCH_ANTHROPIC_API_KEY)" --kind token --used-by blueslab >/dev/null
$L set BLUESLAB_SECRET "$(python3 -c 'import secrets; print(secrets.token_hex(32))')" --kind token --used-by blueslab >/dev/null
$L list | grep BLUESLAB
```

Expected: twee regels `BLUESLAB_…` met metadata, zonder waarden. (Controleer eerst met `$L get --help` of `get` alleen de waarde print; zo niet, pas de substitutie aan.)

Het wachtwoord kiest **Bob zelf**. Vraag hem in de prompt te typen:
`! cd ~/BluesLab && .venv/bin/python -m app.auth`
Laat hem daarna de hash opslaan:
`! cd ~/labs-mcp && PYTHONPATH=~/labs-mcp python3 -m labsctl.cli set BLUESLAB_PASSWORD_HASH 'scrypt:…' --kind password --used-by blueslab`

- [ ] **Step 3: Profiel `blueslab` in `seed_profiles.py`** (vóór `vault.save_vault(d, data)`):

```python
    data["profiles"]["blueslab"] = {"targets": [{
        "type": "env_file",
        "path": "/home/bob/BluesLab/.env.secrets",
        "keys": ["BLUESLAB_ANTHROPIC_API_KEY", "BLUESLAB_PASSWORD_HASH", "BLUESLAB_SECRET"],
        "restart_unit": "blueslab.service",
    }]}
```

Run:

```bash
cd ~/labs-mcp && PYTHONPATH=~/labs-mcp python3 scripts/seed_profiles.py && PYTHONPATH=~/labs-mcp python3 -m labsctl.cli render blueslab
ls -l /home/bob/BluesLab/.env.secrets && cut -d= -f1 /home/bob/BluesLab/.env.secrets
cd /home/bob/BluesLab && git status --short   # .env.secrets mag hier NIET verschijnen
```

Expected: het bestand heeft `-rw-------`, drie sleutelnamen, en `git status` toont alleen `.env.example`. (Render zonder `--restart`: de unit bestaat pas na Task 9.)

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -m "BL-2: .env.example voor de BluesLab-secrets" -m "Co-Authored-By: Claude <model> <noreply@anthropic.com>"
```

Commit in `~/labs-mcp` alleen de wijziging aan `scripts/seed_profiles.py`, als dat een git-repo is.

---

### Task 7: `app/main.py` — API, upload-flow, statische site

**Files:**
- Create: `app/main.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: Task 2 (`check_bar_count, check_sections, detect_sections, flatten, key_dict, key_for_section, parse_key, same_key, speelschema, written_key_name`), Task 1 (`parse_chord`), Task 3 (`auth.*`), Task 4 (`db.*`), Task 5 (`ClaudeFout`; module met `lees_pdf`, `structuur`).
- Produces:
  - `maak_app(instellingen: dict = None) -> FastAPI` met de sleutels `data_dir`, `password_hash`, `secret`, `claude` (object met `lees_pdf`/`structuur`) en `web_dir`. Ontbrekende sleutels komen uit de env; zonder hash of secret volgt `RuntimeError`.
  - `engine_key(maten, voortekening) -> toonsoort-dict` (nooit een exception).
  - Routes (alles behalve login/logout vereist de cookie, anders 401 "Log eerst in."):
    - `POST /api/login {wachtwoord}`, `POST /api/logout`, `GET /api/ik`
    - `GET /api/setlists`, `POST /api/setlists {naam}` → `{id}` (201)
    - `GET /api/setlists/{id}` → setlist + `songs[]` met `sleutels: {bb, eb}`
    - `PUT /api/setlists/{id}/volgorde {song_ids}`
    - `POST /api/setlists/{id}/songs` (multipart `bestand`) → `{id}` (201); 404/413/415/429/502
    - `GET /api/songs/{id}` → song + `telling`, `onparseerbaar`, `aantal_maten`, per deel `engine_key` en `afwijking`
    - `PUT /api/songs/{id}` (controle) → status `gecontroleerd`; 422 met een lijst NL-problemen
    - `DELETE /api/songs/{id}`
    - `GET /api/songs/{id}/schema?instrument=bb|eb` → kop + `delen` (speelschema)
  - `web/` gemount op `/` als die map bestaat.

- [ ] **Step 1: Write the failing test** — `tests/test_api.py`:

```python
@@FILE tests/test_api.py@@
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py -q`
Expected: FAIL met `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write the implementation** — `app/main.py`:

```python
@@FILE app/main.py@@
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q && python3 core/theory.py --selftest`
Expected: alles PASS (de live-test wordt `skipped`); selftest OK.

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "BL-2: app/main — API, login, PDF-upload, controle en speelschema" -m "Co-Authored-By: Claude <model> <noreply@anthropic.com>"
```

---

### Task 8: Live-test met de echte PDF + golden fixture

**Files:**
- Create: `tests/test_live.py`, `tests/fixtures/crazy-regels.json`, `tests/test_golden.py`

**Interfaces:**
- Consumes: `app.claude.lees_pdf`, `core.analysis.check_bar_count`, `flatten`, `key_for_section`, `speelschema`.
- Produces: `tests/fixtures/crazy-regels.json` = `{"titel", "artiest", "tempo", "maatsoort", "voortekening", "regels"}` (exact de vorm van `lees_pdf`, handmatig gecontroleerd).

- [ ] **Step 1: Live-test** — `tests/test_live.py`:

```python
@@FILE tests/test_live.py@@
```

- [ ] **Step 2: Draaien (één API-aanroep)**

```bash
cd /home/bob/BluesLab && set -a && . ./.env.secrets && set +a && BLUESLAB_LIVE=1 .venv/bin/python -m pytest tests/test_live.py -v -s
```

Expected: PASS. Faalt hij, **pas dan niet de test aan**, maar:
- Is de maattelling fout, verbeter dan `LEES_PROMPT` in `app/claude.py`. Draai het hooguit drie keer; blijft het fout, meld dat aan Bob met de JSON-uitvoer. Het controlescherm vangt het in de praktijk op, maar de spec eist de smoketest.
- Is de titel fout, kijk dan of `schoon_titel` hem had moeten vangen.

- [ ] **Step 3: Handmatige controle en golden fixture**

Leg de geprinte JSON naast de PDF (`pdftoppm -r 80 -png tests/fixtures/chordify-crazy.pdf <scratchpad>/crazy`, bekijk de PNG). Controleer elke regel maat voor maat en verbeter waar nodig. De eerste regel moet bijvoorbeeld beginnen met `["Bbm"], ["Gb"], ["Db"], ["Ab", …]`. Schrijf het gecontroleerde resultaat naar `tests/fixtures/crazy-regels.json` (UTF-8, `indent=1`). **Laat Bob de fixture bevestigen** voordat je hem commit: hij is de waarheid voor latere regressietests.

- [ ] **Step 4: Golden-test** — `tests/test_golden.py`:

```python
@@FILE tests/test_golden.py@@
```

Run: `.venv/bin/python -m pytest -q`
Expected: alles PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_live.py tests/test_golden.py tests/fixtures/crazy-regels.json
git commit -m "BL-2: live-smoketest Chordify-PDF + golden fixture Crazy" -m "Co-Authored-By: Claude <model> <noreply@anthropic.com>"
```

(Pas je `LEES_PROMPT` aan, neem dan ook `app/claude.py` op in deze commit.)

---

### Task 9: `web/` — login, setlists, controle, speelschema

**Files:**
- Create: `web/index.html`, `web/setlist.html`, `web/controle.html`, `web/song.html`, `web/app.js`, `web/style.css`

**Interfaces:**
- Consumes: de routes uit Task 7. Elke pagina heeft `<body data-pagina="index|setlist|controle|song">`; `app.js` kiest daarop de init-functie.
- Instrumentkeuze in `localStorage["instrument"]` (`bb`/`eb`, standaard `bb`; elke toegang zit in try/catch).
- Weergave: `mooi("Bbm7")` → `B♭m7`. De API levert ASCII-namen.

- [ ] **Step 1: `web/index.html`**

```html
@@FILE web/index.html@@
```

- [ ] **Step 2: `web/setlist.html`**

```html
@@FILE web/setlist.html@@
```

- [ ] **Step 3: `web/controle.html`**

```html
@@FILE web/controle.html@@
```

- [ ] **Step 4: `web/song.html`**

```html
@@FILE web/song.html@@
```

- [ ] **Step 5: `web/style.css`**

```css
@@FILE web/style.css@@
```

- [ ] **Step 6: `web/app.js`**

```javascript
@@FILE web/app.js@@
```

- [ ] **Step 7: Syntax en statische serving**

```bash
node --check web/app.js && echo syntax-ok   # node 12 op orin3: gebruik geen ?? of ?. in app.js
.venv/bin/python -m pytest -q
```

Expected: `syntax-ok`; alle tests PASS.

- [ ] **Step 8: Handmatig doorlopen in de browser (lokaal)**

```bash
cd /home/bob/BluesLab && set -a && . ./.env.secrets && set +a && .venv/bin/uvicorn app.main:maak_app --factory --host 127.0.0.1 --port 8796
```

Gebruik de skill `run` of open `http://localhost:8796` via `ssh -L 8796:localhost:8796 bob@orin3`. Let op: de cookie is `Secure`, dus over plain HTTP logt de browser niet in. Test daarom de login pas via de tunnel (Task 10), of start lokaal tijdelijk via `https` niet. De API-flow zelf is al gedekt door `tests/test_api.py`. Controleer lokaal alleen dat de pagina's laden en het loginscherm verschijnt.

- [ ] **Step 9: Commit**

```bash
git add web/
git commit -m "BL-2: web — login, setlists, controlescherm en speelschema per maat" -m "Co-Authored-By: Claude <model> <noreply@anthropic.com>"
```

---

### Task 10: Deploy — systemd, cloudflared, documentatie

**Files:**
- Create: `deploy/blueslab.service`
- Modify: `CLAUDE.md`, `README.md`, `/home/bob/ORIN3_SYSTEEM.md`, `/mnt/nvme/workspaces/leeratelier/docs/inventaris-orin3.md`

- [ ] **Step 1: `deploy/blueslab.service`**

```ini
[Unit]
Description=BluesLab site (blues.felixisfelix.com, poort 8796)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=bob
WorkingDirectory=/home/bob/BluesLab
EnvironmentFile=/home/bob/BluesLab/.env.secrets
ExecStart=/home/bob/BluesLab/.venv/bin/uvicorn app.main:maak_app --factory --host 127.0.0.1 --port 8796
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Installeren en starten**

```bash
sudo ss -ltnp | grep ':8796 ' && echo "BEZET — stop en overleg met Bob" || echo vrij
sudo cp deploy/blueslab.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now blueslab.service
sleep 2 && systemctl is-active blueslab.service && curl -s -o /dev/null -w '%{http_code}\n' localhost:8796/ && curl -s localhost:8796/api/ik
```

Expected: `vrij`, `active`, `200`, `{"detail":"Log eerst in."}`.

- [ ] **Step 3: cloudflared Public Hostname (handmatige stap voor Bob)**

Vraag Bob in het Zero Trust-dashboard (tunnel `ca12e4f6-…`, Public Hostnames) toe te voegen: `blues.felixisfelix.com` → service `HTTP` `localhost:8796`. Wacht op zijn bevestiging en controleer dan:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://blues.felixisfelix.com/ && curl -s https://blues.felixisfelix.com/api/ik
```

Expected: `200` en `{"detail":"Log eerst in."}`.

- [ ] **Step 4: Live end-to-end (met Bob, op zijn telefoon)**

Inloggen → setlist "Next week" → `tests/fixtures/chordify-crazy.pdf` uploaden → controlescherm (regels zonder rood) → Opslaan → speelschema. Controleer: klarinet geeft kop `Cm` en maat 1 `Cm`; alt sax geeft `Gm`. Wisselen van instrument blijft bewaard na herladen. Na zes foute wachtwoorden binnen een minuut volgt "Te veel pogingen".

- [ ] **Step 5: Documentatie**

- `CLAUDE.md`: "Gereserveerde backend-poort: `8793`…" wordt "Backend-poort: **`8796`** (`blueslab.service`; 8793 is van leeratelier)". Zet BL-2 bij Stories met status "geïmplementeerd" en een verwijzing naar dit plan. Voeg een valkuil toe: "Cookie is `Secure`: inloggen alleen via https (tunnel)."
- `README.md`: sectie "Site (BL-2)" met starten, testen (`.venv/bin/python -m pytest`, live-test) en secrets (labs-secrets-profiel `blueslab`).
- `/home/bob/ORIN3_SYSTEEM.md`: dienstentabel `blueslab` | 8796 | BluesLab-site (127.0.0.1) | enabled; ingress `blues.felixisfelix.com` → `http://localhost:8796`.
- `inventaris-orin3.md`: BluesLab van "SLUIMERT" naar actief, met `https://blues.felixisfelix.com · :8796`; poorttabel en ingress-regel aanvullen.

- [ ] **Step 6: Commit (alleen BluesLab-bestanden)**

```bash
git add deploy/blueslab.service CLAUDE.md README.md
git commit -m "BL-2: deploy — blueslab.service op 8796, docs bijgewerkt" -m "Co-Authored-By: Claude <model> <noreply@anthropic.com>"
```

`ORIN3_SYSTEEM.md` staat niet in een repo. De inventaris hoort bij `leeratelier`: commit die daar apart en alleen dat bestand. **Niet pushen.** Vraag Bob of en wanneer.
