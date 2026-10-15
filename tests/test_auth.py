from app.auth import (
    RateLimiter, controleer_wachtwoord, maak_hash, maak_sessie, sessie_geldig,
)


def test_hash_roundtrip():
    h = maak_hash("blauw", salt=b"0" * 16)
    assert h.startswith("scrypt:") and "$" not in h
    assert controleer_wachtwoord("blauw", h)
    assert not controleer_wachtwoord("rood", h)


def test_hash_rejects_garbage():
    assert not controleer_wachtwoord("blauw", "")
    assert not controleer_wachtwoord("blauw", "scrypt:zz:00")
    assert not controleer_wachtwoord("blauw", "md5:00:00")


def test_sessie_geldig_en_verlopen():
    c = maak_sessie("geheim", nu=1000)
    assert sessie_geldig(c, "geheim", nu=1001)
    assert not sessie_geldig(c, "ander-geheim", nu=1001)
    assert not sessie_geldig(c, "geheim", nu=1000 + 31 * 24 * 3600)


def test_sessie_vervalst():
    verloopt, _, sig = maak_sessie("geheim", nu=1000).partition(".")
    assert not sessie_geldig(f"{int(verloopt) + 999}.{sig}", "geheim", nu=1001)
    assert not sessie_geldig("", "geheim")
    assert not sessie_geldig("abc.def", "geheim")
    assert not sessie_geldig(maak_sessie("geheim"), "")


def test_rate_limiter_window():
    rl = RateLimiter(5, 60)
    assert all(rl.toegestaan("1.2.3.4", nu=t) for t in range(5))
    assert not rl.toegestaan("1.2.3.4", nu=10)
    assert rl.toegestaan("5.6.7.8", nu=10)          # ander IP telt apart
    assert rl.toegestaan("1.2.3.4", nu=61)          # eerste treffer is uit het venster


def test_rate_limiter_aantal():
    rl = RateLimiter(30, 3600)
    assert all(rl.toegestaan("claude", nu=0, aantal=2) for _ in range(15))
    assert not rl.toegestaan("claude", nu=1, aantal=2)
    assert not rl.toegestaan("claude", nu=1, aantal=1)


def test_sessie_niet_ascii_geeft_false():
    from app.auth import sessie_geldig
    assert sessie_geldig("123.é", "geheim") is False
    assert sessie_geldig("²." + "a" * 64, "geheim") is False


def test_ratelimiter_ruimt_lege_sleutels_op():
    from app.auth import RateLimiter
    rl = RateLimiter(5, 60)
    for i in range(100):
        rl.toegestaan(f"ip{i}", nu=0)
    rl.toegestaan("nieuw", nu=1000)
    assert len(rl._treffers) == 1
