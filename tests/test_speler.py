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


def test_ontgrendel_maakt_context_een_keer_en_hervat():
    r = js("(() => { let gemaakt = 0, hervat = 0; const ctx = {resume() { hervat += 1; }};"
           " const s = new Speler({maakContext: () => { gemaakt += 1; return ctx; }});"
           " const a = s.ontgrendel(); s.ontgrendel(); return {zelfde: a === ctx, gemaakt, hervat}; })()")
    assert r == {"zelfde": True, "gemaakt": 1, "hervat": 2}


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


WEB = Path(__file__).parent.parent / "web"


def test_pianosamples_aanwezig_en_klein():
    noten = js("PIANO_NOTEN")
    assert noten == list(range(36, 79, 3))
    for m in noten:
        f = WEB / "piano" / f"{m}.mp3"
        assert f.is_file(), f
        assert 5_000 < f.stat().st_size < 60_000, f


NEP_PIANO = ("(() => { const bronnen = []; const tonen = [];"
             " const param = () => ({setValueAtTime() {}, linearRampToValueAtTime() {},"
             " exponentialRampToValueAtTime() {}});"
             " const knoop = x => Object.assign({connect: y => y}, x);"
             " const ctx = {createGain: () => knoop({gain: param()}),"
             " createBufferSource: () => { const b = knoop({playbackRate: {}, start() {}, stop() {}});"
             " bronnen.push(b); return b; },"
             " createOscillator: () => { const o = knoop({frequency: {}, start() {}, stop() {}});"
             " tonen.push(o); return o; }};"
             " const buffers = {}; PIANO_NOTEN.forEach(m => { buffers[m] = 'buf' + m; });")


def test_piano_geluid_dichtstbijzijnde_sample_en_toonhoogte():
    r = js(NEP_PIANO + " const g = pianoGeluid(buffers);"
           " g(ctx, {soort: 'akkoord', midi: [37, 30, 80], duur: 0.5, maat: 1}, 1, {});"
           " g(ctx, {soort: 'tik', midi: [], duur: 0.03, maat: 1}, 1, {});"
           " return {bronnen: bronnen.map(b => [b.buffer, Math.round(b.playbackRate.value * 10000) / 10000]),"
           " tonen: tonen.length}; })()")
    assert r["bronnen"] == [["buf36", 1.0595], ["buf36", 0.7071], ["buf78", 1.1225]]
    assert r["tonen"] == 1  # de tik blijft de synth


LAAD = ("(() => { const gevraagd = []; const ctx = {decodeAudioData: d => Promise.resolve('dec:' + d)};"
        " const haal = url => { gevraagd.push(url); const ok = url !== FOUT;"
        " return Promise.resolve({ok, status: ok ? 200 : 404, arrayBuffer: () => Promise.resolve(url)}); };")


def test_laad_piano_haalt_alle_samples():
    r = js("const FOUT = null;" + LAAD + " return laadPiano(ctx, haal).then(b =>"
           " ({gevraagd, b36: b[36], n: Object.keys(b).length})); })()")
    assert r["gevraagd"] == [f"piano/{m}.mp3" for m in range(36, 79, 3)]
    assert (r["b36"], r["n"]) == ("dec:piano/36.mp3", 15)


def test_laad_piano_een_fout_is_alles_fout():
    r = js("const FOUT = 'piano/51.mp3';" + LAAD + " return laadPiano(ctx, haal); })()")
    assert r == {"fout": "piano/51.mp3: 404"}


def test_binnen_tijdslimiet():
    assert js("binnen(new Promise(() => {}), 10)") == {"fout": "te traag"}
    assert js("binnen(Promise.resolve(5), 5000)") == 5  # en de wekker houdt node niet open


def test_tik_tijdens_spelen_zachter_dan_inteltel():
    r = js("(() => { const pieken = []; const knoop = x => Object.assign({connect: y => y}, x);"
           " const ctx = {createOscillator: () => knoop({frequency: {}, start() {}, stop() {}}),"
           " createGain: () => knoop({gain: {setValueAtTime() {}, exponentialRampToValueAtTime() {},"
           " linearRampToValueAtTime(v) { pieken.push(v); }}})};"
           " speelGeluid(ctx, {soort: 'tik', midi: [], duur: 0.03, maat: null}, 0, {});"
           " speelGeluid(ctx, {soort: 'tik', midi: [], duur: 0.03, maat: 1}, 0, {});"
           " return pieken; })()")
    assert r[0] > r[1] > 0


