"""
查询理解与扩展模块
在用户输入过于宽泛（大类、用途、场景）时，自动联想出具体商品关键词，
使底层 best_price_mcp 能够有效返回结果。

工作流程：
1. 判断输入是否为宽泛查询
2. 从同义词库、类别映射库、用途映射库中扩展出候选关键词列表
3. 按优先级排序后返回，由上层 agent 逐个尝试搜索并合并结果
"""

import re
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# 同义词/别名映射：一个词对应一组可互换的表达
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 同义词/别名映射：一个词对应一组可互换的表达
#
# 注意：只保留**无歧义**的同义词。比如 "笔记本电脑" 的同义词列表里，
# 不能有 "笔记本" 这种歧义大的词（既指电子笔记本也指纸质笔记本/文具）。
# 有歧义的词统一加限定词，如 "笔记本" → "笔记本 电脑"，避免被底层 MCP 误解。
# ---------------------------------------------------------------------------

# 已知的歧义/危险词：这些词单独拿去搜大概率返回不相关商品，
# 要么加限定词用，要么直接从同义词里移除。
_DISAMBIGUOUS_TERMS: Dict[str, str] = {
    "笔记本": "笔记本 电脑",   # 单独"笔记本"→文具；加限定词让搜索引擎明确
    "笔电":  "笔记本电脑",     # 口语缩写，底层 MCP 识别不了
    "laptop": "笔记本电脑",    # 英文缩写，底层 MCP 可能匹配不上
    "手机":  None,            # "手机"→独立词本身可用，但不做它的同义词源
    "平板":  "平板电脑",       # 单独"平板"→可能匹配其他品类
    "耳机":  None,            # 可用
    "屏幕":  "显示器",         # 单独"屏幕"→范围太广
    "键盘":  None,
    "鼠标":  None,
    "手表":  "智能手表",       # 单独"手表"→可能匹配机械表
    "牙刷":  "电动牙刷",       # 单独"牙刷"→可能匹配普通牙刷
    "硬盘":  "机械硬盘",       # 单独"硬盘"→范围太广
    "净化器": "空气净化器",
    "奶粉":  "婴儿奶粉",
    "跑鞋":  "跑步鞋",         # 单独"跑鞋"→可能匹配不同品类
}


def _disambiguate(term: str) -> Optional[str]:
    """如果 term 是已知的歧义词，返回加了限定词的安全版本；否则返回原词。"""
    if term in _DISAMBIGUOUS_TERMS:
        fixed = _DISAMBIGUOUS_TERMS[term]
        return fixed if fixed else None  # None 表示直接丢弃
    return term


SYNONYM_MAP: Dict[str, List[str]] = {
    "笔记本电脑": [
        _d for _d in [_disambiguate("手提电脑"), _disambiguate("笔记本"),
                      _disambiguate("laptop"), _disambiguate("笔电"),
                      _disambiguate("便携电脑")] if _d
    ],
    "笔记本": [
        _d for _d in [_disambiguate("笔记本电脑"), _disambiguate("手提电脑"),
                      _disambiguate("便携电脑")] if _d
    ],
    "电脑": ["台式机", "pc"],
    "台式电脑": ["台式机", "桌面电脑", "pc主机", "diy电脑"],
    "台式机": ["台式电脑", "pc主机", "diy电脑"],
    "平板": [_disambiguate("平板电脑")],
    "平板电脑": ["平板"],
    "手机": ["移动电话", "智能机"],
    "耳机": ["耳麦", "头戴耳机", "入耳耳机"],
    "无线耳机": ["蓝牙耳机", "tws耳机", "蓝牙无线耳机"],
    "显示器": ["显示屏"],
    "显卡": ["gpu"],
    "固态硬盘": ["ssd", "固态盘"],
    "机械硬盘": ["hdd"],
    "路由器": ["无线路由器", "wifi路由器"],
    "键盘": [],
    "鼠标": [],
    "键盘鼠标": ["键鼠套装"],
    "打印机": [],
    "投影仪": ["投影机"],
    "智能手表": [_disambiguate("手表"), "智能腕表"],
    "手表": [_disambiguate("智能手表")],
    "手环": ["运动手环", "智能手环"],
    "扫地机器人": ["扫地机"],
    "空气净化器": [_disambiguate("净化器")],
    "空调": [],
    "冰箱": ["电冰箱"],
    "洗衣机": [],
    "吹风机": ["电吹风"],
    "剃须刀": ["电动剃须刀"],
    "电动牙刷": [_disambiguate("牙刷")],
    "空气炸锅": ["无油炸锅"],
    "电饭煲": ["电饭锅"],
    "电视": ["电视机"],
    "游戏机": ["游戏主机"],
    "switch": ["任天堂switch", "switch游戏机", "switch 主机"],
    "ps5": ["playstation5", "索尼ps5", "ps5 主机"],
    "单反相机": ["单反"],
    "微单": ["无反相机"],
    "相机": ["照相机"],
    "无人机": ["航拍器"],
    "婴儿奶粉": [_disambiguate("奶粉")],
    "运动鞋": ["球鞋"],
    "跑步鞋": [_disambiguate("跑鞋"), "运动鞋"],
    "品牌包": ["奢侈品包", "名牌包"],
    "品牌手表": ["名表"],
    "白酒": ["中国白酒"],
}


