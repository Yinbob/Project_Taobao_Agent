"""
多平台商品推荐Agent核心模块
负责接收用户输入、协调各模块工作、管理Agent状态和会话
"""

import asyncio
import time
from typing import List, Optional, Dict, Any
from data_models import (
    Platform, Product, SearchRequest, SearchResponse, 
    RecommendationResult, PriceComparison, RecommendationScore
)
from mcp_client import mcp_client
from recommendation_engine import recommendation_engine
from query_expander import query_expander
from config import config

class TaobaoAgent:
    """淘宝商品推荐Agent类"""
    
    def __init__(self):
        self.initialized = False
        self.search_history: List[Dict[str, Any]] = []
    
    async def initialize(self) -> bool:
        """
        初始化Agent
        
        Returns:
            是否初始化成功
        """
        try:
            # 连接MCP服务器
            success = await mcp_client.connect()
            if success:
                self.initialized = True
                print("Agent初始化成功")
                return True
            else:
                print("Agent初始化失败：无法连接MCP服务器")
                return False
        except Exception as e:
            print(f"Agent初始化失败: {e}")
            return False
    
    async def shutdown(self):
        """关闭Agent"""
        try:
            await mcp_client.disconnect()
            self.initialized = False
            print("Agent已关闭")
        except Exception as e:
            print(f"关闭Agent时出错: {e}")
    
    async def _search_single_keyword(self, keyword: str, 
                                      platforms: List[Platform],
                                      budget_min: float, 
                                      budget_max: float) -> List[Product]:
        """使用单个关键词在所有平台搜索，返回去重后的商品列表"""
        products_seen = set()
        results: List[Product] = []
        for platform in platforms:
            try:
                platform_products = await mcp_client.search_products(
                    keyword=keyword,
                    platform=platform.value,
                    price_min=budget_min,
                    price_max=budget_max
                )
                for p in platform_products:
                    if p.id not in products_seen:
                        products_seen.add(p.id)
                        results.append(p)
            except Exception as e:
                print(f"搜索{platform.value}平台商品失败(keyword={keyword}): {e}")
                continue
        return results

    async def search_and_recommend(self, request: SearchRequest) -> SearchResponse:
        """
        搜索并推荐商品

        当用户输入的是宽泛查询（如 "笔记本电脑"、"打游戏用的"）时，
        会自动扩展出多个具体关键词，逐个尝试搜索并合并结果。

        Args:
            request: 搜索请求

        Returns:
            搜索响应
        """
        if not self.initialized:
            return SearchResponse(
                success=False,
                message="Agent未初始化",
                error="请先初始化Agent"
            )

        start_time = time.time()

        try:
            # 记录搜索历史
            self.search_history.append({
                "query": request.query,
                "budget_min": request.budget_min,
                "budget_max": request.budget_max,
                "platforms": [p.value for p in request.platforms],
                "timestamp": time.time()
            })

            # 查询扩展：把宽泛词拆成多个具体关键词
            expanded_keywords = query_expander.expand(request.query)
            generic_hint = query_expander.extract_generic_hint(request.query)

            MAX_EXPANDED_ATTEMPTS = 10  # 硬性上限：最多尝试这么多个扩展关键词

            print(f"[QueryExpander] 原始查询: '{request.query}' → 扩展为 {len(expanded_keywords)} 个关键词: {expanded_keywords[:8]}{'...' if len(expanded_keywords) > 8 else ''}")

            # 逐个关键词搜索，收集所有商品
            # 已搜索过的关键词，避免底层 MCP 重复请求
            searched_keywords: set = set()
            all_products: List[Product] = []
            no_hit_streak = 0  # 连续无结果次数

            for idx, keyword in enumerate(expanded_keywords):
                if idx >= MAX_EXPANDED_ATTEMPTS:
                    print(f"[QueryExpander] 已达到最大尝试次数 {MAX_EXPANDED_ATTEMPTS}，停止扩展搜索")
                    break
                if keyword in searched_keywords:
                    continue
                searched_keywords.add(keyword)

                batch = await self._search_single_keyword(
                    keyword=keyword,
                    platforms=request.platforms,
                    budget_min=request.budget_min,
                    budget_max=request.budget_max
                )
                if batch:
                    print(f"[QueryExpander] 关键词 '{keyword}' 命中 {len(batch)} 件商品")
                    no_hit_streak = 0
                    all_products.extend(batch)
                else:
                    no_hit_streak += 1

                # 如果已经拿到了不错的结果，可以提前停止，避免过多的底层请求
                if len(all_products) >= request.top_n * 3:
                    print(f"[QueryExpander] 已收集到 {len(all_products)} 件商品，提前停止扩展搜索")
                    break

                # 如果连续多个关键词都没结果，也提前放弃（底层 MCP 可能对这类型号不认）
                if no_hit_streak >= 6 and len(all_products) < request.top_n:
                    print(f"[QueryExpander] 连续 {no_hit_streak} 个关键词无结果，当前仅 {len(all_products)} 件商品，停止扩展")
                    break

            # 全没搜到的话，返回友好提示（包含智能联想信息）
            if not all_products:
                error_msg = "未找到符合条件的商品"
                if generic_hint:
                    error_msg = f"未找到商品（已尝试智能联想，但当前平台无匹配结果）。{generic_hint}"
                return SearchResponse(
                    success=False,
                    message=error_msg,
                    error="请尝试调整搜索关键词或预算范围"
                )

            # 第二道防线：结果相关性过滤
            # 即便前面做了歧义清理，底层 MCP 仍可能因为某些原因返回鼠标垫、电笔
            # 这种完全不沾边的结果。这里用核心品类词做一次二次验证，零重合的直接丢。
            all_products = recommendation_engine.filter_by_relevance(
                all_products, request.query
            )

            # 过滤完如果空了，也需要告知用户
            if not all_products:
                error_msg = "未找到符合条件的商品"
                if generic_hint:
                    error_msg = f"未找到商品（智能联想结果已全部过滤，平台无匹配商品）。{generic_hint}"
                return SearchResponse(
                    success=False,
                    message=error_msg,
                    error="请尝试调整搜索关键词或预算范围"
                )

            # 进行价格比较
            price_comparisons = recommendation_engine.compare_prices(all_products)

            # 生成推荐
            recommendations = recommendation_engine.recommend_products(
                products=all_products,
                budget_min=request.budget_min,
                budget_max=request.budget_max,
                top_n=request.top_n
            )

            # 计算搜索耗时
            search_time = time.time() - start_time

            # 构建推荐结果
            result = RecommendationResult(
                query=request.query,
                budget_min=request.budget_min,
                budget_max=request.budget_max,
                platforms=request.platforms,
                price_comparisons=price_comparisons,
                recommendations=recommendations,
                total_products_found=len(all_products),
                search_time=search_time
            )

            # 构建成功消息（包含扩展提示，让用户知道我们做了什么）
            success_msg = "搜索成功"
            if generic_hint:
                success_msg = f"搜索成功（{generic_hint}）"

            return SearchResponse(
                success=True,
                message=success_msg,
                data=result
            )

        except Exception as e:
            search_time = time.time() - start_time
            return SearchResponse(
                success=False,
                message=f"搜索失败: {str(e)}",
                error=str(e)
            )
    
    async def get_product_details(self, product_id: str, platform: Platform) -> Optional[Product]:
        """
        获取商品详情
        
        Args:
            product_id: 商品ID
            platform: 平台
        
        Returns:
            商品详情
        """
        if not self.initialized:
            return None
        
        try:
            return await mcp_client.get_product_details(product_id, platform.value)
        except Exception as e:
            print(f"获取商品详情失败: {e}")
            return None
    
    def get_search_history(self) -> List[Dict[str, Any]]:
        """
        获取搜索历史
        
        Returns:
            搜索历史列表
        """
        return self.search_history.copy()
    
    def clear_search_history(self):
        """清空搜索历史"""
        self.search_history.clear()
    
    def get_supported_categories(self) -> List[str]:
        """
        获取支持的商品类别
        
        Returns:
            支持的商品类别列表
        """
        return config.SUPPORTED_CATEGORIES.copy()
    
    def get_supported_platforms(self) -> List[Dict[str, str]]:
        """
        获取支持的平台
        
        Returns:
            支持的平台列表
        """
        return [
            {"id": "jd", "name": "京东", "description": "京东自营，品质保证"},
            {"id": "taobao", "name": "淘宝/天猫", "description": "商品丰富，价格实惠"},
            {"id": "pdd", "name": "拼多多", "description": "拼团优惠，价格更低"}
        ]
    
    def get_recommendation_weights(self) -> Dict[str, float]:
        """
        获取推荐算法权重
        
        Returns:
            推荐算法权重
        """
        return config.RECOMMENDATION_WEIGHTS.copy()
    
    def update_recommendation_weights(self, weights: Dict[str, float]) -> bool:
        """
        更新推荐算法权重
        
        Args:
            weights: 新的权重配置
        
        Returns:
            是否更新成功
        """
        try:
            # 验证权重
            required_keys = ["price", "sales", "shop_reputation", "platform_reliability"]
            for key in required_keys:
                if key not in weights:
                    return False
            
            # 验证权重总和
            total = sum(weights.values())
            if abs(total - 1.0) > 0.01:
                return False
            
            # 更新权重
            config.RECOMMENDATION_WEIGHTS.update(weights)
            recommendation_engine.weights = config.RECOMMENDATION_WEIGHTS
            
            return True
        except Exception as e:
            print(f"更新推荐算法权重失败: {e}")
            return False

# 创建全局Agent实例
agent = TaobaoAgent()