# --- Stijlen met drums ----------------------------------------------------------

def _tijden(g, soort, maat=1):
    return [x[0] for x in g if x[1] == soort and x[3] == maat]


def _stijl(stijl, *maten, drums=True):
    return plan(_maten(*maten), {"bpm": 100, "inteltel": 0, "stijl": stijl, "drums": drums})[0]


def test_pop_patroon():
    g = _stijl("pop", "C")
    assert _tijden(g, "bas") == [0, 900, 1200]
    assert _tijden(g, "akkoord") == list(range(0, 2400, 300))
    assert (_tijden(g, "kick"), _tijden(g, "snare")) == ([0, 1200], [600, 1800])
    assert _tijden(g, "hihat") == list(range(0, 2400, 300))
    assert _tijden(g, "tik") == []  # met drums geen tik tijdens het spelen


def test_pop_twee_akkoorden_bas_op_8_is_tweede_akkoord():
    g = _stijl("pop", "C G")
    assert [x[2] for x in g if x[1] == "bas"] == [[36], [36], [43]]


def test_ballad_gebroken_akkoord_drie_en_vierklank():
    g = _stijl("ballad", "C", "C7")
    assert [x[2][0] for x in g if x[1] == "akkoord" and x[3] == 1] == [60, 64, 67, 72] * 2
    assert [x[2][0] for x in g if x[1] == "akkoord" and x[3] == 2] == [60, 64, 67, 70] * 2
    assert _tijden(g, "bas") == [0, 1200]
    assert (_tijden(g, "kick"), _tijden(g, "snare"), _tijden(g, "hihat")) == (
        [0], [1200], [0, 600, 1200, 1800])


def test_ballad_rechterhand_zacht():
    r = js("speelplan([{nr: 1, akkoorden: [{concert: 'C'}]}], {bpm: 100, inteltel: 0,"
           " stijl: 'ballad'}).gebeurtenissen.filter(e => e.soort === 'akkoord')[0].sterkte")
    assert r == 0.5


def test_funk_patroon():
    g = _stijl("funk", "C")
    assert [(x[0], x[2]) for x in g if x[1] == "bas"] == [
        (0, [36]), (450, [36]), (900, [48]), (1200, [36]), (1650, [43]), (2100, [48])]
    assert _tijden(g, "akkoord") == [750, 1050, 1950, 2250]
    assert (_tijden(g, "kick"), _tijden(g, "snare")) == ([0, 900], [600, 1800])
    assert _tijden(g, "hihat") == list(range(0, 2400, 150))


def test_shuffle_met_drums_zwingende_hihat():
    g = _stijl("shuffle", "C")
    assert _tijden(g, "hihat") == [0, 400, 600, 1000, 1200, 1600, 1800, 2200]
    assert (_tijden(g, "kick"), _tijden(g, "snare"), _tijden(g, "tik")) == ([0, 1200], [600, 1800], [])


def test_stijl_slash_akkoord_bas_is_slashnoot():
    assert {tuple(x[2]) for x in _stijl("pop", "Bbm7/F") if x[1] == "bas"} == {(41,)}


def test_stijl_nc_met_drums_alleen_hihat_zonder_drums_tik():
    met = _stijl("pop", "N.C.")
    assert {x[1] for x in met} == {"hihat"} and _tijden(met, "hihat") == [0, 600, 1200, 1800]
    zonder = _stijl("pop", "N.C.", drums=False)
    assert {x[1] for x in zonder} == {"tik"} and _tijden(zonder, "tik") == [0, 600, 1200, 1800]


def test_stijl_zonder_drums_tik_en_geen_drums():
    g = _stijl("funk", "C", drums=False)
    assert _tijden(g, "tik") == [0, 600, 1200, 1800]
    assert not [x for x in g if x[1] in ("kick", "snare", "hihat")]


def test_drums_aftellen_blijft_tik():
    g, _ = plan(_maten("C"), {"bpm": 100, "stijl": "pop", "drums": True})
    assert [x for x in g if x[1] == "tik"] == [[t, "tik", [], None] for t in (0, 600, 1200, 1800)]


def test_stijl_niet_bij_drie_kwart():
    opties = {"bpm": 120, "tellen": 3}
    assert plan(_maten("C"), dict(opties, stijl="pop", drums=True)) == plan(_maten("C"), opties)


