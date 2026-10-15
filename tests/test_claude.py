import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app import claude
from app.claude import ClaudeFout, lees_pdf, schoon_titel, structuur


class NepClient:
    """Vangt de request-argumenten en geeft een vast antwoord terug."""

    def __init__(self, data=None, stop_reason="end_turn", fout=None):
        self.data, self.stop_reason, self.fout = data, stop_reason, fout
        self.kwargs = None
        self.messages = self

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.fout:
            raise self.fout
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.data))])


GELEZEN = {"titel": "Crazy (Acoustic version)", "artiest": "Lost Frequencies", "tempo": 103,
           "maatsoort": "4/4", "voortekening": -5,
           "regels": [{"start_maat": 1, "maten": [["Bbm"], ["Gb"]]}]}


def test_lees_pdf_request_en_titel():
    nep = NepClient(GELEZEN)
    uit = lees_pdf(b"%PDF-1.4 test", client=nep)
    assert uit["titel"] == "Crazy"
    assert nep.kwargs["model"] == "claude-sonnet-5-5"
    doc = nep.kwargs["messages"][0]["content"][0]
    assert doc["type"] == "document"
    assert doc["source"]["media_type"] == "application/pdf"
    fmt = nep.kwargs["output_config"]["format"]
    assert fmt["type"] == "json_schema" and "regels" in fmt["schema"]["properties"]


def test_lees_pdf_zonder_regels():
    with pytest.raises(ClaudeFout):
        lees_pdf(b"%PDF", client=NepClient(dict(GELEZEN, regels=[])))


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_stop_reasons(stop):
    with pytest.raises(ClaudeFout):
        lees_pdf(b"%PDF", client=NepClient(GELEZEN, stop_reason=stop))


def test_api_fout_wordt_claudefout():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fout = anthropic.APITimeoutError(request=req)
    with pytest.raises(ClaudeFout, match="niet op tijd"):
        lees_pdf(b"%PDF", client=NepClient(fout=fout))


def test_structuur_prompt_bevat_maten():
    delen = [{"naam": "Couplet", "start_maat": 1, "eind_maat": 2, "toonsoort": "Bbm",
              "solo_geschikt": False, "reden": "x"}]
    nep = NepClient({"delen": delen})
    assert structuur("Crazy", "LF", -5, [["Bbm"], ["Gb", "Db"]], client=nep) == delen
    tekst = nep.kwargs["messages"][0]["content"]
    assert "1: Bbm" in tekst and "2: Gb Db" in tekst and "maat 1 tot en met 2" in tekst


@pytest.mark.parametrize("ruw, schoon", [
    ("Crazy (Acoustic version) (Official Music Video)", "Crazy"),
    ("Californication", "Californication"),
    ("(Official)", "(Official)"),
])
def test_schoon_titel(ruw, schoon):
    assert schoon_titel(ruw) == schoon


def test_model_constant():
    assert claude.MODEL == "claude-sonnet-5-5"