# ---------------------------------------------------------------------------
# 类别 → 热门具体商品型号联想
# 当用户只说大类时，联想出市面上主流的、有明确型号的商品，
# 让底层 best_price_mcp 能精准匹配到。
# ---------------------------------------------------------------------------
CATEGORY_TO_PRODUCTS: Dict[str, List[str]] = {
    "笔记本电脑": [
        "联想小新Pro14", "联想小新Pro16",
        "ThinkPad X1", "ThinkPad E14",
        "联想拯救者Y9000P", "联想拯救者R9000P",
        "华为MateBook 14", "华为MateBook 15", "华为MateBook X Pro",
        "华为擎云G540",
        "戴尔XPS 13", "戴尔XPS 15",
        "戴尔灵越14", "戴尔游匣G15",
        "MacBook Air 13", "MacBook Pro 14", "MacBook Pro 16",
        "惠普暗影精灵10", "惠普战66", "惠普星14",
        "华硕ROG枪神7", "华硕ROG魔霸7",
        "华硕无畏Pro14", "华硕天选5",
        "RedmiBook Pro15", "RedmiBook 15",
        "小米笔记本Pro15",
        "宏碁掠夺者擎Neo",
    ],
    "笔记本": [
        "联想小新Pro14", "联想小新Pro16",
        "ThinkPad X1", "ThinkPad E14",
        "联想拯救者Y9000P",
        "华为MateBook 14", "华为MateBook X Pro",
        "戴尔XPS 15",
        "MacBook Air 13", "MacBook Pro 14",
        "惠普暗影精灵10",
        "华硕ROG枪神7",
        "RedmiBook Pro15",
    ],
    "手机": [
        "iPhone 16", "iPhone 16 Pro", "iPhone 15", "iPhone 15 Pro",
        "华为Mate70", "华为Mate70 Pro", "华为Pura70 Pro", "华为Nova13",
        "小米15 Pro", "小米14", "Redmi K80 Pro", "Redmi K70",
        "三星S25 Ultra", "三星S24 Ultra",
        "vivo X200 Pro", "OPPO Find X8 Pro",
        "荣耀Magic7", "荣耀300 Pro",
        "一加13",
    ],
    "平板电脑": [
        "iPad Pro 12.9", "iPad Air 13", "iPad 10", "iPad mini 7",
        "华为MatePad Pro 13", "华为MatePad 11.5",
        "小米平板6 Pro", "Redmi Pad Pro",
        "三星Galaxy Tab S10",
        "荣耀平板V9",
    ],
    "平板": [
        "iPad Pro 12.9", "iPad Air 13",
        "华为MatePad Pro 13",
        "小米平板6 Pro",
    ],
    "显示器": [
        "戴尔U2723QE", "戴尔S2723HC",
        "三星Odyssey G5", "三星ViewFinity 27",
        "LG 27UK850", "LG UltraFine 27",
        "AOC 27G2", "飞利浦27E1N5500E",
        "华硕ROG PG27AQDM",
        "小米显示器27",
    ],
    "显卡": [
        "RTX 4090", "RTX 4080 Super", "RTX 4070 Ti Super", "RTX 4060",
        "RTX 5090", "RTX 5080", "RTX 5070 Ti",
        "RX 7900 XTX", "RX 7800 XT", "RX 9070 XT",
    ],
    "耳机": [
        "AirPods Pro 2", "AirPods 4", "AirPods Max",
        "索尼WH-1000XM5", "索尼WF-1000XM5",
        "BOSE QC Ultra", "BOSE QC 45",
        "华为FreeBuds Pro 4",
        "小米Redmi Buds 5",
        "漫步者NeoBuds Pro",
    ],
    "无线耳机": [
        "AirPods Pro 2", "索尼WF-1000XM5", "BOSE QC Ultra",
        "华为FreeBuds Pro 4", "小米Redmi Buds 5",
    ],
    "路由器": [
        "小米路由器BE6500", "Redmi路由器AX6000",
        "TP-LINK AX5400",
        "华硕RT-AX86U", "华硕ROG Rapture GT",
        "华为路由BE3 Pro",
    ],
    "键盘": [
        "罗技MX Keys S", "雷蛇黑寡妇蜘蛛V3",
        "Keychron K8 Pro", "Keychron Q1 Pro",
        "小米机械键盘",
    ],
    "鼠标": [
        "罗技MX Master 3S", "雷蛇蝰蛇V3",
        "微软Arc Mouse",
        "小米无线鼠标",
    ],
    "打印机": [
        "惠普LaserJet Pro", "佳能TS8380",
        "爱普生L3251", "爱普生L3253",
        "兄弟HL-L2350DW",
    ],
    "投影仪": [
        "极米H6", "极米Z7X",
        "当贝X5 Pro", "当贝D5X Pro",
        "坚果O1 Pro", "坚果J10",
        "爱普生CH-TW5800",
    ],
    "智能手表": [
        "Apple Watch Ultra 2", "Apple Watch Series 10",
        "华为Watch GT5 Pro", "华为Watch 4 Pro",
        "小米手表S4", "Redmi Watch 4",
        "三星Galaxy Watch 7",
    ],
    "手表": [
        "Apple Watch Series 10", "华为Watch GT5",
        "小米手表S4", "卡西欧G-SHOCK 5600", "天梭机械表",
    ],
    "游戏机": [
        "Switch OLED", "Switch Lite", "Switch 2",
        "PS5 Slim", "PS5 Pro",
        "Xbox Series X", "Xbox Series S",
        "Steam Deck OLED",
    ],
    "switch": ["Switch OLED", "Switch Lite", "Switch 2"],
    "ps5": ["PS5 Slim", "PS5 Pro"],
    "无人机": [
        "大疆Mavic 3 Pro", "大疆Air 3", "大疆Mini 4 Pro",
    ],
    "扫地机器人": [
        "石头G20 Pro", "石头S7 MaxV",
        "科沃斯X5 Pro", "科沃斯T30 Pro",
        "小米扫地机器人C101", "追觅X40 Pro",
    ],
    "空气净化器": [
        "小米空气净化器4 Pro",
        "美的空气净化器KJ500G",
        "飞利浦AC4076",
        "布鲁雅尔280i",
    ],
    "空调": [
        "格力云锦2代", "美的酷省电3代", "海尔劲享",
        "小米空调巨省电",
    ],
    "冰箱": [
        "海尔BCD-510", "美的BCD-508",
        "容声BCD-520", "西门子KA92",
    ],
    "洗衣机": [
        "海尔EG100", "小天鹅V87", "美的MD100",
        "西门子WG54",
    ],
    "电视": [
        "小米S Pro Mini LED", "小米ES Pro",
        "TCL Q9K", "海信E5K",
        "三星QN90D", "索尼A80K",
    ],
    "净水器": [
        "小米净水器1200G", "美的净水器白泽1200",
        "沁园净水器小白鲸",
    ],
    "空气炸锅": [
        "美的空气炸锅MF-KZ", "九阳空气炸锅KL40",
        "飞利浦HD9252",
    ],
    "电饭煲": [
        "美的电饭煲MB-FB50S701", "九阳电饭煲40N1",
        "苏泊尔电饭煲CFXB", "松下电饭煲SR-L10H8",
    ],
    "吹风机": [
        "戴森吹风机HD15", "戴森吹风机Supersonic",
        "徕芬吹风机SE 2.0", "飞科吹风机FH6290",
    ],
    "剃须刀": [
        "飞利浦剃须刀S9000", "飞利浦剃须刀S5000",
        "飞科剃须刀FS926", "博朗剃须刀9系",
    ],
    "电动牙刷": [
        "飞利浦声波电动牙刷HX9393", "欧乐B P2000",
        "小米电动牙刷T500", "usmile电动牙刷P10",
    ],
    "婴儿奶粉": [
        "飞鹤星飞帆", "惠氏启赋蓝钻", "爱他美卓萃",
        "美赞臣蓝臻", "雅培菁挚",
    ],
    "尿布": [
        "帮宝适纸尿裤", "花王妙而舒", "好奇铂金装",
        "尤妮佳纸尿裤",
    ],
    "运动鞋": [
        "Nike Pegasus 41", "Nike Air Max 270",
        "Adidas Ultraboost 22",
        "安踏氮科技", "李宁飞电",
    ],
    "跑步鞋": [
        "Nike Pegasus 41", "Adidas Ultraboost 22",
        "安踏氮科技", "李宁飞电",
    ],
    "品牌包": [
        "LV Neverfull", "Gucci GG Marmont", "Prada Saffiano",
        "Coach Tabby",
    ],
    "品牌手表": [
        "劳力士Submariner", "欧米茄海马", "卡地亚Tank",
        "天梭力洛克", "浪琴名匠",
    ],
    "香水": [
        "Dior Sauvage", "Dior 真我",
        "Chanel No.5", "Chanel Coco",
        "YSL Libre",
    ],
    "白酒": [
        "茅台飞天53度", "五粮液普五第八代",
        "泸州老窖国窖1573",
        "洋河海之蓝",
    ],
}


