from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth import maak_hash
from app.claude import ClaudeFout
from app.main import maak_app

PDF = b"%PDF-1.4 nep"
WACHTWOORD = "blauwe-noot"

GELEZEN = {"titel": "Crazy", "artiest": "Lost Frequencies", "tempo": 103, "maatsoort": "4/4",
           "voortekening": -5,
           "regels": [{"start_maat": 1, "maten": [["Bbm"], ["Gb"], ["Db"], ["Ab"]]},
                      {"start_maat": 5, "maten": [["Bbm"], ["Gb"], ["Db"], ["Ab"]]}]}
DELEN = [{"naam": "Couplet", "start_maat": 1, "eind_maat": 8, "toonsoort": "Bbm",
          "solo_geschikt": True, "reden": "Hele nummer."}]


class NepClaude:
    def __init__(self, gelezen=GELEZEN, delen=DELEN, lees_fout=None, structuur_fout=None):
        self.gelezen, self.delen = gelezen, delen
        self.lees_fout, self.structuur_fout = lees_fout, structuur_fout
        self.aanroepen = 0

    def lees_pdf(self, pdf):
        self.aanroepen += 1
        if self.lees_fout:
            raise self.lees_fout
        return {**self.gelezen, "regels": [dict(r) for r in self.gelezen["regels"]]}

    def structuur(self, titel, artiest, voortekening, maten):
        self.aanroepen += 1
        if self.structuur_fout:
            raise self.structuur_fout
        return [dict(d) for d in self.delen]


@pytest.fixture
def maak(tmp_path):
    def _maak(claude=None):
        app = maak_app({"data_dir": str(tmp_path), "password_hash": maak_hash(WACHTWOORD),
                        "secret": "test-geheim", "claude": claude or NepClaude(),
                        "web_dir": str(tmp_path / "geen-web")})
        return TestClient(app, base_url="https://testserver")
    return _maak


def _login(client):
    assert client.post("/api/login", json={"wachtwoord": WACHTWOORD}).status_code == 200
    return client


def _setlist(client):
    return client.post("/api/setlists", json={"naam": "Next week"}).json()["id"]


def _upload(client, sl, inhoud=PDF):
    return client.post(f"/api/setlists/{sl}/songs",
                       files={"bestand": ("crazy.pdf", inhoud, "application/pdf")})


def test_zonder_login_401(maak):
    c = maak()
    assert c.get("/api/setlists").status_code == 401
    assert c.get("/api/ik").json()["detail"] == "Log eerst in."


def test_login_fout_en_goed(maak):
    c = maak()
    assert c.post("/api/login", json={"wachtwoord": "fout"}).status_code == 401
    r = c.post("/api/login", json={"wachtwoord": WACHTWOORD})
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "samesite=lax" in cookie.lower()
    assert c.get("/api/ik").status_code == 200
    c.post("/api/logout")
    assert c.get("/api/ik").status_code == 401


def test_login_rate_limit_per_ip(maak):
    c = maak()
    for _ in range(5):
        c.post("/api/login", json={"wachtwoord": "fout"}, headers={"CF-Connecting-IP": "1.1.1.1"})
    r = c.post("/api/login", json={"wachtwoord": WACHTWOORD},
               headers={"CF-Connecting-IP": "1.1.1.1"})
    assert r.status_code == 429
    r = c.post("/api/login", json={"wachtwoord": WACHTWOORD},
               headers={"CF-Connecting-IP": "2.2.2.2"})
    assert r.status_code == 200


