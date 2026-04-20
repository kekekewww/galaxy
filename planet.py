from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Union


class PlanetStatus(Enum):
    EMPTY = "empty"
    LANDED = "landed"
    OCCUPIED = "occupied"


RewardDict = Dict[str, Union[int, str]]
RequirementDict = Dict[str, int]


class Planet:
    def __init__(
        self,
        name: str,
        land_req: Optional[RequirementDict],
        land_reward: Optional[RewardDict],
        occupy_req: RequirementDict,
        occupy_reward: RewardDict,
        seize_req: RequirementDict,
    ) -> None:
        self.name = name
        self.land_req = land_req          # None means cannot land (Sun)
        self.land_reward = land_reward    # None means no reward (Sun)
        self.occupy_req = occupy_req
        self.occupy_reward = occupy_reward
        self.seize_req = seize_req

        self.status: PlanetStatus = PlanetStatus.EMPTY
        self.occupant: Optional[str] = None  # company name of current occupant
        self.landers: List[str] = []         # companies with active Landed status

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------

    def can_land(self) -> bool:
        """
        Landing is allowed unless:
        - The planet has no landing mechanic (land_req is None and name is Sun), or
        - The planet is already Occupied.
        Earth has land_req=None but IS landable by default; Sun has land_req=None
        and is NOT landable. We distinguish by checking land_reward as well.
        """
        if self.land_req is None and self.land_reward is None:
            return False  # Sun: no land mechanic at all
        return self.status != PlanetStatus.OCCUPIED

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def land(self, company_name: str) -> bool:
        """
        Register company as Landed. Multiple companies may be Landed
        simultaneously as long as the planet is not Occupied.
        Returns False if landing is not allowed.
        """
        if not self.can_land():
            return False
        if company_name not in self.landers:
            self.landers.append(company_name)
        if self.status == PlanetStatus.EMPTY:
            self.status = PlanetStatus.LANDED
        return True

    def occupy(self, company_name: str) -> bool:
        """
        Set company as sole occupant. Clears all current landers per
        the exclusivity rule. Returns False if already Occupied (use seize).
        """
        if self.status == PlanetStatus.OCCUPIED:
            return False
        self.occupant = company_name
        self.landers = []
        self.status = PlanetStatus.OCCUPIED
        return True

    def seize(self, company_name: str) -> bool:
        """
        Transfer Occupied status to a new company. Clears landers.
        Returns False if the planet is not currently Occupied.
        """
        if self.status != PlanetStatus.OCCUPIED:
            return False
        self.occupant = company_name
        self.landers = []
        return True  # status remains OCCUPIED, occupant changes

    def remove_lander(self, company_name: str) -> None:
        """Remove a company's Landed status. Reverts to EMPTY if no landers remain."""
        if company_name in self.landers:
            self.landers.remove(company_name)
        if not self.landers and self.status == PlanetStatus.LANDED:
            self.status = PlanetStatus.EMPTY

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Planet({self.name!r}, status={self.status.value}, "
            f"occupant={self.occupant!r}, landers={self.landers})"
        )
