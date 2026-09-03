"""
多平台MCP客户端模块
负责与多平台MCP服务器的通信

数据源说明:
- 京东/淘宝(天猫): 通过 best-price-mcp 模块，基于腾讯云SCF代理实时搜索
- 拼多多: 可通过 pdd-selection-mcp 模块（需要多多进宝认证），认证失败时回退到模拟数据
"""

import hashlib
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

# 尝试导入pdd_selection_mcp模块
try:
    import pdd_selection_mcp
    PDD_MCP_AVAILABLE = True
except ImportError:
    PDD_MCP_AVAILABLE = False
    print("警告: pdd_selection_mcp模块未安装，拼多多搜索不可用")


def _parse_sales_tip(sales_tip: Any) -> Optional[int]:
    """解析销量文本如'1.5万+'为整数"""
    if sales_tip is None:
        return None
    if isinstance(sales_tip, (int, float)):
        return int(sales_tip)
    if not isinstance(sales_tip, str):
        return None
    s = sales_tip.strip().rstrip("+")
    try:
        if "万" in s:
            return int(float(s.replace("万", "")) * 10000)
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _safe_float_price(val: Any) -> float:
    """安全转float，失败返回0"""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


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
    
    async def compare_price(self, query: str, platform: str = "all", 
                            price_min: float = 0, price_max: float = 0) -> List[Dict[str, Any]]:
        """
        比较商品价格
        
        Args:
            query: 商品关键词
            platform: 平台选择（jd, taobao, pdd, all）
            price_min: 最低价格（用于降级模拟数据的生成）
            price_max: 最高价格（用于降级模拟数据的生成）
        
        Returns:
            价格比较结果列表
        """
        if not self.connected:
            raise Exception("MCP服务器未连接")
        
        try:
            if self.use_direct_module:
                # 调用best_price_mcp的内部比价函数，返回JSON格式数据
                result_str = best_price_mcp._compare_price(query, platform)
                
                # 解析JSON结果
                if isinstance(result_str, str):
                    try:
                        data = json.loads(result_str)
                    except json.JSONDecodeError:
                        print("解析best_price_mcp结果失败，返回原始文本")
                        return self._get_mock_comparison_data(query, platform, price_min, price_max)
                elif isinstance(result_str, dict):
                    data = result_str
                else:
                    return self._get_mock_comparison_data(query, platform, price_min, price_max)
                
                # 如果返回了hint提示（模糊输入/非标品/链接），降级使用模拟数据
                if isinstance(data, dict) and data.get("hint"):
                    print(f"best_price_mcp提示: {data.get('hint')}，降级使用模拟数据")
                    return self._get_mock_comparison_data(query, platform, price_min, price_max)
                
                # 将best_price_mcp的JSON数据转换为统一的比较格式
                converted = self._convert_comparison_data(query, data, platform)
                if not converted:
                    print("best_price_mcp未返回有效结果，降级使用模拟数据")
                    return self._get_mock_comparison_data(query, platform, price_min, price_max)
                return converted
            else:
                # 如果没有best_price_mcp模块，返回模拟数据
                return self._get_mock_comparison_data(query, platform, price_min, price_max)
                
        except Exception as e:
            print(f"调用compare_price失败: {e}")
            # 返回模拟数据
            return self._get_mock_comparison_data(query, platform, price_min, price_max)
    
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
            # 针对拼多多平台使用pdd_selection_mcp
            if platform == "pdd":
                # 拼多多需要多多进宝认证，默认关闭真实搜索
                if config.MCP_PDD_ENABLED and PDD_MCP_AVAILABLE:
                    products = await self._search_pdd_products(
                        keyword, price_min, price_max
                    )
                    if products:
                        return products
                # 拼多多不可用或未返回结果，回退到模拟数据
                print("拼多多搜索不可用，返回模拟数据")
                return self._get_mock_products(keyword, platform, price_min, price_max)
            
            # 京东/淘宝(天猫)使用best_price_mcp
            comparisons = await self.compare_price(keyword, platform, price_min, price_max)
            
            products = []
            for comparison in comparisons:
                # 从比较结果中提取商品信息
                if "platforms" in comparison:
                    for platform_name, product_info in comparison["platforms"].items():
                        try:
                            # 平台过滤
                            if platform != "all" and platform_name != platform:
                                continue
                            
                            # 创建Product对象
                            product = Product(
                                id=product_info.get("id", f"{platform_name}_{keyword}"),
                                title=product_info.get("title", keyword),
                                price=_safe_float_price(product_info.get("price")),
                                original_price=_safe_float_price(product_info.get("original_price")) if product_info.get("original_price") else None,
                                sales=product_info.get("sales"),
                                platform=Platform(platform_name),
                                shop_name=product_info.get("shop_name", ""),
                                shop_type=product_info.get("shop_type", ""),
                                product_url=product_info.get("url", ""),
                                image_url=product_info.get("image_url", ""),
                                rating=product_info.get("rating"),
                                specs=product_info.get("specs")
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
                
                # 兼容 best_price_mcp 返回的 "best"/"alternatives" 结构
                for key in ("best", "alternatives"):
                    item = comparison.get(key)
                    if not isinstance(item, dict):
                        continue
                    try:
                        product = self._convert_item_to_product(keyword, platform, item)
                        if product is None:
                            continue
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
    
    async def _search_pdd_products(self, keyword: str, price_min: float, 
                                   price_max: float) -> List[Product]:
        """使用pdd_selection_mcp搜索拼多多商品"""
        try:
            # 调用pdd_selection_mcp搜索商品
            result_str = pdd_selection_mcp.search_goods(
                keyword=keyword,
                page=1,
                page_size=20
            )
            
            # search_goods返回的是格式化文本，需要调用底层API获取结构化数据
            data = pdd_selection_mcp.call_proxy("search", {
                "keyword": keyword,
                "page": 1,
                "page_size": 20,
            })
            
            if not data.get("ok"):
                error = data.get("error", "未知错误")
                print(f"拼多多搜索失败: {error}")
                return []
            
            items = data.get("data", [])
            products = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    price = _safe_float_price(item.get("min_group_price")) / 100
                    final_price = _safe_float_price(item.get("final_price")) / 100
                    if final_price > 0:
                        price = final_price
                    
                    # 应用价格过滤
                    if price_min > 0 and price < price_min:
                        continue
                    if price_max > 0 and price > price_max:
                        continue
                    
                    product = Product(
                        id=f"pdd_{item.get('goods_id', '')}",
                        title=item.get("goods_name", keyword),
                        price=price,
                        original_price=_safe_float_price(item.get("min_group_price")) / 100 if item.get("min_group_price") else None,
                        sales=_parse_sales_tip(item.get("sales_tip")),
                        platform=Platform.PDD,
                        shop_name=item.get("mall_name", ""),
                        shop_type="拼多多",
                        product_url=item.get("goods_sign", ""),
                        image_url=item.get("goods_image_url", ""),
                        rating=None
                    )
                    products.append(product)
                except Exception as e:
                    print(f"解析拼多多商品数据失败: {e}")
                    continue
            
            return products
        except Exception as e:
            print(f"搜索拼多多商品失败: {e}")
            return []
    
    def _convert_comparison_data(self, query: str, data: Dict[str, Any], 
                                 platform: str) -> List[Dict[str, Any]]:
        """
        将best_price_mcp返回的JSON数据转换为统一的比较格式
        
        best_price_mcp._compare_price 返回格式:
        {
            "query": "iPhone 16",
            "cleaned_keyword": "iPhone 16",
            "results": {
                "jd": {"best": {...}, "alternatives": [...], "note": "..."},
                "taobao": {"best": {...}, "alternatives": [...], "note": "..."}
            },
            "hint": null
        }
        """
        results = data.get("results") if isinstance(data, dict) else None
        
        # 处理hint提示（非标品、模糊输入、链接等）
        if data.get("hint"):
            print(f"best_price_mcp提示: {data.get('hint')}")
        
        if not isinstance(results, dict):
            return []
        
        # 平台名称映射
        platform_names = {"jd": "jd", "taobao": "taobao"}
        if platform != "all":
            # 只保留指定的平台
            if platform in results:
                results = {platform: results[platform]}
            else:
                return []
        
        comparisons = []
        for pk, pd in results.items():
            if not isinstance(pd, dict):
                continue
            
            pn = platform_names.get(pk, pk)
            platforms = {}
            best = pd.get("best")
            alternatives = pd.get("alternatives", [])
            note = pd.get("note")
            
            # 合并最优商品和替代商品
            all_items = []
            if isinstance(best, dict):
                all_items.append(best)
            if isinstance(alternatives, list):
                all_items.extend([a for a in alternatives if isinstance(a, dict)])
            
            for item in all_items:
                product = self._convert_item_to_product(query, pn, item)
                if product is None:
                    continue
                platforms[product.platform] = product
            
            if not platforms:
                continue
            
            # 计算价格对比信息
            products_list = list(platforms.values())
            prices = [p.price for p in products_list]
            min_price = min(prices)
            max_price = max(prices)
            min_price_platform = min(products_list, key=lambda p: p.price).platform
            price_difference = max_price - min_price
            price_difference_percentage = (price_difference / min_price * 100) if min_price > 0 else 0
            
            comparisons.append({
                "product_title": query,
                "platforms": {
                    pk: {
                        "id": p.id,
                        "title": p.title,
                        "price": p.price,
                        "original_price": p.original_price,
                        "shop_name": p.shop_name,
                        "shop_type": p.shop_type,
                        "sales": p.sales,
                        "rating": p.rating,
                        "url": p.product_url,
                        "image_url": p.image_url,
                        "specs": p.specs
                    }
                    for pk, p in platforms.items()
                },
                "min_price": min_price,
                "min_price_platform": min_price_platform.value,
                "max_price": max_price,
                "price_difference": price_difference,
                "price_difference_percentage": round(price_difference_percentage, 2),
                "note": note
            })
        
        return comparisons
    
    def _convert_item_to_product(self, query: str, platform: str, 
                                 item: Dict[str, Any]) -> Optional[Product]:
        """
        将best_price_mcp的单个商品项转换为Product对象
        
        best_price_mcp 商品项格式:
        {
            "name": "Apple/苹果iPhoneAir手机",
            "brand": "Apple/苹果",
            "shop": "中国联通手机官方旗舰店",
            "shop_type": "天猫",
            "price": "7999",
            "final_price": 5749.0,
            "saved": 2250.0,
            "coupon": "省¥2250",
            "sales": "100",
            "rating": null,
            "image": "https://...",
            "buy_url": "https://..."
        }
        """
        try:
            name = item.get("name", "")
            if not name:
                return None
            
            price = _safe_float_price(item.get("final_price"))
            if price <= 0:
                price = _safe_float_price(item.get("price"))
            
            # 生成稳定的商品ID
            id_source = item.get("buy_url", "") or item.get("name", "")
            product_id = f"{platform}_{hashlib.md5(id_source.encode('utf-8')).hexdigest()[:10]}"
            
            # 销售数据
            sales = _parse_sales_tip(item.get("sales"))
            
            # 店铺评分：best_price_mcp的rating是好评率百分比(0-100)，转换为0-5分制
            rating = item.get("rating")
            if rating is not None:
                try:
                    rating_float = float(rating)
                    if rating_float > 20:  # 好评率百分比(0-100) → 0-5分制
                        rating = rating_float / 20.0
                    else:
                        rating = rating_float
                except (ValueError, TypeError):
                    rating = None
            
            platform_enum = Platform(platform) if platform in ["jd", "taobao", "pdd"] else None
            if platform_enum is None:
                return None
            
            return Product(
                id=product_id,
                title=name,
                price=price,
                original_price=_safe_float_price(item.get("price")) if item.get("price") else None,
                sales=sales,
                shop_name=item.get("shop", ""),
                shop_type=item.get("shop_type", ""),
                platform=platform_enum,
                product_url=item.get("buy_url", ""),
                image_url=item.get("image", ""),
                rating=rating
            )
        except Exception as e:
            print(f"转换商品数据失败: {e}")
            return None
    
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
    
    def _get_mock_comparison_data(self, query: str, platform: str, 
                                  price_min: float = 0, price_max: float = 0) -> List[Dict[str, Any]]:
        """获取模拟的价格比较数据
        
        当给定预算范围时，生成落在预算范围内的模拟价格。
        """
        # 根据预算范围生成合理的基础价格
        base_price = 4999.00
        if price_min > 0 and price_max > 0:
            # 在预算范围内取中位偏下作为基础价
            base_price = (price_min + price_max) / 2 * 0.9
        elif price_min > 0:
            base_price = max(price_min * 1.2, 499.00)
        elif price_max > 0:
            base_price = min(price_max * 0.85, 4999.00)
        
        # 生成三个平台的价格（略有差异，用于价格对比）
        prices = {
            "jd": round(base_price, 2),
            "taobao": round(base_price * 0.98, 2),
            "pdd": round(base_price * 0.96, 2)
        }
        
        mock_data = [
            {
                "product_title": query,
                "platforms": {
                    "jd": {
                        "id": "jd_001",
                        "title": f"{query} - 京东自营",
                        "price": prices["jd"],
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
                        "price": prices["taobao"],
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
                        "price": prices["pdd"],
                        "shop_name": "品牌官方店",
                        "shop_type": "官方店",
                        "sales": 8000,
                        "rating": 4.7,
                        "url": "https://mobile.yangkeduo.com/goods.html?goods_id=123456",
                        "image_url": ""
                    }
                },
                "min_price": prices["pdd"],
                "min_price_platform": "pdd",
                "max_price": prices["jd"],
                "price_difference": round(prices["jd"] - prices["pdd"], 2),
                "price_difference_percentage": round((prices["jd"] - prices["pdd"]) / prices["pdd"] * 100, 2)
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
        """获取模拟的商品数据
        
        当给定预算范围时，生成落在预算范围内的模拟价格。
        """
        # 根据预算范围生成合理的基础价格
        base_price = 4999.00
        if price_min > 0 and price_max > 0:
            # 在预算范围内取中位偏下作为基础价
            base_price = (price_min + price_max) / 2 * 0.9
        elif price_min > 0:
            base_price = max(price_min * 1.2, 499.00)
        elif price_max > 0:
            base_price = min(price_max * 0.85, 4999.00)
        
        # 各平台价格略有差异
        prices = {
            "jd": round(base_price, 2),
            "taobao": round(base_price * 0.98, 2),
            "pdd": round(base_price * 0.96, 2)
        }
        
        mock_products = [
            Product(
                id="mock_001",
                title=f"{keyword} - 旗舰版",
                price=prices["jd"],
                platform=Platform.JD,
                shop_name="京东自营",
                shop_type="自营",
                sales=15000,
                rating=4.9
            ),
            Product(
                id="mock_002",
                title=f"{keyword} - 标准版",
                price=prices["taobao"],
                platform=Platform.TAOBAO,
                shop_name="品牌旗舰店",
                shop_type="旗舰店",
                sales=25000,
                rating=4.8
            ),
            Product(
                id="mock_003",
                title=f"{keyword} - 经济版",
                price=prices["pdd"],
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