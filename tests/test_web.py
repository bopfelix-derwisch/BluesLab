"""Frontend-gedrag van web/app.js, gedraaid met node in een nep-browser (tests/web_harness.js)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNAS = Path(__file__).parent / "web_harness.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node ontbreekt")


def draai(pagina, ik_status):
    uit = subprocess.run(["node", str(HARNAS), pagina, str(ik_status)],
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