@pytest.mark.parametrize("stijl", ["shuffle", "pop", "ballad", "funk"])
@pytest.mark.parametrize("drums", [True, False])
def test_stijl_gesorteerd_op_tijd(stijl, drums):
    g, _ = plan(_maten("C F G", "Bbm7/F", "N.C.", "C"), {"bpm": 100, "stijl": stijl, "drums": drums})
    tijden = [x[0] for x in g]
    assert tijden == sorted(tijden)


def test_drumsamples_aanwezig_en_licentie():
    for n in ("kick", "snare", "hihat"):
        f = WEB / "drums" / f"{n}.mp3"
        assert f.is_file(), f
        assert 1_000 < f.stat().st_size < 30_000, f
    assert "Apache License" in (WEB / "drums" / "LICENSE-Apache-2.0.txt").read_text()


def test_laad_drums_haalt_drie_samples():
    r = js("const FOUT = null;" + LAAD + " return laadDrums(ctx, haal).then(b =>"
           " ({gevraagd, sleutels: Object.keys(b).sort(), kick: b.kick})); })()")
    assert r["gevraagd"] == ["drums/kick.mp3", "drums/snare.mp3", "drums/hihat.mp3"]
    assert r["sleutels"] == ["hihat", "kick", "snare"]
    assert r["kick"] == "dec:drums/kick.mp3"


NEP_GELUID = ("(() => { const bronnen = []; let oscs = 0;"
              " const param = log => ({setValueAtTime(v) { log.push(v); }, linearRampToValueAtTime() {},"
              " exponentialRampToValueAtTime() {}});"
              " const knoop = x => Object.assign({connect: y => y}, x); let laatsteGain = [];"
              " const ctx = {createGain: () => { laatsteGain = []; return knoop({gain: param(laatsteGain)}); },"
              " createBufferSource: () => { const b = knoop({playbackRate: {}, start() {}, stop() {}});"
              " bronnen.push(b); return b; },"
              " createOscillator: () => { oscs += 1; return knoop({frequency: {}, start() {}, stop() {}}); }};"
              " const DR = {kick: 'K', snare: 'S', hihat: 'H'};")


def test_maak_geluid_drums_met_sterkte():
    r = js(NEP_GELUID + " const g = maakGeluid({drums: DR});"
           " g(ctx, {soort: 'kick', midi: [], duur: 0.5, maat: 1, sterkte: 0.5}, 1, {});"
           " return {buf: bronnen.map(b => b.buffer), gain: laatsteGain[0], oscs}; })()")
    assert r == {"buf": ["K"], "gain": 0.45, "oscs": 0}


def test_maak_geluid_inteltik_wordt_hihat_met_drums():
    r = js(NEP_GELUID + " const g = maakGeluid({drums: DR});"
           " g(ctx, {soort: 'tik', midi: [], duur: 0.03, maat: null}, 1, {});"
           " g(ctx, {soort: 'tik', midi: [], duur: 0.03, maat: 1}, 1, {});"
           " return {buf: bronnen.map(b => b.buffer), oscs}; })()")
    assert r == {"buf": ["H"], "oscs": 1}  # alleen de inteltik wordt hi-hat


def test_maak_geluid_zonder_piano_synth_en_zonder_drums_stil():
    r = js(NEP_GELUID + " maakGeluid({drums: DR})(ctx, {soort: 'bas', midi: [36, 43], duur: 0.5, maat: 1}, 1, {});"
           " const synth = oscs;"
           " maakGeluid({})(ctx, {soort: 'snare', midi: [], duur: 0.5, maat: 1}, 1, {});"
           " return {synth, bronnen: bronnen.length, oscs}; })()")
    assert r == {"synth": 2, "bronnen": 0, "oscs": 2}


def test_synth_volgt_sterkte():
    r = js("(() => { const pieken = []; const knoop = x => Object.assign({connect: y => y}, x);"
           " const ctx = {createOscillator: () => knoop({frequency: {}, start() {}, stop() {}}),"
           " createGain: () => knoop({gain: {setValueAtTime() {}, exponentialRampToValueAtTime() {},"
           " linearRampToValueAtTime(v) { pieken.push(v); }}})};"
           " speelGeluid(ctx, {soort: 'akkoord', midi: [60], duur: 0.3, maat: 1}, 0, {});"
           " speelGeluid(ctx, {soort: 'akkoord', midi: [60], duur: 0.3, maat: 1, sterkte: 0.5}, 0, {});"
           " return pieken; })()")
    assert r[1] == r[0] / 2
