from __future__ import annotations

ENERGY_KEYWORDS = [
    "smart grid",
    "energy",
    "energy storage",
    "industrial efficiency",
]

EIP_PORTFOLIO_URLS = ["https://www.energyimpactpartners.com/_portfolio/"]
SET_PORTFOLIO_URLS = ["https://www.setventures.com/portfolio/"]
EIP_LOCAL_HTML = "data/energyimpacters.html"
SET_LOCAL_HTML = "data/setventures.html"

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GEMINI_MODEL = "gemini-3-flash-preview"
LLM_HTML_CHAR_LIMIT = 120000

LOG_LEVEL_ENV = "HITACHI_LOG_LEVEL"
LOG_LEVEL_DEFAULT = "INFO"

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HitachiPortfolioBot/1.0; +https://example.com/bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8",
}
HTTP_TIMEOUT_SECONDS = 15
