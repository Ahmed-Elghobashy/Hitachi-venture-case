from __future__ import annotations

import csv
from typing import Iterable

from models.portfolio_models import Company


def protfolio_csv_exporter(companies: Iterable[Company], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["company_name", "website", "description", "source", "last_round"])
        for company in companies:
            writer.writerow(
                [
                    company.name,
                    company.website,
                    company.description,
                    company.source,
                    getattr(company.last_round, "value", company.last_round),
                ]
            )
