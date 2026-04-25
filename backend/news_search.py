import os
from tavily import TavilyClient


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
