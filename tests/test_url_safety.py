import pytest

from quati.core.browser.url_safety import (
    validate_public_hostname_resolution,
    validate_public_https_url,
)


def test_normalizes_https_url_and_removes_fragment() -> None:
    assert (
        validate_public_https_url(" https://PORTAL.GUPY.IO/vaga?a=1#section", ("gupy.io",))
        == "https://portal.gupy.io/vaga?a=1"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://gupy.io/jobs",
        "https://user:secret@gupy.io/jobs",  # pragma: allowlist secret
        "https://gupy.io:8443/jobs",
        "https://127.0.0.1/jobs",
        "https://localhost/jobs",
        "https://evil.example/jobs",
    ],
)
def test_rejects_unsafe_or_non_allowed_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_public_https_url(url, ("gupy.io",))


def test_allows_subdomains_only_for_approved_domain() -> None:
    assert validate_public_https_url("https://acme.gupy.io/jobs", ("gupy.io",))


def test_rejects_localhost_without_a_domain_allowlist() -> None:
    with pytest.raises(ValueError):
        validate_public_https_url("https://localhost/jobs")


def test_dns_resolution_rejects_private_addresses() -> None:
    def private_resolver(*args: object, **kwargs: object) -> list[tuple]:
        return [(2, 1, 6, "", ("127.0.0.1", 443))]

    with pytest.raises(ValueError, match="não pública"):
        validate_public_hostname_resolution("models.example", resolver=private_resolver)


def test_dns_resolution_accepts_only_public_addresses() -> None:
    def public_resolver(*args: object, **kwargs: object) -> list[tuple]:
        return [(2, 1, 6, "", ("8.8.8.8", 443))]

    validate_public_hostname_resolution("models.example", resolver=public_resolver)
