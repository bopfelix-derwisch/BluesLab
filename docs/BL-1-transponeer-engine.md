# BluesLab — Story BL-1: Transponeer-engine

**Voor:** Claude Code op `orin3` (Developer)
**Van:** PO/Architect (claude.ai)
**Versie:** 1.0 · **Datum:** 2026-06-26
**Status:** klaar voor implementatie

> **Doel van BL-1:** een pure-Python module die voor een opgegeven blues-toonsoort (in concert pitch) het 12-maats schema, de bluestoonladder en de akkoordtonen levert — getransponeerd naar de **geschreven** notatie voor **Bes klarinet (Bb)** en **alt sax (Eb)**. Geen backend, geen hardware, geen audio. Alleen logica + zelftest.

---

## 0. Naamgeving & conventies (niet onderhandelbaar)

| Item | Waarde |
|------|--------|
| Projectnaam | `BluesLab` |
| Repo/root op orin3 | `/home/bob/BluesLab` |
| Backend-poort (gereserveerd, NIET in BL-1) | `8793` |
| Interne representatie | **altijd concert pitch** (pitch-class 0–11) |
| Weergave | getransponeerd naar geschreven Bb (klarinet) / Eb (alt sax) |
| Primair instrument | **Bes klarinet (Bb sopraan)** |
| Secundair | alt sax (Eb) |
| Taal output/CLI | Nederlands |

---

## ⚠️ Waarschuwingen (lees eerst — bespaart een avond)

| # | Valkuil | Correct |
|---|---------|---------|
| 1 | Het is **Bes klarinet (Bb sopraan)**, geen basklarinet | Pitch-class transpositie is identiek (+2); octaaf-tessituur pas relevant in BL-4/5 |
| 2 | Transpositierichting omdraaien | **geschreven = klinkend + transpositie.** Bb-instrument: `+2`. Eb-instrument: `+9`. De zelftest-asserts in §6 vangen een omgedraaid teken |
| 3 | Dit hoort **niet** in de Derwisch-repo | Nieuwe repo: `/home/bob/BluesLab` |
| 4 | `find ~` bevriest op orin3 | Gebruik `ls <pad>` of expliciete paden |
| 5 | Enharmonische spelling is een rabbit hole | MVP: pragmatische spelling (§5), bekende beperking — niet perfectioneren |
| 6 | Geen backend/HTTP/audio in BL-1 | Puur `core/theory.py` + CLI + zelftest |

---

## 1. Story

**Als** oefenende klarinettist/saxofonist
**wil ik** voor elke blues-toonsoort het schema + de toonladders zien in de notatie die ík voor mijn neus heb,
**zodat** ik niet bij elke toonsoort handmatig hoef te transponeren.

### In scope
- 12-maats blues genereren in twee vormen: `basic` (quick-change shuffle) en `jazz`.
- Per "voice" (concert / Bes klarinet / alt sax): geschreven toonsoort, 12 akkoorden, bluestoonladder, en per uniek akkoord de akkoordtonen + aanbevolen toonladder.
- Alle 12 concert-toonsoorten ondersteund.
- CLI om snel een toonsoort/vorm/instrument te tonen.
- `--selftest` met harde asserts.

### Uit scope (latere stories)
- HTTP/backend (BL-0/later), audio/play-along (BL-2), mic/transcriptie (BL-3/4), akkoord-mapping van gespeelde noten (BL-5), LLM-coaching (BL-6), sessielog (BL-7).

---

## 2. Bestandsstructuur (BL-1)

```text
/home/bob/BluesLab/
  core/
    theory.py        # pure logica — geen imports buiten stdlib + argparse
  README.md          # korte run-instructie
```

Geen `requirements.txt` nodig (alleen stdlib). `tests/` mag, maar `python3 core/theory.py --selftest` is de minimale eis.

---

## 3. API-contract

### Hoofdfunctie
```python
def get_blues(concert_key: str, form: str = "basic") -> dict
```

- `concert_key`: een van `C C# Db D D# Eb E F F# Gb G G# Ab A A# Bb B` (case-insensitief, `#`/`b` toegestaan).
- `form`: `"basic"` of `"jazz"`.
- Bij ongeldige input: `ValueError` met duidelijke NL-melding.

