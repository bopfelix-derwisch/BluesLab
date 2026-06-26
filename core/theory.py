#!/usr/bin/env python3
"""BluesLab — transponeer-engine (BL-1).

Pure-Python logica: levert per concert-toonsoort het 12-maats blues-schema,
de bluestoonladder en de akkoordtonen, getransponeerd naar de geschreven
notatie voor Bes klarinet (+2) en alt sax (+9). Alleen stdlib + argparse.

Interne representatie is ALTIJD concert pitch (pitch-class 0-11);
weergave wordt getransponeerd. Zie docs/BL-1-transponeer-engine.md.

STATUS: scaffold — projectstructuur staat, logica volgt (zie TODO's).
"""

import argparse
import sys

# --- 4.1 Pitch-classes ---------------------------------------------------
PITCH_CLASSES = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
    "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9,
    "A#": 10, "Bb": 10, "B": 11,
}

# --- 4.2 Voices (transpositie in halve tonen) ----------------------------
VOICES = {
    "concert": 0,
    "bb_clarinet": 2,   # geschreven = klinkend + 2
    "eb_alto_sax": 9,   # geschreven = klinkend + 9
}

FORMS = ("basic", "jazz")

# --- 5. Spelling (muziektheoretisch correct, letter-gebaseerd) -----------
# Een notnaam = letter + voorteken. We kennen elke schaal-/akkoordtoon de
# juiste *letter* toe voor zijn functie (terts op de tertsletter, b5 op de
# kwintletter, enz.); het voorteken volgt uit het pitch-class-verschil. Zo
# komen blue notes als mollen (Bb, Db) en niet als A#/C#, en krijgt elke
# diatonische ladder elke letter precies één keer.
LETTERS = ("C", "D", "E", "F", "G", "A", "B")
LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# Fallback-tabellen voor de zeldzame randgevallen die anders een dubbel
# voorteken zouden vragen (bv. b5 van Ab = Ebb); dan enharmonisch herspellen.
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Geschreven toonsoort-naam per pitch-class.
KEY_BY_PC = {
    0: "C", 1: "Db", 2: "D", 3: "Eb", 4: "E", 5: "F",
    6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B",
}
# Mol-toonsoorten (voor enharmonische fallback); de rest is een kruis-toonsoort.
FLAT_KEYS = {"C", "F", "Bb", "Eb", "Ab", "Db", "Gb"}

# --- 4.3 Bouwstenen als (halve-toon-offset, letter-offset) ---------------
# letter-offset = aantal letterstappen vanaf de root-letter (terts=2, kwint=4,
# septiem=6, ...). Zo valt elke trap op de muziektheoretisch juiste letter.
BLUES_SCALE = ((0, 0), (3, 2), (5, 3), (6, 4), (7, 4), (10, 6))   # 1 b3 4 b5 5 b7
MIXOLYDIAN = ((0, 0), (2, 1), (4, 2), (5, 3), (7, 4), (9, 5), (10, 6))
DORIAN = ((0, 0), (2, 1), (3, 2), (5, 3), (7, 4), (9, 5), (10, 6))
# hele-halve diminished (8 tonen in 7 letters: zesde letter komt dubbel voor).
DIM_SCALE = ((0, 0), (2, 1), (3, 2), (5, 3), (6, 4), (8, 5), (9, 5), (11, 6))

CHORD_TONES = {
    "dom7": ((0, 0), (4, 2), (7, 4), (10, 6)),   # 1 3 5 b7
    "min7": ((0, 0), (3, 2), (7, 4), (10, 6)),   # 1 b3 5 b7
    # dim7: de verminderde septiem op de zesde letter (lead-sheet-conventie,
    # bv. C°7 = C Eb Gb A) i.p.v. de strikte dubbelmol Bbb.
    "dim7": ((0, 0), (3, 2), (6, 4), (9, 5)),
}
CHORD_SCALE = {  # 4.3 aanbevolen toonladder per akkoord
    "dom7": MIXOLYDIAN,
    "min7": DORIAN,
    "dim7": DIM_SCALE,
}
CHORD_SUFFIX = {"dom7": "7", "min7": "m7", "dim7": "dim7"}  # 4.4

# Akkoord-root -> letterstappen vanaf de toonsoort-root (voor de naamgeving
# binnen de toonsoort): bv. #IV (graad 6) als verhoogde kwart -> kwartletter.
DEGREE_LETTER = {0: 0, 1: 0, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 10: 6, 11: 6}

