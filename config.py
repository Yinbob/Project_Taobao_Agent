"""
多平台商品推荐Agent配置文件
"""

import os
from typing import Dict, Any

class Config:
    """配置类"""
    
    # 服务器配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # MCP服务器配置
    # best-price: 京东/淘宝(天猫)比价，通过腾讯云SCF代理实时搜索
    # pdd-selection: 拼多多搜索，需要多多进宝认证（PDD_PROXY_URL/PDD_PROXY_TOKEN）
    MCP_SERVERS: Dict[str, Dict[str, Any]] = {
        "best-price": {
            "command": "best-price-mcp",
            "args": [],
            "env": {}
        },
        "pdd-selection": {
            "command": "pdd-selection-mcp",
            "args": [],
            "env": {
                "PDD_PROXY_URL": os.getenv("PDD_PROXY_URL", ""),
                "PDD_PROXY_TOKEN": os.getenv("PDD_PROXY_TOKEN", "")
            }
        }
    }
    
    # MCP数据源配置
    MCP_ENABLED: bool = True  # 是否启用真实MCP数据源（为False时全部使用模拟数据）
    MCP_PDD_ENABLED: bool = os.getenv("MCP_PDD_ENABLED", "false").lower() == "true"  # 拼多多需要认证，默认关闭
    
    # 推荐算法权重配置
    RECOMMENDATION_WEIGHTS: Dict[str, float] = {
        "price": 0.4,
        "sales": 0.3,
        "shop_reputation": 0.2,
        "platform_reliability": 0.1
    }
    
    # 平台配置
    PLATFORMS: list = ["jd", "taobao", "pdd"]
    
    # 默认搜索结果数量
    DEFAULT_TOP_N: int = 10
    
    # 支持的商品类别
    SUPPORTED_CATEGORIES: list = [
        "手机", "智能手表", "平板电脑", "笔记本电脑", "显示器", "打印机",
        "存储设备", "显卡", "耳机", "相机", "投影仪", "游戏机", "路由器",
        "键盘鼠标", "扫地机器人", "电视", "冰箱", "洗衣机", "空调",
        "热水器", "吹风机", "剃须刀", "电动牙刷", "空气净化器",
        "净水器", "搅拌机", "空气炸锅", "电饭煲", "品牌运动鞋",
        "品牌包", "品牌手表", "香水", "白酒", "婴儿奶粉", "尿布",
        "书籍", "品牌粮油"
    ]
    
    # 平台可靠性评分
    PLATFORM_RELIABILITY: Dict[str, float] = {
        "jd": 0.95,      # 京东
        "taobao": 0.90,   # 淘宝/天猫
        "pdd": 0.85       # 拼多多
    }
    
    # 价格评分参数
    PRICE_SCORE_PARAMS: Dict[str, float] = {
        "optimal_ratio": 0.8,  # 最优价格占预算的比例
        "weight_factor": 2.0   # 价格权重因子
    }
    
    # 销量评分参数
    SALES_SCORE_PARAMS: Dict[str, float] = {
        "log_base": 10,        # 对数底数
        "max_sales_cap": 100000 # 最大销量上限
    }

# 创建全局配置实例
config = Config()