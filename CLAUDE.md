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
- **Gereserveerde backend-poort:** `8793` (pas vanaf een latere story, niet in BL-1).
- Stdlib-only waar mogelijk (BL-1: `core/theory.py` = puur stdlib + `argparse`).

## Stories
- **BL-1** (`docs/BL-1-transponeer-engine.md`): pure-Python transponeer-engine + zelftest. *Status: structuur opgezet, implementatie volgt.*
- BL-2+ (later): play-along (MIDI/fluidsynth), mic/transcriptie, akkoord-mapping, LLM-coaching, sessielog.

## Valkuilen
- `find ~` bevriest op orin3 → gebruik `ls <pad>`.
- Transpositie-teken niet omdraaien; de `--selftest`-asserts vangen dit.
- Enharmonische spelling is een rabbit hole → MVP-pragmatisch (story §5), niet perfectioneren.
