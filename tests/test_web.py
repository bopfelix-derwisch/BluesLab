"""Frontend-gedrag van web/app.js, gedraaid met node in een nep-browser (tests/web_harness.js)."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HARNAS = Path(__file__).parent / "web_harness.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node ontbreekt")


def draai(pagina, ik_status, zoek="", fixtures=None):
    env = dict(os.environ, BLUESLAB_FIXTURES=json.dumps(fixtures or {}))
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
