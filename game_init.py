from __future__ import annotations

from typing import Dict, List, Tuple

from data_loader import DataLoader
from planet import Planet
from company import Company


def initialize_game(
    config_path: str = "game_config.json",
) -> Tuple[List[Company], Dict[str, Planet]]:
    """
    Load config, instantiate all companies and planets, then apply the
    starting rule: every company begins with Landed status on Earth.

    Returns:
        companies  — list of Company subclass instances in config order
        planets    — dict keyed by planet name for O(1) lookup
    """
    loader = DataLoader(config_path)

    companies: List[Company] = loader.load_companies()
    planets: Dict[str, Planet] = {p.name: p for p in loader.load_planets()}

    # Rule: all companies start Landed on Earth (no cost required)
    earth = planets["Earth"]
    for company in companies:
        earth.land(company.name)

    return companies, planets


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

if __name__ == "__main__":
    from game_engine import GameEngine

    companies, planets = initialize_game()
    engine = GameEngine(companies, planets)
    engine.run()
