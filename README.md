# BluesLab

Oefentool die voor elke blues-toonsoort het 12-maats schema, de bluestoonladder en
de akkoordtonen toont — **getransponeerd naar de geschreven notatie** voor
**Bes klarinet (Bb)** en **alt sax (Eb)**. Interne representatie is altijd concert pitch.

## Structuur

```text
BluesLab/
  core/            # stdlib-engine: theory.py (BL-1), chords.py, analysis.py (BL-2)
  app/             # FastAPI: auth, db (SQLite), claude (PDF lezen), main (API)
  web/             # vanilla HTML/JS, geen build-stap
  deploy/          # blueslab.service (systemd)
  docs/            # stories / specs / plannen
  tests/           # pytest; fixtures/chordify-crazy.pdf + golden crazy-regels.json
```

## Gebruik (BL-1)

```bash
# Toon een toonsoort/vorm/instrument leesbaar:
python3 core/theory.py --key Bb --form jazz  --instrument bb_clarinet
python3 core/theory.py --key F  --form basic --instrument eb_alto_sax

# Zelftest (harde asserts):
python3 core/theory.py --selftest
```

Instrumenten: `concert`, `bb_clarinet` (+2), `eb_alto_sax` (+9).
Vormen: `basic` (quick-change shuffle) en `jazz` (F-blues template).

## Status

BL-1 geïmplementeerd: `core/theory.py` levert `get_blues()` + CLI + `--selftest`
(stdlib-only) volgens `docs/BL-1-transponeer-engine.md`. Zelftest groen.

**Notatie:** de spelling is muziektheoretisch (letter-gebaseerd): elke schaal-
en akkoordtoon krijgt de juiste notnaam-letter voor zijn functie (terts op de
tertsletter, b5 op de kwintletter, enz.). Daardoor zijn blue notes mollen
(G-blues = `G Bb C Db D F`, ook al is G een kruis-toonsoort) en krijgt elke
diatonische ladder elke letter precies één keer.

> Pragmatische keuzes (story §5, bewust): verminderde-septiemakkoorden krijgen
> de lead-sheet-spelling (`C°7 = C Eb Gb A`, niet de strikte dubbelmol `Bbb`), en
> de zeldzame trap die anders een dubbel voorteken zou vragen (bv. b5 van Ab)
> wordt enharmonisch met één voorteken herspeld.

## Site (BL-2) — https://blues.felixisfelix.com

Upload een Chordify-PDF, controleer de gelezen maten en krijg per maat een speelschema
(geschreven akkoord, akkoordtonen, doeltoon) voor Bes klarinet of alt sax.

Oefenen op de songpagina: **▶ Fragment** speelt 30 s van de echte opname (iTunes), en
**▶ Speel** speelt uit de concert-akkoorden een shuffle op piano (linkerhand kwint-sext-septiem,
akkoord op 2 en 4) met een zachte tik.
Tik op een maat om daar te beginnen; tempo 50/75/100 %; **🔁 Herhaal dit deel** lust het deel.
Pianoklank: samples van de **Salamander Grand Piano** (Alexander Holm, CC-BY 3.0), via Tone.js,
verkleind met `scripts/piano-samples.sh` naar `web/piano/`. Lukt het laden niet, dan klinkt een
eenvoudige synth.

```bash
# Eenmalig
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

# Testen (live-test wordt overgeslagen)
.venv/bin/python -m pytest
# Live-test tegen de Claude-API (één aanroep)
set -a; . ./.env.secrets; set +a; BLUESLAB_LIVE=1 .venv/bin/python -m pytest tests/test_live.py -s

# Dienst (poort 8796, alleen 127.0.0.1; publiek via de cloudflared-tunnel)
sudo systemctl restart blueslab.service
journalctl -u blueslab.service -f
```

**Secrets** komen uit labs-secrets, profiel `blueslab` → `.env.secrets` (niet in git), zie
`.env.example`. Nieuw wachtwoord: `.venv/bin/python -m app.auth` in een echte terminal
(getpass), en de hash opslaan als `BLUESLAB_PASSWORD_HASH`; daarna
`labsctl render blueslab` en de dienst herstarten.
