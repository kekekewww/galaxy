# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
sys.stdout.reconfigure(encoding='utf-8')

from typing import Dict, List, Optional, Tuple

from company import (
    Company,
    TitanCompany,
    CelestialCompany,
    GalaxyCompany,
    StellarCompany,
    RESOURCE_KEYS,
)
from planet import Planet, PlanetStatus


# -----------------------------------------------------------------------
# Localization tables
# -----------------------------------------------------------------------

COMPANY_DISPLAY: Dict[str, str] = {
    "Titan":     "泰坦 (Titan)",
    "Celestial": "天穹 (Celestial)",
    "Galaxy":    "銀河 (Galaxy)",
    "Stellar":   "恆星 (Stellar)",
}

PLANET_DISPLAY: Dict[str, str] = {
    "Mercury": "水星 (Mercury)",
    "Venus":   "金星 (Venus)",
    "Earth":   "地球 (Earth)",
    "Mars":    "火星 (Mars)",
    "Jupiter": "木星 (Jupiter)",
    "Saturn":  "土星 (Saturn)",
    "Uranus":  "天王星 (Uranus)",
    "Neptune": "海王星 (Neptune)",
    "Sun":     "太陽 (Sun)",
}

RESOURCE_DISPLAY: Dict[str, str] = {
    "tech":    "技術",
    "talent":  "人才",
    "support": "支持",
    "funds":   "資金",
}

STATUS_DISPLAY: Dict[str, str] = {
    "empty":    "空置",
    "landed":   "落地",
    "occupied": "佔領",
}


# Convenience shorthands
def _cn(name: str) -> str:
    """Company display name."""
    return COMPANY_DISPLAY.get(name, name)


def _pn(name: str) -> str:
    """Planet display name."""
    return PLANET_DISPLAY.get(name, name)


def _rn(key: str) -> str:
    """Resource display name."""
    return RESOURCE_DISPLAY.get(key, key)


def _sn(status: PlanetStatus) -> str:
    """Status display name."""
    return STATUS_DISPLAY.get(status.value, status.value)


def _req_display(req: Optional[Dict[str, int]], free_label: str = "免費") -> str:
    """Format a requirement dict as a readable cost string."""
    if not req:
        return free_label
    return "  ".join(f"{_rn(k)}:{v}" for k, v in req.items())


# -----------------------------------------------------------------------
# Input helpers
# -----------------------------------------------------------------------

def _yes_no(prompt: str) -> bool:
    """Prompt until the user enters y/是 (True) or n/否 (False)."""
    while True:
        raw = input(prompt).strip().lower()
        if raw in ("y", "是"):
            return True
        if raw in ("n", "否"):
            return False
        print("  請輸入 y（是）或 n（否）。")


def _pick_int(prompt: str, lo: int, hi: int) -> int:
    """Prompt until the user enters an integer in [lo, hi]."""
    while True:
        raw = input(prompt).strip()
        if raw.lstrip("-").isdigit() and lo <= int(raw) <= hi:
            return int(raw)
        print(f"  請輸入 {lo} 到 {hi} 之間的數字。")


def _pick_resource(prompt: str, choices: List[str]) -> str:
    """Show a numbered resource menu and return the chosen resource key."""
    print(prompt)
    for i, key in enumerate(choices, 1):
        print(f"    [{i}] {_rn(key)}")
    idx = _pick_int("  > ", 1, len(choices)) - 1
    return choices[idx]


# -----------------------------------------------------------------------
# GameEngine
# -----------------------------------------------------------------------

