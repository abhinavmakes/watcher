from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}


def normalize_url(raw_url: str) -> str:
    stripped_url = raw_url.strip()
    if "://" not in stripped_url:
        stripped_url = f"https://{stripped_url}"

    parsed = urlsplit(stripped_url)
    scheme = parsed.scheme.lower() or "https"
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    netloc = hostname
    if parsed.port is not None and not _is_default_port(scheme, parsed.port):
        netloc = f"{netloc}:{parsed.port}"

    path = parsed.path.rstrip("/")
    query_params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_query_key(key)
    ]
    query = urlencode(query_params, doseq=True)

    return urlunsplit((scheme, netloc, path, query, ""))


def _is_default_port(scheme: str, port: int) -> bool:
    return (scheme == "http" and port == 80) or (scheme == "https" and port == 443)


def _is_tracking_query_key(key: str) -> bool:
    lower_key = key.lower()
    return lower_key.startswith("utm_") or lower_key in TRACKING_QUERY_KEYS
