import pytest

from quati.core.browser import PlaywrightBrowser
from quati.core.browser import playwright as playwright_module


def test_rejects_unsafe_url_before_launching_browser() -> None:
    browser = PlaywrightBrowser()

    with pytest.raises(ValueError):
        browser.fetch_html("https://127.0.0.1/internal", allowed_hosts=("gupy.io",))

    with pytest.raises(ValueError):
        browser.fetch_json("https://127.0.0.1/internal", allowed_hosts=("inhire.app",))


def test_fetch_json_disables_redirects_and_environment_proxy(monkeypatch) -> None:
    observed: dict[str, object] = {}

    class Response:
        headers = {"content-type": "application/json"}
        is_redirect = False
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        @staticmethod
        def iter_bytes():
            yield b'{"jobsPage": []}'

    class Client:
        def __init__(self, **kwargs: object) -> None:
            observed.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        @staticmethod
        def stream(method: str, url: str, *, headers: dict[str, str]):
            observed["method"] = method
            observed["url"] = url
            observed["headers"] = headers
            return Response()

    monkeypatch.setattr(playwright_module, "validate_public_hostname_resolution", lambda host: None)
    monkeypatch.setattr(playwright_module.httpx, "Client", Client)

    payload = PlaywrightBrowser().fetch_json(
        "https://api.inhire.app/job-posts/public/pages",
        allowed_hosts=("inhire.app",),
        headers={"x-tenant": "empresa"},
    )

    assert payload == {"jobsPage": []}
    assert observed["follow_redirects"] is False
    assert observed["trust_env"] is False
    assert observed["headers"] == {"x-tenant": "empresa"}
