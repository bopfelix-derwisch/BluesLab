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
    assert js(f"akkoordMidi({json.dumps(tekst)})") == {"nc": False, "bas": bas, "akkoord": akkoord}


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
