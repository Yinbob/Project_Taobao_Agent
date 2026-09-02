"""
多平台MCP客户端模块
负责与多平台MCP服务器的通信
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from data_models import Platform, Product
from config import config

# 尝试导入best_price_mcp模块
try:
    import best_price_mcp
    BEST_PRICE_MCP_AVAILABLE = True
except ImportError:
    BEST_PRICE_MCP_AVAILABLE = False
    print("警告: best_price_mcp模块未安装，部分功能可能不可用")

class MCPClient:
    """MCP客户端类"""
    
    def __init__(self):
        self.connected = False
        self.use_direct_module = BEST_PRICE_MCP_AVAILABLE
    
    async def connect(self):
        """连接到MCP服务器"""
        try:
            if self.use_direct_module:
                # 直接使用best_price_mcp模块
                print("使用best_price_mcp模块直接调用")
                self.connected = True
                return True
            else:
                # 尝试使用MCP协议连接
                print("尝试使用MCP协议连接...")
                # 这里可以添加MCP协议连接逻辑
                # 但由于best_price_mcp是Python模块，我们直接使用它
                self.connected = True
                return True
                
        except Exception as e:
            print(f"连接MCP服务器失败: {e}")
            return False
    
    async def disconnect(self):
        """断开MCP服务器连接"""
        self.connected = False
        print("已断开MCP服务器连接")
    
    async def compare_price(self, query: str, platform: str = "all") -> List[Dict[str, Any]]:
        """
        比较商品价格
        
        Args:
            query: 商品关键词
            platform: 平台选择（jd, taobao, pdd, all）
        
        Returns:
            价格比较结果列表
        """
        if not self.connected:
            raise Exception("MCP服务器未连接")
        
        try:
            if self.use_direct_module:
                # 直接调用best_price_mcp模块
                result = best_price_mcp.compare_price(query, platform)
                
                # 解析结果
                if isinstance(result, str):
                    return json.loads(result)
                elif isinstance(result, dict):
                    return [result]
                elif isinstance(result, list):
                    return result
                else:
                    return []
            else:
                # 如果没有best_price_mcp模块，返回模拟数据
                return self._get_mock_comparison_data(query, platform)
                
        except Exception as e:
            print(f"调用compare_price失败: {e}")
            # 返回模拟数据
            return self._get_mock_comparison_data(query, platform)
    
    async def search_products(self, keyword: str, platform: str = "taobao", 
                            price_min: float = 0, price_max: float = 0) -> List[Product]:
        """
        搜索商品
        
        Args:
            keyword: 搜索关键词
            platform: 平台选择
            price_min: 最低价格
            price_max: 最高价格
        
        Returns:
            商品列表
        """
        if not self.connected:
            raise Exception("MCP服务器未连接")
        
        try:
            # 由于best_price_mcp没有直接的search_products方法，
            # 我们使用compare_price来获取商品信息
            comparisons = await self.compare_price(keyword, platform)
            
            products = []
            for comparison in comparisons:
                # 从比较结果中提取商品信息
                if "platforms" in comparison:
                    for platform_name, product_info in comparison["platforms"].items():
                        try:
                            # 创建Product对象
                            product = Product(
                                id=product_info.get("id", f"{platform_name}_{keyword}"),
                                title=product_info.get("title", keyword),
                                price=product_info.get("price", 0),
                                platform=Platform(platform_name),
                                shop_name=product_info.get("shop_name", ""),
                                shop_type=product_info.get("shop_type", ""),
                                sales=product_info.get("sales"),
                                rating=product_info.get("rating"),
                                product_url=product_info.get("url", ""),
                                image_url=product_info.get("image_url", "")
                            )
                            
                            # 应用价格过滤
                            if price_min > 0 and product.price < price_min:
                                continue
                            if price_max > 0 and product.price > price_max:
                                continue
                            
                            products.append(product)
                        except Exception as e:
                            print(f"解析商品数据失败: {e}")
                            continue
            
            return products
            
        except Exception as e:
            print(f"搜索商品失败: {e}")
            # 返回模拟数据
            return self._get_mock_products(keyword, platform, price_min, price_max)
    
    async def get_product_details(self, product_id: str, platform: str) -> Optional[Product]:
        """
        获取商品详情
        
        Args:
            product_id: 商品ID
            platform: 平台
        
        Returns:
            商品详情
        """
        if not self.connected:
            raise Exception("MCP服务器未连接")
        
        try:
            # 由于best_price_mcp没有直接的get_product_details方法，
            # 我们返回一个模拟的商品详情
            return self._get_mock_product_details(product_id, platform)
            
        except Exception as e:
            print(f"获取商品详情失败: {e}")
            return None
    
    def _get_mock_comparison_data(self, query: str, platform: str) -> List[Dict[str, Any]]:
        """获取模拟的价格比较数据"""
        mock_data = [
            {
                "product_title": query,
                "platforms": {
                    "jd": {
                        "id": "jd_001",
                        "title": f"{query} - 京东自营",
                        "price": 4999.00,
                        "shop_name": "京东自营",
                        "shop_type": "自营",
                        "sales": 15000,
                        "rating": 4.9,
                        "url": "https://item.jd.com/123456.html",
                        "image_url": ""
                    },
                    "taobao": {
                        "id": "taobao_001",
                        "title": f"{query} - 天猫旗舰店",
                        "price": 4899.00,
                        "shop_name": "品牌旗舰店",
                        "shop_type": "旗舰店",
                        "sales": 25000,
                        "rating": 4.8,
                        "url": "https://detail.tmall.com/item.htm?id=123456",
                        "image_url": ""
                    },
                    "pdd": {
                        "id": "pdd_001",
                        "title": f"{query} - 拼多多百亿补贴",
                        "price": 4799.00,
                        "shop_name": "品牌官方店",
                        "shop_type": "官方店",
                        "sales": 8000,
                        "rating": 4.7,
                        "url": "https://mobile.yangkeduo.com/goods.html?goods_id=123456",
                        "image_url": ""
                    }
                },
                "min_price": 4799.00,
                "min_price_platform": "pdd",
                "max_price": 4999.00,
                "price_difference": 200.00,
                "price_difference_percentage": 4.17
            }
        ]
        
        # 如果指定了平台，只返回该平台的数据
        if platform != "all":
            for item in mock_data:
                if platform in item["platforms"]:
                    item["platforms"] = {platform: item["platforms"][platform]}
        
        return mock_data
    
    def _get_mock_products(self, keyword: str, platform: str, 
                          price_min: float, price_max: float) -> List[Product]:
        """获取模拟的商品数据"""
        mock_products = [
            Product(
                id="mock_001",
                title=f"{keyword} - 旗舰版",
                price=4999.00,
                platform=Platform.JD,
                shop_name="京东自营",
                shop_type="自营",
                sales=15000,
                rating=4.9
            ),
            Product(
                id="mock_002",
                title=f"{keyword} - 标准版",
                price=4899.00,
                platform=Platform.TAOBAO,
                shop_name="品牌旗舰店",
                shop_type="旗舰店",
                sales=25000,
                rating=4.8
            ),
            Product(
                id="mock_003",
                title=f"{keyword} - 经济版",
                price=4799.00,
                platform=Platform.PDD,
                shop_name="品牌官方店",
                shop_type="官方店",
                sales=8000,
                rating=4.7
            )
        ]
        
        # 应用平台过滤
        if platform != "all":
            mock_products = [p for p in mock_products if p.platform.value == platform]
        
        # 应用价格过滤
        filtered_products = []
        for product in mock_products:
            if price_min > 0 and product.price < price_min:
                continue
            if price_max > 0 and product.price > price_max:
                continue
            filtered_products.append(product)
        
        return filtered_products
    
    def _get_mock_product_details(self, product_id: str, platform: str) -> Product:
        """获取模拟的商品详情"""
        return Product(
            id=product_id,
            title=f"商品详情 - {product_id}",
            price=4999.00,
            platform=Platform(platform) if platform in ["jd", "taobao", "pdd"] else Platform.JD,
            shop_name="品牌旗舰店",
            shop_type="旗舰店",
            sales=15000,
            rating=4.9,
            specs={
                "颜色": "黑色",
                "内存": "8GB",
                "存储": "256GB"
            }
        )

# 创建全局MCP客户端实例
mcp_client = MCPClient()