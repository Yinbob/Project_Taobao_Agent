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
    
    async def search_and_recommend(self, request: SearchRequest) -> SearchResponse:
        """
        搜索并推荐商品
        
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
            
            # 搜索商品
            all_products = []
            for platform in request.platforms:
                try:
                    products = await mcp_client.search_products(
                        keyword=request.query,
                        platform=platform.value,
                        price_min=request.budget_min,
                        price_max=request.budget_max
                    )
                    all_products.extend(products)
                except Exception as e:
                    print(f"搜索{platform.value}平台商品失败: {e}")
                    continue
            
            if not all_products:
                return SearchResponse(
                    success=False,
                    message="未找到符合条件的商品",
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
            
            return SearchResponse(
                success=True,
                message="搜索成功",
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