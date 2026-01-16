#!/usr/bin/env python3
"""
Case study script:
- Scrape two energy VC portfolio pages (EIP, SET Ventures) when possible.
- Enrich missing round data (mock fallback).
- Filter by stage and energy keywords.
- Output a CSV of Hitachi-relevant companies.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import List

from config.portfolio_config import (
    EIP_LOCAL_HTML,
    EIP_PORTFOLIO_URLS,
    LOG_LEVEL_DEFAULT,
    LOG_LEVEL_ENV,
    SET_LOCAL_HTML,
    SET_PORTFOLIO_URLS,
)
from services.portfolio_enrichment import (
    enrich_from_vc_profile,
    enrich_round,
    fill_missing_fields,
    load_enrichment_map,
    mock_portfolio_data,
)
from services.portfolio_filtering import filter_relevant, is_relevant
from models.portfolio_models import Company
from exporters.protfolio_csv_exporter import protfolio_csv_exporter
from services.portfolio_scraper import scrape_portfolio


def scrape_portfolios(urls: List[str], source: str, fallback: List[Company]) -> List[Company]:
    companies: List[Company] = []
    for url in urls:
        companies.extend(scrape_portfolio(url, source, []))
    return companies or fallback


def main() -> int:
    log_level_name = os.getenv(LOG_LEVEL_ENV, LOG_LEVEL_DEFAULT).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    use_mock = "--use-mock" in sys.argv
    no_filter = "--no-filter" in sys.argv

    mock_data = mock_portfolio_data()
    mock_lookup = {c.name.lower(): c for companies in mock_data.values() for c in companies}
    enrichment_map = load_enrichment_map()

    if use_mock:
        eip_companies = mock_data["EIP"]
        set_companies = mock_data["SET"]
    else:
        eip_companies = scrape_portfolios(EIP_PORTFOLIO_URLS, "EIP", [])
        if not eip_companies and EIP_LOCAL_HTML:
            eip_companies = scrape_portfolios([EIP_LOCAL_HTML], "EIP", mock_data["EIP"])
        elif not eip_companies:
            eip_companies = mock_data["EIP"]

        set_companies = scrape_portfolios(SET_PORTFOLIO_URLS, "SET", [])
        if not set_companies and SET_LOCAL_HTML:
            set_companies = scrape_portfolios([SET_LOCAL_HTML], "SET", mock_data["SET"])
        elif not set_companies:
            set_companies = mock_data["SET"]

    all_companies = eip_companies + set_companies

    enriched: List[Company] = []
    for company in all_companies:
        company = enrich_from_vc_profile(company)
        company = fill_missing_fields(company, mock_lookup)
        company = enrich_round(company, enrichment_map)
        enriched.append(company)

    if no_filter:
        relevant = enriched
    else:
        relevant = filter_relevant(enriched)

    output_path = "hitachi_relevant_companies.csv"
    protfolio_csv_exporter(relevant, output_path)

    print(f"Wrote {len(relevant)} relevant companies to {output_path}")
    if not relevant:
        print("No companies matched the filters. Try --use-mock for demo data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