class GameEngine:
    """
    主遊戲引擎，管理回合制流程與五個階段的推進。

    回合階段（嚴格順序）：
      1. 商店  — 資源交易（2:1，每回合最多 3 次）
      2. 行動  — 落地 / 佔領 / 搶佔 / 跳過
      3. 聯盟  — 組成或解除雙邊聯盟
      4. 事件  — 事件卡（佔位符）
      5. 結算  — 收取各星球的回合收益

    核心經濟系統：
      - 聯盟共用帳本：行動費用以雙方合計資源判定可行性，
        扣除時先從行動方扣除，不足部分由盟友支付。
      - 泰坦被動：搶佔使用佔領費用。
      - 天穹被動：獲得技術時可消耗 1 人才 → 2 額外技術（每回合一次）。
      - 恆星被動：聯盟中，最低費用資源需求免除。
    """

    def __init__(
        self,
        companies: List[Company],
        planets: Dict[str, Planet],
    ) -> None:
        self.companies: List[Company] = companies
        self.planets: Dict[str, Planet] = planets
        self.current_turn: int = 1
        # 雙邊聯盟表：公司名 → 盟友名
        self._alliances: Dict[str, str] = {}

    # ===================================================================
    # Alliance / Shared Ledger core
    # ===================================================================

    def _get_ally(self, company: Company) -> Optional[Company]:
        """Return the alliance partner object, or None."""
        ally_name = self._alliances.get(company.name)
        if ally_name is None:
            return None
        return next((c for c in self.companies if c.name == ally_name), None)

    def _combined_can_afford(
        self, company: Company, requirements: Dict[str, int]
    ) -> bool:
        """Check if the company + ally have enough combined resources."""
        if not requirements:
            return True
        ally = self._get_ally(company)
        for resource, amount in requirements.items():
            total = getattr(company, resource)
            if ally:
                total += getattr(ally, resource)
            if total < amount:
                return False
        return True

    def _consume_shared(
        self, company: Company, requirements: Dict[str, int]
    ) -> bool:
        """
        聯盟共用帳本扣除：先從行動方扣除，不足部分由盟友支付。
        Returns False (without mutating state) if combined total is insufficient.
        """
        ally = self._get_ally(company)

        # 1) Pre-check total affordability
        for resource, amount in requirements.items():
            total = getattr(company, resource)
            if ally:
                total += getattr(ally, resource)
            if total < amount:
                return False

        # 2) Deduct: active company first, overflow to ally
        for resource, amount in requirements.items():
            active_has = getattr(company, resource)
            if active_has >= amount:
                setattr(company, resource, active_has - amount)
            else:
                # Exhaust active company's balance, remainder from ally
                setattr(company, resource, 0)
                remaining = amount - active_has
                ally_has = getattr(ally, resource)  # type: ignore[union-attr]
                setattr(ally, resource, ally_has - remaining)  # type: ignore[union-attr]
                print(
                    f"  │    ⤷ 聯盟共用帳本："
                    f"{_cn(ally.name)} 支付 {remaining} {_rn(resource)}"  # type: ignore[union-attr]
                )
        return True

    # ===================================================================
    # Passive-aware requirement calculation
    # ===================================================================

    def _effective_requirements(
        self, company: Company, base_req: Dict[str, int]
    ) -> Dict[str, int]:
        """
        Apply Stellar's exemption to any requirement dict.
        Drops the lowest-cost key if the company or its ally is Stellar
        and the company is in an alliance.
        """
        if not base_req:
            return base_req
        ally = self._get_ally(company)
        is_stellar = (
            isinstance(company, StellarCompany)
            or (ally is not None and isinstance(ally, StellarCompany))
        )
        if is_stellar and company.in_alliance:
            exempt = min(base_req, key=lambda k: base_req[k])
            return {k: v for k, v in base_req.items() if k != exempt}
        return base_req

    def _seize_requirements(
        self, company: Company, planet: Planet
    ) -> Dict[str, int]:
        """
        Determine effective seize cost:
          1. Titan passive → use occupy_req instead of seize_req
          2. Stellar passive → drop lowest-cost key
        """
        ally = self._get_ally(company)
        is_titan = (
            isinstance(company, TitanCompany)
            or (ally is not None and isinstance(ally, TitanCompany))
        )
        base = planet.occupy_req if is_titan else planet.seize_req
        return self._effective_requirements(company, base)

    # ===================================================================
    # Celestial conversion trigger
    # ===================================================================

    def _check_celestial_conversion(
        self, company: Company, resource: str, amount: int
    ) -> None:
        """
        天穹被動：獲得技術時，可消耗 1 人才 → 2 額外技術（每回合一次）。
        人才消耗遵循聯盟共用帳本規則。額外技術歸觸發方。
        """
        if resource != "tech" or amount <= 0:
            return

        ally = self._get_ally(company)

        # Identify the Celestial company in this alliance (if any)
        celestial: Optional[CelestialCompany] = None
        if isinstance(company, CelestialCompany):
            celestial = company
        elif ally is not None and isinstance(ally, CelestialCompany):
            celestial = ally

        if celestial is None or celestial.used_conversion_this_turn:
            return

        # Check combined talent ≥ 1
        talent_total = company.talent
        if ally:
            talent_total += ally.talent
        if talent_total < 1:
            return

        # Display talent breakdown and prompt
        talent_detail = f"{_cn(company.name)}={company.talent}"
        if ally:
            talent_detail += f"  {_cn(ally.name)}={ally.talent}"

        print(f"  │")
        print(f"  │  ✦ 天穹被動觸發！可消耗 1 人才 → 獲得 2 額外技術")
        print(f"  │    目前人才：{talent_detail}")

        if _yes_no("  │    是否轉換？(y/n)："):
            self._consume_shared(company, {"talent": 1})
            company.add_resource("tech", 2)  # direct add — no re-trigger
            celestial.used_conversion_this_turn = True
            print(f"  │    ✓ 轉換完成！-1 人才，+2 技術。")
            print(f"  │    目前資源：{self._res_summary(company)}")

    def _grant_resource(
        self, company: Company, resource: str, amount: int
    ) -> None:
        """
        Add resource then check Celestial conversion trigger.
        Use this instead of company.add_resource() wherever the engine grants
        resources (shop gains, settlement rewards, etc.).
        """
        company.add_resource(resource, amount)
        self._check_celestial_conversion(company, resource, amount)

    # ===================================================================
    # UI helpers
    # ===================================================================

    @staticmethod
    def _line(char: str = "─", width: int = 62) -> str:
        return char * width

    def _res_summary(self, company: Company) -> str:
        r = company.get_resources()
        return (
            f"技術={r['tech']}  人才={r['talent']}  "
            f"支持={r['support']}  資金={r['funds']}"
        )

    def _print_header(self, company: Company) -> None:
        ally = self._get_ally(company)
        ally_label = _cn(ally.name) if ally else "無"

        print("\n" + self._line("═"))
        print(f"  第 {self.current_turn} 回合  ——  {_cn(company.name)}")
        print(self._line("═"))
        print(f"  資源：{self._res_summary(company)}")
        if ally:
            print(f"  聯盟：{ally_label}  （{self._res_summary(ally)}）")
        else:
            print(f"  聯盟：{ally_label}")
        print()
        print("  ── 天體狀態 " + "─" * 44)
        for planet in self.planets.values():
            if planet.status == PlanetStatus.OCCUPIED:
                detail = f"佔領者：{_cn(planet.occupant)}"
            elif planet.status == PlanetStatus.LANDED:
                detail = "落地者：" + "、".join(_cn(c) for c in planet.landers)
            else:
                detail = ""
            if planet.occupant == company.name:
                marker = " ◀"
            elif company.name in planet.landers:
                marker = " ·"
            else:
                marker = "  "
            print(
                f"  {marker} {_pn(planet.name):<22}  [{_sn(planet.status):<2}]  {detail}"
            )
        print(self._line())

    @staticmethod
    def _phase_banner(number: int, name: str) -> None:
        print(f"\n  ┌── 第 {number} 階段：{name} " + "─" * 38 + "┐")

    # ===================================================================
    # 第 1 階段：商店
    # ===================================================================

    def _phase_shop(self, company: Company) -> None:
        self._phase_banner(1, "商店")
        if not company.use_shop():
            print(f"  │  【{_cn(company.name)}】聯盟中，商店已封鎖，跳過。")
            print("  └")
            return

        trades_left = 3
        while trades_left > 0:
            print(f"  │  剩餘交易次數：{trades_left}/3  ｜  {self._res_summary(company)}")
            if not _yes_no("  │  是否進行交易？(y/n)："):
                break

            # Shop trades use the company's OWN resources only (not shared ledger)
            spendable = [r for r in RESOURCE_KEYS if getattr(company, r) >= 2]
            if not spendable:
                print("  │  無資源餘額 ≥ 2，無法交易。")
                break

            spend = _pick_resource("  │  消耗 2 點（選擇資源）：", spendable)
            others = [r for r in RESOURCE_KEYS if r != spend]
            gain  = _pick_resource("  │  獲得 1 點（選擇資源）：", others)

            company.consume_resource(spend, 2)
            self._grant_resource(company, gain, 1)   # may trigger Celestial
            print(f"  │  ✓ 交易完成。{self._res_summary(company)}")
            trades_left -= 1

        print("  └")

    # ===================================================================
    # 第 2 階段：行動
    # ===================================================================

    def _action_requirements(
        self, company: Company, planet: Planet, action: str
    ) -> Optional[Dict[str, int]]:
        """
        Return the effective requirement dict for an action on a planet,
        with all applicable passives (Titan, Stellar) factored in.
        Returns None for free actions (Earth land).
        """
        if action == "land":
            if planet.land_req is None:
                return None  # free (Earth)
            return self._effective_requirements(company, planet.land_req)
        elif action == "occupy":
            return self._effective_requirements(company, planet.occupy_req)
        else:  # seize
            return self._seize_requirements(company, planet)

    def _affordable_planets(
        self, company: Company, action: str
    ) -> List[Tuple[str, Planet]]:
        """回傳目前可執行指定行動且合計資源（含盟友）足夠的星球列表。"""
        results: List[Tuple[str, Planet]] = []
        for name, planet in self.planets.items():

            if action == "land":
                if not planet.can_land():
                    continue
                if company.name in planet.landers:
                    continue
                req = self._action_requirements(company, planet, "land")
                if req is not None and not self._combined_can_afford(company, req):
                    continue
                results.append((name, planet))

            elif action == "occupy":
                if planet.status != PlanetStatus.LANDED:
                    continue
                if company.name not in planet.landers:
                    continue
                req = self._action_requirements(company, planet, "occupy")
                if req is not None and not self._combined_can_afford(company, req):
                    continue
                results.append((name, planet))

            elif action == "seize":
                if planet.status != PlanetStatus.OCCUPIED:
                    continue
                if planet.occupant == company.name:
                    continue
                req = self._action_requirements(company, planet, "seize")
                if req is not None and not self._combined_can_afford(company, req):
                    continue
                results.append((name, planet))

        return results

    def _phase_action(self, company: Company) -> None:
        self._phase_banner(2, "行動")
        print("  │  [1] 落地   [2] 佔領   [3] 搶佔   [4] 跳過")
        choice = _pick_int("  │  > ", 1, 4)

        if choice == 4:
            print("  │  已跳過。\n  └")
            return

        action_key   = {1: "land",   2: "occupy",  3: "seize"}[choice]
        action_label = {1: "落地",   2: "佔領",    3: "搶佔"}[choice]

        options = self._affordable_planets(company, action_key)
        if not options:
            print(f"  │  目前沒有可執行【{action_label}】的星球。\n  └")
            return

        print(f"\n  │  選擇要【{action_label}】的星球：")
        for i, (name, planet) in enumerate(options, 1):
            req = self._action_requirements(company, planet, action_key)
            cost = _req_display(req, "免費（地球）")
            print(f"  │    [{i}] {_pn(name):<24}  費用：{cost}")

        idx = _pick_int("  │  > ", 1, len(options)) - 1
        chosen_name, chosen_planet = options[idx]

        # 先扣除資源（聯盟共用帳本），再更新星球狀態
        req = self._action_requirements(company, chosen_planet, action_key)

        if action_key == "land":
            if req is not None:
                if not self._consume_shared(company, req):
                    print("  │  資源不足，行動取消。\n  └")
                    return
            chosen_planet.land(company.name)
            print(f"  │  ✓ {_cn(company.name)} 已落地於 {_pn(chosen_name)}。")

        elif action_key == "occupy":
            if not self._consume_shared(company, req):  # type: ignore[arg-type]
                print("  │  資源不足，行動取消。\n  └")
                return
            chosen_planet.occupy(company.name)
            print(f"  │  ✓ {_cn(company.name)} 佔領了 {_pn(chosen_name)}。")

        elif action_key == "seize":
            prev = chosen_planet.occupant
            if not self._consume_shared(company, req):  # type: ignore[arg-type]
                print("  │  資源不足，行動取消。\n  └")
                return
            chosen_planet.seize(company.name)
            print(
                f"  │  ✓ {_cn(company.name)} 從 {_cn(prev)} "
                f"手中搶佔了 {_pn(chosen_name)}。（原佔領者無懲罰）"
            )

        print("  └")

    # ===================================================================
    # 第 3 階段：聯盟
    # ===================================================================

    def _phase_alliance(self, company: Company) -> None:
        self._phase_banner(3, "聯盟")
        current_ally = self._alliances.get(company.name)

        if current_ally:
            print(
                f"  │  目前聯盟：{_cn(company.name)} ↔ {_cn(current_ally)}"
            )
            if _yes_no("  │  是否解除聯盟？(y/n)："):
                ally_obj = next(
                    (c for c in self.companies if c.name == current_ally), None
                )
                company.in_alliance = False
                if ally_obj:
                    ally_obj.in_alliance = False
                self._alliances.pop(company.name, None)
                self._alliances.pop(current_ally, None)
                print(
                    f"  │  聯盟已解除：{_cn(company.name)} 與 "
                    f"{_cn(current_ally)} 各自獨立。"
                )
            else:
                print("  │  維持現有聯盟。")

        else:
            print("  │  目前聯盟：無")
            if not _yes_no("  │  是否組成聯盟？(y/n)："):
                print("  └")
                return

            available = [
                c for c in self.companies
                if c.name != company.name and c.name not in self._alliances
            ]
            if not available:
                print("  │  目前無可結盟的公司（其他公司均已在聯盟中）。")
                print("  └")
                return

            print("  │  可選夥伴：")
            for i, c in enumerate(available, 1):
                r = c.get_resources()
                print(
                    f"  │    [{i}] {_cn(c.name):<22}  "
                    f"技術={r['tech']}  人才={r['talent']}  "
                    f"支持={r['support']}  資金={r['funds']}"
                )
            idx = _pick_int("  │  > ", 1, len(available)) - 1
            partner = available[idx]

            company.in_alliance = True
            partner.in_alliance = True
            self._alliances[company.name] = partner.name
            self._alliances[partner.name] = company.name
            print(
                f"  │  ✓ 聯盟成立：{_cn(company.name)} ↔ {_cn(partner.name)}"
            )
            # Notify applicable passives
            if isinstance(company, TitanCompany) or isinstance(partner, TitanCompany):
                print("  │    （泰坦被動：搶佔使用佔領費用，現已生效）")
            if isinstance(company, StellarCompany) or isinstance(partner, StellarCompany):
                print("  │    （恆星被動：最低費用資源需求免除，現已生效）")
            if isinstance(company, CelestialCompany) or isinstance(partner, CelestialCompany):
                print("  │    （天穹被動：獲得技術時可轉換人才，現已生效）")
            if isinstance(company, GalaxyCompany) or isinstance(partner, GalaxyCompany):
                print("  │    （銀河限制：聯盟中商店封鎖，現已生效）")

        print("  └")

    # ===================================================================
    # 第 4 階段：事件
    # ===================================================================

    def _phase_event(self, company: Company) -> None:
        self._phase_banner(4, "事件")
        print("  │  抽取事件卡…（尚未實裝）")
        print("  └")

    # ===================================================================
    # 第 5 階段：結算
    # ===================================================================

    def _prompt_any_resource(
        self, company: Company, amount: int, source: str
    ) -> None:
        print(f"  │  獲得 {amount} 點任意資源（來源：{source}）。")
        for i in range(amount):
            label = f"（第 {i + 1}/{amount} 點）" if amount > 1 else ""
            chosen = _pick_resource(f"  │  {label}選擇資源：", list(RESOURCE_KEYS))
            self._grant_resource(company, chosen, 1)   # may trigger Celestial
            print(f"  │    +1 {_rn(chosen)}  →  目前 {getattr(company, chosen)}")

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
                    f"  │  【{_cn(company.name)}】觸發特殊效果：『{value}』"
                    f"（{source}）— 尚未實裝"
                )
            else:
                amount = int(value)  # type: ignore[arg-type]
                self._grant_resource(company, key, amount)   # may trigger Celestial
                sign = "+" if amount >= 0 else ""
                print(
                    f"  │  【{_cn(company.name)}】{source}：{sign}{amount} {_rn(key)}"
                )

    def _phase_settlement(self, company: Company) -> None:
        self._phase_banner(5, "結算")
        earned = False
        for planet in self.planets.values():
            pname = _pn(planet.name)
            if company.name in planet.landers and planet.land_reward:
                self._apply_reward(company, planet.land_reward, f"{pname} 落地")
                earned = True
            if planet.occupant == company.name and planet.occupy_reward:
                self._apply_reward(company, planet.occupy_reward, f"{pname} 佔領")
                earned = True
        if not earned:
            print("  │  本回合無收益。")
        print("  └")

    # ===================================================================
    # 完整回合
    # ===================================================================

    def play_turn(self, company: Company) -> None:
        # 重置天穹被動（每回合每公司可觸發一次）
        for c in self.companies:
            if isinstance(c, CelestialCompany):
                c.reset_conversion_flag()

        self._print_header(company)
        input(f"  【按 Enter 開始 {_cn(company.name)} 的回合…】")

        self._phase_shop(company)
        self._phase_action(company)
        self._phase_alliance(company)
        self._phase_event(company)
        self._phase_settlement(company)

        r = company.get_resources()
        print(f"\n  ── {_cn(company.name)} 回合結束 " + "─" * 32)
        print(
            f"  最終資源：技術={r['tech']}  人才={r['talent']}  "
            f"支持={r['support']}  資金={r['funds']}"
        )
        print(self._line())

    # ===================================================================
    # 勝利判定
    # ===================================================================

    def check_monopoly_victory(self) -> Optional[Company]:
        """若有公司同時佔領全部 9 個天體，回傳該公司；否則回傳 None。"""
        for company in self.companies:
            if all(
                planet.occupant == company.name
                for planet in self.planets.values()
            ):
                return company
        return None

    # ===================================================================
    # 主遊戲循環
    # ===================================================================

    def run(self) -> None:
        print("\n" + "★" * 62)
        print("   星海之霸（Star Sea Hegemony）  ——  遊戲開始")
        print("★" * 62)

        while True:
            for company in self.companies:
                self.play_turn(company)

                winner = self.check_monopoly_victory()
                if winner:
                    print("\n" + "★" * 62)
                    print(f"   勝利！{_cn(winner.name)} 已完成星際壟斷！")
                    print(f"   共歷時 {self.current_turn} 回合。")
                    print("★" * 62)
                    return

            self.current_turn += 1
