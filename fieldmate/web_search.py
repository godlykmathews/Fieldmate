"""Called only after a query-specific permission is claimed by the server."""

from urllib.parse import urlsplit


def search_web(query):
    from ddgs import DDGS

    try:
        rows = DDGS(timeout=12).text(query, backend="duckduckgo", max_results=5, safesearch="moderate")
    except Exception as error:
        raise ValueError(
            "Web search is unavailable. The connection or search provider may be offline. No web results were used."
        ) from error
    results = []
    for row in rows[:5]:
        url = row.get("href", "")
        if urlsplit(url).scheme not in {"https", "http"}:
            continue
        results.append(
            {
                "id": f"web-{len(results) + 1}",
                "title": row.get("title", "")[:300],
                "url": url,
                "text": row.get("body", "")[:1800],
            }
        )
    return results