# --- 4.5 Vormen (per maat: lijst van (graad-offset, quality)) ------------
BASIC_FORM = [
    [(0, "dom7")], [(5, "dom7")], [(0, "dom7")], [(0, "dom7")],
    [(5, "dom7")], [(5, "dom7")], [(0, "dom7")], [(0, "dom7")],
    [(7, "dom7")], [(5, "dom7")], [(0, "dom7")], [(7, "dom7")],
]
JAZZ_FORM = [
    [(0, "dom7")], [(5, "dom7")], [(0, "dom7")], [(7, "min7"), (0, "dom7")],
    [(5, "dom7")], [(6, "dim7")], [(0, "dom7")], [(9, "dom7")],
    [(2, "min7")], [(7, "dom7")], [(0, "dom7"), (9, "dom7")], [(2, "min7"), (7, "dom7")],
]
FORM_TABLE = {"basic": BASIC_FORM, "jazz": JAZZ_FORM}


def parse_key(name: str) -> int:
    """Concert-toonsoort-naam -> pitch-class (0-11). Case-insensitief.

    Raises ValueError (NL) bij een onbekende toonsoort.
    """
    if not name:
        raise ValueError("Geen toonsoort opgegeven.")
    norm = name[0].upper() + name[1:].lower()
    if norm not in PITCH_CLASSES:
        geldig = "C C# Db D D# Eb E F F# Gb G G# Ab A A# Bb B"
        raise ValueError(f"Onbekende toonsoort: {name!r}. Geldig: {geldig}.")
    return PITCH_CLASSES[norm]


def _acc(n: int) -> str:
    """Voortekens: -2..+2 -> 'bb','b','','#','##'."""
    return "b" * -n if n < 0 else "#" * n


def spell_note(pc: int, letter_idx: int, prefer_flats: bool) -> str:
    """Notnaam voor een pitch-class op een gekozen letter.

    Het voorteken volgt uit pc - letter-pitch-class (genormaliseerd naar
    -2..+2). Vraagt de spelling een dubbel voorteken, dan herspellen we
    enharmonisch met één voorteken volgens de toonsoort (mol/kruis).
    """
    pc %= 12
    letter = LETTERS[letter_idx % 7]
    delta = (pc - LETTER_PC[letter] + 6) % 12 - 6   # -6..+5
    if abs(delta) <= 1:
        return letter + _acc(delta)
    return (FLAT_NAMES if prefer_flats else SHARP_NAMES)[pc]


def _spell_from(root_pc: int, root_letter_idx: int, degrees, prefer_flats: bool):
    """Spel een schaal/akkoord: per (semitoon-offset, letter-offset)."""
    return [
        spell_note(root_pc + semi, root_letter_idx + loff, prefer_flats)
        for semi, loff in degrees
    ]


def written_key_pc(concert_key: str, voice: str) -> int:
    """Geschreven toonsoort-root als pitch-class voor een voice.

    geschreven = klinkend + transpositie (story §4.2).
    """
    if voice not in VOICES:
        raise ValueError(f"Onbekende voice: {voice!r}. Geldig: {', '.join(VOICES)}.")
    return (parse_key(concert_key) + VOICES[voice]) % 12


def _build_voice(concert_pc: int, transpose: int, form: str) -> dict:
    """Bouw de voice-structuur (§3) op de geschreven root."""
    root_pc = (concert_pc + transpose) % 12
    written_key = KEY_BY_PC[root_pc]
    prefer_flats = written_key in FLAT_KEYS
    key_letter_idx = LETTERS.index(written_key[0])

    def chord_root(degree: int):
        """(pitch-class, letter-index) van een akkoord-root binnen de toonsoort."""
        return (root_pc + degree) % 12, key_letter_idx + DEGREE_LETTER[degree]

    def chord_name(degree: int, quality: str) -> str:
        pc, letter_idx = chord_root(degree)
        return spell_note(pc, letter_idx, prefer_flats) + CHORD_SUFFIX[quality]

    bars = [
        [chord_name(degree, quality) for (degree, quality) in measure]
        for measure in FORM_TABLE[form]
    ]

    chords: dict = {}
    for measure in FORM_TABLE[form]:
        for degree, quality in measure:
            cname = chord_name(degree, quality)
            if cname in chords:
                continue
            r_pc, r_letter = chord_root(degree)
            chords[cname] = {
                "root": spell_note(r_pc, r_letter, prefer_flats),
                "quality": quality,
                "chord_tones": _spell_from(r_pc, r_letter, CHORD_TONES[quality], prefer_flats),
                "scale": _spell_from(r_pc, r_letter, CHORD_SCALE[quality], prefer_flats),
            }

    return {
        "transpose_semitones": transpose,
        "written_key": written_key,
        "bars": bars,
        "blues_scale": _spell_from(root_pc, key_letter_idx, BLUES_SCALE, prefer_flats),
        "chords": chords,
    }


