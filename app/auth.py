"""BluesLab — wachtwoord, sessiecookie en rate-limits (BL-2). Alleen stdlib.

Wachtwoord-hash in .env.secrets (BLUESLAB_PASSWORD_HASH; ':' i.p.v. '$' zodat
shell/systemd niets expanderen): "scrypt:<salt-hex>:<hash-hex>".
Maak er een met:  .venv/bin/python -m app.auth
Sessie = cookie "<verloopt-epoch>.<hmac-sha256-hex>" ondertekend met BLUESLAB_SECRET.
"""

import getpass
import hashlib
import hmac
import os
import time
from collections import defaultdict, deque

SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}
SESSIE_DUUR = 30 * 24 * 3600
COOKIE = "blueslab_sessie"


def maak_hash(wachtwoord: str, salt: bytes = None) -> str:
    salt = salt if salt is not None else os.urandom(16)
    h = hashlib.scrypt(wachtwoord.encode(), salt=salt, **SCRYPT)
    return f"scrypt:{salt.hex()}:{h.hex()}"


def controleer_wachtwoord(wachtwoord: str, opgeslagen: str) -> bool:
    try:
        soort, salt_hex, hash_hex = opgeslagen.split(":")
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    if soort != "scrypt":
        return False
    h = hashlib.scrypt(wachtwoord.encode(), salt=salt, **SCRYPT)
    return hmac.compare_digest(h.hex(), hash_hex)


def _teken(secret: str, tekst: str) -> str:
    return hmac.new(secret.encode(), tekst.encode(), hashlib.sha256).hexdigest()


def maak_sessie(secret: str, nu: float = None) -> str:
    verloopt = int((nu if nu is not None else time.time()) + SESSIE_DUUR)
    return f"{verloopt}.{_teken(secret, str(verloopt))}"


def sessie_geldig(cookie: str, secret: str, nu: float = None) -> bool:
    if not cookie or not secret:
        return False
    verloopt, _, handtekening = cookie.partition(".")
    # isascii: compare_digest geeft TypeError op niet-ASCII, en isdigit accepteert ook '²'.
    if not (cookie.isascii() and verloopt.isdigit()):
        return False
    if not hmac.compare_digest(_teken(secret, verloopt), handtekening):
        return False
    return int(verloopt) > (nu if nu is not None else time.time())


class RateLimiter:
    """Schuivend venster in geheugen: max `maximum` treffers per `venster` seconden per sleutel."""

    def __init__(self, maximum: int, venster: float):
        self.maximum = maximum
        self.venster = venster
        self._treffers = defaultdict(deque)

    def toegestaan(self, sleutel: str, nu: float = None, aantal: int = 1) -> bool:
        """Registreert `aantal` treffers als dat binnen de limiet past; anders False."""
        nu = nu if nu is not None else time.monotonic()
        # Verlopen treffers en lege sleutels opruimen, zodat het geheugen niet per IP groeit.
        for k in list(self._treffers):
            oud = self._treffers[k]
            while oud and oud[0] <= nu - self.venster:
                oud.popleft()
            if not oud:
                del self._treffers[k]
        q = self._treffers[sleutel]
        if len(q) + aantal > self.maximum:
            return False
        q.extend([nu] * aantal)
        return True


if __name__ == "__main__":
    eerste = getpass.getpass("Nieuw wachtwoord: ")
    if eerste != getpass.getpass("Nog een keer: "):
        raise SystemExit("Wachtwoorden verschillen.")
    print(f"BLUESLAB_PASSWORD_HASH={maak_hash(eerste)}")
