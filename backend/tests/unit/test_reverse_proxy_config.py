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


def test_backend_is_not_published_outside_the_reverse_proxy() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert '"8000:8000"' not in compose
    assert (
        "image: nginx:1.27.3-alpine@sha256:"
        "814a8e88df978ade80e584cc5b333144b9372a8e3c98872d07137dbf3b44d0e4" in compose
    )