# ---------------------------------------------------------------------------
# 用途/场景 → 商品类别映射
# 用户输入的不是商品名而是用途（"打游戏"、"办公"、"追剧"），
# 先映射到商品类别，再走 CATEGORY_TO_PRODUCTS 联想链路。
# ---------------------------------------------------------------------------
USECASE_TO_CATEGORIES: Dict[str, List[str]] = {
    # 游戏相关
    "打游戏": ["游戏本", "游戏机", "游戏耳机", "游戏鼠标", "游戏键盘", "游戏手柄", "显卡", "显示器"],
    "游戏": ["游戏本", "游戏机", "游戏耳机", "显卡"],
    "玩游戏": ["游戏本", "游戏机", "显卡"],
    "电竞": ["游戏本", "显示器", "显卡", "游戏鼠标", "游戏键盘", "游戏耳机"],
    "fps": ["显示器", "游戏鼠标", "游戏耳机"],
    "主机游戏": ["Switch", "PS5", "Xbox", "显示器"],
    "原神": ["手机", "游戏本", "平板"],
    # 办公相关
    "办公": ["笔记本电脑", "显示器", "键盘鼠标", "打印机"],
    "商务": ["ThinkPad", "MateBook", "笔记本电脑"],
    "出差": ["轻薄本", "笔记本电脑"],
    "程序员": ["笔记本电脑", "显示器", "机械键盘"],
    "编程": ["笔记本电脑", "显示器"],
    # 学习相关
    "学习": ["平板", "笔记本电脑", "耳机"],
    "上网课": ["平板", "笔记本电脑", "耳机"],
    "考研": ["平板", "笔记本电脑"],
    "学生": ["平板", "笔记本电脑", "耳机"],
    # 影音娱乐
    "追剧": ["平板", "电视", "耳机", "投影仪"],
    "看电影": ["投影仪", "电视", "耳机"],
    "听音乐": ["耳机", "蓝牙音箱", "无线耳机"],
    "音乐": ["耳机", "无线耳机"],
    "听歌": ["耳机", "无线耳机"],
    # 摄影
    "拍照": ["相机", "无人机", "手机"],
    "摄影": ["相机", "无人机"],
    "vlog": ["相机", "无人机", "运动相机"],
    # 运动健康
    "运动": ["智能手表", "手环", "运动鞋"],
    "跑步": ["智能手表", "跑步鞋", "耳机"],
    "健身": ["智能手表", "手环"],
    "减脂": ["智能手表", "体脂秤"],
    # 家居生活
    "清洁": ["扫地机器人", "吸尘器", "空气净化器"],
    "打扫": ["扫地机器人", "吸尘器"],
    "做饭": ["空气炸锅", "电饭煲", "搅拌机"],
    "喝水": ["净水器"],
    "降温": ["空调"],
    "保暖": ["电暖器", "暖风机"],
    # 其他
    "送礼": ["智能手表", "耳机", "平板电脑", "品牌包", "品牌手表"],
    "结婚": ["白酒", "品牌包"],
    "出差用": ["行李箱", "笔记本电脑"],
    "开车": ["行车记录仪", "车载充电器", "车载支架"],
}


