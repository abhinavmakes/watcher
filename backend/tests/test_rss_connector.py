from datetime import UTC, datetime

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


def _body_feed_xml(description: str, encoded: str | None) -> bytes:
    encoded_element = (
        f"<content:encoded><![CDATA[{encoded}]]></content:encoded>" if encoded is not None else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Body Feed</title>
    <item>
      <title>Post</title>
      <link>https://www.example.com/posts/body</link>
      <guid>body-post</guid>
      <description><![CDATA[{description}]]></description>
      {encoded_element}
    </item>
  </channel>
</rss>""".encode()


@pytest.mark.asyncio
@respx.mock
async def test_content_encoded_wins_over_summary_teaser() -> None:
    # The teaser in <description> is what a summary-only reader would have captured.
    respx.get(FEED_URL).mock(
        return_value=httpx.Response(
            200,
            content=_body_feed_xml(
                "<p>Read the rest at...</p>", "<p>The <em>full</em> post body.</p>"
            ),
        )
    )

    async with httpx.AsyncClient() as client:
        articles = await RssConnector(client, [FEED_URL]).fetch_articles(limit=10)

    assert articles[0].content == "The full post body."


@pytest.mark.asyncio
@respx.mock
async def test_falls_back_to_summary_when_no_content_element() -> None:
    respx.get(FEED_URL).mock(
        return_value=httpx.Response(200, content=_body_feed_xml("<p>Only a teaser</p>", None))
    )

    async with httpx.AsyncClient() as client:
        articles = await RssConnector(client, [FEED_URL]).fetch_articles(limit=10)

    assert articles[0].content == "Only a teaser"


@pytest.mark.asyncio
@respx.mock
async def test_falls_back_to_summary_when_content_element_is_empty() -> None:
    respx.get(FEED_URL).mock(
        return_value=httpx.Response(200, content=_body_feed_xml("<p>Only a teaser</p>", ""))
    )

    async with httpx.AsyncClient() as client:
        articles = await RssConnector(client, [FEED_URL]).fetch_articles(limit=10)

    assert articles[0].content == "Only a teaser"


def _multi_item_feed_xml(prefix: str, count: int) -> bytes:
    items = "".join(
        f"""
    <item>
      <title>{prefix} {index}</title>
      <link>https://www.example.com/{prefix.lower()}/{index}</link>
      <guid>{prefix.lower()}-{index}</guid>
    </item>"""
        for index in range(count)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<rss version="2.0"><channel><title>{prefix} Feed</title>{items}</channel></rss>'
    ).encode()


@pytest.mark.asyncio
@respx.mock
async def test_fetch_articles_applies_per_feed_cap() -> None:
    feed_a = "https://example.com/a.xml"
    feed_b = "https://example.com/b.xml"
    respx.get(feed_a).mock(
        return_value=httpx.Response(200, content=_multi_item_feed_xml("Alpha", 3))
    )
    respx.get(feed_b).mock(
        return_value=httpx.Response(200, content=_multi_item_feed_xml("Beta", 3))
    )

    async with httpx.AsyncClient() as client:
        articles = await RssConnector(client, [feed_a, feed_b]).fetch_articles(limit=2)

    # Each feed contributes at most `limit`; the dense first feed does not starve the second.
    assert [article.title for article in articles] == ["Alpha 0", "Alpha 1", "Beta 0", "Beta 1"]


def _atom_feed_xml(published: str | None, updated: str) -> bytes:
    published_element = f"<published>{published}</published>" if published is not None else ""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Post</title>
    <link href="https://www.example.com/posts/atom"/>
    <id>atom-post</id>
    {published_element}
    <updated>{updated}</updated>
    <content type="html">Body text.</content>
  </entry>
</feed>""".encode()


@pytest.mark.asyncio
@respx.mock
async def test_falls_back_to_updated_when_atom_entry_has_no_published() -> None:
    # feedparser aliases `updated` -> `published` but not the reverse, so an Atom entry
    # carrying only <updated> used to lose its date silently.
    respx.get(FEED_URL).mock(
        return_value=httpx.Response(200, content=_atom_feed_xml(None, "2026-07-14T10:30:00Z"))
    )

    async with httpx.AsyncClient() as client:
        articles = await RssConnector(client, [FEED_URL]).fetch_articles(limit=10)

    assert articles[0].published_at == datetime(2026, 7, 14, 10, 30, tzinfo=UTC)


@pytest.mark.asyncio
@respx.mock
async def test_published_wins_over_updated_when_both_are_present() -> None:
    respx.get(FEED_URL).mock(
        return_value=httpx.Response(
            200,
            content=_atom_feed_xml("2026-07-01T08:00:00Z", "2026-07-14T10:30:00Z"),
        )
    )

    async with httpx.AsyncClient() as client:
        articles = await RssConnector(client, [FEED_URL]).fetch_articles(limit=10)

    assert articles[0].published_at == datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
