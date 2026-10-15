"""BluesLab — akkoorden parsen, transponeren en akkoordtonen (BL-2).

Stdlib-only. Een akkoord is intern een dict in concert pitch:
    {"nc": False, "root_pc": 10, "root_letter": 6, "kwaliteit": "min",
     "extensie": "7", "bas_pc": 5, "bas_letter": 3, "tekst": "B♭m7/F"}
"N.C." (geen akkoord) wordt {"nc": True, "tekst": "N.C."}.

Transponeren gaat letter-gebaseerd: Bes klarinet = grote secunde omhoog
(+2 halve tonen, +1 letter), alt sax = grote sext omhoog (+9, +5 letters).
Zo wordt concert G♭ geschreven A♭ (klarinet) en E♭ (alt sax), nooit G#/D#.
"""

from core.theory import LETTERS, LETTER_PC, VOICES, spell_note

# Letterstappen per voice; hoort bij de halve tonen in theory.VOICES.
VOICE_LETTERS = {"concert": 0, "bb_clarinet": 1, "eb_alto_sax": 5}

_ACC = {"♭": -1, "b": -1, "♯": 1, "#": 1}

# (halve-toon-offset, letter-offset) per kwaliteit (drieklank).
TRIADS = {
    "maj": ((0, 0), (4, 2), (7, 4)),
    "min": ((0, 0), (3, 2), (7, 4)),
    "dim": ((0, 0), (3, 2), (6, 4)),
    "aug": ((0, 0), (4, 2), (8, 4)),
    "sus2": ((0, 0), (2, 1), (7, 4)),
    "sus4": ((0, 0), (5, 3), (7, 4)),
}
# Extra tonen per extensie.
EXTENSIONS = {
    "": (),
    "7": ((10, 6),),
    "maj7": ((11, 6),),
    "6": ((9, 5),),
    "9": ((10, 6), (14, 8)),
    "add9": ((14, 8),),
}
# dim + "7" = verminderd septiemakkoord, lead-sheet-spelling op de zesde
# letter (C°7 = C Eb Gb A), zoals theory.CHORD_TONES["dim7"].
DIM7 = ((9, 5),)
# Extensies waarvan de vierde toon een gidstoon is (septiem/sext).
GUIDE_EXTENSIONS = {"7", "maj7", "6", "9"}

NC_TEXTS = {"N.C.", "N.C", "NC"}


def _parse_note(s: str):
    """'B♭m7' -> (pc, letter_idx, rest). Hoofdletter A-G + max. één voorteken."""
    if not s or s[0] not in LETTER_PC:
        raise ValueError(f"Geen grondtoon in {s!r}.")
    letter = s[0]
    acc = 0
    rest = s[1:]
    if rest and rest[0] in _ACC:
        acc = _ACC[rest[0]]
        rest = rest[1:]
    return (LETTER_PC[letter] + acc) % 12, LETTERS.index(letter), rest


def _parse_suffix(s: str):
    """Achtervoegsel -> (kwaliteit, extensie). ValueError bij iets onbekends."""
    origineel = s
    kwaliteit = "maj"
    for tok, val in (("min", "min"), ("dim", "dim"), ("aug", "aug"),
                     ("°", "dim"), ("+", "aug"), ("-", "min")):
        if s.startswith(tok):
            kwaliteit, s = val, s[len(tok):]
            break
    else:
        if s.startswith("m") and not s.startswith("maj"):
            kwaliteit, s = "min", s[1:]
    extensie = ""
    for tok, val in (("maj7", "maj7"), ("M7", "maj7"), ("add9", "add9"),
                     ("7", "7"), ("6", "6"), ("9", "9")):
        if s.startswith(tok):
            extensie, s = val, s[len(tok):]
            break
    for tok, val in (("sus2", "sus2"), ("sus4", "sus4"), ("sus", "sus4")):
        if s.startswith(tok):
            if kwaliteit != "maj":
                raise ValueError(f"Onbekend akkoord-achtervoegsel: {origineel!r}.")
            kwaliteit, s = val, s[len(tok):]
            break
    if s:
        raise ValueError(f"Onbekend akkoord-achtervoegsel: {origineel!r}.")
    return kwaliteit, extensie