# ---------------------------------------------------------------------------
# 用途关键词到具体商品型号的直接映射（无需经过类别）
# ---------------------------------------------------------------------------
USECASE_TO_DIRECT_PRODUCTS: Dict[str, List[str]] = {
    "办公笔记本": [
        "ThinkPad X1", "ThinkPad E14",
        "联想小新Pro14",
        "华为MateBook 14", "华为MateBook X Pro",
        "戴尔灵越14",
        "惠普战66", "华硕无畏Pro14",
    ],
    "游戏本": [
        "联想拯救者Y9000P", "联想拯救者R9000P",
        "华硕ROG枪神7", "华硕ROG魔霸7",
        "华硕天选5",
        "戴尔游匣G15",
        "惠普暗影精灵10",
        "宏碁掠夺者擎Neo",
    ],
    "轻薄本": [
        "联想小新Pro14",
        "华为MateBook X Pro", "MacBook Air 13",
        "戴尔XPS 13", "惠普星14", "华硕无畏Pro14",
    ],
    "设计用": [
        "MacBook Pro 16", "戴尔XPS 15", "惠普Z系列G11",
        "ThinkPad P16", "华硕ProArt P16",
    ],
    "开发用": [
        "MacBook Pro 14", "ThinkPad X1", "戴尔XPS 15",
    ],
}


