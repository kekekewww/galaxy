from __future__ import annotations

from data_loader import DataLoader
from planet import Planet
from company import Company


def initialize_game(
    config_path: str = "game_config.json",
) -> tuple[list[Company], dict[str, Planet]]:
    """
    Load config, instantiate all companies and planets, then apply the
    starting rule: every company begins with Landed status on Earth.

    Returns:
        companies  — list of Company subclass instances in config order
        planets    — dict keyed by planet name for O(1) lookup
    """
    loader = DataLoader(config_path)

    companies: list[Company] = loader.load_companies()
    planets: dict[str, Planet] = {p.name: p for p in loader.load_planets()}

    # Rule: all companies start Landed on Earth (no cost required)
    earth = planets["Earth"]
    for company in companies:
        earth.land(company.name)

    return companies, planets


# ----------------------------------------------------------------------
# Entry point — prints initial game state for manual verification
# ----------------------------------------------------------------------

if __name__ == "__main__":
    companies, planets = initialize_game()

    print("=" * 50)
    print("STAR SEA HEGEMONY — Initial Game State")
    print("=" * 50)

    print("\n--- Companies ---")
    for c in companies:
        print(c)

    print("\n--- Planets ---")
    for p in planets.values():
        print(p)
