import pytest

from app import db

KOP = {"titel": "Crazy", "artiest": "Lost Frequencies", "tempo": 103,
       "maatsoort": "4/4", "voortekening": -5}
REGELS = [{"start_maat": 1, "maten": [["Bbm"], ["Gb", "Db"]]},
          {"start_maat": 3, "maten": [["Ab"]]}]
DELEN = [{"naam": "Intro", "start_maat": 1, "eind_maat": 3, "concert_key": "Bbm",
          "key_source": "claude", "solo_geschikt": True, "reden": "Opening."}]


@pytest.fixture
def conn(tmp_path):
    c = db.verbind(str(tmp_path / "t.sqlite"))
    yield c
    c.close()


def test_setlists(conn):
    a = db.maak_setlist(conn, "Next week")
    db.maak_setlist(conn, "Later")
    lijst = db.setlists(conn)
    assert [s["naam"] for s in lijst] == ["Later", "Next week"]
    assert db.setlist(conn, a)["naam"] == "Next week"
    assert db.setlist(conn, 999) is None


def test_song_roundtrip(conn):
    sl = db.maak_setlist(conn, "Next week")
    sid = db.maak_song(conn, sl, "/x.pdf", KOP, REGELS, DELEN)
    s = db.song(conn, sid)
    assert (s["titel"], s["tempo"], s["voortekening"], s["status"]) == ("Crazy", 103, -5, "gelezen")
    assert s["regels"] == REGELS
    assert s["delen"] == DELEN
    assert db.songs(conn, sl)[0]["concert_key"] == "Bbm"


def test_werk_song_bij(conn):
    sl = db.maak_setlist(conn, "Next week")
    sid = db.maak_song(conn, sl, "/x.pdf", KOP, REGELS, DELEN)
    nieuw = [{"start_maat": 1, "maten": [["Bbm"], ["Gb"], ["Db"]]}]
    delen = [dict(DELEN[0], concert_key="Db", key_source="handmatig")]
    db.werk_song_bij(conn, sid, dict(KOP, titel="Crazy!"), nieuw, delen)
    s = db.song(conn, sid)
    assert (s["titel"], s["status"]) == ("Crazy!", "gecontroleerd")
    assert s["regels"] == nieuw
    assert s["delen"][0]["key_source"] == "handmatig"


def test_volgorde_en_verwijderen(conn):
    sl = db.maak_setlist(conn, "Next week")
    a = db.maak_song(conn, sl, "/a.pdf", KOP, REGELS, DELEN)
    b = db.maak_song(conn, sl, "/b.pdf", dict(KOP, titel="Tweede"), REGELS, DELEN)
    assert [n["id"] for n in db.songs(conn, sl)] == [a, b]
    db.herorden(conn, sl, [b, a])
    assert [n["id"] for n in db.songs(conn, sl)] == [b, a]
    assert db.verwijder_song(conn, a) == "/a.pdf"
    assert db.song(conn, a) is None
    assert db.verwijder_song(conn, a) is None
    assert conn.execute("SELECT COUNT(*) FROM bar WHERE song_id = ?", (a,)).fetchone()[0] == 0


def test_unicode_akkoorden_bewaard(conn):
    sl = db.maak_setlist(conn, "x")
    sid = db.maak_song(conn, sl, "/x.pdf", KOP, [{"start_maat": 1, "maten": [["B♭m"]]}],
                       [dict(DELEN[0], eind_maat=1)])
    assert db.song(conn, sid)["regels"][0]["maten"] == [["B♭m"]]
