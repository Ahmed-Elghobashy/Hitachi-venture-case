from __future__ import annotations

import logging
import re
import time
import urllib.error
import urllib.request
from urllib.parse import unquote, urlparse
from pathlib import Path
from html.parser import HTMLParser
from typing import List, Optional

from config.portfolio_config import HTTP_TIMEOUT_SECONDS, REQUEST_HEADERS
from models.portfolio_models import Company, RoundStage

logger = logging.getLogger(__name__)


class AnchorTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_anchor = False
        self.anchors: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag.lower() == "a":
            self.in_anchor = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self.in_anchor = False

    def handle_data(self, data: str) -> None:
        if self.in_anchor:
            text = data.strip()
            if text:
                self.anchors.append(text)


class AnchorLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_anchor = False
        self.current_href: Optional[str] = None
        self.links: List[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag.lower() == "a":
            self.in_anchor = True
            href = ""
            for key, value in attrs:
                if key.lower() == "href" and value:
                    href = value
                    break
            self.current_href = href

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self.in_anchor = False
            self.current_href = None

    def handle_data(self, data: str) -> None:
        if self.in_anchor and self.current_href:
            text = data.strip()
            if text:
                self.links.append((text, self.current_href))


def fetch_html(url: str) -> Optional[str]:
    if url.startswith("file://"):
        parsed = urlparse(url)
        local_path = Path(unquote(parsed.path))
        try:
            body = local_path.read_bytes()
        except OSError as exc:
            logger.warning("Local file read failed url=%s error=%s", url, exc)
            return None
        logger.info("Loaded local HTML url=%s bytes=%s", url, len(body))
        return body.decode("utf-8", errors="replace")

    local_path = Path(url)
    if local_path.exists():
        try:
            body = local_path.read_bytes()
        except OSError as exc:
            logger.warning("Local file read failed path=%s error=%s", local_path, exc)
            return None
        logger.info("Loaded local HTML path=%s bytes=%s", local_path, len(body))
        return body.decode("utf-8", errors="replace")

    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read()
            elapsed = time.monotonic() - start
            logger.info(
                "Fetched HTML url=%s status=%s bytes=%s seconds=%s",
                url,
                response.status,
                len(body),
                round(elapsed, 2),
            )
            return body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        elapsed = time.monotonic() - start
        snippet = ""
        try:
            snippet = exc.read(500).decode("utf-8", errors="replace")
        except Exception:
            snippet = ""
        logger.warning(
            "HTTP fetch failed url=%s status=%s reason=%s seconds=%s body_snippet=%s",
            url,
            exc.code,
            exc.reason,
            round(elapsed, 2),
            snippet,
        )
        return None
    except (urllib.error.URLError, TimeoutError) as exc:
        elapsed = time.monotonic() - start
        logger.warning("Fetch failed url=%s error=%s seconds=%s", url, exc, round(elapsed, 2))
        return None


def extract_company_names_from_html(html: str) -> List[str]:
    parser = AnchorTextParser()
    parser.feed(html)
    # Heuristic: company names are typically short anchor texts.
    names = []
    for text in parser.anchors:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if 2 <= len(cleaned) <= 60:
            names.append(cleaned)
    # Deduplicate while preserving order.
    seen = set()
    unique = []
    for name in names:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            unique.append(name)
    return unique


def extract_company_entries_from_html(html: str) -> List[tuple[str, str]]:
    parser = AnchorLinkParser()
    parser.feed(html)
    entries: List[tuple[str, str]] = []
    seen = set()
    for text, href in parser.links:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if not (2 <= len(cleaned) <= 60):
            continue
        if not href.startswith(("http://", "https://")):
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        entries.append((cleaned, href))
    return entries


class EIPPortfolioParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_overlay = False
        self._in_text = False
        self._overlay_div_depth = 0
        self._current_description: List[str] = []
        self._current_site: str = ""
        self.entries: List[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "div" and "portfolio-item-overlay" in attr_map.get("class", ""):
            self._in_overlay = True
            self._overlay_div_depth = 1
            self._current_description = []
            self._current_site = ""
        elif self._in_overlay and tag.lower() == "div":
            self._overlay_div_depth += 1
        if self._in_overlay and tag.lower() == "div" and "text" in attr_map.get("class", ""):
            self._in_text = True
        if self._in_overlay and tag.lower() == "a" and "portfolio-site-url" in attr_map.get("class", ""):
            href = attr_map.get("href", "")
            if href:
                self._current_site = href

    def handle_endtag(self, tag: str) -> None:
        if self._in_overlay and tag.lower() == "div" and self._in_text:
            self._in_text = False
        if self._in_overlay and tag.lower() == "div":
            self._overlay_div_depth -= 1
            if self._overlay_div_depth > 0:
                return
            description = " ".join(self._current_description).strip()
            if description or self._current_site:
                self.entries.append((description, self._current_site))
            self._in_overlay = False

    def handle_data(self, data: str) -> None:
        if self._in_overlay and self._in_text:
            text = data.strip()
            if text:
                self._current_description.append(text)


class SetVenturesParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.entries: List[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if "nectar-post-grid-link" in attr_map.get("class", ""):
            name = attr_map.get("aria-label", "").strip()
            href = attr_map.get("href", "").strip()
            if name and href:
                self.entries.append((name, href))


def infer_company_name(description: str, website: str) -> str:
    if description:
        match = re.match(r"^([A-Z][A-Za-z0-9&.+-]*(?:\s+[A-Z][A-Za-z0-9&.+-]*){0,3})[’']s\b", description)
        if match:
            return match.group(1).strip()
        match = re.search(
            r"\b([A-Z][A-Za-z0-9&.+-]*(?:\s+[A-Z][A-Za-z0-9&.+-]*){0,3})\s+(is|are|provides|develops|builds|offers|delivers|enables)\b",
            description,
        )
        if match:
            return match.group(1).strip()
    if website:
        try:
            host = urlparse(website).hostname or ""
        except ValueError:
            host = ""
        host = host.replace("www.", "")
        if host:
            primary = host.split(".")[0]
            return primary.replace("-", " ").replace("_", " ").title()
    return "Unknown"


def build_company_from_name(name: str, source: str, website: str = "", description: str = "", profile_url: str = "") -> Company:
    # Placeholder entries for scraped names. Round and description may be enriched.
    return Company(
        name=name,
        website=website,
        description=description,
        last_round=RoundStage.UNKNOWN,
        source=source,
        profile_url=profile_url,
    )


def scrape_portfolio(url: str, source: str, fallback: List[Company]) -> List[Company]:
    html = fetch_html(url)
    if not html:
        return fallback
    if "energyimpactpartners.com" in url:
        parser = EIPPortfolioParser()
        parser.feed(html)
        companies = []
        for description, website in parser.entries:
            name = infer_company_name(description, website)
            companies.append(build_company_from_name(name, source, website, description))
        return companies or fallback

    if "setventures.com" in url:
        parser = SetVenturesParser()
        parser.feed(html)
        companies = []
        for name, profile_url in parser.entries:
            clean_name = name.title() if name.isupper() else name
            companies.append(build_company_from_name(clean_name, source, profile_url=profile_url))
        return companies or fallback

    entries = extract_company_entries_from_html(html)
    if entries:
        return [build_company_from_name(name, source, website) for name, website in entries]
    names = extract_company_names_from_html(html)
    if not names:
        return fallback
    return [build_company_from_name(name, source) for name in names]
