# BluesLab

Oefentool die voor elke blues-toonsoort het 12-maats schema, de bluestoonladder en
de akkoordtonen toont — **getransponeerd naar de geschreven notatie** voor
**Bes klarinet (Bb)** en **alt sax (Eb)**. Interne representatie is altijd concert pitch.

## Structuur

```text
BluesLab/
  core/theory.py   # pure logica (stdlib + argparse) — BL-1
  docs/            # stories / specs
  tests/           # optioneel; minimale eis is --selftest in theory.py
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
