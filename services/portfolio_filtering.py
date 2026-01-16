from __future__ import annotations

from config.portfolio_config import ENERGY_KEYWORDS
from models.portfolio_models import Company, RoundStage
from services.llm_client import llm_filter_energy_bulk, llm_matches_energy


EARLY_STAGE_ALLOWED = {RoundStage.SEED, RoundStage.SERIES_A, RoundStage.SERIES_B, RoundStage.SERIES_C}
LATE_STAGE_BLOCKED = {
    RoundStage.SERIES_D,
    RoundStage.SERIES_E,
    RoundStage.SERIES_F,
    RoundStage.SERIES_G,
    RoundStage.IPO,
    RoundStage.PUBLIC,
}


def is_round_eligible(round_stage: RoundStage) -> bool:
    if not round_stage:
        return False
    if round_stage in LATE_STAGE_BLOCKED:
        return False
    return round_stage in EARLY_STAGE_ALLOWED


def matches_energy_keywords(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ENERGY_KEYWORDS)


def is_relevant(company: Company) -> bool:
    if not is_round_eligible(company.last_round):
        return False
    if not company.description:
        return False
    return llm_matches_energy(company.description, ENERGY_KEYWORDS)


def filter_relevant(companies: list[Company]) -> list[Company]:
    eligible_indices: list[int] = []
    descriptions: list[str] = []
    for index, company in enumerate(companies):
        if not is_round_eligible(company.last_round):
            continue
        if not company.description:
            continue
        eligible_indices.append(index)
        descriptions.append(company.description)

    if not descriptions:
        return []

    matches = llm_filter_energy_bulk(descriptions, ENERGY_KEYWORDS)
    relevant: list[Company] = []
    for idx, match in zip(eligible_indices, matches):
        if match:
            relevant.append(companies[idx])
    return relevant
