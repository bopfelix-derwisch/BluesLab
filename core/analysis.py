"""BluesLab — analyse van een akkoordschema (BL-2).

Stdlib-only. Maten zijn altijd concert pitch: list[list[str]] (1..n akkoorden
per maat). Een toonsoort is een dict {"naam": "Bbm", "tonic_pc": 10, "mode": "min"}.
"""

from core.chords import (
    chord_pcs, chord_tones, guide_tone_name, guide_tones, note_name,
    parse_chord, transpose_chord, transpose_note,
)

MAJOR_SCALE = ((0, 0), (2, 1), (4, 2), (5, 3), (7, 4), (9, 5), (11, 6))
MINOR_SCALE = ((0, 0), (2, 1), (3, 2), (5, 3), (7, 4), (8, 5), (10, 6))

MAJOR_NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
MINOR_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]

# Gewichten voor key_for_section (zie docstring).
TONIC_WEIGHT = 2.0
FIRST_WEIGHT = 1.5
LAST_WEIGHT = 1.0
PRIOR_WEIGHT = 1.0

LETTERS_AZ = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# --- maattelling -----------------------------------------------------------
def check_bar_count(regels: list) -> list:
    """Per regel: klopt het aantal maten met de start van de volgende regel?

    regels = [{"start_maat": int, "maten": [[str, ...], ...]}, ...]
    Geeft per regel {"start_maat", "verwacht" (int|None), "gevonden", "ok"}.
    De laatste regel heeft geen volgende start: verwacht = None, ok = True.
    """
    uit = []
    for i, regel in enumerate(regels):
        gevonden = len(regel["maten"])
        verwacht = None
        if i + 1 < len(regels):
            verwacht = regels[i + 1]["start_maat"] - regel["start_maat"]
        uit.append({
            "start_maat": regel["start_maat"],
            "verwacht": verwacht,
            "gevonden": gevonden,
            "ok": verwacht is None or verwacht == gevonden,
        })
    return uit


def flatten(regels: list) -> list:
    """Regels -> doorlopende maatlijst (maat 1 = index 0)."""
    return [list(maat) for regel in regels for maat in regel["maten"]]


# --- delen -----------------------------------------------------------------
def detect_sections(maten: list, blok: int = 4) -> list:
    """Kandidaat-delen op basis van herhaalde blokken van `blok` maten.

    Gelijke blokken krijgen dezelfde letter; opeenvolgende blokken met dezelfde
    letter worden samengevoegd. Fallback als Claude-aanroep 2 faalt.
    Geeft [{"naam": "Deel A", "start_maat", "eind_maat"}].
    """
    gezien: dict = {}
    delen: list = []
    for i in range(0, len(maten), blok):
        sleutel = tuple(tuple(m) for m in maten[i:i + blok])
        if sleutel not in gezien:
            gezien[sleutel] = LETTERS_AZ[len(gezien) % 26]
        naam = "Deel " + gezien[sleutel]
        eind = min(i + blok, len(maten))
        if delen and delen[-1]["naam"] == naam:
            delen[-1]["eind_maat"] = eind
        else:
            delen.append({"naam": naam, "start_maat": i + 1, "eind_maat": eind})
    return delen


def check_sections(delen: list, aantal_maten: int) -> list:
    """Sluiten de delen op elkaar aan en dekken ze maat 1..aantal_maten? -> NL-problemen."""
    problemen = []
    if not delen:
        return ["Er zijn geen delen."]
    verwacht = 1
    for deel in delen:
        if deel["start_maat"] != verwacht:
            problemen.append(
                f"{deel['naam']} begint in maat {deel['start_maat']}, verwacht maat {verwacht}.")
        if deel["eind_maat"] < deel["start_maat"]:
            problemen.append(f"{deel['naam']} eindigt vóór het begint.")
        verwacht = deel["eind_maat"] + 1
    if delen[-1]["eind_maat"] != aantal_maten:
        problemen.append(
            f"Het laatste deel eindigt in maat {delen[-1]['eind_maat']}, "
            f"het nummer heeft {aantal_maten} maten.")
    return problemen


