"""Smoketest tegen de echte Claude-API. Alleen met BLUESLAB_LIVE=1 (kost een API-aanroep).

    set -a; . ./.env.secrets; set +a
    BLUESLAB_LIVE=1 .venv/bin/python -m pytest tests/test_live.py -v -s
"""

import json
import os
from pathlib import Path

import pytest

from core.analysis import check_bar_count

FIXTURE = Path(__file__).parent / "fixtures" / "chordify-crazy.pdf"
CRAZY_STARTS = [1, 10, 20, 29, 39, 49, 58, 67]

pytestmark = pytest.mark.skipif(os.environ.get("BLUESLAB_LIVE") != "1",
                                reason="live-test: zet BLUESLAB_LIVE=1")


def test_lees_crazy_pdf():
    from app.claude import lees_pdf
    data = lees_pdf(FIXTURE.read_bytes())
    print(json.dumps(data, ensure_ascii=False, indent=1))
    assert data["titel"] == "Crazy"
    assert data["tempo"] == 103
    assert data["voortekening"] == -5
    assert data["regels"][0]["maten"][0][0] == "Bbm"
    assert [r["start_maat"] for r in data["regels"]] == CRAZY_STARTS
    assert all(r["ok"] for r in check_bar_count(data["regels"]))