### Retourstructuur
```json
{
  "concert_key": "Bb",
  "form": "basic",
  "voices": {
    "concert": {
      "transpose_semitones": 0,
      "written_key": "Bb",
      "bars": [["Bb7"], ["Eb7"], ["Bb7"], ["Bb7"], ["Eb7"], ["Eb7"],
               ["Bb7"], ["Bb7"], ["F7"], ["Eb7"], ["Bb7"], ["F7"]],
      "blues_scale": ["Bb", "Db", "Eb", "E", "F", "Ab"],
      "chords": {
        "Bb7": { "root": "Bb", "quality": "dom7",
                 "chord_tones": ["Bb", "D", "F", "Ab"],
                 "scale": ["Bb", "C", "D", "Eb", "F", "G", "Ab"] },
        "Eb7": { "...": "..." },
        "F7":  { "...": "..." }
      }
    },
    "bb_clarinet": { "transpose_semitones": 2, "written_key": "C",  "...": "..." },
    "eb_alto_sax": { "transpose_semitones": 9, "written_key": "G",  "...": "..." }
  }
}
```

- `bars`: lijst van 12 maten; elke maat is een lijst akkoordnamen (meestal 1, soms 2 in `jazz`).
- `chords`: per unieke akkoordnaam in deze voice de details. `scale` = mixolydisch (dominant) als default per akkoord; voor de bluestoonladder zie `blues_scale` op voice-niveau.

---

## 4. Muziektheorie-spec (exact — geen interpretatie nodig)

### 4.1 Pitch-classes
```
C=0  C#/Db=1  D=2  D#/Eb=3  E=4  F=5  F#/Gb=6  G=7  G#/Ab=8  A=9  A#/Bb=10  B=11
```

### 4.2 Voices (transpositie in halve tonen)
```python
VOICES = {
    "concert":     0,
    "bb_clarinet": 2,   # geschreven = klinkend + 2
    "eb_alto_sax": 9,   # geschreven = klinkend + 9
}
```
Werkwijze: bereken `written_root = (concert_root_pc + transpose) % 12`, bouw dan de vorm met onderstaande graad-offsets op die `written_root`. Toonladders idem (+transpose).

### 4.3 Bouwstenen op een root-pc `R`
- **Bluestoonladder** (hexatonisch): `[R, R+3, R+5, R+6, R+7, R+10]`
- **Mixolydisch** (dominant): `[R, R+2, R+4, R+5, R+7, R+9, R+10]`
- **Akkoordtonen:**
  - `dom7`: `[R, R+4, R+7, R+10]`
  - `min7`: `[R, R+3, R+7, R+10]`
  - `dim7`: `[R, R+3, R+6, R+9]`
- **Aanbevolen toonladder per akkoord:** `dom7 → mixolydisch`, `min7 → dorisch [R,R+2,R+3,R+5,R+7,R+9,R+10]`, `dim7 → hele-halve dim [R,R+2,R+3,R+5,R+6,R+8,R+9,R+11]`.

### 4.4 Akkoordnaamgeving
`<root><suffix>` met suffix: `dom7 → "7"`, `min7 → "m7"`, `dim7 → "dim7"`. Bijv. root=Eb, dom7 → `"Eb7"`; root=G, min7 → `"Gm7"`.

### 4.5 Vormen (per graad — `(offset_t.o.v._key_root, quality)`)

**`basic`** (quick-change, turnaround), 12 maten, elk 1 akkoord:
```
1:(0,dom7)  2:(5,dom7)  3:(0,dom7)  4:(0,dom7)
5:(5,dom7)  6:(5,dom7)  7:(0,dom7)  8:(0,dom7)
9:(7,dom7) 10:(5,dom7) 11:(0,dom7) 12:(7,dom7)
```

**`jazz`** (F-blues template, in graden — transponeert naar elke toonsoort), maten met 1 of 2 akkoorden:
```
1:[(0,dom7)]            2:[(5,dom7)]            3:[(0,dom7)]   4:[(7,min7),(0,dom7)]
5:[(5,dom7)]            6:[(6,dim7)]            7:[(0,dom7)]   8:[(9,dom7)]
9:[(2,min7)]           10:[(7,dom7)]           11:[(0,dom7),(9,dom7)]  12:[(2,min7),(7,dom7)]
```
Controle in concert F: F7 | Bb7 | F7 | Cm7 F7 | Bb7 | Bdim7 | F7 | D7 | Gm7 | C7 | F7 D7 | Gm7 C7. ✓

