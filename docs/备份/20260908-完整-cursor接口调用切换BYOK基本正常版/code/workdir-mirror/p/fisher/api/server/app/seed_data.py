"""种子数据：首次启动时自动填充钓场和鱼种表。

每新增钓场/鱼种只需在此文件追加一行数据，API 重启即生效。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import FishSpecies, FishingSpot

# ---- 钓场（sort_order 控制展示顺序） ----
SPOTS_SEED: list[dict] = [
    {"id": 0, "name": "乡村小河", "sort_order": 0, "unlock_coins": 0, "unlock_rod_level": 0,
     "description": "家门口的小河沟，水流平缓，适合新手练手。"},
    {"id": 1, "name": "野外池塘", "sort_order": 1, "unlock_coins": 0, "unlock_rod_level": 0,
     "description": "绿树环绕的野塘，水草丛生，暗藏好货。"},
    {"id": 2, "name": "郊外湖泊", "sort_order": 2, "unlock_coins": 300, "unlock_rod_level": 0,
     "description": "晨雾缭绕的大湖，鱼种丰富，是进阶钓手的天堂。"},
    {"id": 3, "name": "沿江堤坝", "sort_order": 3, "unlock_coins": 800, "unlock_rod_level": 2,
     "description": "江水奔腾，暗流涌动，只有老手才敢下竿。"},
    {"id": 4, "name": "近海码头", "sort_order": 4, "unlock_coins": 1500, "unlock_rod_level": 5,
     "description": "咸腥的海风扑面，远处白帆点点，该征服大海了。"},
    {"id": 5, "name": "秘境暗流", "sort_order": 5, "unlock_coins": 3000, "unlock_score": 200, "unlock_rod_level": 8,
     "description": "传说中的地下暗河，荧光水母照亮幽深水域，栖息着远古异种。"},
    {"id": 6, "name": "龙宫深渊", "sort_order": 6, "unlock_coins": 6000, "unlock_score": 500, "unlock_rod_level": 12,
     "description": "深海裂谷万丈之下，龙宫的残垣散落海底，传说之鱼在此巡游。"},
    {"id": 7, "name": "远古海域", "sort_order": 7, "unlock_coins": 12000, "unlock_score": 1000, "unlock_rod_level": 18,
     "description": "时间尽头的原始海洋，巨兽横行，只有最顶尖的钓者才敢踏足。"},
]

# ---- 鱼种（rarity: common/uncommon/rare/epic/legendary） ----
SPECIES_SEED: list[dict] = [
    # 乡村小河 (spot 0) — 入门鱼
    {"id": 1, "name": "白条", "spot_id": 0, "price": 8, "currency": "coin", "rarity": "common",
     "weight_min": 0.02, "weight_max": 0.15, "description": "最常见的小杂鱼，油炸很香。"},
    {"id": 2, "name": "小鲫鱼", "spot_id": 0, "price": 12, "currency": "coin", "rarity": "common",
     "weight_min": 0.05, "weight_max": 0.3, "description": "乡间小河的特产，熬汤鲜美。"},
    {"id": 3, "name": "麦穗鱼", "spot_id": 0, "price": 10, "currency": "coin", "rarity": "common",
     "weight_min": 0.01, "weight_max": 0.08, "description": "身形细长如麦穗，成群结队。"},
    {"id": 4, "name": "塘鳢", "spot_id": 0, "price": 20, "currency": "coin", "rarity": "uncommon",
     "weight_min": 0.05, "weight_max": 0.25, "description": "趴在石头底下的懒家伙。"},
    {"id": 5, "name": "河鳗", "spot_id": 0, "price": 35, "currency": "coin", "rarity": "rare",
     "weight_min": 0.3, "weight_max": 1.5, "description": "滑溜溜的夜行者，力气不小。"},
    {"id": 6, "name": "金色小鲫", "spot_id": 0, "price": 55, "currency": "coin", "rarity": "epic",
     "weight_min": 0.2, "weight_max": 0.6, "description": "罕见的金色变种，传说能带来好运。"},

    # 野外池塘 (spot 1)
    {"id": 7, "name": "小鲤鱼", "spot_id": 1, "price": 18, "currency": "coin", "rarity": "common",
     "weight_min": 0.1, "weight_max": 0.8, "description": "鲤鱼跃龙门的幼年版。"},
    {"id": 8, "name": "罗非鱼", "spot_id": 1, "price": 22, "currency": "coin", "rarity": "common",
     "weight_min": 0.15, "weight_max": 0.6, "description": "来自非洲的入侵者，繁殖力惊人。"},
    {"id": 9, "name": "泥鳅", "spot_id": 1, "price": 15, "currency": "coin", "rarity": "common",
     "weight_min": 0.02, "weight_max": 0.1, "description": "淤泥里的小泥鳅，滑不溜手。"},
    {"id": 10, "name": "黄颡鱼", "spot_id": 1, "price": 28, "currency": "coin", "rarity": "uncommon",
     "weight_min": 0.1, "weight_max": 0.5, "description": "嘎牙子，背鳍有毒刺，小心摘钩。"},
    {"id": 11, "name": "鳜鱼", "spot_id": 1, "price": 45, "currency": "coin", "rarity": "rare",
     "weight_min": 0.3, "weight_max": 2.0, "description": "桃花流水鳜鱼肥，淡水鱼中的贵族。"},
    {"id": 12, "name": "锦鲤王", "spot_id": 1, "price": 80, "currency": "coin", "rarity": "epic",
     "weight_min": 1.5, "weight_max": 5.0, "description": "身披彩鳞的池中王者。"},

    # 郊外湖泊 (spot 2)
    {"id": 13, "name": "草鱼", "spot_id": 2, "price": 35, "currency": "coin", "rarity": "common",
     "weight_min": 0.5, "weight_max": 3.0, "description": "吃草的巨物，上钩后力道十足。"},
    {"id": 14, "name": "青鱼", "spot_id": 2, "price": 48, "currency": "coin", "rarity": "uncommon",
     "weight_min": 1.0, "weight_max": 8.0, "description": "湖底的石螺杀手，体长可达一米。"},
    {"id": 15, "name": "鲢鱼", "spot_id": 2, "price": 30, "currency": "coin", "rarity": "common",
     "weight_min": 0.5, "weight_max": 2.5, "description": "滤食浮游生物，净化水质的好帮手。"},
    {"id": 16, "name": "鳙鱼", "spot_id": 2, "price": 38, "currency": "coin", "rarity": "uncommon",
     "weight_min": 1.0, "weight_max": 5.0, "description": "大头鱼，剁椒鱼头的主角。"},
    {"id": 17, "name": "甲鱼", "spot_id": 2, "price": 70, "currency": "coin", "rarity": "rare",
     "weight_min": 0.5, "weight_max": 3.0, "description": "不是鱼，是鳖！大补之物。"},
    {"id": 18, "name": "湖中巨鲤", "spot_id": 2, "price": 120, "currency": "score", "rarity": "epic",
     "weight_min": 5.0, "weight_max": 15.0, "description": "传说活了上百年的老鲤，鳞片如铜钱大小。"},

    # 沿江堤坝 (spot 3)
    {"id": 19, "name": "黑鱼", "spot_id": 3, "price": 55, "currency": "coin", "rarity": "uncommon",
     "weight_min": 1.0, "weight_max": 5.0, "description": "凶猛的掠食者，牙齿锋利。"},
    {"id": 20, "name": "鲶鱼", "spot_id": 3, "price": 52, "currency": "coin", "rarity": "uncommon",
     "weight_min": 0.8, "weight_max": 6.0, "description": "江底的夜行巨兽，两根长须如鞭。"},
    {"id": 21, "name": "巨型鲤鱼", "spot_id": 3, "price": 68, "currency": "coin", "rarity": "uncommon",
     "weight_min": 2.0, "weight_max": 10.0, "description": "江中力道十足的搏斗者。"},
    {"id": 22, "name": "鳡鱼", "spot_id": 3, "price": 85, "currency": "coin", "rarity": "rare",
     "weight_min": 3.0, "weight_max": 15.0, "description": "淡水鲨鱼！时速可达60公里。"},
    {"id": 23, "name": "鲟鱼", "spot_id": 3, "price": 150, "currency": "score", "rarity": "rare",
     "weight_min": 5.0, "weight_max": 30.0, "description": "活化石，鱼子酱来自它的后代。"},
    {"id": 24, "name": "江豚", "spot_id": 3, "price": 300, "currency": "score", "rarity": "legendary",
     "weight_min": 30.0, "weight_max": 80.0, "description": "长江的微笑天使…你不会真的钓它吧？拍照放生后获得大量积分。"},

    # 近海码头 (spot 4)
    {"id": 25, "name": "小黄鱼", "spot_id": 4, "price": 2, "currency": "score", "rarity": "common",
     "weight_min": 0.05, "weight_max": 0.3, "description": "金黄的小家伙，香煎最好吃。"},
    {"id": 26, "name": "带鱼", "spot_id": 4, "price": 3, "currency": "score", "rarity": "common",
     "weight_min": 0.3, "weight_max": 1.5, "description": "银光闪闪的带子，离开水面就死。"},
    {"id": 27, "name": "海鲈", "spot_id": 4, "price": 5, "currency": "score", "rarity": "uncommon",
     "weight_min": 1.0, "weight_max": 5.0, "description": "海钓入门的最佳目标鱼。"},
    {"id": 28, "name": "鲷鱼", "spot_id": 4, "price": 6, "currency": "score", "rarity": "uncommon",
     "weight_min": 0.5, "weight_max": 3.0, "description": "真鲷，红色喜庆，刺身极品。"},
    {"id": 29, "name": "石斑鱼", "spot_id": 4, "price": 10, "currency": "score", "rarity": "rare",
     "weight_min": 2.0, "weight_max": 15.0, "description": "礁石区的霸王，清蒸一绝。"},
    {"id": 30, "name": "变异浅海巨鱼", "spot_id": 4, "price": 12, "currency": "score", "rarity": "rare",
     "weight_min": 10.0, "weight_max": 50.0, "description": "核废水造就的怪物？还是深海逃上来的异兽？"},

    # 秘境暗流 (spot 5)
    {"id": 31, "name": "荧光水母鱼", "spot_id": 5, "price": 8, "currency": "score", "rarity": "common",
     "weight_min": 0.01, "weight_max": 0.2, "description": "透明身体发出幽幽蓝光，像游动的小灯泡。"},
    {"id": 32, "name": "盲眼洞穴鱼", "spot_id": 5, "price": 10, "currency": "score", "rarity": "common",
     "weight_min": 0.05, "weight_max": 0.3, "description": "没有眼睛，靠侧线感知一切。"},
    {"id": 33, "name": "石甲鲶", "spot_id": 5, "price": 15, "currency": "score", "rarity": "uncommon",
     "weight_min": 0.5, "weight_max": 3.0, "description": "皮肤硬如岩石，在暗河中擦身而过。"},
    {"id": 34, "name": "电鳗", "spot_id": 5, "price": 20, "currency": "score", "rarity": "uncommon",
     "weight_min": 1.0, "weight_max": 8.0, "description": "别碰！800伏特高压，瞬间麻痹。"},
    {"id": 35, "name": "暗河巨骨舌鱼", "spot_id": 5, "price": 35, "currency": "score", "rarity": "rare",
     "weight_min": 20.0, "weight_max": 100.0, "description": "亚马逊的远古巨鱼，不知如何出现在这里。"},
    {"id": 36, "name": "幽灵水母王", "spot_id": 5, "price": 60, "currency": "score", "rarity": "epic",
     "weight_min": 0.5, "weight_max": 5.0, "description": "千年水母王，触手可延伸数十米。"},
    {"id": 37, "name": "深渊巨口", "spot_id": 5, "price": 100, "currency": "score", "rarity": "legendary",
     "weight_min": 50.0, "weight_max": 200.0, "description": "暗河最深处的传说，张开的大嘴能吞下一艘小船。"},

    # 龙宫深渊 (spot 6)
    {"id": 38, "name": "灯笼鱼", "spot_id": 6, "price": 12, "currency": "score", "rarity": "common",
     "weight_min": 0.05, "weight_max": 0.5, "description": "头顶发光器，深海中的点点星光。"},
    {"id": 39, "name": "深海鳕鱼", "spot_id": 6, "price": 15, "currency": "score", "rarity": "common",
     "weight_min": 0.5, "weight_max": 3.0, "description": "冷冽深海中的肥美鱼生。"},
    {"id": 40, "name": "龙宫侍女锦鲤", "spot_id": 6, "price": 25, "currency": "score", "rarity": "uncommon",
     "weight_min": 2.0, "weight_max": 8.0, "description": "身披七彩鳞片，据说是龙宫侍女的化身。"},
    {"id": 41, "name": "龟丞相", "spot_id": 6, "price": 40, "currency": "score", "rarity": "rare",
     "weight_min": 10.0, "weight_max": 50.0, "description": "背甲上刻着古老文字的大海龟。"},
    {"id": 42, "name": "深海鮟鱇", "spot_id": 6, "price": 45, "currency": "score", "rarity": "rare",
     "weight_min": 5.0, "weight_max": 30.0, "description": "丑到极致就是美，深海猎手。"},
    {"id": 43, "name": "龙王幼子", "spot_id": 6, "price": 80, "currency": "score", "rarity": "epic",
     "weight_min": 30.0, "weight_max": 150.0, "description": "身披金鳞的小龙，角刚冒出头顶。"},
    {"id": 44, "name": "深海龙鱼", "spot_id": 6, "price": 150, "currency": "score", "rarity": "legendary",
     "weight_min": 100.0, "weight_max": 500.0, "description": "龙宫深渊的主人，鳞片比盔甲还硬，一口龙息可蒸干浅海。"},

    # 远古海域 (spot 7)
    {"id": 45, "name": "三叶虫", "spot_id": 7, "price": 20, "currency": "score", "rarity": "common",
     "weight_min": 0.01, "weight_max": 0.1, "description": "寒武纪的活化石，居然上了钩！"},
    {"id": 46, "name": "菊石", "spot_id": 7, "price": 30, "currency": "score", "rarity": "uncommon",
     "weight_min": 0.5, "weight_max": 5.0, "description": "螺旋外壳的远古头足类，触手依然在蠕动。"},
    {"id": 47, "name": "邓氏鱼", "spot_id": 7, "price": 50, "currency": "score", "rarity": "rare",
     "weight_min": 50.0, "weight_max": 200.0, "description": "泥盆纪的海洋霸主，咬合力数吨！"},
    {"id": 48, "name": "巨齿鲨", "spot_id": 7, "price": 80, "currency": "score", "rarity": "epic",
     "weight_min": 1000.0, "weight_max": 5000.0, "description": "史上最强掠食者，一颗牙比手掌还大。"},
    {"id": 49, "name": "利维坦鲸", "spot_id": 7, "price": 120, "currency": "score", "rarity": "epic",
     "weight_min": 3000.0, "weight_max": 10000.0, "description": "远古巨鲸，与巨齿鲨争夺海洋霸权。"},
    {"id": 50, "name": "远古海神", "spot_id": 7, "price": 300, "currency": "score", "rarity": "legendary",
     "weight_min": 10000.0, "weight_max": 50000.0, "description": "时间尽头的终极存在，钓上它的人将成为新的传说。"},
]


def seed_catalog(db: Session) -> None:
    """首次启动时填充钓场和鱼种，已存在则跳过。"""
    from .models import FishingSpot, FishSpecies

    existing_spots = db.query(FishingSpot).count()
    if existing_spots == 0:
        for s in SPOTS_SEED:
            db.add(FishingSpot(**s))
        db.commit()
        print(f"[seed] Created {len(SPOTS_SEED)} fishing spots")

    existing_species = db.query(FishSpecies).count()
    if existing_species == 0:
        for s in SPECIES_SEED:
            db.add(FishSpecies(**s))
        db.commit()
        print(f"[seed] Created {len(SPECIES_SEED)} fish species")