BRAND_TO_PRODUCTS: Dict[str, List[str]] = {
    "苹果": ["iPhone 16 Pro", "iPhone 15 Pro",
             "MacBook Air 13", "MacBook Pro 14", "MacBook Pro 16",
             "iPad Pro 12.9", "iPad Air 13",
             "AirPods Pro 2", "Apple Watch Series 10"],
    "apple": ["iPhone 16 Pro", "MacBook Air 13", "iPad Pro 12.9", "AirPods Pro 2"],
    "华为": ["华为Mate70 Pro", "华为Pura70 Pro", "华为Nova13",
             "华为MateBook 14", "华为MateBook X Pro",
             "华为FreeBuds Pro 4", "华为Watch GT5 Pro",
             "华为路由BE3 Pro"],
    "小米": ["小米15 Pro", "小米14", "Redmi K80 Pro",
             "小米平板6 Pro",
             "小米路由器BE6500",
             "小米空气净化器4 Pro",
             "小米S Pro Mini LED",
             "Redmi Buds 5"],
    "戴尔": ["戴尔XPS 15", "戴尔XPS 13",
             "戴尔灵越14", "戴尔游匣G15",
             "戴尔U2723QE"],
    "联想": ["联想小新Pro14", "联想小新Pro16",
             "ThinkPad X1", "ThinkPad E14",
             "联想拯救者Y9000P",
             "联想ThinkBook 14"],
    "惠普": ["惠普暗影精灵10", "惠普战66", "惠普星14"],
    "华硕": ["华硕ROG枪神7", "华硕ROG魔霸7",
             "华硕天选5", "华硕无畏Pro14",
             "华硕ROG PG27AQDM"],
    "三星": ["三星S25 Ultra", "三星S24 Ultra",
             "三星Galaxy Tab S10",
             "三星QN90D", "三星Odyssey G5"],
    "索尼": ["索尼WH-1000XM5", "索尼WF-1000XM5",
             "索尼A80K", "索尼A7C II"],
    "oppo": ["OPPO Find X8 Pro", "OPPO Reno 13"],
    "vivo": ["vivo X200 Pro", "vivo S19"],
    "荣耀": ["荣耀Magic7", "荣耀300 Pro", "荣耀平板V9"],
    "airpods": ["AirPods Pro 2", "AirPods Max", "AirPods 4"],
}


