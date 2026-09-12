from bs4 import BeautifulSoup


def clean_html(value: object) -> str | None:
    """Strip markup from a feed-supplied body and collapse it to plain text.

    Shared by both connectors so `ArticleInput.content` has one format behind the
    `ArticleConnector` protocol: HN's `text` field is HTML just like an RSS body, and
    leaving it raw sends `<p>` tags and `&#x27;` entities into the classifier prompt
    and the embedding input.
    """
    if not isinstance(value, str):
        return None

    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    return text or None
