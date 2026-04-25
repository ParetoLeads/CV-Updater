import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Patterns that indicate a page didn't render its JS content
_TEMPLATE_PATTERNS = [
    r"\{\{.*?\}\}",       # Handlebars/Mustache {{var}}
    r"%7B%7B.*?%7D%7D",   # URL-encoded {{ }}
    r"\[object Object\]",
]


def _looks_like_template(text: str) -> bool:
    """Return True if the text is mostly unrendered JS template placeholders."""
    for pattern in _TEMPLATE_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def _parse_html(html: str, max_chars: int = 15000) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


def _scrape_with_requests(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return _parse_html(response.text)


def _scrape_with_playwright(url: str, max_chars: int = 15000) -> str:
    """Render the page in a headless browser and return visible text."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])
        page.goto(url, wait_until="networkidle", timeout=30000)
        # Wait a bit extra for any lazy-loaded content
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()
    return _parse_html(html, max_chars)


class LinkedInURLError(ValueError):
    pass


def scrape_url(url: str, max_chars: int = 15000) -> str:
    """Fetch a URL and return cleaned plain text. Uses Playwright for JS-heavy pages."""
    if "linkedin.com" in url:
        raise LinkedInURLError(
            "LinkedIn requires login to view job posts — scraping isn't possible. "
            "Please switch to 'Paste Description' and copy the job text directly from LinkedIn."
        )

    # Try fast path first
    try:
        text = _scrape_with_requests(url)
        if not _looks_like_template(text) and len(text) > 300:
            return text
    except requests.RequestException:
        pass  # fall through to Playwright

    # Fall back to headless browser
    try:
        return _scrape_with_playwright(url, max_chars)
    except Exception as e:
        raise ValueError(f"Could not scrape URL (tried both requests and Playwright): {e}")


def _try_paths(origin: str, paths: list, max_chars: int = 4000) -> str:
    """Try each path in order, return text from the first one that yields real content."""
    for path in paths:
        try:
            text = _scrape_with_requests(origin + path)
            if len(text) > 200 and not _looks_like_template(text):
                return text[:max_chars]
        except Exception:
            continue
    return ""


def scrape_company_pages(base_url: str, max_total_chars: int = 12000) -> str:
    """Scrape homepage + About page + Product/Solutions page. Returns combined text."""
    if not base_url or "linkedin.com" in base_url:
        return ""

    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    ABOUT_PATHS   = ["/about", "/about-us", "/company", "/our-story", "/mission", "/who-we-are", "/team"]
    PRODUCT_PATHS = ["/product", "/products", "/solutions", "/platform", "/services", "/what-we-do", "/features"]

    homepage_text = ""
    try:
        homepage_text = scrape_url(base_url)[:5000]
    except Exception:
        pass

    about_text   = _try_paths(origin, ABOUT_PATHS,   max_chars=4000)
    product_text = _try_paths(origin, PRODUCT_PATHS, max_chars=3000)

    sections = []
    if homepage_text:
        sections.append(homepage_text)
    if about_text:
        sections.append(f"--- About / Mission ---\n\n{about_text}")
    if product_text:
        sections.append(f"--- Product / Solutions ---\n\n{product_text}")

    combined = "\n\n".join(sections)
    return combined[:max_total_chars]


def clean_pasted_text(raw: str, max_chars: int = 15000) -> str:
    """Clean up a messy copy-paste from LinkedIn or similar."""
    lines = raw.splitlines()
    seen = set()
    cleaned = []
    for line in lines:
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            cleaned.append(line)
    text = "\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]
