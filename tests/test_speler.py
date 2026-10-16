"""Meespeel-begeleiding: pure functies uit web/speler.js, gedraaid met node."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

EVAL = Path(__file__).parent / "web_eval.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node ontbreekt")


def js(expressie):
    uit = subprocess.run(["node", str(EVAL), expressie],
                         capture_output=True, text=True, check=True, timeout=20)
    return json.loads(uit.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("tekst, bas, akkoord", [
    ("C", 36, [60, 64, 67]),
    ("E", 40, [52, 56, 59]),
    ("Bbm7/F", 41, [58, 61, 65, 68]),
    ("B♭m7/F", 41, [58, 61, 65, 68]),
    ("Gsus4", 43, [55, 60, 62]),
    ("G7sus4", 43, [55, 60, 62, 65]),
    ("A°7", 45, [57, 60, 63, 66]),
    ("Am9", 45, [57, 60, 64, 67, 71]),
    ("F#m", 42, [54, 57, 61]),
    ("Cmaj7", 36, [60, 64, 67, 71]),
])
def test_akkoord_midi(tekst, bas, akkoord):
    r = js(f"akkoordMidi({json.dumps(tekst)})")
    assert {k: r[k] for k in ("nc", "bas", "akkoord")} == {"nc": False, "bas": bas, "akkoord": akkoord}


@pytest.mark.parametrize("tekst, grond, kwint, slash", [
    ("G7", 43, 7, False), ("Bdim", 47, 6, False), ("Caug", 36, 8, False),
    ("Gsus4", 43, 7, False), ("Bbm7/F", 46, 7, True)])
def test_akkoord_midi_grond_kwint_slash(tekst, grond, kwint, slash):
    r = js(f"akkoordMidi({json.dumps(tekst)})")
    assert (r["grond"], r["kwint"], r["slash"]) == (grond, kwint, slash)


@pytest.mark.parametrize("tekst", ["N.C.", "NC", "n.c."])
def test_akkoord_midi_nc(tekst):
    assert js(f"akkoordMidi({json.dumps(tekst)})") == {"nc": True}


@pytest.mark.parametrize("tekst", ["Hm", "Cxyz", "C/Xb", "C/Fm", "Cmsus4", "", "  "])
def test_akkoord_midi_onleesbaar(tekst):
    assert js(f"akkoordMidi({json.dumps(tekst)})") is None


@pytest.mark.parametrize("maatsoort, tellen", [
    ("4/4", 4), ("3/4", 3), ("2/2", 2), ("6/8", 6), ("", 4), (None, 4), ("x", 4), ("0/4", 4)])
def test_tellen_uit(maatsoort, tellen):
    assert js(f"tellenUit({json.dumps(maatsoort)})") == tellen


def _maten(*akkoorden, eerste=1):
    return [{"nr": eerste + i, "akkoorden": [{"concert": a} for a in m.split()]}
            for i, m in enumerate(akkoorden)]


def plan(maten, opties):
    """[ms, soort, midi, maat] per gebeurtenis, plus de duur in ms."""
    r = js(f"(p => ({{g: p.gebeurtenissen.map(e => [Math.round(e.t * 1000), e.soort, e.midi, e.maat]),"
           f" duur: Math.round(p.duur * 1000)}}))(speelplan({json.dumps(maten)}, {json.dumps(opties)}))")
    return r["g"], r["duur"]


def test_speelplan_inteltel_en_basritme():
    g, duur = plan(_maten("C"), {"bpm": 120})
    assert g == [
        [0, "tik", [], None], [500, "tik", [], None], [1000, "tik", [], None], [1500, "tik", [], None],
        [2000, "tik", [], 1], [2000, "bas", [36], 1],
        [2500, "tik", [], 1], [2500, "akkoord", [60, 64, 67], 1],
        [3000, "tik", [], 1], [3000, "bas", [36], 1],
        [3500, "tik", [], 1], [3500, "akkoord", [60, 64, 67], 1]]
    assert duur == 4000


def test_speelplan_twee_akkoorden_elk_halve_maat():
    g, _ = plan(_maten("C G"), {"bpm": 120, "inteltel": 0})
    assert [x for x in g if x[1] != "tik"] == [
        [0, "bas", [36], 1], [500, "akkoord", [60, 64, 67], 1],
        [1000, "bas", [43], 1], [1500, "akkoord", [55, 59, 62], 1]]


def test_speelplan_nc_onleesbaar_en_lege_maat_alleen_tik():
    g, duur = plan(_maten("N.C.", "Hm", ""), {"bpm": 120, "inteltel": 0})
    assert {x[1] for x in g} == {"tik"}
    assert [x[3] for x in g] == [1] * 4 + [2] * 4 + [3] * 4
    assert duur == 6000


def test_speelplan_slash_bas():
    g, _ = plan(_maten("Bbm7/F"), {"bpm": 120, "inteltel": 0})
    assert g[1] == [0, "bas", [41], 1]


def test_speelplan_drie_kwart():
    g, duur = plan(_maten("C"), {"bpm": 120, "tellen": 3})
    assert [x[1] for x in g if x[3] == 1] == ["tik", "bas", "tik", "akkoord", "tik", "akkoord"]
    assert len([x for x in g if x[3] is None]) == 3
    assert duur == 3000


def test_speelplan_half_tempo():
    g, duur = plan(_maten("C"), {"bpm": 60, "inteltel": 0})
    assert [x[0] for x in g if x[1] == "tik"] == [0, 1000, 2000, 3000]
    assert duur == 4000


def test_speelplan_start_en_eind():
    g, duur = plan(_maten("C", "F", "G", "C"), {"bpm": 120, "start": 2, "eind": 3})
    assert sorted({x[3] for x in g if x[3] is not None}) == [2, 3]
    assert g[4] == [2000, "tik", [], 2]
    assert duur == 6000


def test_speelplan_zonder_maten():
    g, duur = plan([], {"bpm": 120, "inteltel": 0})
    assert (g, duur) == ([], 0)


SHUF = {"bpm": 100, "inteltel": 0, "stijl": "shuffle"}  # tel 600 ms, korte achtste op 400 ms


def test_shuffle_een_akkoord_kwint_sext_septiem_sext():
    g, duur = plan(_maten("C"), SHUF)
    assert g == [
        [0, "tik", [], 1], [0, "bas", [36, 43], 1], [400, "bas", [36, 43], 1],
        [600, "tik", [], 1], [600, "bas", [36, 45], 1], [600, "akkoord", [60, 64, 67], 1],
        [1000, "bas", [36, 45], 1],
        [1200, "tik", [], 1], [1200, "bas", [36, 46], 1], [1600, "bas", [36, 46], 1],
        [1800, "tik", [], 1], [1800, "bas", [36, 45], 1], [1800, "akkoord", [60, 64, 67], 1],
        [2200, "bas", [36, 45], 1]]
    assert duur == 2400


def test_shuffle_twee_akkoorden_elk_kwint_sext():
    g, _ = plan(_maten("C G"), SHUF)
    assert [x[2] for x in g if x[1] == "bas"][::2] == [[36, 43], [36, 45], [43, 50], [43, 52]]
    assert [x[:3] for x in g if x[1] == "akkoord"] == [[600, "akkoord", [60, 64, 67]],
                                                       [1800, "akkoord", [55, 59, 62]]]


def test_shuffle_slash_alleen_basnoot():
    g, _ = plan(_maten("Bbm7/F"), SHUF)
    assert {tuple(x[2]) for x in g if x[1] == "bas"} == {(41,)}


def test_shuffle_dim_en_aug_alleen_eigen_kwint():
    g, _ = plan(_maten("Bdim", "Caug"), SHUF)
    assert {tuple(x[2]) for x in g if x[1] == "bas" and x[3] == 1} == {(47, 53)}
    assert {tuple(x[2]) for x in g if x[1] == "bas" and x[3] == 2} == {(36, 44)}


def test_shuffle_nc_alleen_tik():
    g, _ = plan(_maten("N.C.", ""), SHUF)
    assert {x[1] for x in g} == {"tik"}


def test_shuffle_niet_bij_drie_kwart():
    opties = {"bpm": 120, "tellen": 3}
    assert plan(_maten("C"), dict(opties, stijl="shuffle")) == plan(_maten("C"), opties)


def test_shuffle_gesorteerd_op_tijd_met_inteltel():
    # Speler.vooruit plant op volgorde: een gebeurtenis die te vroeg in de lijst staat geeft een gat.
    g, duur = plan(_maten("C F G", "Bbm7/F", "N.C.", "C"), {"bpm": 100, "stijl": "shuffle"})
    tijden = [x[0] for x in g]
    assert tijden == sorted(tijden)
    assert duur == 12000  # inteltel + 4 maten van 2,4 s


NEP = ("(() => { const log = []; let klaar = 0; const ctx = {currentTime: 0, resume() {},"
       " destination: 'luidspreker', createGain: () => ({gain: {setValueAtTime() {},"
       " linearRampToValueAtTime() {}, cancelScheduledValues() {}}, connect() {}, disconnect() {}})};"
       " const s = new Speler({maakContext: () => ctx, opKlaar: () => { klaar += 1; },"
       " geluid: (c, e, w) => log.push([e.soort, Math.round(w * 1000), e.maat])});")


def test_speler_plant_vooruit_vanaf_t0():
    r = js(NEP + " s.start(speelplan([{nr: 1, akkoorden: [{concert: 'C'}]}], {bpm: 120}));"
           " const eerst = log.slice(); s.vooruit(2.2); const daarna = log.slice(); s.stop();"
           " return {eerst, daarna, klaar, speelt: s.speelt}; })()")
    assert r["eerst"] == [["tik", 100, None]]          # alleen wat binnen 0,12 s valt
    assert r["daarna"][-2:] == [["tik", 2100, 1], ["bas", 2100, 1]]
    assert len(r["daarna"]) == 6
    assert (r["klaar"], r["speelt"]) == (1, False)


def test_speler_herhaalt_na_het_plan():
    r = js(NEP + " const m = [{nr: 1, akkoorden: [{concert: 'C'}]}];"
           " s.start(speelplan(m, {bpm: 120}), speelplan(m, {bpm: 120, inteltel: 0}));"
           " s.vooruit(10.1); s.stop(); return log.filter(x => x[0] === 'bas').map(x => x[1]); })()")
    # eerste keer na 4 inteltikken (t0 0,1 + 2 s), daarna elke 2 s zonder inteltel
    assert r == [2100, 3100, 4100, 5100, 6100, 7100, 8100, 9100]


def test_speler_leeg_herhaalplan_geen_eindeloze_lus():
    r = js(NEP + " s.start(speelplan([], {bpm: 120}), speelplan([], {bpm: 120, inteltel: 0}));"
           " s.vooruit(100); const n = log.length; s.stop(); return n; })()")
    assert r == 4


def test_speler_stop_meldt_een_keer():
    r = js(NEP + " s.start(speelplan([], {bpm: 120})); s.stop(); s.stop(); return klaar; })()")
    assert r == 1


def test_kan_spelen_zonder_web_audio():
    assert js("kanSpelen()") is False


def test_stop_dempt_wat_al_gepland_is():
    # Gebeurtenissen tot 0,12 s vooruit en een basnoot van bijna een tel klinken anders na Stop door.
    r = js("(() => { const log = []; const ctx = {currentTime: 0, resume() {}, destination: 'luidspreker',"
           " createGain: () => ({gain: {setValueAtTime: (v, t) => log.push(['zet', v]),"
           " linearRampToValueAtTime: (v, t) => log.push(['naar', v]), cancelScheduledValues() {}},"
           " connect: d => log.push(['aan', d]), disconnect() {}})};"
           " const s = new Speler({maakContext: () => ctx, geluid: (c, e, w, uit) => log.push(['geluid', !!uit])});"
           " s.start(speelplan([], {bpm: 120})); s.stop(); return log; })()")
    assert ["aan", "luidspreker"] in r
    assert ["geluid", True] in r
    assert r[-1] == ["naar", 0]
