import os
from urllib.parse import urlparse
from tavily import TavilyClient

_SKIP_DOMAINS = [
    "linkedin.com", "crunchbase.com", "glassdoor.com", "indeed.com",
    "facebook.com", "twitter.com", "x.com", "wikipedia.org",
    "bloomberg.com", "forbes.com", "techcrunch.com", "wired.com",
    "pitchbook.com", "zoominfo.com", "g2.com", "capterra.com",
]


def find_company_url(company_name: str) -> str:
    """Search for a company's official homepage URL using Tavily. Returns origin URL or empty string."""
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return ""
    try:
        client = TavilyClient(api_key=api_key)
        results = client.search(
            query=f'"{company_name}" official website',
            search_depth="basic",
            max_results=5,
            include_answer=False,
        )
        for r in results.get("results", []):
            url = r.get("url", "")
            if not url:
                continue
            if any(skip in url for skip in _SKIP_DOMAINS):
                continue
            parsed = urlparse(url)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return ""


def search_recent_news(company_name: str) -> list[dict]:
    """Return up to 5 news items about the company from the last ~6 months."""
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return []

    client = TavilyClient(api_key=api_key)
    try:
        results = client.search(
            query=f"{company_name} news 2025 2026",
            search_depth="basic",
            max_results=5,
            include_answer=False,
        )
        news = []
        for r in results.get("results", []):
            news.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")[:300],
                "published_date": r.get("published_date", ""),
            })
        return news
    except Exception:
        return []
