from pathlib import Path

ROOT = Path(__file__).parents[3]


def test_reverse_proxy_re_resolves_compose_upstreams() -> None:
    config = (ROOT / "infrastructure" / "nginx" / "default.conf").read_text(encoding="utf-8")

    assert "resolver 127.0.0.11 valid=10s ipv6=off;" in config
    assert "set $backend_upstream http://backend:8000;" in config
    assert "set $frontend_upstream http://frontend:8080;" in config
    assert "proxy_pass $backend_upstream;" in config
    assert "proxy_pass $frontend_upstream;" in config
    assert "proxy_pass http://backend:8000;" not in config
    assert "proxy_pass http://frontend:8080;" not in config
