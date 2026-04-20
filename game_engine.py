from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from company import Company, StellarCompany, RESOURCE_KEYS
from planet import Planet, PlanetStatus


# -----------------------------------------------------------------------
# Input helpers
# -----------------------------------------------------------------------

def _prompt_choice(prompt: str, valid: List[str]) -> str:
    """Re-prompt until the user enters a value in `valid` (case-insensitive)."""
    valid_lower = [v.lower() for v in valid]
    while True:
        raw = input(prompt).strip().lower()
        if raw in valid_lower:
            return raw
        print(f"    Invalid input. Choose from: {valid}")


def _prompt_int(prompt: str, lo: int, hi: int) -> int:
    """Re-prompt until the user enters an integer in [lo, hi]."""
    while True:
        raw = input(prompt).strip()
        if raw.lstrip("-").isdigit() and lo <= int(raw) <= hi:
            return int(raw)
        print(f"    Enter a number between {lo} and {hi}.")


# -----------------------------------------------------------------------
# GameEngine
# -----------------------------------------------------------------------

class GameEngine:
    """
    Manages the turn-based loop and 5-phase structure for Star Sea Hegemony.

    Turn order (strict per phase):
      1. Shop      — resource trading (2:1, max 3 trades)
      2. Action    — Land / Occupy / Seize / Pass
      3. Alliance  — form or break a bilateral alliance
      4. Event     — stub (card draw placeholder)
      5. Settlement — collect per-planet rewards
    """

    def __init__(
        self,
        companies: List[Company],
        planets: Dict[str, Planet],
    ) -> None:
        self.companies: List[Company] = companies
        self.planets: Dict[str, Planet] = planets
        self.current_turn: int = 1
        # Bilateral alliance map: company_name -> ally_name
        self._alliances: Dict[str, str] = {}

    # -------------------------------------------------------------------
    # UI helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _divider(char: str = "─", width: int = 62) -> str:
        return char * width

    def _print_header(self, company: Company) -> None:
        r = company.get_resources()
        ally = self._alliances.get(company.name, "None")
        print("\n" + self._divider("═"))
        print(f"  TURN {self.current_turn}  —  {company.name.upper()}")
        print(self._divider("═"))
        print(
            f"  Resources:  Tech={r['tech']}  |  Talent={r['talent']}  "
            f"|  Support={r['support']}  |  Funds={r['funds']}"
        )
        print(f"  Alliance:   {ally}")
        print()
        print("  ── Celestial Bodies ──────────────────────────────────")
        for planet in self.planets.values():
            if planet.status == PlanetStatus.OCCUPIED:
                detail = f"Occupant: {planet.occupant}"
            elif planet.status == PlanetStatus.LANDED:
                detail = f"Landers: {', '.join(planet.landers)}"
            else:
                detail = ""
            marker = " ◀" if planet.occupant == company.name else (
                " ·" if company.name in planet.landers else "  "
            )
            print(
                f"  {marker} {planet.name:<10}  [{planet.status.value.upper():<8}]  {detail}"
            )
        print(self._divider())

    @staticmethod
    def _phase_banner(number: int, name: str) -> None:
        print(f"\n  ┌── Phase {number}: {name} " + "─" * max(0, 44 - len(name)) + "┐")

    # -------------------------------------------------------------------
    # Phase 1: Shop
    # -------------------------------------------------------------------

    def _phase_shop(self, company: Company) -> None:
        self._phase_banner(1, "Shop  商店")
        if not company.use_shop():
            print(
                f"  │  [{company.name}] Shop is blocked while in an alliance.\n  └"
            )
            return

        trades_left = 3
        while trades_left > 0:
            r = company.get_resources()
            print(
                f"  │  Trades remaining: {trades_left}/3  |  "
                f"Tech={r['tech']} Talent={r['talent']} "
                f"Support={r['support']} Funds={r['funds']}"
            )
            ans = _prompt_choice("  │  Open shop this trade? [y/n]: ", ["y", "n"])
            if ans == "n":
                break

            affordable = [res for res in RESOURCE_KEYS if getattr(company, res) >= 2]
            if not affordable:
                print("  │  No resource has a balance ≥ 2. Cannot trade.")
                break

            print(f"  │  Spend 2 of:  {affordable}")
            spend = _prompt_choice("  │  > Spend: ", affordable)

            others = [res for res in RESOURCE_KEYS if res != spend]
            print(f"  │  Gain  1 of:  {others}")
            gain = _prompt_choice("  │  > Gain:  ", others)

            company.consume_resource(spend, 2)
            company.add_resource(gain, 1)
            r = company.get_resources()
            print(
                f"  │  ✓ Trade done.  "
                f"Tech={r['tech']} Talent={r['talent']} "
                f"Support={r['support']} Funds={r['funds']}"
            )
            trades_left -= 1

        print("  └")

    # -------------------------------------------------------------------
    # Phase 2: Action
    # -------------------------------------------------------------------

    def _effective_seize_req(
        self, company: Company, planet: Planet
    ) -> Dict[str, int]:
        """Return seize requirements after applying Stellar's alliance exemption."""
        req = planet.seize_req
        if isinstance(company, StellarCompany) and company.in_alliance and req:
            exempt = min(req, key=lambda k: req[k])
            return {k: v for k, v in req.items() if k != exempt}
        return req

    def _affordable_planets(
        self, company: Company, action: str
    ) -> List[Tuple[str, Planet]]:
        """Return (name, planet) pairs that are valid and affordable for the action."""
        results: List[Tuple[str, Planet]] = []
        for name, planet in self.planets.items():
            if action == "land":
                if not planet.can_land():
                    continue
                if company.name in planet.landers:
                    continue
                # Earth: land_req is None (free). Others must be affordable.
                if planet.land_req is not None:
                    if any(
                        getattr(company, r) < amt
                        for r, amt in planet.land_req.items()
                    ):
                        continue
                results.append((name, planet))

            elif action == "occupy":
                if planet.status != PlanetStatus.LANDED:
                    continue
                if company.name not in planet.landers:
                    continue
                if any(
                    getattr(company, r) < amt
                    for r, amt in planet.occupy_req.items()
                ):
                    continue
                results.append((name, planet))

            elif action == "seize":
                if planet.status != PlanetStatus.OCCUPIED:
                    continue
                if planet.occupant == company.name:
                    continue
                effective = self._effective_seize_req(company, planet)
                if any(
                    getattr(company, r) < amt
                    for r, amt in effective.items()
                ):
                    continue
                results.append((name, planet))

        return results

    @staticmethod
    def _req_str(req: Optional[Dict[str, int]], free_label: str = "Free") -> str:
        if not req:
            return free_label
        return "  ".join(f"{k.capitalize()}:{v}" for k, v in req.items())

    def _phase_action(self, company: Company) -> None:
        self._phase_banner(2, "Action  行動")
        print("  │  [1] Land   [2] Occupy   [3] Seize   [4] Pass")
        choice = _prompt_int("  │  > ", 1, 4)

        if choice == 4:
            print("  │  Passed.\n  └")
            return

        action_map = {1: "land", 2: "occupy", 3: "seize"}
        action = action_map[choice]

        options = self._affordable_planets(company, action)
        if not options:
            print(f"  │  No valid planets available for {action}.\n  └")
            return

        print(f"\n  │  Choose a planet to {action}:")
        for i, (name, planet) in enumerate(options, 1):
            if action == "land":
                cost = self._req_str(planet.land_req, "Free (Earth)")
            elif action == "occupy":
                cost = self._req_str(planet.occupy_req)
            else:
                cost = self._req_str(self._effective_seize_req(company, planet))
            print(f"  │    [{i}] {name:<10}  Cost: {cost}")

        idx = _prompt_int("  │  > ", 1, len(options)) - 1
        chosen_name, chosen_planet = options[idx]

        # Always deduct resources before mutating planet state
        if action == "land":
            if chosen_planet.land_req:
                if not company.consume_resources(chosen_planet.land_req):
                    print("  │  Insufficient resources. Action cancelled.\n  └")
                    return
            chosen_planet.land(company.name)
            print(f"  │  ✓ {company.name} has landed on {chosen_name}.")

        elif action == "occupy":
            if not company.consume_resources(chosen_planet.occupy_req):
                print("  │  Insufficient resources. Action cancelled.\n  └")
                return
            chosen_planet.occupy(company.name)
            print(f"  │  ✓ {company.name} now occupies {chosen_name}.")

        elif action == "seize":
            prev_occupant = chosen_planet.occupant
            effective_req = self._effective_seize_req(company, chosen_planet)
            if not company.consume_resources(effective_req):
                print("  │  Insufficient resources. Action cancelled.\n  └")
                return
            chosen_planet.seize(company.name)
            print(
                f"  │  ✓ {company.name} seized {chosen_name} "
                f"from {prev_occupant}. (Clean transfer — no penalty.)"
            )

        print("  └")

    # -------------------------------------------------------------------
    # Phase 3: Alliance
    # -------------------------------------------------------------------

    def _phase_alliance(self, company: Company) -> None:
        self._phase_banner(3, "Alliance  聯盟")
        current_ally = self._alliances.get(company.name)

        if current_ally:
            print(f"  │  Current alliance: {company.name} ↔ {current_ally}")
            ans = _prompt_choice("  │  Break this alliance? [y/n]: ", ["y", "n"])
            if ans == "y":
                ally_obj = next(
                    (c for c in self.companies if c.name == current_ally), None
                )
                company.in_alliance = False
                if ally_obj:
                    ally_obj.in_alliance = False
                self._alliances.pop(company.name, None)
                self._alliances.pop(current_ally, None)
                print(
                    f"  │  Alliance between {company.name} and {current_ally} dissolved."
                )
            else:
                print("  │  Alliance maintained.")
        else:
            print("  │  Current alliance: None")
            ans = _prompt_choice("  │  Form a new alliance? [y/n]: ", ["y", "n"])
            if ans == "n":
                print("  └")
                return

            available = [
                c for c in self.companies
                if c.name != company.name and c.name not in self._alliances
            ]
            if not available:
                print("  │  No available partners (all others are already allied).")
                print("  └")
                return

            print("  │  Available partners:")
            for i, c in enumerate(available, 1):
                r = c.get_resources()
                print(
                    f"  │    [{i}] {c.name:<12}  "
                    f"Tech={r['tech']} Talent={r['talent']} "
                    f"Support={r['support']} Funds={r['funds']}"
                )
            idx = _prompt_int("  │  > ", 1, len(available)) - 1
            partner = available[idx]

            company.in_alliance = True
            partner.in_alliance = True
            self._alliances[company.name] = partner.name
            self._alliances[partner.name] = company.name
            print(f"  │  ✓ Alliance formed: {company.name} ↔ {partner.name}")
            # Notify relevant passives
            if isinstance(company, StellarCompany) or isinstance(partner, StellarCompany):
                print("  │    (Stellar passive: lowest-cost exemption is now active)")
            # Check Galaxy shop constraint
            from company import GalaxyCompany
            if isinstance(company, GalaxyCompany) or isinstance(partner, GalaxyCompany):
                print("  │    (Galaxy constraint: shop is now blocked for Galaxy)")

        print("  └")

    # -------------------------------------------------------------------
    # Phase 4: Event
    # -------------------------------------------------------------------

    def _phase_event(self, company: Company) -> None:
        self._phase_banner(4, "Event  事件")
        print("  │  Drawing Event Card... (To be implemented)")
        print("  └")

    # -------------------------------------------------------------------
    # Phase 5: Settlement
    # -------------------------------------------------------------------

    def _prompt_any_resource(
        self, company: Company, amount: int, source: str
    ) -> None:
        """Ask the player to allocate each point of an 'any' reward."""
        print(f"  │  [{company.name}] earned {amount}× Any resource from {source}.")
        for i in range(amount):
            label = f"(choice {i + 1}/{amount}) " if amount > 1 else ""
            res = _prompt_choice(
                f"  │    {label}Which resource? [tech/talent/support/funds]: ",
                list(RESOURCE_KEYS),
            )
            company.add_resource(res, 1)
            print(f"  │    +1 {res}  →  now {getattr(company, res)}")

    def _apply_reward(
        self,
        company: Company,
        reward: Dict[str, object],
        source: str,
    ) -> None:
        for key, value in reward.items():
            if key == "any":
                self._prompt_any_resource(company, int(value), source)  # type: ignore[arg-type]
            elif key == "special":
                print(
                    f"  │  [{company.name}] special effect '{value}' "
                    f"on {source} — (To be implemented)"
                )
            else:
                amount = int(value)  # type: ignore[arg-type]
                company.add_resource(key, amount)
                sign = "+" if amount >= 0 else ""
                print(f"  │  [{company.name}] {source}:  {sign}{amount} {key}")

    def _phase_settlement(self, company: Company) -> None:
        self._phase_banner(5, "Settlement  結算")
        earned = False
        for planet in self.planets.values():
            # Landed reward
            if company.name in planet.landers and planet.land_reward:
                self._apply_reward(
                    company, planet.land_reward, f"{planet.name} (landed)"
                )
                earned = True
            # Occupation reward
            if planet.occupant == company.name and planet.occupy_reward:
                self._apply_reward(
                    company, planet.occupy_reward, f"{planet.name} (occupied)"
                )
                earned = True
        if not earned:
            print("  │  No rewards this turn.")
        print("  └")

    # -------------------------------------------------------------------
    # Full turn
    # -------------------------------------------------------------------

    def play_turn(self, company: Company) -> None:
        self._print_header(company)
        input(f"  [ Press Enter to begin {company.name}'s turn... ]")

        self._phase_shop(company)
        self._phase_action(company)
        self._phase_alliance(company)
        self._phase_event(company)
        self._phase_settlement(company)

        r = company.get_resources()
        print(f"\n  ── End of {company.name}'s turn ──────────────────────────")
        print(
            f"  Final:  Tech={r['tech']}  Talent={r['talent']}  "
            f"Support={r['support']}  Funds={r['funds']}"
        )
        print(self._divider())

    # -------------------------------------------------------------------
    # Victory condition
    # -------------------------------------------------------------------

    def check_monopoly_victory(self) -> Optional[Company]:
        """Return the company that holds OCCUPIED on all 9 celestial bodies, else None."""
        for company in self.companies:
            if all(
                planet.occupant == company.name
                for planet in self.planets.values()
            ):
                return company
        return None

    # -------------------------------------------------------------------
    # Main game loop
    # -------------------------------------------------------------------

    def run(self) -> None:
        print("\n" + "★" * 62)
        print("   STAR SEA HEGEMONY  ★  星海之霸   —   Game Start")
        print("★" * 62)

        while True:
            for company in self.companies:
                self.play_turn(company)

                winner = self.check_monopoly_victory()
                if winner:
                    print("\n" + "★" * 62)
                    print(
                        f"   VICTORY!  {winner.name.upper()} has achieved Solar Monopoly!"
                    )
                    print(f"   Completed in {self.current_turn} turn(s).")
                    print("★" * 62)
                    return

            self.current_turn += 1
