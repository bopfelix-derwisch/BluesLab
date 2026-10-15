"""BluesLab — FastAPI-app (BL-2).

Start:  .venv/bin/uvicorn app.main:maak_app --factory --host 127.0.0.1 --port 8796
Instellingen uit de omgeving (.env + .env.secrets): BLUESLAB_DATA, BLUESLAB_PASSWORD_HASH,
BLUESLAB_SECRET, BLUESLAB_ANTHROPIC_API_KEY.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import auth, db
from app.claude import ClaudeFout
from core.analysis import (
    check_bar_count, check_sections, detect_sections, flatten, key_dict,
    key_for_section, parse_key, same_key, speelschema, written_key_name,
)
from core.chords import parse_chord

ROOT = Path(__file__).resolve().parent.parent
MAX_PDF = 10 * 1024 * 1024
log = logging.getLogger("uvicorn.error.blueslab")  # erft de handler van uvicorn → journal
VOICE = {"bb": "bb_clarinet", "eb": "eb_alto_sax"}


class Login(BaseModel):
    wachtwoord: str


class NieuweSetlist(BaseModel):
    naam: str


class Volgorde(BaseModel):
    song_ids: list[int]


class Regel(BaseModel):
    start_maat: int
    maten: list[list[str]]


class Deel(BaseModel):
    naam: str
    start_maat: int
    eind_maat: int
    concert_key: str
    key_source: Literal["claude", "engine", "handmatig"]
    solo_geschikt: bool = False
    reden: str = ""


class Controle(BaseModel):
    titel: str
    artiest: str = ""
    tempo: Optional[int] = None
    voortekening: int = 0
    regels: list[Regel]
    delen: list[Deel]


def engine_key(maten: list, voortekening: int) -> dict:
    """Toonsoort volgens de engine; zonder akkoorden de majeur van de voortekening."""
    try:
        return key_for_section(maten, voortekening)
    except ValueError:
        return key_dict((voortekening * 7) % 12, "maj", voortekening)


def bepaal_delen(claude, gelezen: dict, maten: list) -> list:
    """Delen via Claude-aanroep 2; bij een fout of gaten: detect_sections als fallback."""
    vt = gelezen["voortekening"]
    try:
        voorstel = claude.structuur(gelezen["titel"], gelezen["artiest"], vt, maten)
        if check_sections(voorstel, len(maten)):
            voorstel = None
    except ClaudeFout:
        voorstel = None
    if voorstel is None:
        voorstel = [dict(d, toonsoort="", solo_geschikt=False,
                         reden="Automatisch ingedeeld op herhaling.")
                    for d in detect_sections(maten)]
    delen = []
    for d in voorstel:
        deel_maten = maten[d["start_maat"] - 1:d["eind_maat"]]
        try:
            key_for_section(deel_maten, vt)
            zonder_akkoorden = False
        except ValueError:
            zonder_akkoorden = True
        try:
            if zonder_akkoorden:  # alleen N.C./leeg: Claude's toonsoort is dan een gok
                raise ValueError
            key, bron = parse_key(d.get("toonsoort") or ""), "claude"
        except ValueError:
            key, bron = engine_key(deel_maten, vt), "engine"
        delen.append({"naam": d["naam"], "start_maat": d["start_maat"],
                      "eind_maat": d["eind_maat"], "concert_key": key["naam"],
                      "key_source": bron, "solo_geschikt": bool(d.get("solo_geschikt")),
                      "reden": d.get("reden", "")})
    return delen


def verrijk(song: dict) -> dict:
    """Voegt controle-informatie toe: telling per regel, onparseerbare akkoorden, engine-toonsoort."""
    maten = flatten(song["regels"])
    song["telling"] = check_bar_count(song["regels"])
    onparseerbaar = []
    for nr, maat in enumerate(maten, start=1):
        for tekst in maat:
            try:
                parse_chord(tekst)
            except ValueError:
                onparseerbaar.append({"maat": nr, "akkoord": tekst})
    song["onparseerbaar"] = onparseerbaar
    for deel in song["delen"]:
        eng = engine_key(maten[deel["start_maat"] - 1:deel["eind_maat"]], song["voortekening"])
        deel["engine_key"] = eng["naam"]
        deel["afwijking"] = not same_key(eng, parse_key(deel["concert_key"]))
    song["aantal_maten"] = len(maten)
    return song


def sleutels(concert_key) -> dict:
    if not concert_key:
        return {"bb": None, "eb": None}
    key = parse_key(concert_key)
    return {inst: written_key_name(key, voice) for inst, voice in VOICE.items()}


def maak_app(instellingen: dict = None) -> FastAPI:
    inst = instellingen or {}
    data_dir = Path(inst.get("data_dir") or os.environ.get("BLUESLAB_DATA") or ROOT / "data")
    password_hash = inst.get("password_hash") or os.environ.get("BLUESLAB_PASSWORD_HASH")
    secret = inst.get("secret") or os.environ.get("BLUESLAB_SECRET")
    if not password_hash or not secret:
        raise RuntimeError("BLUESLAB_PASSWORD_HASH en BLUESLAB_SECRET moeten gezet zijn "
                           "(zie .env.example).")
    claude = inst.get("claude")
    if claude is None:
        from app import claude as claude_module
        claude = claude_module
    web_dir = Path(inst.get("web_dir") or ROOT / "web")
    uploads = data_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    db_pad = str(data_dir / "blueslab.sqlite")

    login_limiet = auth.RateLimiter(5, 60)
    login_globaal = auth.RateLimiter(20, 60)  # één account: ook over alle IP's samen begrenzen
    claude_limiet = auth.RateLimiter(30, 3600)

    def conn_dep():
        conn = db.verbind(db_pad)
        try:
            yield conn
        finally:
            conn.close()

    def vereis_login(request: Request):
        if not auth.sessie_geldig(request.cookies.get(auth.COOKIE, ""), secret):
            raise HTTPException(401, "Log eerst in.")

    app = FastAPI(title="BluesLab", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def poortwachter(request: Request, call_next):
        # Vóór FastAPI de body leest: te grote verzoeken en niet-ingelogde API-aanroepen weigeren.
        pad = request.url.path
        if pad.startswith("/api/"):
            lengte = request.headers.get("content-length", "")
            if lengte.isdigit() and int(lengte) > MAX_PDF + 1024 * 1024:
                return JSONResponse({"detail": "Het verzoek is groter dan 10 MB."}, status_code=413)
            cookie = request.cookies.get(auth.COOKIE, "")
            if pad not in ("/api/login", "/api/logout") and not auth.sessie_geldig(cookie, secret):
                # Alleen de reden loggen, nooit de waarde.
                log.info("401 %s: %s", pad, "ongeldige cookie" if cookie else
                         f"geen cookie (cookienamen: {sorted(request.cookies) or 'geen'})")
                return JSONResponse({"detail": "Log eerst in."}, status_code=401)
        return await call_next(request)

    def probeer_login(request: Request, wachtwoord: str) -> Optional[str]:
        """None bij succes, anders 'limiet' of 'wachtwoord'."""
        ip = request.headers.get("cf-connecting-ip") or (
            request.client.host if request.client else "onbekend")
        if not (login_limiet.toegestaan(ip) and login_globaal.toegestaan("alle")):
            return "limiet"
        if not auth.controleer_wachtwoord(wachtwoord, password_hash):
            return "wachtwoord"
        return None

    def zet_sessie(response: Response):
        response.set_cookie(auth.COOKIE, auth.maak_sessie(secret), max_age=auth.SESSIE_DUUR,
                            httponly=True, secure=True, samesite="lax")

    @app.post("/api/login")
    def login(body: Login, request: Request, response: Response):
        fout = probeer_login(request, body.wachtwoord)
        if fout == "limiet":
            raise HTTPException(429, "Te veel pogingen. Wacht een minuut.")
        if fout:
            raise HTTPException(401, "Onjuist wachtwoord.")
        zet_sessie(response)
        return {"ok": True}

    @app.post("/login")
    def login_formulier(request: Request, wachtwoord: str = Form(...)):
        # Gewone formulier-POST + 303: iOS Safari bewaarde de cookie uit een fetch()-antwoord niet.
        fout = probeer_login(request, wachtwoord)
        response = RedirectResponse(f"/?fout={fout}" if fout else "/", status_code=303)
        if not fout:
            zet_sessie(response)
        return response

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie(auth.COOKIE)
        return {"ok": True}

    api = APIRouter(prefix="/api", dependencies=[Depends(vereis_login)])

    @api.get("/ik")
    def ik():
        return {"ok": True}

    @api.get("/setlists")
    def lijst_setlists(conn=Depends(conn_dep)):
        return db.setlists(conn)

    @api.post("/setlists", status_code=201)
    def nieuwe_setlist(body: NieuweSetlist, conn=Depends(conn_dep)):
        naam = body.naam.strip()
        if not naam:
            raise HTTPException(422, "Geef de setlist een naam.")
        return {"id": db.maak_setlist(conn, naam)}

    @api.get("/setlists/{setlist_id}")
    def toon_setlist(setlist_id: int, conn=Depends(conn_dep)):
        s = db.setlist(conn, setlist_id)
        if not s:
            raise HTTPException(404, "Setlist niet gevonden.")
        s["songs"] = [dict(n, sleutels=sleutels(n["concert_key"]))
                      for n in db.songs(conn, setlist_id)]
        return s

    @api.put("/setlists/{setlist_id}/volgorde")
    def volgorde(setlist_id: int, body: Volgorde, conn=Depends(conn_dep)):
        bestaand = sorted(n["id"] for n in db.songs(conn, setlist_id))
        if sorted(body.song_ids) != bestaand:
            raise HTTPException(422, "De volgorde moet precies de nummers van deze setlist bevatten.")
        db.herorden(conn, setlist_id, body.song_ids)
        return {"ok": True}

    @api.post("/setlists/{setlist_id}/songs", status_code=201)
    def upload(setlist_id: int, bestand: UploadFile = File(...), conn=Depends(conn_dep)):
        if not db.setlist(conn, setlist_id):
            raise HTTPException(404, "Setlist niet gevonden.")
        pdf = bestand.file.read(MAX_PDF + 1)
        if len(pdf) > MAX_PDF:
            raise HTTPException(413, "De PDF is groter dan 10 MB.")
        if not pdf.startswith(b"%PDF"):
            raise HTTPException(415, "Dit is geen PDF.")
        if not claude_limiet.toegestaan("claude", aantal=2):
            raise HTTPException(429, "Claude-limiet bereikt (30 per uur). Probeer het later opnieuw.")
        try:
            gelezen = claude.lees_pdf(pdf)
        except ClaudeFout as exc:
            raise HTTPException(502, str(exc))
        maten = flatten(gelezen["regels"])
        delen = bepaal_delen(claude, gelezen, maten)
        pad = uploads / f"{uuid.uuid4().hex}.pdf"
        pad.write_bytes(pdf)
        try:
            song_id = db.maak_song(conn, setlist_id, str(pad), gelezen, gelezen["regels"], delen)
        except Exception:
            pad.unlink(missing_ok=True)
            raise
        return {"id": song_id}

    @api.get("/songs/{song_id}")
    def toon_song(song_id: int, conn=Depends(conn_dep)):
        s = db.song(conn, song_id)
        if not s:
            raise HTTPException(404, "Nummer niet gevonden.")
        s.pop("pdf_path")
        return verrijk(s)

    @api.put("/songs/{song_id}")
    def controleer(song_id: int, body: Controle, conn=Depends(conn_dep)):
        if not db.song(conn, song_id):
            raise HTTPException(404, "Nummer niet gevonden.")
        titel = body.titel.strip()
        if not titel:
            raise HTTPException(422, "Geef het nummer een titel.")
        regels = [{"start_maat": r.start_maat,
                   "maten": [[a.strip() for a in maat if a.strip()] for maat in r.maten]}
                  for r in body.regels]
        maten = flatten(regels)
        if not maten:
            raise HTTPException(422, "Het nummer heeft geen maten.")
        delen = [d.model_dump() for d in body.delen]
        problemen = check_sections(delen, len(maten))
        for d in delen:
            try:
                d["concert_key"] = parse_key(d["concert_key"])["naam"]
            except ValueError as exc:
                problemen.append(f"{d['naam']}: {exc}")
        if problemen:
            raise HTTPException(422, problemen)
        kop = {"titel": titel, "artiest": body.artiest.strip(), "tempo": body.tempo,
               "voortekening": body.voortekening}
        db.werk_song_bij(conn, song_id, kop, regels, delen)
        return {"ok": True}

    @api.delete("/songs/{song_id}")
    def verwijder(song_id: int, conn=Depends(conn_dep)):
        pad = db.verwijder_song(conn, song_id)
        if pad is None:
            raise HTTPException(404, "Nummer niet gevonden.")
        Path(pad).unlink(missing_ok=True)
        return {"ok": True}

    @api.get("/songs/{song_id}/schema")
    def schema(song_id: int, instrument: Literal["bb", "eb"] = "bb", conn=Depends(conn_dep)):
        s = db.song(conn, song_id)
        if not s:
            raise HTTPException(404, "Nummer niet gevonden.")
        voice = VOICE[instrument]
        delen = speelschema(flatten(s["regels"]), s["delen"], voice)
        return {
            "id": s["id"], "setlist_id": s["setlist_id"],
            "titel": s["titel"], "artiest": s["artiest"], "tempo": s["tempo"],
            "maatsoort": s["maatsoort"], "status": s["status"], "instrument": instrument,
            "concert_key": delen[0]["concert_key"] if delen else None,
            "geschreven_key": delen[0]["geschreven_key"] if delen else None,
            "delen": delen,
        }

    app.include_router(api)
    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
    return app
