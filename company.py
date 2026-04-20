from __future__ import annotations

from typing import Dict, Optional, Tuple, Union

ResourceDict = Dict[str, int]

RESOURCE_KEYS: Tuple[str, ...] = ("tech", "talent", "support", "funds")


class Company:
    """
    Base class for all four corporations.
    Handles the four core resources: Tech, Talent, Support, Funds.
    """

    def __init__(
        self,
        name: str,
        tech: int,
        talent: int,
        support: int,
        funds: int,
    ) -> None:
        self.name = name
        self.tech: int = tech
        self.talent: int = talent
        self.support: int = support
        self.funds: int = funds
        self.in_alliance: bool = False

    # ------------------------------------------------------------------
    # Resource accessors
    # ------------------------------------------------------------------

    def get_resources(self) -> ResourceDict:
        return {r: getattr(self, r) for r in RESOURCE_KEYS}

    # ------------------------------------------------------------------
    # Resource addition
    # ------------------------------------------------------------------

    def add_resource(self, resource: str, amount: int) -> None:
        """Add `amount` to a named resource. Amount may be negative (penalty)."""
        if resource not in RESOURCE_KEYS:
            raise ValueError(f"Unknown resource: {resource!r}")
        setattr(self, resource, getattr(self, resource) + amount)

    def add_resources(self, rewards: Dict[str, Union[int, str]]) -> None:
        """
        Apply a reward dict. Handles:
        - Normal keys: {"tech": 2, "funds": -1}
        - Any-resource keys: {"any": 1}  →  routed to _resolve_any_resource
        - Special keys: {"special": "dyson_sphere_buff"}  →  routed to _apply_special
        """
        for key, value in rewards.items():
            if key == "any":
                self._resolve_any_resource(int(value))
            elif key == "special":
                self._apply_special(str(value))
            else:
                self.add_resource(key, int(value))

    def _resolve_any_resource(self, amount: int) -> None:
        """
        Placeholder: in the full game the player chooses which resource to gain.
        Default AI heuristic: add to the currently lowest resource.
        """
        lowest = min(RESOURCE_KEYS, key=lambda r: getattr(self, r))
        self.add_resource(lowest, amount)

    def _apply_special(self, effect_id: str) -> None:
        """Dispatch point for named special effects (card draws, Dyson Sphere, etc.)."""
        # Full implementation deferred to game engine
        pass

    # ------------------------------------------------------------------
    # Resource consumption
    # ------------------------------------------------------------------

    def consume_resource(self, resource: str, amount: int) -> bool:
        """
        Deduct `amount` of a resource. Returns True on success.
        Returns False (without mutating state) if the balance is insufficient.
        """
        if resource not in RESOURCE_KEYS:
            raise ValueError(f"Unknown resource: {resource!r}")
        if getattr(self, resource) < amount:
            return False
        setattr(self, resource, getattr(self, resource) - amount)
        return True

    def consume_resources(self, requirements: ResourceDict) -> bool:
        """
        Consume all requirements atomically.
        Checks all balances first; only deducts if every check passes.
        """
        for resource, amount in requirements.items():
            if getattr(self, resource, 0) < amount:
                return False
        for resource, amount in requirements.items():
            self.consume_resource(resource, amount)
        return True

    # ------------------------------------------------------------------
    # Shop
    # ------------------------------------------------------------------

    def use_shop(self) -> bool:
        """Returns True if the company may access the shop this action."""
        return True

    # ------------------------------------------------------------------
    # Passive hook (overridden by subclasses)
    # ------------------------------------------------------------------

    def passive_ability(self) -> None:
        """Trigger the company's unique passive. Subclasses implement logic."""
        pass

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        r = self.get_resources()
        return (
            f"{self.__class__.__name__}({self.name!r}, "
            f"tech={r['tech']}, talent={r['talent']}, "
            f"support={r['support']}, funds={r['funds']}, "
            f"in_alliance={self.in_alliance})"
        )


# ----------------------------------------------------------------------
# Subclasses
# ----------------------------------------------------------------------

class TitanCompany(Company):
    """
    Titan (泰坦) — Base 3, Talent +2 → starts at (tech=3, talent=5, support=3, funds=3).
    Passive: [TBD — expected combat / seize advantage].
    """

    def passive_ability(self) -> None:
        """Placeholder for Titan's unique passive ability."""
        pass


class CelestialCompany(Company):
    """
    Celestial (天穹) — Base 1, Tech +3 → starts at (tech=4, talent=1, support=1, funds=1).
    Passive: Resource conversion (Tech → other resource types).
    """

    def passive_ability(self) -> None:
        """Placeholder for Celestial's passive ability."""
        pass

    def convert_resource(
        self,
        from_resource: str,
        to_resource: str,
        amount: int,
        rate: int = 1,
    ) -> bool:
        """
        Placeholder: convert `amount` of `from_resource` into `amount * rate`
        of `to_resource`. Exact conversion ratio TBD in full ruleset.
        Returns True on success, False if balance insufficient.
        """
        if not self.consume_resource(from_resource, amount):
            return False
        self.add_resource(to_resource, amount * rate)
        return True


class GalaxyCompany(Company):
    """
    Galaxy (銀河) — Base 1, Support +4 → starts at (tech=1, talent=1, support=5, funds=1).
    Constraint: Cannot use the shop while in an alliance.
    Passive: [TBD].
    """

    def use_shop(self) -> bool:
        """Shop access is blocked when the company is in an alliance."""
        if self.in_alliance:
            return False
        return True

    def passive_ability(self) -> None:
        """Placeholder for Galaxy's unique passive ability."""
        pass


class StellarCompany(Company):
    """
    Stellar (恆星) — Base 1, Funds +4 → starts at (tech=1, talent=1, support=1, funds=5).
    Passive: When in an alliance, the single resource requirement with the lowest
             cost value is exempt from consumption.
    """

    def consume_resources(self, requirements: ResourceDict) -> bool:
        """
        Stellar override: if in_alliance and requirements has ≥1 entry,
        drop the key with the smallest required amount before consuming.
        Tie-breaking follows dict iteration order (first minimum wins).
        """
        effective = requirements
        if self.in_alliance and requirements:
            exempt_key = min(requirements, key=lambda r: requirements[r])
            effective = {k: v for k, v in requirements.items() if k != exempt_key}

        for resource, amount in effective.items():
            if getattr(self, resource, 0) < amount:
                return False
        for resource, amount in effective.items():
            self.consume_resource(resource, amount)
        return True

    def passive_ability(self) -> None:
        """Placeholder for any additional Stellar passive logic."""
        pass
