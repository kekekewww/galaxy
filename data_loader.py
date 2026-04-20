from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Type

from planet import Planet
from company import (
    Company,
    TitanCompany,
    CelestialCompany,
    GalaxyCompany,
    StellarCompany,
    RESOURCE_KEYS,
)

COMPANY_CLASS_MAP: Dict[str, Type[Company]] = {
    "Titan": TitanCompany,
    "Celestial": CelestialCompany,
    "Galaxy": GalaxyCompany,
    "Stellar": StellarCompany,
}


class DataLoader:
    """
    Reads game_config.json and returns fully initialised Planet and Company objects.
    Raises FileNotFoundError if the config is missing.
    Raises ValueError if required top-level keys are absent.
    """

    def __init__(self, config_path: str = "game_config.json") -> None:
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Config file not found: {config_path!r}. "
                "Ensure game_config.json is in the working directory."
            )
        with open(config_path, "r", encoding="utf-8") as fh:
            raw: Any = json.load(fh)

        missing = [k for k in ("planets", "companies") if k not in raw]
        if missing:
            raise ValueError(
                f"game_config.json is missing required keys: {missing}"
            )

        self._raw: dict[str, Any] = raw

    # ------------------------------------------------------------------
    # Public factory methods
    # ------------------------------------------------------------------

    def load_planets(self) -> List[Planet]:
        """Return one Planet instance per entry in the 'planets' array."""
        planets: List[Planet] = []
        for entry in self._raw["planets"]:
            planet = Planet(
                name=entry["name"],
                land_req=entry.get("land_req"),        # Optional[dict]
                land_reward=entry.get("land_reward"),  # Optional[dict]
                occupy_req=entry["occupy_req"],
                occupy_reward=entry["occupy_reward"],
                seize_req=entry["seize_req"],
            )
            planets.append(planet)
        return planets

    def load_companies(self) -> List[Company]:
        """
        Return one Company subclass instance per entry in the 'companies' array.
        Starting resources = base + bonus (per-resource override).
        """
        companies: List[Company] = []
        for entry in self._raw["companies"]:
            base: int = entry["base"]
            bonus: Dict[str, int] = entry.get("bonus", {})

            stats: Dict[str, int] = {r: base for r in RESOURCE_KEYS}
            for resource, amount in bonus.items():
                if resource not in RESOURCE_KEYS:
                    raise ValueError(
                        f"Unknown resource {resource!r} in bonus for company {entry['name']!r}"
                    )
                stats[resource] += amount

            cls = COMPANY_CLASS_MAP.get(entry["name"])
            if cls is None:
                raise ValueError(
                    f"Unknown company name {entry['name']!r}. "
                    f"Expected one of: {list(COMPANY_CLASS_MAP)}"
                )

            company = cls(
                name=entry["name"],
                tech=stats["tech"],
                talent=stats["talent"],
                support=stats["support"],
                funds=stats["funds"],
            )
            companies.append(company)
        return companies
