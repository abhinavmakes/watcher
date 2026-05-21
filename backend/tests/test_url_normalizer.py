from app.services.url_normalizer import normalize_url


def test_normalize_url_removes_tracking_noise() -> None:
    assert (
        normalize_url("https://www.Example.com:443/posts/ai-agents/?utm_source=hn&ref=keep#section")
        == "https://example.com/posts/ai-agents?ref=keep"
    )


def test_normalize_url_preserves_identity_query_params() -> None:
    assert normalize_url("https://example.com/article?id=123&utm_campaign=test") == (
        "https://example.com/article?id=123"
    )


def test_normalize_url_adds_default_scheme() -> None:
    assert normalize_url("www.example.com/path/") == "https://example.com/path"