def get_blues(concert_key: str, form: str = "basic") -> dict:
    """Hoofdfunctie — zie API-contract §3 in de story."""
    if form not in FORMS:
        raise ValueError(f"Onbekende vorm: {form!r}. Geldig: {', '.join(FORMS)}.")
    concert_pc = parse_key(concert_key)
    return {
        "concert_key": KEY_BY_PC[concert_pc],
        "form": form,
        "voices": {
            voice: _build_voice(concert_pc, transpose, form)
            for voice, transpose in VOICES.items()
        },
    }


def _selftest() -> int:
    # Asserts uit story §6 (docs/BL-1-transponeer-engine.md).
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
    assert get_blues("C", "basic")["voices"]["concert"]["blues_scale"] == \
        ["C", "Eb", "F", "Gb", "G", "Bb"]

    # jazz F klopt met template
    j = get_blues("F", "jazz")["voices"]["concert"]["bars"]
    assert j[3] == ["Cm7", "F7"] and j[11] == ["Gm7", "C7"] and j[5] == ["Bdim7"]

    # --- muziektheoretisch correcte spelling (letter-gebaseerd) -----------
    # Bluestoonladder gebruikt mollen voor de blue notes, óók in een
    # kruis-toonsoort: geschreven G (concert Bb op alt sax) -> G Bb C Db D F.
    assert get_blues("Bb", "basic")["voices"]["eb_alto_sax"]["blues_scale"] == \
        ["G", "Bb", "C", "Db", "D", "F"]
    # Akkoordtonen volgen de tertsen-stapeling: A7 = A C# E G (terts is C#,
    # geen Db), ook al staat het in een mol-toonsoort (concert C).
    aj = get_blues("C", "jazz")["voices"]["concert"]["chords"]
    assert aj["A7"]["chord_tones"] == ["A", "C#", "E", "G"]
    # En de bijbehorende mixolydische ladder krijgt elke letter één keer:
    assert aj["A7"]["scale"] == ["A", "B", "C#", "D", "E", "F#", "G"]
    # Mineurseptiem: Cm7 = C Eb G Bb (geen D# voor de terts).
    assert get_blues("F", "jazz")["voices"]["concert"]["chords"]["Cm7"]["chord_tones"] == \
        ["C", "Eb", "G", "Bb"]

    # alle 12 toonsoorten crashen niet
    for k in ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]:
        get_blues(k, "basic")
        get_blues(k, "jazz")

    print("✅ selftest OK")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="BluesLab transponeer-engine (BL-1)")
    p.add_argument("--key", help="concert-toonsoort, bv. Bb")
    p.add_argument("--form", choices=FORMS, default="basic")
    p.add_argument("--instrument", choices=tuple(VOICES), default="concert")
    p.add_argument("--selftest", action="store_true", help="harde asserts")
    args = p.parse_args(argv)

    if args.selftest:
        return _selftest()

    if not args.key:
        p.error("geef --key op (of gebruik --selftest)")
    try:
        data = get_blues(args.key, args.form)
    except ValueError as exc:
        print(f"Fout: {exc}", file=sys.stderr)
        return 2
    print(_render(data, args.instrument))
    return 0


INSTRUMENT_LABEL = {
    "concert": "concert",
    "bb_clarinet": "Bes klarinet",
    "eb_alto_sax": "alt sax (Eb)",
}


def _render(data: dict, instrument: str) -> str:
    """Leesbare NL-weergave van één voice (story §7)."""
    voice = data["voices"][instrument]
    label = INSTRUMENT_LABEL[instrument]
    lines = [
        f"BluesLab — {data['concert_key']} blues ({data['form']}) · "
        f"{label} (geschreven in {voice['written_key']})",
        "",
        "Schema (geschreven):",
    ]
    # 12 maten in 3 rijen van 4; kolombreedte op de langste maat.
    cells = [" ".join(measure) for measure in voice["bars"]]
    width = max(len(c) for c in cells)
    for row in range(0, 12, 4):
        cols = " | ".join(cells[i].ljust(width) for i in range(row, row + 4))
        lines.append(f"| {cols} |")
    lines.append("")
    lines.append(
        f"Bluestoonladder ({voice['written_key']}): "
        + "  ".join(voice["blues_scale"])
    )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
