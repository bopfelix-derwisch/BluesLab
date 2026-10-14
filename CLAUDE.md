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
- **Gereserveerde backend-poort:** `8793` was gereserveerd, maar is bezet door `atelier-portaal` (leeratelier); het BL-2-plan stelt **`8796`** voor (nog te bevestigen).
- Stdlib-only waar mogelijk (BL-1: `core/theory.py` = puur stdlib + `argparse`).

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
  - *Status: plan-review door Bob (sectie "Afwijkingen van de spec"), daarna Task 1.*
- Later: play-along (MIDI/fluidsynth), mic/transcriptie, LLM-coaching, sessielog.

## Valkuilen
- `find ~` bevriest op orin3 → gebruik `ls <pad>`.
- Transpositie-teken niet omdraaien; de `--selftest`-asserts vangen dit.
- Enharmonische spelling is een rabbit hole → MVP-pragmatisch (story §5), niet perfectioneren.
