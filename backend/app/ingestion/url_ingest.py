"""
URL / Website Ingestion Service using Crawl4AI with SSRF safety & fallback parser.
"""

import re
import logging
import hashlib
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from urllib.parse import urlparse
from ipaddress import ip_address

logger = logging.getLogger(__name__)

# Forbidden hostnames and private IP ranges for SSRF prevention
FORBIDDEN_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "::1"}


@dataclass
class URLTextBlock:
    text: str
    section_header: Optional[str] = None
    is_table: bool = False


@dataclass
class ParsedURLPage:
    url: str
    title: str
    raw_text: str
    blocks: List[URLTextBlock] = field(default_factory=list)
    file_hash: str = ""
    parse_error: Optional[str] = None
    domain: str = ""


def validate_url(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate URL safety to prevent SSRF and invalid protocol attacks.
    Returns (is_valid, error_message).
    """
    if not url or not isinstance(url, str):
        return False, "URL string must not be empty"

    url_str = url.strip()
    if not (url_str.startswith("http://") or url_str.startswith("https://")):
        return False, "URL must start with http:// or https://"

    try:
        parsed = urlparse(url_str)
        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL host"

        hostname_lower = hostname.lower()
        if hostname_lower in FORBIDDEN_HOSTS or hostname_lower.endswith(".local") or hostname_lower.endswith(".internal"):
            return False, f"Access to private/local host '{hostname}' is forbidden for security reasons"

        # Check if hostname is an IP address
        try:
            ip = ip_address(hostname_lower)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False, f"Access to private IP address '{hostname}' is forbidden"
        except ValueError:
            pass  # Domain name, not a raw IP address

        return True, None
    except Exception as e:
        return False, f"Malformed URL: {e}"


def sha256_url(url: str, content: str) -> str:
    """Deterministic hash of URL and content."""
    combined = f"{url.strip().lower()}::{content[:5000]}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


async def fetch_url_content(url: str) -> ParsedURLPage:
    """
    Fetch and parse a webpage using Crawl4AI with automatic HTTP/BeautifulSoup fallback.
    Extracts webpage title, structured text blocks, and specification tables.
    """
    is_valid, err_msg = validate_url(url)
    if not is_valid:
        return ParsedURLPage(
            url=url,
            title="Invalid URL",
            raw_text="",
            parse_error=err_msg,
        )

    parsed_url = urlparse(url)
    domain = parsed_url.netloc or parsed_url.hostname or "website"

    # Try Crawl4AI first
    try:
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler(verbose=False) as crawler:
            crawl_result = await crawler.arun(url=url)
            if crawl_result and crawl_result.success:
                raw_markdown = crawl_result.markdown or ""
                title = getattr(crawl_result, "title", None) or f"{domain} specification"
                
                # Split markdown into text blocks
                blocks = _split_markdown_into_blocks(raw_markdown)
                file_hash = sha256_url(url, raw_markdown)

                return ParsedURLPage(
                    url=url,
                    title=title.strip(),
                    raw_text=raw_markdown,
                    blocks=blocks,
                    file_hash=file_hash,
                    domain=domain,
                )
    except Exception as crawl_err:
        logger.warning(f"Crawl4AI browser execution warning for {url}: {crawl_err}. Falling back to HTTP client...")

    # Fallback to httpx + BeautifulSoup
    try:
        import httpx
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IndustrialProductTruthEngine/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()

            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")

            # Extract title
            title_tag = soup.find("title")
            title = title_tag.get_text().strip() if title_tag else f"{domain} specification"

            # Remove scripts & styles
            for elem in soup(["script", "style", "nav", "footer", "header"]):
                elem.decompose()

            blocks = []
            # Process table elements
            for table in soup.find_all("table"):
                table_text = []
                for row in table.find_all("tr"):
                    cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                    if cols:
                        table_text.append(" | ".join(cols))
                if table_text:
                    blocks.append(URLTextBlock(
                        text="\n".join(table_text),
                        section_header="Specification Table",
                        is_table=True,
                    ))

            # Process headings & paragraphs
            for elem in soup.find_all(["h1", "h2", "h3", "h4", "p", "div", "li"]):
                txt = elem.get_text(strip=True)
                if len(txt) > 15:
                    section_header = None
                    prev_heading = elem.find_previous(["h1", "h2", "h3"])
                    if prev_heading:
                        section_header = prev_heading.get_text(strip=True)
                    blocks.append(URLTextBlock(text=txt, section_header=section_header))

            full_text = "\n".join(b.text for b in blocks)
            file_hash = sha256_url(url, full_text)

            return ParsedURLPage(
                url=url,
                title=title,
                raw_text=full_text,
                blocks=blocks,
                file_hash=file_hash,
                domain=domain,
            )

    except Exception as http_err:
        logger.error(f"Failed to fetch webpage content for {url}: {http_err}")
        return ParsedURLPage(
            url=url,
            title="Fetch Error",
            raw_text="",
            parse_error=f"Unable to process this webpage: {http_err}",
            domain=domain,
        )


def _split_markdown_into_blocks(markdown_text: str) -> List[URLTextBlock]:
    """Helper to break markdown into structured section blocks."""
    blocks: List[URLTextBlock] = []
    lines = markdown_text.split("\n")

    current_header = None
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("#"):
            if current_lines:
                blocks.append(URLTextBlock(
                    text="\n".join(current_lines),
                    section_header=current_header,
                ))
                current_lines = []
            current_header = stripped.lstrip("#").strip()
        else:
            current_lines.append(stripped)
            if len(current_lines) >= 4:
                blocks.append(URLTextBlock(
                    text="\n".join(current_lines),
                    section_header=current_header,
                ))
                current_lines = []

    if current_lines:
        blocks.append(URLTextBlock(
            text="\n".join(current_lines),
            section_header=current_header,
        ))

    return blocks
