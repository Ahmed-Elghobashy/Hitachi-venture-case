from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class RoundStage(str, Enum):
    SEED = "Seed"
    SERIES_A = "Series A"
    SERIES_B = "Series B"
    SERIES_C = "Series C"
    SERIES_D = "Series D"
    SERIES_E = "Series E"
    SERIES_F = "Series F"
    SERIES_G = "Series G"
    IPO = "IPO"
    PUBLIC = "Public"
    UNKNOWN = "Unknown"


@dataclass
class Company:
    name: str
    website: str
    description: str
    last_round: RoundStage
    source: str
    energy_keywords: Optional[List[str]] = None
    stage: str = ""
    profile_url: str = ""