# ---------------------------------------------------------------------------
# 判断函数
# ---------------------------------------------------------------------------

# 宽泛关键词集合：用户只说了"笔记本电脑"、"手机"这种类别，
# 而没说具体型号/品牌/系列，就视为宽泛查询，需要走扩展逻辑。
# 这里我们通过规则判断：
#   - 纯类别词（命中 CATEGORY_TO_PRODUCTS 的 key）
#   - 含"用"、"打"、"看"、"听"、"办公"、"学习" 等用途动词
#   - 长度 ≤ 4 且不含数字（型号通常带数字，如 iPhone 15、MateBook X Pro）


def _looks_like_generic_category(query: str) -> bool:
    """判断 query 是否只是一个宽泛的商品类别词"""
    if not query or len(query.strip()) == 0:
        return False
    q = query.strip().lower()
    # 命中类别库
    if q in CATEGORY_TO_PRODUCTS or query.strip() in CATEGORY_TO_PRODUCTS:
        return True
    # 命中用途库
    for key in USECASE_TO_CATEGORIES:
        if key in query:
            return True
    for key in USECASE_TO_DIRECT_PRODUCTS:
        if key in query:
            return True
    # 包含典型用途动词
    use_case_verbs = ["用来", "用于", "打", "玩", "看", "听", "拍", "送",
                      "办公", "学习", "追剧", "听音乐", "唱歌", "运动",
                      "跑步", "健身", "清洁", "打扫", "做饭", "洗澡"]
    for v in use_case_verbs:
        if v in query:
            return True
    # 过短且不含数字/品牌（大概率是类别词）
    if len(query.strip()) <= 4:
        has_number = bool(re.search(r'\d', query))
        has_brand = any(b in query.lower() for b in BRAND_TO_PRODUCTS)
        if not has_number and not has_brand:
            return True
    return False


# ---------------------------------------------------------------------------
# 扩展主逻辑
# ---------------------------------------------------------------------------

