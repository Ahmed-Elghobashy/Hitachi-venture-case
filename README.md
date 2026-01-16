# Hitachi Energy Portfolio - Design Doc

This repository contains a case-study script that ingests two energy-focused VC portfolio pages,
extracts company names/descriptions, mocks round data when missing, and uses an LLM to filter
companies relevant to the Hitachi Ventures Energy Team.

## Goals
- Ingest Energy Impact Partners and SET Ventures portfolio pages.
- Extract company name, description, and website from VC HTML.
- Mock round data (Seed/Series A/B/C allowed; Series D+ excluded).
- Use a single LLM call to filter energy relevance by keywords.
- Export a clean CSV of relevant companies.

## Non-Goals
- Perfect accuracy of funding rounds (mocked when missing).
- Large-scale web crawling of individual company sites.
- Paid data sources or vendor APIs.

## High-Level Architecture

```
                 +------------------------------+
                 | hitachi_energy_portfolio.py  |
                 +---------------+--------------+
                                 |
                                 v
               +-----------------+-----------------+
               |      Portfolio Scraper (VC HTML)  |
               |  services/portfolio_scraper.py     |
               +-----------+--------------+---------+
                           |              |
                           v              v
                    EIP HTML parse   SET HTML parse
                   (name+desc+site) (name+profile)
                           |              |
                           +------v-------+
                                  |
                                  v
                     +------------+-------------+
                     |  Enrichment (Mock Round) |
                     |  services/portfolio_enrichment.py
                     +------------+-------------+
                                  |
                                  v
                     +------------+-------------+
                     | LLM Filter (single call) |
                     | services/llm_client.py   |
                     +------------+-------------+
                                  |
                                  v
                     +------------+-------------+
                     |   CSV Export (results)   |
                     | exporters/protfolio_csv_exporter.py
                     +--------------------------+
```

## Data Flow

```
EIP/SET portfolio HTML
   -> parse company entries (name, description, website)
   -> fill missing rounds (mock Seed if missing)
   -> filter by round + LLM keyword relevance
   -> write CSV output
```

## Scraping Strategy

### Energy Impact Partners (EIP)
- The portfolio page contains descriptions directly in the HTML overlays.
- We parse:
  - Description from `.portfolio-item-overlay .text`
  - Website from `.portfolio-site-url`
  - Name inferred from the description or website hostname.

### SET Ventures
- The portfolio page is a grid that links to VC profile pages.
- We parse:
  - Company name from `aria-label`
  - Profile URL from the anchor
- We then fetch the VC profile page only (not the company site) to pull:
  - Meta description / OG description / first paragraph

## Filtering Logic

### Round Filter (enum)
Allowed:
- Seed, Series A, Series B, Series C

Blocked:
- Series D+, IPO, Public

### Energy Relevance (LLM)
The LLM evaluates descriptions for relevance to:
- Smart Grid
- Energy
- Energy Storage
- Industrial Efficiency

Filtering is executed in a **single LLM call** using a JSON list of descriptions.

## Key Modules

- `hitachi_energy_portfolio.py`  
  Orchestrates the pipeline and output.

- `services/portfolio_scraper.py`  
  VC HTML parsing and company extraction.

- `services/portfolio_enrichment.py`  
  Round mocking and VC profile description extraction.

- `services/llm_client.py`  
  LLM client + bulk filter call.

- `services/portfolio_filtering.py`  
  Round filter + LLM energy relevance.

- `exporters/protfolio_csv_exporter.py`  
  CSV writer.

## Config

- `config/portfolio_config.py`
  - `ENERGY_KEYWORDS`
  - `EIP_PORTFOLIO_URLS`, `SET_PORTFOLIO_URLS`
  - `EIP_LOCAL_HTML`, `SET_LOCAL_HTML`
  - `GEMINI_API_KEY_ENV`, `GEMINI_MODEL`
  - `LLM_HTML_CHAR_LIMIT`

## Risks / Limitations
- VC HTML structure can change; parsers are heuristic.
- Descriptions might be missing or truncated.
- Round data is mocked unless explicitly available.
- LLM classification is probabilistic and may need calibration.

## Running

```
export GEMINI_API_KEY=YOUR_KEY
python hitachi_energy_portfolio.py
```

To skip filtering:
```
python hitachi_energy_portfolio.py --no-filter
```