---

## 5. Spelling (flats vs sharps) — MVP-pragmatisch

Spel akkoord- en ladder-noten met flats óf sharps afhankelijk van de **geschreven** toonsoort:

- **Flat-toonsoorten** (gebruik flats): `C, F, Bb, Eb, Ab, Db, Gb`
- **Sharp-toonsoorten** (gebruik sharps): `G, D, A, E, B, F#`

Implementeer `pc_to_name(pc, prefer_flats: bool)` met twee naamtabellen. Bepaal `prefer_flats` uit de `written_key` van de voice.

> **Bekende beperking (akkoord, geen bug):** enharmonische randgevallen (bv. een geschreven F#-blues) kunnen niet-ideale spelling tonen. Acceptabel voor MVP; eventueel verfijnen in een latere story. Niet nu oplossen.

---

## 6. Zelftest (verplicht — `python3 core/theory.py --selftest`)

Harde asserts, exit-code 1 bij falen:

```python
# Transpositie van toonsoort-root (concert pc -> geschreven pc)
assert written_key_pc("Bb", "bb_clarinet") == 0   # Bb -> C
assert written_key_pc("Bb", "eb_alto_sax") == 7   # Bb -> G
assert written_key_pc("F",  "bb_clarinet") == 7   # F  -> G
assert written_key_pc("F",  "eb_alto_sax") == 2   # F  -> D
assert written_key_pc("C",  "bb_clarinet") == 2   # C  -> D
assert written_key_pc("Eb", "eb_alto_sax") == 0   # Eb -> C

# basic blues in concert Bb, maat 2 (IV7)
b = get_blues("Bb", "basic")
assert b["voices"]["concert"]["bars"][1]     == ["Eb7"]
assert b["voices"]["bb_clarinet"]["bars"][1] == ["F7"]
assert b["voices"]["eb_alto_sax"]["bars"][1] == ["C7"]

# bluestoonladder concert C
assert get_blues("C","basic")["voices"]["concert"]["blues_scale"] == ["C","Eb","F","Gb","G","Bb"]

# jazz F klopt met template
j = get_blues("F","jazz")["voices"]["concert"]["bars"]
assert j[3] == ["Cm7","F7"] and j[11] == ["Gm7","C7"] and j[5] == ["Bdim7"]

# alle 12 toonsoorten crashen niet
for k in ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","B"]:
    get_blues(k,"basic"); get_blues(k,"jazz")
print("✅ selftest OK")
```

---

## 7. CLI

```bash
# Toon een toonsoort/vorm/instrument leesbaar:
python3 core/theory.py --key Bb --form jazz --instrument bb_clarinet
python3 core/theory.py --key F  --form basic --instrument eb_alto_sax

# Zelftest:
python3 core/theory.py --selftest
```

Voorbeeld leesbare output (richtlijn, exacte opmaak vrij):
```
BluesLab — F blues (jazz) · Bes klarinet (geschreven in G)

Schema (geschreven):
| G7    | C7    | G7    | Dm7 G7 |
| C7    | C#dim7| G7    | E7     |
| Am7   | D7    | G7 E7 | Am7 D7 |

Bluestoonladder (G): G  Bb  C  Db  D  F
```

---

## 8. Definition of Done

- [ ] `/home/bob/BluesLab/core/theory.py` bestaat; alleen stdlib + `argparse`.
- [ ] `python3 -c "import ast; ast.parse(open('core/theory.py').read()); print('OK')"` groen.
- [ ] `python3 core/theory.py --selftest` print `✅ selftest OK`, exit 0.
- [ ] CLI werkt voor minstens `Bb/F/C/G` × `basic/jazz` × beide instrumenten zonder crash.
- [ ] `get_blues` retourneert exact de structuur uit §3 voor alle drie de voices.
- [ ] Ongeldige `concert_key`/`form` geeft `ValueError` met NL-melding.
- [ ] `README.md` met de drie CLI-commando's uit §7.
- [ ] Geen netwerk/audio/backend-afhankelijkheden.

---

## 9. Daarna (niet nu bouwen)
BL-2 = play-along: hetzelfde 12-maats grid (we kennen het exact) → backing via MIDI/fluidsynth met count-in en click-grid. BL-1 levert het schema dat BL-2 hoorbaar maakt.
