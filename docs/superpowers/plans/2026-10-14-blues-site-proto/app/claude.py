"""BluesLab — Claude-aanroepen (BL-2): PDF -> maten, en maten -> delen.

Structured output (output_config.format = json_schema) garandeert geldige JSON.
De engine (core/) controleert alles wat hieruit komt; Claude rekent niet.
"""

import base64
import json
import os
import re

import anthropic

MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 16000
DEEL_NAMEN = ["Intro", "Couplet", "Refrein", "Brug", "Solo", "Outro"]


class ClaudeFout(Exception):
    """Fout met een Nederlandse melding voor de gebruiker."""


LEES_SCHEMA = {
    "type": "object",
    "properties": {
        "titel": {"type": "string"},
        "artiest": {"type": "string"},
        "tempo": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "maatsoort": {"type": "string"},
        "voortekening": {"type": "integer"},
        "regels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_maat": {"type": "integer"},
                    "maten": {"type": "array",
                              "items": {"type": "array", "items": {"type": "string"}}},
                },
                "required": ["start_maat", "maten"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["titel", "artiest", "tempo", "maatsoort", "voortekening", "regels"],
    "additionalProperties": False,
}

LEES_PROMPT = """Dit is een Chordify-PDF: bladmuziek voor piano met akkoordnamen boven de notenbalk.
Lees het volledige akkoordenschema uit, regel voor regel, precies zoals het gedrukt staat.

- titel: alleen de songtitel, zonder artiest en zonder toevoegingen tussen haakjes
  (dus niet "(Acoustic version)" of "(Official Music Video)").
- artiest: de artiest(en) zoals in de kop.
- tempo: het getal achter de kwartnoot (♩ = ...), of null als het er niet staat.
- maatsoort: bijvoorbeeld "4/4" (C = 4/4, ₵ = 2/2).
- voortekening: aantal kruizen als positief getal, aantal mollen als negatief (5 mollen = -5).
- regels: één item per notenbalkregel. start_maat = het maatnummer links van de regel
  (de eerste regel begint bij 1). maten = per maat de akkoordnamen in volgorde.
  Een maat zonder nieuw akkoord bevat het akkoord dat doorklinkt (herhaal het).
  Schrijf ♭ als "b" en ♯ als "#" (B♭m -> "Bbm"), superscript als gewone tekst
  (A♭ met sus4 -> "Absus4") en "N.C." voor geen akkoord.
Tel de maten per regel zorgvuldig aan de maatstrepen."""

STRUCTUUR_SCHEMA = {
    "type": "object",
    "properties": {
        "delen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "naam": {"type": "string", "enum": DEEL_NAMEN},
                    "start_maat": {"type": "integer"},
                    "eind_maat": {"type": "integer"},
                    "toonsoort": {"type": "string"},
                    "solo_geschikt": {"type": "boolean"},
                    "reden": {"type": "string"},
                },
                "required": ["naam", "start_maat", "eind_maat", "toonsoort",
                             "solo_geschikt", "reden"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["delen"],
    "additionalProperties": False,
}

STRUCTUUR_PROMPT = """Nummer: {titel} — {artiest}. Voortekening: {voortekening} (negatief = mollen).
Hieronder het akkoordenschema in concert pitch, één maat per regel ("maatnummer: akkoorden").

{maten}

Deel het nummer in delen in (namen: {namen}). Gebruik je kennis van het nummer
(bijvoorbeeld waar de gitaarsolo zit) en de herhalingen in het schema.
- De delen sluiten op elkaar aan en dekken maat 1 tot en met {aantal}.
- toonsoort: de concert-toonsoort van dat deel, bijv. "Bbm" of "Db" ("b" voor mol, "m" voor mineur).
  Let op toonsoortwisselingen binnen het nummer.
- solo_geschikt: true als een blazer hier goed kan soleren.
- reden: één korte zin in het Nederlands."""


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("BLUESLAB_ANTHROPIC_API_KEY"),
                                      timeout=180.0, max_retries=2)
    return _client


def _vraag(content, schema: dict, client=None) -> dict:
    client = client or _get_client()
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.APITimeoutError as exc:
        raise ClaudeFout("Claude reageerde niet op tijd. Probeer het opnieuw.") from exc
    except anthropic.APIError as exc:
        raise ClaudeFout(f"Claude gaf een fout ({type(exc).__name__}). Probeer het opnieuw.") from exc
    if resp.stop_reason == "refusal":
        raise ClaudeFout("Claude weigerde deze PDF te verwerken.")
    if resp.stop_reason == "max_tokens":
        raise ClaudeFout("Het antwoord van Claude was te lang en is afgebroken.")
    tekst = next((b.text for b in resp.content if b.type == "text"), None)
    if tekst is None:
        raise ClaudeFout("Claude gaf geen antwoord.")
    try:
        return json.loads(tekst)
    except json.JSONDecodeError as exc:
        raise ClaudeFout("Claude gaf onleesbare uitvoer.") from exc


def schoon_titel(titel: str) -> str:
    """Haalt toevoegingen tussen haakjes weg: 'Crazy (Acoustic version)' -> 'Crazy'."""
    return re.sub(r"\s*\([^)]*\)", "", titel).strip() or titel.strip()


def lees_pdf(pdf: bytes, client=None) -> dict:
    """PDF -> {titel, artiest, tempo, maatsoort, voortekening, regels: [{start_maat, maten}]}."""
    content = [
        {"type": "document",
         "source": {"type": "base64", "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf).decode("ascii")}},
        {"type": "text", "text": LEES_PROMPT},
    ]
    data = _vraag(content, LEES_SCHEMA, client)
    data["titel"] = schoon_titel(data["titel"])
    if not data["regels"]:
        raise ClaudeFout("Claude vond geen akkoorden in deze PDF.")
    return data


def structuur(titel: str, artiest: str, voortekening: int, maten: list, client=None) -> list:
    """Maten (concert) -> [{naam, start_maat, eind_maat, toonsoort, solo_geschikt, reden}]."""
    regels = "\n".join(f"{i}: {' '.join(maat)}" for i, maat in enumerate(maten, start=1))
    tekst = STRUCTUUR_PROMPT.format(titel=titel, artiest=artiest, voortekening=voortekening,
                                    maten=regels, namen=", ".join(DEEL_NAMEN), aantal=len(maten))
    return _vraag(tekst, STRUCTUUR_SCHEMA, client)["delen"]
