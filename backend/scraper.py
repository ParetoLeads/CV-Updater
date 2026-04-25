import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin


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


def _fetch_raw_html(url: str) -> str:
    """Fetch raw HTML, falling back to Playwright for JS-rendered pages."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        html = response.text
        preview = _parse_html(html, max_chars=500)
        if len(preview) >= 300 and not _looks_like_template(preview):
            return html
    except requests.RequestException:
        pass
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            html = page.content()
            browser.close()
        return html
    except Exception:
        return ""


def _extract_nav_links(html: str, origin: str) -> list:
    """Extract internal links from the site's navigation and footer elements."""
    soup = BeautifulSoup(html, "lxml")
    origin_host = urlparse(origin).netloc

    # Cast a wide net: semantic tags + common class/id patterns
    containers = soup.select(
        "nav, header, footer, "
        "[class*='nav'], [class*='menu'], [class*='footer'], "
        "[id*='nav'], [id*='menu'], [id*='footer']"
    )

    links = []
    seen = set()
    for container in containers:
        for a in container.find_all("a", href=True):
            href = a.get("href", "").strip()
            text = a.get_text(strip=True)
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            full_url = urljoin(origin, href)
            parsed = urlparse(full_url)
            if parsed.netloc and parsed.netloc != origin_host:
                continue
            # Strip query params and fragments for deduplication
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            if not clean or clean == origin.rstrip("/"):
                continue
            if clean in seen:
                continue
            seen.add(clean)
            links.append({"url": clean, "text": text, "path": parsed.path.lower()})

    return links


def _scrape_best_match(nav_links: list, keywords: list, max_chars: int = 4000) -> str:
    """Score nav links by keyword match against text + path, scrape the best one."""
    def score(link):
        combo = link["text"].lower() + " " + link["path"]
        return sum(kw in combo for kw in keywords)

    candidates = sorted(nav_links, key=score, reverse=True)
    candidates = [l for l in candidates if score(l) > 0][:3]

    for link in candidates:
        try:
            text = _scrape_with_requests(link["url"])
            if len(text) > 200 and not _looks_like_template(text):
                return text[:max_chars]
        except Exception:
            continue
    return ""


def _try_paths(origin: str, paths: list, max_chars: int = 4000) -> str:
    """Fallback: try common paths when nav extraction yields no links."""
    for path in paths:
        try:
            text = _scrape_with_requests(origin + path)
            if len(text) > 200 and not _looks_like_template(text):
                return text[:max_chars]
        except Exception:
            continue
    return ""


def scrape_company_pages(base_url: str, max_total_chars: int = 12000) -> str:
    """Scrape homepage then discover About and Product pages from the site's own navigation."""
    if not base_url or "linkedin.com" in base_url:
        return ""

    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    # Fetch raw HTML so we can both extract text and read the navigation
    homepage_html = _fetch_raw_html(base_url)
    if not homepage_html:
        return ""

    homepage_text = _parse_html(homepage_html)[:5000]
    nav_links = _extract_nav_links(homepage_html, origin)

    ABOUT_KW   = ["about", "company", "mission", "story", "who we are", "values", "team", "culture"]
    PRODUCT_KW = ["product", "solution", "platform", "service", "features", "what we do", "how it works", "use case"]

    if nav_links:
        about_text   = _scrape_best_match(nav_links, ABOUT_KW,   max_chars=4000)
        product_text = _scrape_best_match(nav_links, PRODUCT_KW, max_chars=3000)
    else:
        # Nav extraction failed (rare) — fall back to guessing common paths
        about_text   = _try_paths(origin, ["/about", "/about-us", "/company", "/our-story", "/mission"], max_chars=4000)
        product_text = _try_paths(origin, ["/product", "/products", "/solutions", "/platform", "/services"], max_chars=3000)

    sections = [homepage_text] if homepage_text else []
    if about_text:
        sections.append(f"--- About / Mission ---\n\n{about_text}")
    if product_text:
        sections.append(f"--- Product / Solutions ---\n\n{product_text}")

    return "\n\n".join(sections)[:max_total_chars]


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