# --- toonsoort -------------------------------------------------------------
def key_dict(tonic_pc: int, mode: str, voortekening: int = 0) -> dict:
    """Toonsoort-dict met een naam; voortekening (<0 = mollen) kiest tussen F#/Gb en D#m/Ebm."""
    if mode == "maj":
        naam = MAJOR_NAMES[tonic_pc]
        if tonic_pc == 6 and voortekening < 0:
            naam = "Gb"
    else:
        naam = MINOR_NAMES[tonic_pc] + "m"
        if tonic_pc == 3 and voortekening > 0:
            naam = "D#m"
    return {"naam": naam, "tonic_pc": tonic_pc, "mode": mode}


def parse_key(naam: str) -> dict:
    """'Bbm' / 'B♭m' / 'Db' -> toonsoort-dict. ValueError (NL) als het geen toonsoort is."""
    akkoord = parse_chord(naam)
    if akkoord["nc"] or akkoord["kwaliteit"] not in ("maj", "min") \
            or akkoord["extensie"] or akkoord["bas_pc"] is not None:
        raise ValueError(f"Geen toonsoort: {naam!r} (verwacht bv. 'Bbm' of 'Db').")
    mode = akkoord["kwaliteit"]
    return {
        "naam": transpose_chord(akkoord, "concert"),
        "tonic_pc": akkoord["root_pc"],
        "mode": mode,
    }


def same_key(a: dict, b: dict) -> bool:
    return a["tonic_pc"] == b["tonic_pc"] and a["mode"] == b["mode"]


def _scale_pcs(tonic_pc: int, mode: str) -> set:
    schaal = MAJOR_SCALE if mode == "maj" else MINOR_SCALE
    return {(tonic_pc + semi) % 12 for semi, _ in schaal}


def _signature_keys(voortekening: int) -> set:
    """(tonic_pc, mode) van de majeur- en mineurtoonsoort bij een voortekening."""
    majeur = (voortekening * 7) % 12
    return {(majeur, "maj"), ((majeur + 9) % 12, "min")}


def key_for_section(maten: list, voortekening: int = 0) -> dict:
    """Waarschijnlijkste toonsoort voor een reeks maten (concert).

    Score per kandidaat (12 majeur + 12 mineur):
      Σ per akkoord (in − 2·uit) / aantal tonen   (diatonische fit)
      + TONIC_WEIGHT per tonica-akkoord, + FIRST_WEIGHT als het eerste akkoord
      de tonica is, + LAST_WEIGHT voor het laatste, + PRIOR_WEIGHT als de
      voortekening (aantal kruizen, negatief = mollen) bij de toonsoort hoort.
    N.C. en onparseerbare akkoorden tellen niet mee.
    """
    akkoorden = []
    for maat in maten:
        for tekst in maat:
            try:
                a = parse_chord(tekst)
            except ValueError:
                continue
            if not a["nc"]:
                akkoorden.append(a)
    if not akkoorden:
        raise ValueError("Geen akkoorden om een toonsoort uit af te leiden.")
    prior = _signature_keys(voortekening)

    def is_tonica(a, tonic_pc, mode):
        return a["root_pc"] == tonic_pc and a["kwaliteit"] == mode

    beste, beste_score = None, None
    for mode in ("maj", "min"):
        for tonic_pc in range(12):
            schaal = _scale_pcs(tonic_pc, mode)
            score = 0.0
            for a in akkoorden:
                pcs = chord_pcs(a)
                binnen = sum(1 for pc in pcs if pc in schaal)
                score += (binnen - 2 * (len(pcs) - binnen)) / len(pcs)
                if is_tonica(a, tonic_pc, mode):
                    score += TONIC_WEIGHT
            if is_tonica(akkoorden[0], tonic_pc, mode):
                score += FIRST_WEIGHT
            if is_tonica(akkoorden[-1], tonic_pc, mode):
                score += LAST_WEIGHT
            if (tonic_pc, mode) in prior:
                score += PRIOR_WEIGHT
            if beste_score is None or score > beste_score:
                beste, beste_score = (tonic_pc, mode), score
    return key_dict(beste[0], beste[1], voortekening)