class QueryExpander:
    """查询理解与扩展器"""

    def is_generic_query(self, query: str) -> bool:
        """对外暴露的宽泛查询判断"""
        return _looks_like_generic_category(query)

    def expand(self, query: str) -> List[str]:
        """
        将用户的宽泛查询扩展成若干具体的、可被底层 MCP 识别的搜索词。

        扩展策略（按优先级从高到低，排在前面的更先搜索）：
        1. 原始 query 本身（兜底，用户万一输入的其实已经能匹配）
        2. 用途 → 直接商品型号 + 品牌 → 热门产品 + 类别 → 热门型号
           （这三类都是**具体型号**，零歧义，优先搜。"联想拯救者"绝对不会
            搜出鼠标垫，"MacBook Pro" 绝对不会搜出电笔）
        3. 同义词扩展（经过 _disambiguate 清洗后已无高风险歧义）

        Args:
            query: 用户原始输入

        Returns:
            候选搜索词列表（去重，按推荐度排序）。
            如果 query 本身就足够具体，只返回 [query]。
        """
        query = query.strip()
        if not query:
            return []

        if not self.is_generic_query(query):
            return [query]

        candidates: List[str] = [query]
        seen = {query.lower()}

        def _add(kw: str):
            key = kw.lower()
            if key not in seen:
                seen.add(key)
                candidates.append(kw)

        q_lower = query.lower()

        # ---------------- 阶段 1：零歧义的具体型号（优先搜索） ----------------

        # 1a. 用途 → 直接商品型号（"办公笔记本" → ThinkPad、联想小新...）
        for use_key, products in USECASE_TO_DIRECT_PRODUCTS.items():
            if use_key in query:
                for p in products:
                    _add(p)

        # 1b. 用途 → 类别 → 商品型号（"打游戏" → 游戏本 → 联想拯救者...）
        for use_key, categories in USECASE_TO_CATEGORIES.items():
            if use_key in query:
                for cat in categories:
                    if cat in CATEGORY_TO_PRODUCTS:
                        for p in CATEGORY_TO_PRODUCTS[cat]:
                            _add(p)
                    elif cat in USECASE_TO_DIRECT_PRODUCTS:
                        for p in USECASE_TO_DIRECT_PRODUCTS[cat]:
                            _add(p)

        # 1c. 品牌匹配（"苹果" → iPhone 16、MacBook Air...）
        for brand_key, products in BRAND_TO_PRODUCTS.items():
            if brand_key in q_lower or brand_key in query:
                for p in products:
                    _add(p)

        # 1d. 直接类别命中 → 热门型号（"笔记本电脑" → 联想小新、华为MateBook...）
        if query in CATEGORY_TO_PRODUCTS:
            for p in CATEGORY_TO_PRODUCTS[query]:
                _add(p)
        if q_lower in CATEGORY_TO_PRODUCTS:
            for p in CATEGORY_TO_PRODUCTS[q_lower]:
                _add(p)

        # ---------------- 阶段 2：同义词扩展（已清洗歧义） ----------------

        if q_lower in SYNONYM_MAP:
            for syn in SYNONYM_MAP[q_lower]:
                _add(syn)
        if query in SYNONYM_MAP:
            for syn in SYNONYM_MAP[query]:
                _add(syn)

        return candidates

    def extract_core_terms(self, query: str) -> List[str]:
        """
        从用户查询中提取核心品类词，供**结果过滤器**使用。

        这些核心品类词会被用来验证每个返回商品的标题是否沾边——
        如果商品标题里一个核心词都没有（比如用户搜"笔记本电脑"，
        结果商品标题里既没有"笔记本"/"电脑"/"laptop"也没有任何具体型号），
        那这个商品就是脏数据，应该丢掉。

        提取策略：
        - 原始 query 本身（总是核心）
        - 同义词里的大类词（不是具体型号的那些）
        - 类别映射库中的原始 key（用户可能简写，但品类还是那个品类）
        - 用途映射库关联到的类别词

        Returns:
            核心词列表（去重、lowercase）
        """
        query = query.strip().lower()
        if not query:
            return []

        core: List[str] = [query]
        seen = {query}

        def _add(term: str):
            t = term.lower().strip()
            if t and t not in seen:
                seen.add(t)
                core.append(t)

        # 同义词
        if query in SYNONYM_MAP:
            for syn in SYNONYM_MAP[query]:
                _add(syn)
        # 反过来查：如果 query 是某个 key 的同义词，也把 key 加进来
        for key, syns in SYNONYM_MAP.items():
            if query in [s.lower() for s in syns]:
                _add(key)

        # 类别 key 本身
        for cat in CATEGORY_TO_PRODUCTS:
            if cat in query or query in cat:
                _add(cat)
            if cat.lower() in query:
                _add(cat)

        # 用途 → 关联类别
        for use_key, categories in USECASE_TO_CATEGORIES.items():
            if use_key in query:
                for cat in categories:
                    _add(cat)

        return core

    def extract_generic_hint(self, query: str) -> Optional[str]:
        """
        给用户一个友好的提示，说明我们把他的宽泛搜索理解成了什么。

        例如：
            "笔记本电脑" → "检测到您在搜索笔记本电脑，已为您扩展联想小新、华为MateBook 等热门型号"
            "打游戏的笔记本" → "检测到您想用来打游戏，已为您推荐游戏本（联想拯救者、华硕ROG 等）"

        Returns:
            提示文本；如果 query 本身已经很具体则返回 None
        """
        if not self.is_generic_query(query):
            return None

        hint_parts = []

        # 用途识别
        for use_key, products in USECASE_TO_DIRECT_PRODUCTS.items():
            if use_key in query:
                top = products[:3]
                hint_parts.append(f"您想找「{use_key}」，已为您联想：{'、'.join(top)} 等")

        for use_key, categories in USECASE_TO_CATEGORIES.items():
            if use_key in query:
                top_cats = categories[:2]
                hint_parts.append(f"检测到您的用途：「{use_key}」，已关联 {top_cats}")

        # 类别识别
        matched_category = None
        if query in CATEGORY_TO_PRODUCTS:
            matched_category = query
        elif query.lower() in CATEGORY_TO_PRODUCTS:
            matched_category = query.lower()
        if matched_category:
            top_models = CATEGORY_TO_PRODUCTS[matched_category][:4]
            hint_parts.append(f"「{matched_category}」大类已联想热门型号：{'、'.join(top_models)} 等")

        if not hint_parts:
            return None
        return "；".join(hint_parts)


# 全局单例
query_expander = QueryExpander()