def parse_chord(text: str) -> dict:
    """Akkoordnaam (concert) -> akkoord-dict. ValueError (NL) als het niet lukt."""
    t = text.strip()
    if t.replace(" ", "").upper() in NC_TEXTS:
        return {"nc": True, "tekst": t}
    hoofd, slash, bas = t.partition("/")
    root_pc, root_letter, rest = _parse_note(hoofd)
    kwaliteit, extensie = _parse_suffix(rest)
    bas_pc = bas_letter = None
    if slash:
        bas_pc, bas_letter, bas_rest = _parse_note(bas)
        if bas_rest:
            raise ValueError(f"Onbekende bastoon in {t!r}.")
    return {
        "nc": False, "root_pc": root_pc, "root_letter": root_letter,
        "kwaliteit": kwaliteit, "extensie": extensie,
        "bas_pc": bas_pc, "bas_letter": bas_letter, "tekst": t,
    }


def _check_voice(voice: str) -> None:
    if voice not in VOICES:
        raise ValueError(f"Onbekende voice: {voice!r}. Geldig: {', '.join(VOICES)}.")


def transpose_note(pc: int, letter: int, voice: str):
    """(pc, letter) concert -> (pc, letter) geschreven voor een voice."""
    _check_voice(voice)
    return (pc + VOICES[voice]) % 12, (letter + VOICE_LETTERS[voice]) % 7


def note_name(pc: int, letter: int) -> str:
    """Notnaam op een gekozen letter; dubbele voortekens -> mol-spelling."""
    return spell_note(pc, letter, prefer_flats=True)


def _suffix(kwaliteit: str, extensie: str) -> str:
    if kwaliteit in ("sus2", "sus4"):
        return extensie + kwaliteit
    return {"maj": "", "min": "m", "dim": "dim", "aug": "aug"}[kwaliteit] + extensie


def transpose_chord(chord: dict, voice: str) -> str:
    """Akkoord-dict -> geschreven akkoordnaam (ASCII: 'b' en '#')."""
    _check_voice(voice)
    if chord["nc"]:
        return "N.C."
    naam = note_name(*transpose_note(chord["root_pc"], chord["root_letter"], voice))
    naam += _suffix(chord["kwaliteit"], chord["extensie"])
    if chord["bas_pc"] is not None:
        naam += "/" + note_name(*transpose_note(chord["bas_pc"], chord["bas_letter"], voice))
    return naam


def _intervals(chord: dict):
    if chord["kwaliteit"] == "dim" and chord["extensie"] == "7":
        return TRIADS["dim"] + DIM7
    return TRIADS[chord["kwaliteit"]] + EXTENSIONS[chord["extensie"]]


def chord_pcs(chord: dict) -> list:
    """Concert pitch-classes van het akkoord (grondtoon eerst); [] bij N.C."""
    if chord["nc"]:
        return []
    return [(chord["root_pc"] + semi) % 12 for semi, _ in _intervals(chord)]


def chord_tones(chord: dict, voice: str) -> list:
    """Geschreven akkoordtonen: grondtoon, terts, kwint, (septiem/sext/noon)."""
    if chord["nc"]:
        return []
    pc, letter = transpose_note(chord["root_pc"], chord["root_letter"], voice)
    return [note_name(pc + semi, letter + loff) for semi, loff in _intervals(chord)]


def guide_tones(chord: dict) -> list:
    """Concert pitch-classes van de gidstonen: terts (of sus-toon), plus septiem/sext."""
    if chord["nc"]:
        return []
    pcs = chord_pcs(chord)
    gids = [pcs[1]]
    if chord["extensie"] in GUIDE_EXTENSIONS:
        gids.append(pcs[3])
    return gids


def guide_tone_name(pc: int, chord: dict, voice: str) -> str:
    """Geschreven naam van een gidstoon (pc concert) binnen dit akkoord."""
    root_pc, root_letter = chord["root_pc"], chord["root_letter"]
    for semi, loff in _intervals(chord):
        if (root_pc + semi) % 12 == pc:
            wpc, wletter = transpose_note(pc, root_letter + loff, voice)
            return note_name(wpc, wletter)
    raise ValueError(f"Toon {pc} hoort niet bij {chord['tekst']!r}.")
