"""Golden fixture: de handmatig gecontroleerde maatlijst van Crazy (uit de live-test)."""

import json
from pathlib import Path

from core.analysis import check_bar_count, flatten, key_for_section, speelschema

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "crazy-regels.json").read_text())


def test_golden_telling_klopt():
    assert [r["start_maat"] for r in GOLDEN["regels"]] == [1, 10, 20, 29, 39, 49, 58, 67]
    assert all(r["ok"] for r in check_bar_count(GOLDEN["regels"]))


def test_golden_toonsoort_bbm():
    assert key_for_section(flatten(GOLDEN["regels"]), GOLDEN["voortekening"])["naam"] == "Bbm"


def test_golden_speelschema_klarinet():
    maten = flatten(GOLDEN["regels"])
    delen = [{"naam": "Couplet", "start_maat": 1, "eind_maat": len(maten), "concert_key": "Bbm"}]
    schema = speelschema(maten, delen, "bb_clarinet")
    assert schema[0]["geschreven_key"] == "Cm"
    assert schema[0]["maten"][0]["akkoorden"][0]["geschreven"] == "Cm"
