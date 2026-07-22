"""Static checks for the context and trusted-client-header deployment snippets."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent


def check_contexts(site: str, http: str) -> None:
    """Ensure limit zones are only in the standalone http-context fragment."""
    assert "limit_req_zone" not in site
    assert "limit_req_zone" in http
    assert "server {" in site
    assert "server {" not in http


def check_proxy_headers(site: str, headers: str) -> None:
    """Ensure every API proxy location uses the trusted replacement header snippet."""
    proxy_locations = site.count("proxy_pass http://127.0.0.1:8000;")
    includes = site.count("include /etc/nginx/snippets/quiz-proxy-headers.conf;")
    assert proxy_locations == includes
    forwarded = [
        line.strip()
        for line in headers.splitlines()
        if line.strip().startswith("proxy_set_header X-Forwarded-For")
    ]
    assert forwarded == ["proxy_set_header X-Forwarded-For $remote_addr;"]


def main() -> int:
    """Run static checks when nginx is unavailable in the development environment."""
    site = (ROOT / "nginx.conf.example").read_text(encoding="utf-8")
    http = (ROOT / "nginx.http.conf.example").read_text(encoding="utf-8")
    headers = (ROOT / "nginx.proxy-headers.conf.example").read_text(encoding="utf-8")
    check_contexts(site, http)
    check_proxy_headers(site, headers)
    print("nginx example static checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
