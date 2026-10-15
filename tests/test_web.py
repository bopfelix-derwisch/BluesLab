"""Frontend-gedrag van web/app.js, gedraaid met node in een nep-browser (tests/web_harness.js)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNAS = Path(__file__).parent / "web_harness.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node ontbreekt")


def draai(pagina, ik_status, zoek=""):
    uit = subprocess.run(["node", str(HARNAS), pagina, str(ik_status), zoek],
                         capture_output=True, text=True, check=True, timeout=20)
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
