# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
sys.stdout.reconfigure(encoding='utf-8')

from typing import Dict, List, Optional, Tuple

from company import Company, StellarCompany, GalaxyCompany, RESOURCE_KEYS
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

    # -------------------------------------------------------------------
    # UI 工具方法
    # -------------------------------------------------------------------

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
        ally_key = self._alliances.get(company.name)
        ally_label = _cn(ally_key) if ally_key else "無"

        print("\n" + self._line("═"))
        print(f"  第 {self.current_turn} 回合  ——  {_cn(company.name)}")
        print(self._line("═"))
        print(f"  資源：{self._res_summary(company)}")
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

    # -------------------------------------------------------------------
    # 第 1 階段：商店
    # -------------------------------------------------------------------

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

            spendable = [r for r in RESOURCE_KEYS if getattr(company, r) >= 2]
            if not spendable:
                print("  │  無資源餘額 ≥ 2，無法交易。")
                break

            spend = _pick_resource("  │  消耗 2 點（選擇資源）：", spendable)
            others = [r for r in RESOURCE_KEYS if r != spend]
            gain  = _pick_resource("  │  獲得 1 點（選擇資源）：", others)

            company.consume_resource(spend, 2)
            company.add_resource(gain, 1)
            print(f"  │  ✓ 交易完成。{self._res_summary(company)}")
            trades_left -= 1

        print("  └")

    # -------------------------------------------------------------------
    # 第 2 階段：行動
    # -------------------------------------------------------------------

    def _effective_seize_req(
        self, company: Company, planet: Planet
    ) -> Dict[str, int]:
        """恆星被動：聯盟中搶佔時，免除最低費用的資源需求。"""
        req = planet.seize_req
        if isinstance(company, StellarCompany) and company.in_alliance and req:
            exempt = min(req, key=lambda k: req[k])
            return {k: v for k, v in req.items() if k != exempt}
        return req

    def _affordable_planets(
        self, company: Company, action: str
    ) -> List[Tuple[str, Planet]]:
        """回傳目前可執行指定行動且資源足夠的星球列表。"""
        results: List[Tuple[str, Planet]] = []
        for name, planet in self.planets.items():

            if action == "land":
                if not planet.can_land():
                    continue
                if company.name in planet.landers:
                    continue
                # 地球 land_req=None，免費；其他星球需確認資源
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
            if action_key == "land":
                cost = _req_display(planet.land_req, "免費（地球）")
            elif action_key == "occupy":
                cost = _req_display(planet.occupy_req)
            else:
                cost = _req_display(self._effective_seize_req(company, planet))
            print(f"  │    [{i}] {_pn(name):<24}  費用：{cost}")

        idx = _pick_int("  │  > ", 1, len(options)) - 1
        chosen_name, chosen_planet = options[idx]

        # 先扣除資源，再更新星球狀態
        if action_key == "land":
            if chosen_planet.land_req:
                if not company.consume_resources(chosen_planet.land_req):
                    print("  │  資源不足，行動取消。\n  └")
                    return
            chosen_planet.land(company.name)
            print(f"  │  ✓ {_cn(company.name)} 已落地於 {_pn(chosen_name)}。")

        elif action_key == "occupy":
            if not company.consume_resources(chosen_planet.occupy_req):
                print("  │  資源不足，行動取消。\n  └")
                return
            chosen_planet.occupy(company.name)
            print(f"  │  ✓ {_cn(company.name)} 佔領了 {_pn(chosen_name)}。")

        elif action_key == "seize":
            prev = chosen_planet.occupant
            effective_req = self._effective_seize_req(company, chosen_planet)
            if not company.consume_resources(effective_req):
                print("  │  資源不足，行動取消。\n  └")
                return
            chosen_planet.seize(company.name)
            print(
                f"  │  ✓ {_cn(company.name)} 從 {_cn(prev)} "
                f"手中搶佔了 {_pn(chosen_name)}。（原佔領者無懲罰）"
            )

        print("  └")

    # -------------------------------------------------------------------
    # 第 3 階段：聯盟
    # -------------------------------------------------------------------

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
            if isinstance(company, StellarCompany) or isinstance(partner, StellarCompany):
                print("  │    （恆星被動：搶佔時最低費用資源免除，現已生效）")
            if isinstance(company, GalaxyCompany) or isinstance(partner, GalaxyCompany):
                print("  │    （銀河限制：聯盟中商店封鎖，現已生效）")

        print("  └")

    # -------------------------------------------------------------------
    # 第 4 階段：事件
    # -------------------------------------------------------------------

    def _phase_event(self, company: Company) -> None:
        self._phase_banner(4, "事件")
        print("  │  抽取事件卡…（尚未實裝）")
        print("  └")

    # -------------------------------------------------------------------
    # 第 5 階段：結算
    # -------------------------------------------------------------------

    def _prompt_any_resource(
        self, company: Company, amount: int, source: str
    ) -> None:
        print(f"  │  獲得 {amount} 點任意資源（來源：{source}）。")
        for i in range(amount):
            label = f"（第 {i + 1}/{amount} 點）" if amount > 1 else ""
            chosen = _pick_resource(f"  │  {label}選擇資源：", list(RESOURCE_KEYS))
            company.add_resource(chosen, 1)
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
                company.add_resource(key, amount)
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

    # -------------------------------------------------------------------
    # 完整回合
    # -------------------------------------------------------------------

    def play_turn(self, company: Company) -> None:
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

    # -------------------------------------------------------------------
    # 勝利判定
    # -------------------------------------------------------------------

    def check_monopoly_victory(self) -> Optional[Company]:
        """若有公司同時佔領全部 9 個天體，回傳該公司；否則回傳 None。"""
        for company in self.companies:
            if all(
                planet.occupant == company.name
                for planet in self.planets.values()
            ):
                return company
        return None

    # -------------------------------------------------------------------
    # 主遊戲循環
    # -------------------------------------------------------------------

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