def test_ontbrekende_instellingen(tmp_path, monkeypatch):
    monkeypatch.delenv("BLUESLAB_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("BLUESLAB_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        maak_app({"data_dir": str(tmp_path)})


def test_setlist_lege_naam(maak):
    c = _login(maak())
    assert c.post("/api/setlists", json={"naam": "  "}).status_code == 422


def test_upload_en_controle_flow(maak):
    c = _login(maak())
    sl = _setlist(c)
    r = _upload(c, sl)
    assert r.status_code == 201
    sid = r.json()["id"]

    lijst = c.get(f"/api/setlists/{sl}").json()
    assert lijst["songs"][0]["titel"] == "Crazy"
    assert lijst["songs"][0]["sleutels"] == {"bb": "Cm", "eb": "Gm"}

    s = c.get(f"/api/songs/{sid}").json()
    assert s["status"] == "gelezen"
    assert all(t["ok"] for t in s["telling"])
    assert s["delen"][0]["concert_key"] == "Bbm"
    assert s["delen"][0]["engine_key"] == "Bbm"
    assert s["delen"][0]["afwijking"] is False
    assert "pdf_path" not in s

    body = {"titel": "Crazy", "artiest": "Lost Frequencies", "tempo": 103, "voortekening": -5,
            "regels": s["regels"],
            "delen": [{"naam": "Couplet", "start_maat": 1, "eind_maat": 4, "concert_key": "B♭m",
                       "key_source": "claude", "solo_geschikt": False},
                      {"naam": "Refrein", "start_maat": 5, "eind_maat": 8, "concert_key": "Db",
                       "key_source": "handmatig", "solo_geschikt": True}]}
    assert c.put(f"/api/songs/{sid}", json=body).status_code == 200
    s = c.get(f"/api/songs/{sid}").json()
    assert s["status"] == "gecontroleerd"
    assert [d["concert_key"] for d in s["delen"]] == ["Bbm", "Db"]

    schema = c.get(f"/api/songs/{sid}/schema?instrument=eb").json()
    assert schema["geschreven_key"] == "Gm"
    assert [d["geschreven_key"] for d in schema["delen"]] == ["Gm", "Bb"]
    assert schema["delen"][1]["wissel"] is True
    assert schema["delen"][0]["maten"][1]["akkoorden"][0]["geschreven"] == "Eb"
    bb = c.get(f"/api/songs/{sid}/schema").json()
    assert bb["instrument"] == "bb" and bb["geschreven_key"] == "Cm"
    assert c.get(f"/api/songs/{sid}/schema?instrument=tuba").status_code == 422


def test_upload_weigert_geen_pdf_en_te_groot(maak):
    nep = NepClaude()
    c = _login(maak(nep))
    sl = _setlist(c)
    assert _upload(c, sl, b"GIF89a").status_code == 415
    assert _upload(c, sl, b"%PDF" + b"0" * (10 * 1024 * 1024)).status_code == 413
    assert nep.aanroepen == 0
    assert _upload(c, 999).status_code == 404


def test_upload_claude_fout_laat_niets_achter(maak, tmp_path):
    c = _login(maak(NepClaude(lees_fout=ClaudeFout("Claude reageerde niet op tijd."))))
    sl = _setlist(c)
    r = _upload(c, sl)
    assert r.status_code == 502
    assert r.json()["detail"] == "Claude reageerde niet op tijd."
    assert c.get(f"/api/setlists/{sl}").json()["songs"] == []
    assert list((tmp_path / "uploads").iterdir()) == []


def test_upload_structuur_fallback(maak):
    c = _login(maak(NepClaude(structuur_fout=ClaudeFout("stuk"))))
    sl = _setlist(c)
    sid = _upload(c, sl).json()["id"]
    delen = c.get(f"/api/songs/{sid}").json()["delen"]
    assert [d["naam"] for d in delen] == ["Deel A"]
    assert delen[0]["key_source"] == "engine" and delen[0]["concert_key"] == "Bbm"


def test_upload_structuur_met_gat_valt_terug(maak):
    gat = [dict(DELEN[0], eind_maat=6)]
    c = _login(maak(NepClaude(delen=gat)))
    sid = _upload(c, _setlist(c)).json()["id"]
    assert c.get(f"/api/songs/{sid}").json()["delen"][0]["eind_maat"] == 8


def test_upload_claude_toonsoort_onleesbaar(maak):
    raar = [dict(DELEN[0], toonsoort="B flat minor")]
    c = _login(maak(NepClaude(delen=raar)))
    sid = _upload(c, _setlist(c)).json()["id"]
    d = c.get(f"/api/songs/{sid}").json()["delen"][0]
    assert (d["concert_key"], d["key_source"]) == ("Bbm", "engine")


def test_afwijking_gemarkeerd(maak):
    c = _login(maak(NepClaude(delen=[dict(DELEN[0], toonsoort="E")])))
    sid = _upload(c, _setlist(c)).json()["id"]
    d = c.get(f"/api/songs/{sid}").json()["delen"][0]
    assert d["afwijking"] is True and d["engine_key"] == "Bbm"


def test_telling_en_onparseerbaar_gemarkeerd(maak):
    gelezen = dict(GELEZEN, regels=[{"start_maat": 1, "maten": [["Bbm"], ["H7"], ["Db"]]},
                                    {"start_maat": 5, "maten": [["Bbm"], ["Gb"], ["Db"], ["Ab"]]}])
    delen = [dict(DELEN[0], eind_maat=7)]
    c = _login(maak(NepClaude(gelezen=gelezen, delen=delen)))
    sid = _upload(c, _setlist(c)).json()["id"]
    s = c.get(f"/api/songs/{sid}").json()
    assert s["telling"][0] == {"start_maat": 1, "verwacht": 4, "gevonden": 3, "ok": False}
    assert s["onparseerbaar"] == [{"maat": 2, "akkoord": "H7"}]
    schema = c.get(f"/api/songs/{sid}/schema").json()
    assert schema["delen"][0]["maten"][1]["akkoorden"][0]["fout"]


def test_controle_weigert_gaten_en_foute_toonsoort(maak):
    c = _login(maak())
    sid = _upload(c, _setlist(c)).json()["id"]
    s = c.get(f"/api/songs/{sid}").json()
    body = {"titel": "Crazy", "regels": s["regels"],
            "delen": [{"naam": "Couplet", "start_maat": 1, "eind_maat": 6, "concert_key": "Xq",
                       "key_source": "handmatig"}]}
    r = c.put(f"/api/songs/{sid}", json=body)
    assert r.status_code == 422
    assert any("laatste deel" in p for p in r.json()["detail"])
    assert any("Couplet" in p for p in r.json()["detail"])
    body["titel"] = " "
    assert c.put(f"/api/songs/{sid}", json=body).status_code == 422
    assert c.put("/api/songs/999", json=body).status_code == 404


def test_controle_bewaart_telfout_wel(maak):
    c = _login(maak())
    sid = _upload(c, _setlist(c)).json()["id"]
    regels = [{"start_maat": 1, "maten": [["Bbm"], ["Gb"], ["Db"]]},
              {"start_maat": 5, "maten": [["Bbm"], ["Gb"], ["Db"], [" Ab ", ""]]}]
    body = {"titel": "Crazy", "regels": regels,
            "delen": [{"naam": "Couplet", "start_maat": 1, "eind_maat": 7, "concert_key": "Bbm",
                       "key_source": "claude"}]}
    assert c.put(f"/api/songs/{sid}", json=body).status_code == 200
    s = c.get(f"/api/songs/{sid}").json()
    assert s["telling"][0]["ok"] is False
    assert s["regels"][1]["maten"][3] == ["Ab"]


def test_volgorde_en_verwijderen(maak, tmp_path):
    c = _login(maak())
    sl = _setlist(c)
    a = _upload(c, sl).json()["id"]
    b = _upload(c, sl).json()["id"]
    assert c.put(f"/api/setlists/{sl}/volgorde", json={"song_ids": [b]}).status_code == 422
    assert c.put(f"/api/setlists/{sl}/volgorde", json={"song_ids": [b, a]}).status_code == 200
    assert [n["id"] for n in c.get(f"/api/setlists/{sl}").json()["songs"]] == [b, a]
    assert c.delete(f"/api/songs/{a}").status_code == 200
    assert c.delete(f"/api/songs/{a}").status_code == 404
    assert len(list((tmp_path / "uploads").iterdir())) == 1


def test_claude_limiet(maak):
    nep = NepClaude()
    c = _login(maak(nep))
    sl = _setlist(c)
    for _ in range(15):
        assert _upload(c, sl).status_code == 201
    r = _upload(c, sl)
    assert r.status_code == 429
    assert nep.aanroepen == 30


def test_web_wordt_geserveerd(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<title>BluesLab</title>")
    app = maak_app({"data_dir": str(tmp_path), "password_hash": maak_hash("x"),
                    "secret": "s", "claude": NepClaude(), "web_dir": str(web)})
    c = TestClient(app, base_url="https://testserver")
    assert "BluesLab" in c.get("/").text
    assert c.get("/api/ik").status_code == 401


def test_engine_key_deel_zonder_akkoorden():
    from app.main import engine_key
    assert engine_key([["N.C."], []], -5)["naam"] == "Db"
    assert engine_key([["N.C."]], 2)["naam"] == "D"


def test_upload_deel_met_alleen_nc(maak):
    gelezen = dict(GELEZEN, regels=[{"start_maat": 1, "maten": [["N.C."], ["N.C."]]},
                                    {"start_maat": 3, "maten": [["Bbm"], ["Gb"]]}])
    delen = [{"naam": "Intro", "start_maat": 1, "eind_maat": 2, "toonsoort": "",
              "solo_geschikt": False, "reden": "Stilte."},
             {"naam": "Couplet", "start_maat": 3, "eind_maat": 4, "toonsoort": "Bbm",
              "solo_geschikt": False, "reden": "x"}]
    c = _login(maak(NepClaude(gelezen=gelezen, delen=delen)))
    sid = _upload(c, _setlist(c)).json()["id"]
    s = c.get(f"/api/songs/{sid}").json()
    assert s["delen"][0]["concert_key"] == "Db" and s["delen"][0]["key_source"] == "engine"
    schema = c.get(f"/api/songs/{sid}/schema").json()
    assert schema["delen"][0]["maten"][0]["doeltoon"] is None


# --- review-fixes (Final review BL-2) ---------------------------------------

def test_zonder_login_body_niet_gelezen(maak):
    # Login wordt gecontroleerd vóór de body geparsed wordt: 401, geen 422.
    c = maak()
    r = c.post("/api/setlists", content=b"{kapot", headers={"content-type": "application/json"})
    assert r.status_code == 401
    assert _upload(c, 1).status_code == 401


def test_te_groot_verzoek_413_voor_body(maak):
    c = _login(maak())
    r = c.post("/api/setlists/1/songs", content=b"x",
               headers={"content-type": "application/pdf", "content-length": str(12 * 1024 * 1024)})
    assert r.status_code == 413


def test_upload_nc_deel_negeert_claude_toonsoort(maak):
    gelezen = dict(GELEZEN, regels=[{"start_maat": 1, "maten": [["N.C."], ["N.C."]]},
                                    {"start_maat": 3, "maten": [["Bbm"], ["Gb"]]}])
    delen = [{"naam": "Intro", "start_maat": 1, "eind_maat": 2, "toonsoort": "Bbm",
              "solo_geschikt": False, "reden": "Stilte."},
             {"naam": "Couplet", "start_maat": 3, "eind_maat": 4, "toonsoort": "Bbm",
              "solo_geschikt": False, "reden": "x"}]
    c = _login(maak(NepClaude(gelezen=gelezen, delen=delen)))
    sid = _upload(c, _setlist(c)).json()["id"]
    d = c.get(f"/api/songs/{sid}").json()["delen"][0]
    assert d["concert_key"] == "Db" and d["key_source"] == "engine"


def test_login_globale_limiet_over_ips(maak):
    c = maak()
    codes = [c.post("/api/login", json={"wachtwoord": "fout"},
                    headers={"cf-connecting-ip": f"10.0.0.{i}"}).status_code for i in range(25)]
    assert codes[:20] == [401] * 20
    assert codes[20:] == [429] * 5
