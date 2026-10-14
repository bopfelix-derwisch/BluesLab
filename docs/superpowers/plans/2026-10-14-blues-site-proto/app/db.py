"""BluesLab — SQLite-opslag (BL-2). Alleen stdlib sqlite3.

Akkoorden staan altijd in concert pitch. De regelindeling van de PDF blijft
bewaard: bar.regel (0-based) + song.regelstarts (gedrukte maatnummers).
"""

import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS setlist (
    id INTEGER PRIMARY KEY,
    naam TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS song (
    id INTEGER PRIMARY KEY,
    setlist_id INTEGER NOT NULL REFERENCES setlist(id) ON DELETE CASCADE,
    positie INTEGER NOT NULL,
    titel TEXT NOT NULL,
    artiest TEXT NOT NULL DEFAULT '',
    pdf_path TEXT NOT NULL,
    tempo INTEGER,
    maatsoort TEXT NOT NULL DEFAULT '4/4',
    voortekening INTEGER NOT NULL DEFAULT 0,
    regelstarts TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'gelezen'
);
CREATE TABLE IF NOT EXISTS bar (
    song_id INTEGER NOT NULL REFERENCES song(id) ON DELETE CASCADE,
    nr INTEGER NOT NULL,
    regel INTEGER NOT NULL,
    akkoorden TEXT NOT NULL,
    PRIMARY KEY (song_id, nr)
);
CREATE TABLE IF NOT EXISTS section (
    song_id INTEGER NOT NULL REFERENCES song(id) ON DELETE CASCADE,
    naam TEXT NOT NULL,
    start_bar INTEGER NOT NULL,
    end_bar INTEGER NOT NULL,
    concert_key TEXT NOT NULL,
    key_source TEXT NOT NULL,
    solo_geschikt INTEGER NOT NULL DEFAULT 0,
    reden TEXT NOT NULL DEFAULT ''
);
"""


def verbind(pad: str) -> sqlite3.Connection:
    conn = sqlite3.connect(pad, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


# --- setlists --------------------------------------------------------------
def maak_setlist(conn, naam: str) -> int:
    with conn:
        return conn.execute("INSERT INTO setlist (naam) VALUES (?)", (naam,)).lastrowid


def setlists(conn) -> list:
    rijen = conn.execute(
        "SELECT s.id, s.naam, s.created_at, COUNT(n.id) AS aantal FROM setlist s "
        "LEFT JOIN song n ON n.setlist_id = s.id GROUP BY s.id ORDER BY s.id DESC")
    return [dict(r) for r in rijen]


def setlist(conn, setlist_id: int):
    r = conn.execute("SELECT id, naam, created_at FROM setlist WHERE id = ?",
                     (setlist_id,)).fetchone()
    return dict(r) if r else None


# --- songs -----------------------------------------------------------------
def _schrijf_inhoud(conn, song_id: int, regels: list, delen: list) -> None:
    conn.execute("DELETE FROM bar WHERE song_id = ?", (song_id,))
    conn.execute("DELETE FROM section WHERE song_id = ?", (song_id,))
    nr = 0
    for i, regel in enumerate(regels):
        for maat in regel["maten"]:
            nr += 1
            conn.execute("INSERT INTO bar (song_id, nr, regel, akkoorden) VALUES (?,?,?,?)",
                         (song_id, nr, i, json.dumps(maat, ensure_ascii=False)))
    for d in delen:
        conn.execute(
            "INSERT INTO section (song_id, naam, start_bar, end_bar, concert_key, key_source,"
            " solo_geschikt, reden) VALUES (?,?,?,?,?,?,?,?)",
            (song_id, d["naam"], d["start_maat"], d["eind_maat"], d["concert_key"],
             d["key_source"], int(bool(d.get("solo_geschikt"))), d.get("reden", "")))


def maak_song(conn, setlist_id: int, pdf_path: str, kop: dict, regels: list, delen: list) -> int:
    """Nieuw nummer in één transactie. kop = {titel, artiest, tempo, maatsoort, voortekening}."""
    with conn:
        positie = conn.execute(
            "SELECT COALESCE(MAX(positie), 0) + 1 FROM song WHERE setlist_id = ?",
            (setlist_id,)).fetchone()[0]
        song_id = conn.execute(
            "INSERT INTO song (setlist_id, positie, titel, artiest, pdf_path, tempo, maatsoort,"
            " voortekening, regelstarts, status) VALUES (?,?,?,?,?,?,?,?,?, 'gelezen')",
            (setlist_id, positie, kop["titel"], kop.get("artiest", ""), pdf_path, kop.get("tempo"),
             kop.get("maatsoort", "4/4"), kop.get("voortekening", 0),
             json.dumps([r["start_maat"] for r in regels]))).lastrowid
        _schrijf_inhoud(conn, song_id, regels, delen)
    return song_id


def werk_song_bij(conn, song_id: int, kop: dict, regels: list, delen: list) -> None:
    """Controle opslaan: kop + maten + delen vervangen, status 'gecontroleerd'."""
    with conn:
        conn.execute(
            "UPDATE song SET titel = ?, artiest = ?, tempo = ?, voortekening = ?, regelstarts = ?,"
            " status = 'gecontroleerd' WHERE id = ?",
            (kop["titel"], kop.get("artiest", ""), kop.get("tempo"), kop.get("voortekening", 0),
             json.dumps([r["start_maat"] for r in regels]), song_id))
        _schrijf_inhoud(conn, song_id, regels, delen)


def song(conn, song_id: int):
    """Nummer met regels [{start_maat, maten}] en delen [{naam, start_maat, eind_maat, ...}]."""
    r = conn.execute("SELECT * FROM song WHERE id = ?", (song_id,)).fetchone()
    if not r:
        return None
    s = dict(r)
    starts = json.loads(s.pop("regelstarts"))
    regels = [{"start_maat": start, "maten": []} for start in starts]
    for b in conn.execute("SELECT regel, akkoorden FROM bar WHERE song_id = ? ORDER BY nr",
                          (song_id,)):
        regels[b["regel"]]["maten"].append(json.loads(b["akkoorden"]))
    s["regels"] = regels
    s["delen"] = [
        {"naam": d["naam"], "start_maat": d["start_bar"], "eind_maat": d["end_bar"],
         "concert_key": d["concert_key"], "key_source": d["key_source"],
         "solo_geschikt": bool(d["solo_geschikt"]), "reden": d["reden"]}
        for d in conn.execute("SELECT * FROM section WHERE song_id = ? ORDER BY start_bar",
                              (song_id,))
    ]
    return s


def songs(conn, setlist_id: int) -> list:
    """Nummers van een setlist op volgorde, met de toonsoort van het eerste deel."""
    rijen = conn.execute(
        "SELECT n.id, n.positie, n.titel, n.artiest, n.tempo, n.status,"
        " (SELECT concert_key FROM section WHERE song_id = n.id ORDER BY start_bar LIMIT 1)"
        " AS concert_key FROM song n WHERE n.setlist_id = ? ORDER BY n.positie",
        (setlist_id,))
    return [dict(r) for r in rijen]


def herorden(conn, setlist_id: int, song_ids: list) -> None:
    with conn:
        for positie, song_id in enumerate(song_ids, start=1):
            conn.execute("UPDATE song SET positie = ? WHERE id = ? AND setlist_id = ?",
                         (positie, song_id, setlist_id))


def verwijder_song(conn, song_id: int):
    """Verwijdert het nummer; geeft het pdf-pad terug (of None als het niet bestond)."""
    r = conn.execute("SELECT pdf_path FROM song WHERE id = ?", (song_id,)).fetchone()
    if not r:
        return None
    with conn:
        conn.execute("DELETE FROM song WHERE id = ?", (song_id,))
    return r["pdf_path"]
