# BluesLab — blazersfills per maat

**Datum:** 2026-10-31 · **Status:** ontwerp · **Bouwt op:** stijlen per nummer (`2026-10-16-stijlen-drums-design.md`, branch `stijlen-drums`)

## 1. Doel

Bob speelt in de band de blazerspartij. Uit de Demucs-stems van Spooky ("Other") zijn de
blazersfills per maat uitgelezen, maar automatisch, dus ongeveer. Gekozen in de chat:
- per maat een **fill** (een rijtje nootnamen) op de songpagina, **geschreven voor het gekozen
  instrument** (Bes klarinet of alt sax);
- **aanpasbaar**: Bob verbetert op het gehoor wat niet klopt en kan fills bij andere nummers
  zetten;
- Spooky wordt na de bouw **eenmalig gevuld** met de uitgelezen fills (geen code).

**Succes:** op de Spooky-pagina staat bij maat 40 (concert D–E♭–D) voor klarinet `♪ E–F–E` en voor
alt sax `♪ B–C–B`; Bob zet de bewerkstand aan, tikt op een maat, typt `D D# E` en ziet de fill meteen;
na het wisselen naar alt sax staat dezelfde fill goed geschreven.

**Niet in deze versie:** ritme of octaaf, fills laten meeklinken in de begeleiding, fills
automatisch uit stems halen.

## 2. Noten (`core/chords.py`, stdlib-only)

- Een noot is intern **concert** `[pc, letter]` (pitch class 0–11, letterindex 0–6 in
  `LETTERS`), zoals de grondtoon van een akkoord. De letter bewaart Bobs spelling: geschreven
  D♯ op klarinet wordt concert C♯ en op alt sax A♯ — nooit een andere letter.
- `parse_fill(tekst: str, voice: str) -> list` — tekst zoals Bob hem typt, **geschreven** voor
  `voice` → lijst concert `[pc, letter]`.
  - Scheidingstekens: spaties, komma's, `-` en `–`. Lege tekst → `[]`.
  - Een noot: letter `A`–`G` (kleine letter mag; wordt hoofdletter) plus hooguit één voorteken
    `#`, `♯`, `b`, `♭`. Dus `bb` = B♭, `eb` = E♭.
  - Fout → `ValueError` met een Nederlandse melding: `Onbekende noot: 'H'.`; meer dan 32 noten →
    `Te veel noten (max. 32).`
  - Terugrekenen: `pc - VOICES[voice]`, `letter - VOICE_LETTERS[voice]` (beide modulo).
- `fill_names(noten: list, voice: str) -> list` — concert `[pc, letter]` → geschreven namen via
  `transpose_note` + `note_name` (bv. `["E", "F", "E"]`). Dubbele voortekens vallen terug op de
  mol-spelling van `note_name`; dat is goed genoeg (MVP).

## 3. Opslag (`app/db.py`)

- Nieuwe tabel, **los van `bar`** (de controlepagina schrijft alle maten opnieuw weg; fills moeten
  dat overleven):
  ```sql
  CREATE TABLE IF NOT EXISTS fill (
      song_id INTEGER NOT NULL REFERENCES song(id) ON DELETE CASCADE,
      nr INTEGER NOT NULL,
      noten TEXT NOT NULL,          -- JSON: [[pc, letter], ...] concert
      PRIMARY KEY (song_id, nr)
  );
  ```
  Staat in `SCHEMA`, dus `CREATE TABLE IF NOT EXISTS` maakt hem ook in een bestaande database
  (geen ALTER nodig).
- `zet_fill(conn, song_id, nr, noten) -> bool` — `noten == []` verwijdert de rij; `False` als het
  nummer niet bestaat.
- `fills(conn, song_id) -> dict` — `{nr: [[pc, letter], ...]}`.
- Fills op een maatnummer dat (na een controle) niet meer bestaat, blijven staan maar worden niet
  getoond.

## 4. API (`app/main.py`)

- `GET /api/songs/{id}/schema`: elke maat krijgt **`fill`**: lijst geschreven namen, of `null`
  zonder fill.
- `PUT /api/songs/{id}/fills/{nr}` met `{"noten": "D D# E", "instrument": "bb"|"eb"}`:
  - `parse_fill` met de voice van het instrument, dan `zet_fill`;
  - antwoord `{"fill": [...geschreven namen voor dat instrument...]}` (`null` na wissen);
  - 400 met de melding van `parse_fill` bij een foute noot; 404 als het nummer niet bestaat of
    `nr` buiten de maten valt (`1 ≤ nr ≤ aantal maten`).

## 5. Songpagina (`web/app.js`, `web/style.css`)

- **Weergave**: in `maatRaster` onder de doeltoon een regel `el("div", {class: "fill"}, "♪ " +
  namen.map(mooi).join("–"))`, alleen als `m.fill` er is. Eigen kleur (CSS-token), ook leesbaar in
  het gemarkeerde (spelende) maatvak.
- **Bewerkstand**: knop **"✎ Fills bewerken"** in de kop (`#kop`), ook zonder Web Audio. Aan →
  de knop heet "✎ Klaar", en een tik op een maat roept `bewerkFill(nr)` aan in plaats van
  `kiesStart(nr)`:
  - `prompt("Fill maat 40 (geschreven voor Bes klarinet), bv. F E:", huidige namen met spaties)`;
  - Annuleren (`null`) → niets; anders `PUT`; bij succes alleen de fill-regel van dat maatvak
    bijwerken (geen herteken van het hele schema, dus de pagina springt niet) en de fill in
    `schema` bijwerken;
  - fout → melding uit het antwoord in `#hulp`, of "Fill niet bewaard." bij een netwerkfout.
- **Herhalingen**: de vingerafdruk in `herhalingen` neemt de fills mee; een refrein met andere
  fills dan het eerste refrein klapt dus niet in ("zoals Refrein …" zou dan niet kloppen).
- `app.js?v=10` in alle `web/*.html`; uitleg in de hulptekst van `song.html`.

## 6. Spooky vullen (eenmalig, na de bouw)

Na de herstart (of direct via `db.verbind`, die de tabel aanmaakt) vul ik songs 1 en 2 met de
uitgelezen fills, in concert: maat 40, 56, 72 `D Eb D`; 41 `D G F G Bb`; 47 `G C`; 49 `F G`;
50 `C C# D`; 78 `G A F G A G`; 81 `F E Eb D`. Dit is data in `data/` (niet in git), geen code.

## 7. Testen

- `tests/test_chords.py`: `parse_fill` (klarinet en alt, kleine letters, scheidingstekens,
  `♯`/`♭`, lege tekst, foute noot, >32 noten) en `fill_names` (heen en terug houdt de spelling).
- `tests/test_db.py`: tabel in een oude database, `zet_fill`/`fills`, wissen, cascade bij
  verwijderen, overleeft `werk_song_bij`.
- `tests/test_api.py`: `fill` in het schema voor bb en eb, PUT goed/fout/404/buiten bereik, wissen.
- `tests/test_web.py` (harness): fill-regel getekend; bewerkstand roept `prompt` aan, stuurt de
  PUT en zet de nieuwe regel; tik buiten bewerkstand zet nog steeds het startpunt; foutmelding in
  `#hulp`; refrein met andere fills klapt niet in.