def written_key_name(key: dict, voice: str) -> str:
    """Geschreven toonsoortnaam, bv. Bbm -> Cm (klarinet), Gm (alt sax)."""
    return transpose_chord(parse_chord(key["naam"]), voice)


def scale_names(key: dict, voice: str) -> list:
    """Geschreven toonladder (majeur of natuurlijk mineur) van een toonsoort."""
    tonica = parse_chord(key["naam"])
    pc, letter = transpose_note(tonica["root_pc"], tonica["root_letter"], voice)
    schaal = MAJOR_SCALE if key["mode"] == "maj" else MINOR_SCALE
    return [note_name(pc + semi, letter + loff) for semi, loff in schaal]


# --- speelschema -----------------------------------------------------------
def _afstand(a: int, b: int) -> int:
    d = (a - b) % 12
    return min(d, 12 - d)


def bar_guide(nr: int, maat: list, voice: str, vorige_doel_pc=None) -> dict:
    """Eén maat voor het speelschema.

    Doeltoon = gidstoon (terts, of septiem/sext) van het eerste akkoord; met
    `vorige_doel_pc` (concert) kiezen we de gidstoon die daar het dichtst bij
    ligt (stemvoering). Bij gelijke afstand wint de terts.
    Geeft {"nr", "akkoorden": [{"concert", "geschreven", "tonen", "fout"}],
           "doeltoon" (str|None), "doel_pc" (int|None, concert)}.
    """
    akkoorden = []
    eerste = None
    for tekst in maat:
        try:
            a = parse_chord(tekst)
        except ValueError as exc:
            akkoorden.append({"concert": tekst, "geschreven": None, "tonen": [],
                              "fout": str(exc)})
            continue
        akkoorden.append({"concert": tekst, "geschreven": transpose_chord(a, voice),
                          "tonen": chord_tones(a, voice), "fout": None})
        if eerste is None and not a["nc"]:
            eerste = a
    doeltoon = doel_pc = None
    if eerste is not None:
        kandidaten = guide_tones(eerste)
        doel_pc = kandidaten[0]
        if vorige_doel_pc is not None:
            doel_pc = min(kandidaten, key=lambda pc: _afstand(pc, vorige_doel_pc))
        doeltoon = guide_tone_name(doel_pc, eerste, voice)
    return {"nr": nr, "akkoorden": akkoorden, "doeltoon": doeltoon, "doel_pc": doel_pc}


def speelschema(maten: list, delen: list, voice: str) -> list:
    """Volledig speelschema per deel.

    delen = [{"naam", "start_maat", "eind_maat", "concert_key"}] (concert_key = naam, bv. "Bbm").
    Geeft per deel {"naam", "start_maat", "eind_maat", "concert_key",
    "geschreven_key", "toonladder", "wissel", "maten": [bar_guide(...)]}.
    "wissel" = True als de toonsoort anders is dan die van het vorige deel.
    """
    uit = []
    vorige_key = None
    vorige_doel = None
    for deel in delen:
        key = parse_key(deel["concert_key"])
        regels = []
        for nr in range(deel["start_maat"], deel["eind_maat"] + 1):
            gids = bar_guide(nr, maten[nr - 1], voice, vorige_doel)
            if gids["doel_pc"] is not None:
                vorige_doel = gids["doel_pc"]
            regels.append(gids)
        uit.append({
            "naam": deel["naam"],
            "start_maat": deel["start_maat"],
            "eind_maat": deel["eind_maat"],
            "concert_key": key["naam"],
            "geschreven_key": written_key_name(key, voice),
            "toonladder": scale_names(key, voice),
            "wissel": vorige_key is not None and not same_key(key, vorige_key),
            "maten": regels,
        })
        vorige_key = key
    return uit
