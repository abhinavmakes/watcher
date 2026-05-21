import httpx
import pytest
import respx

from app.connectors.hackernews import HN_BASE_URL, HackerNewsConnector


@pytest.mark.asyncio
@respx.mock
async def test_fetch_articles_maps_hn_stories_to_article_input() -> None:
    respx.get(f"{HN_BASE_URL}/topstories.json").mock(
        return_value=httpx.Response(200, json=[101, 102, 103, 104])
    )
    respx.get(f"{HN_BASE_URL}/item/101.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 101,
                "type": "story",
                "by": "alice",
                "time": 1_700_000_000,
                "title": "Useful launch",
                "url": "https://www.example.com/post/?utm_source=hn&ref=keep#comments",
                "score": 120,
                "descendants": 33,
            },
        )
    )
    respx.get(f"{HN_BASE_URL}/item/102.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 102,
                "type": "story",
                "by": "bob",
                "time": 1_700_000_010,
                "title": "Ask HN: How should ingestion work?",
                "text": "Trying to understand source adapters.",
                "score": 42,
                "descendants": 9,
            },
        )
    )
    respx.get(f"{HN_BASE_URL}/item/103.json").mock(
        return_value=httpx.Response(200, json={"id": 103, "type": "comment", "text": "skip me"})
    )
    respx.get(f"{HN_BASE_URL}/item/104.json").mock(
        return_value=httpx.Response(
            200,
            json={"id": 104, "type": "story", "dead": True, "title": "skip me too"},
        )
    )

    async with httpx.AsyncClient() as client:
        articles = await HackerNewsConnector(client).fetch_articles(limit=4)

    assert len(articles) == 2
    assert articles[0].source == "hn"
    assert articles[0].title == "Useful launch"
    assert str(articles[0].url) == "https://www.example.com/post/?utm_source=hn&ref=keep#comments"
    assert articles[0].canonical_url == "https://example.com/post?ref=keep"
    assert articles[0].source_metadata == {
        "hn_id": 101,
        "author": "alice",
        "score": 120,
        "comment_count": 33,
        "discussion_url": "https://news.ycombinator.com/item?id=101",
    }

    assert str(articles[1].url) == "https://news.ycombinator.com/item?id=102"
    assert articles[1].canonical_url == "https://news.ycombinator.com/item?id=102"
    assert articles[1].content == "Trying to understand source adapters."


@pytest.mark.asyncio
@respx.mock
async def test_fetch_articles_skips_failed_item_requests() -> None:
    respx.get(f"{HN_BASE_URL}/topstories.json").mock(
        return_value=httpx.Response(200, json=[201, 202])
    )
    respx.get(f"{HN_BASE_URL}/item/201.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 201,
                "type": "story",
                "title": "Working story",
                "url": "https://example.com/working",
            },
        )
    )
    respx.get(f"{HN_BASE_URL}/item/202.json").mock(return_value=httpx.Response(503))

    async with httpx.AsyncClient() as client:
        articles = await HackerNewsConnector(client).fetch_articles(limit=2)

    assert [article.title for article in articles] == ["Working story"]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_articles_returns_empty_for_unexpected_topstories_payload() -> None:
    respx.get(f"{HN_BASE_URL}/topstories.json").mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )

    async with httpx.AsyncClient() as client:
        articles = await HackerNewsConnector(client).fetch_articles(limit=10)

    assert articles == []


@pytest.mark.asyncio
@respx.mock
async def test_fetch_articles_raises_when_topstories_request_fails() -> None:
    respx.get(f"{HN_BASE_URL}/topstories.json").mock(return_value=httpx.Response(503))

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.HTTPStatusError):
            await HackerNewsConnector(client).fetch_articles(limit=10)
