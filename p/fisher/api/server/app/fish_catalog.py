"""鱼种与钓场（与 `docs/产品规划-山海渔-完整版-v1.0.md` 数值表一致，供服务端随机与售卖结算）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class FishSpecies:
    id: int
    name: str
    price: int
    currency: str  # "coin" | "score"
    spot_id: int  # 0=乡村小河 … 见 SPOT_NAMES


# 钓场 id 与文案（MVP 先全开随机权重，后续可按 spot_id 过滤）
SPOT_NAMES: Final[dict[int, str]] = {
    0: "乡村小河",
    1: "野外池塘",
    2: "郊外湖泊",
    3: "沿江堤坝",
    4: "简易木质码头",
    5: "近海浅海码头",
}

SPECIES: Final[list[FishSpecies]] = [
    FishSpecies(1, "白条", 8, "coin", 0),
    FishSpecies(2, "小鲫鱼", 12, "coin", 0),
    FishSpecies(3, "麦穗鱼", 10, "coin", 0),
    FishSpecies(4, "小鲤鱼", 18, "coin", 1),
    FishSpecies(5, "罗非鱼", 22, "coin", 1),
    FishSpecies(6, "草鱼", 35, "coin", 2),
    FishSpecies(7, "青鱼", 48, "coin", 2),
    FishSpecies(8, "黑鱼", 55, "coin", 3),
    FishSpecies(9, "鲶鱼", 52, "coin", 3),
    FishSpecies(10, "巨型鲤鱼", 68, "coin", 3),
    FishSpecies(11, "小黄鱼", 2, "score", 4),
    FishSpecies(12, "带鱼", 3, "score", 4),
    FishSpecies(13, "海鲈", 5, "score", 5),
    FishSpecies(14, "鲷鱼", 6, "score", 5),
    FishSpecies(15, "变异浅海巨鱼", 12, "score", 5),
]

_BY_ID: dict[int, FishSpecies] = {s.id: s for s in SPECIES}


def species_by_id(sid: int) -> FishSpecies | None:
    return _BY_ID.get(int(sid))
