# BluesLab — Claude Code instructies

> **Machine-breed:** `~/.claude/CLAUDE.md` + `ORIN3_SYSTEEM.md`.
> **Domein:** Persoonlijk & Web (muziek-oefentool). **Start via** `orin3` → window `blueslab`.

Oefentool voor blues op **Bes klarinet (Bb)** en **alt sax (Eb)**: genereert per
concert-toonsoort het 12-maats schema, bluestoonladder en akkoordtonen,
**getransponeerd naar de geschreven notatie** van het instrument.

## Vaste conventies (uit de stories — niet onderhandelbaar)
- **Repo-root:** `/home/bob/BluesLab` (NIET in de Derwisch-repo).
- **Interne representatie:** altijd **concert pitch**, pitch-class 0–11. Weergave = getransponeerd.
- **Transpositie:** geschreven = klinkend + offset. Bb-klarinet `+2`, Eb-altsax `+9`.
- **Primair instrument:** Bes klarinet (Bb sopraan) — géén basklarinet.
- **Output/CLI-taal:** Nederlands.
- **Backend-poort:** **`8796`** (`blueslab.service`, bind 127.0.0.1; 8793 is van leeratelier). Publiek: `https://blues.felixisfelix.com` via de cloudflared-tunnel.
- Stdlib-only waar mogelijk: heel `core/` is stdlib-only; `app/` (FastAPI, anthropic) draait in `.venv/`.
- **Secrets** via labs-secrets-profiel `blueslab` → `.env.secrets` (`BLUESLAB_ANTHROPIC_API_KEY`, `BLUESLAB_PASSWORD_HASH`, `BLUESLAB_SECRET`). Claude mag de kluis niet lezen/schrijven (auto-mode blokkeert dat): Bob draait die commando's zelf.

## Werkwijze (sessies)
1. `ssh bob@orin3` → `tmux attach -t orin3` (of `orin3` als de sessie nog niet bestaat).
2. Window **`blueslab`** kiezen: `Ctrl-b '` → `blueslab`, of `tmux select-window -t orin3:blueslab`.
3. Daar `claude --continue` om de vorige sessie te hervatten (of `claude` voor een nieuwe).
4. Weg? `Ctrl-b d` (detach) of verbinding gewoon laten vallen — Claude draait door.

**Nooit `claude` direct in de SSH-shell starten:** valt SSH weg, dan stopt Claude en wordt
de sessie "gearchiveerd" (gebeurde 3× op 2026-10-14). Tussenresultaten (plannen,
prototypes) gaan meteen de repo in en worden gecommit — nooit alleen in de scratchpad.

## Stories
- **BL-1** (`docs/BL-1-transponeer-engine.md`): pure-Python transponeer-engine + zelftest. *Status: klaar (`51ff3be`).*
- **BL-2 — BluesLab-site** (`blues.felixisfelix.com`, Chordify-PDF → speelschema per maat):
  - spec v2: `docs/superpowers/specs/2026-10-14-blues-site-design.md`
  - plan (10 tasks): `docs/superpowers/plans/2026-10-14-blues-site.md`
  - geverifieerd prototype (100 tests groen): `docs/superpowers/plans/2026-10-14-blues-site-proto/`
  - *Status: geïmplementeerd en live (2026-10-15), branch `bl-2-site`. Tests: `.venv/bin/python -m pytest` (live-test: `set -a; . ./.env.secrets; set +a; BLUESLAB_LIVE=1 .venv/bin/python -m pytest tests/test_live.py -s`).*
- **Oefenen per nummer** (fragment + meespeel-begeleiding op de songpagina):
  spec `docs/superpowers/specs/2026-10-15-oefenen-design.md`, plan `docs/superpowers/plans/2026-10-15-oefenen.md`.
  Fragment = iTunes Search API vanuit de browser; begeleiding = eigen Web-Audio-synth in `web/speler.js`.
  Geen serverwijziging. *Status: gebouwd (2026-10-15), branch `bl-2-site`.*
- **Meespelen met piano en shuffle**: spec `docs/superpowers/specs/2026-10-16-piano-shuffle-design.md`,
  plan `docs/superpowers/plans/2026-10-16-piano-shuffle.md`. Salamander-samples in `web/piano/`
  (opnieuw maken: `scripts/piano-samples.sh`), geladen bij de eerste ▶. *Status: gebouwd (2026-10-16), branch `bl-2-site`.*
- **Stijlen per nummer met drums** (Shuffle · Pop · Ballad · Funk): spec
  `docs/superpowers/specs/2026-10-16-stijlen-drums-design.md`, plan `docs/superpowers/plans/2026-10-16-stijlen-drums.md`.
  Patronen = tabellen `STIJLEN` in `web/speler.js`; stijl per nummer in `song.stijl` (`PUT /api/songs/{id}/stijl`).
  *Status: gebouwd (2026-10-16), branch `stijlen-drums`.*
- Later: live meeluisteren (mic), feedback na de repetitie, LLM-coaching, sessielog.

## Valkuilen
- `find ~` bevriest op orin3 → gebruik `ls <pad>`.
- Transpositie-teken niet omdraaien; de `--selftest`-asserts vangen dit.
- Cookie is `Secure`: inloggen alleen via https (de tunnel), niet via `http://localhost:8796`.
- **Login = gewoon formulier** (`POST /login` → 303), géén `fetch`: iOS Safari 26 bewaarde de sessiecookie uit een fetch-antwoord niet (vastgesteld 2026-10-15). `/api/login` (JSON) bestaat alleen nog voor tests.
- Een 401 op `/api/*` logt de reden (`geen cookie` + cookienamen, of `ongeldige cookie`), nooit de waarde: `journalctl -u blueslab.service`.
- Pagina's laden `app.js?v=N`: Cloudflare geeft statische bestanden 4 uur browsercache. **Verhoog `v`** in alle `web/*.html` bij elke wijziging aan `app.js`/`style.css` (en in `song.html` voor `speler.js`).
- Frontend-tests: `tests/test_web.py` en `tests/test_speler.py` draaien `web/speler.js` + `web/app.js` met node in een nep-browser (`tests/web_harness.js`, `tests/web_eval.js`).
- **Node op orin3 is v12**: geen `?.` of `??` in `web/*.js`, anders falen de frontend-tests (syntaxfout).
- iOS zet audio alleen aan binnen een tik: `speler.ontgrendel()` vóór elke `await` (het laden van de piano is async).
- Fragmentkeuze: iTunes zet soms een ander nummer bovenaan (Spooky → de Stones); `kiesFragment` laat daarom de exacte titel voorgaan.
- Na een wijziging aan `app/`/`core/`/`web/`: `sudo systemctl restart blueslab.service`.
- Enharmonische spelling is een rabbit hole → MVP-pragmatisch (story §5), niet perfectioneren.
