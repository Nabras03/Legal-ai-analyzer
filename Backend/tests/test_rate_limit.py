from types import SimpleNamespace

from rate_limit import DAY, MINUTE, RateLimiter, client_ip


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


def limiter(**limits):
    clock = Clock()
    return RateLimiter(**({"per_minute": 2, "per_day": 3, "global_per_day": 5} | limits), clock=clock), clock


def test_per_minute_limit_resets_after_a_minute():
    rl, clock = limiter()
    assert rl.check("a") is None
    assert rl.check("a") is None
    assert "per minute" in rl.check("a")
    clock.now += MINUTE + 1
    assert rl.check("a") is None


def test_per_day_limit():
    rl, clock = limiter()
    for _ in range(3):
        assert rl.check("a") is None
        clock.now += MINUTE + 1
    assert "per day" in rl.check("a")
    clock.now += DAY
    assert rl.check("a") is None


def test_ips_are_counted_separately_but_share_the_global_cap():
    rl, clock = limiter(per_minute=10)
    for _ in range(3):
        assert rl.check("a") is None
    assert "per day" in rl.check("a")      # a used its 3; b is unaffected
    assert rl.check("b") is None
    assert rl.check("b") is None
    assert "daily limit" in rl.check("c")  # global 5 reached, even for a new IP


def test_refused_requests_are_not_counted():
    rl, clock = limiter()
    rl.check("a"), rl.check("a")
    for _ in range(10):
        rl.check("a")                       # refused, per-minute
    clock.now += MINUTE + 1
    assert rl.check("a") is None            # day count is still 2, not 12


def test_client_ip_prefers_forwarded_header():
    req = SimpleNamespace(headers={"x-forwarded-for": "203.0.113.7, 10.0.0.1"}, client=SimpleNamespace(host="10.0.0.2"))
    assert client_ip(req) == "203.0.113.7"
    req = SimpleNamespace(headers={}, client=SimpleNamespace(host="10.0.0.2"))
    assert client_ip(req) == "10.0.0.2"
