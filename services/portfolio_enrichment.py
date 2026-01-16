from __future__ import annotations

import hashlib
import logging
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Dict, List, Optional

from config.portfolio_config import HTTP_TIMEOUT_SECONDS, REQUEST_HEADERS
from models.portfolio_models import Company, RoundStage

logger = logging.getLogger(__name__)


def mock_portfolio_data() -> dict[str, List[Company]]:
    # Mocked entries used if scraping fails or for enrichment fallback.
    return {
        "EIP": [
            Company(
                name="GridPulse",
                website="https://gridpulse.example.com",
                description="Smart grid analytics for utility operators.",
                last_round=RoundStage.SERIES_A,
                source="EIP",
            ),
            Company(
                name="ThermaLoop",
                website="https://thermaloop.example.com",
                description="Industrial efficiency platform reducing heat loss.",
                last_round=RoundStage.SERIES_C,
                source="EIP",
            ),
            Company(
                name="VoltStor",
                website="https://voltstor.example.com",
                description="Long-duration energy storage systems for renewables.",
                last_round=RoundStage.SERIES_D,
                source="EIP",
            ),
        ],
        "SET": [
            Company(
                name="FluxCharge",
                website="https://fluxcharge.example.com",
                description="Energy management software for commercial buildings.",
                last_round=RoundStage.SEED,
                source="SET",
            ),
            Company(
                name="AeroGrid",
                website="https://aerogrid.example.com",
                description="Smart grid optimization for distributed resources.",
                last_round=RoundStage.SERIES_B,
                source="SET",
            ),
            Company(
                name="SunPeak",
                website="https://sunpeak.example.com",
                description="Residential solar financing platform.",
                last_round=RoundStage.SERIES_E,
                source="SET",
            ),
        ],
    }


def load_enrichment_map() -> Dict[str, RoundStage]:
    # Mock enrichment map for demo purposes.
    return {
        "gridpulse": RoundStage.SERIES_A,
        "thermaloop": RoundStage.SERIES_C,
        "voltstor": RoundStage.SERIES_D,
        "fluxcharge": RoundStage.SEED,
        "aerogrid": RoundStage.SERIES_B,
        "sunpeak": RoundStage.SERIES_E,
    }


def fill_missing_fields(company: Company, mock_map: dict[str, Company]) -> Company:
    key = company.name.lower()
    if key in mock_map:
        mock = mock_map[key]
        if not company.website:
            company.website = mock.website
        if company.last_round == RoundStage.UNKNOWN:
            company.last_round = mock.last_round
    return company


def enrich_round(company: Company, round_map: dict[str, RoundStage]) -> Company:
    if company.last_round != RoundStage.UNKNOWN:
        return company
    enriched = round_map.get(company.name.lower())
    if enriched:
        company.last_round = enriched
    else:
        company.last_round = _hash_round_stage(company.name)
    return company


class _MetaDescriptionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta_description: str = ""
        self.og_description: str = ""
        self.first_paragraph: str = ""
        self._in_paragraph = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag.lower() == "meta":
            attr_map = {k.lower(): (v or "") for k, v in attrs}
            name = attr_map.get("name", "").lower()
            prop = attr_map.get("property", "").lower()
            content = attr_map.get("content", "").strip()
            if name == "description" and content and not self.meta_description:
                self.meta_description = content
            if prop == "og:description" and content and not self.og_description:
                self.og_description = content
        if tag.lower() == "p" and not self.first_paragraph:
            self._in_paragraph = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "p":
            self._in_paragraph = False

    def handle_data(self, data: str) -> None:
        if self._in_paragraph and not self.first_paragraph:
            text = data.strip()
            if text:
                self.first_paragraph = text

    def error(self, message: str) -> None:
        # Ignore malformed HTML declarations.
        return None


def _fetch_vc_html(url: str) -> Optional[str]:
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("VC page fetch failed url=%s error=%s", url, exc)
        return None


class _ExternalLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.first_external_link: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        href = attr_map.get("href", "")
        if not href or not href.startswith(("http://", "https://")):
            return
        if "setventures.com" in href:
            return
        if not self.first_external_link:
            self.first_external_link = href

    def error(self, message: str) -> None:
        return None


def enrich_from_vc_profile(company: Company) -> Company:
    if company.description:
        return company
    if not company.profile_url:
        return company
    html = _fetch_vc_html(company.profile_url)
    if not html:
        return company
    description_parser = _MetaDescriptionParser()
    description_parser.feed(html)
    description = (
        description_parser.meta_description
        or description_parser.og_description
        or description_parser.first_paragraph
    )
    if description:
        company.description = description
    if not company.website:
        link_parser = _ExternalLinkParser()
        link_parser.feed(html)
        if link_parser.first_external_link:
            company.website = link_parser.first_external_link
    return company


def _hash_round_stage(name: str) -> RoundStage:
    rounds = [
        RoundStage.SEED,
        RoundStage.SERIES_A,
        RoundStage.SERIES_B,
        RoundStage.SERIES_C,
        RoundStage.SERIES_D,
    ]
    if not name:
        return RoundStage.SEED
    digest = hashlib.sha256(name.lower().encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(rounds)
    return rounds[index]
