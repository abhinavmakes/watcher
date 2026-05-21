import httpx
import pytest
import respx

from app.connectors.rss import RssConnector

FEED_URL = "https://example.com/feed.xml"


def _feed_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>First Post</title>
      <link>https://www.example.com/posts/first/?utm_source=rss&amp;ref=keep</link>
      <guid>first-post</guid>
      <pubDate>Sun, 17 May 2026 10:00:00 GMT</pubDate>
      <description><![CDATA[<p>Hello <strong>RSS</strong></p>]]></description>
      <category>ai</category>
      <category>tools</category>
    </item>
    <item>
      <title>Missing Link</title>
    </item>
  </channel>
</rss>"""


@pytest.mark.asyncio
@respx.mock
async def test_fetch_articles_maps_rss_entries_to_article_input() -> None:
    respx.get(FEED_URL).mock(return_value=httpx.Response(200, content=_feed_xml()))

    async with httpx.AsyncClient() as client:
        articles = await RssConnector(client, [FEED_URL]).fetch_articles(limit=10)

    assert len(articles) == 1
    assert articles[0].source == "rss"
    assert articles[0].title == "First Post"
    assert str(articles[0].url) == "https://www.example.com/posts/first/?utm_source=rss&ref=keep"
    assert articles[0].canonical_url == "https://example.com/posts/first?ref=keep"
    assert articles[0].content == "Hello RSS"
    assert articles[0].published_at is not None
    assert articles[0].source_metadata == {
        "feed_url": FEED_URL,
        "feed_title": "Example Feed",
        "entry_id": "first-post",
        "tags": ["ai", "tools"],
    }


@pytest.mark.asyncio
@respx.mock
async def test_fetch_articles_skips_failed_feeds() -> None:
    working_feed_url = "https://example.com/working.xml"
    failed_feed_url = "https://example.com/failing.xml"
    respx.get(working_feed_url).mock(return_value=httpx.Response(200, content=_feed_xml()))
    respx.get(failed_feed_url).mock(return_value=httpx.Response(503))

    async with httpx.AsyncClient() as client:
        articles = await RssConnector(client, [failed_feed_url, working_feed_url]).fetch_articles(
            limit=10
        )

    assert [article.title for article in articles] == ["First Post"]


@pytest.mark.asyncio
async def test_fetch_articles_returns_empty_for_non_positive_limit() -> None:
    async with httpx.AsyncClient() as client:
        articles = await RssConnector(client, [FEED_URL]).fetch_articles(limit=0)

    assert articles == []
