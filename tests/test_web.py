"""Frontend-gedrag van web/app.js, gedraaid met node in een nep-browser (tests/web_harness.js)."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HARNAS = Path(__file__).parent / "web_harness.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node ontbreekt")


def draai(pagina, ik_status, zoek="", fixtures=None, audio=False, acties=()):
    env = dict(os.environ, BLUESLAB_FIXTURES=json.dumps(fixtures or {}),
               BLUESLAB_AUDIO="1" if audio else "0", BLUESLAB_ACTIES=json.dumps(list(acties)))
    uit = subprocess.run(["node", str(HARNAS), pagina, str(ik_status), zoek],
                         capture_output=True, text=True, check=True, timeout=20, env=env)
    return json.loads(uit.stdout.strip().splitlines()[-1])


def test_loginpagina_niet_ingelogd_herlaadt_niet():
    # Regressie: 401 op /api/ik stuurde de loginpagina naar zichzelf → eindeloze herlaadlus.
    r = draai("index", 401)
    assert r["navigaties"] == []
    assert r["login_zichtbaar"] is True


def test_andere_pagina_niet_ingelogd_gaat_naar_login():
    r = draai("setlist", 401)
    assert r["navigaties"] == ["index.html"]


def test_loginformulier_post_native_naar_login():
    html = (Path(__file__).parent.parent / "web" / "index.html").read_text()
    assert '<form id="login-form" method="post" action="/login">' in html
    assert 'name="wachtwoord"' in html


def test_loginformulier_niet_onderschept_door_js():
    # Safari bewaarde de cookie uit een fetch()-login niet: het formulier moet native posten.
    r = draai("index", 401)
    assert "#login-form:submit" not in r["luisterNaar"]


def test_loginfout_uit_url_getoond():
    assert draai("index", 401, "?fout=wachtwoord")["fout"] == "Onjuist wachtwoord."
    assert draai("index", 401, "?fout=limiet")["fout"] == "Te veel pogingen. Wacht een minuut."


# --- iPad-weergave: pure functies uit app.js ---------------------------------

EVAL = Path(__file__).parent / "web_eval.js"


def js(expressie):
    uit = subprocess.run(["node", str(EVAL), expressie],
                         capture_output=True, text=True, check=True, timeout=20)
    return json.loads(uit.stdout.strip().splitlines()[-1])


def _deel(start, akkoorden):
    return {"start_maat": start, "maten": [
        {"nr": start + i, "akkoorden": [{"concert": a} for a in maat.split()]}
        for i, maat in enumerate(akkoorden)]}


def test_herhalingen_wijst_naar_eerste_gelijke_deel():
    delen = [_deel(1, ["Gm", "Gm"]), _deel(3, ["Gm", "C7"]), _deel(5, ["Gm", "Gm"]),
             _deel(7, ["Gm", "C7"]), _deel(9, ["Gm"]), _deel(10, ["Gm Eb", "D7"])]
    assert js(f"herhalingen({json.dumps(delen)})") == [None, None, 1, 3, None, None]


def test_herhalingen_twee_akkoorden_in_een_maat_tellen_mee():
    delen = [_deel(1, ["Gm Eb", "D7"]), _deel(3, ["Gm", "Eb D7"])]
    assert js(f"herhalingen({json.dumps(delen)})") == [None, None]


def test_buren_in_setlist():
    songs = [{"id": 3}, {"id": 5}, {"id": 9}]
    assert js(f"buren({json.dumps(songs)}, 5)") == {"vorige": 3, "volgende": 9}
    assert js(f"buren({json.dumps(songs)}, 3)") == {"vorige": None, "volgende": 5}
    assert js(f"buren({json.dumps(songs)}, 9)") == {"vorige": 5, "volgende": None}
    assert js(f"buren({json.dumps(songs)}, 42)") == {"vorige": None, "volgende": None}


def _schema_maat(nr, akkoord):
    return {"nr": nr, "doeltoon": "E", "doel_pc": 4, "akkoorden": [
        {"concert": akkoord, "geschreven": akkoord, "tonen": ["A", "C", "E"], "fout": None}]}


SCHEMA = {"id": 1, "setlist_id": 7, "titel": "Spooky", "artiest": "Dusty", "tempo": 110,
          "maatsoort": "4/4", "status": "gecontroleerd", "instrument": "bb",
          "concert_key": "Gm", "geschreven_key": "Am",
          "delen": [dict(naam=n, start_maat=s, eind_maat=s + 1, concert_key="Gm", geschreven_key="Am",
                         toonladder=["A", "B", "C"], wissel=False,
                         maten=[_schema_maat(s, "Am"), _schema_maat(s + 1, "Dm")])
                    for n, s in (("Couplet", 1), ("Refrein", 3), ("Couplet", 5))]}
SETLIST = {"id": 7, "naam": "Next week", "songs": [{"id": 1}, {"id": 2}]}


def test_songpagina_rendert_en_houdt_scherm_aan():
    r = draai("song", 200, "?id=1", {"/api/songs/": SCHEMA, "/api/setlists/": SETLIST})
    assert r["fout"] == ""
    assert r["navigaties"] == []
    assert r["wakelock"] == 1
    assert r["nullKinderen"] == 0  # anders staat er letterlijk "null" op de pagina


# --- Oefenen: pure helpers uit app.js ----------------------------------------

def _itunes(n, zonder_preview=()):
    return [{"trackName": f"Spooky {i}", "artistName": f"Artiest {i}",
             **({} if i in zonder_preview else {"previewUrl": f"https://audio/{i}.m4a"})}
            for i in range(n)]


def test_kies_fragment_eerste_en_rondlopen():
    r = _itunes(3)
    assert js(f"kiesFragment({json.dumps(r)}, 0)") == {
        "url": "https://audio/0.m4a", "track": "Spooky 0", "artiest": "Artiest 0", "index": 0, "aantal": 3}
    assert js(f"kiesFragment({json.dumps(r)}, 4)")["index"] == 1


def test_kies_fragment_slaat_zonder_preview_over_en_max_vijf():
    r = _itunes(8, zonder_preview={0, 2})
    f = js(f"kiesFragment({json.dumps(r)}, 0)")
    assert (f["track"], f["aantal"]) == ("Spooky 1", 5)


def test_kies_fragment_niets():
    assert js("kiesFragment([], 0)") is None
    assert js("kiesFragment(undefined, 0)") is None
    assert js(f"kiesFragment({json.dumps(_itunes(2, zonder_preview={0, 1}))}, 0)") is None


def test_fragment_zoek_url():
    assert js('fragmentZoekUrl("Spooky", "Dusty Springfield")') == (
        "https://itunes.apple.com/search?term=Spooky%20Dusty%20Springfield&entity=song&country=NL&limit=10")
    assert js('fragmentZoekUrl("Crazy", "")').startswith("https://itunes.apple.com/search?term=Crazy&")


DELEN = [{"start_maat": 1, "eind_maat": 8}, {"start_maat": 9, "eind_maat": 20},
         {"start_maat": 21, "eind_maat": 24}]


def test_speel_bereik_zonder_herhalen():
    assert js(f"speelBereik({json.dumps(DELEN)}, null, false)") == {"start": 1, "eind": 24, "lusStart": 1}
    assert js(f"speelBereik({json.dumps(DELEN)}, 12, false)") == {"start": 12, "eind": 24, "lusStart": 12}


def test_speel_bereik_herhaalt_het_deel_van_de_startmaat():
    assert js(f"speelBereik({json.dumps(DELEN)}, 12, true)") == {"start": 12, "eind": 20, "lusStart": 9}
    assert js(f"speelBereik({json.dumps(DELEN)}, null, true)") == {"start": 1, "eind": 8, "lusStart": 1}


def test_speel_bereik_zonder_delen():
    assert js("speelBereik([], null, true)") == {"start": 1, "eind": 0, "lusStart": 1}


# --- Oefenen: songpagina ------------------------------------------------------

ITUNES = {"resultCount": 1, "results": [
    {"trackName": "Spooky", "artistName": "Dusty", "previewUrl": "https://audio/1.m4a"}]}


def test_songpagina_speelbalk_en_fragment():
    r = draai("song", 200, "?id=1", {"/api/songs/": SCHEMA, "/api/setlists/": SETLIST,
                                     "https://itunes.apple.com/": ITUNES}, audio=True)
    assert r["fout"] == ""
    assert r["speler_zichtbaar"] is True
    assert r["nullKinderen"] == 0
    assert any(f.startswith("https://itunes.apple.com/search?term=Spooky%20Dusty") for f in r["fetches"])
    assert r["maatvakken"] == 6  # elk maatvak is aan te tikken als startmaat


def test_songpagina_zonder_web_audio_geen_speelbalk():
    r = draai("song", 200, "?id=1", {"/api/songs/": SCHEMA, "/api/setlists/": SETLIST})
    assert r["fout"] == ""
    assert r["speler_zichtbaar"] is False
    assert r["nullKinderen"] == 0


def test_kies_fragment_titel_gaat_voor():
    # Echt iTunes-antwoord voor "Spooky Bill Wyman & The Rhythm Kings": de Stones stonden bovenaan.
    r = [{"trackName": "Sympathy For The Devil", "artistName": "The Rolling Stones", "previewUrl": "s"},
         {"trackName": "Spooky", "artistName": "Bill Wyman's Rhythm Kings", "previewUrl": "a"},
         {"trackName": "spooky (live)", "artistName": "Iemand", "previewUrl": "b"}]
    assert [js(f"kiesFragment({json.dumps(r)}, {i}, 'Spooky')")["url"] for i in range(3)] == ["a", "b", "s"]
    assert js(f"kiesFragment({json.dumps(r)}, 0)")["url"] == "s"  # zonder titel: volgorde van iTunes


def test_kies_fragment_exacte_titel_eerst():
    r = [{"trackName": "Crazy (feat. David Benjamin) [Acoustic Version]", "previewUrl": "akoestisch"},
         {"trackName": "Crazy", "previewUrl": "origineel"}]
    assert js(f"kiesFragment({json.dumps(r)}, 0, 'Crazy')")["url"] == "origineel"


def _speel(*acties):
    return draai("song", 200, "?id=1", {"/api/songs/": SCHEMA, "/api/setlists/": SETLIST},
                 audio=True, acties=acties)


def test_tik_op_maat_tijdens_spelen_start_daar_opnieuw():
    assert _speel("tekst=▶ Speel")["starts"] == 1
    assert _speel("tekst=▶ Speel", "data-nr=3")["starts"] == 2


def test_tik_op_maat_zonder_spelen_start_niet():
    assert _speel("data-nr=3")["starts"] == 0


def test_speel_zet_audiosessie_op_playback():
    # Anders dempt de stille modus van iPad/iPhone de begeleiding (het fragment klinkt wel).
    assert _speel()["audiosessie"] == "auto"
    assert _speel("tekst=▶ Speel")["audiosessie"] == "playback"


def test_ander_fragment_knop_is_groot_genoeg():
    import re
    css = (Path(__file__).parent.parent / "web" / "style.css").read_text()
    regel = re.search(r"\.fragment button\.stil\s*\{([^}]*)\}", css)
    assert regel and "min-height: 44px" in regel.group(1)
