import pytest

from core.analysis import (
    bar_guide, check_bar_count, check_sections, detect_sections, flatten,
    key_for_section, parse_key, scale_names, speelschema, written_key_name,
)

# Regelstarts van tests/fixtures/chordify-crazy.pdf.
CRAZY_STARTS = [1, 10, 20, 29, 39, 49, 58, 67]
CRAZY_LOOP = ["Bbm", "Gb", "Db", "Ab"]


def _regels(starts, laatste_lengte):
    regels = []
    for i, start in enumerate(starts):
        lengte = starts[i + 1] - start if i + 1 < len(starts) else laatste_lengte
        regels.append({"start_maat": start,
                       "maten": [[CRAZY_LOOP[(start - 1 + j) % 4]] for j in range(lengte)]})
    return regels


def test_check_bar_count_crazy_ok():
    uit = check_bar_count(_regels(CRAZY_STARTS, 9))
    assert [r["start_maat"] for r in uit] == CRAZY_STARTS
    assert all(r["ok"] for r in uit)
    assert uit[0] == {"start_maat": 1, "verwacht": 9, "gevonden": 9, "ok": True}
    assert uit[-1]["verwacht"] is None


def test_check_bar_count_flags_missing_bar():
    regels = _regels(CRAZY_STARTS, 9)
    regels[2]["maten"].pop()           # regel die bij maat 20 begint mist er één
    uit = check_bar_count(regels)
    assert [r["ok"] for r in uit] == [True, True, False, True, True, True, True, True]
    assert (uit[2]["verwacht"], uit[2]["gevonden"]) == (9, 8)


def test_flatten():
    assert flatten([{"start_maat": 1, "maten": [["A"], ["B", "C"]]},
                    {"start_maat": 3, "maten": [["D"]]}]) == [["A"], ["B", "C"], ["D"]]


COUPLET = [["Am"], ["F"], ["Am"], ["F"]]
REFREIN = [["C"], ["G"], ["D"], ["Am"], ["F"]]


def test_detect_sections_repeats():
    maten = COUPLET + [["C"], ["G"], ["D"], ["Am"]] + COUPLET
    assert detect_sections(maten) == [
        {"naam": "Deel A", "start_maat": 1, "eind_maat": 4},
        {"naam": "Deel B", "start_maat": 5, "eind_maat": 8},
        {"naam": "Deel A", "start_maat": 9, "eind_maat": 12},
    ]


def test_detect_sections_merges_and_handles_tail():
    maten = COUPLET + COUPLET + [["C"]]
    assert detect_sections(maten) == [
        {"naam": "Deel A", "start_maat": 1, "eind_maat": 8},
        {"naam": "Deel B", "start_maat": 9, "eind_maat": 9},
    ]


def test_check_sections_ok_and_problems():
    goed = [{"naam": "Intro", "start_maat": 1, "eind_maat": 4},
            {"naam": "Couplet", "start_maat": 5, "eind_maat": 12}]
    assert check_sections(goed, 12) == []
    gat = [{"naam": "Intro", "start_maat": 1, "eind_maat": 4},
           {"naam": "Couplet", "start_maat": 6, "eind_maat": 12}]
    assert check_sections(gat, 12) == ["Couplet begint in maat 6, verwacht maat 5."]
    kort = [{"naam": "Intro", "start_maat": 1, "eind_maat": 10}]
    assert check_sections(kort, 12) == [
        "Het laatste deel eindigt in maat 10, het nummer heeft 12 maten."]
    assert check_sections([], 12) == ["Er zijn geen delen."]


def test_key_for_section_crazy_is_bbm():
    maten = [[c] for c in CRAZY_LOOP * 4] + [["Bbm"], ["N.C."]]
    assert key_for_section(maten, -5) == {"naam": "Bbm", "tonic_pc": 10, "mode": "min"}


def test_key_for_section_californication_like_two_keys():
    assert key_for_section(COUPLET * 2, 0)["naam"] == "Am"
    assert key_for_section(REFREIN * 2, 0)["naam"] == "C"


def test_key_for_section_ignores_unparseable():
    assert key_for_section([["Am"], ["???"], ["F"], ["Am"]], 0)["naam"] == "Am"


def test_key_for_section_no_chords():
    with pytest.raises(ValueError):
        key_for_section([["N.C."]], 0)


def test_parse_key():
    assert parse_key("B♭m") == {"naam": "Bbm", "tonic_pc": 10, "mode": "min"}
    assert parse_key("Db") == {"naam": "Db", "tonic_pc": 1, "mode": "maj"}
    for fout in ("Bb7", "C/E", "N.C.", "x"):
        with pytest.raises(ValueError):
            parse_key(fout)


def test_written_key_and_scale():
    bbm = parse_key("Bbm")
    assert written_key_name(bbm, "bb_clarinet") == "Cm"
    assert written_key_name(bbm, "eb_alto_sax") == "Gm"
    assert written_key_name(parse_key("Gm"), "bb_clarinet") == "Am"
    assert written_key_name(parse_key("Gm"), "eb_alto_sax") == "Em"
    assert scale_names(bbm, "bb_clarinet") == ["C", "D", "Eb", "F", "G", "Ab", "Bb"]
    assert scale_names(parse_key("Db"), "eb_alto_sax") == ["Bb", "C", "D", "Eb", "F", "G", "A"]


def test_bar_guide_voice_leading():
    # C7 -> F7: gidstonen C7 = E/Bb, F7 = A/Eb. Na Bb (10) is A (9) dichterbij dan Eb (3).
    eerste = bar_guide(1, ["C7"], "concert")
    assert eerste["doeltoon"] == "E"                 # zonder vorige: de terts
    tweede = bar_guide(2, ["F7"], "concert", vorige_doel_pc=10)
    assert tweede["doeltoon"] == "A"
    assert tweede["akkoorden"] == [{"concert": "F7", "geschreven": "F7",
                                    "tonen": ["F", "A", "C", "Eb"], "fout": None}]


def test_bar_guide_written_and_flags_unparseable():
    gids = bar_guide(7, ["B♭m", "Hx"], "bb_clarinet")
    assert gids["nr"] == 7
    assert gids["akkoorden"][0]["geschreven"] == "Cm"
    assert gids["doeltoon"] == "Eb"
    assert gids["akkoorden"][1]["geschreven"] is None
    assert gids["akkoorden"][1]["fout"]


def test_bar_guide_no_chord():
    gids = bar_guide(3, ["N.C."], "bb_clarinet")
    assert gids["doeltoon"] is None
    assert gids["akkoorden"][0]["geschreven"] == "N.C."


def test_speelschema_marks_key_change():
    maten = COUPLET + REFREIN
    delen = [{"naam": "Couplet", "start_maat": 1, "eind_maat": 4, "concert_key": "Am"},
             {"naam": "Refrein", "start_maat": 5, "eind_maat": 9, "concert_key": "C"}]
    schema = speelschema(maten, delen, "bb_clarinet")
    assert [d["geschreven_key"] for d in schema] == ["Bm", "D"]
    assert [d["wissel"] for d in schema] == [False, True]
    assert [m["nr"] for m in schema[1]["maten"]] == [5, 6, 7, 8, 9]
    assert schema[0]["maten"][0]["akkoorden"][0]["geschreven"] == "Bm"
    assert schema[0]["toonladder"] == ["B", "C#", "D", "E", "F#", "G", "A"]
