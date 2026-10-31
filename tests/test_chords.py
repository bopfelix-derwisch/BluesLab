import re

import pytest

from core.chords import (
    chord_tones, fill_names, guide_tones, parse_chord, parse_fill, transpose_chord,
)


@pytest.mark.parametrize("tekst, root_pc, kwaliteit, extensie", [
    ("B♭m", 10, "min", ""),
    ("Bbm", 10, "min", ""),
    ("G♭", 6, "maj", ""),
    ("F#m7", 6, "min", "7"),
    ("C♯dim", 1, "dim", ""),
    ("A°7", 9, "dim", "7"),
    ("Cmaj7", 0, "maj", "maj7"),
    ("CM7", 0, "maj", "maj7"),
    ("Dmin", 2, "min", ""),
    ("D-7", 2, "min", "7"),
    ("E+", 4, "aug", ""),
    ("Eaug", 4, "aug", ""),
    ("A♭sus4", 8, "sus4", ""),
    ("G7sus4", 7, "sus4", "7"),
    ("Dsus2", 2, "sus2", ""),
    ("C6", 0, "maj", "6"),
    ("Am9", 9, "min", "9"),
    ("Fadd9", 5, "maj", "add9"),
])
def test_parse_chord(tekst, root_pc, kwaliteit, extensie):
    a = parse_chord(tekst)
    assert (a["nc"], a["root_pc"], a["kwaliteit"], a["extensie"]) == \
        (False, root_pc, kwaliteit, extensie)
    assert a["tekst"] == tekst


def test_parse_slash_chord():
    a = parse_chord("B♭m7/F")
    assert (a["root_pc"], a["kwaliteit"], a["extensie"], a["bas_pc"]) == (10, "min", "7", 5)


@pytest.mark.parametrize("tekst", ["N.C.", "NC", "n.c."])
def test_parse_no_chord(tekst):
    assert parse_chord(tekst)["nc"] is True


@pytest.mark.parametrize("tekst", ["", "H7", "Bbm7b5x", "C/Q", "bbm", "Cmsus4"])
def test_parse_chord_rejects(tekst):
    with pytest.raises(ValueError):
        parse_chord(tekst)


@pytest.mark.parametrize("concert, klarinet, altsax", [
    ("B♭m", "Cm", "Gm"),
    ("Gm", "Am", "Em"),
    ("G♭", "Ab", "Eb"),
    ("D♭", "Eb", "Bb"),
    ("A♭", "Bb", "F"),
    ("A♭sus4", "Bbsus4", "Fsus4"),
    ("E♭m", "Fm", "Cm"),
    ("Fm", "Gm", "Dm"),
    ("B♭m7/F", "Cm7/G", "Gm7/D"),
    ("F#7", "G#7", "D#7"),
    ("N.C.", "N.C.", "N.C."),
])
def test_transpose_chord(concert, klarinet, altsax):
    a = parse_chord(concert)
    assert transpose_chord(a, "bb_clarinet") == klarinet
    assert transpose_chord(a, "eb_alto_sax") == altsax


def test_transpose_chord_concert_is_ascii_name():
    assert transpose_chord(parse_chord("B♭m7"), "concert") == "Bbm7"


def test_transpose_chord_unknown_voice():
    with pytest.raises(ValueError):
        transpose_chord(parse_chord("C"), "tuba")


def test_chord_tones_written():
    assert chord_tones(parse_chord("B♭m"), "concert") == ["Bb", "Db", "F"]
    assert chord_tones(parse_chord("B♭m"), "bb_clarinet") == ["C", "Eb", "G"]
    assert chord_tones(parse_chord("B♭m"), "eb_alto_sax") == ["G", "Bb", "D"]
    assert chord_tones(parse_chord("A7"), "concert") == ["A", "C#", "E", "G"]
    assert chord_tones(parse_chord("A♭sus4"), "concert") == ["Ab", "Db", "Eb"]
    assert chord_tones(parse_chord("C°7"), "concert") == ["C", "Eb", "Gb", "A"]
    assert chord_tones(parse_chord("N.C."), "concert") == []


def test_guide_tones():
    assert guide_tones(parse_chord("C7")) == [4, 10]   # E, Bb
    assert guide_tones(parse_chord("Am")) == [0]       # C
    assert guide_tones(parse_chord("Fadd9")) == [9]    # A (noon is geen gidstoon)


# --- fills ---------------------------------------------------------------

def test_parse_fill_klarinet_naar_concert():
    assert parse_fill("E F E", "bb_clarinet") == [[2, 1], [3, 2], [2, 1]]  # concert D Eb D


def test_parse_fill_alt_naar_concert():
    assert parse_fill("B C B", "eb_alto_sax") == [[2, 1], [3, 2], [2, 1]]


def test_parse_fill_scheidingstekens_en_kleine_letters():
    assert parse_fill(" e–f - e, d ", "bb_clarinet") == [[2, 1], [3, 2], [2, 1], [0, 0]]


def test_parse_fill_voortekens():
    assert parse_fill("D# D♯ bb B♭ eb", "concert") == [[3, 1], [3, 1], [10, 6], [10, 6], [3, 2]]


def test_parse_fill_leeg():
    assert parse_fill("", "bb_clarinet") == []
    assert parse_fill("  - , ", "bb_clarinet") == []


@pytest.mark.parametrize("tekst, fout", [
    ("D H", "Onbekende noot: 'H'."),
    ("Dm", "Onbekende noot: 'Dm'."),
    ("D##", "Onbekende noot: 'D##'."),
])
def test_parse_fill_foute_noot(tekst, fout):
    with pytest.raises(ValueError, match=re.escape(fout)):
        parse_fill(tekst, "bb_clarinet")


def test_parse_fill_max_32():
    assert len(parse_fill(" ".join(["C"] * 32), "concert")) == 32
    with pytest.raises(ValueError, match=re.escape("Te veel noten (max. 32).")):
        parse_fill(" ".join(["C"] * 33), "concert")


def test_fill_names_geschreven():
    noten = [[2, 1], [3, 2], [2, 1]]  # concert D Eb D
    assert fill_names(noten, "bb_clarinet") == ["E", "F", "E"]
    assert fill_names(noten, "eb_alto_sax") == ["B", "C", "B"]


def test_fill_heen_en_terug_houdt_spelling():
    for voice in ("bb_clarinet", "eb_alto_sax"):
        assert fill_names(parse_fill("D D# E Gb", voice), voice) == ["D", "D#", "E", "Gb"]
    assert fill_names(parse_fill("D#", "bb_clarinet"), "eb_alto_sax") == ["A#"]  # nooit Bb
